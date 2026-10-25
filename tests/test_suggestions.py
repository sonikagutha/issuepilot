from __future__ import annotations

from datetime import date

from issuepilot.discovery.suggestions import build_search_query, load_curated, suggest_repos
from issuepilot.github.client import GitHubAPIError

TODAY = date(2026, 10, 25)


def _repo(name: str, stars: int, language: str = "Python") -> dict:
    return {
        "full_name": name,
        "description": f"{name} description",
        "language": language,
        "stargazers_count": stars,
        "html_url": f"https://github.com/{name}",
    }


class _FakeClient:
    def __init__(self, results: dict[str, list[dict]] | None = None, fail: bool = False) -> None:
        self.results = results or {}
        self.fail = fail
        self.queries: list[str] = []

    def search_repositories(self, query: str, sort: str = "stars", per_page: int = 10) -> list[dict]:
        self.queries.append(query)
        if self.fail:
            raise GitHubAPIError(403, "rate limited")
        language = query.split("language:")[1]
        return self.results.get(language, [])


def test_build_search_query_beginner() -> None:
    q = build_search_query("beginner", "python", TODAY)

    assert "good-first-issues:>=5" in q
    assert "stars:50..50000" in q
    assert "archived:false" in q
    assert "pushed:>=2026-07-27" in q
    assert q.endswith("language:python")


def test_build_search_query_advanced() -> None:
    q = build_search_query("advanced", "go", TODAY)

    assert "help-wanted-issues:>=10" in q
    assert "stars:>=2000" in q


def test_suggest_sorts_by_stars_and_limits() -> None:
    client = _FakeClient({"python": [_repo(f"o/r{i}", i * 10) for i in range(10)]})

    repos, fallback = suggest_repos(client, "beginner", ["python"], today=TODAY)

    assert fallback is False
    assert len(repos) == 6
    assert repos[0].full_name == "o/r9"
    assert repos[0].stars == 90


def test_suggest_dedupes() -> None:
    shared = _repo("o/shared", 500)
    client = _FakeClient({"python": [shared], "go": [shared, _repo("o/go", 100, "Go")]})

    repos, _ = suggest_repos(client, "beginner", ["python", "go"], today=TODAY)

    assert [r.full_name for r in repos] == ["o/shared", "o/go"]


def test_suggest_falls_back_to_curated() -> None:
    repos, fallback = suggest_repos(_FakeClient(fail=True), "beginner", ["rust"], today=TODAY)

    assert fallback is True
    assert repos
    assert all(r.language == "rust" for r in repos)


def test_suggest_empty_search_falls_back_to_curated() -> None:
    repos, fallback = suggest_repos(_FakeClient(), "beginner", ["go"], today=TODAY)

    assert fallback is True
    assert {r.full_name for r in repos} >= {"cli/cli"}


def test_load_curated_all_languages_when_empty() -> None:
    languages = {r.language for r in load_curated([])}

    assert languages >= {"python", "javascript", "go", "rust"}
