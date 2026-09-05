from __future__ import annotations

from datetime import date

import pytest

from app.github.client import GitHubAuthenticationError, GitHubClient
from app.github.models import PullRequest, RepositoryInfo
from app.github.prs import PRService, prepared_diff


class Response:
    def __init__(self, status_code, payload, links=None, headers=None, reason="Bad Request"):
        self.status_code, self._payload, self.links, self.headers, self.reason = status_code, payload, links or {}, headers or {}, reason
        self.ok = 200 <= status_code < 300
        self.text = str(payload)

    def json(self):
        return self._payload


def test_authentication_failure_is_helpful(monkeypatch):
    client = GitHubClient("not-a-real-token", max_retries=0)
    monkeypatch.setattr(client.session, "request", lambda *args, **kwargs: Response(401, {"message": "Bad credentials"}))
    with pytest.raises(GitHubAuthenticationError):
        client.get_current_user()


def test_pagination_uses_next_link(monkeypatch):
    client = GitHubClient("token")
    calls = []
    responses = [Response(200, [{"id": 1}], links={"next": {"url": "https://api.github.com/next"}}), Response(200, [{"id": 2}])]
    def request(*args, **kwargs):
        calls.append(args[1])
        return responses.pop(0)
    monkeypatch.setattr(client.session, "request", request)
    assert client.get_list("/example") == [{"id": 1}, {"id": 2}]
    assert calls == ["https://api.github.com/example", "https://api.github.com/next"]


def test_pr_retrieval_filters_author_and_date():
    class FakeClient:
        def get(self, path):
            return {"full_name": "org/repo", "description": None, "language": "Python", "organization": {"login": "org"}}
        def get_list(self, path, params=None):
            return [
                {"number": 1, "title": "Mine", "body": None, "state": "closed", "created_at": "2024-03-01T00:00:00Z", "updated_at": "2024-03-02T00:00:00Z", "closed_at": None, "merged_at": None, "user": {"login": "me"}, "labels": [], "html_url": "https://example/1"},
                {"number": 2, "title": "Other", "body": None, "state": "open", "created_at": "2024-03-01T00:00:00Z", "updated_at": "2024-03-02T00:00:00Z", "user": {"login": "other"}, "labels": [], "html_url": "https://example/2"},
            ]
    prs = PRService(FakeClient()).list_pull_requests("org/repo", "me", date(2024, 1, 1), date(2024, 12, 31))
    assert [pr.number for pr in prs] == [1]


def test_missing_patch_continues_with_file_metadata():
    from app.github.models import ChangedFile
    diff, partial = prepared_diff([ChangedFile(filename="image.png", status="modified", changes=1, patch=None)], 100)
    assert "patch unavailable" in diff
    assert partial is True


def test_rate_limit_retries(monkeypatch):
    client = GitHubClient("token", max_retries=1)
    responses = [Response(403, {"message": "rate limit"}, headers={"X-RateLimit-Remaining": "0", "Retry-After": "0"}), Response(200, {"login": "me"})]
    monkeypatch.setattr(client.session, "request", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr("app.github.client.time.sleep", lambda value: None)
    assert client.get_current_user()["login"] == "me"
