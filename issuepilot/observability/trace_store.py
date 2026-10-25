from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class TraceStore:
    """Minimal SQLite trace log: one row per traced call.

    This is intentionally not the full observability story (no tokens,
    no tool-call breakdown yet — that's a later milestone once
    LangSmith/callbacks are wired in). The point right now is that no
    LLM call is ever made without *something* recording that it
    happened, how long it took, and whether it failed.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_name TEXT NOT NULL,
                prompt_version TEXT,
                latency_ms REAL NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def record(self, node_name: str, prompt_version: str | None, latency_ms: float, error: str | None) -> None:
        self._conn.execute(
            "INSERT INTO traces (node_name, prompt_version, latency_ms, error) VALUES (?, ?, ?, ?)",
            (node_name, prompt_version, latency_ms, error),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


@contextmanager
def trace(store: TraceStore, node_name: str, prompt_version: str | None = None) -> Iterator[None]:
    start = time.monotonic()
    error: str | None = None
    try:
        yield
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        store.record(node_name, prompt_version, (time.monotonic() - start) * 1000, error)
