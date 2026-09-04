"""V5b live-in-place lazy Settings bodies (WidgetsTab integration, A-J bar).

Option-1 exception: Spectrum stays eagerly constructed (it hosts the genuinely
shared fill/border/opacity controls physically nested in its Appearance bucket).
The other four modes (oscilloscope / sine_wave / bubble / devcurve) become lazy:
constructed on first selection, hydrated once from the canonical config at
construction, cached thereafter (no rebuild, no re-hydrate, no clobbering of
unsaved edits). Unbuilt modes run no loader and require no QWidget.
"""
from __future__ import annotations

import pytest

import ui.tabs.media.spectrum_builder as spectrum_builder
import ui.tabs.media.oscilloscope_builder as oscilloscope_builder
import ui.tabs.media.sine_wave_builder as sine_wave_builder
import ui.tabs.media.bubble_builder as bubble_builder
import ui.tabs.media.devcurve_builder as devcurve_builder
from ui.tabs.widgets_tab import WidgetsTab


_BUILDERS = {
    "spectrum": (spectrum_builder, "build_spectrum_ui"),
    "oscilloscope": (oscilloscope_builder, "build_oscilloscope_ui"),
    "sine_wave": (sine_wave_builder, "build_sine_wave_ui"),
    "bubble": (bubble_builder, "build_bubble_ui"),
    "devcurve": (devcurve_builder, "build_devcurve_ui"),
}

_CONTAINER_ATTR = {
    "spectrum": "_spectrum_settings_container",
    "oscilloscope": "_osc_settings_container",
    "sine_wave": "_sine_wave_settings_container",
    "bubble": "_bubble_settings_container",
    "devcurve": "_devcurve_settings_container",
}


def _install_counters(monkeypatch) -> dict[str, int]:
    counts: dict[str, int] = {mode: 0 for mode in _BUILDERS}
    for mode, (module, fn_name) in _BUILDERS.items():
        original = getattr(module, fn_name)

        def _wrapped(tab, layout, *, _mode=mode, _orig=original):
            counts[_mode] += 1
            return _orig(tab, layout)

        monkeypatch.setattr(module, fn_name, _wrapped)
    return counts


def _vis_settings(mode: str) -> dict:
    return {
        "spotify_visualizer": {
            "enabled": True,
            "visualizers_enabled": True,
            "mode": mode,
            # Distinct per-mode values so a stray re-hydration would be visible.
            "bubble_big_bass_pulse": 0.50,   # -> slider value 50
            "preset_bubble": 3,              # Custom slot, so controls hydrate raw
            "preset_oscilloscope": 3,
            "preset_sine_wave": 3,
            "preset_devcurve": 3,
        }
    }


def _make_tab(settings_manager, mode: str) -> WidgetsTab:
    settings_manager.set("widgets", _vis_settings(mode))
    return WidgetsTab(
        settings_manager,
        lazy_sections=True,
        initial_view_state={"subtab_id": "visualizers"},
    )


def _select_mode(tab: WidgetsTab, mode: str) -> None:
    combo = tab.vis_mode_combo
    idx = combo.findData(mode)
    assert idx >= 0, mode
    combo.blockSignals(True)
    combo.setCurrentIndex(idx)
    combo.blockSignals(False)
    tab._update_vis_mode_sections()


def test_open_with_bubble_active_builds_only_bubble(qt_app, settings_manager, monkeypatch):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        # V6a: every mode is lazy. Opening with Bubble active builds ONLY Bubble;
        # Spectrum (no longer eager) and the other three modes stay unbuilt.
        assert counts["bubble"] == 1
        assert counts["spectrum"] == 0
        assert counts["oscilloscope"] == 0
        assert counts["sine_wave"] == 0
        assert counts["devcurve"] == 0
        assert hasattr(tab, _CONTAINER_ATTR["bubble"])
        assert not hasattr(tab, _CONTAINER_ATTR["spectrum"])
        assert not hasattr(tab, _CONTAINER_ATTR["oscilloscope"])
        assert not hasattr(tab, _CONTAINER_ATTR["sine_wave"])
        assert not hasattr(tab, _CONTAINER_ATTR["devcurve"])
        # The shared appearance controls exist even though NO Spectrum body was
        # constructed — they are owned outside every mode body.
        assert hasattr(tab, "vis_fill_color_btn")
        assert hasattr(tab, "vis_border_color_btn")
        assert hasattr(tab, "vis_border_opacity")
        # Bubble was hydrated from the resolved config at construction: its slider
        # matches the config-derived value (computed exactly as the loader does).
        cfg = tab._vis_loaded_config
        expected = max(0, min(200, int(
            tab._config_float("spotify_visualizer", cfg, "bubble_big_bass_pulse", 0.5) * 100
        )))
        assert tab.bubble_big_bass_pulse.value() == expected
    finally:
        tab.deleteLater()


def test_spectrum_is_lazy_and_constructs_on_select(qt_app, settings_manager, monkeypatch):
    # V6a: Spectrum is no longer eager. Opening with Bubble active leaves Spectrum
    # unbuilt; selecting Spectrum constructs exactly it, once, and hydrates it.
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        assert counts["spectrum"] == 0
        assert not hasattr(tab, _CONTAINER_ATTR["spectrum"])

        _select_mode(tab, "spectrum")
        assert counts["spectrum"] == 1
        assert hasattr(tab, _CONTAINER_ATTR["spectrum"])
        # A Spectrum-owned control now exists (was absent while Spectrum unbuilt).
        assert hasattr(tab, "vis_ghost_enabled")

        _select_mode(tab, "spectrum")  # cached
        assert counts["spectrum"] == 1
    finally:
        tab.deleteLater()


def test_unsaved_spectrum_edit_survives_switch_away_and_back(qt_app, settings_manager, monkeypatch):
    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "spectrum")
    try:
        slider = tab.spectrum_drop_speed
        hydrated = slider.value()
        edited = slider.maximum() if hydrated != slider.maximum() else slider.minimum()
        slider.setValue(edited)

        _select_mode(tab, "bubble")
        _select_mode(tab, "spectrum")

        # Spectrum was not rebuilt and its unsaved edit was not re-hydrated.
        assert tab.spectrum_drop_speed is slider
        assert tab.spectrum_drop_speed.value() == edited
    finally:
        tab.deleteLater()


def test_saving_while_spectrum_unbuilt_preserves_its_persisted_state(qt_app, settings_manager, monkeypatch):
    # Active Bubble, Spectrum unbuilt: save must not require Spectrum QWidgets and
    # must not synthesize fallback Spectrum keys (ghost / preset stay persisted).
    from ui.tabs.widgets_tab_media import save_visualizer_settings

    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        assert not tab._vis_body_host.is_constructed("spectrum")
        result = save_visualizer_settings(tab)
        assert result["mode"] == "bubble"
        # Spectrum-owned ghost + preset keys are not synthesized while unbuilt.
        assert "spectrum_ghosting_enabled" not in result
        assert "spectrum_ghost_alpha" not in result
        assert "spectrum_ghost_decay" not in result
        assert "preset_spectrum" not in result
    finally:
        tab.deleteLater()


def test_selecting_a_lazy_mode_builds_only_that_mode_once(qt_app, settings_manager, monkeypatch):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        # B: selecting Oscilloscope constructs exactly that body, once.
        _select_mode(tab, "oscilloscope")
        assert counts["oscilloscope"] == 1
        assert counts["sine_wave"] == 0
        assert counts["devcurve"] == 0
        assert hasattr(tab, _CONTAINER_ATTR["oscilloscope"])

        # Selecting the same mode again reuses the cached body (build once).
        _select_mode(tab, "oscilloscope")
        assert counts["oscilloscope"] == 1
    finally:
        tab.deleteLater()


def test_switching_back_does_not_rebuild_or_rehydrate_unsaved_edit(qt_app, settings_manager, monkeypatch):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        # Bubble was built + hydrated at open.
        assert counts["bubble"] == 1
        hydrated = tab.bubble_big_bass_pulse.value()

        # An unsaved in-session edit to a value distinct from the hydrated one.
        edited = 200 if hydrated != 200 else 0
        tab.bubble_big_bass_pulse.setValue(edited)

        # Switch to another mode and back.
        _select_mode(tab, "spectrum")
        _select_mode(tab, "bubble")

        # Bubble was NOT rebuilt and its edited value was NOT re-hydrated.
        assert counts["bubble"] == 1
        assert tab.bubble_big_bass_pulse.value() == edited
    finally:
        tab.deleteLater()


def test_building_a_new_mode_does_not_rehydrate_another_modes_technical_edits(
    qt_app, settings_manager, monkeypatch
):
    # Constructing a NEW lazy mode hydrates only that mode's technical controls;
    # it must not re-hydrate (and clobber unsaved edits in) an already-built mode.
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        bubble_controls = get_per_mode_controls_for_mode(tab, "bubble")
        slider_key = next(
            k
            for k, w in bubble_controls.items()
            if hasattr(w, "setValue") and hasattr(w, "value") and hasattr(w, "maximum")
        )
        widget = bubble_controls[slider_key]
        original = widget.value()
        edited = widget.maximum() if original != widget.maximum() else widget.minimum()
        widget.setValue(edited)

        # Build a different lazy mode (triggers technical-control hydration).
        _select_mode(tab, "oscilloscope")

        # Bubble's unsaved technical edit is intact.
        assert bubble_controls[slider_key].value() == edited
    finally:
        tab.deleteLater()


def test_save_with_lazy_modes_unbuilt_preserves_their_persisted_state(qt_app, settings_manager, monkeypatch):
    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        # G: a save with only Spectrum + Bubble built must not require unbuilt
        # controls and must not emit fallback preset indices for absent sliders.
        from ui.tabs.widgets_tab_media import save_visualizer_settings

        result = save_visualizer_settings(tab)
        assert result["mode"] == "bubble"
        # Bubble (built) contributes its preset key; unbuilt modes do not.
        assert "preset_bubble" in result
        assert "preset_oscilloscope" not in result
        assert "preset_sine_wave" not in result
        assert "preset_devcurve" not in result
    finally:
        tab.deleteLater()


def test_missing_container_fails_loudly_and_leaves_mode_unconstructed(
    qt_app, settings_manager, monkeypatch
):
    # If a builder runs but does not create its settings container, the factory
    # must raise a contract error (no placeholder body) and the host must not
    # record the mode as constructed. The failure is not swallowed by
    # ensure_visualizer_mode_body.
    from ui.tabs.widgets_tab_media import ensure_visualizer_mode_body
    import ui.tabs.media.oscilloscope_builder as osc_mod

    tab = _make_tab(settings_manager, "bubble")
    try:
        # A builder that violates the container contract (creates nothing).
        monkeypatch.setattr(osc_mod, "build_oscilloscope_ui", lambda _tab, _layout: None)

        with pytest.raises(RuntimeError):
            ensure_visualizer_mode_body(tab, "oscilloscope")

        # Not cached as success, and no half-built container attribute.
        assert not tab._vis_body_host.is_constructed("oscilloscope")
        assert not hasattr(tab, _CONTAINER_ATTR["oscilloscope"])

        # The host is not poisoned: a well-behaved mode still constructs.
        monkeypatch.undo()
        _select_mode(tab, "sine_wave")
        assert tab._vis_body_host.is_constructed("sine_wave")
        assert hasattr(tab, _CONTAINER_ATTR["sine_wave"])
    finally:
        tab.deleteLater()


def test_settings_recreation_keeps_lazy_modes_unbuilt(qt_app, settings_manager, monkeypatch):
    # F: a fresh WidgetsTab (dialog recreation) with Spectrum active builds only
    # Spectrum; every lazy mode stays unbuilt until selected.
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "spectrum")
    try:
        assert counts["spectrum"] == 1
        assert counts["oscilloscope"] == 0
        assert counts["sine_wave"] == 0
        assert counts["bubble"] == 0
        assert counts["devcurve"] == 0
    finally:
        tab.deleteLater()
