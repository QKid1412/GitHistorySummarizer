"""Small GitHub REST client with pagination, retries, and rate-limit awareness."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

LOG = logging.getLogger(__name__)


class GitHubError(RuntimeError):
    """Base GitHub API error."""


class GitHubAuthenticationError(GitHubError):
    """Invalid, missing, or insufficient GitHub credentials."""


class GitHubClient:
    def __init__(self, token: str, timeout: int = 30, max_retries: int = 3) -> None:
        if not token:
            raise GitHubAuthenticationError("GITHUB_TOKEN is not configured. Add it to .env.")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-career-analyzer",
        })
        self.timeout = timeout
        self.max_retries = max_retries

    def get_current_user(self) -> dict[str, Any]:
        return self.get("/user")

    def get(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._request("GET", path_or_url, params=params)
        return response.json()

    def get_list(self, path_or_url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return list(self.paginate(path_or_url, params))

    def paginate(self, path_or_url: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        next_url: str | None = path_or_url
        next_params = {"per_page": 100, **(params or {})}
        while next_url:
            response = self._request("GET", next_url, params=next_params)
            payload = response.json()
            if not isinstance(payload, list):
                raise GitHubError(f"Expected a list from GitHub API endpoint {path_or_url}.")
            yield from payload
            next_url = response.links.get("next", {}).get("url")
            next_params = None

    def _request(self, method: str, path_or_url: str, params: dict[str, Any] | None = None) -> requests.Response:
        url = path_or_url if path_or_url.startswith("http") else f"https://api.github.com{path_or_url}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(method, url, params=params, timeout=self.timeout)
            except requests.RequestException as error:
                last_error = error
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise GitHubError(f"GitHub request failed: {error}") from error
            if response.status_code == 401:
                raise GitHubAuthenticationError("GitHub rejected the token. Check GITHUB_TOKEN in .env.")
            if response.status_code == 403 and (response.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in response.text.lower()):
                if attempt < self.max_retries:
                    self._wait_for_rate_limit(response)
                    continue
                raise GitHubError("GitHub API rate limit exceeded. Try again after it resets.")
            if response.status_code >= 500 and attempt < self.max_retries:
                time.sleep(2 ** attempt)
                continue
            if not response.ok:
                message = _api_message(response)
                raise GitHubError(f"GitHub API request failed ({response.status_code}): {message}")
            return response
        raise GitHubError(f"GitHub request failed: {last_error}")

    def _wait_for_rate_limit(self, response: requests.Response) -> None:
        reset = response.headers.get("X-RateLimit-Reset")
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            delay = min(int(retry_after), 60)
        elif reset and reset.isdigit():
            delay = min(max(1, int(reset) - int(datetime.now(timezone.utc).timestamp()) + 1), 60)
        else:
            delay = 5
        LOG.warning("GitHub rate limit reached; waiting %s seconds before retrying.", delay)
        time.sleep(delay)


def _api_message(response: requests.Response) -> str:
    try:
        return str(response.json().get("message", response.reason))
    except ValueError:
        return response.reason

