"""Runtime configuration for Jal Parakh.

Everything is read from environment variables (a local `.env` file is loaded automatically).
Without GEMINI_API_KEY the app runs in MOCK mode, so anyone can try the full flow offline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional: python-dotenv
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


# Default reader model and fallback chain (override with GEMINI_MODEL / GEMINI_FALLBACK_MODEL).
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_GEMINI_FALLBACKS = "gemini-2.5-flash,gemini-3.1-flash-lite"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass
class Settings:
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))
    # Comma-separated models tried in order if the primary one is missing, overloaded or out of quota.
    gemini_fallback_model: str = field(default_factory=lambda: _env("GEMINI_FALLBACK_MODEL", DEFAULT_GEMINI_FALLBACKS))
    # Per-HTTP-call timeout and total retry budget (seconds). AI runs in the background.
    gemini_timeout: float = field(default_factory=lambda: float(_env("GEMINI_TIMEOUT", "60")))
    gemini_total_budget: float = field(default_factory=lambda: float(_env("GEMINI_TOTAL_BUDGET", "150")))
    # "thread": AI work runs in a background thread (default). "inline": synchronous (tests, debugging).
    ai_background: str = field(default_factory=lambda: _env("AI_BACKGROUND", "thread").lower())
    # "auto" (mock only when the key is missing) or "mock" (force mock)
    mode: str = field(default_factory=lambda: _env("JALPARAKH_MODE", "auto").lower())
    # Below this reader confidence a pad is "uncertain" and the verdict becomes "retake" (never "safe").
    confidence_threshold: float = field(default_factory=lambda: float(_env("CONFIDENCE_THRESHOLD", "0.6")))
    database_path: str = field(
        default_factory=lambda: _env("DATABASE_PATH", str(BASE_DIR / "data" / "jalparakh.db")))
    max_photo_mb: float = field(default_factory=lambda: float(_env("MAX_PHOTO_MB", "8")))
    # India Post pincode API (free, no key). "off" uses only the offline prefix table.
    pincode_lookup: bool = field(default_factory=lambda: _env("PINCODE_LOOKUP", "on").lower() in ("1", "on", "true", "yes"))
    # Protects POST /api/admin/import (restore the impact log after a free-tier redeploy). Empty = disabled.
    admin_token: str = field(default_factory=lambda: _env("ADMIN_TOKEN"))
    # Max tests per client IP per 10 minutes (in memory; IPs are never stored).
    rate_limit: int = field(default_factory=lambda: int(_env("RATE_LIMIT", "30")))

    @property
    def ai_mock(self) -> bool:
        return self.mode == "mock" or not self.gemini_api_key

    def summary(self) -> dict:
        return {"ai": "mock" if self.ai_mock else f"gemini:{self.gemini_model}",
                "confidence_threshold": self.confidence_threshold}
