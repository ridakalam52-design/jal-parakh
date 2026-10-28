"""The real Gemini REST client against a fake HTTP transport (no network, no key)."""
import json

import httpx

from app.ai import GeminiAgent, normalize_reading
from app.standards import evaluate


def gemini_reply(payload: dict) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


READING = {"image_quality": "ok", "chart_visible": True, "strip_visible": True, "overall_confidence": 0.82,
           "readings": [{"param": "pH", "value": 7.5, "confidence": 0.9},
                        {"param": "Total Hardness", "value": 250, "confidence": 0.8},
                        {"param": "fluoride", "value": 2, "confidence": 0.78},
                        {"param": "nitrate", "value": 10, "confidence": 85}]}  # percent -> 0.85


def test_read_strip_sends_image_and_parses_json():
    seen = {}

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen["url"] = str(req.url)
        seen["key"] = req.headers.get("x-goog-api-key")
        seen["parts"] = body["contents"][0]["parts"]
        seen["schema"] = body["generationConfig"]["responseSchema"]
        return httpx.Response(200, json=gemini_reply(READING))

    agent = GeminiAgent("k-123", "gemini-test", transport=httpx.MockTransport(handler))
    out = agent.read_strip("image/png", b"\x89PNG fake")
    assert "gemini-test:generateContent" in seen["url"] and seen["key"] == "k-123"
    assert seen["parts"][1]["inline_data"]["mime_type"] == "image/png"
    assert "image_quality" in seen["schema"]["properties"]
    keys = [r["param"] for r in out["readings"]]
    assert keys == ["ph", "total_hardness", "fluoride", "nitrate"]
    assert out["readings"][3]["confidence"] == 0.85
    assert evaluate(out["readings"], out["image_quality"], overall_confidence=out["overall_confidence"])["verdict"] == "unsafe"


def test_fallback_model_on_404_and_429():
    calls = []

    def handler(req: httpx.Request):
        model = str(req.url).split("/models/")[1].split(":")[0]
        calls.append(model)
        if model == "primary":
            return httpx.Response(404, json={"error": {"message": "not found"}})
        if model == "second":
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json=gemini_reply(READING))

    agent = GeminiAgent("k", "primary", transport=httpx.MockTransport(handler),
                        fallback_model="second,third", retry_sleep=0)
    assert agent.read_strip("image/jpeg", b"x")["image_quality"] == "ok"
    assert calls[0] == "primary" and calls[-1] == "third"


def test_model_contradictions_fail_safe():
    out = normalize_reading({**READING, "chart_visible": False})
    assert out["image_quality"] == "no_chart"
    assert evaluate(out["readings"], out["image_quality"])["verdict"] == "retake"
    assert normalize_reading({"image_quality": "weird"})["image_quality"] == "blurry"


def test_advise_grounded_and_merged():
    advice = {"summary_en": "Unsafe. Fluoride is high. Boiling does not remove it.",
              "summary_hi": "पानी असुरक्षित है। फ्लोराइड ज़्यादा है। उबालने से नहीं निकलता।",
              "steps_en": ["Use the community plant."], "steps_hi": ["सामुदायिक प्लांट का पानी लें।"],
              "doctor_en": ["Joint pain -> doctor."], "doctor_hi": ["जोड़ों में दर्द -> डॉक्टर।"]}
    prompts = []

    def handler(req: httpx.Request):
        prompts.append(json.loads(req.content)["contents"][0]["parts"][0]["text"])
        return httpx.Response(200, json=gemini_reply(advice))

    agent = GeminiAgent("k", "m", transport=httpx.MockTransport(handler))
    ev = evaluate([{"param": p, "value": v, "confidence": 0.9} for p, v in (("ph", 7), ("nitrate", 5), ("fluoride", 2))])
    out = agent.advise(ev, {"risks": [{"en": "Fluoride above 1.5 mg/L in parts of Jaipur (CGWB)."}]})
    assert '"verdict": "unsafe"' in prompts[0] and "Jaipur" in prompts[0] and "does NOT remove fluoride" in prompts[0]
    assert out["agent"] == "gemini:m" and out["steps_en"] == ["Use the community plant."]
    assert out["germs_en"]  # deterministic facts always kept


# --- safety-biased rounding (model outputs below mimic the live under-reads on the synthetic demo strips) ---
from app.ai import BETWEEN_SWATCH_CONFIDENCE, READ_PROMPT, READ_SCHEMA, safety_round  # noqa: E402
from app.config import DEFAULT_GEMINI_FALLBACKS, DEFAULT_GEMINI_MODEL, Settings  # noqa: E402


def pad(param, value, lo, hi, conf=1.0, color="pink"):
    return {"param": param, "observed_color": color, "nearest_low": lo, "nearest_high": hi,
            "value": value, "confidence": conf}


def test_between_swatches_takes_higher_value_and_caps_confidence():
    raw = {"image_quality": "ok", "chart_visible": True, "strip_visible": True, "overall_confidence": 1.0,
           "readings": [pad("nitrate", 25, 25, 100), pad("nitrite", 0.5, 0.5, 1), pad("iron", 1, 1, 3),
                        pad("total_hardness", 50, 50, 120), pad("ph", 7, 7, 7)]}
    out = normalize_reading(raw)
    got = {r["param"]: (r["value"], r["confidence"]) for r in out["readings"]}
    assert got["nitrate"] == (100, BETWEEN_SWATCH_CONFIDENCE)
    assert got["nitrite"] == (1, BETWEEN_SWATCH_CONFIDENCE)
    assert got["iron"] == (3, BETWEEN_SWATCH_CONFIDENCE)
    assert got["total_hardness"] == (120, BETWEEN_SWATCH_CONFIDENCE)
    assert got["ph"] == (7, 1.0)  # exact match: untouched
    assert all(r["between_swatches"] for r in out["readings"] if r["param"] != "ph")
    # this exact model answer was SAFE before the fix; now the riskier values drive the verdict
    ev = evaluate(out["readings"], out["image_quality"], overall_confidence=out["overall_confidence"])
    assert ev["verdict"] == "unsafe" and "nitrate" in ev["unsafe_params"]


def test_fluoride_between_swatches_is_unsafe_not_caution():
    out = normalize_reading({"image_quality": "ok", "chart_visible": True, "strip_visible": True,
                             "overall_confidence": 0.95,
                             "readings": [pad("fluoride", 1.5, 1.5, 2.0, 0.95), pad("ph", 8, 8, 8, 0.9),
                                          pad("nitrate", 10, 10, 10, 0.9)]})
    f = next(r for r in out["readings"] if r["param"] == "fluoride")
    assert f["value"] == 2.0 and f["confidence"] == 0.7
    assert evaluate(out["readings"], out["image_quality"])["verdict"] == "unsafe"


def test_ph_rounds_away_from_neutral():
    assert safety_round("ph", 7.0, 0.9, 7.0, 7.5) == (7.5, 0.7, True)
    assert safety_round("ph", 7.0, 0.9, 6.5, 7.0) == (6.5, 0.7, True)
    assert safety_round("ph", 8.0, 0.9, 8.0, 8.5)[0] == 8.5
    assert safety_round("ph", 6.5, 0.9, 6.0, 6.5)[0] == 6.0


def test_rounding_edge_cases():
    # reversed low/high, value already riskier, low confidence kept, missing value, single swatch
    assert safety_round("nitrate", 50, 0.9, 100, 50) == (100, 0.7, True)
    assert safety_round("nitrate", 250, 0.9, 50, 100) == (250, 0.7, True)
    assert safety_round("nitrate", 50, 0.4, 50, 100) == (100, 0.4, True)
    assert safety_round("iron", None, 0.8, 1, 3) == (3, 0.7, True)
    assert safety_round("iron", None, 0.8, 3, 3) == (3, 0.8, False)
    assert safety_round("iron", 1, 0.8, None, 3) == (3, 0.8, False)
    assert safety_round("iron", 1, 0.8, "n/a", None) == (1, 0.8, False)
    # string numbers and percent confidence from a sloppy model
    r = normalize_reading({"image_quality": "ok", "readings": [pad("lead", "0", "0", "0.01", 95)]})["readings"][0]
    assert r["value"] == 0.01 and r["confidence"] == 0.7


def test_old_response_shape_still_parses_unchanged():
    out = normalize_reading(READING)
    assert [r["value"] for r in out["readings"]] == [7.5, 250, 2, 10]
    assert "nearest_low" not in out["readings"][0]
    assert out["readings"][0]["confidence"] == 0.9


def test_gemini_read_strip_applies_rounding_end_to_end():
    reply = {"image_quality": "ok", "chart_visible": True, "strip_visible": True, "overall_confidence": 1.0,
             "readings": [pad("fluoride", 0, 0, 0.5), pad("total_hardness", 50, 50, 120), pad("ph", 7, 7, 7)]}
    agent = GeminiAgent("k", "m", transport=httpx.MockTransport(lambda req: httpx.Response(200, json=gemini_reply(reply))))
    got = {r["param"]: r for r in agent.read_strip("image/png", b"x")["readings"]}
    assert got["fluoride"]["value"] == 0.5 and got["total_hardness"]["value"] == 120
    assert got["fluoride"]["confidence"] == 0.7


def test_read_schema_and_prompt_ask_for_swatch_bounds():
    item = READ_SCHEMA["properties"]["readings"]["items"]
    for f in ("observed_color", "nearest_low", "nearest_high", "value", "confidence"):
        assert f in item["properties"] and f in item["required"]
    assert "HIGHER" in READ_PROMPT and "FARTHER" in READ_PROMPT and "UNDER" in READ_PROMPT


def test_mock_reader_unaffected(demo):
    from app.ai import MockAgent
    out = MockAgent().read_strip("image/png", demo("demo_high_nitrate_iron.png"))
    got = {r["param"]: r["value"] for r in out["readings"]}
    assert got["nitrate"] == 100 and got["iron"] == 3.0


def test_default_models(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
    s = Settings()
    assert s.gemini_model == DEFAULT_GEMINI_MODEL == "gemini-3.5-flash"
    assert s.gemini_fallback_model == DEFAULT_GEMINI_FALLBACKS == "gemini-2.5-flash,gemini-3.1-flash-lite"
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    assert Settings().gemini_model == "gemini-custom"
    assert GeminiAgent("k").model == "gemini-3.5-flash"
