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


@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager

    manager = SettingsManager(organization="SRPSSFocusedTests", application="VisualizerLazyBodies",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


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
        "preset_bubble": get_custom_preset_index("bubble"),
        "preset_devcurve": get_custom_preset_index("devcurve"),
    }
    if enabled_modes is not None:
        section["mode_activation"] = build_visualizer_mode_activation(enabled_modes)
    return {"spotify_visualizer": section}


def _cache(tab, mode: str) -> dict:
    """The Studio-owned body's value cache (the body builds no controls)."""
    from core.settings.visualizer_mode_settings import require_mode_settings
    return getattr(tab, f"_{require_mode_settings(mode).prefix}_lazy_values")


def _edit(tab, mode: str, key: str, value) -> None:
    """One edit as the Studio makes it: the value through the body's owner, Custom, then Settings' save."""
    _cache(tab, mode)[key] = value
    tab._force_visualizer_preset_to_custom(mode)
    tab._save_settings()


def _other(mode: str, key: str, current):
    from core.settings.visualizer_mode_settings import require_mode_settings
    control = require_mode_settings(mode).control(key)
    return control.low if float(current) != control.low else control.high


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
        # The shared families are held without a widget, for every owning mode, before any body exists.
        from ui.tabs.media.visualizer_mode_binding import FAMILY_CACHE_ATTR, family_controls
        held = getattr(tab, FAMILY_CACHE_ATTR)
        assert {c.key for m in _BUILDERS for c in family_controls(m)} <= set(held)
    finally:
        tab.deleteLater()


def test_all_current_3d_settings_pages_construct_and_roundtrip_owned_values(
    qt_app, settings_manager
):
    """The 3D Settings bodies are real pages: each builds through the lazy path, holds one mode-owned
    presentation value and one Technical value edited per mode, persists them, and a fresh Settings host
    restores each mode independently. Both values live in the body's value cache (no widget owns them)."""
    from core.settings.visualizer_mode_settings import require_mode_settings

    modes = ("extruded_spectrum", "shockwave_grid", "sphere")
    presentation_controls = {
        "extruded_spectrum": "extruded_spectrum_depth",
        "shockwave_grid": "shockwave_grid_wave_height",
        "sphere": "sphere_gloss",
    }

    tab = _make_tab(settings_manager, "extruded_spectrum", enabled_modes=modes)
    authored: dict[str, tuple[float, int]] = {}
    try:
        for mode in modes:
            tab._select_mode_page(mode)
            assert tab._vis_body_host.is_constructed(mode)
            assert tab._vis_body_host.selected_mode == mode
            assert not mode_has_rainbow_controls(mode)

            bar_count = require_mode_settings(mode).control(f"{mode}_bar_count")
            current_bar_count = _cache(tab, mode)[f"{mode}_bar_count"]

            key = presentation_controls[mode]
            new_presentation = _other(mode, key, _cache(tab, mode)[key])
            new_bar_count = (
                int(bar_count.low)
                if current_bar_count != int(bar_count.low)
                else int(bar_count.high)
            )
            _edit(tab, mode, key, new_presentation)
            _edit(tab, mode, f"{mode}_bar_count", new_bar_count)
            tab._save_settings_now()
            authored[mode] = (new_presentation, new_bar_count)

            persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
            assert persisted[key] == pytest.approx(new_presentation)
            assert persisted[f"{mode}_bar_count"] == new_bar_count
    finally:
        tab.deleteLater()
        qt_app.processEvents()

    reopened = VisualizersTab(settings_manager)
    try:
        for mode in modes:
            reopened._select_mode_page(mode)
            expected_presentation, expected_bar_count = authored[mode]
            assert _cache(reopened, mode)[presentation_controls[mode]] == pytest.approx(expected_presentation)
            assert _cache(reopened, mode)[f"{mode}_bar_count"] == expected_bar_count
    finally:
        reopened.deleteLater()


def test_current_3d_settings_curated_round_trip_restores_each_custom_without_cross_mode_leakage(
    qt_app, settings_manager
):
    """Exercise the real top-level preset transaction for every current 3D mode.

    A 3D mode leaving Custom must snapshot its own authored Settings state before
    a curated preset replaces the visible controls. Returning to Custom restores
    that exact mode-owned snapshot without borrowing from or mutating either of
    the other 3D modes.
    """
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
            assert _cache(tab, mode)[presentation_attr] == pytest.approx(expected_slider_value / 100.0)
            assert _cache(tab, mode)[f"{mode}_bar_count"] == bar_counts[mode]

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
            assert _cache(tab, mode)[presentation_attr] == pytest.approx(expected_slider_value / 100.0)
            assert _cache(tab, mode)[f"{mode}_bar_count"] == bar_counts[mode]

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


def test_shared_families_are_held_per_owning_mode_without_any_widget(
    qt_app, settings_manager, monkeypatch
):
    """Bar Appearance and Rainbow are edited in the Studios: the page holds them in its value cache, follows the
    selected mode's resolved preset, and never builds a widget for them in a body, on the page or in a holder."""
    from PySide6.QtWidgets import QWidget
    from ui.tabs.media.visualizer_mode_binding import FAMILY_CACHE_ATTR, family_controls
    _install_counters(monkeypatch)
    settings_manager.set("widgets", _vis_settings("spectrum"))
    tab = VisualizersTab(settings_manager)
    try:
        for target in ("spectrum", "bubble"):
            tab._select_mode_page(target)
            body = tab._vis_body_host.body(target)
            assert body is not None
            held = getattr(tab, FAMILY_CACHE_ATTR)
            resolved = tab._vis_loaded_config
            for control in family_controls(target):
                default = tab._widget_default("spotify_visualizer", control.key)
                assert held[control.key] == control.admit(resolved.get(control.key, default), default)
        tab._select_setup_page()
        assert tab.findChild(QWidget, "visualizer_studio_family_values") is None
        for attr in ("_base_appearance_group", "_rainbow_controls_container", "rainbow_enabled", "vis_border_opacity"):
            assert not hasattr(tab, attr), attr
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
        edited = _other("spectrum", "spectrum_drop_speed", _cache(tab, "spectrum")["spectrum_drop_speed"])
        _edit(tab, "spectrum", "spectrum_drop_speed", edited)
        tab._save_settings_now()
        tab._select_setup_page()

        tab._on_mode_admission_toggled("spectrum", False)
        assert not tab._vis_body_host.is_constructed("spectrum")
        assert not hasattr(tab, "_spectrum_settings_container")
        assert "spectrum" not in tab._vis_body_host.enabled_modes

        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert "spectrum_drop_speed" in persisted

        tab._on_mode_admission_toggled("spectrum", True)
        tab._select_mode_page("spectrum")
        second_body = tab._vis_body_host.body("spectrum")
        assert second_body is not first_body
        assert counts["spectrum"] == 2
        assert _cache(tab, "spectrum")["spectrum_drop_speed"] == pytest.approx(edited)
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
        edited = _other("spectrum", "spectrum_drop_speed", _cache(tab, "spectrum")["spectrum_drop_speed"])
        _edit(tab, "spectrum", "spectrum_drop_speed", edited)

        tab._select_mode_page("bubble")
        persisted = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert persisted["mode"] == "bubble"
        assert "spectrum_drop_speed" in persisted

        tab._select_mode_page("spectrum")
        assert _cache(tab, "spectrum")["spectrum_drop_speed"] == pytest.approx(edited)
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
        from core.settings.visualizer_mode_settings import require_mode_settings
        high = require_mode_settings("bubble").control("bubble_stream_reactivity").high
        assert _cache(tab, "bubble")["bubble_stream_reactivity"] == pytest.approx(high)
    finally:
        tab.deleteLater()
