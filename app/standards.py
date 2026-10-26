"""Deterministic rules engine: strip readings -> BIS IS 10500:2012 verdict.

No AI here. Every verdict can be traced to a number in LIMITS and a rule in `evaluate`.

Source of the limits
--------------------
Bureau of Indian Standards, IS 10500:2012 "Drinking Water - Specification (Second Revision)",
including Amendment No. 1 (June 2015), which set iron to 1.0 mg/L and removed the arsenic relaxation.
  * BIS copy:  https://www.bis.gov.in/other/DrinWatIS10500.pdf
  * CPCB copy: https://cpcb.nic.in/wqm/BIS_Drinking_Water_Specification.pdf
  * Extract tabled in Parliament (PIB, 21 Jul 2022): https://www.pib.gov.in/PressReleasePage.aspx?PRID=1843385
"Acceptable" = the requirement. "Permissible" = the limit tolerated only in the absence of an alternate
source; above it BIS says the source has to be rejected. `None` means "no relaxation".

Nitrite is not in IS 10500, so the WHO Guidelines for Drinking-water Quality (4th ed., 2017 + addenda)
value of 3 mg/L (as NO2-) is used and labelled as WHO.
https://www.who.int/publications/i/item/9789240045064

How a verdict is reached (Jal Parakh policy, documented in the README)
--------------------------------------------------------------------
Per parameter:
  ok         within the acceptable limit
  caution    above acceptable, within permissible (or a non-health parameter above its limit)
  unsafe     a HEALTH parameter above its permissible / no-relaxation limit, or an extreme pH / chlorine
  low        below a minimum that only matters for treated supply (free residual chlorine < 0.2)
  uncertain  the reader's confidence is below the threshold -> this pad must be re-read
Overall:
  1. Photo not usable (blurry, no colour chart, no strip, glare, too dark)          -> RETAKE
  2. Any CONFIDENT unsafe parameter                                                  -> UNSAFE
     (a confident danger signal is never hidden behind a retake)
  3. Any uncertain parameter, or too few pads read                                   -> RETAKE
     (water is never called safe or "use with caution" on a low-confidence read)
  4. Any caution parameter                                                           -> CAUTION
  5. Otherwise                                                                       -> SAFE (on the tested parameters only)
"""
from __future__ import annotations

from dataclasses import dataclass

BIS_SOURCE = "BIS IS 10500:2012 (incl. Amendment 1, 2015) - https://www.bis.gov.in/other/DrinWatIS10500.pdf"
WHO_SOURCE = "WHO Guidelines for Drinking-water Quality, 4th ed. - https://www.who.int/publications/i/item/9789240045064"

VERDICTS = ("safe", "caution", "unsafe", "retake")
DEFAULT_CONFIDENCE_THRESHOLD = 0.6
MIN_STRIP_PADS = 3  # a strip photo must yield at least this many confident readings to be called safe
BAD_QUALITY = ("blurry", "no_chart", "no_strip", "glare", "too_dark", "not_a_strip")


@dataclass(frozen=True)
class Limit:
    key: str
    name_en: str
    name_hi: str
    unit: str
    acceptable: float | None          # max (or the range low for pH)
    permissible: float | None         # None = no relaxation
    health: bool                      # health-relevant (unsafe when over the limit) vs aesthetic/operational
    source: str = BIS_SOURCE
    low: float | None = None          # minimum (pH range low / chlorine minimum)
    unsafe_above: float | None = None # extreme value that makes even a non-health parameter unsafe
    unsafe_below: float | None = None
    plausible_max: float = 10000.0
    note_en: str = ""
    note_hi: str = ""


LIMITS: dict[str, Limit] = {l.key: l for l in [
    Limit("ph", "pH", "पीएच (pH)", "", 8.5, None, False, low=6.5, unsafe_below=5.0, unsafe_above=10.0,
          plausible_max=14, note_en="Outside 6.5-8.5 the water can be corrosive or bitter; it is mainly a sign of other problems.",
          note_hi="6.5-8.5 से बाहर पानी पाइप को खराब कर सकता है या कड़वा लग सकता है; यह दूसरी गड़बड़ी का संकेत भी है।"),
    Limit("total_hardness", "Total hardness", "कुल कठोरता (हार्डनेस)", "mg/L as CaCO3", 200, 600, False, plausible_max=2000,
          note_en="Hard water causes scaling and a salty taste; not a direct health risk.",
          note_hi="कठोर पानी से बर्तनों में सफेद परत जमती है; यह सीधा स्वास्थ्य खतरा नहीं है।"),
    Limit("total_alkalinity", "Total alkalinity", "कुल क्षारीयता", "mg/L as CaCO3", 200, 600, False, plausible_max=2000,
          note_en="High alkalinity gives a soda taste and scaling.", note_hi="ज़्यादा क्षारीयता से स्वाद खराब और परत जमती है।"),
    Limit("nitrate", "Nitrate", "नाइट्रेट", "mg/L as NO3", 45, None, True, plausible_max=1000,
          note_en="Dangerous for babies under 6 months (blue baby syndrome). Comes from fertiliser and sewage.",
          note_hi="6 महीने से छोटे बच्चों के लिए खतरनाक (ब्लू बेबी)। खाद और गंदे पानी से आता है।"),
    Limit("nitrite", "Nitrite", "नाइट्राइट", "mg/L as NO2", 3, None, True, source=WHO_SOURCE, plausible_max=100,
          note_en="Not in IS 10500; WHO limit used. Signals fresh sewage or fertiliser contamination.",
          note_hi="IS 10500 में नहीं है; WHO सीमा ली गई है। ताज़ा गंदगी या खाद मिलने का संकेत।"),
    Limit("free_chlorine", "Free residual chlorine", "मुक्त क्लोरीन", "mg/L", 1.0, None, False, low=0.2,
          unsafe_above=5.0, plausible_max=20,
          note_en="0.2-1 mg/L in tap supply shows it was disinfected. Above 5 mg/L (WHO) is too much.",
          note_hi="नल के पानी में 0.2-1 mg/L का मतलब पानी कीटाणु-रहित किया गया है। 5 mg/L से ज़्यादा बहुत अधिक है।"),
    Limit("iron", "Iron", "आयरन (लोहा)", "mg/L", 1.0, None, False, plausible_max=50,
          note_en="Reddish colour, metallic taste and stains. Mainly aesthetic, but BIS gives no relaxation.",
          note_hi="लाल/पीला रंग, धातु जैसा स्वाद और दाग। मुख्यतः स्वाद की समस्या, पर BIS कोई छूट नहीं देता।"),
    Limit("fluoride", "Fluoride", "फ्लोराइड", "mg/L", 1.0, 1.5, True, plausible_max=50,
          note_en="Above 1.5 mg/L for years causes dental and skeletal fluorosis (stained teeth, stiff bones).",
          note_hi="1.5 mg/L से ज़्यादा लंबे समय तक पीने से दाँतों पर दाग और हड्डियों का फ्लोरोसिस होता है।"),
    Limit("lead", "Lead", "लेड (सीसा)", "mg/L", 0.01, None, True, plausible_max=10,
          note_en="No safe level, especially for children and pregnancy (brain development).",
          note_hi="कोई सुरक्षित मात्रा नहीं, खासकर बच्चों और गर्भवती महिलाओं के लिए।"),
    Limit("arsenic", "Arsenic", "आर्सेनिक", "mg/L", 0.01, None, True, plausible_max=10,
          note_en="Long-term exposure causes skin lesions and cancers.",
          note_hi="लंबे समय तक पीने से त्वचा पर धब्बे और कैंसर हो सकता है।"),
    Limit("copper", "Copper", "कॉपर (ताँबा)", "mg/L", 0.05, 1.5, True, plausible_max=50,
          note_en="High copper causes stomach upset.", note_hi="ज़्यादा ताँबे से पेट खराब होता है।"),
    Limit("tds", "Total dissolved solids", "कुल घुलित ठोस (TDS)", "mg/L", 500, 2000, False, plausible_max=20000,
          note_en="High TDS = salty/brackish water.", note_hi="ज़्यादा TDS = खारा पानी।"),
    Limit("chloride", "Chloride", "क्लोराइड", "mg/L", 250, 1000, False, plausible_max=20000,
          note_en="Salty taste; corrodes pipes.", note_hi="नमकीन स्वाद; पाइप में जंग।"),
    Limit("sulphate", "Sulphate", "सल्फेट", "mg/L", 200, 400, False, plausible_max=5000,
          note_en="Laxative effect at high levels.", note_hi="ज़्यादा मात्रा में दस्त जैसा असर।"),
    Limit("manganese", "Manganese", "मैंगनीज़", "mg/L", 0.1, 0.3, False, plausible_max=50,
          note_en="Black stains and bitter taste.", note_hi="काले दाग और कड़वा स्वाद।"),
]}

# Pads printed on common 9-16 in 1 drinking-water strips, in the order we ask the reader for.
STRIP_PARAMS = ["ph", "total_hardness", "total_alkalinity", "nitrate", "nitrite", "free_chlorine", "iron",
                "fluoride", "lead", "copper", "arsenic", "tds", "chloride", "sulphate", "manganese"]

ALIASES = {
    "hardness": "total_hardness", "th": "total_hardness", "alkalinity": "total_alkalinity", "ta": "total_alkalinity",
    "chlorine": "free_chlorine", "free chlorine": "free_chlorine", "residual chlorine": "free_chlorine",
    "cl2": "free_chlorine", "no3": "nitrate", "no2": "nitrite", "fe": "iron", "f": "fluoride", "pb": "lead",
    "cu": "copper", "as": "arsenic", "mn": "manganese", "so4": "sulphate", "sulfate": "sulphate", "cl": "chloride",
}


def canonical_key(raw: str) -> str | None:
    k = str(raw or "").strip().lower().replace("-", "_")
    k2 = k.replace("_", " ")
    if k in LIMITS:
        return k
    if k2 in ALIASES:
        return ALIASES[k2]
    if k in ALIASES:
        return ALIASES[k]
    k3 = k2.replace("total ", "").strip()
    return ALIASES.get(k3) or (("total_" + k3.replace(" ", "_")) if ("total_" + k3.replace(" ", "_")) in LIMITS else None)


def fmt(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{v:g}"


def limit_text(lim: Limit) -> str:
    """Short limit label, e.g. '≤ 1 (max 1.5)'; '≤ 45 (no relaxation)'."""
    if lim.key == "ph":
        return "6.5-8.5"
    if lim.key == "free_chlorine":
        return "0.2-1"
    if lim.permissible is None:
        return f"≤ {fmt(lim.acceptable)}"
    return f"≤ {fmt(lim.acceptable)} (max {fmt(lim.permissible)})"


def classify(lim: Limit, value: float) -> tuple[str, str, str]:
    """Return (status, reason_en, reason_hi) for one confident reading."""
    u = f" {lim.unit}" if lim.unit else ""
    v = fmt(value)
    if lim.unsafe_above is not None and value > lim.unsafe_above:
        return ("unsafe", f"{lim.name_en} {v}{u} is far above the safe range (> {fmt(lim.unsafe_above)}).",
                f"{lim.name_hi} {v}{u} सुरक्षित सीमा से बहुत ज़्यादा है (> {fmt(lim.unsafe_above)})।")
    if lim.unsafe_below is not None and value < lim.unsafe_below:
        return ("unsafe", f"{lim.name_en} {v} is far below the safe range (< {fmt(lim.unsafe_below)}).",
                f"{lim.name_hi} {v} सुरक्षित सीमा से बहुत कम है (< {fmt(lim.unsafe_below)})।")
    if lim.key == "ph":
        if value < lim.low or value > lim.acceptable:
            return ("caution", f"pH {v} is outside the BIS range 6.5-8.5.", f"pH {v} BIS सीमा 6.5-8.5 से बाहर है।")
        return ("ok", f"pH {v} is within 6.5-8.5.", f"pH {v} सही सीमा (6.5-8.5) में है।")
    if lim.key == "free_chlorine":
        if value > lim.acceptable:
            return ("caution", f"Free chlorine {v}{u} is above the BIS maximum of 1 mg/L (strong taste).",
                    f"मुक्त क्लोरीन {v}{u} BIS की अधिकतम सीमा 1 mg/L से ज़्यादा है।")
        if value < lim.low:
            return ("low", f"Free chlorine {v}{u}: no disinfectant left. Fine for well water, but tap supply should "
                           f"carry 0.2-1 mg/L; germs are possible.",
                    f"मुक्त क्लोरीन {v}{u}: कीटाणुनाशक नहीं बचा। नल के पानी में 0.2-1 mg/L होना चाहिए; कीटाणु हो सकते हैं।")
        return ("ok", f"Free chlorine {v}{u} is in the 0.2-1 mg/L range.", f"मुक्त क्लोरीन {v}{u} सही सीमा में है।")
    hard_limit = lim.permissible if lim.permissible is not None else lim.acceptable
    if value > hard_limit:
        if lim.health:
            return ("unsafe", f"{lim.name_en} {v}{u} is above the {'BIS' if lim.source == BIS_SOURCE else 'WHO'} "
                              f"limit of {fmt(hard_limit)}{u}.",
                    f"{lim.name_hi} {v}{u} सीमा {fmt(hard_limit)}{u} से ज़्यादा है।")
        return ("caution", f"{lim.name_en} {v}{u} is above the BIS limit of {fmt(hard_limit)}{u} "
                           f"(taste/scaling problem, not an immediate health risk).",
                f"{lim.name_hi} {v}{u} BIS सीमा {fmt(hard_limit)}{u} से ज़्यादा है (स्वाद/परत की समस्या, तुरंत खतरा नहीं)।")
    if value > lim.acceptable:
        return ("caution", f"{lim.name_en} {v}{u} is above the acceptable {fmt(lim.acceptable)}{u} but within the "
                           f"permissible {fmt(lim.permissible)}{u} - use only if there is no other source.",
                f"{lim.name_hi} {v}{u} स्वीकार्य सीमा {fmt(lim.acceptable)}{u} से ज़्यादा है पर {fmt(lim.permissible)}{u} "
                f"के अंदर - दूसरा स्रोत न हो तभी पिएँ।")
    return ("ok", f"{lim.name_en} {v}{u} is within the acceptable limit ({fmt(lim.acceptable)}{u}).",
            f"{lim.name_hi} {v}{u} स्वीकार्य सीमा में है।")


def evaluate(readings: list[dict], image_quality: str = "ok", source: str = "strip",
             threshold: float = DEFAULT_CONFIDENCE_THRESHOLD, district_risk: dict | None = None,
             overall_confidence: float | None = None) -> dict:
    """Readings: [{"param": "fluoride", "value": 2.0, "confidence": 0.8}, ...] -> verdict dict."""
    results: list[dict] = []
    seen: set[str] = set()
    for r in readings or []:
        key = canonical_key(r.get("param"))
        if not key or key in seen:
            continue
        lim = LIMITS[key]
        try:
            value = float(r.get("value"))
        except (TypeError, ValueError):
            value = None
        try:
            conf = max(0.0, min(1.0, float(r.get("confidence", 0))))
        except (TypeError, ValueError):
            conf = 0.0
        if value is None or value < 0 or value > lim.plausible_max:
            status, en, hi = "uncertain", f"{lim.name_en}: the reading was not a plausible number.", \
                f"{lim.name_hi}: पढ़ा गया मान सही नहीं लगता।"
            value = None
        elif conf < threshold:
            status = "uncertain"
            en = f"{lim.name_en}: not sure about this pad (confidence {round(conf * 100)}%). Please retake the photo."
            hi = f"{lim.name_hi}: इस पैड को ठीक से नहीं पढ़ पाए (भरोसा {round(conf * 100)}%)। कृपया फिर से फोटो लें।"
        else:
            status, en, hi = classify(lim, value)
        seen.add(key)
        results.append({
            "param": key, "name_en": lim.name_en, "name_hi": lim.name_hi, "unit": lim.unit,
            "value": value, "confidence": round(conf, 2), "status": status,
            "reason_en": en, "reason_hi": hi, "limit": limit_text(lim), "health": lim.health,
            "source": "WHO" if lim.source == WHO_SOURCE else "BIS IS 10500:2012",
            "note_en": lim.note_en, "note_hi": lim.note_hi,
        })
    order = {k: i for i, k in enumerate(STRIP_PARAMS)}
    results.sort(key=lambda x: order.get(x["param"], 99))

    unsafe = [x for x in results if x["status"] == "unsafe"]
    caution = [x for x in results if x["status"] == "caution"]
    uncertain = [x for x in results if x["status"] == "uncertain"]
    confident = [x for x in results if x["status"] != "uncertain"]
    min_pads = MIN_STRIP_PADS if source == "strip" else 1
    retake_reasons: list[str] = []
    q = (image_quality or "ok").lower()

    if source == "strip" and q != "ok":
        verdict = "retake"
        retake_reasons.append(q if q in BAD_QUALITY else "bad_photo")
    elif unsafe:
        verdict = "unsafe"
        if uncertain:
            retake_reasons.append("some_pads_uncertain")
    elif source == "strip" and overall_confidence is not None and overall_confidence < threshold:
        verdict = "retake"
        retake_reasons.append("low_overall_confidence")
    elif uncertain:
        verdict = "retake"
        retake_reasons.append("some_pads_uncertain")
    elif len(confident) < min_pads:
        verdict = "retake"
        retake_reasons.append("too_few_pads")
    elif caution:
        verdict = "caution"
    else:
        verdict = "safe"

    tested = {x["param"] for x in confident}
    gaps = []
    for risk in (district_risk or {}).get("risks", []):
        # only district-level official findings (fluoride / arsenic); state-wide counts are too coarse
        if risk.get("level", "district") == "district" and risk.get("param") in LIMITS and risk["param"] not in tested:
            gaps.append(risk["param"])

    return {
        "verdict": verdict,
        "results": results,
        "unsafe_params": [x["param"] for x in unsafe],
        "caution_params": [x["param"] for x in caution],
        "uncertain_params": [x["param"] for x in uncertain],
        "retake_reasons": retake_reasons,
        "untested_district_risks": gaps,
        "bacteria_tested": False,
        "threshold": threshold,
        "standard": "BIS IS 10500:2012",
    }


def limits_table() -> list[dict]:
    return [{"param": l.key, "name_en": l.name_en, "name_hi": l.name_hi, "unit": l.unit,
             "acceptable": l.acceptable, "permissible": l.permissible, "low": l.low, "health": l.health,
             "limit": limit_text(l), "source": "WHO" if l.source == WHO_SOURCE else "BIS IS 10500:2012"}
            for l in LIMITS.values()]
