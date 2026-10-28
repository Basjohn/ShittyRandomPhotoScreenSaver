"""Extruded Bubble collisions on real music: how long bounce contacts last and how fused pairs sit.

A bounce should part the pair quickly (short contacts); a lasting contact is a pair grinding along each other. A fuse
should draw the members into a visible merge (surface separation ratio well below 1) and hold it steadily as they
breathe; a ratio near 1 is two bubbles stuck surface-to-surface.

    python -m tools.visualizer_replay.eb_collision_probe [--preset 1] [clip]
"""
from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "logs" / "visualizer_recordings"


def run(clip, params, collision):
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import (
        ExtrudedBubbleFrameRuntime, controls_from_parameters,
    )
    engine = ReplayBeatEngine(32)
    runtime = ExtrudedBubbleFrameRuntime(1)
    controls = controls_from_parameters({**params, "extruded_bubble_collision": list(collision)})
    simulation = runtime._simulation
    open_contacts: dict[tuple[int, int], float] = {}
    durations, ratios, slides, clusters = [], [], [], []
    previous_offsets = {}
    for frame in clip.frames:
        engine.accept_feature_frame(frame)
        now = frame.timestamp_us / 1e6
        runtime.advance(onsets=engine.get_onset_events(runtime.onset_serial), now_ts=now, playing=bool(frame.playing),
                        identity=(1, 1, 1), source_identity=(1, 1),
                        body_bands=tuple(getattr(engine.get_extruded_bubble_body_bands(), n)
                                         for n in ("bass", "mid", "high")),
                        controls=controls)
        bubbles = {b.ident: b for b in simulation._bubbles}
        # Bounce contacts: from first touch until the pair parts.
        live = {pair for pair, response in simulation._contacts.items() if response == "bounce"}
        for pair in live - open_contacts.keys():
            open_contacts[pair] = now
        for pair in list(open_contacts):
            if pair not in live:
                durations.append(now - open_contacts.pop(pair))
        # Fused pairs: surface separation ratio, and how far the contact point slides per second on the members.
        clusters.append(len(simulation._clusters))
        for cluster in simulation._clusters.values():
            for left, right, _axis, _ratio in cluster.edges:
                a, b = bubbles.get(left), bubbles.get(right)
                if a is None or b is None:
                    continue
                distance = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
                ratio = distance / max(a.visual_radius + b.visual_radius, 1e-9)
                ratios.append(ratio)
                contact = tuple(pa + (pb - pa) * a.visual_radius / (a.visual_radius + b.visual_radius)
                                for pa, pb in zip((a.x, a.y, a.z), (b.x, b.y, b.z)))
                local = tuple(c - p for c, p in zip(contact, (a.x, a.y, a.z)))
                key = (left, right)
                if key in previous_offsets:
                    slides.append(math.dist(local, previous_offsets[key][0]) / max(now - previous_offsets[key][1], 1e-6)
                                  / max(a.visual_radius, 1e-9))
                previous_offsets[key] = (local, now)
    return durations, ratios, slides, clusters


def _q(values, cuts=(50, 90)):
    if not values:
        return "none"
    ordered = sorted(values)
    return " / ".join(f"{ordered[min(len(ordered) - 1, int(len(ordered) * c / 100))]:.3f}" for c in cuts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preset", type=int, default=1)
    parser.add_argument("clip", nargs="?", default="human_heavy1")
    args = parser.parse_args(argv)
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    params = dict(resolve_visualizer_activation_payload(
        {"mode": "extruded_bubble", "preset_extruded_bubble": args.preset - 1}, mode="extruded_bubble").resolved_config)
    clip = FeatureClip.from_jsonl_bytes(args.clip, (ROOT / f"{args.clip}.jsonl").read_bytes())
    durations, _r, _s, _c = run(clip, params, (0.0, 0.0, 1.0))
    print(f"bounce only: {len(durations)} contacts, duration p50/p90 {_q(durations)} s, "
          f"longer than 0.3 s: {sum(d > 0.3 for d in durations)}")
    _d, ratios, slides, clusters = run(clip, params, (1.0, 0.0, 0.0))
    print(f"fuse only: clusters mean {statistics.fmean(clusters):.1f}, surface ratio p50/p90 {_q(ratios)}, "
          f"contact slide p50/p90 {_q(slides)} radii/s")


if __name__ == "__main__":
    main()
