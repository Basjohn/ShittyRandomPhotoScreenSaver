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

    assert [item.family_id for item in descriptors] == [
        "rss",
        "reddit",
        "weather",
        "gmail",
        "steam",
        "settings",
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
        app_root / "steam" / "cache" / "opaque-profile" / "owned_games.json": b"steam",
        app_root / "steam" / "cache" / "opaque-profile" / "art" / "header.png": b"art",
        app_root / "cache" / "settings_dialog_cache.json": b"settings-cache",
    }
    protected = {
        reddit_root / "_startup_gate.touch": b"tracked-marker",
        reddit_root / "notes.txt": b"not-a-post-cache",
        app_root / "steam" / "credentials.bin": b"encrypted-secret",
        app_root / "steam" / "credential_meta.json": b"credential-metadata",
        app_root / "settings_v2.json": b"installed-settings",
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
