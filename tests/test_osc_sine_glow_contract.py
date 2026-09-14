from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
TEST_APPDATA = ROOT / "tests_tmp_appdata"
TEST_APPDATA.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(TEST_APPDATA)


def test_glow_shaders_expose_reactivity_and_intensity_strength_contract() -> None:
    osc_src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "oscilloscope.frag").read_text(encoding="utf-8")
    sine_src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "sine_wave.frag").read_text(encoding="utf-8")

    # Contract: glow intensity remains the master visible-strength control.
    assert "glow_alpha *= clamp(u_glow_intensity" in osc_src
    assert "glow_alpha *= clamp(u_glow_intensity" in sine_src

    # Contract: reactivity has its own scalar control.
    assert "uniform float u_glow_reactivity;" in osc_src
    assert "uniform float u_glow_reactivity;" in sine_src


def test_build_gpu_extra_uses_mode_specific_glow_reactivity() -> None:
    from widgets.spotify_visualizer.config_applier import _append_line_mode_visual_extras

    widget = SimpleNamespace(
        _sine_glow_enabled=True,
        _osc_glow_enabled=True,
        _sine_glow_intensity=0.7,
        _osc_glow_intensity=0.3,
        _sine_glow_size=1.0,
        _osc_glow_size=1.0,
        _sine_glow_reactivity=1.6,
        _osc_glow_reactivity=0.4,
        _sine_glow_color=[0, 0, 0, 255],
        _osc_glow_color=[0, 0, 0, 255],
        _sine_reactive_glow=True,
        _osc_reactive_glow=True,
        _sine_sensitivity=1.0,
        _sine_smoothing=0.55,
        _osc_line_amplitude=3.0,
        _osc_smoothing=0.7,
        _sine_speed=1.0,
        _osc_speed=1.0,
        _sine_line_dim=False,
        _osc_line_dim=False,
        _sine_line_offset_bias=0.0,
        _osc_line_offset_bias=0.0,
        _osc_vertical_shift=0,
        _sine_wave_travel=0,
        _sine_card_adaptation=0.3,
        _sine_travel_line2=0,
        _sine_travel_line3=0,
        _sine_travel_line4=0,
        _sine_travel_line5=0,
        _sine_travel_line6=0,
        _sine_line1_shift=0.0,
        _sine_line2_shift=0.0,
        _sine_line3_shift=0.0,
        _sine_line4_shift=0.0,
        _sine_line5_shift=0.0,
        _sine_line6_shift=0.0,
        _sine_wave_effect=0.0,
        _sine_micro_wobble=0.0,
        _sine_crawl_amount=0.0,
        _sine_width_reaction=0.0,
        _sine_vertical_shift=0,
        _sine_line_color=[0, 0, 0, 255],
        _osc_line_color=[0, 0, 0, 255],
        _sine_line_count=1,
        _osc_line_count=1,
        _sine_line2_color=[0, 0, 0, 255],
        _osc_line2_color=[0, 0, 0, 255],
        _sine_line2_glow_color=[0, 0, 0, 255],
        _osc_line2_glow_color=[0, 0, 0, 255],
        _sine_line3_color=[0, 0, 0, 255],
        _osc_line3_color=[0, 0, 0, 255],
        _sine_line3_glow_color=[0, 0, 0, 255],
        _osc_line3_glow_color=[0, 0, 0, 255],
        _sine_line4_color=[0, 0, 0, 255],
        _osc_line4_color=[0, 0, 0, 255],
        _sine_line4_glow_color=[0, 0, 0, 255],
        _osc_line4_glow_color=[0, 0, 0, 255],
        _sine_line5_color=[0, 0, 0, 255],
        _osc_line5_color=[0, 0, 0, 255],
        _sine_line5_glow_color=[0, 0, 0, 255],
        _osc_line5_glow_color=[0, 0, 0, 255],
        _sine_line6_color=[0, 0, 0, 255],
        _osc_line6_color=[0, 0, 0, 255],
        _sine_line6_glow_color=[0, 0, 0, 255],
        _osc_line6_glow_color=[0, 0, 0, 255],
        _sine_ghost_line2_enabled=True,
        _osc_ghost_line2_enabled=True,
        _sine_ghost_line3_enabled=True,
        _osc_ghost_line3_enabled=True,
        _sine_ghost_line4_enabled=True,
        _osc_ghost_line4_enabled=True,
        _sine_ghost_line5_enabled=True,
        _osc_ghost_line5_enabled=True,
        _sine_ghost_line6_enabled=True,
        _osc_ghost_line6_enabled=True,
        _sine_density=1.0,
        _sine_displacement=0.0,
        _sine_heartbeat=0.0,
        _heartbeat_intensity=0.0,
    )

    widget.presentation_config_host = widget
    sine_extra = {}
    osc_extra = {}
    _append_line_mode_visual_extras(sine_extra, widget, is_sine=True)
    _append_line_mode_visual_extras(osc_extra, widget, is_sine=False)

    assert sine_extra["glow_reactivity"] == 1.6
    assert osc_extra["glow_reactivity"] == 0.4


def test_line_mode_gpu_extra_uses_neutral_runtime_transport_keys() -> None:
    from widgets.spotify_visualizer.config_applier import _append_line_mode_visual_extras

    widget = SimpleNamespace(
        _sine_glow_enabled=True,
        _osc_glow_enabled=True,
        _sine_glow_intensity=0.7,
        _osc_glow_intensity=0.3,
        _sine_glow_size=1.0,
        _osc_glow_size=1.0,
        _sine_glow_reactivity=1.6,
        _osc_glow_reactivity=0.4,
        _sine_glow_color=[0, 0, 0, 255],
        _osc_glow_color=[0, 0, 0, 255],
        _sine_reactive_glow=True,
        _osc_reactive_glow=True,
        _sine_sensitivity=1.25,
        _sine_smoothing=0.42,
        _osc_line_amplitude=3.75,
        _osc_smoothing=0.7,
        _sine_speed=0.73,
        _osc_speed=0.41,
        _sine_line_dim=True,
        _osc_line_dim=False,
        _sine_line_offset_bias=0.22,
        _osc_line_offset_bias=0.11,
        _osc_vertical_shift=0,
        _sine_wave_travel=2,
        _sine_card_adaptation=0.3,
        _sine_travel_line2=1,
        _sine_travel_line3=2,
        _sine_travel_line4=3,
        _sine_travel_line5=4,
        _sine_travel_line6=5,
        _sine_line1_shift=0.0,
        _sine_line2_shift=0.0,
        _sine_line3_shift=0.0,
        _sine_line4_shift=0.0,
        _sine_line5_shift=0.0,
        _sine_line6_shift=0.0,
        _sine_wave_effect=0.0,
        _sine_micro_wobble=0.0,
        _sine_crawl_amount=0.0,
        _sine_width_reaction=0.0,
        _sine_vertical_shift=0,
        _sine_line_color=[0, 0, 0, 255],
        _osc_line_color=[0, 0, 0, 255],
        _sine_line_count=3,
        _osc_line_count=1,
        _sine_line2_color=[1, 2, 3, 255],
        _osc_line2_color=[4, 5, 6, 255],
        _sine_line2_glow_color=[7, 8, 9, 255],
        _osc_line2_glow_color=[10, 11, 12, 255],
        _sine_line3_color=[13, 14, 15, 255],
        _osc_line3_color=[16, 17, 18, 255],
        _sine_line3_glow_color=[19, 20, 21, 255],
        _osc_line3_glow_color=[22, 23, 24, 255],
        _sine_line4_color=[25, 26, 27, 255],
        _osc_line4_color=[28, 29, 30, 255],
        _sine_line4_glow_color=[31, 32, 33, 255],
        _osc_line4_glow_color=[34, 35, 36, 255],
        _sine_line5_color=[37, 38, 39, 255],
        _osc_line5_color=[40, 41, 42, 255],
        _sine_line5_glow_color=[43, 44, 45, 255],
        _osc_line5_glow_color=[46, 47, 48, 255],
        _sine_line6_color=[49, 50, 51, 255],
        _osc_line6_color=[52, 53, 54, 255],
        _sine_line6_glow_color=[55, 56, 57, 255],
        _osc_line6_glow_color=[58, 59, 60, 255],
        _sine_ghost_line2_enabled=True,
        _osc_ghost_line2_enabled=True,
        _sine_ghost_line3_enabled=True,
        _osc_ghost_line3_enabled=True,
        _sine_ghost_line4_enabled=True,
        _osc_ghost_line4_enabled=True,
        _sine_ghost_line5_enabled=True,
        _osc_ghost_line5_enabled=True,
        _sine_ghost_line6_enabled=True,
        _osc_ghost_line6_enabled=True,
        _sine_density=1.0,
        _sine_displacement=0.0,
        _sine_heartbeat=0.0,
        _heartbeat_intensity=0.0,
    )

    widget.presentation_config_host = widget
    sine_extra = {}
    osc_extra = {}
    _append_line_mode_visual_extras(sine_extra, widget, is_sine=True)
    _append_line_mode_visual_extras(osc_extra, widget, is_sine=False)

    assert sine_extra["line_sensitivity"] == 1.25
    assert sine_extra["line_smoothing"] == 0.42
    assert sine_extra["line_speed"] == 0.73
    assert sine_extra["line_dim"] is True
    assert sine_extra["line_offset_bias"] == 0.22
    assert sine_extra["line_count"] == 3
    assert sine_extra["sine_wave_travel"] == 2
    assert "osc_line_amplitude" not in sine_extra
    assert "osc_speed" not in sine_extra
    assert "osc_line_count" not in sine_extra

    assert osc_extra["line_sensitivity"] == 3.75
    assert osc_extra["line_smoothing"] == 0.7
    assert osc_extra["line_speed"] == 0.41
    assert osc_extra["line_dim"] is False
    assert osc_extra["line_offset_bias"] == 0.11
    assert osc_extra["line_count"] == 1
    assert "osc_line_amplitude" not in osc_extra
    assert "osc_speed" not in osc_extra
    assert "osc_line_count" not in osc_extra


# Per-mode renderer source isolation is owned by
# tests/test_visualizer_mode_isolation.py, rehomed onto the current
# rendering/quick/visualizer/implementations/ owners after the pre-Quick
# widgets/spotify_visualizer/renderers/ directory was retired. The two former
# scrape cells here duplicated that invariant against the dead path and were
# removed rather than kept as redundant fossils.


# Removed test_settings_model_legacy_glow_size_falls_back_to_reactivity: the
# legacy `osc_glow_size`/`sine_glow_size` -> `*_glow_reactivity` migration alias
# was fully retired (no `glow_size` reference remains anywhere in core/settings).
# The current keys are `osc_glow_reactivity`/`sine_glow_reactivity`; this was a
# retired-migration fossil, not a live contract.
