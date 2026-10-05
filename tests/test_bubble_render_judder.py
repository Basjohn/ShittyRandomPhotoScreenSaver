"""Bubble judder (operator 2026-10-04): a bubble caught between breathing states vibrated 1-2 px.

The drawn radius read a size gate and render loudness that flipped between ~0 and ~1 frame to frame on energy
noise. They now rise at once and fall over ``RENDER_SIZE_RELEASE_S``; the simulation keeps the raw values. The
negative control is the same replay with an instant release (the old behaviour)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.qt


def _judder_steps(monkeypatch, release_s: float) -> int:
    import widgets.spotify_visualizer.bubble_simulation as simulation
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from tools.visualizer_replay.bubble_judder import analyse
    from tools.visualizer_replay.driver import load_clips

    monkeypatch.setattr(simulation, "RENDER_SIZE_RELEASE_S", release_s)
    stats = analyse(load_clips()["broadband_noise"], px_per_unit=300.0, min_px=0.5,
                    settings=frozen_visualizer_settings)
    return stats["radius_steps"]


def test_drawn_radius_no_longer_vibrates_on_energy_noise(qt_app, monkeypatch):
    from widgets.spotify_visualizer.bubble_simulation import RENDER_SIZE_RELEASE_S

    fixed = _judder_steps(monkeypatch, RENDER_SIZE_RELEASE_S)
    raw = _judder_steps(monkeypatch, 1e-6)
    assert raw > 0, "negative control: the instant release must reproduce the judder"
    assert fixed <= 0.6 * raw, (fixed, raw)


def _tiny_assist_series(monkeypatch, targets_px, *, assist_px: float):
    import widgets.spotify_visualizer.bubble_simulation as simulation

    monkeypatch.setattr(simulation, "TINY_BREATH_ASSIST_PX", assist_px)
    sim = simulation.BubbleSimulation()
    sim._apply_viewport_domain((420.0, 300.0))
    bubble = simulation.BubbleState(
        radius=3.0 / 300.0,
        pulse_energy=0.50,
    )
    return [
        sim._apply_tiny_breath_assist(bubble, target_px / 300.0) * 300.0
        for target_px in targets_px
    ]


def test_tiny_breath_assist_has_an_exact_negative_control(qt_app, monkeypatch):
    """The focused operator command must prove the new seam changes output."""
    targets = [4.0, 5.0, 6.0, 5.4, 6.4, 7.4]
    disabled = _tiny_assist_series(monkeypatch, targets, assist_px=0.0)
    enabled = _tiny_assist_series(monkeypatch, targets, assist_px=1.0)

    assert disabled == pytest.approx(targets)
    assert enabled == pytest.approx([4.0, 5.0, 7.0, 6.4, 6.4, 7.4])
    assert enabled != pytest.approx(disabled)


def test_tiny_breath_assist_does_not_touch_pulse_endpoints_or_strong_edges(qt_app, monkeypatch):
    import widgets.spotify_visualizer.bubble_simulation as simulation

    monkeypatch.setattr(simulation, "TINY_BREATH_ASSIST_PX", 1.0)
    sim = simulation.BubbleSimulation()
    sim._apply_viewport_domain((420.0, 300.0))

    for pulse in (0.05, 0.95):
        bubble = simulation.BubbleState(radius=3.0 / 300.0, pulse_energy=pulse)
        outputs = [
            sim._apply_tiny_breath_assist(bubble, target_px / 300.0) * 300.0
            for target_px in (4.0, 5.0, 6.0)
        ]
        assert outputs == pytest.approx([4.0, 5.0, 6.0])

    bubble = simulation.BubbleState(radius=3.0 / 300.0, pulse_energy=0.50)
    strong = [
        sim._apply_tiny_breath_assist(bubble, target_px / 300.0) * 300.0
        for target_px in (4.0, 7.0, 8.0)
    ]
    assert strong == pytest.approx([4.0, 7.0, 8.0])




def test_tiny_breath_assist_returns_raw_authority_on_a_target_plateau(qt_app, monkeypatch):
    outputs = _tiny_assist_series(
        monkeypatch,
        [4.0, 5.0, 6.0, 6.0],
        assist_px=1.0,
    )
    assert outputs == pytest.approx([4.0, 5.0, 7.0, 6.0])

def test_tiny_breath_assist_never_strays_more_than_one_physical_pixel(qt_app, monkeypatch):
    """A suppressed reversal may reshape one pixel, never bank hidden size debt."""
    import widgets.spotify_visualizer.bubble_simulation as simulation

    monkeypatch.setattr(simulation, "TINY_BREATH_ASSIST_PX", 1.0)
    sim = simulation.BubbleSimulation()
    sim._apply_viewport_domain((420.0, 300.0))
    bubble = simulation.BubbleState(radius=3.0 / 300.0, pulse_energy=0.50)

    targets = [4.0, 5.0, 6.0, 4.2, 4.1, 5.8, 5.7, 6.6]
    outputs = [
        sim._apply_tiny_breath_assist(bubble, target_px / 300.0) * 300.0
        for target_px in targets
    ]

    assert all(abs(output - target) <= 1.000001 for output, target in zip(outputs, targets))


def test_tiny_breath_assist_does_not_manufacture_dot_outline_crossings(qt_app, monkeypatch):
    import widgets.spotify_visualizer.bubble_simulation as simulation

    monkeypatch.setattr(simulation, "TINY_BREATH_ASSIST_PX", 1.0)

    below = simulation.BubbleSimulation()
    below._apply_viewport_domain((420.0, 300.0))
    below_bubble = simulation.BubbleState(radius=2.0 / 300.0, pulse_energy=0.50)
    below_outputs = [
        below._apply_tiny_breath_assist(below_bubble, target_px / 300.0) * 300.0
        for target_px in (2.4, 2.9, 3.8)
    ]
    assert below_outputs[-1] == pytest.approx(3.999)
    assert below_outputs[-1] != pytest.approx(3.8)

    above = simulation.BubbleSimulation()
    above._apply_viewport_domain((420.0, 300.0))
    above_bubble = simulation.BubbleState(radius=2.0 / 300.0, pulse_energy=0.50)
    above_outputs = [
        above._apply_tiny_breath_assist(above_bubble, target_px / 300.0) * 300.0
        for target_px in (5.6, 5.1, 4.2)
    ]
    assert above_outputs[-1] == pytest.approx(4.0)
    assert above_outputs[-1] != pytest.approx(4.2)

def test_tiny_breath_assist_is_physically_bounded_to_tiny_render_radii(qt_app, monkeypatch):
    import widgets.spotify_visualizer.bubble_simulation as simulation

    monkeypatch.setattr(simulation, "TINY_BREATH_ASSIST_PX", 1.0)
    sim = simulation.BubbleSimulation()
    sim._apply_viewport_domain((420.0, 300.0))
    bubble = simulation.BubbleState(radius=9.0 / 300.0, pulse_energy=0.50)

    outputs = [
        sim._apply_tiny_breath_assist(bubble, target_px / 300.0) * 300.0
        for target_px in (9.0, 10.0, 11.0)
    ]
    assert outputs == pytest.approx([9.0, 10.0, 11.0])
