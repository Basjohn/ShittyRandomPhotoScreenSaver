"""Recorded music -> DevCurve's production logical path -> drive distributions and space-time maps.

Runs the production logical tick (configured worker, ReplayBeatEngine, DevCurveFrameRuntime) over a recording
and measures what DevCurve actually does with the music:

* every drive as a fraction of its authored Range (p05/p50/p95, share of ticks above 0.9);
* the realised reactive displacement of each layer (its curve minus the same curve solved with no reaction),
  its beat-scale modulation and its quiet-vs-loud contrast over 2 s windows ranked by passage;
* per-tick acceleration/jerk of identical curve points per x-band (centre, edges);
* a space-time map PNG of the foreground layer's displacement (rows = logical time at a uniform cadence).

``--reanalyze-pcm`` (default) recomputes DevCurve's own body lanes from the recorded PCM through the configured
worker, so the preset's technical settings reach them; onsets, loudness and passage stay recorded (the
documented replay hybrid). A sidecar: production never imports it. No window, no renderer.

Example:
  .venv\\Scripts\\python.exe -m tools.visualizer_replay.devcurve_reactivity_audit
      --clip logs/visualizer_recordings/human_heavy1.jsonl --output <dir> --preset 1
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LAYERS = ("bass", "vocals", "mids", "transients")
BANDS = {"edge_left": (0.0, 0.2), "centre": (0.4, 0.6), "edge_right": (0.8, 1.0)}


def _dist(values):
    import numpy as np
    a = np.asarray(values, float)
    if a.size == 0:
        return {}
    return {"p05": float(np.percentile(a, 5)), "p50": float(np.percentile(a, 50)),
            "p95": float(np.percentile(a, 95)), "max": float(a.max()),
            "above_0.9": float((a > 0.9).mean())}


def replay(clip_path: Path, preset: int, *, reanalyze: bool = True, seconds: float | None = None,
           overrides=None, playing_override: bool | None = None):
    """One row per playing logical tick: drives, inputs, realised curves and their no-reaction rest."""
    import numpy as np
    from PySide6.QtCore import QCoreApplication
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    from widgets.spotify_visualizer.feature_replay import (
        PcmReanalysis, ReplayBeatEngine, configure_offline_controller, deterministic_clock,
    )
    QCoreApplication.instance() or QCoreApplication([])
    clip = load_feature_clip(clip_path)
    origin = clip.frames[0].timestamp_us
    frames = [f for f in clip.frames if seconds is None or (f.timestamp_us - origin) / 1e6 <= seconds]
    from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
    from widgets.spotify_visualizer.render_state import VisualizerEnergyState, VisualizerTransientState
    rows = []
    twins: dict[int, DevCurveFrameRuntime] = {}
    original_advance = DevCurveFrameRuntime.advance

    def advance(self, **kwargs):
        # A lockstep twin with the same clock, passage and settings but no band or transient energy: its
        # curves are the no-reaction rest, so curve - twin is exactly what the music added.
        result = original_advance(self, **kwargs)
        twin = twins.setdefault(id(self), DevCurveFrameRuntime())
        original_advance(twin, **{**kwargs, "energy": VisualizerEnergyState(), "transient": VisualizerTransientState()})
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.object(DevCurveFrameRuntime, "advance", advance))
        clock = stack.enter_context(deterministic_clock())
        if reanalyze:
            # DevCurve's body lanes (get_energy_bands -> the worker's pre-AGC control lanes) from the PCM,
            # through this preset's configured DSP state, instead of the recorder's own.
            stack.enter_context(patch.object(ReplayBeatEngine, "get_pre_agc_energy_bands",
                                             _SpotifyBeatEngine.get_pre_agc_energy_bands))
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode="devcurve",
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        configure_offline_controller(controller, "devcurve", preset - 1, overrides=overrides)
        reanalysis = PcmReanalysis() if reanalyze else None
        try:
            for feature in frames:
                clock[0] = feature.timestamp_us / 1e6
                playing = feature.playing if playing_override is None else playing_override
                controller.playing = playing
                engine.set_playback_state(playing)
                engine.accept_feature_frame(feature)
                if reanalysis is not None:
                    reanalysis.accept(engine, feature)
                logical = logical_tick(controller.logical_tick_state)
                if logical is None or logical.mode_state is None:
                    continue
                runtime = controller.peek_logical_mode_state("devcurve")
                latest = runtime.latest
                diag = latest.diagnostics
                curves = {name: np.asarray(values, float) for name, values in latest.curves}
                rest = {name: np.asarray(values, float) for name, values in twins[id(runtime)].latest.curves}
                rows.append({
                    "t": (feature.timestamp_us - origin) / 1e6,
                    "playing": bool(playing),
                    "ready": bool(latest.reactive_source_ready),
                    "input": (float(latest.energy.bass), float(latest.energy.mid), float(latest.energy.high),
                              float(latest.transient.bass)),
                    "loudness": float(engine.get_musical_level()[0]),
                    "intensity": float(engine.get_musical_intensity()),
                    "energies": dict(diag.get("energies", {})),
                    "drives": dict(diag.get("drives", {}) or {}),
                    "passage_drive": float(diag.get("passage_drive", 0.0)),
                    "curves": curves,
                    "rest": rest,
                    "foreground": latest.foreground_layer,
                    "enabled": {name: bool(latest.parameters.get(f"devcurve_layer_{name}_enabled")) for name in LAYERS},
                    "smoothness": float(latest.parameters.get("devcurve_smoothness", 0.0)),
                })
        finally:
            engine.force_stop()
    return rows


def summarise(rows, *, fps: float = 45.0):
    import numpy as np
    active = [r for r in rows if r["playing"] and r["ready"]]
    if not active:
        raise ValueError("no playing, source-ready ticks")
    t = np.asarray([r["t"] for r in active])
    out = {"ticks": len(active), "seconds": float(t[-1] - t[0])}
    enabled = [name for name in LAYERS if active[0]["enabled"][name]]
    out["inputs"] = {name: _dist([r["input"][i] for r in active])
                     for i, name in enumerate(("bass", "mid", "high", "bass_transient"))}
    out["smooth_energy"] = {name: _dist([r["energies"].get(name, 0.0) for r in active]) for name in enabled}
    drive_keys = sorted({k for r in active for k in r["drives"]})
    out["drives"] = {k: _dist([r["drives"].get(k, 0.0) for r in active]) for k in drive_keys}
    out["passage_drive"] = _dist([r["passage_drive"] for r in active])
    out["intensity"] = _dist([r["intensity"] for r in active])
    out["loudness"] = _dist([r["loudness"] for r in active])
    layers = {}
    for name in enabled:
        if not all(name in r["rest"] for r in active):
            continue
        disp = np.stack([r["curves"][name] - r["rest"][name] for r in active])     # (ticks, x)
        amp = np.sqrt((disp ** 2).mean(axis=1))
        # Beat-scale modulation: the part of the amplitude that a 1 s mean does not explain.
        k = max(1, int(round(1.0 / max(1e-6, np.median(np.diff(t))))))
        kernel = np.ones(k) / k
        slow = np.convolve(np.pad(amp, (k // 2, k - 1 - k // 2), mode="edge"), kernel, mode="valid")
        beat = amp - slow
        # 2 s windows ranked by the passage (eased intensity), never by single ticks (guide §5, §13C).
        window = 2.0
        edges = np.arange(t[0], t[-1] - window + 1e-9, window)
        wins = []
        for start in edges:
            sel = (t >= start) & (t < start + window)
            if sel.sum() < 10:
                continue
            wins.append((float(np.mean([active[i]["intensity"] for i in np.nonzero(sel)[0]])),
                         float(np.median(amp[sel])), float(np.std(beat[sel]))))
        wins.sort()
        fifth = max(1, len(wins) // 5)
        quiet, loud = wins[:fifth], wins[-fifth:]
        # Per-tick kinematics of identical points (the x grid is fixed; curves never resample).
        y = np.stack([r["curves"][name] for r in active])
        dt = np.diff(t)
        vel = np.diff(y, axis=0) / dt[:, None]
        acc = np.diff(y, 2, axis=0)
        jerk = np.diff(y, 3, axis=0)
        xs = np.linspace(0.0, 1.0, y.shape[1])
        bands = {}
        for band, (lo, hi) in BANDS.items():
            sel = (xs >= lo) & (xs <= hi)
            a = np.abs(acc[:, sel]).max(axis=1)
            j = np.abs(jerk[:, sel]).max(axis=1)
            med = float(np.median(a)) + 1e-12
            bands[band] = {"accel_p50": float(np.median(a)), "accel_p99": float(np.percentile(a, 99)),
                           "accel_spike_share_4x": float((a > 4 * med).mean()),
                           "jerk_p50": float(np.median(j)), "jerk_p99": float(np.percentile(j, 99)),
                           "speed_p50": float(np.median(np.abs(vel[:, sel]).max(axis=1))),
                           "speed_p95": float(np.percentile(np.abs(vel[:, sel]).max(axis=1), 95))}
        # Geometric saturation: segments held by the smoothness slope limiter (straight runs at the limit
        # survive the moving averages) and samples in the top knee / bottom clamp. A reaction cannot show there.
        max_step = 0.040 - 0.020 * min(1.0, max(0.0, active[0]["smoothness"]))
        steps = np.abs(np.diff(y, axis=1))
        limited = steps >= 0.97 * max_step
        clamped = (y > 0.95) | (y < 0.045)
        layers[name] = {
            "slope_limited_samples": float(limited.mean()),
            "slope_limited_ticks": float(limited.any(axis=1).mean()),
            "clamped_samples": float(clamped.mean()),
            "amplitude": _dist(amp),
            "beat_modulation": float(np.std(beat) / (np.mean(amp) + 1e-12)),
            "beat_std": float(np.std(beat)),
            "quiet_windows": {"intensity": float(np.mean([w[0] for w in quiet])),
                              "amplitude_p50": float(np.mean([w[1] for w in quiet])),
                              "beat_std": float(np.mean([w[2] for w in quiet]))},
            "loud_windows": {"intensity": float(np.mean([w[0] for w in loud])),
                             "amplitude_p50": float(np.mean([w[1] for w in loud])),
                             "beat_std": float(np.mean([w[2] for w in loud]))},
            "bands": bands,
        }
    out["layers"] = layers
    return out


def space_time_map(rows, path: Path, *, layer: str | None = None, fps: float = 45.0, scale: float = 0.3,
                   start: float | None = None, seconds: float | None = None, column: int = 4):
    """Rows = logical time sampled at ``fps`` (a divisor of the ~90 Hz clock), columns = x along the curve.
    Colour: the layer's reactive displacement (red up, blue down, fixed ``scale``); right strip: loudness."""
    import numpy as np
    from PIL import Image, ImageDraw
    active = [r for r in rows if r["playing"] and r["ready"]]
    if start is not None:
        active = [r for r in active if r["t"] >= start]
    if seconds is not None:
        active = [r for r in active if r["t"] <= active[0]["t"] + seconds]
    name = layer or active[0]["foreground"]
    t = np.asarray([r["t"] for r in active])
    picks = [int(np.searchsorted(t, t[0] + i / fps)) for i in range(int((t[-1] - t[0]) * fps))]
    picks = [p for p in picks if p < len(active)]
    disp = np.stack([active[p]["curves"][name] - active[p]["rest"][name] for p in picks])
    v = np.clip(disp / scale, -1.0, 1.0)
    rgb = np.zeros(v.shape + (3,), np.uint8)
    rgb[..., 0] = (255 * np.clip(v, 0, 1)).astype(np.uint8)
    rgb[..., 2] = (255 * np.clip(-v, 0, 1)).astype(np.uint8)
    rgb[..., 1] = (60 * (1 - np.abs(v))).astype(np.uint8)
    img = Image.fromarray(rgb).resize((v.shape[1] * column, v.shape[0]), Image.NEAREST)
    loud = np.asarray([active[p]["loudness"] for p in picks])
    # Side strips: bus loudness (/17) and the layer's displacement RMS (/scale), grey.
    amp = np.sqrt((disp ** 2).mean(axis=1))
    strips = [np.clip(loud / 17.0, 0, 1), np.clip(amp / scale, 0, 1)]
    sheet = Image.new("RGB", (img.width + 28 * len(strips) + 4, img.height + 16), (0, 0, 0))
    sheet.paste(img, (0, 16))
    for i, strip in enumerate(strips):
        side = Image.fromarray((np.repeat((strip * 255)[:, None], 24, axis=1)).astype(np.uint8)).convert("RGB")
        sheet.paste(side, (img.width + 4 + 28 * i, 16))
    ImageDraw.Draw(sheet).text((4, 2), f"{name} displacement +-{scale}  {fps:g} fps  t0={t[0]:.1f}s | loud | rms",
                               fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", type=int, default=1)
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--recorded-bands", action="store_true", help="serve the recorder's pre-AGC lanes")
    parser.add_argument("--map-start", type=float)
    parser.add_argument("--map-seconds", type=float, default=20.0)
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {}
    for clip in args.clip:
        rows = replay(clip, args.preset, reanalyze=not args.recorded_bands, seconds=args.seconds)
        summary = summarise(rows)
        report[clip.stem] = summary
        space_time_map(rows, args.output / f"{args.label}_{clip.stem}_p{args.preset}_spacetime.png",
                       start=args.map_start, seconds=args.map_seconds)
        print(clip.stem, json.dumps({k: summary[k] for k in ("smooth_energy", "drives", "passage_drive")}), flush=True)
    target = args.output / f"{args.label}_p{args.preset}_summary.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
