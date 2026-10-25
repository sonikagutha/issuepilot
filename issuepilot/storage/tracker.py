from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Status = Literal["starred", "working", "pr_opened", "merged", "dropped"]

STATUS_LABELS: dict[Status, str] = {
    "starred": "Starred",
    "working": "Working on it",
    "pr_opened": "PR opened",
    "merged": "Merged",
    "dropped": "Dropped",
}

_COLUMNS = "repo, number, title, html_url, status, note, pr_url, pr_state, starred_at, updated_at"


class TrackedIssue(BaseModel):
    repo: str
    number: int
    title: str
    html_url: str
    status: Status
    note: str
    pr_url: str | None
    pr_state: str | None
    starred_at: datetime
    updated_at: datetime


class Tracker:
    """SQLite store of issues a contributor has starred and is tracking.

    Keyed by (repo, number). Timestamps are stored as microsecond ISO
    strings so "most recently updated" ordering stays stable even when
    several edits land in the same second.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_issues (
                repo TEXT NOT NULL,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                html_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'starred',
                note TEXT NOT NULL DEFAULT '',
                pr_url TEXT,
                pr_state TEXT,
                starred_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (repo, number)
            )
            """
        )
        self._conn.commit()

    def star(self, repo: str, number: int, title: str, html_url: str) -> TrackedIssue:
        now = _now()
        # ON CONFLICT DO NOTHING keeps an existing status/note: starring twice is a no-op.
        self._conn.execute(
            "INSERT INTO tracked_issues (repo, number, title, html_url, starred_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (repo, number) DO NOTHING",
            (repo, number, title, html_url, now, now),
        )
        self._conn.commit()
        return self._require(repo, number)

    def get(self, repo: str, number: int) -> TrackedIssue | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM tracked_issues WHERE repo = ? AND number = ?", (repo, number)
        ).fetchone()
        return _from_row(row) if row else None

    def list(self) -> list[TrackedIssue]:
        rows = self._conn.execute(f"SELECT {_COLUMNS} FROM tracked_issues ORDER BY updated_at DESC").fetchall()
        return [_from_row(row) for row in rows]

    def update(
        self,
        repo: str,
        number: int,
        *,
        status: Status | None = None,
        note: str | None = None,
        pr_url: str | None = None,
        pr_state: str | None = None,
    ) -> TrackedIssue:
        self._require(repo, number)
        changes = {"status": status, "note": note, "pr_url": pr_url, "pr_state": pr_state}
        changes = {key: value for key, value in changes.items() if value is not None}
        changes["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in changes)
        self._conn.execute(
            f"UPDATE tracked_issues SET {assignments} WHERE repo = ? AND number = ?",
            (*changes.values(), repo, number),
        )
        self._conn.commit()
        return self._require(repo, number)

    def remove(self, repo: str, number: int) -> bool:
        cursor = self._conn.execute("DELETE FROM tracked_issues WHERE repo = ? AND number = ?", (repo, number))
        self._conn.commit()
        return cursor.rowcount > 0

    def counts(self) -> dict[Status, int]:
        counts: dict[Status, int] = dict.fromkeys(STATUS_LABELS, 0)
        for status, count in self._conn.execute("SELECT status, COUNT(*) FROM tracked_issues GROUP BY status"):
            counts[status] = count
        return counts

    def close(self) -> None:
        self._conn.close()

    def _require(self, repo: str, number: int) -> TrackedIssue:
        item = self.get(repo, number)
        if item is None:
            raise KeyError(f"{repo}#{number} is not tracked")
        return item


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _from_row(row: tuple) -> TrackedIssue:
    return TrackedIssue(**dict(zip(_COLUMNS.split(", "), row, strict=True)))
