from core.steam.links import friend_message_target, store_target


def test_friend_message_target_is_numeric_only_and_has_profile_fallback():
    target = friend_message_target("76561198000000001")
    assert target is not None
    assert target.steam_url == "steam://friends/message/76561198000000001"
    assert target.browser_url == (
        "https://steamcommunity.com/profiles/76561198000000001"
    )
    assert friend_message_target("7656/not-safe") is None
    assert friend_message_target("1") is None


def test_store_target_is_positive_uint32_only():
    target = store_target(620)
    assert target is not None
    assert target.steam_url == "steam://store/620"
    assert target.browser_url == "https://store.steampowered.com/app/620/"
    assert store_target(0) is None
    assert store_target("1/../../bad") is None
    assert store_target(0x100000000) is None
