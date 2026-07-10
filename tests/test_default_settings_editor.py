from __future__ import annotations

from copy import deepcopy

from core.settings.defaults import (
    MC_PROFILE,
    NORMAL_PROFILE,
    get_base_default_settings,
    get_default_settings,
)
from tools.default_settings_editor import (
    DefaultSettingsEditor,
    build_profile_models,
    build_profile_overrides,
    iter_leaf_settings,
    load_profile_overrides,
    read_undo_record,
    render_profile_overrides_module,
    set_path,
    setting_tooltip,
    write_undo_record,
)


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
    assert build_profile_overrides(base, models) == overrides

    path = tmp_path / "default_profile_overrides.py"
    path.write_text(render_profile_overrides_module(overrides), encoding="utf-8")
    assert load_profile_overrides(path) == overrides
    assert "Controls whether" in setting_tooltip(
        ("widgets", "new_card", "enabled"),
        True,
        NORMAL_PROFILE,
    )


def test_editor_transactional_save_and_single_level_undo(qt_app, tmp_path) -> None:
    overrides = {NORMAL_PROFILE: {}, MC_PROFILE: {}}
    overrides_path = tmp_path / "default_profile_overrides.py"
    undo_path = tmp_path / "undo.json"
    original_source = render_profile_overrides_module(overrides)
    overrides_path.write_text(original_source, encoding="utf-8")
    regenerations: list[bool] = []
    editor = DefaultSettingsEditor(
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
        assert saved[NORMAL_PROFILE]["widgets"]["achievement_pulse"]["square_artwork_size"] == 155
        assert read_undo_record(undo_path) == original_source

        editor._undo_and_regenerate()

        assert overrides_path.read_text(encoding="utf-8") == original_source
        assert not undo_path.exists()
        assert len(regenerations) == 2
    finally:
        editor.close()


def test_failed_save_restores_previous_undo_source_and_artifacts(qt_app, tmp_path, monkeypatch) -> None:
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
        overrides_path=overrides_path,
        undo_path=undo_path,
        regenerate=_regenerate,
    )
    try:
        path = ("widgets", "achievement_pulse", "square_artwork_size")
        set_path(editor._models[NORMAL_PROFILE], path, 155)
        set_path(editor._models[MC_PROFILE], path, 155)
        editor._save_and_regenerate()

        assert overrides_path.read_text(encoding="utf-8") == source_before
        assert read_undo_record(undo_path) == previous_source
        assert calls == [1, 2]
    finally:
        editor.close()


def test_failed_undo_restores_current_source_and_artifacts(qt_app, tmp_path, monkeypatch) -> None:
    overrides_path = tmp_path / "default_profile_overrides.py"
    undo_path = tmp_path / "undo.json"
    original_source = render_profile_overrides_module({NORMAL_PROFILE: {}, MC_PROFILE: {}})
    current_source = render_profile_overrides_module(
        {NORMAL_PROFILE: {"timing": {"update_interval": 321}}, MC_PROFILE: {}}
    )
    overrides_path.write_text(current_source, encoding="utf-8")
    write_undo_record(original_source, undo_path)
    calls: list[int] = []

    def _regenerate() -> str:
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            raise RuntimeError("injected undo generation failure")
        return "Restored current test artifacts"

    monkeypatch.setattr("tools.default_settings_editor.QMessageBox.critical", lambda *_args: None)
    editor = DefaultSettingsEditor(
        overrides_path=overrides_path,
        undo_path=undo_path,
        regenerate=_regenerate,
    )
    try:
        editor._undo_and_regenerate()

        assert overrides_path.read_text(encoding="utf-8") == current_source
        assert read_undo_record(undo_path) == original_source
        assert calls == [1, 2]
    finally:
        editor.close()
