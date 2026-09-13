from __future__ import annotations

import json

from core.steam.friend_pulse_pins import (
    PIN_FILE_NAME,
    load_friend_pulse_pins,
    save_friend_pulse_pins,
)


def test_friend_pulse_pins_round_trip_opaque_account_private_state(tmp_path) -> None:
    profile_key = "profile_0123456789abcdef"
    pins = {"friend_aaa", "friend_bbb", "friend_ccc"}

    path = save_friend_pulse_pins(profile_key, pins, root=tmp_path)

    assert path == tmp_path / PIN_FILE_NAME
    assert load_friend_pulse_pins(profile_key, root=tmp_path) == frozenset(pins)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["pinned_fingerprints"] == sorted(pins)
    assert "steamid" not in path.read_text(encoding="utf-8").lower()


def test_friend_pulse_pins_reject_nonopaque_profile_key_and_corrupt_file(tmp_path) -> None:
    try:
        save_friend_pulse_pins("76561198000000001", {"friend"}, root=tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("raw Steam identity must not be accepted as pin namespace")

    profile_key = "profile_deadbeef"
    path = tmp_path / PIN_FILE_NAME
    path.write_text("not json", encoding="utf-8")
    assert load_friend_pulse_pins(profile_key, root=tmp_path) == frozenset()


def test_pinned_friends_sort_ahead_without_losing_online_order() -> None:
    from core.steam.friend_pulse import (
        FriendPulseEntry,
        FriendPulseSnapshot,
        project_friend_pulse,
    )
    from core.steam.models import SteamResultStatus

    entries = (
        FriendPulseEntry("a", display_name="Alpha", persona_state=1),
        FriendPulseEntry("b", display_name="Beta", persona_state=0),
        FriendPulseEntry("c", display_name="Gamma", persona_state=1),
    )
    snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        entries=entries,
        online_count=2,
    )
    projection = project_friend_pulse(
        snapshot,
        privacy_mode="Rich",
        capacity=8,
        friend_action_identities={"a", "b", "c"},
        pinned_identities={"b", "c"},
    )

    assert [row.identity_fingerprint for row in projection.rows] == ["c", "b", "a"]
    assert [row.pinned for row in projection.rows] == [True, True, False]


def test_friend_pulse_pins_have_no_artificial_product_count_cap(tmp_path) -> None:
    profile_key = "profile_many"
    pins = {f"friend_{index:04d}" for index in range(750)}

    save_friend_pulse_pins(profile_key, pins, root=tmp_path)

    assert load_friend_pulse_pins(profile_key, root=tmp_path) == frozenset(pins)
