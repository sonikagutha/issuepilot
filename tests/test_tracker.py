from __future__ import annotations

from pathlib import Path

import pytest

from issuepilot.storage.tracker import STATUS_LABELS, Tracker


@pytest.fixture
def tracker(tmp_path: Path) -> Tracker:
    return Tracker(tmp_path / "app.db")


def _star(tracker: Tracker, number: int = 1):
    return tracker.star("octo/hello", number, f"Issue {number}", f"https://github.com/octo/hello/issues/{number}")


def test_star_and_get(tracker: Tracker) -> None:
    item = _star(tracker)

    assert item.status == "starred"
    assert item.note == ""
    assert tracker.get("octo/hello", 1) == item
    assert tracker.get("octo/hello", 2) is None


def test_star_is_idempotent(tracker: Tracker) -> None:
    _star(tracker)
    tracker.update("octo/hello", 1, status="working", note="started")

    again = _star(tracker)

    assert again.status == "working"
    assert again.note == "started"


def test_update_untracked_raises_key_error(tracker: Tracker) -> None:
    with pytest.raises(KeyError):
        tracker.update("octo/hello", 99, status="working")


def test_update_sets_fields(tracker: Tracker) -> None:
    _star(tracker)

    item = tracker.update(
        "octo/hello", 1, pr_url="https://github.com/octo/hello/pull/5", pr_state="open", status="pr_opened"
    )

    assert item.pr_url == "https://github.com/octo/hello/pull/5"
    assert item.pr_state == "open"
    assert item.status == "pr_opened"


def test_remove(tracker: Tracker) -> None:
    _star(tracker)

    assert tracker.remove("octo/hello", 1) is True
    assert tracker.remove("octo/hello", 1) is False
    assert tracker.get("octo/hello", 1) is None


def test_counts_include_every_status(tracker: Tracker) -> None:
    _star(tracker, 1)
    _star(tracker, 2)
    tracker.update("octo/hello", 2, status="merged")

    counts = tracker.counts()

    assert set(counts) == set(STATUS_LABELS)
    assert counts["starred"] == 1
    assert counts["merged"] == 1
    assert counts["dropped"] == 0


def test_list_most_recently_updated_first(tracker: Tracker) -> None:
    _star(tracker, 1)
    _star(tracker, 2)
    tracker.update("octo/hello", 1, note="bump")

    assert [i.number for i in tracker.list()] == [1, 2]


def test_tracker_persists_across_instances(tmp_path: Path) -> None:
    first = Tracker(tmp_path / "app.db")
    first.star("octo/hello", 1, "Issue 1", "https://github.com/octo/hello/issues/1")
    first.close()

    second = Tracker(tmp_path / "app.db")

    assert second.get("octo/hello", 1) is not None
