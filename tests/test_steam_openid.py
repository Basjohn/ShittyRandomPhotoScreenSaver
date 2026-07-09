from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from core.steam.openid import (
    STEAM_OPENID_ENDPOINT,
    STEAM_OPENID_IDENTIFIER_SELECT,
    SteamOpenIdLinkSession,
    build_login_url,
    extract_steam_id64,
    validate_assertion,
)


# SteamID64's account-id-zero base value is a structural sentinel, not a user.
STEAM_ID64 = "76561197960265728"
RETURN_TO = "http://127.0.0.1:48123/steam/openid?state=fake_state"


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, _limit: int) -> bytes:
        return self._payload


def _assertion_params(**overrides: str) -> dict[str, str]:
    claimed_id = f"https://steamcommunity.com/openid/id/{STEAM_ID64}"
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "id_res",
        "openid.op_endpoint": STEAM_OPENID_ENDPOINT,
        "openid.claimed_id": claimed_id,
        "openid.identity": claimed_id,
        "openid.return_to": RETURN_TO,
        "openid.response_nonce": "2026-07-09T10:00:00Zexample",
        "openid.signed": "op_endpoint,claimed_id,identity,return_to,response_nonce",
        "openid.sig": "fake_signature",
    }
    params.update(overrides)
    return params


def test_build_login_url_uses_steam_openid_and_fixed_local_callback() -> None:
    login_url = build_login_url(RETURN_TO)
    parsed = urlparse(login_url)
    query = parse_qs(parsed.query)

    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == STEAM_OPENID_ENDPOINT
    assert query["openid.mode"] == ["checkid_setup"]
    assert query["openid.return_to"] == [RETURN_TO]
    assert query["openid.claimed_id"] == [STEAM_OPENID_IDENTIFIER_SELECT]
    assert query["openid.identity"] == [STEAM_OPENID_IDENTIFIER_SELECT]


def test_extract_steam_id64_accepts_only_documented_claimed_id_shape() -> None:
    assert extract_steam_id64(f"https://steamcommunity.com/openid/id/{STEAM_ID64}") == STEAM_ID64
    assert extract_steam_id64(f"http://steamcommunity.com/openid/id/{STEAM_ID64}/") == STEAM_ID64
    assert extract_steam_id64("https://evil.example/openid/id/76561197960265728") is None
    assert extract_steam_id64("https://steamcommunity.com/openid/id/not-a-steamid") is None


def test_validate_assertion_posts_check_authentication_before_accepting_identity() -> None:
    opened: list[tuple[str, bytes]] = []

    def _opener(request, _timeout: float):
        opened.append((request.full_url, request.data))
        return _Response(b"ns:http://specs.openid.net/auth/2.0\nis_valid:true\n")

    result = validate_assertion(_assertion_params(), expected_return_to=RETURN_TO, opener=_opener)

    assert result.success is True
    assert result.steam_id64 == STEAM_ID64
    assert opened[0][0] == STEAM_OPENID_ENDPOINT
    posted = parse_qs(opened[0][1].decode("utf-8"))
    assert posted["openid.mode"] == ["check_authentication"]
    assert posted["openid.claimed_id"] == [f"https://steamcommunity.com/openid/id/{STEAM_ID64}"]


def test_validate_assertion_rejects_mismatched_callback_without_posting_to_steam() -> None:
    called = False

    def _opener(_request, _timeout: float):
        nonlocal called
        called = True
        return _Response(b"is_valid:true\n")

    result = validate_assertion(
        _assertion_params(**{"openid.return_to": "http://127.0.0.1:9999/steam/openid?state=wrong"}),
        expected_return_to=RETURN_TO,
        opener=_opener,
    )

    assert result.success is False
    assert "match" in result.message.lower()
    assert called is False


def test_openid_link_session_uses_an_unpredictable_loopback_callback() -> None:
    session = SteamOpenIdLinkSession()
    try:
        login_url = session.start()
        assert session.callback_url is not None
        assert "state=" in session.callback_url
        assert session.callback_url.startswith("http://127.0.0.1:")
        assert parse_qs(urlparse(login_url).query)["openid.return_to"] == [session.callback_url]
    finally:
        session.close()
