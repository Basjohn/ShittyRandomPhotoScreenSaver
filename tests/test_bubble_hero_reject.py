"""The hero loop's square reject in ``bubble.frag`` (Current_Plan.md item 8b, Bubble GPU optimisation) changes no
pixel: real-GL frames of many heroes (big and small, tiny dots, popping, overlapping, at the card's edges, with the
capacity zoom's firmer outline) drawn by the production host with the shader as it ships and with the reject line
removed are byte-identical. Control: the same reject made too tight (r + 1 px, inside the outline's outer edge) must
change pixels, so the comparison can see a reject that cuts a hero."""

from __future__ import annotations

import pytest

from rendering.quick.visualizer.implementations import bubble as bubble_impl
from tests.test_bubble_aspect_pixels import _presentation, _real_gl  # noqa: F401  (the fixture)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)

_REJECT_PREFIX = "        if (abs(delta.x) > brad + 4.0 * px || abs(delta.y) > brad + 4.0 * px) continue;\n"


def _heroes(count: int):
    """``count`` heroes over the card and past its edges: radii from tiny dots to large, some popping."""
    positions, extras = [], []
    for i in range(count):
        x = ((i * 37) % 101) / 100.0 * 1.1 - 0.05
        y = ((i * 53) % 97) / 96.0 * 1.1 - 0.05
        radius = (0.004, 0.012, 0.03, 0.06, 0.11)[i % 5]
        alpha = (1.0, 0.95, 0.6, 1.0, 0.3)[i % 5]
        positions += [x, y, radius, alpha]
        extras += [0.6 + 0.1 * (i % 4), 0.0, 0.08 * ((i % 3) - 1), 0.05 * ((i % 5) - 2)]
    return tuple(positions), tuple(extras)


def _snapshot(width: int, height: int, *, count: int, world_scale: float = 1.0):
    positions, extras = _heroes(count)
    words = [0, 0, 0, 0]
    for i in range(0, count, 3):                  # every third hero big: the coverage layer is exercised
        words[i >> 5] |= 1 << (i & 31)
    parameters = freeze_render_fields({
        "bubble_trail_strength": 0.0, "bubble_tail_opacity": 0.0, "bubble_ghosting_enabled": False,
        "bubble_ghost_alpha": 0.0, "bubble_ghost_decay": 0.0, "bubble_gradient_direction": "top",
        "bubble_specular_direction": "top_left", "bubble_gradient_light": (40, 60, 120, 255),
        "bubble_gradient_dark": (5, 10, 30, 255), "bubble_outline_color": (230, 240, 255, 255),
        "bubble_specular_color": (255, 255, 255, 230), "bubble_pop_color": (255, 120, 80, 255),
        "rainbow_enabled": False,
    })
    logical = VisualizerLogicalFrame(
        runtime_generation=1, engine_generation=2, activation_id=3, source_generation=2, source_activation_id=3,
        mode_id="bubble", playing=True, logical_timestamp=1.0, source_timestamp=1.0, changed=True,
        present_frame=True, mode_reveal_ready=True,
        common=VisualizerCommonState(bars=(), bar_count=0, energy=VisualizerEnergyState()),
        mode_state=BubbleFrame(positions=positions, extras=extras, trails=(), bubble_count=count,
                               big_class_bits=tuple(words), source_timestamp=1.0,
                               simulation_timestamp=1.0, parameters=parameters, world_scale=world_scale),
    )
    return compose_visualizer_render_snapshot(logical, _presentation(width, height), logical_revision=1)


_CASES = ((420, 280, 44, 1.0), (1260, 420, 72, 1.0), (420, 1260, 72, 1.0), (630, 420, 72, 3.0))


def _frames(render, monkeypatch, host_reset, shader_edit):
    source = bubble_impl.load_fragment_shader("bubble")
    assert source.count(_REJECT_PREFIX) == 1, "bubble.frag's hero reject line is not found exactly once"
    edited = shader_edit(source)
    monkeypatch.setattr(bubble_impl, "load_fragment_shader",
                        lambda name, _real=bubble_impl.load_fragment_shader: edited if name == "bubble" else _real(name))
    host_reset()
    try:
        return [render(_snapshot(w, h, count=n, world_scale=s), w, h) for w, h, n, s in _CASES]
    finally:
        monkeypatch.undo()
        host_reset()


@pytest.fixture
def _host_reset(_real_gl):  # noqa: F811
    _gl, render = _real_gl
    return render, render.host.release_resources


def test_hero_reject_changes_no_pixel(_host_reset, monkeypatch):
    render, reset = _host_reset
    shipped = _frames(render, monkeypatch, reset, lambda text: text)
    without = _frames(render, monkeypatch, reset, lambda text: text.replace(_REJECT_PREFIX, ""))
    assert all(any(frame) for frame in shipped)
    assert [i for i, (a, b) in enumerate(zip(shipped, without)) if a != b] == []
    # Control: a reject inside the outline's outer edge cuts the heroes' rings, and the comparison sees it.
    tight = _frames(render, monkeypatch, reset,
                    lambda text: text.replace(_REJECT_PREFIX, _REJECT_PREFIX.replace("4.0 * px", "1.0 * px")))
    assert all(a != b for a, b in zip(shipped, tight))
