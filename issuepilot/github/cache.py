from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CachedResponse:
    etag: str | None
    body: str


class ResponseCache:
    """SQLite-backed HTTP response cache, keyed by full request URL.

    GitHub does not count conditional requests that come back 304 against
    the caller's rate limit, so storing the ETag from a prior 200 lets us
    re-poll the same resource for free until it actually changes.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_cache (
                cache_key TEXT PRIMARY KEY,
                etag TEXT,
                body TEXT NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def get(self, cache_key: str) -> CachedResponse | None:
        row = self._conn.execute(
            "SELECT etag, body FROM http_cache WHERE cache_key = ?", (cache_key,)
        ).fetchone()
        if row is None:
            return None
        return CachedResponse(etag=row[0], body=row[1])

    def put(self, cache_key: str, etag: str | None, body: str) -> None:
        self._conn.execute(
            """
            INSERT INTO http_cache (cache_key, etag, body, fetched_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(cache_key) DO UPDATE SET
                etag = excluded.etag,
                body = excluded.body,
                fetched_at = excluded.fetched_at
            """,
            (cache_key, etag, body),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
