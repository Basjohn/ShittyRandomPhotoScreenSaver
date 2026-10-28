"""Extruded Bubble control audit on real music: does each reactive control's authored range reach what is shown?

For every reactive Range (quiet .. loud) and Slider, replay recorded songs through the production simulation
(``ExtrudedBubbleFrameRuntime`` driven by the replay BeatEngine, as ``extruded_bubble_traces``) and the renderer's own
drivers (``ray_strength``, ``ray_motion``, ``_procedural_fill``), then report the realized value in the song's quietest
and loudest fifths (by passage intensity). Cases per Range: the left (quiet) handle at its minimum, the preset's own
values, the left handle raised to the right one (a flat range: quiet should then match loud), and the right handle at
its minimum. A working minimum shows a clearly lower quiet value than the preset's; a faithful range keeps quiet near
the left handle and loud near the right one.

    python -m tools.visualizer_replay.eb_control_audit [--preset 1] [clip ...]

``--realized`` instead reports each preset's own values once (quietest fifth / middle fifth / loudest fifth) for every
metric from one replay per song, for re-authoring presets: ``--realized --preset 1 2 3``.
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "logs" / "visualizer_recordings"
DEFAULT_CLIPS = ("human_heavy1", "1985_loud1", "nightsolong_acousticsoft1")


def _metrics():
    from rendering.gl_programs.extruded_bubble_scene import ray_motion, ray_strength
    from rendering.quick.visualizer.implementations.extruded_bubble import _procedural_fill, chain_drive
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
        "extruded_bubble_ray_shimmer": ("shimmer depth", lambda p, s, r: ray_motion(p, s.rays, s.sustain)[0]),
        "extruded_bubble_ray_modulation": ("ray intensity", lambda p, s, r: ray_strength(p, s.rays)),
        "extruded_bubble_large_bubbles": ("live large", population(True)),
        "extruded_bubble_mid_bubbles": ("live small", population(False)),
        "extruded_bubble_bead_chains": ("chains", lambda p, s, r: _procedural_fill(p, chain_drive(s), s.emission)[0]),
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
    quiet, _middle, loud = _replay_all(clip, params, {"metric": metric})["metric"]
    return quiet, loud


def _replay_all(clip, params, metrics):
    """Each metric's mean in the quietest, middle and loudest fifths of the song, from one replay."""
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import (
        ExtrudedBubbleFrameRuntime, controls_from_parameters, passage_intensity_from_body_bands,
    )
    engine = ReplayBeatEngine(32)
    runtime = ExtrudedBubbleFrameRuntime(1)
    controls = controls_from_parameters(params)
    rows = []
    for frame in clip.frames:
        engine.accept_feature_frame(frame)
        now = frame.timestamp_us / 1e6
        onsets = engine.get_onset_events(runtime.onset_serial)
        bands = engine.get_extruded_bubble_body_bands()
        body_bands = (bands.bass, bands.mid, bands.high)
        snap = runtime.advance(onsets=onsets, now_ts=now, playing=bool(frame.playing),
                               identity=(1, 1, 1), source_identity=(1, 1), body_bands=body_bands,
                               controls=controls)
        rows.append((passage_intensity_from_body_bands(body_bands), tuple(m(params, snap, runtime) for m in metrics.values())))
    # Rank by the PASSAGE (a centred 4 s mean of EB's body-derived intensity), not the instantaneous value: that snaps
    # to 0 in every near-silent gap between beats, so its quietest fifth was beat gaps inside loud music.
    times = [f.timestamp_us / 1e6 for f in clip.frames]
    sums = [0.0]
    for intensity, _v in rows:
        sums.append(sums[-1] + intensity)
    passage, lo, hi = [], 0, 0
    for i, t in enumerate(times):
        while times[lo] < t - 2.0:
            lo += 1
        while hi < len(times) and times[hi] <= t + 2.0:
            hi += 1
        passage.append((sums[hi] - sums[lo]) / (hi - lo))
    rows = [(p, v) for p, (_i, v) in zip(passage, rows)][len(rows) // 10:]      # skip warm-up
    rows.sort(key=lambda r: r[0])
    result = {}
    for index, name in enumerate(metrics):
        # skip warm-up and empty frames (NaN: no bubble of that class on screen)
        values = [(p, v[index]) for p, v in rows if v[index] == v[index]]
        fifth = max(1, len(values) // 5)
        middle = len(values) // 2 - fifth // 2
        result[name] = tuple(statistics.fmean(v for _p, v in part) if part else float("nan")
                             for part in (values[:fifth], values[middle:middle + fifth], values[-fifth:]))
    return result


def realized(presets, clip_names, keys=()):
    """Each preset's own values, every metric from one replay per song: quiet / middle / loud fifths."""
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    clips = [FeatureClip.from_jsonl_bytes(n, (ROOT / f"{n}.jsonl").read_bytes()) for n in clip_names]
    metrics = {k: m for k, (_label, m) in _metrics().items() if not keys or k in keys}
    for preset in presets:
        params = dict(resolve_visualizer_activation_payload(
            {"mode": "extruded_bubble", "preset_extruded_bubble": preset - 1}, mode="extruded_bubble").resolved_config)
        params.setdefault("scene3d_detail", "High")
        params["extruded_bubble_rays_enabled"] = params.get("extruded_bubble_rays_enabled", True)
        results = [_replay_all(clip, params, metrics) for clip in clips]
        print(f"\nPreset {preset}")
        for key in metrics:
            cells = "   ".join(f"{clip.name[:12]:>12s} " + " / ".join(f"{v:6.3f}" for v in result[key])
                               for clip, result in zip(clips, results))
            print(f"  {key[len('extruded_bubble_'):]:26s} {str(params[key]):14s} {cells}", flush=True)


def _cases(control, value):
    if isinstance(value, (list, tuple)):
        low, high = (float(v) for v in value)
        return (("left at min", [control.low, high]), ("preset", [low, high]),
                ("left = right", [high, high]), ("right at min", [low, control.low]))
    return (("min", control.low), ("preset", float(value)), ("max", control.high))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preset", type=int, nargs="+", default=[1])
    parser.add_argument("--realized", action="store_true", help="each preset's own values only, every metric")
    parser.add_argument("--keys", nargs="*", help="only these controls (extruded_bubble_ prefix optional)")
    parser.add_argument("clips", nargs="*", default=list(DEFAULT_CLIPS))
    args = parser.parse_args(argv)
    wanted = {k if k.startswith("extruded_bubble_") else "extruded_bubble_" + k for k in (args.keys or ())}
    if args.realized:
        realized(args.preset, args.clips, wanted)
        return
    from core.settings.visualizer_mode_settings import require_mode_settings
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    base = dict(resolve_visualizer_activation_payload(
        {"mode": "extruded_bubble", "preset_extruded_bubble": args.preset[0] - 1}, mode="extruded_bubble").resolved_config)
    # The renderer's drivers also read the 3D Detail tier (resolved per display, not a setting): audit at High.
    base.setdefault("scene3d_detail", "High")
    spec = require_mode_settings("extruded_bubble")
    clips = [FeatureClip.from_jsonl_bytes(n, (ROOT / f"{n}.jsonl").read_bytes()) for n in args.clips]
    for key, (label, metric) in _metrics().items():
        if wanted and key not in wanted:
            continue
        control = spec.control(key)
        print(f"\n{key}  ({label}; preset {base[key]})")
        for case, value in _cases(control, base[key]):
            params = {**base, key: value}
            if key in ("extruded_bubble_ray_shimmer", "extruded_bubble_ray_modulation", "extruded_bubble_rays"):
                params["extruded_bubble_rays_enabled"] = True
            cells = []
            for clip in clips:
                quiet, loud = _replay(clip, params, metric)
                cells.append(f"{clip.name[:14]:>14s} {quiet:7.3f} / {loud:7.3f}")
            print(f"  {case:13s} {str(value):22s} " + "   ".join(cells), flush=True)


if __name__ == "__main__":
    main()
