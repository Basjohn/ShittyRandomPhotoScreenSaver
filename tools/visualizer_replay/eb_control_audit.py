"""Extruded Bubble control audit on real music: does each reactive control's authored range reach what is shown?

For every reactive Range (quiet .. loud) and Slider, replay recorded songs through the production simulation
(``ExtrudedBubbleFrameRuntime`` driven by the replay BeatEngine, as ``extruded_bubble_traces``) and the renderer's own
drivers (``ray_strength``, ``ray_motion``, ``_procedural_fill``), then report the realized value in the song's quietest
and loudest fifths (by passage intensity). Cases per Range: the left (quiet) handle at its minimum, the preset's own
values, the left handle raised to the right one (a flat range: quiet should then match loud), and the right handle at
its minimum. A working minimum shows a clearly lower quiet value than the preset's; a faithful range keeps quiet near
the left handle and loud near the right one.

    python -m tools.visualizer_replay.eb_control_audit [--preset 1] [clip ...]
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "logs" / "visualizer_recordings"
DEFAULT_CLIPS = ("human_heavy1", "1985_loud1", "nightsolong_acousticsoft1")


def _metrics():
    from rendering.gl_programs.extruded_bubble_scene import ray_motion, ray_strength
    from rendering.quick.visualizer.implementations.extruded_bubble import _procedural_fill
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import STREAM_SPEED_FULL
    from widgets.spotify_visualizer.extruded_bubble_simulation import BUBBLE_STRIDE, WORLD_UNIT

    def population(large):
        def count(params, snap, runtime):
            kinds = {b.ident: b.large for b in runtime._simulation._bubbles}
            return sum(1 for i in range(0, len(snap.bubbles), BUBBLE_STRIDE)
                       if snap.bubbles[i + 4] > 0.9 and kinds.get(int(snap.bubbles[i + 6])) == large)
        return count

    def breath(large):
        def mean(params, snap, runtime):
            kinds = {b.ident: b.large for b in runtime._simulation._bubbles}
            values = [snap.bubbles[i + 5] for i in range(0, len(snap.bubbles), BUBBLE_STRIDE)
                      if snap.bubbles[i + 4] > 0.9 and kinds.get(int(snap.bubbles[i + 6])) == large]
            return statistics.fmean(values) if values else float("nan")
        return mean

    # key -> (what is measured, per-frame metric)
    return {
        "extruded_bubble_rays": ("ray intensity", lambda p, s, r: ray_strength(p, s.rays)),
        "extruded_bubble_ray_flicker": ("flicker depth", lambda p, s, r: ray_motion(p, s.rays, s.sustain)[0]),
        "extruded_bubble_large_bubbles": ("live large", population(True)),
        "extruded_bubble_mid_bubbles": ("live small", population(False)),
        "extruded_bubble_bead_chains": ("chains", lambda p, s, r: _procedural_fill(p, s.level, s.emission)[0]),
        "extruded_bubble_stream_speed": ("speed (x full)", lambda p, s, r: s.stream_speed / (WORLD_UNIT * STREAM_SPEED_FULL)),
        "extruded_bubble_drift": ("drift", lambda p, s, r: s.drift),
        "extruded_bubble_breathing": ("large breath", breath(True)),
        "extruded_bubble_small_pulse": ("small breath", breath(False)),
        "extruded_bubble_sustained": ("sustain", lambda p, s, r: s.sustain),
        "extruded_bubble_particles": ("emission", lambda p, s, r: s.emission),
        "extruded_bubble_particle_glow_reactivity": ("glow multiplier",
                                                     lambda p, s, r: 1.0 + float(p["extruded_bubble_particle_glow_reactivity"])
                                                     * (0.5 * s.rays + 0.2 * s.flash)),
    }


def _replay(clip, params, metric):
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import (
        ExtrudedBubbleFrameRuntime, controls_from_parameters,
    )
    engine = ReplayBeatEngine(32)
    runtime = ExtrudedBubbleFrameRuntime(1)
    controls = controls_from_parameters(params)
    rows = []
    for frame in clip.frames:
        engine.accept_feature_frame(frame)
        now = frame.timestamp_us / 1e6
        onsets = engine.get_onset_events(runtime.onset_serial)
        snap = runtime.advance(onsets=onsets, now_ts=now, playing=bool(frame.playing),
                               intensity=engine.get_musical_intensity(), identity=(1, 1, 1), source_identity=(1, 1),
                               body_bands=tuple(getattr(engine.get_extruded_bubble_body_bands(), n)
                                                for n in ("bass", "mid", "high")),
                               controls=controls)
        rows.append((engine.get_musical_intensity(), metric(params, snap, runtime)))
    rows = [r for r in rows[len(rows) // 10:] if r[1] == r[1]]          # skip warm-up and empty frames
    rows.sort(key=lambda r: r[0])
    fifth = max(1, len(rows) // 5)
    return statistics.fmean(v for _i, v in rows[:fifth]), statistics.fmean(v for _i, v in rows[-fifth:])


def _cases(control, value):
    if isinstance(value, (list, tuple)):
        low, high = (float(v) for v in value)
        return (("left at min", [control.low, high]), ("preset", [low, high]),
                ("left = right", [high, high]), ("right at min", [low, control.low]))
    return (("min", control.low), ("preset", float(value)), ("max", control.high))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preset", type=int, default=1)
    parser.add_argument("--keys", nargs="*", help="only these controls (extruded_bubble_ prefix optional)")
    parser.add_argument("clips", nargs="*", default=list(DEFAULT_CLIPS))
    args = parser.parse_args(argv)
    from core.settings.visualizer_mode_settings import require_mode_settings
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    base = dict(resolve_visualizer_activation_payload(
        {"mode": "extruded_bubble", "preset_extruded_bubble": args.preset - 1}, mode="extruded_bubble").resolved_config)
    # The renderer's drivers also read the 3D Detail tier (resolved per display, not a setting): audit at High.
    base.setdefault("scene3d_detail", "High")
    wanted = {k if k.startswith("extruded_bubble_") else "extruded_bubble_" + k for k in (args.keys or ())}
    spec = require_mode_settings("extruded_bubble")
    clips = [FeatureClip.from_jsonl_bytes(n, (ROOT / f"{n}.jsonl").read_bytes()) for n in args.clips]
    for key, (label, metric) in _metrics().items():
        if wanted and key not in wanted:
            continue
        control = spec.control(key)
        print(f"\n{key}  ({label}; preset {base[key]})")
        for case, value in _cases(control, base[key]):
            params = {**base, key: value}
            if key == "extruded_bubble_ray_flicker" or key == "extruded_bubble_rays":
                params["extruded_bubble_rays_enabled"] = True
            cells = []
            for clip in clips:
                quiet, loud = _replay(clip, params, metric)
                cells.append(f"{clip.name[:14]:>14s} {quiet:7.3f} / {loud:7.3f}")
            print(f"  {case:13s} {str(value):22s} " + "   ".join(cells), flush=True)


if __name__ == "__main__":
    main()
