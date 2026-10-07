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


def test_small_radius_snapshot_preserves_every_authored_target(qt_app, monkeypatch):
    """No temporal small-radius filter may rewrite reversals or amplitude."""
    from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation, BubbleState

    simulation = BubbleSimulation()
    bubble = BubbleState(radius=0.01, pulse_energy=0.5)
    simulation._bubbles = [bubble]
    # TEST INPUT, NOT A DEFAULT GOLDEN: intentional monotonic/reversing targets
    # straddle the former assist's thresholds without changing audio authority.
    targets = [4.0, 5.0, 6.0, 5.4, 6.4, 7.4, 7.4, 4.2, 8.5]
    for target in targets:
        factor = target / 300.0 / bubble.radius
        monkeypatch.setattr(simulation, "_small_render_pulse_factor", lambda *args, **kwargs: factor)
        positions, _extras, _trails = simulation.snapshot()
        assert positions[2] * 300.0 == pytest.approx(target)
        assert bubble.pulse_energy == 0.5
