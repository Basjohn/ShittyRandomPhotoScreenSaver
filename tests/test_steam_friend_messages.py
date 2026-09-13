from __future__ import annotations

from core.steam.credentials import safe_fingerprint
from core.steam.friend_messages import parse_friend_message_sessions
from core.steam.models import SteamResultStatus


def test_active_message_sessions_reduce_to_known_friend_unread_state() -> None:
    steam_a = "76561198000000001"
    steam_b = "76561198000000002"
    fp_a = safe_fingerprint(steam_a)
    fp_b = safe_fingerprint(steam_b)
    payload = {
        "response": {
            "message_sessions": [
                {
                    "accountid_friend": int(steam_a) & 0xFFFFFFFF,
                    "last_message": 200,
                    "last_view": 150,
                    "unread_message_count": 2,
                },
                {
                    "accountid_friend": int(steam_b) & 0xFFFFFFFF,
                    "last_message": 300,
                    "last_view": 250,
                    "unread_message_count": 1,
                },
                # Unknown people are never admitted into Friend Pulse.
                {
                    "accountid_friend": 999999,
                    "last_message": 400,
                    "unread_message_count": 9,
                },
                # Read sessions do not become notification rows.
                {
                    "accountid_friend": int(steam_a) & 0xFFFFFFFF,
                    "last_message": 500,
                    "unread_message_count": 0,
                },
            ]
        }
    }

    snapshot = parse_friend_message_sessions(
        payload,
        friend_steam_ids={fp_a: steam_a, fp_b: steam_b},
        accepted_at=123.0,
    )

    assert snapshot.status is SteamResultStatus.SUCCESS
    assert snapshot.source_available is True
    assert snapshot.total_unread == 3
    assert [session.identity_fingerprint for session in snapshot.sessions] == [fp_b, fp_a]
    assert [session.unread_count for session in snapshot.sessions] == [1, 2]
    assert snapshot.sessions[0].last_message_at == 300
    assert snapshot.sessions[0].last_view_at == 250


def test_active_message_sessions_fail_closed_on_bad_shape_or_fingerprint_map() -> None:
    invalid = parse_friend_message_sessions(
        {"response": {"message_sessions": {"not": "a list"}}},
        friend_steam_ids={},
    )
    assert invalid.status is SteamResultStatus.INVALID_RESPONSE
    assert invalid.source_available is False

    steam_id = "76561198000000001"
    payload = {
        "response": {
            "message_sessions": [
                {
                    "accountid_friend": int(steam_id) & 0xFFFFFFFF,
                    "unread_message_count": 5,
                }
            ]
        }
    }
    mismatched = parse_friend_message_sessions(
        payload,
        friend_steam_ids={"not-the-real-fingerprint": steam_id},
    )
    assert mismatched.status is SteamResultStatus.SUCCESS
    assert mismatched.source_available is True
    assert mismatched.sessions == ()
    assert mismatched.total_unread == 0
