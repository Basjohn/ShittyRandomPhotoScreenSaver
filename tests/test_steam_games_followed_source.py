"""Source/cache-only Games You Follow contracts; no live Steam identity/network or Qt."""
from __future__ import annotations

import json
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


def test_news_normalization_strict_identity_no_untrusted_link_or_html():
    appid = 42
    row = _story(appid, 1, url=False)
    result = normalize_app_news({"appnews": {"appid": appid, "newsitems": [row]}}, appid)
    assert result is not None and not result[0].action_available
    assert "url" not in vars(result[0]) and "contents" not in vars(result[0])
    bad = (
        {"appnews": {"appid": 99, "newsitems": []}},
        {"appnews": {"appid": appid, "newsitems": "invalid"}},
        {"appnews": {"appid": appid, "newsitems": [_story(appid, 1)] * 2}},
        {"appnews": {"appid": appid, "newsitems": [{**_story(appid, 1), "date": True}]}},
        {"appnews": {"appid": appid, "newsitems": [{**_story(appid, 1), "gid": "../bad"}]}},
        {"appnews": {"appid": appid, "newsitems": [_story(appid, 1)] * 4}},
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
    # G2 staging may contain an inert retained QML component. What matters is
    # that no active family adapter/service can construct it or start requests
    # merely because it is present on disk.
    registry = (root / "rendering/quick/widgets/registry.py").read_text("utf-8")
    services = (root / "rendering/widget_runtime_services.py").read_text("utf-8")
    assert 'qml_filename="GamesYouFollowPresentation.qml"' not in registry
    assert '"steam_progress": _FOLLOWED' not in services


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
    assert recovered.status == "available" and len(requests) == 3
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
