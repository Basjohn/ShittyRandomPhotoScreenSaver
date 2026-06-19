from __future__ import annotations

import pytest

from core.reddit_post_provider import (
    PullPushProvider,
    RedditFetchRequest,
    build_reddit_post_provider,
    normalize_reddit_provider_id,
)


class _StubResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_normalize_reddit_provider_defaults_to_pullpush() -> None:
    assert normalize_reddit_provider_id(None) == "pullpush"
    assert normalize_reddit_provider_id("unknown") == "pullpush"
    assert normalize_reddit_provider_id("public_json") == "public_json"


def test_build_reddit_post_provider_uses_configured_provider() -> None:
    assert type(build_reddit_post_provider("pullpush")).__name__ == "PullPushProvider"
    assert type(build_reddit_post_provider("public_json")).__name__ == "RedditPublicJsonProvider"


def test_pullpush_provider_maps_submission_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def _fake_get(url, params=None, timeout=None):  # noqa: ANN001
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _StubResponse(
            {
                "data": [
                    {
                        "title": "Mapped post",
                        "permalink": "/r/python/comments/abc123/mapped_post/",
                        "score": 77,
                        "created_utc": 1710000000,
                    }
                ]
            }
        )

    monkeypatch.setattr("core.reddit_post_provider.requests.get", _fake_get)

    provider = PullPushProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=10,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert captured["url"] == "https://api.pullpush.io/reddit/search/submission/"
    assert captured["params"]["subreddit"] == "python"
    assert captured["params"]["sort"] == "desc"
    assert captured["params"]["sort_type"] == "created_utc"
    assert captured["params"]["size"] == 10
    assert captured["timeout"] == 10
    assert result.skip_reason is None
    assert result.posts == [
        {
            "title": "Mapped post",
            "url": "https://www.reddit.com/r/python/comments/abc123/mapped_post/",
            "score": 77,
            "created_utc": 1710000000.0,
        }
    ]


def test_pullpush_provider_filters_rows_missing_title_or_link(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.reddit_post_provider.requests.get",
        lambda *args, **kwargs: _StubResponse(  # noqa: ANN001
            {
                "data": [
                    {"title": "", "permalink": "/r/python/comments/abc123/missing_title/"},
                    {"title": "Missing link"},
                    {"title": "Direct link", "url": "https://example.com/direct", "created_utc": 1710000001},
                ]
            }
        ),
    )

    provider = PullPushProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=10,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert result.posts == [
        {
            "title": "Direct link",
            "url": "https://example.com/direct",
            "score": 0,
            "created_utc": 1710000001.0,
        }
    ]


def test_pullpush_provider_returns_empty_posts_for_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.reddit_post_provider.requests.get",
        lambda *args, **kwargs: _StubResponse({"data": []}),  # noqa: ANN001
    )

    provider = PullPushProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=10,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert result.posts == []
    assert result.skip_reason is None


def test_pullpush_provider_surfaces_network_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("network down")

    monkeypatch.setattr("core.reddit_post_provider.requests.get", _boom)

    provider = PullPushProvider()
    with pytest.raises(RuntimeError, match="network down"):
        provider.fetch_posts(
            RedditFetchRequest(
                subreddit="python",
                sort="hot",
                limit=10,
                cache_key="reddit",
                shutdown_event=None,
            )
        )
