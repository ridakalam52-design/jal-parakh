"""AI agents: (1) strip reader (Gemini vision), (2) action agent (Gemini text, grounded on the rules output).

`GeminiAgent` calls the Google Gemini REST API with structured JSON output and a fallback-model chain
(same client as ProofPay). `MockAgent` is a deterministic stand-in used when no key is set, so the demo
and the tests run offline. Neither agent decides the verdict: that is `standards.evaluate` (no AI).
"""
from __future__ import annotations

import base64
import json
import re
import zlib

import httpx

from .advice import GRIEVANCE, summary_calls_safe, template_advice, unsafe_boiling_claim
from .config import DEFAULT_GEMINI_MODEL
from .standards import LIMITS, STRIP_PARAMS, canonical_key

DEMO_MARKER_KEY = "jalparakh_demo"  # PNG tEXt key written into the synthetic demo strips


class AIError(Exception):
    pass


# ---------------------------------------------------------------------------
# Schemas & prompts
# ---------------------------------------------------------------------------
READ_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "image_quality": {"type": "STRING",
                          "enum": ["ok", "blurry", "no_chart", "no_strip", "glare", "too_dark", "not_a_strip"]},
        "chart_visible": {"type": "BOOLEAN"},
        "strip_visible": {"type": "BOOLEAN"},
        "overall_confidence": {"type": "NUMBER", "description": "0.0-1.0"},
        "readings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "param": {"type": "STRING", "description": "one of the parameter keys listed in the prompt"},
                    "label_on_chart": {"type": "STRING"},
                    "chart_scale": {"type": "ARRAY", "items": {"type": "NUMBER"},
                                    "description": "every value printed under this chart row, left to right"},
                    "observed_color": {"type": "STRING", "description": "the pad colour in plain words"},
                    "nearest_low": {"type": "NUMBER",
                                    "description": "chart value of the closest swatch at or below the pad colour"},
                    "nearest_high": {"type": "NUMBER",
                                     "description": "chart value of the closest swatch at or above the pad colour "
                                                    "(equal to nearest_low only for an exact, unambiguous match)"},
                    "value": {"type": "NUMBER", "description": "chosen value in the unit stated in the prompt"},
                    "confidence": {"type": "NUMBER", "description": "0.0-1.0"},
                    "matched_swatch": {"type": "STRING", "description": "the chart swatch label the pad matched"},
                },
                "required": ["param", "observed_color", "nearest_low", "nearest_high", "value", "confidence"],
            },
        },
        "notes": {"type": "STRING"},
    },
    "required": ["image_quality", "chart_visible", "strip_visible", "overall_confidence", "readings"],
}

# A pad that sits between two swatches, or matches neither clearly, gets at most this confidence.
BETWEEN_SWATCH_CONFIDENCE = 0.7

READ_PROMPT = """You are Jal Parakh's water test-strip reader. The photo should show a multi-parameter
drinking-water test strip held next to the colour chart printed on its bottle or pack.
Water safety depends on this reading. Reading a pad too LOW can make dangerous water look safe, so every
doubt must push the reading toward the RISKIER value, never toward the cleaner one.

Step 1 - photo check. Set image_quality:
  "ok" only if BOTH the strip pads and the colour chart are clearly visible and in focus;
  "blurry", "glare", "too_dark" if that stops you matching colours; "no_chart" if the colour chart is not
  in the photo; "no_strip" if no dipped strip is visible; "not_a_strip" if it is not a water test strip.
  Never guess colours from memory of typical charts: if the chart is not visible, use "no_chart".

Step 2 - understand the chart layout before matching anything.
  - The chart has one ROW per parameter (row name on the left). Each row is a line of colour swatches,
    usually 5-7, ordered left to right from the LOWEST concentration (often white/pale) to the HIGHEST.
  - The number printed directly UNDER a swatch is that swatch's value. Do not use the number under the
    neighbouring swatch, and do not shift labels by one position.
  - Copy the row's numbers, left to right, into chart_scale.
  - The strip's pads are in the SAME top-to-bottom order as the chart rows (the first pad below the
    blank handle end is the first chart row). When the strip lies beside the chart, each pad is level with
    its own row. Match each pad only against its own row.

Step 3 - read each pad. For each pad you can see:
  observed_color  describe the pad colour (hue and how light/dark), e.g. "medium magenta-pink".
  Compare it with EVERY swatch in its row. A strongly coloured pad is never the pale first swatch.
  Count which swatch position (1st, 2nd, ...) is closest and read the number under that swatch.
  nearest_low / nearest_high  the chart values of the two swatches the pad colour lies between
                  (the closest swatch at-or-below and at-or-above the pad colour). Set both to the SAME
                  value only when the pad clearly matches one swatch exactly.
  value           the chosen chart value. Safety rule: if the pad is between two swatches or the match is
                  not clear, choose the HIGHER concentration of the two. For pH choose the value FARTHER
                  from 7. Do not interpolate toward the cleaner value.
  param           one of: {params}
  units           report value, nearest_low, nearest_high in: {units}
                  (if the chart reports nitrate as nitrate-NITROGEN, multiply by 4.43 to give mg/L as NO3;
                   ppm = mg/L; for pH report the pH number)
  confidence      0-1. Use 0.9+ only for an exact, unambiguous swatch match. Use at most 0.7 when the pad is
                  between swatches, and below 0.6 when it is between very different swatches, partly hidden,
                  discoloured by light, or you are unsure which chart row it belongs to.
Only report pads you can actually see. Do not invent parameters the strip does not have.
overall_confidence = how sure you are about the whole reading.
When in doubt, lower the confidence: the app will ask the user to retake the photo rather than call the
water safe."""

ADVICE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary_en": {"type": "STRING"}, "summary_hi": {"type": "STRING"},
        "steps_en": {"type": "ARRAY", "items": {"type": "STRING"}},
        "steps_hi": {"type": "ARRAY", "items": {"type": "STRING"}},
        "doctor_en": {"type": "ARRAY", "items": {"type": "STRING"}},
        "doctor_hi": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary_en", "summary_hi", "steps_en", "steps_hi", "doctor_en", "doctor_hi"],
}

ADVICE_PROMPT = """You are Jal Parakh's action agent for rural and small-town India. A deterministic rules
engine has ALREADY judged the water against BIS IS 10500:2012. Do not change or second-guess the verdict.

Rules-engine result (JSON):
{evaluation}

Known groundwater risks for the user's district (official CGWB data):
{risk}

Verified treatment facts you must stay consistent with:
{facts}

Write advice that is read aloud on a cheap phone:
- summary_en / summary_hi: 2-3 short sentences: the verdict, the main problem, the cheapest effective fix.
- steps_en / steps_hi: 3-6 short action steps, cheapest effective option first.
- doctor_en / doctor_hi: when to see a doctor (specific symptoms), 1-3 items.
Hard rules:
- Boiling kills germs but does NOT remove fluoride, arsenic, nitrate, nitrite, lead or iron. Never imply it does.
- RO removes fluoride, arsenic, nitrate, lead and salts; activated alumina is for fluoride (and arsenic);
  Jal Jeevan Mission community water purification plants serve fluoride/arsenic villages; chlorine tablets
  and boiling are for germs only.
- A strip cannot detect bacteria; if the verdict is safe, say it is safe on the tested parameters only.
- If the verdict is "retake", tell the user how to take a better photo and to treat the water as unsafe until then.
- Simple words, no jargon, no brand names, no prices you are not sure of. Hindi in Devanagari, natural
  everyday Hindi (not overly Sanskritised). Short sentences."""


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
class GeminiAgent:
    """Gemini REST client (same design as ProofPay's).

    Calls are slow on cold/free infrastructure (minutes are possible), so the app runs them in a
    background thread: the per-call `timeout` and the total retry `budget` can be generous.
    The primary model is tried first, then each comma-separated GEMINI_FALLBACK_MODEL.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, transport: httpx.BaseTransport | None = None,
                 fallback_model: str = "", timeout: float = 150.0, budget: float = 330.0,
                 retry_sleep: float = 1.0):
        self.api_key = api_key
        self.model = model
        self.fallback_model = (fallback_model or "").strip()
        self.mode = f"gemini:{model}"
        self.budget = budget
        self.timeout = timeout
        self.retry_sleep = retry_sleep
        self._thinking_ok: dict[str, bool] = {}  # per model: does it accept thinkingConfig?
        self._http = httpx.Client(
            base_url="https://generativelanguage.googleapis.com", timeout=timeout, transport=transport
        )

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    def list_flash_models(self, timeout: float = 8.0) -> list[str]:
        """Model names available to this key that contain 'flash' (for a startup log line)."""
        r = self._http.get("/v1beta/models", params={"pageSize": 1000}, headers=self._headers(), timeout=timeout)
        r.raise_for_status()
        names = [str(m.get("name", "")).removeprefix("models/") for m in (r.json().get("models") or [])]
        return sorted(n for n in names if "flash" in n.lower())

    def _call_model(self, model: str, parts: list[dict], schema: dict, deadline: float,
                    max_attempts: int = 3) -> httpx.Response:
        """POST generateContent with retries. Returns the last response; raises AIError on transport failure."""
        import time
        gen = {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        }
        if self._thinking_ok.get(model, True):
            # Fast path: minimal reasoning keeps responses snappy on the free tier.
            gen["thinkingConfig"] = {"thinkingLevel": "low"}
        body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen}
        attempt = 0
        while True:
            attempt += 1
            remaining = deadline - time.monotonic()
            # never let one call run past the total budget
            call_timeout = max(5.0, min(self.timeout, remaining))
            try:
                r = self._http.post(f"/v1beta/models/{model}:generateContent", json=body, headers=self._headers(),
                                    timeout=call_timeout)
            except httpx.HTTPError as e:
                if attempt >= max_attempts or deadline - time.monotonic() < 10:
                    raise AIError(f"Gemini request failed ({model}): {type(e).__name__} {e}".strip()) from e
                time.sleep(self.retry_sleep * attempt)
                continue
            if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in gen:
                # Model doesn't support thinking control: remember and retry without it (not an attempt).
                self._thinking_ok[model] = False
                gen.pop("thinkingConfig", None)
                attempt -= 1
                continue
            if (r.status_code in (429, 500, 503) and attempt < max_attempts
                    and time.monotonic() + 2 < deadline):
                time.sleep(self.retry_sleep * attempt)
                continue
            return r

    @staticmethod
    def _error(r: httpx.Response, model: str) -> AIError:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:300])
        except ValueError:
            msg = r.text[:300]
        return AIError(f"Gemini API {r.status_code} ({model}): {msg}")

    def _generate(self, parts: list[dict], schema: dict) -> dict:
        import time
        deadline = time.monotonic() + self.budget  # total budget; after this the app falls back safely
        # Try the primary model, then each fallback (comma-separated GEMINI_FALLBACK_MODEL),
        # moving on when a model is missing, overloaded, out of quota, or times out.
        models = [self.model] + [m.strip() for m in self.fallback_model.split(",")
                                 if m.strip() and m.strip() != self.model]
        errors: list[str] = []
        r = None
        used = self.model
        for i, model in enumerate(models):
            used = model
            last = i == len(models) - 1
            try:
                r = self._call_model(model, parts, schema,
                                     deadline if i == 0 else max(deadline, time.monotonic() + 60),
                                     max_attempts=3 if i == 0 else 1)
            except AIError as e:
                errors.append(str(e))
                if last:
                    raise AIError("; ".join(errors)) from e
                continue
            if r.status_code == 200:
                break
            if r.status_code in (404, 429, 500, 503) and not last:
                errors.append(str(self._error(r, model)))
                continue
            errors.append(str(self._error(r, model)))
            raise AIError("; ".join(errors))
        data = r.json()
        try:
            cand = data["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"] if not p.get("thought"))
        except (KeyError, IndexError):
            reason = (data.get("promptFeedback") or {}).get("blockReason") or "no candidates"
            raise AIError(f"Gemini returned no content ({reason})")
        return _loads_json(text)


    # ------------------------------------------------------------------ agents
    def read_strip(self, mime: str, blob: bytes, filename: str = "") -> dict:
        prompt = READ_PROMPT.format(
            params=", ".join(STRIP_PARAMS),
            units="; ".join(f"{k}: {LIMITS[k].unit or 'pH units'}" for k in STRIP_PARAMS),
        )
        parts = [{"text": prompt}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(blob).decode()}}]
        return normalize_reading(self._generate(parts, READ_SCHEMA))

    def advise(self, evaluation: dict, risk: dict | None = None) -> dict:
        base = template_advice(evaluation, risk)
        slim = {k: evaluation[k] for k in ("verdict", "unsafe_params", "caution_params", "uncertain_params",
                                            "retake_reasons", "untested_district_risks")}
        slim["results"] = [{k: r[k] for k in ("param", "value", "status", "reason_en", "limit")}
                           for r in evaluation["results"]]
        risk_slim = [r["en"] for r in (risk or {}).get("risks", [])] or ["none known"]
        facts = base["steps_en"] + base["health_en"] + [base["germs_en"]]
        prompt = ADVICE_PROMPT.format(evaluation=json.dumps(slim, ensure_ascii=False), risk="\n".join(risk_slim),
                                      facts="\n".join(f"- {f}" for f in facts))
        out = self._generate([{"text": prompt}], ADVICE_SCHEMA)
        return merge_advice(base, out, self.mode, evaluation.get("verdict"))


# ---------------------------------------------------------------------------
# Deterministic mock
# ---------------------------------------------------------------------------
SCENARIOS = {
    "safe": {"image_quality": "ok", "overall_confidence": 0.9, "readings": [
        ("ph", 7.0, .9), ("total_hardness", 120, .85), ("total_alkalinity", 120, .85), ("nitrate", 10, .88),
        ("nitrite", 0, .9), ("free_chlorine", 0.5, .86), ("iron", 0, .9), ("fluoride", 0.5, .82),
        ("lead", 0, .8)]},
    "fluoride": {"image_quality": "ok", "overall_confidence": 0.86, "readings": [
        ("ph", 8.0, .9), ("total_hardness", 250, .82), ("total_alkalinity", 240, .8), ("nitrate", 10, .86),
        ("nitrite", 0, .9), ("free_chlorine", 0, .88), ("iron", 0, .9), ("fluoride", 2.0, .84), ("lead", 0, .8)]},
    "nitrate": {"image_quality": "ok", "overall_confidence": 0.85, "readings": [
        ("ph", 7.0, .9), ("total_hardness", 120, .84), ("total_alkalinity", 120, .82), ("nitrate", 100, .83),
        ("nitrite", 1.0, .78), ("free_chlorine", 0, .88), ("iron", 3.0, .81), ("fluoride", 0.5, .8),
        ("lead", 0, .8)]},
    "uncertain": {"image_quality": "ok", "overall_confidence": 0.55, "readings": [
        ("ph", 7.0, .8), ("total_hardness", 120, .5), ("nitrate", 25, .45), ("fluoride", 1.0, .4),
        ("iron", 0, .7)]},
    "blurry": {"image_quality": "blurry", "overall_confidence": 0.2, "readings": []},
    "no_chart": {"image_quality": "no_chart", "overall_confidence": 0.2, "readings": []},
}
SCENARIO_WORDS = [("blur", "blurry"), ("nochart", "no_chart"), ("no_chart", "no_chart"), ("unsure", "uncertain"),
                  ("uncertain", "uncertain"), ("fluor", "fluoride"), ("nitrate", "nitrate"), ("iron", "nitrate"),
                  ("safe", "safe")]


def png_text(blob: bytes) -> dict[str, str]:
    """Read tEXt chunks of a PNG (used to recognise the synthetic demo strips). Empty for other formats."""
    out: dict[str, str] = {}
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return out
    i = 8
    while i + 8 <= len(blob):
        length = int.from_bytes(blob[i:i + 4], "big")
        ctype = blob[i + 4:i + 8]
        data = blob[i + 8:i + 8 + length]
        if ctype == b"tEXt" and b"\x00" in data:
            k, v = data.split(b"\x00", 1)
            out[k.decode("latin-1")] = v.decode("latin-1")
        elif ctype == b"zTXt" and b"\x00" in data:
            k, v = data.split(b"\x00", 1)
            try:
                out[k.decode("latin-1")] = zlib.decompress(v[1:]).decode("latin-1")
            except zlib.error:
                pass
        if ctype == b"IEND":
            break
        i += 12 + length
    return out


def demo_scenario(blob: bytes, filename: str = "") -> str | None:
    """Scenario name if the image is one of our synthetic demo strips (PNG tEXt marker)."""
    return png_text(blob).get(DEMO_MARKER_KEY) or None


class MockAgent:
    """Deterministic agent so the demo works without any API key.

    Strip reading:
      - a synthetic demo strip (PNG tEXt 'jalparakh_demo') returns its scenario's readings
      - otherwise the file name decides: 'blur' -> blurry, 'nochart' -> no chart, 'unsure' -> low confidence,
        'fluor' -> high fluoride, 'nitrate'/'iron' -> high nitrate + iron, anything else -> a safe reading
    Advice: the rules-based bilingual template (exactly what users get when Gemini is unavailable).
    """

    mode = "mock"

    def read_strip(self, mime: str, blob: bytes, filename: str = "") -> dict:
        name = demo_scenario(blob, filename)
        if not name:
            low = (filename or "").lower()
            name = next((sc for word, sc in SCENARIO_WORDS if word in low), "safe")
        sc = SCENARIOS.get(name, SCENARIOS["safe"])
        return normalize_reading({
            "image_quality": sc["image_quality"], "chart_visible": sc["image_quality"] != "no_chart",
            "strip_visible": True, "overall_confidence": sc["overall_confidence"],
            "readings": [{"param": p, "value": v, "confidence": c} for p, v, c in sc["readings"]],
            "notes": f"mock reader: scenario '{name}'",
        })

    def advise(self, evaluation: dict, risk: dict | None = None) -> dict:
        out = template_advice(evaluation, risk)
        out["agent"] = "rules (mock)"
        return out


# ---------------------------------------------------------------------------
# Normalisation (never trust model output blindly)
# ---------------------------------------------------------------------------
def _loads_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        data = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise AIError("Model did not return JSON")
        data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise AIError("Model returned non-object JSON")
    return data


def _clamp(x, lo=0.0, hi=1.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    if v > 1.0 and hi == 1.0 and v <= 100:  # model answered in percent
        v = v / 100
    return max(lo, min(hi, v))


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None  # drop NaN/inf


def _riskier(key: str, a: float, b: float) -> float:
    """The value that is worse for safety: farther from neutral for pH, the higher concentration otherwise."""
    if key == "ph":
        return a if abs(a - 7.0) > abs(b - 7.0) else b if abs(b - 7.0) > abs(a - 7.0) else min(a, b)
    return max(a, b)


def safety_round(key: str, value: float | None, confidence: float, nearest_low, nearest_high
                 ) -> tuple[float | None, float, bool]:
    """Enforce safety-biased rounding in code (the prompt asks for it, but the model is not trusted).

    If the reader reports two different nearest swatches, the pad is between them: the value becomes the
    riskier swatch (or the model's own value if that is riskier still) and confidence is capped at
    BETWEEN_SWATCH_CONFIDENCE. Returns (value, confidence, was_between). Old-shape readings without
    nearest_low/high pass through unchanged.
    """
    lo, hi = _num(nearest_low), _num(nearest_high)
    if lo is None and hi is None:
        return value, confidence, False
    if lo is None or hi is None:  # only one swatch named: never report cleaner than it
        only = lo if lo is not None else hi
        return (only if value is None else _riskier(key, value, only)), confidence, False
    if lo == hi:
        return (lo if value is None else _riskier(key, value, lo)), confidence, False
    risky = _riskier(key, lo, hi)
    if value is not None:
        risky = _riskier(key, value, risky)
    return risky, min(confidence, BETWEEN_SWATCH_CONFIDENCE), True


def normalize_reading(d: dict) -> dict:
    q = str(d.get("image_quality") or "ok").lower().strip()
    if q not in {"ok", "blurry", "no_chart", "no_strip", "glare", "too_dark", "not_a_strip"}:
        q = "blurry"
    if q == "ok" and d.get("chart_visible") is False:
        q = "no_chart"  # model contradicted itself; fail safe
    if q == "ok" and d.get("strip_visible") is False:
        q = "no_strip"
    readings = []
    seen = set()
    for r in d.get("readings") or []:
        if not isinstance(r, dict):
            continue
        key = canonical_key(r.get("param") or r.get("label_on_chart"))
        if not key or key in seen:
            continue
        seen.add(key)
        value, conf, between = safety_round(key, _num(r.get("value")), _clamp(r.get("confidence", 0)),
                                            r.get("nearest_low"), r.get("nearest_high"))
        out = {"param": key, "value": value, "confidence": round(conf, 2),
               "matched_swatch": str(r.get("matched_swatch") or "")[:40]}
        if "nearest_low" in r or "nearest_high" in r or "observed_color" in r:
            out.update({"observed_color": str(r.get("observed_color") or "")[:60],
                        "nearest_low": _num(r.get("nearest_low")), "nearest_high": _num(r.get("nearest_high")),
                        "between_swatches": between})
        readings.append(out)
    return {"image_quality": q, "overall_confidence": round(_clamp(d.get("overall_confidence", 0)), 2),
            "readings": readings, "notes": str(d.get("notes") or "")[:400]}


def _strs(x, n=8, ln=300) -> list[str]:
    return [str(s).strip()[:ln] for s in (x or []) if str(s).strip()][:n]


def merge_advice(base: dict, out: dict, mode: str, verdict: str | None = None) -> dict:
    """Use the model's wording only if it passes the safety checks; the facts always come from `base`.

    If the verdict is not "safe" but the model's summary calls the water safe ("safe to use but..."),
    the summary (EN + HI together) is replaced by the verified template summary.
    """
    cand = {
        "summary_en": str(out.get("summary_en") or "").strip()[:600],
        "summary_hi": str(out.get("summary_hi") or "").strip()[:600],
        "steps_en": _strs(out.get("steps_en")), "steps_hi": _strs(out.get("steps_hi")),
        "doctor_en": _strs(out.get("doctor_en"), 4), "doctor_hi": _strs(out.get("doctor_hi"), 4),
    }
    text = " ".join([cand["summary_en"], cand["summary_hi"], *cand["steps_en"], *cand["steps_hi"]])
    if not cand["summary_en"] or not cand["summary_hi"] or not cand["steps_en"] or unsafe_boiling_claim(text):
        res = dict(base)
        res["agent"] = "rules (model output rejected)"
        return res
    if verdict and verdict != "safe" and (summary_calls_safe(cand["summary_en"], "en")
                                          or summary_calls_safe(cand["summary_hi"], "hi")):
        cand["summary_en"], cand["summary_hi"] = base["summary_en"], base["summary_hi"]
    res = dict(base)
    res.update({k: v for k, v in cand.items() if v})
    res["facts_en"], res["facts_hi"] = base["steps_en"], base["steps_hi"]
    res["agent"] = mode
    return res


__all__ = ["AIError", "GeminiAgent", "MockAgent", "normalize_reading", "safety_round", "merge_advice", "demo_scenario",
           "png_text", "GRIEVANCE"]
