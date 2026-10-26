from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai import MockAgent
from app.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo_assets"


@pytest.fixture
def settings(tmp_path):
    return Settings(gemini_api_key="", mode="mock", database_path=str(tmp_path / "t.db"),
                    pincode_lookup=False, confidence_threshold=0.6, rate_limit=0, admin_token="secret-token")


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings, agent=MockAgent()))


@pytest.fixture
def demo():
    def load(name: str) -> bytes:
        return (DEMO / name).read_bytes()
    return load


def upload(client, name: str, blob: bytes, mime: str = "image/png", **data):
    data = {"state": "Rajasthan", "district": "Jaipur", "lang": "en", **data}
    return client.post("/api/tests", files={"photo": (name, blob, mime)}, data=data)
