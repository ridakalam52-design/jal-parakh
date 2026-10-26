"""District risk agent (bundled CGWB/PIB data) and the deterministic action knowledge base."""
import csv

from app import risk
from app.advice import complaint_draft, template_advice, unsafe_boiling_claim
from app.standards import evaluate


def test_bundled_dataset_matches_official_totals():
    rows = list(csv.DictReader(open(risk.DATA_DIR / "district_risks.csv", encoding="utf-8")))
    # PIB PRID=1809264: fluoride in parts of 370 districts, arsenic in parts of 152 districts
    assert sum(r["fluoride"] == "1" for r in rows) == 370
    assert sum(r["arsenic"] == "1" for r in rows) == 152
    assert all(r["source"].endswith("PRID=1809264") for r in rows)


def test_known_fluoride_district():
    out = risk.district_risk("Rajasthan", "Jaipur")
    assert out["known_district"] and out["test_for"][0] == "fluoride"
    assert out["lat"] and out["lng"]


def test_arsenic_and_state_level_risks():
    out = risk.district_risk("West Bengal", "Malda")
    params = {r["param"] for r in out["risks"] if r["level"] == "district"}
    assert params == {"fluoride", "arsenic"}
    assert any(r["param"] == "iron" and r["level"] == "state" for r in out["risks"])


def test_old_names_and_typos_resolve():
    assert risk.district_risk("Uttar Pradesh", "Allahabad")["district"] == "Prayagraj"
    assert risk.district_risk("Haryana", "Gurgaon")["district"] == "Gurugram"
    assert risk.district_risk("Rajasthan", "jaipr")["district"] == "Jaipur"  # fuzzy
    assert risk.canonical_state("orissa") == "Odisha"
    assert risk.canonical_state("उत्तर प्रदेश") == "Uttar Pradesh"


def test_district_only_lookup_infers_state():
    out = risk.district_risk(None, "Nalgonda")
    assert out["state"] == "Telangana" and out["known_district"]


def test_unknown_district_still_gives_state_advice():
    out = risk.district_risk("Kerala", "Wayanad")
    assert not out["known_district"]
    assert any(r["param"] == "nitrate" for r in out["risks"])
    assert "fluoride" in out["test_for"]


def test_pincode_offline_fallback():
    res = risk.lookup_pincode("302001", enabled=False)
    assert res["ok"] and res["state"] == "Rajasthan" and res["via"].startswith("pincode prefix")
    assert not risk.lookup_pincode("12", enabled=False)["ok"]


def test_risk_layer_has_coordinates():
    layer = risk.risk_layer()
    assert len(layer) > 400 and all(-90 < d["lat"] < 90 for d in layer)


def _ev(*pairs):
    return evaluate([{"param": p, "value": v, "confidence": 0.9} for p, v in pairs])


def test_advice_is_honest_about_boiling():
    adv = template_advice(_ev(("ph", 7), ("nitrate", 5), ("fluoride", 2.5), ("iron", 0)))
    text = " ".join(adv["steps_en"])
    assert "Boiling does NOT remove fluoride" in text
    assert any("उबालने से फ्लोराइड नहीं निकलता" in s for s in adv["steps_hi"])
    assert "RO" in text and "activated alumina" in text


def test_nitrate_advice_warns_about_babies_and_doctor():
    adv = template_advice(_ev(("ph", 7), ("nitrate", 120), ("fluoride", 0.4)))
    assert any("babies" in s for s in adv["steps_en"])
    assert any("bluish" in s for s in adv["doctor_en"])
    assert adv["summary_hi"].startswith("यह पानी पीने लायक नहीं है")


def test_retake_advice_tells_user_to_treat_as_unsafe():
    adv = template_advice(evaluate([], image_quality="no_chart"))
    assert "colour chart" in adv["steps_en"][0]
    assert any("unsafe" in s for s in adv["steps_en"])


def test_complaint_draft_bilingual_and_never_sends():
    ev = _ev(("ph", 7), ("nitrate", 5), ("fluoride", 2.0))
    en = complaint_draft(ev, {"state": "Rajasthan", "district": "Jaipur"}, "en", "27-10-2026")
    hi = complaint_draft(ev, {"state": "Rajasthan", "district": "Jaipur"}, "hi", "27-10-2026")
    assert "Fluoride: 2 mg/L" in en and "District Jaipur" in en and "pgportal.gov.in" in en
    assert "फ्लोराइड: 2 mg/L" in hi and "ज़िला Jaipur" in hi


def test_unsafe_boiling_claim_detector():
    assert unsafe_boiling_claim("Boil the water to remove fluoride.")
    assert unsafe_boiling_claim("उबालकर पिएँ, इससे नाइट्रेट निकल जाएगा")
    assert not unsafe_boiling_claim("Boiling does not remove fluoride.")
    assert not unsafe_boiling_claim("उबालने से फ्लोराइड नहीं निकलता।")
    assert not unsafe_boiling_claim("Boil water to kill germs.")
