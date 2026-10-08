"""V7 top-level Visualizers tab lazy-body and retirement contracts."""
from __future__ import annotations

import importlib

import pytest

from core.settings.visualizer_mode_registry import (
    build_visualizer_mode_activation,
    iter_visualizer_mode_descriptors,
    mode_has_rainbow_controls,
)
from core.settings.visualizer_presets import get_custom_preset_index
from rendering.widget_descriptors import get_widgets_tab_settings_section_descriptors
from ui.tabs.visualizers_tab import VisualizersTab


_BUILDERS = {
    descriptor.mode_id: (
        importlib.import_module(descriptor.settings_builder_module),
        descriptor.settings_builder_factory,
    )
    for descriptor in iter_visualizer_mode_descriptors()
    if descriptor.settings_builder_module and descriptor.settings_builder_factory
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
        "preset_spectrum": get_custom_preset_index("spectrum"),
        "preset_oscilloscope": get_custom_preset_index("oscilloscope"),
        "preset_sine_wave": get_custom_preset_index("sine_wave"),
        "preset_bubble": get_custom_preset_index("bubble"),
        "preset_devcurve": get_custom_preset_index("devcurve"),
    }
    if enabled_modes is not None:
        section["mode_activation"] = build_visualizer_mode_activation(enabled_modes)
    return {"spotify_visualizer": section}


def _make_tab(settings_manager, mode="bubble", *, enabled_modes=None) -> VisualizersTab:
    settings_manager.set("widgets", _vis_settings(mode, enabled_modes=enabled_modes))
    return VisualizersTab(settings_manager)


def test_widgets_tab_registry_no_longer_hosts_visualizers():
    assert "visualizers" not in {
        descriptor.section_id for descriptor in get_widgets_tab_settings_section_descriptors()
    }


@pytest.mark.parametrize(
    "mode",
    tuple(descriptor.mode_id for descriptor in iter_visualizer_mode_descriptors()),
)
def test_settings_shell_constructs_for_every_persisted_active_visualizer_mode(
    qt_app, settings_manager, mode
):
    """R-109: opening Settings must not assume stable accessories belong to active mode.

    The C6 Settings-authoring pass built the parked Bar Appearance accessory while
    Bubble was the persisted active mode.  Construction queried
    ``bubble:bar_appearance`` even though that bucket exists only for modes that
    physically host the accessory, so Settings died before its dialog appeared.
    Keep the shell lazy and constructible for every persisted mode identity.
    """
    tab = _make_tab(settings_manager, mode)
    try:
        assert tab._page_stack.currentWidget() is tab._setup_page
        assert tab._vis_body_host.constructed_modes() == frozenset()
    finally:
        tab.deleteLater()
        qt_app.processEvents()


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



def test_all_current_3d_settings_pages_construct_and_roundtrip_owned_values(
    qt_app, settings_manager
):
    """The migrated 3D Settings bodies must be real usable pages, not source-only schema.

    Exercise the exact lazy path that exposed the quota-stop KeyErrors, then edit one
    mode-owned presentation value and one Technical value per mode, persist them, and
    prove a fresh Settings host restores each mode independently.
    """
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    modes = ("extruded_spectrum", "shockwave_grid", "sphere")
    # These 3D modes do not participate in the shared 2D Rainbow accessory.
    # It stays parked/hidden instead of being inserted as a phantom bucket in
    # each mode. Extruded authors its renderer-specific Faces/Edges rainbow
    # participation explicitly in its own Appearance bucket.
    expected_buckets = {
        "extruded_spectrum": (["Bar Appearance", "Appearance", "Shape", "Response"], ["Material", "Reflection", "Shadow", "Render", "Ghost"]),
        "shockwave_grid": (["Appearance", "Waves", "Bar Response"], ["Render"]),
        "sphere": (["Frequency Zones", "Appearance", "Particle Flow"], ["Reactivity", "Rotation", "Effects"]),
    }
    presentation_controls = {
        "extruded_spectrum": "extruded_spectrum_depth",
        "shockwave_grid": "shockwave_grid_wave_height",
        "sphere": "sphere_gloss",
    }

    tab = _make_tab(settings_manager, "extruded_spectrum", enabled_modes=modes)
    authored: dict[str, tuple[int, int]] = {}
    try:
        for mode in modes:
            tab._select_mode_page(mode)
            assert tab._vis_body_host.is_constructed(mode)
            assert tab._vis_body_host.selected_mode == mode

            normal = getattr(tab, f"_{mode}_normal")
            advanced = getattr(tab, f"_{mode}_advanced")
            assert _bucket_titles(normal) == expected_buckets[mode][0]
            assert _bucket_titles(advanced) == expected_buckets[mode][1]
            assert not mode_has_rainbow_controls(mode)
            assert tab._rainbow_controls_container.isHidden()

            if mode == "extruded_spectrum":
                shape_host = normal.findChild(type(normal), "extruded_spectrum_bucket_shape")
                response_host = normal.findChild(type(normal), "extruded_spectrum_bucket_response")
                assert shape_host is not None and response_host is not None
                assert shape_host.isAncestorOf(tab.extruded_spectrum_shape_editor)
                assert not response_host.isAncestorOf(tab.extruded_spectrum_shape_editor)
                assert shape_host.isAncestorOf(tab.extruded_spectrum_mirrored)
                assert tab._base_appearance_group.parentWidget() is normal
                assert not hasattr(tab, "extruded_spectrum_colouring")
                assert hasattr(tab, "extruded_spectrum_rainbow_enabled")
                assert hasattr(tab, "extruded_spectrum_rainbow_faces")
                assert hasattr(tab, "extruded_spectrum_rainbow_edges")

            technical = get_per_mode_controls_for_mode(tab, mode)
            assert technical is not None
            assert technical["mode_key"] == mode
            bar_count = technical.get("bar_count")
            assert bar_count is not None

            presentation = getattr(tab, presentation_controls[mode])
            new_presentation = (
                presentation.minimum()
                if presentation.value() != presentation.minimum()
                else presentation.maximum()
            )
            new_bar_count = (
                bar_count.minimum()
                if bar_count.value() != bar_count.minimum()
                else bar_count.maximum()
            )
            presentation.setValue(new_presentation)
            bar_count.setValue(new_bar_count)
            tab._save_settings_now()
            authored[mode] = (new_presentation, new_bar_count)

            persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
            assert persisted[presentation_controls[mode]] == pytest.approx(
                new_presentation / 100.0
            )
            assert persisted[f"{mode}_bar_count"] == new_bar_count
    finally:
        tab.deleteLater()
        qt_app.processEvents()

    reopened = VisualizersTab(settings_manager)
    try:
        for mode in modes:
            reopened._select_mode_page(mode)
            technical = get_per_mode_controls_for_mode(reopened, mode)
            assert technical is not None
            expected_presentation, expected_bar_count = authored[mode]
            assert getattr(reopened, presentation_controls[mode]).value() == expected_presentation
            assert technical["bar_count"].value() == expected_bar_count
    finally:
        reopened.deleteLater()




def test_extruded_settings_explicit_rainbow_controls_encode_runtime_colouring_without_combo(
    qt_app, settings_manager
):
    """C6: product authoring is explicit while the renderer keeps its stable enum input."""
    widgets = _vis_settings("extruded_spectrum", enabled_modes=("extruded_spectrum",))
    section = widgets["spotify_visualizer"]
    section["preset_extruded_spectrum"] = get_custom_preset_index("extruded_spectrum")
    section["extruded_spectrum_colouring"] = "Bar Colours"
    settings_manager.set("widgets", widgets)

    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("extruded_spectrum")
        assert not hasattr(tab, "extruded_spectrum_colouring")
        assert tab.extruded_spectrum_rainbow_enabled.isChecked() is False
        assert tab.extruded_spectrum_rainbow_faces.isChecked() is True
        assert tab.extruded_spectrum_rainbow_faces.isEnabled() is False
        assert tab.extruded_spectrum_rainbow_edges.isEnabled() is False

        tab.extruded_spectrum_rainbow_enabled.setChecked(True)
        tab.extruded_spectrum_rainbow_edges.setChecked(True)
        tab._save_settings_now()
        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert persisted["extruded_spectrum_colouring"] == "Spectral Edges"

        tab.extruded_spectrum_rainbow_enabled.setChecked(False)
        tab._save_settings_now()
        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert persisted["extruded_spectrum_colouring"] == "Bar Colours"
    finally:
        tab.deleteLater()
        qt_app.processEvents()


def test_current_3d_settings_curated_round_trip_restores_each_custom_without_cross_mode_leakage(
    qt_app, settings_manager
):
    """Exercise the real top-level preset transaction for every current 3D mode.

    A 3D mode leaving Custom must snapshot its own authored Settings state before
    a curated preset replaces the visible controls. Returning to Custom restores
    that exact mode-owned snapshot without borrowing from or mutating either of
    the other 3D modes.
    """
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    modes = ("extruded_spectrum", "shockwave_grid", "sphere")
    presentation_controls = {
        "extruded_spectrum": ("extruded_spectrum_depth", 123),
        "shockwave_grid": ("shockwave_grid_wave_height", 61),
        "sphere": ("sphere_gloss", 73),
    }
    bar_counts = {
        "extruded_spectrum": 31,
        "shockwave_grid": 37,
        "sphere": 43,
    }

    widgets = _vis_settings("extruded_spectrum", enabled_modes=modes)
    section = widgets["spotify_visualizer"]
    for mode in modes:
        section[f"preset_{mode}"] = get_custom_preset_index(mode)
    section.update(
        {
            "extruded_spectrum_depth": 1.23,
            "extruded_spectrum_bar_count": bar_counts["extruded_spectrum"],
            "shockwave_grid_wave_height": 0.61,
            "shockwave_grid_bar_count": bar_counts["shockwave_grid"],
            "sphere_gloss": 0.73,
            "sphere_bar_count": bar_counts["sphere"],
        }
    )
    settings_manager.set("widgets", widgets)

    tab = VisualizersTab(settings_manager)
    try:
        # First prove the persisted Custom values hydrate into the real lazy UI.
        for mode in modes:
            tab._select_mode_page(mode)
            slider = getattr(tab, f"_{mode}_preset_slider")
            assert slider.preset_index() == slider.custom_index()
            presentation_attr, expected_slider_value = presentation_controls[mode]
            assert getattr(tab, presentation_attr).value() == expected_slider_value
            technical = get_per_mode_controls_for_mode(tab, mode)
            assert technical is not None
            assert technical["bar_count"].value() == bar_counts[mode]

        # Cycle each mode through a real curated-preset UI change and back to
        # Custom. The slider's own signal path invokes the canonical preset
        # snapshot/apply/restore transaction; flush only the existing bounded
        # Settings save coalescer so the persistence assertion is deterministic.
        for mode in modes:
            tab._select_mode_page(mode)
            slider = getattr(tab, f"_{mode}_preset_slider")
            custom_index = slider.custom_index()
            assert custom_index > 0

            before = settings_manager.get("widgets", {})["spotify_visualizer"]
            peer_snapshot = {
                other: (
                    before[presentation_controls[other][0]],
                    before[f"{other}_bar_count"],
                )
                for other in modes
                if other != mode
            }

            slider._slider.setValue(0)
            tab._flush_pending_visualizer_save()
            assert slider.preset_index() == 0

            slider._slider.setValue(custom_index)
            tab._flush_pending_visualizer_save()
            assert slider.preset_index() == custom_index

            presentation_attr, expected_slider_value = presentation_controls[mode]
            assert getattr(tab, presentation_attr).value() == expected_slider_value
            technical = get_per_mode_controls_for_mode(tab, mode)
            assert technical is not None
            assert technical["bar_count"].value() == bar_counts[mode]

            persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
            assert persisted[presentation_attr] == pytest.approx(expected_slider_value / 100.0)
            assert persisted[f"{mode}_bar_count"] == bar_counts[mode]
            for other, expected in peer_snapshot.items():
                assert persisted[presentation_controls[other][0]] == pytest.approx(expected[0])
                assert persisted[f"{other}_bar_count"] == expected[1]
    finally:
        tab.deleteLater()
        qt_app.processEvents()


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
    settings_manager.set("widgets", _vis_settings("spectrum"))
    settings_manager.set("widgets.spotify_visualizer.preset_spectrum", 0)
    tab = VisualizersTab(settings_manager)
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
        assert persisted["mode_activation"] == build_visualizer_mode_activation(("bubble",))
        assert "enabled_modes" not in persisted
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
        assert _bucket_titles(tab._spectrum_normal) == [
            "Appearance",
            "Shape",
            "Bar Appearance",
            "Rainbow",
        ]
        assert _bucket_titles(tab._spectrum_advanced) == ["Render", "Audio", "Ghost"]
        assert set(tab.spectrum_render_mode_buttons.keys()) == {"segment", "bars"}
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


        # Technical leaves share the same mode-page accordion as Custom leaves.
        tab._rainbow_bucket_toggle.setChecked(True)
        qt_app.processEvents()
        agc_toggle.setChecked(True)
        qt_app.processEvents()
        assert tab._rainbow_bucket_toggle.isChecked() is False
        assert tab.get_visualizer_bucket_state("spectrum", "rainbow") is False

        tab._rainbow_bucket_toggle.setChecked(True)
        qt_app.processEvents()
        assert agc_toggle.isChecked() is False
        assert tab.get_visualizer_tech_bucket_state("spectrum", "agc") is False

        transient_toggle.setChecked(True)
        qt_app.processEvents()

        assert tab._rainbow_bucket_toggle.isChecked() is False
        assert agc_toggle.isChecked() is False
        assert transient_toggle.isChecked() is True
        assert tab.get_visualizer_bucket_state("spectrum", "rainbow") is False
        assert tab.get_visualizer_tech_bucket_state("spectrum", "agc") is False
        assert tab.get_visualizer_tech_bucket_state("spectrum", "transient") is True
    finally:
        tab.deleteLater()

    reloaded = VisualizersTab(settings_manager)
    try:
        reloaded._select_mode_page("spectrum")
        reloaded_controls = get_per_mode_controls_for_mode(reloaded, "spectrum")
        assert reloaded_controls is not None
        assert reloaded_controls.get("agc_visibility_toggle").isChecked() is False
        assert reloaded_controls.get("transient_visibility_toggle").isChecked() is True
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
