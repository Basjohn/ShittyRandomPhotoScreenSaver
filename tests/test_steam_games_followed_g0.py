"""G0-only Steam followed-games probe. No live Steam request is made by tests."""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO

import pytest

from core.steam.backend import build_endpoint
from core.steam.games_followed_probe import normalize_followed_appids, probe_followed_games
from core.steam.models import SteamSourceId
from tools.steam_followed_g0_probe import main

_ID = "76561197960265728"  # Public, fake/fixture SteamID64, never an account credential.


class _Response:
    status = 200

    def __init__(self, body):
        self.data = BytesIO(json.dumps(body).encode("utf-8"))

    def read(self, n=-1):
        return self.data.read(n)


def test_followed_endpoint_is_narrow_read_only_and_redacts_identity():
    endpoint = build_endpoint(SteamSourceId.GAMES_FOLLOWED, steamid=_ID)
    assert endpoint.url == "https://api.steampowered.com/IStoreService/GetGamesFollowed/v1/"
    assert endpoint.params == {"steamid": _ID}
    assert endpoint.requires_user_key is False
    assert "key" not in endpoint.params
    assert _ID not in endpoint.redacted_url()
    for invalid in (None, "", "abc", "7656119", "7656119796026572x"):
        with pytest.raises(ValueError):
            build_endpoint(SteamSourceId.GAMES_FOLLOWED, steamid=invalid)


def test_followed_probe_is_single_bounded_call_without_leaking_identity():
    requests = []

    def opener(request, timeout):
        requests.append((request.full_url, timeout, request.get_method()))
        return _Response({"response": {"appids": [10, 11, 12]}})

    outcome = probe_followed_games(_ID, opener=opener)
    assert (outcome.status, outcome.count) == ("confirmed_nonempty", 3)
    assert len(requests) == 1 and requests[0][2] == "GET"
    assert requests[0][0].startswith("https://api.steampowered.com/IStoreService/")
    assert requests[0][1] <= 12.0
    assert not hasattr(outcome, "appids")


def test_followed_probe_distinguishes_true_empty_from_failure_and_invalid_data():
    assert probe_followed_games(_ID, opener=lambda *_: _Response({"response": {"appids": []}})).status == "confirmed_empty"
    assert probe_followed_games(_ID, opener=lambda *_: _Response({"response": {}})).status == "invalid_response"
    assert probe_followed_games(_ID, opener=lambda *_: _Response({"response": {"appids": ""}})).status == "invalid_response"
    for code, status in ((401, "private"), (403, "unauthorized"), (429, "rate_limited")):
        def denied(request, _timeout):
            raise urllib.error.HTTPError(request.full_url, code, "denied", {}, None)
        outcome = probe_followed_games(_ID, opener=denied)
        assert (outcome.status, outcome.count) == (status, None)


def test_followed_payload_rejects_malformed_or_unbounded_app_lists():
    assert normalize_followed_appids({"response": {"appids": [1, 2]}}) == (1, 2)
    for appids in ([1, 1], [True], [-1], [0], [2**32], [1.5], ["2"], list(range(1, 4098))):
        assert normalize_followed_appids({"response": {"appids": appids}}) is None


def test_cli_requires_explicit_probe_and_prints_no_account_identity(monkeypatch, capsys):
    from core.steam import credentials
    from core.steam import games_followed_probe
    monkeypatch.setattr(credentials, "load_credentials", lambda: type("Credential", (), {"profile_identifier": _ID})())
    monkeypatch.setattr(games_followed_probe, "probe_followed_games", lambda steamid: (
        probe_followed_games(steamid, opener=lambda *_: _Response({"response": {"appids": [123]}}))
    ))
    assert main(["--probe"]) == 0
    printed = capsys.readouterr().out
    assert "confirmed_nonempty" in printed and "count=1" in printed
    assert _ID not in printed and "123" not in printed
