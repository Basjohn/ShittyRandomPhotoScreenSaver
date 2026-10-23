#!/usr/bin/env python3
"""EB-R33: non-rendering quiet/loud Range audit using the production simulation.

No new DSP, Qt, environment variables, or preset rewrites. These are *controlled*
constant-band examples, not a recorded song, renderer result or visual acceptance.

    py -3.14 tools/visualizer_replay/extruded_bubble_range_energy_audit.py
    py -3.14 tools/visualizer_replay/extruded_bubble_range_energy_audit.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.visualizer_replay.eb_simulation_support import simulation_module

# Purposefully different handles, so a missing low or high branch is conspicuous.
# Stream Speed in snapshots is PHYSICAL units; other rate controls are normalized.
_AUDIT = dict(large_count=(4., 16.), mid_count=(12., 48.), stream_speed=(.2, .8),
              drift=(.2, .8), emission=(.2, .8), breathing=(.2, .8), small_pulse=(.2, .8))


def controlled_probe(*, playing: bool, bands: tuple[float, float, float], frames: int = 900) -> dict:
    mod = simulation_module()
    controls = mod.ExtrudedBubbleControls(**_AUDIT, collision_scope="off", sustained=0.4, idle=0.5)
    sim = mod.ExtrudedBubbleSimulation(54)
    for _ in range(frames):
        snapshot = sim.advance(mod.MusicInput(1 / 90, playing, 1.0 if playing else 0.0, (), bands), controls)
    strength = lambda pair, drive: pair[0] + (pair[1] - pair[0]) * drive
    chains = strength((2.0, 8.0), snapshot.level)  # actual renderer Bead Chains Range read
    return {
        "playing": playing, "bands": list(bands), "level": round(snapshot.level, 5),
        "population_drive": round(sim._population_drive, 5),
        "large_count_target": round(strength(_AUDIT["large_count"], sim._population_drive), 5),
        "small_count_target": round(strength(_AUDIT["mid_count"], sim._population_drive), 5),
        "bead_chain_target_before_detail_tier": round(chains, 5),
        "stream_speed_fraction_before_world_units": round(snapshot.stream_speed / mod.WORLD_UNIT, 5),
        "drift": round(snapshot.drift, 5), "particles_emission": round(snapshot.emission, 5),
        "large_body_driver": round(sim._body_big_envelope, 5),
        "small_body_driver": round(sim._body_small_envelope, 5),
        "large_breath_radius_multiplier": round(mod._reaction_scale(_AUDIT["breathing"], sim._body_big_envelope, *mod._LARGE_REACTION), 5),
        "small_breath_radius_multiplier": round(mod._reaction_scale(_AUDIT["small_pulse"], sim._body_small_envelope, *mod._SMALL_REACTION), 5),
        "ray_driver": round(snapshot.rays, 5),
        "ray_range_output_fraction": round((.2 + (.8 - .2) * snapshot.rays) * (.03 + .97 * snapshot.rays), 5),
    }


def report() -> dict:
    return {"limits": {"test_handles_normalized": [.2, .8], "counts": {"large": [4, 16], "small": [12, 48], "chains": [2, 8]}},
            "controlled_inputs": {
                "silence": controlled_probe(playing=False, bands=(0., 0., 0.)),
                "nearly_silent": controlled_probe(playing=True, bands=(.02, .02, .02)),
                "moderate": controlled_probe(playing=True, bands=(.25, .25, .25)),
                "full_bands": controlled_probe(playing=True, bands=(1., 1., 1.)),
            }}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = report()
    if args.json:
        print(json.dumps(data, indent=2))
        return
    print("EB range audit: synthetic settled inputs only, NO visual/recorded acceptance")
    for name, item in data["controlled_inputs"].items():
        print(name, "=>", ", ".join(f"{key}={val}" for key, val in item.items() if key not in ("playing", "bands")))
    print("\nNine Range widgets: Ray Strength, Large Bubbles, Small Bubbles, Bead Chains, "
          "Stream Speed, Drift, Breathing, Small Bubble Pulse, Particles.")
    print("Warning: audible quiet endpoints are not generally literal zero-band/silence outputs. "
          "See Current_Plan.md EB-R33 for consumers and caveats.")


if __name__ == "__main__":
    main()
