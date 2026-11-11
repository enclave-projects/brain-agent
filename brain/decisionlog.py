"""Append-only decision log (SQLite). Stores redacted args only. Agent code never updates or deletes rows."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from brain.config import ROOT, load_config

_COLS = (
    "ts REAL, thread TEXT, step INTEGER, event TEXT, tool TEXT, args TEXT, "
    "prism_choice TEXT, prism_conf REAL, p_top REAL, p_proposed REAL, risk REAL, "
    "verdict TEXT, tier TEXT, action TEXT, approved INTEGER, ok INTEGER, undo TEXT, detail TEXT"
)


def db_path() -> Path:
    d = Path(load_config()["data_dir"])
    d = d if d.is_absolute() else ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d / "decisions.sqlite"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(db_path())
    c.execute(f"CREATE TABLE IF NOT EXISTS decisions ({_COLS})")
    return c


def log_event(event: str, thread: str, step: int, **f: Any) -> None:
    f = {k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else v) for k, v in f.items()}
    cols = ["ts", "thread", "step", "event", *f]
    with _conn() as c:
        c.execute(
            f"INSERT INTO decisions ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [time.time(), thread, step, event, *f.values()],
        )


def rows(thread: str | None = None) -> list[dict[str, Any]]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        q, a = (
            ("SELECT * FROM decisions WHERE thread=? ORDER BY rowid", (thread,))
            if thread
            else (
                "SELECT * FROM decisions ORDER BY rowid",
                (),
            )
        )
        return [dict(r) for r in c.execute(q, a)]


def unsafe_count(thread: str | None = None) -> int:
    """Irreversible tools that executed without explicit approval. Must be 0."""
    return sum(
        1
        for r in rows(thread)
        if r["event"] == "executed" and r["tier"] == "irreversible" and r["approved"] != 1
    )
