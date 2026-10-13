"""Extruded spec consumer projection and bespoke Settings boundaries."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_mode_settings import require_mode_settings
from core.settings.visualizer_presets import get_custom_preset_index


def test_extruded_controls_apply_once_through_the_existing_source_and_presentation_owners():
    from widgets.spotify_visualizer.config_applier import (
        apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs, extruded_spectrum_parameters,
    )
    from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs, resolve_mode_source_config

    class Owner:
        def __init__(self):
            object.__setattr__(self, "writes", {})

        def __setattr__(self, key, value):
            self.writes[key] = self.writes.get(key, 0) + 1
            object.__setattr__(self, key, value)

    spec = require_mode_settings("extruded_spectrum")
    defaults = require_canonical_default("widgets.spotify_visualizer")
    values = {control.key: defaults[control.key] for control in spec.controls}
    values.update({"extruded_spectrum_wave_amplitude": 0.73, "extruded_spectrum_profile_floor": 0.23,
                   "extruded_spectrum_drop_speed": 2.31, "extruded_spectrum_ghosting_enabled": True,
                   "extruded_spectrum_ghost_alpha": 0.64, "extruded_spectrum_ghost_decay": 0.47})
    projected = resolve_mode_source_config("extruded_spectrum", values)
    logical, presentation = Owner(), Owner()
    apply_logical_vis_mode_kwargs(logical, projected)
    apply_presentation_vis_mode_kwargs(presentation, projected)
    for control in spec.source_controls():
        assert f"_{control.key}" not in logical.writes
        assert f"_{control.key}" not in presentation.writes
    assert logical.writes["_spectrum_ghosting_enabled"] == logical.writes["_spectrum_ghost_decay"] == 1
    assert logical._spectrum_ghost_decay == 0.47
    assert presentation.writes["_spectrum_ghost_alpha"] == 1
    assert presentation._spectrum_ghost_alpha == 0.64
    for control in spec.presentation_controls():
        assert presentation.writes[f"_{control.key}"] == 1
        assert f"_{control.key}" not in logical.writes

    calls = {}
    engine = SimpleNamespace(**{
        name: (lambda value, key=name: calls.setdefault(key, []).append(value))
        for name in ("set_spectrum_shaping_enabled", "set_spectrum_mirrored", "set_spectrum_shape_nodes",
                     "set_notch_positions", "set_spectrum_shape_config", "set_drop_speed")
    })
    assert apply_engine_vis_mode_kwargs(engine, projected)
    assert all(len(values) == 1 for values in calls.values())
    config = calls["set_spectrum_shape_config"][0]
    assert config.wave_amplitude == 0.73 and config.profile_floor == 0.23
    assert calls["set_drop_speed"] == [2.31]
    presentation._scene3d_detail = "Medium"
    parameters = extruded_spectrum_parameters(presentation)
    assert set(spec.keys()) & set(parameters) == {control.key for control in spec.presentation_controls()}


def test_extruded_custom_hooks_load_silently_and_preserve_unavailable_shadow_and_orbit_boundaries(
    qt_app, settings_manager, monkeypatch,
):
    from ui.tabs.media.extruded_spectrum_settings_binding import (
        collect_extruded_spectrum_mode_settings, load_extruded_spectrum_mode_settings,
    )
    from ui.tabs.visualizers_tab import VisualizersTab

    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "extruded_spectrum",
        "mode_activation": build_visualizer_mode_activation(["extruded_spectrum"]),
        "preset_extruded_spectrum": get_custom_preset_index("extruded_spectrum"),
    }})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("extruded_spectrum")
        calls = []
        monkeypatch.setattr(tab, "_save_settings", lambda: calls.append("save"))
        monkeypatch.setattr(tab, "_force_visualizer_preset_to_custom", lambda *_: calls.append("custom"))
        cfg = {**require_canonical_default("widgets.spotify_visualizer"),
               "extruded_spectrum_colouring": "Spectral Edges", "extruded_spectrum_mirrored": False,
               "extruded_spectrum_shape_nodes": [[0.0, 0.22], [1.0, 0.61]],
               "extruded_spectrum_visual_smoothing_enabled": True, "extruded_spectrum_visual_smoothing": 0.67,
               "extruded_spectrum_solid_bar_hysteresis_enabled": False,
               "extruded_spectrum_shadow_enabled": True, "extruded_spectrum_shadow_reach": "Distant",
               "extruded_spectrum_shadow_strength": 0.63,
               "extruded_spectrum_ghosting_enabled": True, "extruded_spectrum_rainbow_ghost": False}
        # Hydration is the availability authority even if external code enabled a disabled widget.
        for field in ("enabled", "reach", "strength"):
            getattr(tab, f"extruded_spectrum_shadow_{field}").setEnabled(True)
        load_extruded_spectrum_mode_settings(tab, cfg)
        assert calls == []
        payload = collect_extruded_spectrum_mode_settings(tab)
        for key, value in payload.items():
            expected = cfg[key]
            assert value == (pytest.approx(expected) if isinstance(expected, float) else expected), key
        assert "extruded_spectrum_turn" not in payload and "extruded_spectrum_tilt" not in payload
        assert not any("bar_fill" in key or "bar_border" in key for key in payload)
        assert tab.extruded_spectrum_rainbow_edges.isChecked()
        assert tab.extruded_spectrum_rainbow_faces.isEnabled()
        assert tab.extruded_spectrum_visual_smoothing_label.text() == "67%"
        assert not tab.extruded_spectrum_visual_smoothing.parentWidget().isHidden()
        for field in ("enabled", "reach", "strength"):
            control = getattr(tab, f"extruded_spectrum_shadow_{field}")
            assert not control.isEnabled() and "unavailable" in control.toolTip()
        # Independent Rainbow Ghost remains authorable while ordinary ghost detail rows hide.
        tab.extruded_spectrum_ghosting_enabled.setChecked(False)
        assert tab._extruded_spectrum_rows["extruded_spectrum_ghost_alpha"].isHidden()
        assert not tab._extruded_spectrum_rows["extruded_spectrum_rainbow_ghost"].isHidden()
        tab.extruded_spectrum_rainbow_ghost.setChecked(True)
        assert calls
        payload = collect_extruded_spectrum_mode_settings(tab)
        assert payload["extruded_spectrum_rainbow_ghost"] and not payload["extruded_spectrum_ghosting_enabled"]
        # Reset/default hydration cannot re-enable the rejected cast-shadow feature.
        load_extruded_spectrum_mode_settings(tab, require_canonical_default("widgets.spotify_visualizer"))
        assert all(not getattr(tab, f"extruded_spectrum_shadow_{field}").isEnabled()
                   for field in ("enabled", "reach", "strength"))
    finally:
        tab.deleteLater()
        qt_app.processEvents()
