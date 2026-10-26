r"""Jal Parakh pipeline - three agents and a rules engine.

    photo --(1) strip reader [Gemini vision]--> readings + confidence + photo quality
          --(2) rules engine [deterministic, BIS IS 10500]--> Safe / Use with caution / Unsafe / Retake
          --(3) district risk agent [official CGWB data]--> what else to test for here
          --(4) action agent [Gemini, grounded on (2)+(3)]--> fixes, health warnings, complaint draft
    manual entry skips (1).

Async like ProofPay: with a real model the request returns at once (status "reading") and the work
continues in a background thread; the page polls GET /api/tests/{id}. The verdict is published as soon as
the rules engine runs ("advising"), and the advice follows ("done"). With the MockAgent everything is inline.
Fail safe: a reader error or a restart mid-read never produces a verdict (status "error", retake);
an action-agent error falls back to the deterministic bilingual advice.
"""
from __future__ import annotations

import csv
import io
import logging
import secrets
import threading
from datetime import date, datetime, timedelta, timezone

from . import risk as riskmod
from .advice import GRIEVANCE, complaint_draft, template_advice
from .ai import AIError, demo_scenario
from .config import Settings
from .db import DB, REPORT_COLS
from .standards import LIMITS, canonical_key, evaluate

log = logging.getLogger("jalparakh")

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAGIC = [(b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"RIFF", "image/webp")]
IST = timezone(timedelta(hours=5, minutes=30))


class FlowError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def sniff_mime(blob: bytes, declared: str) -> str:
    for magic, mime in MAGIC:
        if blob.startswith(magic):
            return mime
    if blob[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypheif"):
        return "image/heic"
    return declared


class JalParakh:
    def __init__(self, settings: Settings, db: DB, agent):
        self.s = settings
        self.db = db
        self.agent = agent
        self.recover_interrupted()

    # ------------------------------------------------------------ background
    @property
    def ai_is_mock(self) -> bool:
        return getattr(self.agent, "mode", "") == "mock"

    def _spawn(self, fn, *args) -> None:
        def guarded():
            try:
                fn(*args)
            except Exception:  # never let a background crash go silent
                log.exception("Jal Parakh background task %s failed", getattr(fn, "__name__", fn))

        if self.ai_is_mock or self.s.ai_background == "inline":
            guarded()
        else:
            threading.Thread(target=guarded, name=f"jalparakh-{getattr(fn, '__name__', 'ai')}", daemon=True).start()

    def recover_interrupted(self) -> None:
        """Photos live only in memory, so a restart mid-read cannot resume: ask for a retake (no verdict)."""
        for t in self.db.tests_with_status("reading"):
            self.db.update_test(t["id"], status="error", error="restart")
        for t in self.db.tests_with_status("advising"):
            if isinstance(t.get("evaluation"), dict):
                self.db.update_test(t["id"], status="done", advice=template_advice(t["evaluation"], t.get("risk")),
                                    agent="rules (restart)")

    # ---------------------------------------------------------------- place
    def resolve_place(self, state: str = "", district: str = "", pincode: str = "") -> dict:
        place = {"state": None, "district": None, "pincode_via": None}
        if pincode and not district:
            res = riskmod.lookup_pincode(pincode, enabled=self.s.pincode_lookup)
            if res.get("ok"):
                place.update(state=res["state"], district=res.get("district") or None, pincode_via=res["via"])
        st = riskmod.canonical_state(state) if state else None
        if st:
            place["state"] = st
        if district:
            place["district"] = riskmod.canonical_district(place["state"], district.strip()[:60])
        return place

    def risk_for(self, place: dict) -> dict | None:
        if not (place.get("state") or place.get("district")):
            return None
        return riskmod.district_risk(place.get("state"), place.get("district"))

    # ---------------------------------------------------------------- tests
    def create_strip_test(self, blob: bytes, declared_mime: str, filename: str = "", state: str = "",
                          district: str = "", pincode: str = "", lang: str = "hi", practice: bool = False) -> dict:
        if not blob:
            raise FlowError("photo_missing")
        if len(blob) > self.s.max_photo_mb * 1024 * 1024:
            raise FlowError("photo_too_big")
        mime = sniff_mime(blob, (declared_mime or "").lower())
        if mime not in ALLOWED_MIME:
            raise FlowError("photo_type")
        place = self.resolve_place(state, district, pincode)
        is_demo = practice or self.ai_is_mock or bool(demo_scenario(blob))
        test_id = secrets.token_urlsafe(9)
        self.db.insert_test({"id": test_id, "source": "strip", "status": "reading", "lang": lang,
                             "state": place["state"], "district": place["district"], "risk": self.risk_for(place),
                             "is_demo": int(is_demo), "agent": getattr(self.agent, "mode", "")})
        self._spawn(self._run_strip, test_id, blob, mime, filename or "")
        return self.db.get_test(test_id)

    def _run_strip(self, test_id: str, blob: bytes, mime: str, filename: str) -> None:
        t = self.db.get_test(test_id)
        try:
            reading = self.agent.read_strip(mime, blob, filename=filename)
        except (AIError, Exception) as e:  # noqa: BLE001 - any failure -> no verdict, ask for retake
            log.warning("Strip reader failed for %s: %s", test_id, type(e).__name__)
            self.db.update_test(test_id, status="error", error="reader_failed")
            return
        evaluation = evaluate(reading["readings"], image_quality=reading["image_quality"], source="strip",
                              threshold=self.s.confidence_threshold, district_risk=t.get("risk"),
                              overall_confidence=reading["overall_confidence"])
        self._publish_verdict(t, reading, evaluation)

    def create_manual_test(self, values: dict, state: str = "", district: str = "", pincode: str = "",
                           lang: str = "hi", practice: bool = False) -> dict:
        readings = []
        for k, v in (values or {}).items():
            key = canonical_key(k)
            if key is None or v in (None, ""):
                continue
            try:
                val = float(str(v).replace(",", "."))
            except ValueError:
                raise FlowError(f"bad_value:{key}")
            readings.append({"param": key, "value": val, "confidence": 1.0})
        if not readings:
            raise FlowError("no_values")
        place = self.resolve_place(state, district, pincode)
        test_id = secrets.token_urlsafe(9)
        risk = self.risk_for(place)
        self.db.insert_test({"id": test_id, "source": "manual", "status": "reading", "lang": lang,
                             "state": place["state"], "district": place["district"], "risk": risk,
                             "is_demo": int(practice), "agent": "manual entry"})
        evaluation = evaluate(readings, source="manual", threshold=self.s.confidence_threshold, district_risk=risk)
        t = self.db.get_test(test_id)
        self._publish_verdict(t, {"image_quality": "n/a", "overall_confidence": 1.0, "readings": readings,
                                  "notes": "entered by the user"}, evaluation)
        return self.db.get_test(test_id)

    def _publish_verdict(self, t: dict, reading: dict, evaluation: dict) -> None:
        if not self.db.claim(t["id"], "reading", "advising"):
            return
        self.db.update_test(t["id"], reading=reading, evaluation=evaluation)
        self.db.upsert_report({
            "test_id": t["id"], "day": datetime.now(IST).date().isoformat(), "state": t.get("state") or "",
            "district": t.get("district") or "", "source": t["source"], "verdict": evaluation["verdict"],
            "unsafe_params": " ".join(evaluation["unsafe_params"]), "caution_params": " ".join(evaluation["caution_params"]),
            "complaint_drafted": 0, "is_demo": t.get("is_demo", 0),
            "agent": "manual" if t["source"] == "manual" else getattr(self.agent, "mode", ""),
        })
        self._spawn(self._run_advice, t["id"])

    def _run_advice(self, test_id: str) -> None:
        t = self.db.get_test(test_id)
        evaluation, risk = t["evaluation"], t.get("risk")
        try:
            advice = self.agent.advise(evaluation, risk)
        except Exception as e:  # noqa: BLE001 - fall back to the verified template
            log.warning("Action agent failed for %s: %s", test_id, type(e).__name__)
            advice = template_advice(evaluation, risk)
            advice["agent"] = "rules (AI unavailable)"
        if self.db.claim(test_id, "advising", "done"):
            self.db.update_test(test_id, advice=advice)

    def complaint(self, test_id: str, lang: str = "hi") -> dict:
        t = self.db.get_test(test_id)
        if not t:
            raise FlowError("not_found", 404)
        ev = t.get("evaluation")
        if not isinstance(ev, dict) or ev["verdict"] not in ("unsafe", "caution"):
            raise FlowError("complaint_needs_problem")
        today = datetime.now(IST).strftime("%d-%m-%Y")
        place = {"state": t.get("state"), "district": t.get("district")}
        self.db.mark_complaint(test_id)
        return {"lang": lang, "text_hi": complaint_draft(ev, place, "hi", today),
                "text_en": complaint_draft(ev, place, "en", today), "channels": GRIEVANCE,
                "note": "Draft only. Jal Parakh never sends anything."}

    def view(self, t: dict) -> dict:
        ev = t.get("evaluation") if isinstance(t.get("evaluation"), dict) else None
        reading = t.get("reading") if isinstance(t.get("reading"), dict) else None
        return {
            "id": t["id"], "source": t["source"], "status": t["status"], "lang": t.get("lang"),
            "state": t.get("state"), "district": t.get("district"),
            "verdict": ev["verdict"] if ev else None, "evaluation": ev,
            "image_quality": reading.get("image_quality") if reading else None,
            "overall_confidence": reading.get("overall_confidence") if reading else None,
            "risk": t.get("risk"), "advice": t.get("advice") if isinstance(t.get("advice"), dict) else None,
            "agent": t.get("agent"), "error": t.get("error"), "is_demo": bool(t.get("is_demo")),
            "complaint_drafted": bool(t.get("complaint_drafted")), "url": f"/t/{t['id']}",
            "created_at": t.get("created_at"),
        }

    # --------------------------------------------------------------- impact
    def impact(self, include_demo: bool = False) -> dict:
        rows = self.db.reports(include_demo)
        judged = [r for r in rows if r["verdict"] != "retake"]
        by: dict[tuple, dict] = {}
        params: dict[str, int] = {}
        for r in rows:
            key = (r["state"] or "", r["district"] or "")
            b = by.setdefault(key, {"state": key[0], "district": key[1], "tests": 0, "unsafe": 0, "caution": 0,
                                    "safe": 0, "retake": 0, "complaints": 0, "params": {}})
            b["tests"] += 1
            b[r["verdict"]] = b.get(r["verdict"], 0) + 1
            b["complaints"] += int(r["complaint_drafted"] or 0)
            for p in (r["unsafe_params"] or "").split():
                b["params"][p] = b["params"].get(p, 0) + 1
                params[p] = params.get(p, 0) + 1
        districts = []
        for b in by.values():
            j = b["tests"] - b["retake"]
            c = riskmod.coords(b["state"], b["district"])
            districts.append({**b, "unsafe_rate": round(b["unsafe"] / j, 3) if j else None,
                              "lat": c[0] if c else None, "lng": c[1] if c else None,
                              "top_params": sorted(b["params"], key=lambda p: -b["params"][p])[:3]})
        districts.sort(key=lambda d: (-d["tests"], d["state"], d["district"]))
        unsafe = sum(1 for r in judged if r["verdict"] == "unsafe")
        return {
            "counters": {
                "tests_run": len(rows), "unsafe_found": unsafe,
                "caution_found": sum(1 for r in judged if r["verdict"] == "caution"),
                "safe_found": sum(1 for r in judged if r["verdict"] == "safe"),
                "retakes": len(rows) - len(judged),
                "complaints_drafted": sum(int(r["complaint_drafted"] or 0) for r in rows),
                "districts": len([d for d in districts if d["district"] or d["state"]]),
                "unsafe_rate": round(unsafe / len(judged), 3) if judged else None,
            },
            "params": [{"param": p, "name_en": LIMITS[p].name_en, "name_hi": LIMITS[p].name_hi, "count": n}
                       for p, n in sorted(params.items(), key=lambda kv: -kv[1]) if p in LIMITS],
            "districts": districts,
            "recent": rows[:25],
            "include_demo": include_demo,
            "privacy": "District-level only. No photos, names, phone numbers, IP addresses or exact locations are stored.",
        }

    def impact_csv(self, include_demo: bool = False) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id"] + REPORT_COLS)
        for r in reversed(self.db.reports(include_demo)):
            w.writerow([r["id"]] + [r[c] for c in REPORT_COLS])
        return buf.getvalue()

    def import_csv(self, text: str) -> int:
        n = 0
        for r in csv.DictReader(io.StringIO(text)):
            if r.get("verdict") not in ("safe", "caution", "unsafe", "retake"):
                continue
            try:
                date.fromisoformat(r.get("day", ""))
            except ValueError:
                continue
            r["complaint_drafted"] = int(r.get("complaint_drafted") or 0)
            r["is_demo"] = int(r.get("is_demo") or 0)
            self.db.import_report(r)
            n += 1
        return n
