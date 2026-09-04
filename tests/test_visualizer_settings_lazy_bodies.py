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


def test_custom_accessories_live_inside_custom_and_evacuate_before_retirement(
    qt_app, settings_manager, monkeypatch
):
    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "spectrum")
    try:
        # Stable controls start parked on the mode page: they are not SETUP UI and
        # opening Settings still constructs no mode merely to own them.
        assert tab._base_appearance_group.isAncestorOf(tab._shared_vis_fill_row)
        assert not tab._setup_page.isAncestorOf(tab._shared_vis_fill_row)

        tab._select_mode_page("spectrum")
        body = tab._vis_body_host.body("spectrum")
        assert body is not None
        assert tab._spectrum_normal.isAncestorOf(tab._base_appearance_group)
        assert tab._spectrum_normal.isAncestorOf(tab._rainbow_controls_container)

        # The stored fixture is curated. Custom-only buckets are physically in the
        # mode's normal/Custom section but are not presented until Custom is chosen.
        assert tab._spectrum_preset_slider.preset_index() != tab._spectrum_preset_slider.custom_index()
        assert tab._base_appearance_group.isHidden()
        assert tab._rainbow_controls_container.isHidden()

        old_loading = tab._loading
        tab._loading = True
        try:
            tab._spectrum_preset_slider.set_preset_index(
                tab._spectrum_preset_slider.custom_index()
            )
        finally:
            tab._loading = old_loading
        tab._update_rainbow_visibility()
        assert not tab._base_appearance_group.isHidden()
        assert not tab._rainbow_controls_container.isHidden()

        # Switching modes moves Rainbow into that mode's Custom section and parks
        # the Spectrum-only appearance bucket outside the cached Spectrum body.
        tab._select_mode_page("bubble")
        assert tab._bubble_normal.isAncestorOf(tab._rainbow_controls_container)
        assert not body.isAncestorOf(tab._base_appearance_group)
        assert not body.isAncestorOf(tab._shared_vis_fill_row)
        assert not hasattr(tab, "_shared_vis_appearance_holder")

        tab._select_setup_page()
        assert not body.isAncestorOf(tab._rainbow_controls_container)
        assert not body.isAncestorOf(tab._base_appearance_group)
    finally:
        tab.deleteLater()


def test_rainbow_custom_toggle_persists_immediately_and_speed_is_custom_only(
    qt_app, settings_manager, monkeypatch
):
    _install_counters(monkeypatch)
    tab = _make_tab(settings_manager, "bubble")
    try:
        tab._select_mode_page("bubble")
        slider = tab._bubble_preset_slider
        old_loading = tab._loading
        tab._loading = True
        try:
            slider.set_preset_index(slider.custom_index())
        finally:
            tab._loading = old_loading
        tab._update_rainbow_visibility()

        assert tab._bubble_normal.isAncestorOf(tab._rainbow_controls_container)
        assert not tab._rainbow_controls_container.isHidden()
        assert tab._rainbow_speed_container.isHidden()

        tab.rainbow_enabled.setChecked(True)
        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert persisted["bubble_rainbow_enabled"] is True
        assert not tab._rainbow_speed_container.isHidden()

        old_loading = tab._loading
        tab._loading = True
        try:
            slider.set_preset_index(0)
        finally:
            tab._loading = old_loading
        tab._update_rainbow_visibility()
        assert tab._rainbow_controls_container.isHidden()
        assert tab._rainbow_speed_container.isHidden()
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


# ---------------------------------------------------------------------------
# Invariants migrated from the retired pre-V7 WidgetsTab-hosted visualizer tests
# (test_widgets_tab.py, deleted). Each exercises a Settings-UI behavior that the
# shared builders/context still own, now proven against the VisualizersTab host.
# ---------------------------------------------------------------------------


def _bucket_titles(container) -> list[str]:
    layout = container.layout()
    titles: list[str] = []
    for idx in range(layout.count()):
        widget = layout.itemAt(idx).widget()
        if widget is not None:
            title = widget.property("bucketTitle")
            if title:
                titles.append(title)
    return titles


def test_spectrum_body_uses_authored_bucket_order_and_render_mode_buttons(
    qt_app, settings_manager
):
    tab = _make_tab(settings_manager, "spectrum")
    try:
        tab._select_mode_page("spectrum")
        assert _bucket_titles(tab._spectrum_normal) == ["Appearance", "Shape"]
        assert _bucket_titles(tab._spectrum_advanced) == ["Render", "Audio", "Ghost"]
        assert set(tab.spectrum_render_mode_buttons.keys()) == {"segment", "bars"}
        assert tab.spectrum_render_mode_buttons["bars"].text() == "BAR"
        assert tab.spectrum_render_mode_buttons["segment"].text() == "SEGMENTS"
        assert tab._spectrum_render_mode in {"bars", "segment"}
    finally:
        tab.deleteLater()


def test_spectrum_technical_bucket_visibility_persists_per_mode(qt_app, settings_manager):
    """Technical subsection visibility toggles persist per mode across recreation."""
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    tab = _make_tab(settings_manager, "spectrum")
    try:
        tab._select_mode_page("spectrum")
        controls = get_per_mode_controls_for_mode(tab, "spectrum")
        assert controls is not None
        agc_toggle = controls.get("agc_visibility_toggle")
        transient_toggle = controls.get("transient_visibility_toggle")
        assert agc_toggle is not None
        assert transient_toggle is not None

        agc_toggle.setChecked(True)
        transient_toggle.setChecked(False)
        qt_app.processEvents()

        assert tab.get_visualizer_tech_bucket_state("spectrum", "agc", False) is True
        assert tab.get_visualizer_tech_bucket_state("spectrum", "transient", True) is False
    finally:
        tab.deleteLater()

    reloaded = VisualizersTab(settings_manager)
    try:
        reloaded._select_mode_page("spectrum")
        reloaded_controls = get_per_mode_controls_for_mode(reloaded, "spectrum")
        assert reloaded_controls is not None
        assert reloaded_controls.get("agc_visibility_toggle").isChecked() is True
        assert reloaded_controls.get("transient_visibility_toggle").isChecked() is False
    finally:
        reloaded.deleteLater()


def test_editing_advanced_control_auto_switches_bubble_preset_to_custom(
    qt_app, settings_manager
):
    settings_manager.set(
        "widgets",
        {
            "spotify_visualizer": {
                "enabled": True,
                "visualizers_enabled": True,
                "mode": "bubble",
                "preset_bubble": 0,
            }
        },
    )
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("bubble")
        slider = tab._bubble_preset_slider
        slider.set_preset_index(0)  # a curated preset, not Custom
        assert slider.preset_index() != slider.custom_index()

        pulse = tab.bubble_big_bass_pulse
        pulse.setValue(min(pulse.maximum(), pulse.value() + 5))
        qt_app.processEvents()

        # Editing an advanced (mode-owned) control forks the curated preset to Custom.
        assert slider.preset_index() == slider.custom_index()
    finally:
        tab.deleteLater()


def test_bubble_swirl_toggle_hides_conflicting_direction_rows(qt_app, settings_manager):
    tab = _make_tab(settings_manager, "bubble")
    try:
        tab._select_mode_page("bubble")

        tab.bubble_swirl_enabled.setChecked(True)
        qt_app.processEvents()
        assert tab._bubble_stream_direction_row_widget.isHidden() is True
        assert tab._bubble_drift_direction_row_widget.isHidden() is True
        assert tab._bubble_swirl_direction_row_widget.isHidden() is False

        tab.bubble_swirl_enabled.setChecked(False)
        qt_app.processEvents()
        assert tab._bubble_stream_direction_row_widget.isHidden() is False
        assert tab._bubble_drift_direction_row_widget.isHidden() is False
        assert tab._bubble_swirl_direction_row_widget.isHidden() is True
    finally:
        tab.deleteLater()


def test_bubble_stream_reactivity_load_clamps_to_slider_maximum(qt_app, settings_manager):
    from core.settings.visualizer_presets import get_custom_preset_index

    settings_manager.set(
        "widgets",
        {
            "spotify_visualizer": {
                "enabled": True,
                "visualizers_enabled": True,
                "mode": "bubble",
                "preset_bubble": get_custom_preset_index("bubble"),
                "bubble_stream_reactivity": 2.75,
            }
        },
    )
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("bubble")
        assert tab.bubble_stream_reactivity.maximum() == 200
        assert tab.bubble_stream_reactivity.value() == 200
        assert tab.bubble_stream_reactivity_label.text() == "200%"
    finally:
        tab.deleteLater()
