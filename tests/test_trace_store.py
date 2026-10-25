from __future__ import annotations

from pathlib import Path

import pytest

from issuepilot.observability.trace_store import TraceStore, trace


def _rows(store: TraceStore) -> list[tuple]:
    cursor = store._conn.execute("SELECT node_name, prompt_version, error FROM traces ORDER BY id")
    return cursor.fetchall()


def test_trace_records_success(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces.db")

    with trace(store, "issue_investigation", "v1"):
        pass

    rows = _rows(store)
    assert rows == [("issue_investigation", "v1", None)]


def test_trace_records_error_and_reraises(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces.db")

    with pytest.raises(ValueError):
        with trace(store, "issue_investigation", "v1"):
            raise ValueError("boom")

    rows = _rows(store)
    assert rows == [("issue_investigation", "v1", "boom")]
