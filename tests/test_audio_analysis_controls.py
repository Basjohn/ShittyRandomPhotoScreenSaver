"""Audio Analysis (technical) controls per mode, derived from the registry; no authored value is pinned.

A mode hides a technical control (``technical_hidden_suffixes``) only when its published frame never reads it:

* a hidden control is still owned, stored and serialized, and neither Settings nor the Studio offers it;
* on recorded music re-analysed through the production DSP (``tools/visualizer_replay/analysis_controls_audit``)
  a hidden control leaves the mode's frame bit-identical, and every shown one moves it.

Nothing here shows a window: the replay is headless and the one real Settings tab is never shown.
"""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import (
    get_owned_mode_setting_keys, get_visualizer_mode_descriptor, iter_all_visualizer_mode_descriptors,
)

MODES = [d.mode_id for d in iter_all_visualizer_mode_descriptors()]
HIDING = [m for m in MODES if get_visualizer_mode_descriptor(m).technical_hidden_suffixes]
PREFIX = "widgets.spotify_visualizer."


def _spec(mode):
    from core.settings.visualizer_mode_settings import require_mode_settings
    return require_mode_settings(mode)


def _offered_suffixes(mode):
    return {control.key.removeprefix(f"{mode}_") for control in _spec(mode).technical_controls()}


def _other(control, default):
    """A test-owned value other than ``default`` that the control admits."""
    from core.settings.visualizer_mode_settings import Choice, Toggle
    if isinstance(control, Toggle):
        return not default
    if isinstance(control, Choice):
        return next(value for value in control.choices if value != default)
    span = float(control.high) - float(control.low)
    value = float(control.low) + span * 0.37
    if control.integer:
        value = int(round(value))
        return value if value != default else value + 1
    return value if abs(value - float(default)) > 1e-6 else value + span * 0.1


@pytest.mark.parametrize("mode", MODES)
def test_every_owned_technical_control_is_offered_or_hidden_by_the_one_registry_mechanism(mode):
    owned = set(get_owned_mode_setting_keys(mode, "technical"))
    hidden = set(get_visualizer_mode_descriptor(mode).technical_hidden_suffixes)
    offered = _offered_suffixes(mode)
    assert hidden <= owned, "a hidden control is still an owned (stored, serialized) one"
    assert not offered & hidden
    assert owned <= offered | hidden


@pytest.mark.parametrize("mode", HIDING)
def test_hidden_values_round_trip_through_the_settings_model(mode):
    from core.settings.models import SpotifyVisualizerSettings
    hidden = get_visualizer_mode_descriptor(mode).technical_hidden_suffixes
    defaults = SpotifyVisualizerSettings.from_mapping({}, apply_preset_overlay=False, resolve_preset_indices=False)
    wanted = {}
    for suffix in hidden:
        key = f"{mode}_{suffix}"
        wanted[key] = _other(_spec(mode).control(key), getattr(defaults, key))
    model = SpotifyVisualizerSettings.from_mapping(wanted, apply_preset_overlay=False, resolve_preset_indices=False)
    saved = model.to_dict()
    for key, value in wanted.items():
        assert saved[PREFIX + key] == pytest.approx(value), key
    again = SpotifyVisualizerSettings.from_mapping(
        {key[len(PREFIX):]: value for key, value in saved.items() if key.startswith(PREFIX)},
        apply_preset_overlay=False, resolve_preset_indices=False).to_dict()
    for key, value in wanted.items():
        assert again[PREFIX + key] == pytest.approx(value), key


@pytest.mark.parametrize("mode", MODES)
def test_studio_audio_analysis_group_offers_exactly_the_shown_controls(mode):
    from ui.studio.technical import technical_properties
    offered = {control.key for control in _spec(mode).technical_controls()}
    properties = technical_properties(mode, workspace="reactivity")
    assert set(properties) == offered
    for suffix in get_visualizer_mode_descriptor(mode).technical_hidden_suffixes:
        assert f"{mode}_{suffix}" not in properties


@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="AudioAnalysis",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


@pytest.mark.parametrize("mode", HIDING)
def test_real_tab_holds_no_hidden_control_value_and_keeps_their_stored_values_on_save(
        qt_app, settings_manager, monkeypatch, mode):
    """The real Visualizers tab (inside a dialog that is never shown; every pop-up patched)."""
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui import styled_popup
    from core.settings.visualizer_mode_settings import require_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab
    monkeypatch.setattr(styled_popup.StyledPopup, "exec", lambda self: 0)
    from core.settings.models import SpotifyVisualizerSettings
    hidden = get_visualizer_mode_descriptor(mode).technical_hidden_suffixes
    defaults = SpotifyVisualizerSettings.from_mapping({}, apply_preset_overlay=False, resolve_preset_indices=False)
    wanted = {}
    for suffix in hidden:
        key = f"{mode}_{suffix}"
        wanted[key] = _other(_spec(mode).control(key), getattr(defaults, key))
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": mode,
        "mode_activation": build_visualizer_mode_activation([mode]),
        f"preset_{mode}": get_custom_preset_index(mode), **wanted}})
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    tab = VisualizersTab(settings_manager)
    layout.addWidget(tab)
    tab._select_mode_page(mode)
    qt_app.processEvents()
    # The body's value cache is the only owner of technical values (no widget is built for any of them).
    cache = getattr(tab, f"_{require_mode_settings(mode).prefix}_lazy_values")
    offered = {control.key for control in _spec(mode).technical_controls()}
    hidden_keys = {f"{mode}_{suffix}" for suffix in hidden}
    assert offered and offered <= set(cache), "the shown controls' values are held"
    assert not hidden_keys & set(cache), "a hidden control holds no value"
    tab._save_settings_now()
    assert settings_manager.flush(timeout=5.)
    stored = settings_manager.get("widgets")["spotify_visualizer"]
    for key, value in wanted.items():
        assert stored[key] == pytest.approx(value), f"{key} survives a save with its widget absent"
    dialog.deleteLater()
    qt_app.processEvents()


# ----------------------------------------------------------------------------------- the published frame
WINDOW = {"clip": "growing_pains", "start": 7.5, "seconds": 4.0}      # the hot groove of a shipped Studio clip


@pytest.fixture(scope="module")
def audit(qt_app):
    from tools.visualizer_replay import analysis_controls_audit as module
    return module


@pytest.mark.parametrize("mode", MODES)
def test_shown_controls_move_the_published_frame_and_hidden_ones_never_do(audit, mode):
    clip = audit.load_clip(WINDOW["clip"], WINDOW["seconds"], WINDOW["start"])
    base = audit.baseline_values(mode, audit.frozen(mode))
    plan = audit.variations(mode, base)
    baselines: dict = {}

    def baseline(forced):
        key = repr(sorted(forced.items()))
        if key not in baselines:
            baselines[key] = audit.replay(mode, clip, forced)
        return baselines[key]

    # Negative control: the replay is deterministic, so a repeat differs by exactly nothing.
    assert not audit.difference(baseline({}), audit.replay(mode, clip, {}))["moved"]

    def moves(variation) -> bool:
        series = audit.replay(mode, clip, variation["overrides"])
        return audit.difference(baseline(variation["base_overrides"]), series)["moved"]

    shown = _offered_suffixes(mode)
    hidden = set(get_visualizer_mode_descriptor(mode).technical_hidden_suffixes)
    assert shown, mode
    for suffix in sorted(shown):
        variations = [item for item in plan if item["control"] == suffix]
        assert variations, f"{mode}: no variation planned for the shown control {suffix}"
        assert any(moves(item) for item in variations), f"{mode}: shown control {suffix} changes nothing it publishes"
    for suffix in sorted(hidden):
        for item in (item for item in plan if item["control"] == suffix):
            assert not moves(item), f"{mode}: hidden control {suffix} moves the frame ({item['label']})"
