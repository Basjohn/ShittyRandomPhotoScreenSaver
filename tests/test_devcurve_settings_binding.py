from __future__ import annotations

from PySide6.QtGui import QColor

from ui.tabs.media.devcurve_settings_binding import (
    collect_devcurve_mode_settings,
    load_devcurve_mode_settings,
)


class _Slider:
    def __init__(self):
        self._v = 0
    def setValue(self, v): self._v = int(v)
    def value(self): return int(self._v)


class _Label:
    def __init__(self): self.text = ""
    def setText(self, t): self.text = str(t)


class _Check:
    def __init__(self): self._v = False
    def setChecked(self, v): self._v = bool(v)
    def isChecked(self): return bool(self._v)


class _ShapeEditor:
    def __init__(self):
        self._nodes = [[0.0, 0.5], [1.0, 0.5]]
        self._layer_nodes = {
            "bass": [[0.0, 0.5], [1.0, 0.5]],
            "vocals": [[0.0, 0.5], [1.0, 0.5]],
            "mids": [[0.0, 0.5], [1.0, 0.5]],
            "transients": [[0.0, 0.5], [1.0, 0.5]],
        }
        self._active_layer = "bass"
        self._layer_strengths = {
            "bass": 1.0 / 3.0,
            "vocals": 1.0 / 3.0,
            "mids": 1.0 / 3.0,
            "transients": 1.15 / 3.0,
        }
    def set_nodes(self, nodes): self._nodes = list(nodes)
    def get_nodes(self): return list(self._nodes)
    def set_layer_nodes_map(self, nodes): self._layer_nodes = dict(nodes)
    def get_layer_nodes_map(self): return dict(self._layer_nodes)
    def set_layer_strengths(self, strengths): self._layer_strengths = dict(strengths)
    def get_layer_strengths(self): return dict(self._layer_strengths)
    def set_active_layer(self, layer): self._active_layer = str(layer)


class _Tab:
    def __init__(self):
        self.devcurve_base_level = _Slider(); self.devcurve_base_level_label = _Label()
        self.devcurve_motion_power = _Slider(); self.devcurve_motion_power_label = _Label()
        self.devcurve_idle_motion = _Slider(); self.devcurve_idle_motion_label = _Label()
        self.devcurve_idle_speed = _Slider(); self.devcurve_idle_speed_label = _Label()
        self.devcurve_smoothness = _Slider(); self.devcurve_smoothness_label = _Label()
        self.devcurve_growth = _Slider(); self.devcurve_growth_label = _Label()
        self.devcurve_shape_editor = _ShapeEditor()
        self.devcurve_ghost_enabled = _Check()
        self.devcurve_ghost_opacity = _Slider(); self.devcurve_ghost_opacity_label = _Label()
        self.devcurve_ghost_decay = _Slider(); self.devcurve_ghost_decay_label = _Label()
        self.devcurve_foreground_shadow_enabled = _Check()
        self.devcurve_foreground_shadow_alpha = _Slider(); self.devcurve_foreground_shadow_alpha_label = _Label()
        self.devcurve_foreground_shadow_darken = _Slider(); self.devcurve_foreground_shadow_darken_label = _Label()
        self.devcurve_foreground_shadow_offset = _Slider(); self.devcurve_foreground_shadow_offset_label = _Label()
        self.devcurve_foreground_specular_enabled = _Check()
        self.devcurve_foreground_specular_alpha = _Slider(); self.devcurve_foreground_specular_alpha_label = _Label()
        self.devcurve_foreground_specular_width = _Slider(); self.devcurve_foreground_specular_width_label = _Label()
        self.devcurve_foreground_specular_offset = _Slider(); self.devcurve_foreground_specular_offset_label = _Label()
        self.devcurve_foreground_specular_crest_bias = _Slider(); self.devcurve_foreground_specular_crest_bias_label = _Label()
        for src in ("bass", "vocals", "mids", "transients"):
            setattr(self, f"devcurve_layer_{src}_enabled", _Check())
            setattr(self, f"devcurve_layer_{src}_alpha", _Slider())
            setattr(self, f"devcurve_layer_{src}_alpha_label", _Label())
            setattr(self, f"devcurve_layer_{src}_offset", _Slider())
            setattr(self, f"devcurve_layer_{src}_offset_label", _Label())
            setattr(self, f"devcurve_layer_{src}_order", _Slider())
            setattr(self, f"devcurve_layer_{src}_order_label", _Label())
            setattr(self, f"_devcurve_layer_{src}_color", QColor(255, 255, 255, 255))
    def _config_bool(self, _ns, data, key, default): return bool(data.get(key, default))
    def _config_float(self, _ns, data, key, default): return float(data.get(key, default))


def test_devcurve_binding_load_and_collect_roundtrip():
    tab = _Tab()
    seen = []
    cfg = {
        "devcurve_base_level": 0.61,
        "devcurve_smoothness": 0.72,
        "devcurve_growth": 2.8,
        "devcurve_layer_bass_shape_nodes": [[0.0, 0.52], [1.0, 0.66]],
        "devcurve_layer_bass_alpha": 0.74,
        "devcurve_layer_bass_order": 3,
        "devcurve_layer_bass_outline_color": [12, 34, 56, 180],
        "devcurve_layer_bass_outline_width": 0.009,
        "devcurve_foreground_shadow_enabled": True,
        "devcurve_foreground_shadow_alpha": 0.41,
        "devcurve_foreground_shadow_darken": 0.47,
        "devcurve_foreground_shadow_offset": 0.11,
        "devcurve_foreground_specular_enabled": True,
        "devcurve_foreground_specular_alpha": 0.83,
        "devcurve_foreground_specular_width": 0.029,
        "devcurve_foreground_specular_offset": 0.05,
        "devcurve_foreground_specular_crest_bias": 1.22,
    }
    load_devcurve_mode_settings(tab, cfg, sync_color_button=lambda btn, attr: seen.append((btn, attr)))
    payload = collect_devcurve_mode_settings(tab)
    assert payload["devcurve_base_level"] == 0.61
    assert payload["devcurve_smoothness"] == 0.72
    assert payload["devcurve_growth"] == 2.8
    assert payload["devcurve_layer_bass_shape_nodes"] == [[0.0, 0.52], [1.0, 0.66]]
    assert payload["devcurve_layer_bass_alpha"] == 0.74
    assert payload["devcurve_layer_bass_order"] == 3
    assert payload["devcurve_layer_bass_outline_color"] == [12, 34, 56, 255]
    assert payload["devcurve_layer_bass_outline_width"] == 0.009
    assert payload["devcurve_foreground_shadow_enabled"] is True
    assert payload["devcurve_foreground_shadow_alpha"] == 0.41
    assert payload["devcurve_foreground_shadow_darken"] == 0.47
    assert payload["devcurve_foreground_shadow_offset"] == 0.11
    assert payload["devcurve_foreground_specular_enabled"] is True
    assert payload["devcurve_foreground_specular_alpha"] == 0.83
    assert payload["devcurve_foreground_specular_width"] == 0.029
    assert payload["devcurve_foreground_specular_offset"] == 0.05
    assert payload["devcurve_foreground_specular_crest_bias"] == 1.22
    assert "devcurve_outline_width" not in payload
    assert "devcurve_outline_alpha" not in payload
    assert seen == []
