"""No live network, Qt, persisted identity or widget admission in G0 news tests."""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pytest

from core.steam.games_followed_news_probe import (
    NEWS_PROBE_MAX_APPS,
    NEWS_PROBE_ITEMS_PER_APP,
    NEWS_PROBE_MAX_BYTES,
    normalize_news_sample,
    probe_followed_news,
)
from core.steam.games_followed_probe import fetch_followed_appids_for_news_probe
from tools.steam_followed_g0_probe import main


class _Response:
    status = 200

    def __init__(self, payload):
        self.stream = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, limit=-1):
        return self.stream.read(limit)


def _news(appid, *, items=None):
    return {"appnews": {"appid": appid, "newsitems": [
        {"gid": "123456789", "title": "Update", "date": 1_700_000_000,
         "url": "https://unsafe.example/private?steamid=FAKE", "contents": "<script>"}
    ] if items is None else items}}


def test_two_request_budget_one_per_followed_app_and_no_url_output():
    seen = []

    def opener(request, timeout):
        url = urlparse(request.full_url)
        params = parse_qs(url.query)
        seen.append((url.path, params, timeout))
        assert params["count"] == [str(NEWS_PROBE_ITEMS_PER_APP)]
        assert "key" not in params and "steamid" not in params
        assert timeout == 6.0
        return _Response(_news(int(params["appid"][0])))

    result = probe_followed_news((10, 20, 30, 40), opener=opener)
    assert (result.status, result.apps_checked, result.usable_items) == ("confirmed_nonempty_news", 2, 2)
    assert [params["appid"] for _, params, _ in seen] == [["10"], ["20"]]
    assert all("GetNewsForApp/v2" in path for path, _, _ in seen)
    assert NEWS_PROBE_MAX_APPS == 2


def test_fail_closed_followed_set_is_required_before_network():
    def forbidden(*_):
        raise AssertionError("No request permitted")

    for ids in ((), (0,), (-1,), (True,), (1, 1), ("1",), tuple(range(1, 4098))):
        assert probe_followed_news(ids, opener=forbidden).status == "invalid_followed_set"


def test_news_empty_vs_bad_schema_bad_id_or_bad_items():
    assert probe_followed_news([42], opener=lambda *_: _Response(_news(42, items=[]))).status == "confirmed_empty_news"
    for payload in ({}, {"appnews": {}}, _news(99), _news(42, items="no"),
                    _news(42, items=[{}]), _news(42, items=[{"gid": "1", "title": "x", "date": True}]),
                    _news(42, items=[{"gid": "1", "title": "x", "date": 1700000000}] * 2),
                    _news(42, items=[{"gid": "1", "title": "x", "date": 1700000000}] * 3)):
        assert probe_followed_news([42], opener=lambda *_: _Response(payload)).status == "invalid_response"
    assert normalize_news_sample(_news(42), 42) == 1
    assert normalize_news_sample({"appnews": {"appid": True, "newsitems": []}}, 1) is None


def test_statuses_payload_limit_and_stop_without_fanout():
    for status, expected in ((401, "private"), (403, "unauthorized"), (429, "rate_limited")):
        def denied(request, *_):
            raise urllib.error.HTTPError(request.full_url, status, "deny", {}, None)
        result = probe_followed_news([11, 22], opener=denied)
        assert (result.status, result.apps_checked) == (expected, 1)

    class Huge:
        status = 200
        def read(self, size=-1):
            assert size == NEWS_PROBE_MAX_BYTES + 1
            return b"x" * size
    assert probe_followed_news([11], opener=lambda *_: Huge()).status == "invalid_response"


def test_private_followed_ids_never_emitted_and_errors_distinguished():
    steamid = "76561197960265728"  # public fake ID only
    result, ids = fetch_followed_appids_for_news_probe(
        steamid, opener=lambda *_: _Response({"response": {"appids": [42]}}),
    )
    assert result == "confirmed_nonempty" and ids == (42,)
    result, ids = fetch_followed_appids_for_news_probe(
        steamid, opener=lambda *_: _Response({"response": {"appids": []}}),
    )
    assert result == "confirmed_empty" and ids == ()


def test_news_cli_is_explicit_private_and_does_not_start_widget(monkeypatch, capsys):
    from core.steam import credentials, games_followed_probe, games_followed_news_probe
    monkeypatch.setattr(credentials, "load_credentials", lambda: type("Credential", (), {"profile_identifier": "76561197960265728"})())
    monkeypatch.setattr(games_followed_probe, "fetch_followed_appids_for_news_probe", lambda steamid: ("confirmed_nonempty", (42,)))
    monkeypatch.setattr(games_followed_news_probe, "probe_followed_news", lambda ids: (
        games_followed_news_probe.FollowedNewsProbeResult("confirmed_nonempty_news", 1, 1)
    ))
    assert main(["--news-probe"]) == 0
    output = capsys.readouterr().out
    assert "confirmed_nonempty_news" in output and "apps_checked=1" in output
    assert "765611" not in output and "42" not in output and "http" not in output
    with pytest.raises(SystemExit):
        main([])


def test_news_article_links_use_source_event_id_and_constrain_steam_hosts():
    from core.steam.links import news_article_target, news_hub_target
    gid = "123456789"
    store = "https://store.steampowered.com/news/app/42/view/987654321"
    community = "https://steamcommunity.com/games/Some_Game/announcements/detail/876543210"
    for url in (store, community,
                "https://steamcommunity.com/app/42/announcements/detail/876543210"):
        target = news_article_target(42, gid, url)
        assert target is not None and target.browser_url == url and target.kind == "news_article"
    # Syndicated news does not have a Steam /view/ event ID. Steam's public
    # API supplies an externalpost link whose final number IS the news GID.
    external = "https://steamstore-a.akamaihd.net/news/externalpost/PCGamesN/123456789"
    target = news_article_target(42, gid, external)
    assert target is not None and target.browser_url == external and target.kind == "news_article"
    spaced = news_article_target(42, gid,
        "https://steamstore-a.akamaihd.net/news/externalpost/PC Gamer/123456789")
    assert spaced is not None and spaced.browser_url.endswith("/PC%20Gamer/123456789")
    assert news_article_target(42, gid, spaced.browser_url) == spaced
    for bad in (
        "http://store.steampowered.com/news/app/42/view/987654321",
        "https://store.steampowered.com.evil.example/news/app/42/view/987654321",
        "https://store.steampowered.com:443/news/app/42/view/987654321",
        "https://store.steampowered.com@evil.example/news/app/42/view/987654321",
        "https://store.steampowered.com/news/app/99/view/987654321",
        "https://store.steampowered.com/news/app/42/view/987654321?redirect=https://evil.example",
        "https://store.steampowered.com/news/app/42/view/987654321#fragment",
        "https://store.steampowered.com/news/app/42/view/987654321/../other",
        "https://steamcommunity.com/games/Some_Game/announcements/detail/%31",
        "https://steamcommunity.com/app/99/announcements/detail/876543210",
        "https://steamcommunity.com/groups/other/announcements/detail/876543210",
        "https://steamcommunity.com/games/not/a/real/announcements/detail/876543210",
        "https://store.steampowered.com/news/externalpost/other/876543210",
        "https://steamstore-a.akamaihd.net/news/externalpost/PCGamesN/876543210",
        "https://steamstore-a.akamaihd.net/news/externalpost/PCGamesN/123456789?url=https://evil.example",
        "https://steamstore-a.akamaihd.net.evil.example/news/externalpost/PCGamesN/123456789",
        "https://steamstore-a.akamaihd.net/news/externalpost/PCGamesN%2Fattack/123456789",
        "https://steamstore-a.akamaihd.net/news/externalpost/PCGamesN/123456789/../another",
        "https://steamstore-a.akamaihd.net/news/externalpost/PCGamesN/123456789#fragment",
        "https://[malformed-host]/news/app/42/view/987654321",
    ):
        assert news_article_target(42, gid, bad) is None, bad
    for bad_gid in ("../123", "", "0?x", "１２３", 123, "1" * 33):
        assert news_article_target(42, bad_gid, store) is None
    assert news_article_target(42, gid, "") is None
    hub = news_hub_target(42)
    assert hub is not None and hub.browser_url == "https://store.steampowered.com/news/app/42/"
    assert hub.kind == "news_hub"
    assert all(news_hub_target(bad) is None for bad in ("42", True, 0, -1, 0x100000000))


def test_app_news_log_url_redacts_selected_follow_id():
    from core.steam.backend import build_endpoint
    from core.steam.models import SteamSourceId
    endpoint = build_endpoint(SteamSourceId.APP_NEWS, appid=987654321, count=2)
    assert endpoint.params["appid"] == 987654321
    redacted = endpoint.redacted_url()
    assert "987654321" not in redacted and "appid=" in redacted
    assert "count=2" in redacted
