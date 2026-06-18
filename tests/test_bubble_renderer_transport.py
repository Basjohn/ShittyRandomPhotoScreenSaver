from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtGui import QColor

from widgets.spotify_visualizer.energy_bands import EnergyBands
import widgets.spotify_visualizer.renderers.bubble as bubble_renderer


class _CaptureGL:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def glUniform1f(self, loc, value) -> None:
        self.calls.append(("glUniform1f", loc, value))

    def glUniform1i(self, loc, value) -> None:
        self.calls.append(("glUniform1i", loc, value))

    def glUniform2f(self, loc, a, b) -> None:
        self.calls.append(("glUniform2f", loc, a, b))

    def glUniform4f(self, loc, a, b, c, d) -> None:
        self.calls.append(("glUniform4f", loc, a, b, c, d))

    def glUniform4fv(self, loc, count, values) -> None:
        self.calls.append(("glUniform4fv", loc, count, id(values), np.array(values, copy=True)))

    def glUniform3fv(self, loc, count, values) -> None:
        self.calls.append(("glUniform3fv", loc, count, id(values), np.array(values, copy=True)))


def _make_state(**overrides):
    base = dict(
        _energy_bands=EnergyBands(bass=0.22, mid=0.33, high=0.44, overall=0.55),
        _playing=True,
        _bubble_ghost_alpha=0.45,
        _bubble_ghosting_enabled=True,
        _bubble_count=3,
        _bubble_pos_data=[0.10, 0.20, 0.30, 0.40, 0.50, 0.60],
        _bubble_extra_data=[0.70, 0.80, 0.90, 1.00, 1.10],
        _bubble_trail_data=[0.11, 0.12, 0.13, 0.21, 0.22],
        _bubble_trail_strength=0.35,
        _bubble_tail_opacity=0.65,
        _bubble_specular_direction="top_left",
        _bubble_gradient_direction="top",
        _bubble_outline_color=QColor(10, 20, 30, 255),
        _bubble_specular_color=QColor(40, 50, 60, 255),
        _bubble_gradient_light=QColor(70, 80, 90, 255),
        _bubble_gradient_dark=QColor(15, 25, 35, 255),
        _bubble_pop_color=QColor(200, 210, 220, 255),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_bubble_renderer_reuses_transport_buffers_and_zeroes_tail():
    gl = _CaptureGL()
    uniforms = {
        "u_overall_energy": 1,
        "u_bass_energy": 2,
        "u_mid_energy": 3,
        "u_high_energy": 4,
        "u_playing": 5,
        "u_ghost_alpha": 6,
        "u_bubble_count": 7,
        "u_bubbles_pos": 8,
        "u_bubbles_extra": 9,
        "u_bubbles_trail": 10,
        "u_trail_strength": 11,
        "u_tail_opacity": 12,
        "u_specular_dir": 13,
        "u_gradient_dir": 14,
        "u_gradient_mode": 15,
        "u_outline_color": 16,
        "u_specular_color": 17,
        "u_gradient_light": 18,
        "u_gradient_dark": 19,
        "u_pop_color": 20,
    }
    state = _make_state()

    assert bubble_renderer.upload_uniforms(gl, uniforms, state) is True
    first_pos = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 8))
    first_extra = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 9))
    first_trail = next(call for call in gl.calls if call[:2] == ("glUniform3fv", 10))

    assert first_pos[2] == 3
    assert first_extra[2] == 3
    assert first_trail[2] == 9
    assert first_pos[4][:6].tolist() == pytest.approx([0.10, 0.20, 0.30, 0.40, 0.50, 0.60])
    assert float(first_pos[4][6]) == 0.0
    assert first_extra[4][:5].tolist() == pytest.approx([0.70, 0.80, 0.90, 1.00, 1.10])
    assert float(first_extra[4][5]) == 0.0
    assert first_trail[4][:5].tolist() == pytest.approx([0.11, 0.12, 0.13, 0.21, 0.22])
    assert float(first_trail[4][5]) == 0.0

    gl.calls.clear()
    state._bubble_pos_data = [0.91, 0.81]
    state._bubble_extra_data = [0.71]
    state._bubble_trail_data = [0.61, 0.51]

    assert bubble_renderer.upload_uniforms(gl, uniforms, state) is True
    second_pos = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 8))
    second_extra = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 9))
    second_trail = next(call for call in gl.calls if call[:2] == ("glUniform3fv", 10))

    assert second_pos[3] == first_pos[3]
    assert second_extra[3] == first_extra[3]
    assert second_trail[3] == first_trail[3]
    assert second_pos[2] == 3
    assert second_extra[2] == 3
    assert second_trail[2] == 9

    assert second_pos[4][:4].tolist() == pytest.approx([0.91, 0.81, 0.0, 0.0])
    assert second_extra[4][:4].tolist() == pytest.approx([0.71, 0.0, 0.0, 0.0])
    assert second_trail[4][:4].tolist() == pytest.approx([0.61, 0.51, 0.0, 0.0])


def test_bubble_renderer_skips_trail_upload_when_tail_effect_disabled():
    gl = _CaptureGL()
    uniforms = {
        "u_overall_energy": 1,
        "u_bass_energy": 2,
        "u_mid_energy": 3,
        "u_high_energy": 4,
        "u_playing": 5,
        "u_ghost_alpha": 6,
        "u_bubble_count": 7,
        "u_bubbles_pos": 8,
        "u_bubbles_extra": 9,
        "u_bubbles_trail": 10,
        "u_trail_strength": 11,
        "u_tail_opacity": 12,
        "u_specular_dir": 13,
        "u_gradient_dir": 14,
        "u_gradient_mode": 15,
        "u_outline_color": 16,
        "u_specular_color": 17,
        "u_gradient_light": 18,
        "u_gradient_dark": 19,
        "u_pop_color": 20,
    }
    state = _make_state(
        _bubble_trail_strength=0.0,
        _bubble_tail_opacity=0.0,
    )

    assert bubble_renderer.upload_uniforms(gl, uniforms, state) is True
    assert not any(call[:2] == ("glUniform3fv", 10) for call in gl.calls)


def test_bubble_renderer_transport_preserves_active_payload_prefix_exactly():
    gl = _CaptureGL()
    uniforms = {
        "u_overall_energy": 1,
        "u_bass_energy": 2,
        "u_mid_energy": 3,
        "u_high_energy": 4,
        "u_playing": 5,
        "u_ghost_alpha": 6,
        "u_bubble_count": 7,
        "u_bubbles_pos": 8,
        "u_bubbles_extra": 9,
        "u_bubbles_trail": 10,
        "u_trail_strength": 11,
        "u_tail_opacity": 12,
        "u_specular_dir": 13,
        "u_gradient_dir": 14,
        "u_gradient_mode": 15,
        "u_outline_color": 16,
        "u_specular_color": 17,
        "u_gradient_light": 18,
        "u_gradient_dark": 19,
        "u_pop_color": 20,
    }
    state = _make_state(
        _bubble_count=2,
        _bubble_pos_data=[0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80],
        _bubble_extra_data=[0.91, 0.92, 0.93, 0.94, 1.01, 1.02, 1.03, 1.04],
        _bubble_trail_data=[
            0.11, 0.12, 0.13, 0.21, 0.22, 0.23, 0.31, 0.32, 0.33,
            0.41, 0.42, 0.43, 0.51, 0.52, 0.53, 0.61, 0.62, 0.63,
        ],
        _bubble_trail_strength=0.40,
        _bubble_tail_opacity=0.75,
    )

    assert bubble_renderer.upload_uniforms(gl, uniforms, state) is True

    pos = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 8))
    extra = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 9))
    trail = next(call for call in gl.calls if call[:2] == ("glUniform3fv", 10))

    assert pos[2] == 2
    assert extra[2] == 2
    assert trail[2] == 6
    assert pos[4][:8].tolist() == pytest.approx(state._bubble_pos_data)
    assert extra[4][:8].tolist() == pytest.approx(state._bubble_extra_data)
    assert trail[4][:18].tolist() == pytest.approx(state._bubble_trail_data)


def test_bubble_renderer_zeroes_only_the_active_prefix_when_count_shrinks():
    gl = _CaptureGL()
    uniforms = {
        "u_overall_energy": 1,
        "u_bass_energy": 2,
        "u_mid_energy": 3,
        "u_high_energy": 4,
        "u_playing": 5,
        "u_ghost_alpha": 6,
        "u_bubble_count": 7,
        "u_bubbles_pos": 8,
        "u_bubbles_extra": 9,
        "u_bubbles_trail": 10,
        "u_trail_strength": 11,
        "u_tail_opacity": 12,
        "u_specular_dir": 13,
        "u_gradient_dir": 14,
        "u_gradient_mode": 15,
        "u_outline_color": 16,
        "u_specular_color": 17,
        "u_gradient_light": 18,
        "u_gradient_dark": 19,
        "u_pop_color": 20,
    }
    state = _make_state(
        _bubble_count=3,
        _bubble_pos_data=[float(i) for i in range(12)],
        _bubble_extra_data=[float(i) + 0.5 for i in range(12)],
        _bubble_trail_data=[float(i) + 0.25 for i in range(27)],
        _bubble_trail_strength=0.40,
        _bubble_tail_opacity=0.75,
    )

    assert bubble_renderer.upload_uniforms(gl, uniforms, state) is True
    first_pos = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 8))
    first_extra = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 9))
    first_trail = next(call for call in gl.calls if call[:2] == ("glUniform3fv", 10))

    gl.calls.clear()
    state._bubble_count = 1
    state._bubble_pos_data = [9.1, 9.2, 9.3, 9.4]
    state._bubble_extra_data = [8.1, 8.2, 8.3, 8.4]
    state._bubble_trail_data = [7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9]

    assert bubble_renderer.upload_uniforms(gl, uniforms, state) is True
    second_pos = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 8))
    second_extra = next(call for call in gl.calls if call[:2] == ("glUniform4fv", 9))
    second_trail = next(call for call in gl.calls if call[:2] == ("glUniform3fv", 10))

    assert second_pos[3] == first_pos[3]
    assert second_extra[3] == first_extra[3]
    assert second_trail[3] == first_trail[3]
    assert second_pos[2] == 1
    assert second_extra[2] == 1
    assert second_trail[2] == 3
    assert second_pos[4][:4].tolist() == pytest.approx([9.1, 9.2, 9.3, 9.4])
    assert second_extra[4][:4].tolist() == pytest.approx([8.1, 8.2, 8.3, 8.4])
    assert second_trail[4][:9].tolist() == pytest.approx([7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9])
    assert second_pos[4][4:12].tolist() == pytest.approx([0.0] * 8)
    assert second_extra[4][4:12].tolist() == pytest.approx([0.0] * 8)
    assert second_trail[4][9:27].tolist() == pytest.approx([0.0] * 18)
