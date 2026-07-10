from __future__ import annotations

from copy import deepcopy
import json

from PySide6.QtWidgets import QFontComboBox

from core.settings.defaults import (
    MC_PROFILE,
    NORMAL_PROFILE,
    get_base_default_settings,
    get_default_settings,
)
from tools.default_settings_editor import (
    DEFAULT_SETTINGS_PATH,
    DefaultSettingsEditor,
    build_profile_models,
    build_profile_overrides,
    editable_base_settings,
    iter_leaf_settings,
    load_default_settings_source,
    load_importable_settings_snapshot,
    load_profile_overrides,
    merge_imported_profile,
    read_undo_record,
    read_undo_sources,
    render_default_settings_module,
    render_profile_overrides_module,
    set_path,
    setting_tooltip,
    write_undo_record,
)
from ui.styled_popup import ColorSwatchButton


def _copy_base_source(tmp_path):
    path = tmp_path / "default_settings.py"
    path.write_text(DEFAULT_SETTINGS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_profile_defaults_resolve_normal_and_mc_without_mutating_base() -> None:
    base = get_base_default_settings()
    base_before = deepcopy(base)
    normal = get_default_settings(NORMAL_PROFILE)
    mc = get_default_settings(MC_PROFILE)

    assert base == base_before
    assert normal["display"]["show_on_monitors"] == "ALL"
    assert normal["input"]["interaction_mode"] is False
    assert mc["display"]["show_on_monitors"] == [1]
    assert mc["input"]["interaction_mode"] is True
    assert mc["widgets"]["gmail"]["monitor"] == "2"
    assert mc["widgets"]["media"]["monitor"] == "2"


def test_editor_model_discovers_new_settings_and_compacts_profile_differences(tmp_path) -> None:
    base = {"display": {"mode": "fill"}, "widgets": {"new_card": {"enabled": False, "levels": [1, 2]}}}
    overrides = {
        NORMAL_PROFILE: {"widgets": {"new_card": {"enabled": True}}},
        MC_PROFILE: {"display": {"mode": "fit"}},
    }
    models = build_profile_models(base, overrides)
    paths = {path for path, _value in iter_leaf_settings(models[NORMAL_PROFILE])}

    assert ("widgets", "new_card", "levels") in paths
    assert models[NORMAL_PROFILE]["widgets"]["new_card"]["enabled"] is True
    assert models[MC_PROFILE]["display"]["mode"] == "fit"
    assert build_profile_overrides(base, models) == {
        NORMAL_PROFILE: {},
        MC_PROFILE: {"display": {"mode": "fit"}},
    }

    path = tmp_path / "default_profile_overrides.py"
    path.write_text(render_profile_overrides_module(overrides), encoding="utf-8")
    assert load_profile_overrides(path) == overrides
    assert "Controls whether" in setting_tooltip(
        ("widgets", "new_card", "enabled"),
        True,
        NORMAL_PROFILE,
    )


def test_editor_transactional_save_and_single_level_undo(qt_app, tmp_path) -> None:
    base_path = _copy_base_source(tmp_path)
    original_base_source = base_path.read_text(encoding="utf-8")
    overrides = {NORMAL_PROFILE: {}, MC_PROFILE: {}}
    overrides_path = tmp_path / "default_profile_overrides.py"
    undo_path = tmp_path / "undo.json"
    original_source = render_profile_overrides_module(overrides)
    overrides_path.write_text(original_source, encoding="utf-8")
    regenerations: list[bool] = []
    editor = DefaultSettingsEditor(
        base_path=base_path,
        overrides_path=overrides_path,
        undo_path=undo_path,
        regenerate=lambda: regenerations.append(True) or "Regenerated test artifacts",
    )
    try:
        leaves, tooltips = editor.smoke_check()
        assert leaves >= 700
        assert tooltips == leaves

        path = ("widgets", "achievement_pulse", "square_artwork_size")
        set_path(editor._models[NORMAL_PROFILE], path, 155)
        set_path(editor._models[MC_PROFILE], path, 155)
        editor._save_and_regenerate()

        saved = load_profile_overrides(overrides_path)
        canonical = editable_base_settings(load_default_settings_source(base_path))
        assert canonical["widgets"]["achievement_pulse"]["square_artwork_size"] == 155
        assert saved[NORMAL_PROFILE] == {}
        assert saved[MC_PROFILE] == {}
        assert read_undo_record(undo_path) == original_source
        assert read_undo_sources(undo_path) == (original_base_source, original_source)

        editor._undo_and_regenerate()

        assert base_path.read_text(encoding="utf-8") == original_base_source
        assert overrides_path.read_text(encoding="utf-8") == original_source
        assert not undo_path.exists()
        assert len(regenerations) == 2
    finally:
        editor.close()


def test_failed_save_restores_previous_undo_source_and_artifacts(qt_app, tmp_path, monkeypatch) -> None:
    base_path = _copy_base_source(tmp_path)
    base_source_before = base_path.read_text(encoding="utf-8")
    overrides_path = tmp_path / "default_profile_overrides.py"
    undo_path = tmp_path / "undo.json"
    source_before = render_profile_overrides_module({NORMAL_PROFILE: {}, MC_PROFILE: {}})
    previous_source = render_profile_overrides_module(
        {NORMAL_PROFILE: {"timing": {"update_interval": 321}}, MC_PROFILE: {}}
    )
    overrides_path.write_text(source_before, encoding="utf-8")
    write_undo_record(previous_source, undo_path)
    calls: list[int] = []

    def _regenerate() -> str:
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            raise RuntimeError("injected generation failure")
        return "Rolled back test artifacts"

    monkeypatch.setattr("tools.default_settings_editor.QMessageBox.critical", lambda *_args: None)
    editor = DefaultSettingsEditor(
        base_path=base_path,
        overrides_path=overrides_path,
        undo_path=undo_path,
        regenerate=_regenerate,
    )
    try:
        path = ("widgets", "achievement_pulse", "square_artwork_size")
        set_path(editor._models[NORMAL_PROFILE], path, 155)
        set_path(editor._models[MC_PROFILE], path, 155)
        editor._save_and_regenerate()

        assert base_path.read_text(encoding="utf-8") == base_source_before
        assert overrides_path.read_text(encoding="utf-8") == source_before
        assert read_undo_record(undo_path) == previous_source
        assert calls == [1, 2]
    finally:
        editor.close()


def test_failed_undo_restores_current_source_and_artifacts(qt_app, tmp_path, monkeypatch) -> None:
    base_path = _copy_base_source(tmp_path)
    original_base_source = base_path.read_text(encoding="utf-8")
    current_base_settings = load_default_settings_source(base_path)
    current_base_settings["timing"]["interval"] = 77
    current_base_source = render_default_settings_module(current_base_settings)
    base_path.write_text(current_base_source, encoding="utf-8")
    overrides_path = tmp_path / "default_profile_overrides.py"
    undo_path = tmp_path / "undo.json"
    original_source = render_profile_overrides_module({NORMAL_PROFILE: {}, MC_PROFILE: {}})
    current_source = render_profile_overrides_module(
        {NORMAL_PROFILE: {"timing": {"update_interval": 321}}, MC_PROFILE: {}}
    )
    overrides_path.write_text(current_source, encoding="utf-8")
    write_undo_record(
        original_source,
        undo_path,
        base_source_text=original_base_source,
    )
    calls: list[int] = []

    def _regenerate() -> str:
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            raise RuntimeError("injected undo generation failure")
        return "Restored current test artifacts"

    monkeypatch.setattr("tools.default_settings_editor.QMessageBox.critical", lambda *_args: None)
    editor = DefaultSettingsEditor(
        base_path=base_path,
        overrides_path=overrides_path,
        undo_path=undo_path,
        regenerate=_regenerate,
    )
    try:
        editor._undo_and_regenerate()

        assert base_path.read_text(encoding="utf-8") == current_base_source
        assert overrides_path.read_text(encoding="utf-8") == current_source
        assert read_undo_record(undo_path) == original_source
        assert calls == [1, 2]
    finally:
        editor.close()


def test_snapshot_import_strips_secrets_and_profile_specific_values(tmp_path) -> None:
    snapshot_path = tmp_path / "settings.sst"
    snapshot_path.write_text(
        json.dumps({
            "settings_version": 2,
            "profile": NORMAL_PROFILE,
            "snapshot": {
                "timing": {"interval": 77},
                "sources": {
                    "folders": [r"C:\Users\Private\Pictures"],
                    "rss_feeds": ["https://example.invalid/private"],
                },
                "widgets": {
                    "achievement_pulse": {
                        "font_family": "Jost",
                        "color": [12, 34, 56, 78],
                    },
                    "gmail": {"sound_file_path": r"C:\Users\Private\alert.ogg"},
                    "steam": {"api_key": "SECRET", "enabled": True},
                    "weather": {"location": "Private Home"},
                    "custom_layout": {
                        "displays": {"serial:PRIVATE-MONITOR": {"clock": {"x": 1}}},
                    },
                    "layout_slots": {
                        "slots": {"1": {"monitor_name": "PRIVATE-MONITOR"}},
                        "version": 1,
                    },
                },
            },
        }),
        encoding="utf-8",
    )

    imported = load_importable_settings_snapshot(snapshot_path)
    serialized = json.dumps(imported.settings, sort_keys=True)

    assert imported.settings["timing"]["interval"] == 77
    assert imported.settings["widgets"]["achievement_pulse"]["font_family"] == "Jost"
    assert imported.settings["widgets"]["achievement_pulse"]["color"] == [12, 34, 56, 78]
    assert imported.settings["widgets"]["steam"]["enabled"] is True
    assert "SECRET" not in serialized
    assert "Private Home" not in serialized
    assert "Private\\Pictures" not in serialized
    assert "Private\\alert.ogg" not in serialized
    assert "PRIVATE-MONITOR" not in serialized
    assert imported.removed_secret_fields >= 1
    assert "sources.folders" in imported.skipped_paths
    assert "widgets.weather.location" in imported.skipped_paths
    assert "widgets.custom_layout" in imported.skipped_paths
    assert "widgets.layout_slots" in imported.skipped_paths


def test_every_text_setting_tooltip_describes_valid_text_domain() -> None:
    settings = editable_base_settings(load_default_settings_source())
    text_leaves = [
        (path, value)
        for path, value in iter_leaf_settings(settings)
        if isinstance(value, str)
    ]

    assert text_leaves
    for path, value in text_leaves:
        assert "Valid text" in setting_tooltip(path, value, NORMAL_PROFILE)

    selection_tip = setting_tooltip(
        ("widgets", "achievement_pulse", "selection_mode"),
        "most_recent",
        NORMAL_PROFILE,
    )
    assert all(
        value in selection_tip
        for value in ("most_recent", "recent_5", "custom")
    )
    font_tip = setting_tooltip(
        ("widgets", "clock", "font_family"),
        "Inter",
        NORMAL_PROFILE,
    )
    assert "font installed on the target system" in font_tip


def test_normal_snapshot_import_preserves_explicit_mc_differences() -> None:
    models = {
        NORMAL_PROFILE: {
            "timing": {"interval": 60},
            "widgets": {"clock": {"font_family": "Inter"}},
        },
        MC_PROFILE: {
            "timing": {"interval": 180},
            "widgets": {"clock": {"font_family": "Inter"}},
        },
    }

    merged, explicit = merge_imported_profile(
        models,
        NORMAL_PROFILE,
        {
            "timing": {"interval": 77},
            "widgets": {"clock": {"font_family": "Jost"}},
        },
        {("timing", "interval")},
    )

    assert merged[NORMAL_PROFILE]["timing"]["interval"] == 77
    assert merged[MC_PROFILE]["timing"]["interval"] == 180
    assert merged[NORMAL_PROFILE]["widgets"]["clock"]["font_family"] == "Jost"
    assert merged[MC_PROFILE]["widgets"]["clock"]["font_family"] == "Jost"
    assert explicit == {("timing", "interval")}


def test_editor_uses_alpha_swatch_and_font_delegate_editors(qt_app, tmp_path) -> None:
    base_path = _copy_base_source(tmp_path)
    overrides_path = tmp_path / "default_profile_overrides.py"
    overrides_path.write_text(
        render_profile_overrides_module({NORMAL_PROFILE: {}, MC_PROFILE: {}}),
        encoding="utf-8",
    )
    editor = DefaultSettingsEditor(
        base_path=base_path,
        overrides_path=overrides_path,
        undo_path=tmp_path / "undo.json",
        regenerate=lambda: "",
    )
    try:
        delegate = editor.tree.itemDelegateForColumn(1)
        color_item = editor._leaf_items[("widgets", "achievement_pulse", "color")]
        font_item = editor._leaf_items[("widgets", "achievement_pulse", "font_family")]
        color_editor = delegate.createEditor(
            editor.tree,
            None,
            editor.tree.indexFromItem(color_item, 1),
        )
        font_editor = delegate.createEditor(
            editor.tree,
            None,
            editor.tree.indexFromItem(font_item, 1),
        )

        assert isinstance(color_editor, ColorSwatchButton)
        assert isinstance(font_editor, QFontComboBox)
        assert color_item.icon(1).isNull() is False
        color_editor.deleteLater()
        font_editor.deleteLater()
    finally:
        editor.close()
