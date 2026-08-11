"""Qt-free coverage for Reddit worker preparation and cache persistence."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import os
import time

import pytest

from core.reddit_preparation import (
    RedditPost,
    dedupe_reddit_candidates,
    get_reddit_cached_timestamp,
    load_reddit_startup_snapshot,
    normalize_reddit_rows,
    prepare_reddit_feed,
    read_reddit_post_cache,
    sort_reddit_candidates,
    touch_reddit_marker,
    write_reddit_post_cache,
)
from core.settings.widget_capacity_policy import LIST_WIDGET_MAX_CAPACITY


def _row(post: RedditPost) -> dict[str, object]:
    return {
        "title": post.title,
        "url": post.url,
        "score": post.score,
        "created_utc": post.created_utc,
    }


def test_reddit_post_and_prepared_candidates_are_immutable() -> None:
    post = RedditPost("Post", "https://example.com/post", 1, 10.0)

    with pytest.raises(FrozenInstanceError):
        post.title = "Changed"  # type: ignore[misc]

    prepared = prepare_reddit_feed(
        [_row(post)],
        source_id="rss",
        attempted_sources=("rss",),
        current_candidates=(),
        cache_path=None,
        cache_key="reddit",
        candidate_limit=LIST_WIDGET_MAX_CAPACITY,
    )
    assert prepared.candidates == (post,)
    assert isinstance(prepared.candidates, tuple)


def test_normalize_reddit_rows_preserves_filter_and_numeric_fallback_contract() -> None:
    posts = normalize_reddit_rows(
        [
            {
                "title": " Daily Discussion Thread ",
                "url": "https://example.com/filtered",
                "score": 5,
                "created_utc": 50,
            },
            {
                "title": "A dailyish update",
                "url": " https://example.com/kept ",
                "score": "invalid",
                "created_utc": "invalid",
            },
            {"title": "Missing URL", "url": ""},
        ]
    )

    assert posts == (
        RedditPost(
            title="A dailyish update",
            url="https://example.com/kept",
            score=0,
            created_utc=0.0,
        ),
    )


def test_candidate_dedupe_and_sort_keep_newest_duplicate_and_sink_undated() -> None:
    old = RedditPost("Old", "https://example.com/post?ref=old", 1, 10.0)
    new = RedditPost("New", "https://example.com/post#new", 2, 20.0)
    other = RedditPost("Other", "https://example.com/other", 3, 15.0)
    undated = RedditPost("Undated", "https://example.com/undated", 4, 0.0)

    deduped = dedupe_reddit_candidates((old, other, new, undated))
    sorted_posts = sort_reddit_candidates(deduped)

    assert [post.title for post in sorted_posts] == ["New", "Other", "Undated"]


def test_normal_feed_preparation_deduplicates_url_variants_before_persisting(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    prepared = prepare_reddit_feed(
        [
            {
                "title": "Older duplicate",
                "url": "https://example.com/post?ref=old",
                "score": 1,
                "created_utc": 10.0,
            },
            {
                "title": "Newer duplicate",
                "url": "https://example.com/post#new",
                "score": 2,
                "created_utc": 20.0,
            },
        ],
        source_id="rss",
        attempted_sources=("rss",),
        current_candidates=(),
        cache_path=cache_path,
        cache_key="reddit",
        candidate_limit=LIST_WIDGET_MAX_CAPACITY,
    )

    assert [post.title for post in prepared.candidates] == ["Newer duplicate"]
    assert read_reddit_post_cache(cache_path) == prepared.candidates


def test_sparse_html_preparation_merges_persisted_window_and_writes_final_cache(tmp_path) -> None:
    cache_path = tmp_path / "nested" / "reddit_posts.json"
    persisted = tuple(
        RedditPost(
            title=f"Cached {index}",
            url=f"https://example.com/cached/{index}",
            score=index,
            created_utc=1_700_000_000.0 - index,
        )
        for index in range(LIST_WIDGET_MAX_CAPACITY)
    )
    assert write_reddit_post_cache(cache_path, persisted)

    fresh = RedditPost(
        "Fresh sparse fallback",
        "https://example.com/fresh",
        100,
        1_700_000_500.0,
    )
    prepared = prepare_reddit_feed(
        [_row(fresh)],
        source_id="html_old",
        attempted_sources=("rss", "html_old"),
        current_candidates=(),
        cache_path=cache_path,
        cache_key="reddit",
        candidate_limit=LIST_WIDGET_MAX_CAPACITY,
    )

    assert len(prepared.candidates) == LIST_WIDGET_MAX_CAPACITY
    assert prepared.candidates[0] == fresh
    assert "Cached 24" not in {post.title for post in prepared.candidates}
    assert read_reddit_post_cache(cache_path) == prepared.candidates


def test_sparse_rss_result_remains_authoritative(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    cached = RedditPost("Cached", "https://example.com/cached", 1, 10.0)
    incoming = RedditPost("RSS", "https://example.com/rss", 2, 20.0)
    assert write_reddit_post_cache(cache_path, (cached,))

    prepared = prepare_reddit_feed(
        [_row(incoming)],
        source_id="rss",
        attempted_sources=("rss",),
        current_candidates=(cached,),
        cache_path=cache_path,
        cache_key="reddit",
        candidate_limit=LIST_WIDGET_MAX_CAPACITY,
    )

    assert prepared.candidates == (incoming,)
    assert read_reddit_post_cache(cache_path) == (incoming,)


def test_empty_preparation_does_not_freshen_existing_cache(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    cache_path.write_text(json.dumps([_row(RedditPost("Old", "https://example.com/old", 1, 1.0))]))
    old_timestamp = time.time() - 3600.0
    os.utime(cache_path, (old_timestamp, old_timestamp))

    prepared = prepare_reddit_feed(
        [],
        source_id="rss",
        attempted_sources=("rss",),
        current_candidates=(),
        cache_path=cache_path,
        cache_key="reddit",
        candidate_limit=LIST_WIDGET_MAX_CAPACITY,
    )

    assert prepared.candidates == ()
    assert prepared.raw_count == 0
    assert cache_path.stat().st_mtime == pytest.approx(old_timestamp, abs=1.0)


def test_startup_snapshot_loads_posts_and_control_timestamps_into_memory(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    gate_path = tmp_path / "reddit_gate.touch"
    older = RedditPost("Older", "https://example.com/older", 1, 10.0)
    newer = RedditPost("Newer", "https://example.com/newer", 2, 20.0)
    assert write_reddit_post_cache(cache_path, (older, newer))
    old_cache_timestamp = time.time() - 3600.0
    os.utime(cache_path, (old_cache_timestamp, old_cache_timestamp))
    gate_timestamp = touch_reddit_marker(gate_path, "reddit_startup_gate\n")

    snapshot = load_reddit_startup_snapshot(cache_path, gate_path)

    assert snapshot.candidates == (newer, older)
    assert snapshot.cache_timestamp is not None
    assert snapshot.cache_timestamp.timestamp() == pytest.approx(old_cache_timestamp, abs=1.0)
    assert snapshot.service_gate_timestamp == gate_timestamp

    cache_path.unlink()
    gate_path.unlink()
    assert get_reddit_cached_timestamp(cache_path) == snapshot.cache_timestamp
    assert get_reddit_cached_timestamp(gate_path) == snapshot.service_gate_timestamp
