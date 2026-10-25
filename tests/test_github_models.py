from __future__ import annotations

from issuepilot.github.models import Comment, Issue

RAW_ISSUE = {
    "number": 42,
    "title": "Improve error handling",
    "body": "Errors are swallowed silently in the parser.",
    "state": "open",
    "labels": [{"name": "good first issue"}, {"name": "bug"}],
    "user": {"login": "octocat"},
    "comments": 2,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "html_url": "https://github.com/octo/hello/issues/42",
}

RAW_COMMENTS = [
    {"id": 1, "user": {"login": "alice"}, "body": "I can take this.", "created_at": "2026-01-01T01:00:00Z"},
    {"id": 2, "user": {"login": "bob"}, "body": None, "created_at": "2026-01-01T02:00:00Z"},
]


def test_comment_from_api_handles_null_body() -> None:
    comment = Comment.from_api(RAW_COMMENTS[1])

    assert comment.author == "bob"
    assert comment.body == ""


def test_issue_from_api_parses_labels_and_comments() -> None:
    issue = Issue.from_api(RAW_ISSUE, RAW_COMMENTS)

    assert issue.number == 42
    assert issue.labels == ["good first issue", "bug"]
    assert issue.author == "octocat"
    assert issue.comment_count == 2
    assert len(issue.comments) == 2
    assert issue.comments[0].author == "alice"


def test_issue_from_api_handles_null_body_and_no_comments() -> None:
    raw = dict(RAW_ISSUE, body=None)

    issue = Issue.from_api(raw)

    assert issue.body == ""
    assert issue.comments == []
