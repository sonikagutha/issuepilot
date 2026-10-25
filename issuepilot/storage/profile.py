from __future__ import annotations

import sqlite3
from pathlib import Path


class ProfileStore:
    """Remembers which GitHub username is linked to this local dashboard.

    A one-row key/value table in the same app.db as the Tracker; IssuePilot
    runs locally for a single person, so there is exactly one profile.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._conn.commit()

    def get_username(self) -> str | None:
        row = self._conn.execute("SELECT value FROM app_settings WHERE key = 'github_username'").fetchone()
        return row[0] if row else None

    def set_username(self, username: str) -> None:
        self._conn.execute(
            "INSERT INTO app_settings (key, value) VALUES ('github_username', ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (username,),
        )
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM app_settings WHERE key = 'github_username'")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
