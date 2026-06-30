from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.reddit_post_provider import (
    FallbackRedditPostProvider,
    PullPushProvider,
    RedditFetchRequest,
    RedditHtmlProvider,
    RedditRssProvider,
    build_reddit_post_provider,
    normalize_reddit_provider_id,
)


class _StubResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200, content: bytes | None = None) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = content or b""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict:
        return self._payload or {}


def test_normalize_reddit_provider_defaults_to_rss() -> None:
    assert normalize_reddit_provider_id(None) == "rss"
    assert normalize_reddit_provider_id("unknown") == "rss"
    assert normalize_reddit_provider_id("rss") == "rss"
    assert normalize_reddit_provider_id("html") == "html"
    assert normalize_reddit_provider_id("public_json") == "public_json"


def test_build_reddit_post_provider_uses_configured_provider() -> None:
    rss_provider = build_reddit_post_provider("rss")
    pullpush_provider = build_reddit_post_provider("pullpush")
    json_provider = build_reddit_post_provider("public_json")
    html_provider = build_reddit_post_provider("html")

    assert type(rss_provider).__name__ == "FallbackRedditPostProvider"
    assert type(getattr(rss_provider, "primary")).__name__ == "RedditRssProvider"
    assert type(pullpush_provider).__name__ == "FallbackRedditPostProvider"
    assert type(getattr(pullpush_provider, "primary")).__name__ == "PullPushProvider"
    assert type(json_provider).__name__ == "FallbackRedditPostProvider"
    assert type(getattr(json_provider, "primary")).__name__ == "RedditPublicJsonProvider"
    assert type(html_provider).__name__ == "RedditHtmlProvider"


def test_rss_provider_maps_atom_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    atom_feed = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Fresh post</title>
    <updated>2026-06-19T18:39:20+00:00</updated>
    <link rel="alternate" href="https://www.reddit.com/r/SubredditDrama/comments/abc/fresh_post/" />
  </entry>
</feed>
"""

    def _fake_get(url, headers=None, timeout=None):  # noqa: ANN001
        calls.append({"url": url, "headers": dict(headers or {}), "timeout": timeout})
        return _StubResponse(content=atom_feed)

    monkeypatch.setattr("core.reddit_post_provider._acquire_widget_reddit_request_slot", lambda request: "acquired")
    monkeypatch.setattr("core.reddit_post_provider.requests.get", _fake_get)

    provider = RedditRssProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="SubredditDrama",
            sort="hot",
            limit=10,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert len(calls) == 1
    assert calls[0]["url"] == "https://www.reddit.com/r/SubredditDrama/.rss"
    assert calls[0]["timeout"] == 10
    assert "application/atom+xml" in calls[0]["headers"]["Accept"]
    assert result.skip_reason is None
    assert result.posts == [
        {
            "title": "Fresh post",
            "url": "https://www.reddit.com/r/SubredditDrama/comments/abc/fresh_post/",
            "score": 0,
            "created_utc": float(datetime(2026, 6, 19, 18, 39, 20, tzinfo=timezone.utc).timestamp()),
        }
    ]


def test_html_provider_maps_standard_reddit_shreddit_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    html_payload = b"""
<html><body>
  <shreddit-post
    post-title="Standard &amp; fresh"
    permalink="/r/python/comments/std123/standard_fresh/"
    score="1.2k"
    created-timestamp="2026-06-30T10:11:12+00:00">
  </shreddit-post>
</body></html>
"""

    def _fake_get(url, headers=None, timeout=None):  # noqa: ANN001
        calls.append({"url": url, "headers": dict(headers or {}), "timeout": timeout})
        return _StubResponse(content=html_payload)

    monkeypatch.setattr("core.reddit_post_provider._acquire_widget_reddit_request_slot", lambda request: "acquired")
    monkeypatch.setattr("core.reddit_post_provider.requests.get", _fake_get)

    provider = RedditHtmlProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=25,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert len(calls) == 1
    assert calls[0]["url"] == "https://www.reddit.com/r/python/"
    assert "text/html" in calls[0]["headers"]["Accept"]
    assert result.skip_reason is None
    assert result.posts == [
        {
            "title": "Standard & fresh",
            "url": "https://www.reddit.com/r/python/comments/std123/standard_fresh/",
            "score": 1200,
            "created_utc": float(datetime(2026, 6, 30, 10, 11, 12, tzinfo=timezone.utc).timestamp()),
        }
    ]


def test_html_provider_falls_from_standard_to_old_reddit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    old_payload = b"""
<html><body>
  <div class="thing id-t3_old123" data-permalink="/r/python/comments/old123/old_fresh/" data-score="42" data-timestamp="1710000200000">
    <p class="title">
      <a class="title may-blank" href="/r/python/comments/old123/old_fresh/">Old fresh</a>
    </p>
  </div>
</body></html>
"""

    def _fake_get(url, headers=None, timeout=None):  # noqa: ANN001
        calls.append(url)
        if "www.reddit.com" in url:
            return _StubResponse(content=b"<html><body>No posts here</body></html>")
        return _StubResponse(content=old_payload)

    monkeypatch.setattr("core.reddit_post_provider._acquire_widget_reddit_request_slot", lambda request: "acquired")
    monkeypatch.setattr("core.reddit_post_provider.requests.get", _fake_get)

    provider = RedditHtmlProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=25,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert calls == ["https://www.reddit.com/r/python/", "https://old.reddit.com/r/python/"]
    assert result.posts == [
        {
            "title": "Old fresh",
            "url": "https://old.reddit.com/r/python/comments/old123/old_fresh/",
            "score": 42,
            "created_utc": 1710000200.0,
        }
    ]


def test_composite_provider_uses_html_after_primary_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    html_payload = b"""
<html><body>
  <shreddit-post post-title="Fallback post" permalink="/r/python/comments/fb/fallback_post/" created-timestamp="1710000200"></shreddit-post>
</body></html>
"""

    class FailingPrimary:
        provider_id = "rss"

        def fetch_posts(self, request):  # noqa: ANN001
            raise RuntimeError("rss down")

    def _fake_get(url, headers=None, timeout=None):  # noqa: ANN001
        calls.append(url)
        return _StubResponse(content=html_payload)

    monkeypatch.setattr("core.reddit_post_provider._acquire_widget_reddit_request_slot", lambda request: "acquired")
    monkeypatch.setattr("core.reddit_post_provider.requests.get", _fake_get)

    provider = FallbackRedditPostProvider(FailingPrimary())
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=25,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert calls == ["https://www.reddit.com/r/python/"]
    assert result.posts == [
        {
            "title": "Fallback post",
            "url": "https://www.reddit.com/r/python/comments/fb/fallback_post/",
            "score": 0,
            "created_utc": 1710000200.0,
        }
    ]


def test_pullpush_provider_maps_submission_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def _fake_get(url, params=None, timeout=None):  # noqa: ANN001
        calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
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
            limit=1,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.pullpush.io/reddit/search/submission/"
    assert calls[0]["params"]["subreddit"] == "python"
    assert calls[0]["params"]["size"] == 5
    assert calls[0]["timeout"] == 10
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


def test_pullpush_provider_uses_requested_limit_as_fetch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def _fake_get(url, params=None, timeout=None):  # noqa: ANN001
        calls.append(dict(params or {}))
        return _StubResponse(
            {
                "data": [
                    {
                        "title": "Recent post",
                        "permalink": "/r/python/comments/recent/recent_post/",
                        "score": 7,
                        "created_utc": 1710000200,
                    },
                ]
            }
        )

    monkeypatch.setattr("core.reddit_post_provider.requests.get", _fake_get)

    provider = PullPushProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=20,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert len(calls) == 1
    assert calls[0]["size"] == 20
    assert result.posts == [
        {
            "title": "Recent post",
            "url": "https://www.reddit.com/r/python/comments/recent/recent_post/",
            "score": 7,
            "created_utc": 1710000200.0,
        },
    ]


def test_pullpush_provider_dedupes_duplicate_rows_by_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.reddit_post_provider.requests.get",
        lambda *args, **kwargs: _StubResponse(  # noqa: ANN001
            {
                "data": [
                    {
                        "title": "Duplicate",
                        "permalink": "/r/python/comments/dup/duplicate/",
                        "score": 2,
                        "created_utc": 1710000000,
                    },
                    {
                        "title": "Duplicate",
                        "permalink": "/r/python/comments/dup/duplicate/",
                        "score": 9,
                        "created_utc": 1710000000,
                    },
                ]
            }
        ),
    )

    provider = PullPushProvider()
    result = provider.fetch_posts(
        RedditFetchRequest(
            subreddit="python",
            sort="hot",
            limit=5,
            cache_key="reddit",
            shutdown_event=None,
        )
    )

    assert result.posts == [
        {
            "title": "Duplicate",
            "url": "https://www.reddit.com/r/python/comments/dup/duplicate/",
            "score": 9,
            "created_utc": 1710000000.0,
        }
    ]
