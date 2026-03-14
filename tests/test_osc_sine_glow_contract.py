from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent


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
    from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs

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
        _osc_line_amplitude=3.0,
        _osc_smoothing=0.7,
        _star_density=1.0,
        _star_travel_speed=0.5,
        _star_reactivity=1.0,
        _nebula_tint1=[0, 0, 0, 255],
        _nebula_tint2=[0, 0, 0, 255],
        _nebula_cycle_speed=0.3,
        _blob_color=[0, 0, 0, 255],
        _blob_glow_color=[0, 0, 0, 255],
        _blob_edge_color=[0, 0, 0, 255],
        _blob_outline_color=[0, 0, 0, 255],
        _blob_pulse=1.0,
        _blob_width=1.0,
        _blob_size=1.0,
        _blob_glow_intensity=0.5,
        _blob_glow_reactivity=1.0,
        _blob_glow_max_size=1.0,
        _blob_reactive_glow=True,
        _blob_reactive_deformation=1.0,
        _blob_stage_gain=1.0,
        _blob_core_scale=1.0,
        _blob_core_floor_bias=0.35,
        _blob_stage_bias=0.0,
        _blob_stage2_release_ms=900.0,
        _blob_stage3_release_ms=1200.0,
        _blob_constant_wobble=1.0,
        _blob_reactive_wobble=1.0,
        _blob_stretch_tendency=0.35,
        _blob_stretch_inner=0.5,
        _blob_stretch_outer=0.5,
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
        _sine_line1_shift=0.0,
        _sine_line2_shift=0.0,
        _sine_line3_shift=0.0,
        _sine_wave_effect=0.0,
        _sine_micro_wobble=0.0,
        _sine_crawl_amount=0.0,
        _sine_width_reaction=0.0,
        _sine_vertical_shift=0,
        _helix_turns=4,
        _helix_double=True,
        _helix_speed=1.0,
        _helix_glow_enabled=True,
        _helix_glow_intensity=0.5,
        _helix_glow_color=[0, 0, 0, 255],
        _helix_reactive_glow=True,
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
        _sine_density=1.0,
        _sine_displacement=0.0,
        _sine_heartbeat=0.0,
        _heartbeat_intensity=0.0,
    )

    sine_extra = build_gpu_push_extra_kwargs(widget, "sine_wave", None)
    osc_extra = build_gpu_push_extra_kwargs(widget, "oscilloscope", None)

    assert sine_extra["glow_reactivity"] == 1.6
    assert osc_extra["glow_reactivity"] == 0.4


def test_settings_model_legacy_glow_size_falls_back_to_reactivity() -> None:
    from core.settings.models import SpotifyVisualizerSettings

    model = SpotifyVisualizerSettings.from_mapping({
        "osc_glow_size": 1.25,
        "sine_glow_size": 0.85,
    })

    assert model.osc_glow_reactivity == 1.25
    assert model.sine_glow_reactivity == 0.85
