from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Protocol

import yaml
from pydantic import BaseModel

from issuepilot.github.client import GitHubAPIError

Level = Literal["beginner", "intermediate", "advanced"]

LEVELS: tuple[Level, ...] = ("beginner", "intermediate", "advanced")
LANGUAGES: tuple[str, ...] = ("python", "javascript", "typescript", "go", "rust", "java")

# Label to browse on a suggested repo's page, per level.
ISSUE_LABEL: dict[Level, str] = {
    "beginner": "good first issue",
    "intermediate": "help wanted",
    "advanced": "help wanted",
}

_LEVEL_QUALIFIERS: dict[Level, str] = {
    "beginner": "good-first-issues:>=5 stars:50..50000",
    "intermediate": "help-wanted-issues:>=5 stars:>=500",
    "advanced": "help-wanted-issues:>=10 stars:>=2000",
}

CURATED_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "starter_repos.yaml"


class RepoSearcher(Protocol):
    def search_repositories(self, query: str, sort: str = "stars", per_page: int = 10) -> list[dict]: ...


class RepoSuggestion(BaseModel):
    full_name: str
    description: str
    language: str
    stars: int
    html_url: str


def build_search_query(level: Level, language: str, today: date) -> str:
    """GitHub repository-search query for active repos that welcome this level."""
    pushed_since = (today - timedelta(days=90)).isoformat()
    return f"{_LEVEL_QUALIFIERS[level]} archived:false is:public pushed:>={pushed_since} language:{language}"


def suggest_repos(
    client: RepoSearcher,
    level: Level,
    languages: list[str],
    *,
    today: date | None = None,
    limit: int = 6,
) -> tuple[list[RepoSuggestion], bool]:
    """Suggested repos plus whether they came from the curated fallback.

    Any search failure (rate limit, network) falls back to the curated
    list for the whole page rather than showing a partial mix.
    """
    today = today or date.today()
    languages = languages or list(LANGUAGES)
    found: dict[str, RepoSuggestion] = {}
    try:
        for language in languages:
            for item in client.search_repositories(build_search_query(level, language, today)):
                found.setdefault(item["full_name"], _from_search(item))
    except GitHubAPIError:
        found = {}

    if not found:
        return _top(load_curated(languages), limit), True
    return _top(list(found.values()), limit), False


def load_curated(languages: list[str]) -> list[RepoSuggestion]:
    raw = yaml.safe_load(CURATED_PATH.read_text())
    wanted = set(languages)
    return [
        RepoSuggestion(html_url=f"https://github.com/{entry['full_name']}", **entry)
        for entry in raw["repos"]
        if not wanted or entry["language"] in wanted
    ]


def _from_search(item: dict) -> RepoSuggestion:
    return RepoSuggestion(
        full_name=item["full_name"],
        description=item.get("description") or "",
        language=(item.get("language") or "").lower(),
        stars=item.get("stargazers_count", 0),
        html_url=item["html_url"],
    )


def _top(repos: list[RepoSuggestion], limit: int) -> list[RepoSuggestion]:
    return sorted(repos, key=lambda r: r.stars, reverse=True)[:limit]
