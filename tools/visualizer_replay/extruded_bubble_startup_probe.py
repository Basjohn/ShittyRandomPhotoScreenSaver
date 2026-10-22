#!/usr/bin/env python3
"""Trace EB logical body start/release without Qt, OpenGL, EB Lab, or audio files.

This diagnostic imports the real simulation and the authored P1/P7 controls,
then compares source/start scenarios on the sole simulation tick. It does not
change production controls or accept any visual behavior.

    py -3.14 tools/visualizer_replay/extruded_bubble_startup_probe.py
    py -3.14 tools/visualizer_replay/extruded_bubble_startup_probe.py --json
    py -3.14 tools/visualizer_replay/extruded_bubble_startup_probe.py --gate

--gate was RED on the original 2026-10-20 source. A green candidate must
not be described as live visual acceptance, musical quality or judder repair.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
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


def controls_from_authored_preset(mod, slot):
    from core.settings.default_settings import DEFAULT_SETTINGS
    from core.settings.visualizer_mode_settings import require_mode_settings
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import controls_from_parameters
    preset = ROOT / "presets/visualizer_modes/extruded_bubble" / (
        "preset_1_sunlit_surface.json" if slot == 1 else "preset_7_ember_drift.json")
    values = json.loads(preset.read_text(encoding="utf-8"))["snapshot"]["widgets"]["spotify_visualizer"]
    defaults = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    parameters = {c.key: c.admit(values.get(c.key, defaults[c.key]), defaults[c.key])
                  for c in require_mode_settings("extruded_bubble").controls}
    return controls_from_parameters(parameters)


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable summaries and selected 10Hz samples")
    parser.add_argument("--gate", action="store_true", help="Fail on genuine source-start and source-ramp overshoot")
    args = parser.parse_args()
    mod = simulation_module()
    output = {"source": "production simulation + authored P1/P7 controls",
              "input": "synthetic fixed bands; quadratic playback ramp plus source-owned ramp metadata mirrors beat_engine",
              "scenarios": {}}
    for slot in (1, 7):
        controls = controls_from_authored_preset(mod, slot)
        for scenario in ("already_hot", "play_ramp", "play_ramp_untagged", "quiet_then_hot"):
            for seeded in (False, True):
                name = f"P{slot}/{scenario}/" + ("seed_references_only" if seeded else "current_source")
                rows = trace(mod, controls, scenario, reference_seed=seeded)
                output["scenarios"][name] = summary(rows)
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print("EB logical activation probe (synthetic music, not visual/native acceptance)")
        for name, item in output["scenarios"].items():
            big, small = item["big"], item["small"]
            print(f"{name:43s}  large peak/final {big['peak']:.3f}/{big['final']:.3f}"
                  f" ({big['peak_to_final']:.2f}x), small {small['peak']:.3f}/{small['final']:.3f}")
    if args.gate:
        failing = [(name, lane, value[lane]["peak_to_final"])
                   for name, value in output["scenarios"].items()
                   if name.endswith("/current_source") and
                   any(key in name for key in ("/already_hot/", "/play_ramp/", "/play_ramp_untagged/"))
                   for lane in (("big",) if "/play_ramp_untagged/" in name else ("big", "small"))
                   if value[lane]["peak_to_final"] > 1.30]
        if failing:
            print("GATE RED: held-input startup overshoot " + str(failing), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
