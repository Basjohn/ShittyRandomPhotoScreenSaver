"""V7 top-level Visualizers tab lazy-body and retirement contracts."""
from __future__ import annotations

import ui.tabs.media.spectrum_builder as spectrum_builder
import ui.tabs.media.oscilloscope_builder as oscilloscope_builder
import ui.tabs.media.sine_wave_builder as sine_wave_builder
import ui.tabs.media.bubble_builder as bubble_builder
import ui.tabs.media.devcurve_builder as devcurve_builder

from rendering.widget_descriptors import get_widgets_tab_settings_section_descriptors
from ui.tabs.visualizers_tab import VisualizersTab


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
    counts = {mode: 0 for mode in _BUILDERS}
    for mode, (module, fn_name) in _BUILDERS.items():
        original = getattr(module, fn_name)

        def _wrapped(tab, layout, *, _mode=mode, _orig=original):
            counts[_mode] += 1
            return _orig(tab, layout)

        monkeypatch.setattr(module, fn_name, _wrapped)
    return counts


def _vis_settings(mode: str = "bubble", *, enabled_modes=None) -> dict:
    section = {
        "enabled": True,
        "visualizers_enabled": True,
        "mode": mode,
        "bubble_big_bass_pulse": 0.50,
        "spectrum_drop_speed": 1.85,
        "preset_spectrum": 3,
        "preset_oscilloscope": 3,
        "preset_sine_wave": 3,
        "preset_bubble": 3,
        "preset_devcurve": 3,
    }
    if enabled_modes is not None:
        section["enabled_modes"] = list(enabled_modes)
    return {"spotify_visualizer": section}


def _make_tab(settings_manager, mode="bubble", *, enabled_modes=None) -> VisualizersTab:
    settings_manager.set("widgets", _vis_settings(mode, enabled_modes=enabled_modes))
    return VisualizersTab(settings_manager)


def test_widgets_tab_registry_no_longer_hosts_visualizers():
    assert "visualizers" not in {
        descriptor.section_id for descriptor in get_widgets_tab_settings_section_descriptors()
    }


def test_opening_visualizers_lands_on_setup_and_builds_zero_modes(
    qt_app, settings_manager, monkeypatch
):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        assert tab._page_stack.currentWidget() is tab._setup_page
        assert counts == {mode: 0 for mode in _BUILDERS}
        assert tab._vis_body_host.constructed_modes() == frozenset()
        assert hasattr(tab, "vis_fill_color_btn")
        assert hasattr(tab, "vis_border_color_btn")
        assert hasattr(tab, "vis_border_opacity")
    finally:
        tab.deleteLater()


def test_selecting_mode_pill_constructs_only_that_mode_once(
    qt_app, settings_manager, monkeypatch
):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        tab._select_mode_page("bubble")
        assert counts["bubble"] == 1
        assert sum(counts.values()) == 1
        assert tab._vis_body_host.selected_mode == "bubble"
        assert tab._page_stack.currentWidget() is tab._mode_page

        tab._select_setup_page()
        tab._select_mode_page("bubble")
        assert counts["bubble"] == 1
    finally:
        tab.deleteLater()


def test_base_appearance_is_contextual_but_never_a_mode_body_descendant(
    qt_app, settings_manager, monkeypatch
):
    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "spectrum")
    try:
        # Stable appearance controls belong to the mode page presentation, not
        # SETUP and never to a retireable Spectrum body.
        assert tab._base_appearance_group.isAncestorOf(tab._shared_vis_fill_row)
        assert not tab._setup_page.isAncestorOf(tab._shared_vis_fill_row)

        tab._select_mode_page("spectrum")
        assert tab._base_appearance_group.isVisible()
        body = tab._vis_body_host.body("spectrum")
        assert body is not None
        assert not body.isAncestorOf(tab._shared_vis_fill_row)
        assert not body.isAncestorOf(tab._shared_vis_border_row)
        assert not body.isAncestorOf(tab._shared_vis_border_opacity_row)
        assert tab._shared_vis_fill_row.parent() is not body
        assert not hasattr(tab, "_shared_vis_appearance_holder")

        # The old V6a presentation exposed these rows only with Spectrum; other
        # mode builders have their own authored appearance controls.
        tab._select_mode_page("bubble")
        assert not tab._base_appearance_group.isVisible()
    finally:
        tab.deleteLater()


def test_family_capability_close_retires_constructed_bodies(
    qt_app, settings_manager, monkeypatch
):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        tab._select_mode_page("bubble")
        assert counts["bubble"] == 1
        assert tab._vis_body_host.is_constructed("bubble")

        tab.set_family_capability_available(False)
        assert not tab.isEnabled()
        assert tab._vis_body_host.constructed_modes() == frozenset()
        assert tab._page_stack.currentWidget() is tab._setup_page

        tab.set_family_capability_available(True)
        assert tab.isEnabled()
        assert tab._vis_body_host.constructed_modes() == frozenset()
        tab._select_mode_page("bubble")
        assert counts["bubble"] == 2
    finally:
        tab.deleteLater()


def test_disable_retires_real_qt_body_and_reenable_reconstructs_from_state(
    qt_app, settings_manager, monkeypatch
):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "spectrum")
    try:
        tab._select_mode_page("spectrum")
        first_body = tab._vis_body_host.body("spectrum")
        slider = tab.spectrum_drop_speed
        edited = slider.maximum() if slider.value() != slider.maximum() else slider.minimum()
        slider.setValue(edited)
        tab._save_settings_now()
        tab._select_setup_page()

        tab._on_mode_admission_toggled("spectrum", False)
        assert not tab._vis_body_host.is_constructed("spectrum")
        assert not hasattr(tab, "_spectrum_settings_container")
        assert not hasattr(tab, "spectrum_drop_speed")
        assert "spectrum" not in tab._vis_body_host.enabled_modes

        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert "spectrum_drop_speed" in persisted

        tab._on_mode_admission_toggled("spectrum", True)
        tab._select_mode_page("spectrum")
        second_body = tab._vis_body_host.body("spectrum")
        assert second_body is not first_body
        assert counts["spectrum"] == 2
        assert tab.spectrum_drop_speed.value() == edited
    finally:
        tab.deleteLater()


def test_last_enabled_mode_cannot_be_disabled(qt_app, settings_manager):
    tab = _make_tab(settings_manager, "bubble", enabled_modes=["bubble"])
    try:
        checkbox = tab._mode_admission_checkboxes["bubble"]
        assert checkbox.isChecked()
        assert not checkbox.isEnabled()
        tab._on_mode_admission_toggled("bubble", False)
        assert tab._vis_body_host.enabled_modes == ("bubble",)
    finally:
        tab.deleteLater()


def test_disabling_active_mode_substitutes_without_constructing_replacement(
    qt_app, settings_manager, monkeypatch
):
    counts = _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "spectrum", enabled_modes=["spectrum", "bubble"])
    try:
        tab._select_mode_page("spectrum")
        tab._select_setup_page()
        assert counts["bubble"] == 0

        tab._on_mode_admission_toggled("spectrum", False)
        assert tab._get_active_visualizer_mode() == "bubble"
        assert tab._vis_body_host.enabled_modes == ("bubble",)
        assert counts["bubble"] == 0
        assert not tab._vis_body_host.is_constructed("bubble")

        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert persisted["mode"] == "bubble"
        assert persisted["enabled_modes"] == ["bubble"]
    finally:
        tab.deleteLater()


def test_switch_flushes_outgoing_edit_before_new_mode_becomes_authoritative(
    qt_app, settings_manager, monkeypatch
):
    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "spectrum", enabled_modes=["spectrum", "bubble"])
    try:
        tab._select_mode_page("spectrum")
        slider = tab.spectrum_drop_speed
        edited = slider.maximum() if slider.value() != slider.maximum() else slider.minimum()
        slider.setValue(edited)

        tab._select_mode_page("bubble")
        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert persisted["mode"] == "bubble"
        assert "spectrum_drop_speed" in persisted

        tab._select_mode_page("spectrum")
        assert tab.spectrum_drop_speed.value() == edited
    finally:
        tab.deleteLater()
