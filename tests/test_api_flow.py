"""End-to-end API flow in mock mode, the async path with a fake slow model, and the impact log."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.ai import AIError, MockAgent
from app.main import create_app

from .conftest import upload


# ---------------------------------------------------------------- mock mode, synchronous
@pytest.mark.parametrize("name,verdict,unsafe", [
    ("demo_safe.png", "safe", []),
    ("demo_high_fluoride.png", "unsafe", ["fluoride"]),
    ("demo_high_nitrate_iron.png", "unsafe", ["nitrate"]),
    ("demo_blurry.png", "retake", []),
])
def test_demo_strips(client, demo, name, verdict, unsafe):
    res = upload(client, name, demo(name))
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["status"] == "done" and d["verdict"] == verdict
    assert d["evaluation"]["unsafe_params"] == unsafe
    assert d["is_demo"] is True  # synthetic marker -> excluded from public impact
    assert d["advice"]["summary_en"] and d["advice"]["summary_hi"]
    assert d["state"] == "Rajasthan" and d["district"] == "Jaipur"
    assert client.get(d["url"]).status_code == 200
    assert client.get(f"/api/tests/{d['id']}").json()["verdict"] == verdict


def test_nitrate_iron_demo_flags_iron_as_caution(client, demo):
    d = upload(client, "x.png", demo("demo_high_nitrate_iron.png")).json()
    assert "iron" in d["evaluation"]["caution_params"]


@pytest.mark.parametrize("fname,verdict", [("my_blurry_photo.jpg", "retake"), ("nochart.jpg", "retake"),
                                           ("unsure.jpg", "retake"), ("well.jpg", "safe")])
def test_mock_reader_by_filename(client, fname, verdict):
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 200
    assert upload(client, fname, jpeg, "image/jpeg").json()["verdict"] == verdict


def test_photo_is_not_stored(client, demo, settings, tmp_path):
    upload(client, "demo_safe.png", demo("demo_safe.png"))
    files = [p.name for p in tmp_path.rglob("*") if p.is_file()]
    assert files == ["t.db"]


def test_rejects_non_images_and_big_files(client, settings):
    assert upload(client, "a.txt", b"hello world", "text/plain").json()["error"] == "photo_type"
    big = b"\xff\xd8\xff" + b"0" * int(settings.max_photo_mb * 1024 * 1024 + 10)
    assert upload(client, "big.jpg", big, "image/jpeg").json()["error"] == "photo_too_big"


def test_manual_entry_flow_and_pincode(client):
    d = client.post("/api/manual", json={"values": {"fluoride": "2.2", "nitrate": "", "ph": "7"},
                                         "pincode": "302001", "lang": "hi"}).json()
    assert d["verdict"] == "unsafe" and d["source"] == "manual" and d["state"] == "Rajasthan"
    assert d["is_demo"] is False  # real user entry counts, even without an AI key
    assert client.post("/api/manual", json={"values": {}}).json()["error"] == "no_values"
    assert client.post("/api/manual", json={"values": {"fluoride": "abc"}}).status_code == 400


def test_complaint_only_for_problems_and_counted(client, demo):
    safe = upload(client, "demo_safe.png", demo("demo_safe.png")).json()
    assert client.post(f"/api/tests/{safe['id']}/complaint").status_code == 400
    bad = client.post("/api/manual", json={"values": {"fluoride": 2.0}, "state": "Rajasthan", "district": "Jaipur"}).json()
    c = client.post(f"/api/tests/{bad['id']}/complaint?lang=hi").json()
    assert "Jaipur" in c["text_hi"] and "Jaipur" in c["text_en"] and "never sends" in c["note"]
    imp = client.get("/api/impact").json()
    assert imp["counters"]["complaints_drafted"] == 1


def test_risk_endpoint(client):
    d = client.get("/api/risk", params={"state": "West Bengal", "district": "Malda"}).json()
    assert {"fluoride", "arsenic"} <= set(d["test_for"])
    assert client.get("/api/risk").status_code == 404
    assert client.get("/api/places").json()["states"][0]["en"]
    assert "Jaipur" in client.get("/api/places", params={"state": "Rajasthan"}).json()["districts"]
    assert len(client.get("/api/risk-layer").json()["districts"]) > 400
    assert client.get("/api/limits").json()["standard"] == "BIS IS 10500:2012"


def test_impact_dashboard_excludes_demo_and_exports_csv(client, demo):
    upload(client, "demo_high_fluoride.png", demo("demo_high_fluoride.png"))
    client.post("/api/manual", json={"values": {"nitrate": 90, "ph": 7}, "state": "Uttar Pradesh", "district": "Agra"})
    client.post("/api/manual", json={"values": {"fluoride": 0.4}, "state": "Uttar Pradesh", "district": "Agra"})
    client.post("/api/manual", json={"values": {"fluoride": 0.4}, "state": "Bihar", "district": "Patna", "practice": True})
    real = client.get("/api/impact").json()
    assert real["counters"]["tests_run"] == 2 and real["counters"]["unsafe_found"] == 1
    assert real["counters"]["unsafe_rate"] == 0.5
    agra = real["districts"][0]
    assert agra["district"] == "Agra" and agra["unsafe_rate"] == 0.5 and agra["top_params"] == ["nitrate"]
    assert agra["lat"] and agra["lng"]
    everything = client.get("/api/impact?include_demo=true").json()
    assert everything["counters"]["tests_run"] == 4
    csv_text = client.get("/api/impact.csv").text
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("id,day,state,district,source,verdict") and len(lines) == 3
    for banned in ("photo", "name", "phone", "ip"):
        assert banned not in lines[0].split(",")


def test_admin_import_restores_log(client):
    client.post("/api/manual", json={"values": {"fluoride": 2}, "state": "Rajasthan", "district": "Ajmer"})
    csv_text = client.get("/api/impact.csv").text
    assert client.post("/api/admin/import", content=csv_text).status_code == 403
    r = client.post("/api/admin/import", content=csv_text, headers={"x-admin-token": "secret-token"})
    assert r.json() == {"imported": 1}
    assert client.get("/api/impact").json()["counters"]["tests_run"] == 2


def test_rate_limit(settings, demo):
    settings.rate_limit = 2
    c = TestClient(create_app(settings, agent=MockAgent()))
    codes = [upload(c, "demo_safe.png", demo("demo_safe.png")).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_pages_render(client):
    for path in ("/", "/impact", "/about", "/healthz", "/robots.txt", "/demo_assets/demo_safe.png"):
        assert client.get(path).status_code == 200, path
    assert client.get("/t/nope").status_code == 404
    assert client.get("/healthz").json()["ai"] == "mock"


# ---------------------------------------------------------------- async path with a fake slow model
class FakeGemini:
    """Not 'mock', so the app takes the background-thread path like the real Gemini agent."""

    mode = "gemini:fake"

    def __init__(self, gate=None, read_error=False, advise_error=False, advice=None, reading=None):
        self.gate, self.read_error, self.advise_error = gate, read_error, advise_error
        self.advice, self.reading = advice, reading
        self.calls = 0

    def read_strip(self, mime, blob, filename=""):
        self.calls += 1
        if self.gate is not None:
            assert self.gate.wait(10)
        if self.read_error:
            raise AIError("Gemini API 503: overloaded")
        return self.reading or MockAgent().read_strip(mime, blob, filename)

    def advise(self, evaluation, risk=None):
        if self.advise_error:
            raise AIError("Gemini timeout")
        if self.advice is not None:
            from app.ai import merge_advice
            from app.advice import template_advice
            return merge_advice(template_advice(evaluation, risk), self.advice, self.mode)
        return MockAgent().advise(evaluation, risk)


def wait_for(fn, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.02)
    raise AssertionError("condition not met")


def make(settings, agent):
    settings.mode, settings.gemini_api_key, settings.ai_background = "auto", "fake-key", "thread"
    return TestClient(create_app(settings, agent=agent))


def test_async_reading_then_polling(settings, demo):
    gate = threading.Event()
    c = make(settings, FakeGemini(gate=gate))
    first = upload(c, "demo_high_fluoride.png", demo("demo_high_fluoride.png")).json()
    assert first["status"] == "reading" and first["verdict"] is None  # answered at once
    gate.set()
    done = wait_for(lambda: (d := c.get(f"/api/tests/{first['id']}").json())["status"] == "done" and d)
    assert done["verdict"] == "unsafe" and done["advice"]["summary_en"]


def test_reader_failure_never_gives_a_verdict(settings, demo):
    c = make(settings, FakeGemini(read_error=True))
    t = upload(c, "x.png", demo("demo_safe.png")).json()
    d = wait_for(lambda: (x := c.get(f"/api/tests/{t['id']}").json())["status"] == "error" and x)
    assert d["verdict"] is None and d["error"] == "reader_failed"
    assert c.get("/api/impact?include_demo=true").json()["counters"]["tests_run"] == 0


def test_advice_failure_falls_back_to_rules(settings, demo):
    c = make(settings, FakeGemini(advise_error=True))
    t = upload(c, "x.png", demo("demo_high_nitrate_iron.png")).json()
    d = wait_for(lambda: (x := c.get(f"/api/tests/{t['id']}").json())["status"] == "done" and x)
    assert d["verdict"] == "unsafe" and d["advice"]["agent"] == "rules (AI unavailable)"
    assert any("babies" in s for s in d["advice"]["steps_en"])


def test_model_advice_claiming_boiling_removes_fluoride_is_rejected(settings, demo):
    bad = {"summary_en": "Just boil the water to remove fluoride.", "summary_hi": "पानी उबालें, फ्लोराइड निकल जाएगा।",
           "steps_en": ["Boil it"], "steps_hi": ["उबालें"], "doctor_en": [], "doctor_hi": []}
    c = make(settings, FakeGemini(advice=bad))
    t = upload(c, "x.png", demo("demo_high_fluoride.png")).json()
    d = wait_for(lambda: (x := c.get(f"/api/tests/{t['id']}").json())["status"] == "done" and x)
    assert d["advice"]["agent"] == "rules (model output rejected)"
    assert "Boiling will not fix this" in d["advice"]["summary_en"]


def test_good_model_advice_is_used(settings, demo):
    good = {"summary_en": "Unsafe: fluoride is high. Boiling does not help. Use the community plant.",
            "summary_hi": "पानी असुरक्षित है। फ्लोराइड ज़्यादा है। उबालने से फायदा नहीं।",
            "steps_en": ["Use the community water plant."], "steps_hi": ["सामुदायिक जल संयंत्र का पानी लें।"],
            "doctor_en": ["See a doctor for joint pain."], "doctor_hi": ["जोड़ों में दर्द हो तो डॉक्टर को दिखाएँ।"]}
    c = make(settings, FakeGemini(advice=good))
    t = upload(c, "x.png", demo("demo_high_fluoride.png")).json()
    d = wait_for(lambda: (x := c.get(f"/api/tests/{t['id']}").json())["status"] == "done" and x)
    assert d["advice"]["agent"] == "gemini:fake" and d["advice"]["summary_en"].startswith("Unsafe")
    assert any("Boiling does NOT remove fluoride" in s for s in d["advice"]["facts_en"])


def test_real_photo_with_gemini_counts_as_real_data(settings):
    reading = {"image_quality": "ok", "overall_confidence": 0.9, "notes": "",
               "readings": [{"param": p, "value": v, "confidence": 0.9} for p, v in
                            (("ph", 7), ("nitrate", 5), ("fluoride", 0.4), ("iron", 0))]}
    c = make(settings, FakeGemini(reading=reading))
    t = upload(c, "phone.jpg", b"\xff\xd8\xff\xe0" + b"1" * 300, "image/jpeg").json()
    wait_for(lambda: c.get(f"/api/tests/{t['id']}").json()["status"] == "done")
    assert c.get("/api/impact").json()["counters"]["safe_found"] == 1


def test_restart_mid_read_asks_for_retake(settings, demo):
    gate = threading.Event()
    agent = FakeGemini(gate=gate)
    c = make(settings, agent)
    t = upload(c, "x.png", demo("demo_safe.png")).json()
    # a new process on the same database (the old thread is still blocked)
    c2 = make(settings, FakeGemini())
    d = c2.get(f"/api/tests/{t['id']}").json()
    assert d["status"] == "error" and d["error"] == "restart" and d["verdict"] is None
    gate.set()
    time.sleep(0.1)
    # the stale thread must not overwrite the fail-safe outcome
    assert c2.get(f"/api/tests/{t['id']}").json()["verdict"] is None
