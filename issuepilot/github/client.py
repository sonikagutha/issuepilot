from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from issuepilot.config import Settings, get_settings
from issuepilot.github.cache import ResponseCache


class GitHubAPIError(Exception):
    """Non-2xx, non-304 response from the GitHub API that isn't retryable."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"GitHub API error {status_code}: {message}")
        self.status_code = status_code


class GitHubNotFoundError(GitHubAPIError):
    pass


class _RetryableStatus(Exception):
    """Internal signal telling tenacity a transient failure is worth retrying."""


class GitHubClient:
    """Thin, cached, retried wrapper over the GitHub REST API.

    Two distinct failure classes get two distinct retry strategies:
    transient errors (network blips, 5xx) use exponential backoff via
    tenacity, while hitting the rate limit uses a deterministic sleep
    until the reset time GitHub tells us in the response headers.
    """

    def __init__(self, settings: Settings | None = None, cache: ResponseCache | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache = cache or ResponseCache(self._settings.cache_db_path)
        self._http = httpx.Client(
            base_url=self._settings.github_api_base,
            headers={
                "Authorization": f"Bearer {self._settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._http.close()
        self._cache.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- public API -------------------------------------------------------

    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/issues/{number}")

    def list_issue_comments(self, owner: str, repo: str, number: int) -> Iterator[dict[str, Any]]:
        yield from self._paginate(f"/repos/{owner}/{repo}/issues/{number}/comments")

    def list_issues(
        self, owner: str, repo: str, state: str = "open", per_page: int = 100
    ) -> Iterator[dict[str, Any]]:
        for item in self._paginate(
            f"/repos/{owner}/{repo}/issues", params={"state": state, "per_page": per_page}
        ):
            if "pull_request" not in item:  # this endpoint returns PRs too
                yield item

    # -- internals ----------------------------------------------------------

    def _cache_key(self, path_or_url: str, params: dict[str, Any] | None) -> str:
        request = self._http.build_request("GET", path_or_url, params=params)
        return str(request.url)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        cache_key = self._cache_key(path, params)
        cached = self._cache.get(cache_key)
        headers = {"If-None-Match": cached.etag} if cached and cached.etag else {}

        response = self._send(path, params, headers)

        if response.status_code == 304 and cached:
            return json.loads(cached.body)
        if response.status_code == 200:
            self._cache.put(cache_key, response.headers.get("ETag"), response.text)
            return response.json()
        if response.status_code == 404:
            raise GitHubNotFoundError(404, f"not found: {path}")
        raise GitHubAPIError(response.status_code, response.text[:200])

    def _paginate(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        next_target: str | None = path
        next_params: dict[str, Any] | None = params

        while next_target is not None:
            cache_key = self._cache_key(next_target, next_params)
            cached = self._cache.get(cache_key)
            headers = {"If-None-Match": cached.etag} if cached and cached.etag else {}

            response = self._send(next_target, next_params, headers)

            if response.status_code == 304 and cached:
                body = json.loads(cached.body)
            elif response.status_code == 200:
                self._cache.put(cache_key, response.headers.get("ETag"), response.text)
                body = response.json()
            elif response.status_code == 404:
                raise GitHubNotFoundError(404, f"not found: {next_target}")
            else:
                raise GitHubAPIError(response.status_code, response.text[:200])

            yield from body

            next_link = response.links.get("next")
            next_target = next_link["url"] if next_link else None
            next_params = None  # the next-page URL already carries its own query string

    def _send(
        self, path_or_url: str, params: dict[str, Any] | None, headers: dict[str, str]
    ) -> httpx.Response:
        # Bounded loop, separate from the tenacity-driven backoff below: a
        # rate limit isn't a random transient failure, it's a known wait.
        for _ in range(5):
            try:
                response = self._request_with_backoff(path_or_url, params, headers)
            except _RetryableStatus as exc:
                raise GitHubAPIError(502, "upstream error persisted after retries") from exc
            if self._is_rate_limited(response):
                self._sleep_until_reset(response)
                continue
            return response
        raise GitHubAPIError(429, "exhausted rate-limit retries")

    @retry(
        retry=retry_if_exception_type(_RetryableStatus),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        reraise=True,
    )
    def _request_with_backoff(
        self, path_or_url: str, params: dict[str, Any] | None, headers: dict[str, str]
    ) -> httpx.Response:
        try:
            response = self._http.get(path_or_url, params=params, headers=headers)
        except httpx.TransportError as exc:
            raise _RetryableStatus() from exc

        if response.status_code >= 500:
            raise _RetryableStatus()
        return response

    @staticmethod
    def _is_rate_limited(response: httpx.Response) -> bool:
        if response.status_code not in (403, 429):
            return False
        return response.headers.get("X-RateLimit-Remaining") == "0" or "Retry-After" in response.headers

    @staticmethod
    def _sleep_until_reset(response: httpx.Response) -> None:
        if "Retry-After" in response.headers:
            wait_seconds = int(response.headers["Retry-After"])
        else:
            reset_at = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_seconds = max(0, reset_at - int(time.time())) + 1
        time.sleep(min(wait_seconds, 300))
