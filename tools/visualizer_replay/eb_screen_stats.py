"""Extruded Bubble on-screen composition: how many bubbles a preset shows at each on-screen size, against the lab.

The composition lab (``tools/labs/extruded_bubble_lab.py``), whose scenes came closest to the goal mocks, composes
each scene by on-screen radius: about 10 large (40-85 px), 26 mid (18-40), 60 small (8-18) and 150 tiny (2-7),
~40% of the large and mid fused into doublets/triplets, and two or three near, defocused giants at the edges (scaled
by each scene's ``mid_count`` / ``small_count``). This replays a real recording through the production simulation to
the given moments, projects every ordinary bubble through the production physical camera and reports the same bands,
so a preset's composition can be authored toward the lab's with measurements rather than by eye.

    python -m tools.visualizer_replay.eb_screen_stats --preset 1 2 3 [--at 30 45] [--clip ragdoll_quiet_intro_loud_end1]

Bead chains, wake fizz and particles are GPU-procedural and not counted. Offscreen statistics, not visual acceptance.
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BANDS = ((2.0, 7.0), (7.0, 18.0), (18.0, 40.0), (40.0, 85.0), (85.0, 1e9))
LAB = (150, 60, 26, 10, 3)        # the lab's counts per band at mid_count = small_count = 1 (giants: near edges)


def composition(state, size):
    """On-screen radius (px) of each visible ordinary bubble and whether it is fused, from one logical state."""
    import numpy as np
    from tools.visualizer_replay.extruded_bubble_world_probe import camera_space, frustum_candidates

    parameters = dict(state.parameters)
    values = np.asarray(state.bubbles, dtype=float).reshape(-1, 8)
    if not len(values):
        return []
    view, _eye, tan = camera_space(values[:, :3], parameters, size)
    visible = frustum_candidates(view, values[:, 3], tan) & (values[:, 4] > 0.5)
    depth = np.maximum(-view[:, 2], 0.05)
    pixels = values[:, 3] / (depth * 2.0 * tan[1] / size[1])
    return [(float(p), bool(c >= 0), float(d)) for p, c, d, v in zip(pixels, values[:, 7], depth, visible) if v]


def bands(rows):
    return [sum(1 for p, _c, _d in rows if low <= p < high) for low, high in BANDS]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preset", type=int, nargs="+", default=[1])
    parser.add_argument("--at", type=float, nargs="+", default=[30.0, 45.0])
    parser.add_argument("--clip", default="ragdoll_quiet_intro_loud_end1")
    parser.add_argument("--size", default="1672x941")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON", help="override a setting")
    args = parser.parse_args(argv)
    import json
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools.visualizer_replay.driver import replay_clip
    from tools.visualizer_replay.extruded_bubble_forensics import load_clip

    size = tuple(int(v) for v in args.size.split("x"))
    path = ROOT / "logs" / "visualizer_recordings" / f"{args.clip}.jsonl"
    print(f"bands (px radius)     {'  '.join(f'{int(a)}-{int(b) if b < 1e8 else "+":>3}' for a, b in BANDS)}   fused  "
          f"lab {LAB}")
    for preset in args.preset:
        settings = dict(resolve_visualizer_activation_payload(
            {"mode": "extruded_bubble", "preset_extruded_bubble": preset - 1}, mode="extruded_bubble").resolved_config)
        for item in args.set:
            key, value = item.split("=", 1)
            settings[key if key.startswith("extruded_bubble_") else "extruded_bubble_" + key] = json.loads(value)
        for at in args.at:
            clip = load_clip(path, at)
            index = len(clip.frames) - 1
            state = replay_clip(clip, "extruded_bubble", settings=settings,
                                snapshots_at=[index])["snapshots"][index].logical.mode_state
            rows = composition(state, size)
            large = [r for r in rows if r[0] >= 18.0]
            fused = sum(1 for r in large if r[1]) / max(1, len(large))
            counts = bands(rows)
            print(f"preset {preset} at {at:4.0f}s   " + "  ".join(f"{c:6d}" for c in counts)
                  + f"   {fused:5.0%}   total {len(state.bubbles) // 8}, visible {len(rows)}, median depth "
                  + f"{statistics.median([r[2] for r in rows]) if rows else math.nan:.1f}", flush=True)


if __name__ == "__main__":
    main()
