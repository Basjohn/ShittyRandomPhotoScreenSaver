"""Tests for SettingsManager."""
import json
import uuid
from pathlib import Path

from core.settings import SettingsManager


def _make_manager(tmp_path: Path, *, base_name: str | None = None, app_name: str | None = None) -> SettingsManager:
    """Create a SettingsManager backed by a per-test JSON root."""

    storage_root = tmp_path / (base_name or uuid.uuid4().hex)
    storage_root.mkdir(parents=True, exist_ok=True)
    application = app_name or f"ScreensaverTest_{uuid.uuid4().hex}"
    return SettingsManager(
        organization="Test",
        application=application,
        storage_base_dir=storage_root,
    )


def test_settings_manager_initialization(qt_app, tmp_path):
    """Test SettingsManager initialization."""
    manager = _make_manager(tmp_path)
    
    assert manager is not None


def test_get_set_setting(qt_app, tmp_path):
    """Test getting and setting values."""
    manager = _make_manager(tmp_path)
    
    # Set a value
    manager.set("test.key", "test value")
    
    # Get the value
    value = manager.get("test.key")
    assert value == "test value"


def test_default_values(qt_app, tmp_path):
    """Test default values are set."""
    manager = _make_manager(tmp_path)
    
    # Check some defaults exist
    assert manager.contains("sources.mode")
    assert manager.contains("display.mode")
    assert manager.contains("transitions")


def test_widget_defaults_helper_matches_schema(qt_app, tmp_path):
    """get_widget_defaults sections should mirror the widgets schema in _set_defaults.

    This is a light invariant test to catch accidental drift between the
    canonical defaults map and the helper used by UI code.
    """
    manager = _make_manager(tmp_path)

    # Force canonical defaults to be present in the underlying QSettings.
    manager.reset_to_defaults()

    widgets_value = manager.get("widgets", {})
    assert isinstance(widgets_value, dict)

    for section in ["clock", "clock2", "clock3", "weather", "media", "spotify_visualizer", "reddit", "shadows"]:
        helper_defaults = manager.get_widget_defaults(section)
        assert isinstance(helper_defaults, dict)

        schema_section = widgets_value.get(section, {})
        assert isinstance(schema_section, dict)

        # Every key exposed by get_widget_defaults must exist in the
        # canonical widgets map (and share the same type of value).
        for key, helper_val in helper_defaults.items():
            assert key in schema_section
            schema_val = schema_section[key]
            assert type(schema_val) is type(helper_val)


def test_on_changed_handler(qt_app, tmp_path):
    """Test change notification handler."""
    manager = _make_manager(tmp_path)
    
    changed_values = []
    
    def handler(new_value, old_value):
        changed_values.append((new_value, old_value))
    
    manager.on_changed("test.key", handler)
    
    # Change the value
    manager.set("test.key", "initial")
    manager.set("test.key", "updated")
    
    assert len(changed_values) >= 1


def test_reset_to_defaults(qt_app, tmp_path):
    """Test resetting to defaults."""
    manager = _make_manager(tmp_path)
    
    # Change a value
    manager.set("sources.mode", "custom_value")
    assert manager.get("sources.mode") == "custom_value"
    
    # Reset
    manager.reset_to_defaults()
    
    # Should be back to default
    assert manager.get("sources.mode") == "folders"


def test_get_all_keys(qt_app, tmp_path):
    """Test getting all keys."""
    manager = _make_manager(tmp_path)
    
    keys = manager.get_all_keys()
    
    assert isinstance(keys, list)
    assert len(keys) > 0
    assert "sources.mode" in keys


def test_sst_round_trip_defaults(qt_app, tmp_path):
    """Exporting and re-importing defaults should restore canonical values."""
    base_name = "sst_round_trip"
    manager = _make_manager(tmp_path, base_name=base_name, app_name="SSTDefaults")

    # Start from a clean canonical state and export it.
    manager.reset_to_defaults()
    snapshot_path = tmp_path / "settings_defaults.sst"
    assert manager.export_to_sst(str(snapshot_path))
    assert snapshot_path.exists()

    # Mutate some values away from defaults.
    manager.set("sources.mode", "rss")
    manager.set("display.hw_accel", False)

    widgets = manager.get("widgets", {})
    assert isinstance(widgets, dict)
    spotify_cfg = dict(widgets.get("spotify_visualizer", {}))
    assert spotify_cfg  # should exist in defaults
    spotify_cfg["ghost_alpha"] = 0.1
    widgets["spotify_visualizer"] = spotify_cfg
    manager.set("widgets", widgets)

    assert manager.get("sources.mode") == "rss"
    assert manager.get_bool("display.hw_accel") is False
    widgets_mut = manager.get("widgets", {})
    assert widgets_mut["spotify_visualizer"]["ghost_alpha"] == 0.1

    # Import the exported snapshot and verify defaults are restored.
    assert manager.import_from_sst(str(snapshot_path), merge=True)

    assert manager.get("sources.mode") == "folders"
    assert manager.get_bool("display.hw_accel") is True
    widgets_after = manager.get("widgets", {})
    assert isinstance(widgets_after, dict)
    assert widgets_after["spotify_visualizer"]["ghost_alpha"] == 0.4


def test_sst_merge_and_type_coercion_and_preview(qt_app, tmp_path):
    """SST import should merge sections, coerce basic types, and be previewable."""

    base_name = "sst_merge"
    manager = _make_manager(tmp_path, base_name=base_name, app_name="SSTMerge")
    manager.reset_to_defaults()

    # Add an extra widget entry that should survive a merge-based import.
    widgets = manager.get("widgets", {})
    assert isinstance(widgets, dict)
    widgets["custom_widget"] = {"enabled": True, "monitor": 1}
    manager.set("widgets", widgets)

    # Export current state to SST.
    snapshot_path = tmp_path / "settings_merge.sst"
    assert manager.export_to_sst(str(snapshot_path))
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))

    # Simulate an older snapshot that:
    # - Does not know about custom_widget
    # - Stores some values as strings to exercise type coercion.
    snapshot = data.get("snapshot", {})
    widgets_snap = snapshot.get("widgets", {})
    if "custom_widget" in widgets_snap:
        del widgets_snap["custom_widget"]

    display_section = snapshot.setdefault("display", {})
    display_section["hw_accel"] = "false"
    timing_section = snapshot.setdefault("timing", {})
    timing_section["interval"] = "99"

    data["snapshot"] = snapshot
    modified_path = tmp_path / "settings_merge_modified.sst"
    modified_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Preview the import and ensure we see type-changing keys.
    diffs = manager.preview_import_from_sst(str(modified_path), merge=True)
    assert "display.hw_accel" in diffs
    assert "timing.interval" in diffs

    # Apply the import.
    assert manager.import_from_sst(str(modified_path), merge=True)

    # custom_widget must still be present because merge=True preserves
    # entries that are not present in the snapshot.
    merged_widgets = manager.get("widgets", {})
    assert "custom_widget" in merged_widgets

    # Coercion: bool and int come back with correct types/values.
    assert manager.get_bool("display.hw_accel") is False
    interval_val = manager.get("timing.interval")
    assert isinstance(interval_val, int)
    assert interval_val == 99
