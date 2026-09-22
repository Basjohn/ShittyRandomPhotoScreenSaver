from pathlib import Path

import pytest

from core.cache_maintenance import clear_cache_families, get_cache_family_descriptors


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_cache_family_inventory_excludes_credentials_and_settings(tmp_path: Path) -> None:
    app_root = tmp_path / "SRPSS"
    reddit_root = tmp_path / "repo" / "cache" / "reddit"

    descriptors = get_cache_family_descriptors(
        app_data_dir=app_root,
        reddit_cache_dir=reddit_root,
    )

    # "settings" is no longer a cache family (settings is not clearable cache).
    assert [item.family_id for item in descriptors] == [
        "rss",
        "reddit",
        "feeds",
        "weather",
        "gmail",
        "steam",
    ]
    target_paths = {
        target.path
        for descriptor in descriptors
        for target in descriptor.targets
    }
    assert app_root / "steam" / "cache" in target_paths
    assert app_root / "steam" / "credentials.bin" not in target_paths
    assert app_root / "settings_v2.json" not in target_paths


def test_clear_cache_families_removes_only_allowlisted_files(tmp_path: Path) -> None:
    app_root = tmp_path / "SRPSS"
    reddit_root = tmp_path / "repo" / "cache" / "reddit"
    descriptors = get_cache_family_descriptors(
        app_data_dir=app_root,
        reddit_cache_dir=reddit_root,
    )

    removable = {
        app_root / "cache" / "rss" / "image.jpg": b"rss",
        reddit_root / "reddit_posts.json": b"reddit",
        app_root / "cache" / "weather.json": b"weather-provider",
        app_root / "cache" / "weather_widget_last.json": b"weather-widget",
        app_root / "cache" / "gmail_cache.json": b"gmail",
        app_root / "cache" / "feeds" / "feeds_custom_1_deadbeef.json": b"feed-last-good",
        app_root / "steam" / "cache" / "opaque-profile" / "owned_games.json": b"steam",
        app_root / "steam" / "cache" / "opaque-profile" / "art" / "header.png": b"art",
        app_root / "steam" / "cache" / "opaque-profile" / "games_you_follow_news.json": b"followed-last-good",
        app_root / "steam" / "cache" / "opaque-profile" / "games_followed_app_metadata.json": b"canonical-app-names",
        app_root / "steam" / "cache" / "opaque-profile" / "assets" / "news_inline" / "thumb.png": b"inline-art",
    }
    protected = {
        reddit_root / "_startup_gate.touch": b"tracked-marker",
        reddit_root / "notes.txt": b"not-a-post-cache",
        app_root / "steam" / "credentials.bin": b"encrypted-secret",
        app_root / "steam" / "credential_meta.json": b"credential-metadata",
        app_root / "steam" / "cache" / "opaque-profile" / "friend_pulse_pins.json": b"user-pinned-friends",
        app_root / "steam" / "cache" / "opaque-profile" / "friend_pulse_pins.json.tmp": b"pending-user-state",
        app_root / "settings_v2.json": b"installed-settings",
        # The retired "settings" cache family no longer targets this file.
        app_root / "cache" / "settings_dialog_cache.json": b"settings-cache",
    }
    for path, payload in {**removable, **protected}.items():
        _write(path, payload)

    result = clear_cache_families(
        (item.family_id for item in descriptors),
        descriptors=descriptors,
    )

    assert result.complete is True
    assert result.removed_files == len(removable)
    assert result.removed_bytes == sum(len(payload) for payload in removable.values())
    assert all(not path.exists() for path in removable)
    assert all(path.read_bytes() == payload for path, payload in protected.items())
    assert (app_root / "steam" / "cache").is_dir()


def test_clear_cache_families_rejects_unknown_scope(tmp_path: Path) -> None:
    descriptors = get_cache_family_descriptors(app_data_dir=tmp_path / "SRPSS")

    with pytest.raises(ValueError, match="Unknown cache family"):
        clear_cache_families(("credentials",), descriptors=descriptors)


def test_cache_targets_track_the_real_writer_contracts(tmp_path: Path) -> None:
    """Keep Settings' targets aligned with the named persistent cache writers."""
    root = tmp_path / "SRPSS"
    reddit = tmp_path / "repo" / "cache" / "reddit"
    families = {entry.family_id: entry for entry in get_cache_family_descriptors(
        app_data_dir=root, reddit_cache_dir=reddit)}
    assert families["rss"].targets[0].path == root / "cache" / "rss"
    assert not families["rss"].targets[0].recursive  # RSS images are direct children.
    assert families["reddit"].targets[0].path == reddit
    assert families["reddit"].targets[0].pattern == "*_posts.json"
    assert families["feeds"].targets[0].path == root / "cache" / "feeds"
    assert families["feeds"].targets[0].recursive
    assert {t.path for t in families["weather"].targets} == {
        root / "cache" / "weather.json", root / "cache" / "weather_widget_last.json"}
    assert families["gmail"].targets[0].path == root / "cache" / "gmail_cache.json"
    assert families["steam"].targets[0].path == root / "steam" / "cache"
    assert families["steam"].targets[0].recursive
    assert {"friend_pulse_pins.json", "friend_pulse_pins.json.tmp"} <= families["steam"].protected_names


def test_steam_clear_does_not_delete_pinned_friends_even_if_only_cache_state_is_present(tmp_path: Path) -> None:
    app_root = tmp_path / "SRPSS"
    profile = app_root / "steam" / "cache" / "profile_example"
    pinned = profile / "friend_pulse_pins.json"
    news = profile / "games_you_follow_news.json"
    _write(pinned, b"private-user-state")
    _write(news, b"cached-news")
    descriptors = get_cache_family_descriptors(app_data_dir=app_root)
    first = clear_cache_families(("steam",), descriptors=descriptors)
    assert first.complete and first.removed_files == 1
    assert not news.exists() and pinned.read_bytes() == b"private-user-state"
    second = clear_cache_families(("steam",), descriptors=descriptors)
    assert second.complete and second.removed_files == 0
    assert pinned.read_bytes() == b"private-user-state"
