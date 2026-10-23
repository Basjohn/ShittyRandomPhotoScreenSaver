"""Qt-free coverage for Reddit worker preparation and cache persistence."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import os
import time

import pytest

from core.reddit_preparation import (
    REDDIT_RESERVOIR_CAPACITY,
    RedditPost,
    dedupe_reddit_candidates,
    get_reddit_cached_timestamp,
    load_reddit_startup_snapshot,
    normalize_reddit_rows,
    prepare_reddit_feed,
    read_reddit_post_cache,
    reddit_reservoir_path,
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
        subreddit="python",
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


def _posts(prefix: str, count: int, *, newest: float) -> tuple[RedditPost, ...]:
    return tuple(
        RedditPost(
            title=f"{prefix} {index}",
            url=f"https://example.com/{prefix.casefold()}/{index}",
            score=index,
            created_utc=newest - index,
        )
        for index in range(count)
    )


def _prepare(rows, cache_path, *, source_id="rss", subreddit="python", current=()):
    return prepare_reddit_feed(
        rows,
        source_id=source_id,
        attempted_sources=(source_id,),
        current_candidates=current,
        cache_path=cache_path,
        cache_key="reddit",
        subreddit=subreddit,
        candidate_limit=LIST_WIDGET_MAX_CAPACITY,
    )


def test_normal_feed_preparation_deduplicates_url_variants_before_persisting(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    prepared = _prepare(
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
        cache_path,
    )

    assert [post.title for post in prepared.candidates] == ["Newer duplicate"]
    assert read_reddit_post_cache(cache_path, "python") == prepared.candidates


def test_refetched_post_keeps_its_newest_snapshot(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    stale = RedditPost("Post", "https://example.com/post", 1, 10.0)
    assert write_reddit_post_cache(cache_path, (stale,), "python")
    rescored = RedditPost("Post", "https://example.com/post", 99, 10.0)

    prepared = _prepare([_row(rescored)], cache_path)

    assert prepared.candidates == (rescored,)


@pytest.mark.parametrize("source_id", ["rss", "pullpush", "public_json", "html_old", "html_www"])
def test_successive_three_post_batches_accumulate_for_every_source(tmp_path, source_id) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    batches = [_posts(f"Batch{index}", 3, newest=1_000.0 + 100.0 * index) for index in range(4)]

    seen: list[RedditPost] = []
    for batch in batches:
        prepared = _prepare([_row(post) for post in batch], cache_path, source_id=source_id)
        seen.extend(batch)
        assert set(prepared.candidates) == set(seen)

    assert len(prepared.candidates) == 12
    assert prepared.candidates == sort_reddit_candidates(seen)
    assert read_reddit_post_cache(cache_path, "python") == prepared.candidates


def test_full_window_survives_one_post_rss_and_three_post_fallback(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    full = _posts("Cached", LIST_WIDGET_MAX_CAPACITY, newest=1_000.0)
    assert write_reddit_post_cache(cache_path, full, "python")

    single = RedditPost("Single", "https://example.com/single", 1, 2_000.0)
    after_rss = _prepare([_row(single)], cache_path, source_id="rss")
    assert len(after_rss.candidates) == LIST_WIDGET_MAX_CAPACITY
    assert after_rss.candidates[0] == single

    fallback = _posts("Fallback", 3, newest=500.0)
    after_html = _prepare([_row(post) for post in fallback], cache_path, source_id="html_old")
    # Older fallback posts do not displace the newer display window...
    assert after_html.candidates == after_rss.candidates
    # ...but they join the reservoir instead of being discarded.
    reservoir = read_reddit_post_cache(cache_path, "python")
    assert len(reservoir) == LIST_WIDGET_MAX_CAPACITY + 1 + 3
    assert set(fallback) <= set(reservoir)


def test_old_posts_are_retained_without_age_expiry(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    ancient = RedditPost("Ancient", "https://example.com/ancient", 1, 1.0)
    assert write_reddit_post_cache(cache_path, (ancient,), "python")
    fresh = RedditPost("Fresh", "https://example.com/fresh", 1, time.time())

    prepared = _prepare([_row(fresh)], cache_path)

    assert prepared.candidates == (fresh, ancient)


def test_reservoir_capacity_evicts_only_for_newer_posts(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    full = _posts("Kept", REDDIT_RESERVOIR_CAPACITY, newest=1_000_000.0)
    assert write_reddit_post_cache(cache_path, full, "python")

    older = RedditPost("Older", "https://example.com/older", 1, 1.0)
    _prepare([_row(older)], cache_path)
    reservoir = read_reddit_post_cache(cache_path, "python")
    assert len(reservoir) == REDDIT_RESERVOIR_CAPACITY
    assert set(reservoir) == set(full)

    newer = RedditPost("Newer", "https://example.com/newer", 1, 2_000_000.0)
    _prepare([_row(newer)], cache_path)
    reservoir = read_reddit_post_cache(cache_path, "python")
    assert len(reservoir) == REDDIT_RESERVOIR_CAPACITY
    assert reservoir[0] == newer
    assert full[-1] not in reservoir


def test_empty_preparation_does_not_freshen_or_shrink_existing_cache(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    old = RedditPost("Old", "https://example.com/old", 1, 1.0)
    assert write_reddit_post_cache(cache_path, (old,), "python")
    old_timestamp = time.time() - 3600.0
    os.utime(cache_path, (old_timestamp, old_timestamp))

    for rows in ([], [{"title": "Daily Discussion", "url": "https://example.com/daily"}]):
        prepared = _prepare(rows, cache_path)
        assert prepared.candidates == ()

    assert cache_path.stat().st_mtime == pytest.approx(old_timestamp, abs=1.0)
    assert read_reddit_post_cache(cache_path, "python") == (old,)


def test_reservoirs_are_isolated_by_subreddit_identity(tmp_path) -> None:
    python_path = reddit_reservoir_path(tmp_path, "reddit", "Python")
    pics_path = reddit_reservoir_path(tmp_path, "reddit", "pics")
    assert python_path == reddit_reservoir_path(tmp_path, "reddit", "python")
    assert python_path != pics_path
    assert python_path != reddit_reservoir_path(tmp_path, "reddit2", "python")
    assert python_path.name.endswith("_posts.json")

    python_post = RedditPost("Python", "https://example.com/python", 1, 10.0)
    pics_post = RedditPost("Pics", "https://example.com/pics", 1, 20.0)
    _prepare([_row(python_post)], python_path, subreddit="Python")
    _prepare([_row(pics_post)], pics_path, subreddit="pics")

    assert read_reddit_post_cache(python_path, "python") == (python_post,)
    assert read_reddit_post_cache(pics_path, "PICS") == (pics_post,)
    # A file whose recorded identity differs is never attributed to another subreddit.
    assert read_reddit_post_cache(python_path, "pics") == ()


def test_unidentified_legacy_window_is_not_attributed(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    legacy = RedditPost("Legacy", "https://example.com/legacy", 1, 10.0)
    cache_path.write_text(json.dumps([_row(legacy)]), encoding="utf-8")

    assert read_reddit_post_cache(cache_path, "python") == ()
    fresh = RedditPost("Fresh", "https://example.com/fresh", 1, 20.0)
    assert _prepare([_row(fresh)], cache_path).candidates == (fresh,)
    assert not write_reddit_post_cache(cache_path, (fresh,), "")


def test_startup_snapshot_loads_window_and_control_timestamps_into_memory(tmp_path) -> None:
    cache_path = tmp_path / "reddit_posts.json"
    gate_path = tmp_path / "reddit_gate.touch"
    older = RedditPost("Older", "https://example.com/older", 1, 10.0)
    newer = RedditPost("Newer", "https://example.com/newer", 2, 20.0)
    assert write_reddit_post_cache(cache_path, (older, newer), "python")
    old_cache_timestamp = time.time() - 3600.0
    os.utime(cache_path, (old_cache_timestamp, old_cache_timestamp))
    gate_timestamp = touch_reddit_marker(gate_path, "reddit_startup_gate\n")

    snapshot = load_reddit_startup_snapshot(
        cache_path, gate_path, subreddit="python", candidate_limit=LIST_WIDGET_MAX_CAPACITY
    )

    assert snapshot.candidates == (newer, older)
    assert snapshot.cache_timestamp is not None
    assert snapshot.cache_timestamp.timestamp() == pytest.approx(old_cache_timestamp, abs=1.0)
    assert snapshot.service_gate_timestamp == gate_timestamp
    assert load_reddit_startup_snapshot(
        cache_path, gate_path, subreddit="python", candidate_limit=1
    ).candidates == (newer,)

    cache_path.unlink()
    gate_path.unlink()
    assert get_reddit_cached_timestamp(cache_path) == snapshot.cache_timestamp
    assert get_reddit_cached_timestamp(gate_path) == snapshot.service_gate_timestamp
