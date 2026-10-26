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
