"""Fixed reviewed lower bounds; calibration never runs inside the assertions."""
from __future__ import annotations

import json
import math
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[2] / "tests/goldens/visualizer_replay/reactivity_floor.json"


def check_floors(result, case, reference=None):
    if reference is None:
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    bounds = reference["cases"][case]
    measured = {**result["metrics"], **result["mode_metrics"]}
    for key, floor in bounds["minimums"].items():
        value = measured[key]
        assert math.isfinite(value) and value >= floor, f"{case}: {key}={value} below floor {floor}"
    for key, ceiling in bounds["maximums"].items():
        value = measured[key]
        assert math.isfinite(value) and value <= ceiling, f"{case}: {key}={value} above quiet ceiling {ceiling}"


def calibrate(results):
    """Create a review candidate only; caller must explicitly choose a new file."""
    cases = {}
    for case, result in results.items():
        fixture, mode = case.split("__")
        metrics = {**result["metrics"], **result["mode_metrics"]}
        minimums = {}
        maximums = {}
        if fixture == "silence":
            # Idle Bubble/DevCurve motion is authored. Only audio-response lanes
            # must be quiet; never outlaw idle animation with a motion ceiling.
            maximums = {key: 1e-6 for key in ("bar_peak", "waveform_peak", "onset_count")}
        elif fixture != "mode_visibility_switch":
            keys = ["bar_peak", "bar_flux", "integrated_bar_energy", "attack_slope_per_s",
                    "waveform_rms", "output_flux"]
            if mode == "bubble":
                keys += ["bubble_radius_excursion", "bubble_particle_peak"]
            for key in keys:
                if metrics[key] > 1e-7:
                    minimums[key] = metrics[key] * 0.5
            # A sustained fixture may settle immediately (treble/Sine preset 0
            # is constant). Pulsed fixtures separately guard mode output motion.
            if fixture.startswith("beats_") and not minimums.get("output_flux", 0):
                raise ValueError(f"no measurable mode response for {case}")
        cases[case] = {
            "reference_metrics": result["metrics"],
            "reference_mode_metrics": result["mode_metrics"],
            "minimums": minimums, "maximums": maximums,
        }
    return {"description": "Current authored preset zero; 50% response floors. Silence constrains audio lanes only.",
            "cases": cases}
