"""Rules engine: BIS IS 10500:2012 limits and the fail-safe verdict policy (no AI involved)."""
import pytest

from app.standards import LIMITS, canonical_key, classify, evaluate


def r(param, value, confidence=0.9):
    return {"param": param, "value": value, "confidence": confidence}


SAFE_STRIP = [r("ph", 7.2), r("total_hardness", 120), r("nitrate", 10), r("fluoride", 0.5), r("iron", 0.1),
              r("free_chlorine", 0.5), r("lead", 0)]


# ---------------------------------------------------------------- limits table
def test_limits_match_bis_is_10500():
    assert (LIMITS["fluoride"].acceptable, LIMITS["fluoride"].permissible) == (1.0, 1.5)
    assert (LIMITS["nitrate"].acceptable, LIMITS["nitrate"].permissible) == (45, None)
    assert (LIMITS["iron"].acceptable, LIMITS["iron"].permissible) == (1.0, None)  # Amendment 1 (2015)
    assert (LIMITS["arsenic"].acceptable, LIMITS["arsenic"].permissible) == (0.01, None)
    assert (LIMITS["lead"].acceptable, LIMITS["lead"].permissible) == (0.01, None)
    assert (LIMITS["total_hardness"].acceptable, LIMITS["total_hardness"].permissible) == (200, 600)
    assert (LIMITS["total_alkalinity"].acceptable, LIMITS["total_alkalinity"].permissible) == (200, 600)
    assert (LIMITS["ph"].low, LIMITS["ph"].acceptable) == (6.5, 8.5)
    assert (LIMITS["free_chlorine"].low, LIMITS["free_chlorine"].acceptable) == (0.2, 1.0)
    assert "WHO" in LIMITS["nitrite"].source  # not in IS 10500, labelled honestly


@pytest.mark.parametrize("param,value,status", [
    ("fluoride", 0.8, "ok"), ("fluoride", 1.0, "ok"), ("fluoride", 1.2, "caution"), ("fluoride", 1.5, "caution"),
    ("fluoride", 1.6, "unsafe"), ("nitrate", 45, "ok"), ("nitrate", 50, "unsafe"), ("nitrite", 3.5, "unsafe"),
    ("lead", 0.01, "ok"), ("lead", 0.05, "unsafe"), ("arsenic", 0.05, "unsafe"),
    ("iron", 0.3, "ok"), ("iron", 3, "caution"),  # aesthetic: never 'unsafe' on its own
    ("total_hardness", 300, "caution"), ("total_hardness", 800, "caution"),
    ("ph", 7.0, "ok"), ("ph", 8.8, "caution"), ("ph", 6.2, "caution"), ("ph", 4.0, "unsafe"), ("ph", 11, "unsafe"),
    ("free_chlorine", 0.5, "ok"), ("free_chlorine", 0, "low"), ("free_chlorine", 2, "caution"),
    ("free_chlorine", 6, "unsafe"), ("copper", 1.0, "caution"), ("copper", 2.0, "unsafe"),
])
def test_classify(param, value, status):
    assert classify(LIMITS[param], value)[0] == status


def test_reasons_are_bilingual():
    st, en, hi = classify(LIMITS["fluoride"], 2.0)
    assert st == "unsafe" and "1.5" in en and "फ्लोराइड" in hi


def test_canonical_keys():
    assert canonical_key("Total Hardness") == "total_hardness"
    assert canonical_key("chlorine") == "free_chlorine"
    assert canonical_key("F") == "fluoride"
    assert canonical_key("pH") == "ph"
    assert canonical_key("unobtainium") is None


# ---------------------------------------------------------------- verdicts
def test_safe_strip():
    ev = evaluate(SAFE_STRIP)
    assert ev["verdict"] == "safe" and not ev["unsafe_params"] and ev["bacteria_tested"] is False


def test_high_fluoride_is_unsafe():
    ev = evaluate(SAFE_STRIP[:3] + [r("fluoride", 2.0)] + SAFE_STRIP[4:])
    assert ev["verdict"] == "unsafe" and ev["unsafe_params"] == ["fluoride"]


def test_caution_when_only_between_acceptable_and_permissible():
    ev = evaluate([r("ph", 7), r("total_hardness", 350), r("nitrate", 5), r("fluoride", 1.2)])
    assert ev["verdict"] == "caution"
    assert set(ev["caution_params"]) == {"total_hardness", "fluoride"}


def test_low_chlorine_alone_does_not_block_safe():
    ev = evaluate([r("ph", 7), r("nitrate", 5), r("fluoride", 0.3), r("free_chlorine", 0)])
    assert ev["verdict"] == "safe"
    assert next(x for x in ev["results"] if x["param"] == "free_chlorine")["status"] == "low"


# ---------------------------------------------------------------- fail-safe
@pytest.mark.parametrize("quality", ["blurry", "no_chart", "no_strip", "glare", "too_dark", "not_a_strip"])
def test_bad_photo_is_always_retake_even_with_values(quality):
    ev = evaluate(SAFE_STRIP, image_quality=quality)
    assert ev["verdict"] == "retake" and ev["retake_reasons"] == [quality]


def test_bad_photo_wins_even_over_unsafe_values():
    """If the photo itself is unusable we cannot trust a scary reading either: retake."""
    ev = evaluate([r("fluoride", 3.0), r("ph", 7), r("nitrate", 1)], image_quality="blurry")
    assert ev["verdict"] == "retake"


def test_low_confidence_pad_never_called_safe():
    readings = SAFE_STRIP[:-1] + [r("lead", 0, confidence=0.4)]
    ev = evaluate(readings)
    assert ev["verdict"] == "retake"
    assert ev["uncertain_params"] == ["lead"]
    assert "some_pads_uncertain" in ev["retake_reasons"]


def test_low_confidence_never_called_caution():
    ev = evaluate([r("ph", 7), r("total_hardness", 350), r("nitrate", 5), r("fluoride", 1.2, confidence=0.3)])
    assert ev["verdict"] == "retake"


def test_low_confidence_reading_above_limit_does_not_count_as_unsafe_or_safe():
    ev = evaluate([r("ph", 7), r("nitrate", 5), r("total_hardness", 100), r("fluoride", 3.0, confidence=0.3)])
    assert ev["verdict"] == "retake" and ev["unsafe_params"] == []


def test_confident_danger_is_not_hidden_behind_a_retake():
    ev = evaluate([r("nitrate", 100, 0.9), r("ph", 7, 0.3), r("fluoride", 0.5, 0.3)])
    assert ev["verdict"] == "unsafe" and "some_pads_uncertain" in ev["retake_reasons"]


def test_low_overall_confidence_is_retake():
    assert evaluate(SAFE_STRIP, overall_confidence=0.4)["verdict"] == "retake"


def test_strip_needs_enough_pads():
    ev = evaluate([r("ph", 7), r("nitrate", 5)])
    assert ev["verdict"] == "retake" and ev["retake_reasons"] == ["too_few_pads"]


def test_manual_entry_can_be_a_single_value():
    assert evaluate([r("fluoride", 0.4, 1.0)], source="manual")["verdict"] == "safe"
    assert evaluate([r("fluoride", 2.4, 1.0)], source="manual")["verdict"] == "unsafe"


@pytest.mark.parametrize("bad", [-1, 99999, "abc", None])
def test_implausible_values_are_uncertain(bad):
    ev = evaluate(SAFE_STRIP[:-1] + [{"param": "lead", "value": bad, "confidence": 0.95}])
    assert ev["verdict"] == "retake" and "lead" in ev["uncertain_params"]


def test_unknown_and_duplicate_params_are_ignored():
    ev = evaluate(SAFE_STRIP + [r("unobtainium", 5), r("fluoride", 9.9)])
    assert ev["verdict"] == "safe"
    assert [x["param"] for x in ev["results"]].count("fluoride") == 1


def test_threshold_is_configurable():
    readings = SAFE_STRIP[:-1] + [r("lead", 0, confidence=0.7)]
    assert evaluate(readings, threshold=0.6)["verdict"] == "safe"
    assert evaluate(readings, threshold=0.8)["verdict"] == "retake"


def test_untested_district_risks_are_flagged():
    risk = {"risks": [{"param": "arsenic"}, {"param": "fluoride"}]}
    ev = evaluate(SAFE_STRIP, district_risk=risk)
    assert ev["verdict"] == "safe"
    assert ev["untested_district_risks"] == ["arsenic"]  # fluoride was tested
