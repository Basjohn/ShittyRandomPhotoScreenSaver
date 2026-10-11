from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def test_sine_shader_keeps_intensity_and_reactivity_controls() -> None:
    sine_src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "sine_wave.frag").read_text(
        encoding="utf-8"
    )
    # Sine remains the line-mode shader owner. Oscilloscope's old fragment
    # shader was retired in favour of the instanced beam program.
    assert "glow_alpha *= clamp(u_glow_intensity" in sine_src
    assert "uniform float u_glow_reactivity;" in sine_src


def test_oscilloscope_uses_instanced_beam_and_shared_scene_target() -> None:
    renderer_src = (ROOT / "rendering" / "quick" / "visualizer" / "implementations" / "oscilloscope.py").read_text(
        encoding="utf-8"
    )
    program_src = (ROOT / "rendering" / "gl_programs" / "oscilloscope_program.py").read_text(
        encoding="utf-8"
    )
    assert "SceneTarget" in renderer_src
    assert "glDrawArraysInstanced" in renderer_src
    assert "OscilloscopeFrame" in renderer_src
    assert "layout(std430, binding = 3)" in program_src
    assert "Emission" in program_src
    assert "uBright" in program_src


def _sine_widget() -> SimpleNamespace:
    return SimpleNamespace(
        presentation_config_host=None,
        _sine_glow_enabled=True,
        _sine_glow_intensity=0.7,
        _sine_glow_reactivity=1.6,
        _sine_glow_color=(0, 0, 0, 255),
        _sine_reactive_glow=True,
        _sine_sensitivity=1.25,
        _sine_smoothing=0.42,
        _sine_speed=0.73,
        _sine_line_dim=True,
        _sine_line_offset_bias=0.22,
        _sine_card_adaptation=0.3,
        _sine_wave_travel=2,
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
        _sine_vertical_shift=0.0,
        _sine_line_color=(0, 0, 0, 255),
        _sine_line_count=3,
        _sine_line2_color=(1, 2, 3, 255),
        _sine_line2_glow_color=(4, 5, 6, 255),
        _sine_line3_color=(7, 8, 9, 255),
        _sine_line3_glow_color=(10, 11, 12, 255),
        _sine_line4_color=(13, 14, 15, 255),
        _sine_line4_glow_color=(16, 17, 18, 255),
        _sine_line5_color=(19, 20, 21, 255),
        _sine_line5_glow_color=(22, 23, 24, 255),
        _sine_line6_color=(25, 26, 27, 255),
        _sine_line6_glow_color=(28, 29, 30, 255),
        _sine_ghost_line2_enabled=True,
        _sine_ghost_line3_enabled=True,
        _sine_ghost_line4_enabled=True,
        _sine_ghost_line5_enabled=True,
        _sine_ghost_line6_enabled=True,
        _sine_density=1.0,
        _sine_displacement=0.0,
        _sine_heartbeat=0.0,
        _heartbeat_intensity=0.0,
    )


def test_line_mode_visual_extras_are_sine_only() -> None:
    from widgets.spotify_visualizer.config_applier import _append_line_mode_visual_extras

    widget = _sine_widget()
    widget.presentation_config_host = widget
    extra: dict[str, object] = {}
    _append_line_mode_visual_extras(extra, widget)

    assert extra["glow_reactivity"] == 1.6
    assert extra["line_sensitivity"] == 1.25
    assert extra["line_smoothing"] == 0.42
    assert extra["line_speed"] == 0.73
    assert extra["line_dim"] is True
    assert extra["line_offset_bias"] == 0.22
    assert extra["line_count"] == 3
    assert extra["sine_wave_travel"] == 2
    assert "osc_line_amplitude" not in extra
    assert "osc_speed" not in extra
    assert "osc_line_count" not in extra
