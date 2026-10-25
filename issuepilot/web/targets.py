"""Parse the user's analyze target: `owner/repo` or a GitHub issue/PR URL."""

import re

from fastapi import HTTPException

_REPO_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:github\.com/)?"
    r"(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?"
    r"(?:/(?:issues|pull)/(?P<issue>\d+))?/?(?:[?#].*)?$"
)


def parse_target(repo: str, issue: int | None) -> tuple[str, str, int]:
    """Accept `owner/repo` or a full GitHub issue/repo URL."""
    m = _REPO_RE.match(repo.strip())
    if not m:
        raise HTTPException(400, f"expected owner/repo or a GitHub issue URL, got: {repo}")
    number = issue or (int(m["issue"]) if m["issue"] else None)
    if number is None:
        raise HTTPException(400, "issue number is required")
    return m["owner"], m["repo"], number
