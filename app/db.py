"""Tiny SQLite data layer (no ORM, zero setup).

Two tables:
  tests   - one water test (strip photo or manual entry) while it is processed and shown to its owner.
            Holds the readings, verdict and advice. Never the photo (kept in memory only while reading).
  reports - the ANONYMOUS public impact log: state, district, verdict, which parameters failed, date.
            No photo, no name, no phone, no IP, no exact location.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tests (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,            -- strip | manual
    status TEXT NOT NULL,            -- reading | advising | done | error
    lang TEXT DEFAULT 'hi',
    state TEXT, district TEXT,
    reading TEXT,                    -- normalised reader output (JSON)
    evaluation TEXT,                 -- rules-engine output (JSON)
    risk TEXT,                       -- district risk (JSON)
    advice TEXT,                     -- action-agent output (JSON)
    agent TEXT,
    error TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    complaint_drafted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id TEXT UNIQUE,
    day TEXT NOT NULL,               -- YYYY-MM-DD only
    state TEXT, district TEXT,
    source TEXT NOT NULL,
    verdict TEXT NOT NULL,
    unsafe_params TEXT DEFAULT '',
    caution_params TEXT DEFAULT '',
    complaint_drafted INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0,
    agent TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_reports_place ON reports(state, district);
"""

JSON_COLS = {"reading", "evaluation", "risk", "advice"}
REPORT_COLS = ["day", "state", "district", "source", "verdict", "unsafe_params", "caution_params",
               "complaint_drafted", "is_demo", "agent"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DB:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        out = dict(row)
        for k in JSON_COLS & out.keys():
            if out[k] is not None:
                try:
                    out[k] = json.loads(out[k])
                except (TypeError, ValueError):
                    pass
        return out

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            return self._row(self._conn.execute(sql, params).fetchone())

    def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [self._row(r) for r in self._conn.execute(sql, params).fetchall()]

    # -- tests -------------------------------------------------------------
    def insert_test(self, t: dict) -> None:
        t = {**t, "created_at": now_iso(), "updated_at": now_iso()}
        t = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_COLS and v is not None else v) for k, v in t.items()}
        self.execute(f"INSERT INTO tests ({', '.join(t)}) VALUES ({', '.join('?' for _ in t)})", tuple(t.values()))

    def update_test(self, test_id: str, **fields: Any) -> None:
        fields = {**fields, "updated_at": now_iso()}
        fields = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_COLS and v is not None else v)
                  for k, v in fields.items()}
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.execute(f"UPDATE tests SET {sets} WHERE id = ?", (*fields.values(), test_id))

    def get_test(self, test_id: str) -> dict | None:
        return self.one("SELECT * FROM tests WHERE id = ?", (test_id,))

    def tests_with_status(self, *statuses: str) -> list[dict]:
        qs = ", ".join("?" for _ in statuses)
        return self.all(f"SELECT * FROM tests WHERE status IN ({qs})", statuses)

    def claim(self, test_id: str, from_status: str, to_status: str) -> bool:
        """Atomic compare-and-set on status (so a background step runs exactly once)."""
        cur = self.execute("UPDATE tests SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                           (to_status, now_iso(), test_id, from_status))
        return cur.rowcount == 1

    # -- reports (anonymous impact log) ------------------------------------
    def upsert_report(self, r: dict) -> None:
        cols = ["test_id"] + REPORT_COLS
        vals = tuple(r.get(c, "" if c not in ("complaint_drafted", "is_demo") else 0) for c in cols)
        self.execute(
            f"INSERT INTO reports ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) "
            f"ON CONFLICT(test_id) DO UPDATE SET " + ", ".join(f"{c}=excluded.{c}" for c in REPORT_COLS), vals)

    def mark_complaint(self, test_id: str) -> None:
        self.execute("UPDATE tests SET complaint_drafted = 1 WHERE id = ?", (test_id,))
        self.execute("UPDATE reports SET complaint_drafted = 1 WHERE test_id = ?", (test_id,))

    def reports(self, include_demo: bool = False) -> list[dict]:
        where = "" if include_demo else "WHERE is_demo = 0"
        return self.all(f"SELECT {', '.join(['id'] + REPORT_COLS)} FROM reports {where} ORDER BY id DESC")

    def import_report(self, r: dict) -> None:
        cols = REPORT_COLS
        vals = tuple(r.get(c, "") for c in cols)
        self.execute(f"INSERT INTO reports ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", vals)
