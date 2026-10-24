"""Shared Qt-free EB simulation and synthetic startup fixtures for tests/audits.

No one-off command-line probe: the startup-overshoot regression is asserted by
normal pytest tests/test_extruded_bubble_startup_and_sizes.py and the dedicated
recovery tests. These fixtures are NOT native/audio/visual acceptance.
"""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FREQUENCY = 60
TOTAL_STEPS = 300
HOT_BANDS = (0.7, 0.5, 0.3)  # controlled illustration, NOT a recorded track


def simulation_module():
    """Import only the production geometry/simulation; avoid Qt-heavy package initializer."""
    for name, location in (("widgets", ROOT / "widgets"),
                           ("widgets.spotify_visualizer", ROOT / "widgets/spotify_visualizer")):
        if name not in sys.modules:
            package = types.ModuleType(name)
            package.__path__ = [str(location)]
            sys.modules[name] = package
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module("widgets.spotify_visualizer.extruded_bubble_simulation")


def synthetic_controls(mod, profile: str):
    """Fixed, test-owned input profiles; NEVER read shipped presets or settings.

    These two cases cover different respiratory intensities and population sizes.
    They are not aliases for operator Preset 1/7 and never claim to pin art.
    """
    profiles = {
        "gentle": dict(large_count=(3., 3.), mid_count=(4., 4.),
                       breathing=(.0355, .18), small_pulse=(.001, .10),
                       sustained=.6, smoothing=.5),
        "strong": dict(large_count=(5., 5.), mid_count=(8., 8.),
                       breathing=(.32, .45), small_pulse=(.025, .42),
                       sustained=.7, smoothing=.35),
    }
    return mod.ExtrudedBubbleControls(**profiles[profile],
                                      collision_scope="off",
                                      stream_speed=(0., 0.), drift=(0., 0.), sway=0.)


def input_bands(scenario, i):
    if scenario == "already_hot":
        return HOT_BANDS
    if scenario in ("play_ramp", "play_ramp_untagged"):
        # beat_engine._get_play_ramp_factor: 1s quadratic ramp.
        factor = min(i / FREQUENCY, 1.) ** 2
        return tuple(v * factor for v in HOT_BANDS)
    if scenario == "quiet_then_hot":
        return (0., 0., 0.) if i < FREQUENCY else HOT_BANDS
    raise ValueError(scenario)


def trace(mod, controls, scenario, *, reference_seed=False):
    sim = mod.ExtrudedBubbleSimulation(0x5EB0)
    traces = []
    for i in range(TOTAL_STEPS):
        bands = input_bands(scenario, i)
        # The *existing* engine quadratic play-ramp is authoritatively tagged by
        # source metadata, not inferred from the slope of real recorded music.
        source_ramping = scenario == "play_ramp" and i < FREQUENCY
        if i == 0 and reference_seed:
            bass, mid, high = bands
            sim._big_body_reference = mod._soft_top(bass + 0.28 * mid + 0.10 * high)
            sim._small_body_reference = mod._soft_top(0.70 * mid + 0.35 * high)
        snap = sim.advance(mod.MusicInput(0. if i == 0 else 1 / FREQUENCY,
                                          True, 1., (), bands, source_ramping), controls)
        # Actual population radii are identical in each class for a common envelope;
        # snapshot swell is current_radius / nominal_radius minus one.
        first_large = next((1 + snap.bubbles[j+5] for j in range(0,len(snap.bubbles),8)
                            if sim._bubbles[j//8].large), None)
        first_small = next((1 + snap.bubbles[j+5] for j in range(0,len(snap.bubbles),8)
                            if not sim._bubbles[j//8].large), None)
        traces.append({
            "t": i / FREQUENCY, "band_bass": bands[0],
            "big_reference": sim._big_body_reference,
            "big_envelope": sim._body_big_envelope,
            "small_reference": sim._small_body_reference,
            "small_envelope": sim._body_small_envelope,
            "big_radius_ratio": first_large,
            "small_radius_ratio": first_small,
        })
    return traces


def summary(rows):
    def collect(name):
        values = [float(row[name]) for row in rows if row[name] is not None]
        def at(index):
            value = rows[index][name]
            return round(float(value), 5) if value is not None else None
        return {"peak": round(max(values), 5),
                "at_1s": at(FREQUENCY),
                "at_2s": at(2*FREQUENCY),
                "final": round(values[-1], 5),
                "peak_to_final": round(max(values) / values[-1], 5) if values[-1] else None}
    return {"big": collect("big_radius_ratio"),
            "small": collect("small_radius_ratio"),
            "first": {name: round(rows[0][name], 5)
                      for name in ("big_reference", "big_envelope", "small_reference", "small_envelope")}}

