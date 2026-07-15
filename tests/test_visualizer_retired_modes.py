"""Absence and forward-migration contract for retired visualizer modes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_default_visualizer_mode_id,
)
from core.settings.visualizer_settings_snapshot import (
    normalize_visualizer_section_mapping,
)
from core.visualizer_preset_manifest import (
    load_curated_visualizer_preset_manifest,
    mirror_curated_visualizer_preset_tree,
    scan_curated_visualizer_preset_tree,
)


def _keys_containing_blob(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if "blob" in str(key).casefold():
                found.append(child_path)
            found.extend(_keys_containing_blob(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_keys_containing_blob(child, f"{path}[{index}]"))
    return found


def test_registry_has_no_blob_mode():
    assert "blob" not in VISUALIZER_MODE_IDS


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "blob", "blob_type": "shaped"},
        {"widgets.spotify_visualizer.mode": "blob", "widgets.spotify_visualizer.blob_type": "normal"},
    ],
    ids=["plain", "dotted"],
)
def test_blob_settings_migrate_to_registry_default_without_retired_keys(payload):
    normalized = normalize_visualizer_section_mapping(payload)

    assert normalized["mode"] == get_default_visualizer_mode_id()
    assert normalized["mode"] in VISUALIZER_MODE_IDS
    assert not _keys_containing_blob(normalized)


def test_saved_blob_schema_migration_preserves_sibling_widget_data(tmp_path):
    application = "RetiredBlobMigration"
    manager = SettingsManager(
        organization="Test",
        application=application,
        storage_base_dir=tmp_path,
    )
    manager._settings.setValue(
        "widgets",
        {
            "spotify_visualizer": {
                "mode": "blob",
                "blob_shaper_enabled": True,
                "blob_shape_base_nodes": [[0.0, 0.8]],
            },
            "clock": {"enabled": False, "font": "Consolas"},
        },
    )
    manager._settings.update_metadata(visualizer_schema_version=0)
    manager._settings.sync()

    reloaded = SettingsManager(
        organization="Test",
        application=application,
        storage_base_dir=tmp_path,
    )
    widgets = reloaded.get("widgets")

    assert widgets["spotify_visualizer"]["mode"] == get_default_visualizer_mode_id()
    assert widgets["clock"]["enabled"] is False
    assert widgets["clock"]["font"] == "Consolas"
    assert not _keys_containing_blob(widgets)


def test_retired_keys_never_reemit_from_normalized_section():
    normalized = normalize_visualizer_section_mapping(
        {
            "mode": "blob",
            "blob_type": "shaped",
            "blob_shaper_enabled": True,
            "blob_shape_base_nodes": [[0.0, 0.8]],
        }
    )

    assert not _keys_containing_blob(normalized)
    assert "blob" not in repr(normalized).casefold()


def test_canonical_defaults_have_no_blob_leaves():
    defaults = get_default_settings()

    assert not _keys_containing_blob(defaults)
    assert "blob" not in repr(defaults).casefold()


def test_retired_preset_tree_is_not_mirrored_and_stale_target_is_pruned(tmp_path: Path):
    source_root = tmp_path / "source" / "visualizer_modes"
    target_root = tmp_path / "target" / "visualizer_modes"
    (source_root / "spectrum").mkdir(parents=True)
    (source_root / "blob").mkdir(parents=True)
    (target_root / "blob").mkdir(parents=True)

    supported = source_root / "spectrum" / "preset_1_organs.json"
    retired_source = source_root / "blob" / "preset_1_retired.json"
    retired_target = target_root / "blob" / "preset_1_retired.json"
    supported.write_text("{}", encoding="utf-8")
    retired_source.write_text("{}", encoding="utf-8")
    retired_target.write_text("{}", encoding="utf-8")

    assert scan_curated_visualizer_preset_tree(source_root) == {
        "spectrum/preset_1_organs.json"
    }

    mirrored = mirror_curated_visualizer_preset_tree(source_root, target_root)

    assert mirrored == {"spectrum/preset_1_organs.json"}
    assert (target_root / "spectrum" / "preset_1_organs.json").is_file()
    assert not retired_target.exists()
    assert load_curated_visualizer_preset_manifest(target_root) == mirrored
