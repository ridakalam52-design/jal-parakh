"""District risk agent: what to test for where you live, from official groundwater data.

Data (bundled, cleaned by scripts/build_dataset.py, see datasets/SOURCES.md):
  * datasets/district_risks.csv  - districts with fluoride (> 1.5 mg/L) and arsenic (> 0.01 mg/L) found in
    parts of their groundwater. CGWB data tabled in Lok Sabha, PIB 24 Mar 2022, Annexure-I:
    https://www.pib.gov.in/PressReleasePage.aspx?PRID=1809264
  * datasets/state_risks.csv     - number of partly affected districts per state for nitrate (> 45 mg/L),
    iron (> 1 mg/L) and salinity. PIB 29 Nov 2021, Annexure-I:
    https://www.pib.gov.in/PressReleasePage.aspx?PRID=1776171
  * datasets/district_centroids.csv - map coordinates only.
Pincode -> district uses the free India Post API (api.postalpincode.in) when PINCODE_LOOKUP=on, with an
offline fallback that maps the first two digits to a state.
"""
from __future__ import annotations

import csv
import difflib
import re
from functools import lru_cache
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
SRC_FA = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1809264"
SRC_SNI = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1776171"

STATES = [
    "Andaman & Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh",
    "Chhattisgarh", "Dadra & Nagar Haveli", "Daman & Diu", "Delhi", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry",
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal",
]
STATE_HI = {
    "Andhra Pradesh": "आंध्र प्रदेश", "Arunachal Pradesh": "अरुणाचल प्रदेश", "Assam": "असम", "Bihar": "बिहार",
    "Chhattisgarh": "छत्तीसगढ़", "Delhi": "दिल्ली", "Goa": "गोवा", "Gujarat": "गुजरात", "Haryana": "हरियाणा",
    "Himachal Pradesh": "हिमाचल प्रदेश", "Jammu & Kashmir": "जम्मू और कश्मीर", "Jharkhand": "झारखंड",
    "Karnataka": "कर्नाटक", "Kerala": "केरल", "Madhya Pradesh": "मध्य प्रदेश", "Maharashtra": "महाराष्ट्र",
    "Manipur": "मणिपुर", "Meghalaya": "मेघालय", "Mizoram": "मिज़ोरम", "Nagaland": "नागालैंड", "Odisha": "ओडिशा",
    "Punjab": "पंजाब", "Rajasthan": "राजस्थान", "Sikkim": "सिक्किम", "Tamil Nadu": "तमिलनाडु",
    "Telangana": "तेलंगाना", "Tripura": "त्रिपुरा", "Uttar Pradesh": "उत्तर प्रदेश", "Uttarakhand": "उत्तराखंड",
    "West Bengal": "पश्चिम बंगाल", "Puducherry": "पुडुचेरी", "Chandigarh": "चंडीगढ़", "Ladakh": "लद्दाख",
}
STATE_ALIASES = {
    "orissa": "Odisha", "uttaranchal": "Uttarakhand", "nctofdelhi": "Delhi", "newdelhi": "Delhi",
    "jammuandkashmir": "Jammu & Kashmir", "jk": "Jammu & Kashmir", "andamanandnicobarislands": "Andaman & Nicobar Islands",
    "andamanandnicobar": "Andaman & Nicobar Islands", "pondicherry": "Puducherry", "up": "Uttar Pradesh",
    "mp": "Madhya Pradesh", "ap": "Andhra Pradesh", "tn": "Tamil Nadu", "wb": "West Bengal",
    "dadraandnagarhaveli": "Dadra & Nagar Haveli", "damananddiu": "Daman & Diu",
    "dadraandnagarhavelianddamananddiu": "Daman & Diu",
}
# First two pincode digits -> state (India Post circles). Offline fallback only; ambiguous prefixes omitted.
PIN_PREFIX = {
    "11": "Delhi", "12": "Haryana", "13": "Haryana", "14": "Punjab", "15": "Punjab", "16": "Punjab",
    "17": "Himachal Pradesh", "18": "Jammu & Kashmir", "19": "Jammu & Kashmir", "20": "Uttar Pradesh",
    "21": "Uttar Pradesh", "22": "Uttar Pradesh", "23": "Uttar Pradesh", "27": "Uttar Pradesh",
    "28": "Uttar Pradesh", "30": "Rajasthan", "31": "Rajasthan", "32": "Rajasthan", "33": "Rajasthan",
    "34": "Rajasthan", "36": "Gujarat", "37": "Gujarat", "38": "Gujarat", "39": "Gujarat", "40": "Maharashtra",
    "41": "Maharashtra", "42": "Maharashtra", "43": "Maharashtra", "44": "Maharashtra", "45": "Madhya Pradesh",
    "46": "Madhya Pradesh", "47": "Madhya Pradesh", "48": "Madhya Pradesh", "49": "Chhattisgarh",
    "50": "Telangana", "51": "Andhra Pradesh", "52": "Andhra Pradesh", "53": "Andhra Pradesh", "56": "Karnataka",
    "57": "Karnataka", "58": "Karnataka", "59": "Karnataka", "60": "Tamil Nadu", "61": "Tamil Nadu",
    "62": "Tamil Nadu", "63": "Tamil Nadu", "64": "Tamil Nadu", "67": "Kerala", "68": "Kerala", "69": "Kerala",
    "70": "West Bengal", "71": "West Bengal", "72": "West Bengal", "73": "West Bengal", "74": "West Bengal",
    "75": "Odisha", "76": "Odisha", "77": "Odisha", "78": "Assam", "80": "Bihar", "81": "Bihar", "84": "Bihar",
    "85": "Bihar", "83": "Jharkhand",
}

PARAM_NAMES = {"fluoride": ("Fluoride", "फ्लोराइड"), "arsenic": ("Arsenic", "आर्सेनिक"),
               "nitrate": ("Nitrate", "नाइट्रेट"), "iron": ("Iron", "आयरन"), "tds": ("Salinity (TDS)", "खारापन (TDS)")}


def norm(s: str) -> str:
    s = (s or "").lower().replace("&", "and")
    s = re.sub(r"\bdistrict\b|\bdist\b|\bzila\b|\bjila\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def canonical_state(raw: str) -> str | None:
    raw = (raw or "").strip()
    for st, hi in STATE_HI.items():
        if raw == hi:
            return st
    n = norm(raw)
    if not n:
        return None
    for st in STATES:
        if norm(st) == n:
            return st
    if n in STATE_ALIASES:
        return STATE_ALIASES[n]
    m = difflib.get_close_matches(n, [norm(s) for s in STATES], n=1, cutoff=0.8)
    if m:
        return next(s for s in STATES if norm(s) == m[0])
    return None


@lru_cache(maxsize=1)
def _data() -> dict:
    districts: dict[str, dict] = {}
    with open(DATA_DIR / "district_risks.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            districts[norm(r["state"]) + "|" + norm(r["district"])] = {
                "state": r["state"], "district": r["district"],
                "fluoride": r["fluoride"] == "1", "arsenic": r["arsenic"] == "1"}
    states: dict[str, dict] = {}
    with open(DATA_DIR / "state_risks.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            states[norm(r["state"])] = {k: int(r[k]) for k in ("salinity_districts", "nitrate_districts", "iron_districts")}
    aliases: dict[str, str] = {}
    with open(DATA_DIR / "district_aliases.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            aliases[norm(r["alias"])] = r["district"]
    cents: dict[str, tuple[float, float]] = {}
    names_by_state: dict[str, set[str]] = {}
    with open(DATA_DIR / "district_centroids.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cents[norm(r["state"]) + "|" + norm(r["district"])] = (float(r["lat"]), float(r["lng"]))
            cents.setdefault("*|" + norm(r["district"]), (float(r["lat"]), float(r["lng"])))
            names_by_state.setdefault(norm(r["state"]), set()).add(r["district"])
    for d in districts.values():
        names_by_state.setdefault(norm(d["state"]), set()).add(d["district"])
    state_cent: dict[str, tuple[float, float]] = {}
    acc: dict[str, list] = {}
    for k, (la, ln) in cents.items():
        st = k.split("|")[0]
        if st != "*":
            acc.setdefault(st, []).append((la, ln))
    for st, pts in acc.items():
        state_cent[st] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    state_cent.setdefault(norm("Ladakh"), (34.15, 77.58))
    return {"districts": districts, "states": states, "aliases": aliases, "cents": cents,
            "names": {k: sorted(v) for k, v in names_by_state.items()}, "state_cent": state_cent}


def district_names(state: str) -> list[str]:
    st = canonical_state(state)
    return _data()["names"].get(norm(st or ""), []) if st else []


def canonical_district(state: str | None, district: str) -> str:
    d = (district or "").strip()
    data = _data()
    n = norm(d)
    if n in data["aliases"]:
        d = data["aliases"][n]
        n = norm(d)
    if state:
        names = data["names"].get(norm(state), [])
        for name in names:
            if norm(name) == n:
                return name
        m = difflib.get_close_matches(n, [norm(x) for x in names], n=1, cutoff=0.82)
        if m:
            return next(x for x in names if norm(x) == m[0])
    return d.title() if d.islower() else d


def coords(state: str | None, district: str | None) -> tuple[float, float] | None:
    data = _data()
    if district:
        c = data["cents"].get(norm(state or "") + "|" + norm(district)) or data["cents"].get("*|" + norm(district))
        if c:
            return c
    if state:
        return data["state_cent"].get(norm(state))
    return None


def lookup_pincode(pincode: str, enabled: bool = True, timeout: float = 6.0) -> dict:
    pin = re.sub(r"\D", "", pincode or "")
    if len(pin) != 6 or pin[0] == "0":
        return {"ok": False, "error": "invalid_pincode"}
    if enabled:
        try:
            r = httpx.get(f"https://api.postalpincode.in/pincode/{pin}", timeout=timeout)
            body = r.json()
            po = (body[0].get("PostOffice") or []) if isinstance(body, list) and body else []
            if po:
                st = canonical_state(po[0].get("State", "")) or po[0].get("State")
                return {"ok": True, "pincode": pin, "state": st,
                        "district": canonical_district(st, po[0].get("District", "")), "via": "India Post API"}
        except Exception:  # noqa: BLE001 - network is optional
            pass
    st = PIN_PREFIX.get(pin[:2])
    if st:
        return {"ok": True, "pincode": pin, "state": st, "district": "", "via": "pincode prefix (offline)"}
    return {"ok": False, "error": "pincode_not_found"}


def district_risk(state: str | None, district: str | None) -> dict:
    """Known groundwater risks for a district (and its state) from the bundled official data."""
    st = canonical_state(state or "") if state else None
    dist = canonical_district(st, district or "") if district else ""
    data = _data()
    row = data["districts"].get(norm(st or "") + "|" + norm(dist)) if dist else None
    if not row and dist and not st:
        row = next((v for k, v in data["districts"].items() if k.endswith("|" + norm(dist))), None)
        if row:
            st = row["state"]
    risks: list[dict] = []
    if row and row["fluoride"]:
        risks.append({"param": "fluoride", "level": "district", "limit": "1.5 mg/L", "source": SRC_FA,
                      "en": f"Fluoride above 1.5 mg/L has been found in parts of {row['district']}'s groundwater (CGWB).",
                      "hi": f"{row['district']} के कुछ हिस्सों के भूजल में फ्लोराइड 1.5 mg/L से ज़्यादा पाया गया है (CGWB)।"})
    if row and row["arsenic"]:
        risks.append({"param": "arsenic", "level": "district", "limit": "0.01 mg/L", "source": SRC_FA,
                      "en": f"Arsenic above 0.01 mg/L has been found in parts of {row['district']}'s groundwater (CGWB).",
                      "hi": f"{row['district']} के कुछ हिस्सों के भूजल में आर्सेनिक 0.01 mg/L से ज़्यादा पाया गया है (CGWB)।"})
    srow = data["states"].get(norm(st or "")) if st else None
    if srow:
        for key, param, lim in (("nitrate_districts", "nitrate", "45 mg/L"), ("iron_districts", "iron", "1 mg/L"),
                                ("salinity_districts", "tds", "EC 3000 µS/cm")):
            n = srow.get(key, 0)
            if n:
                en, hi = PARAM_NAMES[param]
                risks.append({"param": param, "level": "state", "limit": lim, "count": n, "source": SRC_SNI,
                              "en": f"{en}: parts of {n} districts in {st} exceed {lim} (CGWB).",
                              "hi": f"{hi}: {STATE_HI.get(st, st)} के {n} ज़िलों के कुछ हिस्सों में {lim} से ज़्यादा (CGWB)।"})
    test_for = []
    for r in risks:
        if r["param"] not in test_for:
            test_for.append(r["param"])
    for always in ("nitrate", "fluoride", "iron", "ph"):  # cheap strip pads everyone should read
        if always not in test_for:
            test_for.append(always)
    c = coords(st, dist)
    return {
        "state": st, "district": dist or None, "known_district": bool(row),
        "risks": risks, "test_for": test_for,
        "lat": c[0] if c else None, "lng": c[1] if c else None,
        "note_en": ("Official data marks only parts of a district; your own source may be fine or worse. "
                    "Bacteria are not covered by this data - boil or chlorinate if unsure."),
        "note_hi": ("सरकारी आँकड़े ज़िले के कुछ हिस्सों के हैं; आपका स्रोत ठीक भी हो सकता है या खराब भी। "
                    "कीटाणुओं की जानकारी इसमें नहीं है - शक हो तो उबालें या क्लोरीन डालें।"),
        "sources": sorted({r["source"] for r in risks}) or [SRC_FA, SRC_SNI],
    }


def risk_layer() -> list[dict]:
    """All fluoride/arsenic districts with coordinates, for the map's official-data layer."""
    out = []
    for d in _data()["districts"].values():
        c = coords(d["state"], d["district"])
        if c:
            out.append({"state": d["state"], "district": d["district"], "fluoride": d["fluoride"],
                        "arsenic": d["arsenic"], "lat": c[0], "lng": c[1]})
    return out
