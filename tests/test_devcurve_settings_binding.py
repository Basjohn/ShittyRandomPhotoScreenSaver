"""The DevCurve Custom shaper crosses the real spec build/load/save boundary."""
from __future__ import annotations

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_presets import get_custom_preset_index
from ui.tabs.media.devcurve_settings_binding import collect_devcurve_mode_settings, load_devcurve_mode_settings
from ui.tabs.visualizers_tab import VisualizersTab


def test_devcurve_binding_load_and_collect_roundtrip(qt_app, settings_manager, monkeypatch):
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "devcurve",
        "mode_activation": build_visualizer_mode_activation(["devcurve"]),
        "preset_devcurve": get_custom_preset_index("devcurve"),
    }})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("devcurve")
        calls = []
        monkeypatch.setattr(tab, "_save_settings", lambda: calls.append("save"))
        monkeypatch.setattr(tab, "_force_visualizer_preset_to_custom", lambda *_: calls.append("custom"))
        cfg = {
            **require_canonical_default("widgets.spotify_visualizer"),
            "devcurve_active_layer": "bass",
            "devcurve_base_level": 0.61, "devcurve_smoothness": 0.72,
            "devcurve_layer_bass_shape_nodes": [[0.0, 0.52], [1.0, 0.66]],
            "devcurve_layer_bass_power": 1.62, "devcurve_layer_bass_alpha": 0.74,
            "devcurve_layer_bass_offset": -0.15,
            "devcurve_layer_bass_order": 3, "devcurve_layer_vocals_order": 1,
            "devcurve_layer_mids_order": 2, "devcurve_layer_transients_order": 4,
            "devcurve_layer_bass_outline_color": [12, 34, 56, 180],
            "devcurve_layer_bass_outline_width": 0.009,
            "devcurve_foreground_shadow_enabled": True,
            "devcurve_foreground_shadow_alpha": 0.41,
            "devcurve_foreground_shadow_darken": 0.47,
            "devcurve_foreground_shadow_offset": 0.11,
            "devcurve_foreground_specular_enabled": True,
            "devcurve_foreground_specular_alpha": 0.83,
            "devcurve_foreground_specular_width": 0.029,
            "devcurve_foreground_specular_offset": -0.05,
            "devcurve_foreground_specular_crest_bias": 1.22,
        }
        load_devcurve_mode_settings(tab, cfg)
        assert calls == [], "loading Custom and scalar controls must neither save nor change the preset"
        payload = collect_devcurve_mode_settings(tab)
        for key in payload:
            expected = [12, 34, 56, 255] if key == "devcurve_layer_bass_outline_color" else cfg[key]
            if key.endswith("shape_nodes") or isinstance(expected, str):
                assert payload[key] == expected, key
            else:
                assert payload[key] == pytest.approx(expected), key
        assert tab.devcurve_foreground_specular_offset_label.text() == "-0.05"
        assert tab.devcurve_layer_bass_offset_label.text() == "-0.15"
        rows = tab._devcurve_rows
        assert rows["devcurve_foreground_shadow_enabled"] is rows["devcurve_foreground_specular_enabled"]
        assert tab.devcurve_active_layer_order.value() == 3
        assert tab.devcurve_active_layer_outline_width.value() == 9
        assert all(row.isHidden() for row in tab._devcurve_layer_rows["vocals"])
        tab.devcurve_layer_buttons["vocals"].click()
        assert all(not row.isHidden() for row in tab._devcurve_layer_rows["vocals"])
        assert collect_devcurve_mode_settings(tab)["devcurve_active_layer"] == "vocals"
        tab.devcurve_layer_vocals_enabled.setChecked(False)
        assert calls, "authoring changes must still cross the save/Custom boundary"
        payload = collect_devcurve_mode_settings(tab)
        assert payload["devcurve_layer_vocals_enabled"] is False
        assert sorted(payload[f"devcurve_layer_{source}_order"] for source in ("bass", "vocals", "mids", "transients")) == [1, 2, 3, 4]
    finally:
        tab.deleteLater()
        qt_app.processEvents()
