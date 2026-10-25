from __future__ import annotations

import httpx
import pytest
import respx

from issuepilot.config import Settings
from issuepilot.github.cache import ResponseCache
from issuepilot.github.client import GitHubAPIError, GitHubClient, GitHubNotFoundError
from issuepilot.github.models import Issue

API = "https://api.github.com"


@pytest.fixture
def client(tmp_path) -> GitHubClient:
    settings = Settings(github_token="test-token", cache_db_path=tmp_path / "cache.db")
    return GitHubClient(settings=settings, cache=ResponseCache(settings.cache_db_path))


@respx.mock
def test_get_issue_success(client: GitHubClient) -> None:
    route = respx.get(f"{API}/repos/octo/hello/issues/1").mock(
        return_value=httpx.Response(200, json={"number": 1, "title": "Bug"}, headers={"ETag": '"abc"'})
    )

    issue = client.get_issue("octo", "hello", 1)

    assert route.called
    assert issue == {"number": 1, "title": "Bug"}


@respx.mock
def test_get_issue_uses_etag_cache_on_304(client: GitHubClient) -> None:
    route = respx.get(f"{API}/repos/octo/hello/issues/1")
    route.side_effect = [
        httpx.Response(200, json={"number": 1, "title": "Original"}, headers={"ETag": '"v1"'}),
        httpx.Response(304),
    ]

    first = client.get_issue("octo", "hello", 1)
    second = client.get_issue("octo", "hello", 1)

    assert first == second == {"number": 1, "title": "Original"}
    assert route.call_count == 2
    # the second request must have presented the cached ETag
    assert route.calls[1].request.headers["If-None-Match"] == '"v1"'


@respx.mock
def test_get_issue_not_found_raises(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octo/hello/issues/404").mock(return_value=httpx.Response(404, json={}))

    with pytest.raises(GitHubNotFoundError):
        client.get_issue("octo", "hello", 404)


@respx.mock
def test_get_issue_server_error_raises(client: GitHubClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("issuepilot.github.client.time.sleep", lambda _: None)
    respx.get(f"{API}/repos/octo/hello/issues/1").mock(return_value=httpx.Response(500))

    with pytest.raises(GitHubAPIError):
        client.get_issue("octo", "hello", 1)


@respx.mock
def test_retries_on_5xx_then_succeeds(client: GitHubClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("issuepilot.github.client.time.sleep", lambda _: None)
    route = respx.get(f"{API}/repos/octo/hello/issues/1")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(500),
        httpx.Response(200, json={"number": 1}, headers={"ETag": '"abc"'}),
    ]

    issue = client.get_issue("octo", "hello", 1)

    assert issue == {"number": 1}
    assert route.call_count == 3


@respx.mock
def test_list_issues_paginates_and_skips_pull_requests(client: GitHubClient) -> None:
    base_url = f"{API}/repos/octo/hello/issues"
    page2_url = f"{base_url}?state=open&per_page=100&page=2"

    # respx's params= match is a "contains" check, not exact — register the
    # more specific (page=2) route first so it's tried before the page-1
    # route, which would otherwise also match page-2 requests.
    respx.get(base_url, params={"state": "open", "per_page": "100", "page": "2"}).mock(
        return_value=httpx.Response(200, json=[{"number": 3}], headers={"ETag": '"p2"'})
    )
    respx.get(base_url, params={"state": "open", "per_page": "100"}).mock(
        return_value=httpx.Response(
            200,
            json=[{"number": 1}, {"number": 2, "pull_request": {}}],
            headers={"ETag": '"p1"', "Link": f'<{page2_url}>; rel="next"'},
        )
    )

    issues = list(client.list_issues("octo", "hello"))

    assert [i["number"] for i in issues] == [1, 3]


@respx.mock
def test_fetch_issue_returns_typed_issue_with_comments(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octo/hello/issues/1").mock(
        return_value=httpx.Response(
            200,
            headers={"ETag": '"abc"'},
            json={
                "number": 1,
                "title": "Bug",
                "body": "Something broke",
                "state": "open",
                "labels": [{"name": "bug"}],
                "user": {"login": "octocat"},
                "comments": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "html_url": "https://github.com/octo/hello/issues/1",
            },
        )
    )
    respx.get(f"{API}/repos/octo/hello/issues/1/comments", params={"per_page": "100"}).mock(
        return_value=httpx.Response(
            200,
            headers={"ETag": '"c1"'},
            json=[{"id": 9, "user": {"login": "alice"}, "body": "me too", "created_at": "2026-01-01T00:00:00Z"}],
        )
    )

    issue = client.fetch_issue("octo", "hello", 1)

    assert isinstance(issue, Issue)
    assert issue.title == "Bug"
    assert len(issue.comments) == 1
    assert issue.comments[0].author == "alice"


@respx.mock
def test_rate_limit_sleeps_until_reset_then_succeeds(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("issuepilot.github.client.time.sleep", slept.append)
    monkeypatch.setattr("issuepilot.github.client.time.time", lambda: 1_000.0)

    route = respx.get(f"{API}/repos/octo/hello/issues/1")
    route.side_effect = [
        httpx.Response(
            403,
            json={"message": "rate limited"},
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1010"},
        ),
        httpx.Response(200, json={"number": 1}, headers={"ETag": '"abc"'}),
    ]

    issue = client.get_issue("octo", "hello", 1)

    assert issue == {"number": 1}
    assert slept == [11]  # reset (1010) - now (1000) + 1
