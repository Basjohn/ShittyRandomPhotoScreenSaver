from __future__ import annotations

import json
import urllib.error
from io import BytesIO

import pytest

from core.steam.backend import (
    SOURCE_EVIDENCE,
    SteamEndpoint,
    build_endpoint,
    classify_http_status,
    fetch_json,
    redact_params,
    require_client_source,
)
from core.steam.models import SteamResultStatus, SteamSourceId, SteamSourceStatus


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self._stream = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def test_source_evidence_keeps_publisher_only_endpoints_excluded() -> None:
    assert SOURCE_EVIDENCE[SteamSourceId.NEWS_AUTHED].publisher_only is True
    assert SOURCE_EVIDENCE[SteamSourceId.NEWS_AUTHED].status == SteamSourceStatus.EXCLUDED
    assert SOURCE_EVIDENCE[SteamSourceId.CHECK_APP_OWNERSHIP].publisher_only is True

    with pytest.raises(ValueError):
        require_client_source(SteamSourceId.NEWS_AUTHED)
    with pytest.raises(ValueError):
        require_client_source(SteamSourceId.CHECK_APP_OWNERSHIP)


def test_build_endpoint_redacts_user_key_and_profile_id() -> None:
    endpoint = build_endpoint(
        SteamSourceId.RECENTLY_PLAYED,
        api_key="STEAM_KEY_SHOULD_NOT_LEAK_1234567890",
        steamid="76561198000000000",
        count=5,
    )

    redacted_url = endpoint.redacted_url()
    assert "STEAM_KEY_SHOULD_NOT_LEAK" not in redacted_url
    assert "76561198000000000" not in redacted_url
    assert "count=5" in redacted_url
    assert endpoint.redacted_params()["key"].startswith("<key:")
    assert endpoint.redacted_params()["steamid"].startswith("<steamid:")


def test_public_app_news_endpoint_does_not_require_user_key() -> None:
    endpoint = build_endpoint(SteamSourceId.APP_NEWS, appid=730, count=3)

    assert endpoint.requires_user_key is False
    assert "key" not in endpoint.params
    assert "steamid" not in endpoint.params
    assert "ISteamNews/GetNewsForApp" in endpoint.url


def test_http_status_classification_keeps_private_distinct_from_offline() -> None:
    assert classify_http_status(200) == SteamResultStatus.SUCCESS
    assert classify_http_status(401) == SteamResultStatus.PRIVATE
    assert classify_http_status(403) == SteamResultStatus.UNAUTHORIZED
    assert classify_http_status(429) == SteamResultStatus.RATE_LIMITED
    assert classify_http_status(500) == SteamResultStatus.NETWORK_ERROR


def test_fetch_json_uses_injected_opener_and_returns_mapping_payload() -> None:
    endpoint = build_endpoint(SteamSourceId.APP_NEWS, appid=730)
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _FakeResponse({"appnews": {"appid": 730, "newsitems": []}})

    result = fetch_json(endpoint, opener=opener)

    assert result.status == SteamResultStatus.SUCCESS
    assert result.payload == {"appnews": {"appid": 730, "newsitems": []}}
    assert result.attempted_sources == (SteamSourceId.APP_NEWS,)
    assert "appid=730" in captured["url"]


def test_fetch_json_classifies_http_error_without_throwing() -> None:
    endpoint = build_endpoint(
        SteamSourceId.FRIEND_LIST,
        api_key="STEAM_KEY_SHOULD_NOT_LEAK_1234567890",
        steamid="76561198000000000",
    )

    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "private", {}, None)

    result = fetch_json(endpoint, opener=opener)

    assert result.status == SteamResultStatus.PRIVATE
    assert result.http_status == 401
    assert result.source_id == SteamSourceId.FRIEND_LIST


def test_fetch_json_refuses_publisher_only_endpoint() -> None:
    endpoint = SteamEndpoint(
        source_id=SteamSourceId.NEWS_AUTHED,
        url="https://partner.steam-api.com/ISteamNews/GetNewsForAppAuthed/v2/",
        params={"key": "publisher-key", "appid": 1},
        requires_user_key=False,
        publisher_only=True,
    )

    result = fetch_json(endpoint, opener=lambda request, timeout: _FakeResponse({}))

    assert result.status == SteamResultStatus.PUBLISHER_ONLY
    assert result.payload is None


def test_redact_params_only_hides_secret_like_identity_fields() -> None:
    redacted = redact_params(
        {
            "key": "abc",
            "steamids": "7656119",
            "appid": 730,
            "relationship": "friend",
        }
    )

    assert redacted["key"].startswith("<key:")
    assert redacted["steamids"].startswith("<steamids:")
    assert redacted["appid"] == 730
    assert redacted["relationship"] == "friend"
