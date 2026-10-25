from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from issuepilot.config import Settings
from issuepilot.github.cache import ResponseCache
from issuepilot.github.client import GitHubAPIError, GitHubClient
from issuepilot.github.profile import load_profile_overview
from issuepilot.storage.profile import ProfileStore

API = "https://api.github.com"

USER = {
    "login": "octocat",
    "name": "The Octocat",
    "avatar_url": "https://avatars.githubusercontent.com/u/1",
    "html_url": "https://github.com/octocat",
    "bio": "I love open source",
    "public_repos": 8,
    "followers": 100,
}

CALENDAR = {
    "user": {
        "contributionsCollection": {
            "contributionCalendar": {
                "totalContributions": 5,
                "weeks": [
                    {
                        "contributionDays": [
                            {"date": "2026-10-18", "contributionCount": 0, "contributionLevel": "NONE"},
                            {"date": "2026-10-19", "contributionCount": 5, "contributionLevel": "FOURTH_QUARTILE"},
                        ]
                    }
                ],
            }
        }
    }
}

PRS = {
    "items": [
        {
            "title": "Fix parser",
            "number": 12,
            "html_url": "https://github.com/octo/hello/pull/12",
            "repository_url": "https://api.github.com/repos/octo/hello",
            "state": "closed",
            "updated_at": "2026-10-20T00:00:00Z",
            "pull_request": {"merged_at": "2026-10-20T00:00:00Z"},
        },
        {
            "title": "Add docs",
            "number": 3,
            "html_url": "https://github.com/octo/world/pull/3",
            "repository_url": "https://api.github.com/repos/octo/world",
            "state": "open",
            "updated_at": "2026-10-19T00:00:00Z",
            "pull_request": {"merged_at": None},
        },
    ]
}


@pytest.fixture
def client(tmp_path: Path) -> GitHubClient:
    settings = Settings(github_token="test-token", cache_db_path=tmp_path / "cache.db")
    return GitHubClient(settings=settings, cache=ResponseCache(settings.cache_db_path))


def test_profile_store_roundtrip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "app.db")
    assert store.get_username() is None

    store.set_username("octocat")
    store.close()

    reopened = ProfileStore(tmp_path / "app.db")
    assert reopened.get_username() == "octocat"
    reopened.clear()
    assert reopened.get_username() is None


@respx.mock
def test_graphql_returns_data(client: GitHubClient) -> None:
    route = respx.post(f"{API}/graphql").mock(return_value=httpx.Response(200, json={"data": CALENDAR}))

    data = client.graphql("query { viewer { login } }", {"login": "octocat"})

    assert data == CALENDAR
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"


@respx.mock
def test_graphql_errors_raise(client: GitHubClient) -> None:
    respx.post(f"{API}/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "Could not resolve to a User"}]})
    )

    with pytest.raises(GitHubAPIError, match="Could not resolve"):
        client.graphql("query { x }", {})


@respx.mock
def test_load_profile_overview(client: GitHubClient) -> None:
    respx.get(f"{API}/users/octocat").mock(return_value=httpx.Response(200, json=USER))
    respx.post(f"{API}/graphql").mock(return_value=httpx.Response(200, json={"data": CALENDAR}))
    search = respx.get(f"{API}/search/issues").mock(return_value=httpx.Response(200, json=PRS))

    overview = load_profile_overview(client, "octocat")

    assert overview.profile.name == "The Octocat"
    assert overview.calendar.total == 5
    assert [d.level for d in overview.calendar.weeks[0]] == [0, 4]
    assert [(pr.repo, pr.state) for pr in overview.pull_requests] == [("octo/hello", "merged"), ("octo/world", "open")]
    assert search.calls.last.request.url.params["q"] == "is:pr author:octocat"
