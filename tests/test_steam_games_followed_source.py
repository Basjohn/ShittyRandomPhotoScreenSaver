"""Source/cache-only Games You Follow contracts; no live Steam identity/network or Qt."""
from __future__ import annotations

import json
import dataclasses
import threading
import urllib.error
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

from core.steam.games_followed_source import (
    FollowedNewsSource, MAX_NEWS_APPS_PER_REFRESH, MAX_NEWS_ITEMS_PER_APP,
    MAX_SELECTED_STORIES, normalize_app_news,
)

FAKE_STEAMID = "76561197960265728"  # Published example, not user data.


class _Response:
    status = 200

    def __init__(self, payload):
        self.body = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, size=-1):
        return self.body.read(size)


def _story(appid, index, *, date=1_700_000_000, url=True):
    gid = str(123456000 + index)
    return {
        "gid": gid, "title": f"Patch {index}", "date": date + index,
        "feedlabel": "Steam News", "contents": "<script>never-cache</script>",
        "url": f"https://store.steampowered.com/news/app/{appid}/view/{gid}"
        if url else "https://evil.example/article?token=abc",
    }


def _opener(follows=(41, 42), *, news_count=2, denied_app=None, requests=None):
    def open_request(request, timeout):
        url = urlsplit(request.full_url)
        params = parse_qs(url.query)
        if requests is not None:
            requests.append((url.path, params, timeout))
        if "GetGamesFollowed" in url.path:
            assert timeout <= 12
            assert params == {"steamid": [FAKE_STEAMID]}
            return _Response({"response": {"appids": list(follows)}})
        assert "GetNewsForApp" in url.path
        assert params.get("count") == [str(MAX_NEWS_ITEMS_PER_APP)]
        assert "key" not in params and "steamid" not in params
        assert timeout == 6
        appid = int(params["appid"][0])
        if appid == denied_app:
            raise urllib.error.HTTPError(request.full_url, 429, "rate limited", {}, None)
        return _Response({"appnews": {"appid": appid, "newsitems": [
            _story(appid, i, date=1_700_000_000 + appid * 10) for i in range(news_count)
        ]}})
    return open_request


def _source(tmp_path):
    from core.steam.credentials import derive_profile_cache_key
    return FollowedNewsSource(
        profile_key=derive_profile_cache_key(FAKE_STEAMID), cache_root=tmp_path / "private",
    )


def test_host_initializes_foreground_osd_lanes_and_retires_both():
    from pathlib import Path
    host = (Path(__file__).resolve().parents[1] / "rendering/quick/widgets/host.py").read_text("utf-8")
    assert "self._foreground_host_item: QQuickItem | None = foreground_host_item" in host
    assert "self._foreground_shadow_host_item: QQuickItem | None = foreground_shadow_host_item" in host
    assert "self._foreground_host_item = None" in host
    assert "self._foreground_shadow_host_item = None" in host


def test_bounded_fetch_cache_and_private_normalization(tmp_path):
    source = _source(tmp_path)
    requests = []
    snap = source.refresh(FAKE_STEAMID, opener=_opener(tuple(range(41, 59)), news_count=3, requests=requests))
    assert snap.status == "available" and not snap.from_cache
    assert snap.followed_count == 18 and snap.checked_count == MAX_NEWS_APPS_PER_REFRESH
    assert len(snap.stories) == MAX_SELECTED_STORIES
    assert [story.published_at for story in snap.stories] == sorted(
        [story.published_at for story in snap.stories], reverse=True)
    assert all(story.action_available for story in snap.stories)
    assert len(requests) == 1 + MAX_NEWS_APPS_PER_REFRESH
    assert all("GetGamesFollowed" in p or "GetNewsForApp" in p for p, _, _ in requests)
    cached = source.cached()
    assert cached is not None and cached.from_cache and cached.stories == snap.stories
    raw = (tmp_path / "private" / "games_you_follow_news.json").read_text("utf-8")
    assert FAKE_STEAMID not in raw and "<script>" not in raw
    assert "evil.example" not in raw and "https://" not in raw and "contents" not in raw
    assert "steamid" not in raw.lower() and "api_key" not in raw


def test_repeated_selection_offset_is_bounded_and_independent_of_qml(tmp_path):
    source = _source(tmp_path)
    seen = []
    snap = source.refresh(FAKE_STEAMID, opener=_opener(tuple(range(40, 47)), requests=seen), window_offset=5)
    requested = [int(params["appid"][0]) for path, params, _ in seen if "GetNewsForApp" in path]
    assert requested == [45, 46, 40, 41]
    assert snap.followed_count == 7 and snap.checked_count == 4 and snap.window_offset == 5
    assert source.cached().window_offset == 5


def test_private_per_app_cache_survives_restart_and_recovers_global_runner_ups(tmp_path):
    """A complete 12-game scan persists all observed rows, not just eight winners."""
    follows = tuple(range(1001, 1013))
    calls = []
    quiet_last = [False]
    base = _opener(follows, news_count=2, requests=calls)

    def provider(request, timeout):
        url = urlsplit(request.full_url)
        if "GetNewsForApp" in url.path and quiet_last[0] and int(parse_qs(url.query)["appid"][0]) == follows[-1]:
            calls.append((url.path, parse_qs(url.query), timeout))
            return _Response({"appnews": {"appid": follows[-1], "newsitems": []}})
        return base(request, timeout)

    source = _source(tmp_path)
    for _ in range(3):
        full = source.refresh(FAKE_STEAMID, opener=provider)
    assert full.covered_count == len(follows)
    assert len(full.stories) == 8
    assert sum("GetGamesFollowed" in path for path, _, _ in calls) == 1
    record = json.loads((tmp_path / "private" / "games_you_follow_news.json").read_text("utf-8"))
    buckets = record["payload"]["per_game_stories"]
    assert len(buckets) == len(follows)
    assert all(len(rows) == 2 for rows in buckets.values())
    source.retire()

    reopened = _source(tmp_path)
    assert reopened.cached().stories == full.stories
    quiet_last[0] = True
    revised = reopened.refresh(FAKE_STEAMID, opener=provider, window_offset=11)
    assert len(revised.stories) == 8
    assert all(story.appid != follows[-1] for story in revised.stories)
    assert [story.published_at for story in revised.stories] == sorted(
        (story.published_at for story in revised.stories), reverse=True)
    # Explicit offset is an operator-probe override and reconfirms membership;
    # ordinary scheduled maintenance reuses recently confirmed membership.
    assert sum("GetGamesFollowed" in path for path, _, _ in calls) == 2


def test_failed_or_partial_refresh_retains_last_good_without_freshening(tmp_path):
    source = _source(tmp_path)
    good = source.refresh(FAKE_STEAMID, opener=_opener())
    good_bytes = (tmp_path / "private" / "games_you_follow_news.json").read_bytes()
    stale = source.refresh(FAKE_STEAMID, opener=_opener(denied_app=42))
    assert stale.status == "stale_cache" and stale.failure == "rate_limited"
    assert stale.stories == good.stories and stale.fetched_at == good.fetched_at
    assert (tmp_path / "private" / "games_you_follow_news.json").read_bytes() == good_bytes
    # Existing request policy now prevents an immediate retry after the 429.
    assert source.refresh(FAKE_STEAMID, opener=lambda *_: (_ for _ in ()).throw(
        AssertionError("backoff may not perform Steam IO"))).failure == "backoff_active"
    # A fresh owner may still read the same private last-good record and
    # independently classify a genuine 403, without a forced retry here.
    second = _source(tmp_path)
    assert second.refresh(FAKE_STEAMID, opener=lambda req, timeout: (_ for _ in ()).throw(
        urllib.error.HTTPError(req.full_url, 403, "denied", {}, None))).failure == "unauthorized"
    assert (tmp_path / "private" / "games_you_follow_news.json").read_bytes() == good_bytes


def test_empty_followed_set_vs_empty_news_vs_denied(tmp_path):
    source = _source(tmp_path)
    empty = source.refresh(FAKE_STEAMID, opener=_opener((), news_count=0))
    assert empty.status == "empty_follow_list" and empty.followed_count == 0 and empty.checked_count == 0
    no_news = source.refresh(FAKE_STEAMID, opener=_opener((41,), news_count=0))
    assert no_news.status == "no_usable_news" and no_news.followed_count == 1 and no_news.checked_count == 1
    denied = _source(tmp_path / "new").refresh(FAKE_STEAMID, opener=_opener(denied_app=41))
    assert denied.status == "rate_limited" and denied.fetched_at is None and not denied.stories


def test_news_normalization_constructs_canonical_link_without_trusting_provider_url_or_html():
    appid = 42
    row = _story(appid, 1, url=False)
    result = normalize_app_news({"appnews": {"appid": appid, "newsitems": [row]}}, appid)
    # The public app-news response validates appid/GID; a hostile syndication
    # link is NEVER opened. Clicks use a separately validated Steam Store URL.
    assert result is not None and result[0].action_available
    assert "url" not in vars(result[0]) and "contents" not in vars(result[0])
    bad = (
        {"appnews": {"appid": 99, "newsitems": []}},
        {"appnews": {"appid": appid, "newsitems": "invalid"}},
        {"appnews": {"appid": appid, "newsitems": [_story(appid, 1)] * 2}},
        {"appnews": {"appid": appid, "newsitems": [{**_story(appid, 1), "date": True}]}},
        {"appnews": {"appid": appid, "newsitems": [{**_story(appid, 1), "gid": "../bad"}]}},
        {"appnews": {"appid": appid, "newsitems": [_story(appid, 1)] * 9}},
    )
    assert all(normalize_app_news(payload, appid) is None for payload in bad)


def test_retired_source_drops_network_completions_and_cache_publication(tmp_path):
    source = _source(tmp_path)
    entered = threading.Event()
    released = threading.Event()
    outcomes = []

    def opener(req, timeout):
        if "GetGamesFollowed" in req.full_url:
            entered.set()
            assert released.wait(2)
        return _opener()(req, timeout)

    thread = threading.Thread(target=lambda: outcomes.append(source.refresh(FAKE_STEAMID, opener=opener)))
    thread.start()
    assert entered.wait(2)
    source.retire()
    released.set()
    thread.join(2)
    assert not thread.is_alive() and outcomes[0].status == "retired"
    assert source.cached() is None
    assert source.refresh(FAKE_STEAMID, opener=_opener()).status == "retired"


def test_source_is_opt_in_and_does_not_create_worker_or_gui_scheduler():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    module = (root / "core/steam/games_followed_source.py").read_text("utf-8")
    assert not any(word in module for word in ("QTimer", "QQuick", "QThread", "Timer(", "singleShot(", "time.sleep(", "ThreadPoolExecutor"))
    # Real family admission is now possible, but importing a Settings or QML
    # component alone must never start the neutral source or read credentials.
    registry = (root / "rendering/quick/widgets/registry.py").read_text("utf-8")
    services = (root / "rendering/widget_runtime_services.py").read_text("utf-8")
    assert 'qml_filename="GamesYouFollowPresentation.qml"' in registry
    # Dormant service registration is permitted: it only constructs an inert
    # lease after the family is admitted, never fetches on module import.
    assert '"steam_progress": _FOLLOWED_SERVICE_SPEC' in services
    assert 'def _build_followed_service(' in services
    assert '"steam_progress": _FOLLOWED_SERVICE_SPEC' not in registry


def test_profile_identity_swap_cannot_read_or_overwrite_previous_private_cache(tmp_path):
    source = _source(tmp_path)
    accepted = source.refresh(FAKE_STEAMID, opener=_opener())
    assert accepted.status == "available"
    path = tmp_path / "private" / "games_you_follow_news.json"
    previous = path.read_bytes()
    # Both are syntactically valid 17-digit IDs; only the linked identity owns
    # this opaque account cache. No network or stale cross-account presentation.
    forbidden = source.refresh("76561197960265729", opener=lambda *_: (_ for _ in ()).throw(
        AssertionError("Wrong profile must not issue source requests")))
    assert forbidden.status == "invalid_identity" and forbidden.stories == ()
    assert path.read_bytes() == previous


def test_bounded_backoff_prevents_repeat_denials_and_preserves_last_good(tmp_path):
    from core.steam.credentials import derive_profile_cache_key
    tick = [100.0]
    source = FollowedNewsSource(
        profile_key=derive_profile_cache_key(FAKE_STEAMID),
        cache_root=tmp_path / "private", clock=lambda: tick[0],
    )
    good = source.refresh(FAKE_STEAMID, opener=_opener())
    cache_path = tmp_path / "private" / "games_you_follow_news.json"
    good_bytes = cache_path.read_bytes()
    initial_requests = []
    failure = source.refresh(
        FAKE_STEAMID, opener=_opener(denied_app=42, requests=initial_requests),
    )
    assert failure.status == "stale_cache" and failure.failure == "rate_limited"
    assert initial_requests and cache_path.read_bytes() == good_bytes
    for _ in range(50):
        result = source.refresh(
            FAKE_STEAMID, opener=lambda *_: (_ for _ in ()).throw(
                AssertionError("No requests may bypass Steam source backoff")
            ),
        )
        assert result.status == "stale_cache" and result.failure == "backoff_active"
        assert result.stories == good.stories and result.fetched_at == good.fetched_at
    assert cache_path.read_bytes() == good_bytes
    tick[0] += 61.0
    requests = []
    recovered = source.refresh(FAKE_STEAMID, opener=_opener(requests=requests))
    assert recovered.status == "available" and len(requests) == 2
    assert all("GetNewsForApp" in path for path, _, _ in requests)
    assert recovered.stories == good.stories


def test_denied_source_without_cache_is_bounded_until_explicit_retry_due(tmp_path):
    from core.steam.credentials import derive_profile_cache_key
    tick = [100.0]
    source = FollowedNewsSource(
        profile_key=derive_profile_cache_key(FAKE_STEAMID),
        cache_root=tmp_path / "private", clock=lambda: tick[0],
    )
    assert source.refresh(FAKE_STEAMID, opener=_opener(denied_app=42)).status == "rate_limited"
    for _ in range(10):
        assert source.refresh(FAKE_STEAMID, opener=lambda *_: (_ for _ in ()).throw(
            AssertionError("backoff no network"))).status == "backoff_active"
    assert source.cached() is None
    source.retire()
    tick[0] += 1000
    assert source.refresh(FAKE_STEAMID, opener=lambda *_: (_ for _ in ()).throw(
        AssertionError("retired no network"))).status == "retired"


def test_default_refresh_rotates_bounded_followed_window_without_explicit_offsets(tmp_path):
    source = _source(tmp_path)
    follow_set = tuple(range(41, 51))
    offsets = []
    windows = []
    for _ in range(4):
        seen = []
        snap = source.refresh(FAKE_STEAMID, opener=_opener(follow_set, requests=seen))
        offsets.append(snap.window_offset)
        windows.append(tuple(int(q["appid"][0]) for path, q, _ in seen if "GetNewsForApp" in path))
        assert snap.checked_count <= MAX_NEWS_APPS_PER_REFRESH
    assert offsets == [0, 4, 8, 0]
    assert windows == [(41, 42, 43, 44), (45, 46, 47, 48),
                       (49, 50), (41, 42, 43, 44)]
    assert source.cached().window_offset == 0


def test_source_previews_are_bounded_plain_text_and_do_not_cache_feed_html(tmp_path):
    source = _source(tmp_path)

    def opener(req, timeout):
        response = _opener((41,), news_count=1)(req, timeout)
        if "GetNewsForApp" not in req.full_url:
            return response
        row = _story(41, 0)
        row["contents"] = "<p>A &amp; B</p><script>secret()</script><b>Patch details</b> " + ("x" * 1000)
        return _Response({"appnews": {"appid": 41, "newsitems": [row]}})

    snap = source.refresh(FAKE_STEAMID, opener=opener)
    assert snap.status == "available"
    assert snap.stories[0].preview.startswith("A & B Patch details")
    assert len(snap.stories[0].preview) <= 320
    raw = (tmp_path / "private" / "games_you_follow_news.json").read_text("utf-8")
    assert "secret()" not in raw and "<p>" not in raw and "contents" not in raw
    assert source.cached().stories[0].preview == snap.stories[0].preview


def test_source_filters_explicit_foreign_language_and_repeat_event_before_selection():
    from core.steam.games_followed_source import _latest_unique
    app = 548430
    en = _story(app, 4, date=1_700_000_000)
    en["title"] = "Hotfix for Minor Bugs"
    en["language"] = "english"
    en["url"] = (f"https://steamcommunity.com/games/DeepRockGalactic/"
                 f"announcements/detail/{en['gid']}")
    foreign = _story(app, 5, date=1_700_000_000)
    foreign["title"] = "Corrections des bugs mineurs [French]"
    foreign["language"] = "french"
    unknown = _story(app, 6, date=1_700_000_000)
    unknown["title"] = "Hotfix for Minor Bugs [English]"
    result = normalize_app_news({"appnews": {"appid": app,
                               "newsitems": [en, foreign, unknown]}}, app)
    assert result is not None and len(result) == 2
    assert result[0].action_available
    assert [s.title for s in _latest_unique(list(result))] == ["Hotfix for Minor Bugs"]
    # A different game with the same generic headline is a different event.
    assert len(_latest_unique([*result, dataclasses.replace(result[0], appid=app+1)])) == 2


def test_progressive_bounded_sweep_keeps_newest_story_from_later_followed_games(tmp_path):
    source = _source(tmp_path)
    follows = tuple(range(101, 112))
    opener = _opener(follows=follows, news_count=1)
    first = source.refresh(FAKE_STEAMID, opener=opener)
    second = source.refresh(FAKE_STEAMID, opener=opener)
    third = source.refresh(FAKE_STEAMID, opener=opener)
    assert (first.covered_count, second.covered_count, third.covered_count) == (4, 8, 11)
    assert third.checked_count == 3  # Initial sweep never re-probes early games.
    assert [s.published_at for s in third.stories] == sorted(
        [s.published_at for s in third.stories], reverse=True)
    assert third.stories[0].appid == follows[-1]
    assert source.cached().stories == third.stories


def test_same_second_translated_posts_are_one_event_but_different_seconds_remain():
    from core.steam.games_followed_source import _latest_unique, FollowedNewsStory
    en = FollowedNewsStory(41, "998", "Latest patch notes", 1700000000, "News", True)
    french = FollowedNewsStory(41, "999", "Notes de mise à jour", 1700000000, "News", True)
    independent = FollowedNewsStory(41, "1000", "Separate hotfix", 1700000011, "News", True)
    chosen = _latest_unique([en, french, independent])
    assert [row.gid for row in chosen] == ["1000", "998"]


def test_latest_news_across_complete_142_game_sweep_is_timestamp_ordered(tmp_path):
    follows = tuple(range(41, 183))
    source = _source(tmp_path)
    opener = _opener(follows=follows, news_count=1)
    result = None
    for _ in range((len(follows) + MAX_NEWS_APPS_PER_REFRESH - 1) // MAX_NEWS_APPS_PER_REFRESH):
        result = source.refresh(FAKE_STEAMID, opener=opener)
    assert result is not None and result.covered_count == len(follows)
    assert result.followed_count == 142 and len(result.stories) == 8
    assert [s.appid for s in result.stories] == list(reversed(follows[-8:]))
    assert [s.published_at for s in result.stories] == sorted(
        (s.published_at for s in result.stories), reverse=True)


def test_full_142_game_cache_is_maintained_eight_at_a_time_not_reswept(tmp_path):
    """The first complete sweep happens once; maintenance survives process restart."""
    follows = tuple(range(41, 183))
    requests = []
    provider = _opener(follows=follows, news_count=1, requests=requests)
    source = _source(tmp_path)
    snapshots = [source.refresh(FAKE_STEAMID, opener=provider) for _ in range(36)]
    assert snapshots[-1].covered_count == 142
    assert snapshots[-1].checked_count == 2  # No wrap-and-refetch at the end.
    assert not snapshots[-1].maintenance_pending
    initial_apps = [int(query["appid"][0]) for path, query, _ in requests
                    if "GetNewsForApp" in path]
    assert initial_apps == list(follows)
    assert sum("GetGamesFollowed" in path for path, _, _ in requests) == 1

    requests.clear()
    first = source.refresh(FAKE_STEAMID, opener=provider)
    assert first.covered_count == 142 and first.maintenance_pending
    assert first.checked_count == 4 and first.window_offset == 0
    source.retire()

    resumed = _source(tmp_path)
    warm = resumed.cached()
    assert warm is not None and warm.maintenance_pending and warm.covered_count == 142
    second = resumed.refresh(FAKE_STEAMID, opener=provider)
    assert second.covered_count == 142 and not second.maintenance_pending
    assert second.window_offset == 4 and second.checked_count == 4
    next_session = resumed.refresh(FAKE_STEAMID, opener=provider)
    assert next_session.window_offset == 8 and next_session.maintenance_pending
    assert [int(query["appid"][0]) for path, query, _ in requests
            if "GetNewsForApp" in path] == list(follows[:12])
    # The already validated membership never triggers a fresh 142-app inquiry
    # for these separate maintenance sessions within its 24-hour TTL.
    assert not any("GetGamesFollowed" in path for path, _, _ in requests)
    assert resumed.cached().stories[0].appid == follows[-1]  # Latest global winner persists.


def test_maintenance_revalidates_membership_when_stale_and_rebuilds_on_change(tmp_path):
    follows = tuple(range(41, 50))
    source = _source(tmp_path)
    for _ in range(3):
        full = source.refresh(FAKE_STEAMID, opener=_opener(follows))
    assert full.covered_count == len(follows)
    path = tmp_path / "private" / "games_you_follow_news.json"
    record = json.loads(path.read_text("utf-8"))
    record["payload"]["membership_checked_at"] -= 25 * 60 * 60
    path.write_text(json.dumps(record), encoding="utf-8")
    source.retire()
    refreshed = _source(tmp_path)
    requests = []
    changed = (*follows[:-1], 999)
    current = refreshed.refresh(FAKE_STEAMID, opener=_opener(changed, requests=requests))
    assert sum("GetGamesFollowed" in path for path, _, _ in requests) == 1
    assert current.covered_count == 4 and not current.maintenance_pending
    assert all(story.appid != follows[-1] for story in current.stories)
    assert refreshed.cached().followed_count == len(changed)


def test_steam_preview_removes_bbcode_and_image_macros_without_source_urls():
    from core.steam.games_followed_source import _plain_preview
    text = '<p>[b]Update[/b] [p]You can play now![/p] {STEAM_CLAN_IMAGE}/123/abc.png [url=https://evil.example/track]More[/url]</p>'
    result = _plain_preview(text)
    assert 'Update' in result and 'You can play now!' in result
    assert '[p]' not in result and '[b]' not in result and 'STEAM_CLAN_IMAGE' not in result
    assert 'evil.example' not in result and 'http' not in result
