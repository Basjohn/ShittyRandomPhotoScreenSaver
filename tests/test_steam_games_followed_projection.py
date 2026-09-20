"""Provider-safe followed-news projection, adaptive geometry and dormancy gates."""
from dataclasses import fields
from pathlib import Path

import pytest

from core.steam.games_followed_projection import project_followed_news
from core.steam.games_followed_source import FollowedNewsSnapshot, FollowedNewsStory
from widgets.steam_followed_layout import followed_news_layout


def _snapshot():
    return FollowedNewsSnapshot(
        "available",
        tuple(FollowedNewsStory(41 + i, str(123456 + i), f"Patch {i}\n{chr(32)}Update", 1700000000 + i,
                                "Steam\tNews", True) for i in range(8)),
        followed_count=142, checked_count=4,
    )


def test_snapshot_projection_never_exposes_private_source_identity_or_unverified_action():
    source = _snapshot()
    shown = project_followed_news(source)
    assert shown.selected_story_count == 8 and shown.checked_count == 4
    assert shown.remaining_followed_count == 138
    assert shown.rows[0].title == "Patch 0 Update"
    assert shown.rows[0].source_label == "Steam News"
    assert shown.rows[0].published_label == "14 Nov 2023"
    assert all(row.action_enabled and not row.local_artwork_source for row in shown.rows)
    assert not any("appid" in field.name or "gid" in field.name or "url" in field.name
                   or "steamid" in field.name for field in fields(shown.rows[0]))
    assert all("http" not in str(row) and "123456" not in str(row) for row in shown.rows)
    assert source.stories[0].appid == 41  # Private identity stays with source, not UI.


def test_cache_and_failure_labels_do_not_invent_empty_news_or_update_age():
    original = _snapshot()
    cached = FollowedNewsSnapshot("stale_cache", original.stories, 142, 4,
                                 fetched_at=1700000000.0, from_cache=True, failure="rate_limited")
    shown = project_followed_news(cached)
    assert shown.status_label == "Cached updates" and shown.stale and len(shown.rows) == 8
    assert project_followed_news(FollowedNewsSnapshot("empty_follow_list")).status_label == "No games followed"
    assert project_followed_news(FollowedNewsSnapshot("no_usable_news", followed_count=142, checked_count=4)).status_label == "No updates in checked games"
    assert project_followed_news(FollowedNewsSnapshot("rate_limited")).status_label == "Updates temporarily unavailable"
    assert project_followed_news(FollowedNewsSnapshot("retired")).status_label == ""


def test_independent_xy_reflow_changes_only_visible_capacity_never_source_set():
    source = _snapshot()
    projection = project_followed_news(source)
    wide = followed_news_layout(900, 260, len(projection.rows))
    tall = followed_news_layout(290, 1100, len(projection.rows))
    square = followed_news_layout(550, 540, len(projection.rows))
    assert (wide.arrangement, tall.arrangement, square.arrangement) == ("wide", "tall", "grid")
    assert wide.visible_count > 0 and tall.visible_count > 0 and square.visible_count > 0
    for layout in (wide, tall, square):
        assert layout.visible_count + layout.overflow_count == len(projection.rows)
    assert len(source.stories) == len(projection.rows) == 8
    tiny = followed_news_layout(160, 130, len(projection.rows))
    assert tiny.visible_count == 0 and tiny.overflow_count == 8
    assert followed_news_layout(900, 260, 0).visible_count == 0
    # A small two-axis drag near either aspect boundary must not alternate
    # between a horizontal rail and grid every pointer event.
    wide_hold = followed_news_layout(168, 100, 8, previous_arrangement="wide")
    wide_exit = followed_news_layout(150, 100, 8, previous_arrangement="wide")
    assert wide_hold.arrangement == "wide" and wide_exit.arrangement == "grid"
    tall_hold = followed_news_layout(82, 100, 8, previous_arrangement="tall")
    tall_exit = followed_news_layout(90, 100, 8, previous_arrangement="tall")
    assert tall_hold.arrangement == "tall" and tall_exit.arrangement == "grid"
    with pytest.raises(ValueError):
        followed_news_layout(float("nan"), 260, 8)


def test_projection_and_layout_have_no_qt_backend_network_or_schedulers():
    root = Path(__file__).resolve().parents[1]
    for filename in ("core/steam/games_followed_projection.py", "widgets/steam_followed_layout.py"):
        content = (root / filename).read_text("utf-8")
        assert not any(word in content for word in ("QTimer", "QQuick", "QThread", "ThreadManager", "fetch_json(", "time.sleep(", "SettingsManager", "get_steam_source_refresh_lock"))



def test_followed_wide_rail_and_large_grid_capacity_match_retained_qml():
    """The pure parent layout must never promise a different default tile rail."""
    wide = followed_news_layout(960, 450, 8)
    assert wide.arrangement == "wide" and wide.rows == 3
    assert wide.visible_count == 8 and wide.overflow_count == 0
    # Five image-capable cards on each 1,570 px wide row; two rows of eight.
    screenshot = followed_news_layout(1570, 700, 8)
    assert (screenshot.columns, screenshot.visible_count, screenshot.overflow_count) == (5, 8, 0)
    # Extreme vertical keeps one readable tile rather than hiding all art.
    portrait = followed_news_layout(290, 1100, 8)
    assert portrait.columns == 1 and portrait.visible_count == 8
    grid = followed_news_layout(1300, 900, 8)
    assert grid.arrangement == "grid" and grid.columns == 4
    assert grid.visible_count == 8 and grid.overflow_count == 0


def test_preview_and_local_artwork_only_traverse_the_safe_view_projection(tmp_path):
    local = tmp_path / "cached-art.jpg"
    local.write_bytes(b"existing-local-file")
    snapshot = FollowedNewsSnapshot(
        "available", (FollowedNewsStory(41, "123456", "Patch", 1700000000, "Steam News",
                                        True, "<b>do not interpret as HTML</b>", "Verified Name"),),
        followed_count=1, checked_count=1, artwork_paths=(str(local),),
    )
    shown = project_followed_news(snapshot)
    assert shown.rows[0].game_label == "Verified Name"
    assert shown.rows[0].preview == "<b>do not interpret as HTML</b>"
    assert shown.rows[0].local_artwork_source == local.as_uri()
    assert shown.rows[0].action_enabled
    assert not any("appid" in name or "gid" in name or "provider" in name.lower()
                   for name in vars(shown.rows[0]))
