"""The wake loop's per-bubble reject in ``bubble.frag`` (Current_Plan.md item 8b, Bubble GPU optimisation) changes no
pixel: real-GL frames of many heroes with ripple wakes and ghost rings (long and short trails, trails far from their
heads, popping and faint bubbles, weak and zero-strength samples, the ripple cap reached, at the card's edges and at the
wide and tall shapes) drawn by the production host with the shader as it ships and with the reject's ``continue``
removed are byte-identical. Control: the reject made too tight (the reach of the newest sample's ripple instead of the
oldest's) must change pixels, so the comparison can see a reject that cuts a ripple."""

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

_WAKE_REJECT = "                || any(greaterThan(wake_frag_lo, wake_hi + wake_reach))) continue;\n"
_WAKE_REACH = "            float wake_reach = min(brad * 8.0 * trail_strength, max_ripple_radius);\n"
_LINES = (_WAKE_REJECT, _WAKE_REACH)


def _without(line: str):
    return lambda text: text.replace(line, line.replace(" continue;", " {}"))


def _heroes(count: int):
    """``count`` heroes over the card and past its edges, each with a three-sample trail (tail, middle, head) of a
    length, direction and strength of its own: some far from their heads, some faint, some with no strength."""
    positions, extras, trails = [], [], []
    for i in range(count):
        x = ((i * 37) % 101) / 100.0 * 1.1 - 0.05
        y = ((i * 53) % 97) / 96.0 * 1.1 - 0.05
        radius = (0.004, 0.012, 0.03, 0.06, 0.11)[i % 5]
        alpha = (1.0, 0.95, 0.6, 1.0, 0.3)[i % 5]
        positions += [x, y, radius, alpha]
        extras += [0.6 + 0.1 * (i % 4), 0.0, 0.08 * ((i % 3) - 1), 0.05 * ((i % 5) - 2)]
        length = (0.02, 0.08, 0.2, 0.45)[i % 4]
        dx, dy = length * (((i * 7) % 11) / 5.0 - 1.0), length * (((i * 5) % 13) / 6.0 - 1.0)
        strength = (1.0, 0.6, 0.25, 0.05, 0.0015, 0.0)[i % 6]
        for step in range(3):
            t = step / 2.0
            trails += [x - dx * (1.0 - t), y - dy * (1.0 - t), strength * (0.45 + 0.55 * t)]
    return tuple(positions), tuple(extras), tuple(trails)


def _snapshot(width: int, height: int, *, count: int, world_scale: float = 1.0, trail_strength: float = 1.5):
    positions, extras, trails = _heroes(count)
    words = [0, 0, 0, 0]
    for i in range(0, count, 3):                  # every third hero big: the coverage layer is exercised
        words[i >> 5] |= 1 << (i & 31)
    parameters = freeze_render_fields({
        "bubble_trail_strength": trail_strength, "bubble_tail_opacity": 0.85, "bubble_ghosting_enabled": True,
        "bubble_ghost_alpha": 1.0, "bubble_ghost_decay": 0.4, "bubble_gradient_direction": "top",
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
        mode_state=BubbleFrame(positions=positions, extras=extras, trails=trails, bubble_count=count,
                               big_class_bits=tuple(words), source_timestamp=1.0,
                               simulation_timestamp=1.0, parameters=parameters, world_scale=world_scale),
    )
    return compose_visualizer_render_snapshot(logical, _presentation(width, height), logical_revision=1)


#: (width, height, heroes, world scale, trail strength): the canonical card, wide, tall, a zoomed card, a weak wake,
#: and a ghost without a wake (trail strength 0: the wake loop does not run, so every ghost bit stays set).
_CASES = ((420, 280, 44, 1.0, 1.5), (1260, 420, 72, 1.0, 1.5), (420, 1260, 72, 1.0, 1.0), (630, 420, 72, 3.0, 1.5),
          (420, 280, 110, 1.0, 0.3), (420, 280, 72, 1.0, 0.0))
_WAKE_CASES = 5


def _frames(render, monkeypatch, host_reset, shader_edit):
    source = bubble_impl.load_fragment_shader("bubble")
    for line in _LINES:
        assert source.count(line) == 1, f"bubble.frag's reject line is not found exactly once: {line.strip()}"
    edited = shader_edit(source)
    monkeypatch.setattr(bubble_impl, "load_fragment_shader",
                        lambda name, _real=bubble_impl.load_fragment_shader: edited if name == "bubble" else _real(name))
    host_reset()
    try:
        return [render(_snapshot(w, h, count=n, world_scale=s, trail_strength=t), w, h) for w, h, n, s, t in _CASES]
    finally:
        monkeypatch.undo()
        host_reset()


@pytest.fixture
def _host_reset(_real_gl):  # noqa: F811
    _gl, render = _real_gl
    return render, render.host.release_resources


@pytest.mark.qt
def test_wake_and_ghost_rejects_change_no_pixel(_host_reset, monkeypatch):
    render, reset = _host_reset
    shipped = _frames(render, monkeypatch, reset, lambda text: text)
    without = _frames(render, monkeypatch, reset, lambda text: _without(_WAKE_REJECT)(text))
    assert all(any(frame) for frame in shipped)
    assert [i for i, (a, b) in enumerate(zip(shipped, without)) if a != b] == []
    # The wakes and the ghosts are drawn (the frames without each differ), so the comparison above covers them.
    no_wake = _frames(render, monkeypatch, reset,
                      lambda text: text.replace("    if (u_trail_strength > 0.001 && u_tail_opacity > 0.001) {\n",
                                                "    if (false) {\n"))
    assert all(a != b for a, b in zip(shipped[:_WAKE_CASES], no_wake[:_WAKE_CASES]))
    no_ghost = _frames(render, monkeypatch, reset,
                       lambda text: text.replace("    if (u_ghost_alpha > 0.001) {\n", "    if (false) {\n"))
    assert all(a != b for a, b in zip(shipped, no_ghost))


@pytest.mark.qt
def test_a_too_tight_wake_reject_is_seen(_host_reset, monkeypatch):
    render, reset = _host_reset
    shipped = _frames(render, monkeypatch, reset, lambda text: text)
    # Control: the reach of the newest sample's ripple (2.9 radii) cuts the older samples' wider ripples.
    tight = _frames(render, monkeypatch, reset,
                    lambda text: text.replace(_WAKE_REACH, _WAKE_REACH.replace("8.0", "2.9")))
    assert all(a != b for a, b in zip(shipped[:_WAKE_CASES], tight[:_WAKE_CASES]))
