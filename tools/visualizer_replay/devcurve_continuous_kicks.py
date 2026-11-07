"""DevCurve kick response in CONTINUOUS play: recordings back to back through one frame runtime, never reset.

Feeds the production ``DevCurveFrameRuntime`` (the seam ``dispatch_devcurve_field`` calls) with each recording's
recorded lanes as the engine getters would return them (control lanes, transient lanes, bus loudness/presence;
passage intensity from the production ``PassageIntensity`` follower). Timestamps continue across recordings, so the
mode's memories (passage, response peak, swells) carry over exactly as in uninterrupted listening. A lockstep twin
with no band/transient energy gives the no-reaction rest.

For every typed kick: the jump of each body layer's height drive, of its visible reaction (the mean multiplier on
its undulation, height x swell) and of the curve's RMS displacement against the rest within ``--post`` seconds after the kick, relative to the mean of the ``--pre`` seconds
before it, tabulated by time in continuous play (0-15, 15-45, 45-90, 90+ s) and by passage (quiet / sustained loud).
Playing the same recording twice (``--clip a --clip a``) compares identical kicks early and late. Sidecar only.

Example:
  .venv\\Scripts\\python.exe -m tools.visualizer_replay.devcurve_continuous_kicks --preset 1 --output <dir>
      --clip logs/visualizer_recordings/human_heavy1.jsonl --clip logs/visualizer_recordings/human_heavy1.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[2]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from tools import artifact_paths  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LAYERS = ("bass", "vocals", "mids", "transients")
BODY = ("bass", "vocals", "mids")
TIME_BUCKETS = ((0.0, 15.0), (15.0, 45.0), (45.0, 90.0), (90.0, 1e9))
METRICS = ("drive", "react", "rms")
# Kick-locked grid (seconds from the kick) for the synchronous average: averaging the traces first and taking the
# peak of the mean removes the bias of a per-kick "max after minus mean before", which is positive on any noisy
# trace even with no kick at all.
LOCK_GRID = tuple(round(-0.3 + i / 90.0, 6) for i in range(int(round(0.45 * 90)) + 1))


def preset_parameters(preset: int):
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    resolved = resolve_visualizer_activation_payload({"mode": "devcurve", "preset_devcurve": preset - 1}).resolved_config
    parameters = {key: value for key, value in resolved.items() if key.startswith("devcurve_")}
    nodes = {name: [list(map(float, node)) for node in resolved[f"devcurve_layer_{name}_shape_nodes"]] for name in LAYERS}
    return parameters, nodes


def play(clip_paths, parameters, nodes, *, warmup: float = 2.0):
    """One row per tick of continuous play: t, clip index, song time, passage, kicks, drives, displacement RMS."""
    import numpy as np
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
    from widgets.spotify_visualizer.render_state import VisualizerEnergyState, VisualizerTransientState
    from widgets.spotify_visualizer.transient_bus import PassageIntensity
    runtime, twin, intensity = DevCurveFrameRuntime(), DevCurveFrameRuntime(), PassageIntensity()
    rows, clock, last = [], 100.0, None
    smooth01 = min(1.0, max(0.0, float(parameters.get("devcurve_smoothness", 0.0))))
    max_step = 0.040 - 0.020 * smooth01
    for index, path in enumerate(clip_paths):
        clip = load_feature_clip(path)
        origin = clip.frames[0].timestamp_us
        start = clock
        for frame in clip.frames:
            song_t = (frame.timestamp_us - origin) / 1e6
            now = start + song_t
            intensity.update(frame.real.musical_level[0], 0.0 if last is None else now - last)
            last = now
            lanes = frame.energy
            common = dict(now_ts=now, runtime_generation=1, engine_generation=1, activation_id=1, source_generation=1,
                          source_activation_id=1, source_timestamp=now, playing=True,
                          musical_level=tuple(frame.real.musical_level), musical_intensity=intensity.value,
                          layer_shape_nodes=nodes, parameters=parameters)
            live = runtime.advance(
                energy=VisualizerEnergyState(bass=lanes.pre_agc.bass, mid=lanes.pre_agc.mid, high=lanes.pre_agc.high,
                                             overall=lanes.pre_agc.overall),
                transient=VisualizerTransientState(bass=lanes.transient.bass, mid=lanes.transient.mid,
                                                   high=lanes.transient.high), **common)
            rest = twin.advance(energy=VisualizerEnergyState(), transient=VisualizerTransientState(), **common)
            curves, still = dict(live.curves), dict(rest.curves)
            diag = live.diagnostics
            drives = diag.get("drives") or {}
            rows.append({
                "t": now - 100.0, "clip": index, "song_t": song_t, "intensity": intensity.value,
                "loudness": float(frame.real.musical_level[0]),
                "kick": any(onset.kind == "kick" for onset in frame.real.onsets),
                "drive": {key: float(drives.get(f"height_{key}", diag["energies"][key])) for key in LAYERS},
                # The mean multiplier the music puts on each layer's undulation (height x swell); revisions
                # without it fall back to the height drive.
                "react": {key: float(drives.get(f"reaction_{key}", drives.get(f"height_{key}", diag["energies"][key])))
                          for key in LAYERS},
                "rms": {key: float(np.sqrt(np.mean((np.asarray(curves[key]) - np.asarray(still[key])) ** 2)))
                        for key in LAYERS},
                # The drawn height: the curve's own peak-to-trough span.
                "span": {key: float(np.ptp(np.asarray(curves[key]))) for key in LAYERS},
                # At the geometric cap: a segment held by the smoothness slope limiter (straight runs at the
                # limit survive the moving averages) or a sample in the top knee / bottom clamp.
                "cap": {key: bool((np.abs(np.diff(np.asarray(curves[key]))) >= 0.97 * max_step).any()
                                  or ((np.asarray(curves[key]) > 0.95) | (np.asarray(curves[key]) < 0.045)).any())
                        for key in LAYERS},
                # Near the floor: a trough within 0.08 of the bottom, flattened by a clamp or a soft floor.
                "low": {key: bool((np.asarray(curves[key]) < 0.08).any()) for key in LAYERS},
            })
        clock = start + (clip.frames[-1].timestamp_us - origin) / 1e6 + 1.0 / 90.0
    return [row for row in rows if row["song_t"] >= warmup or row["clip"] > 0]


def kick_responses(rows, *, pre: float = 0.3, post: float = 0.15, sustain: float = 3.0, gap: float = 0.25):
    """Kicks with no other kick in the ``gap`` before them (so the pre window is the bed, not the last kick)."""
    import numpy as np
    t = np.asarray([row["t"] for row in rows])
    kick_times = t[[row["kick"] for row in rows]]
    inten = np.asarray([row["intensity"] for row in rows])
    out = []
    for i, row in enumerate(rows):
        if not row["kick"]:
            continue
        before = (t >= row["t"] - pre) & (t < row["t"])
        after = (t >= row["t"]) & (t <= row["t"] + post)
        held = (t >= row["t"] - sustain) & (t < row["t"])
        if before.sum() < 5 or after.sum() < 5 or held.sum() < 30:
            continue
        if ((kick_times < row["t"]) & (kick_times >= row["t"] - gap)).any():
            continue
        rec = {"t": row["t"], "clip": row["clip"], "song_t": row["song_t"], "intensity": row["intensity"],
               "held": float(inten[held].mean()), "trace": {}}
        if inten[held].min() >= 0.5:
            rec["passage"] = "sustained_loud"
        elif inten[held].max() <= 0.3:
            rec["passage"] = "quiet"
        else:
            rec["passage"] = "changing"
        for key in LAYERS:
            d = np.asarray([rows[j]["drive"][key] for j in np.nonzero(before | after)[0]])
            r = np.asarray([rows[j]["rms"][key] for j in np.nonzero(before | after)[0]])
            nb = int(before.sum())
            rec[f"drive_{key}"] = float(d[nb:].max() - d[:nb].mean())
            v = np.asarray([rows[j]["react"][key] for j in np.nonzero(before | after)[0]])
            rec[f"react_{key}"] = float(v[nb:].max() - v[:nb].mean())
            rec[f"rms_{key}"] = float(r[nb:].max() - r[:nb].mean())
            window = np.nonzero(before | after)[0]
            tt = t[window] - row["t"]
            for metric, values in (("drive", d), ("react", v), ("rms", r)):
                rec["trace"][f"{metric}_{key}"] = np.interp(LOCK_GRID, tt, values)
        out.append(rec)
    return out


def _locked(sel, name):
    """Synchronous average of the kick-locked traces: peak of the mean within the post window minus its pre mean."""
    import numpy as np
    mean = np.mean([k["trace"][name] for k in sel], axis=0)
    grid = np.asarray(LOCK_GRID)
    return float(mean[grid >= 0.0].max() - mean[grid < 0.0].mean())


def _cell(sel):
    import numpy as np
    cell = {"kicks": len(sel)}
    for key in (*BODY, "transients"):
        for metric in METRICS:
            cell[f"{metric}_{key}"] = float(np.mean([k[f"{metric}_{key}"] for k in sel]))
            cell[f"locked_{metric}_{key}"] = _locked(sel, f"{metric}_{key}")
    return cell


def tabulate(kicks):
    import numpy as np
    table = {}
    for passage in ("all", "sustained_loud", "quiet"):
        for lo, hi in TIME_BUCKETS:
            sel = [k for k in kicks if lo <= k["t"] < hi and (passage == "all" or k["passage"] == passage)]
            if not sel:
                continue
            table[f"{passage} {lo:g}-{'end' if hi > 1e8 else f'{hi:g}'}s"] = _cell(sel)
    # Per recording (clip index in the play order), per passage.
    for clip in sorted({k["clip"] for k in kicks}):
        mine = [k for k in kicks if k["clip"] == clip]
        # The recording's own loudest third (3 s held passage), so every recording has a loud group.
        cut = float(np.percentile([k["held"] for k in mine], 67)) if mine else 0.0
        for passage in ("sustained_loud", "quiet", "loudest_third"):
            if passage == "loudest_third":
                sel = [k for k in mine if k["held"] >= cut]
            else:
                sel = [k for k in mine if k["passage"] == passage]
            if not sel:
                continue
            table[f"clip{clip} {passage}"] = _cell(sel)
    return table


def paired_repeat(kicks, length: float):
    """Same recording played twice: each kick of pass 2 against the identical kick of pass 1 (ratio of means)."""
    import numpy as np
    first = {round(k["song_t"], 2): k for k in kicks if k["clip"] == 0}
    pairs = [(first[round(k["song_t"], 2)], k) for k in kicks if k["clip"] == 1 and round(k["song_t"], 2) in first]
    result = {"pairs": len(pairs)}
    for passage in ("all", "sustained_loud"):
        sel = [(a, b) for a, b in pairs if passage == "all" or (a["passage"] == passage and b["passage"] == passage)]
        if not sel:
            continue
        for key in (*BODY, "transients"):
            for metric in METRICS:
                late = np.mean([b[f"{metric}_{key}"] for _, b in sel])
                early = np.mean([a[f"{metric}_{key}"] for a, _ in sel])
                result[f"{passage} {metric}_{key} late/early"] = float(late / early) if early > 1e-9 else None
                early = _locked([a for a, _ in sel], f"{metric}_{key}")
                late = _locked([b for _, b in sel], f"{metric}_{key}")
                result[f"{passage} locked_{metric}_{key} early"] = early
                result[f"{passage} locked_{metric}_{key} late"] = late
    return result


def geometry(rows):
    """Per recording (clip index in the play order): time at the geometric cap per layer and the height drive's
    reach, over all ticks and over loud ones (passage intensity >= 0.5)."""
    import numpy as np
    out = {}
    for clip in sorted({row["clip"] for row in rows}):
        mine = [row for row in rows if row["clip"] == clip]
        for passage in ("all", "loud"):
            chosen = [row for row in mine if passage == "all" or row["intensity"] >= 0.5]
            for key in LAYERS if chosen else ():
                drive = np.asarray([row["drive"][key] for row in chosen])
                out[f"clip{clip} {passage} {key}"] = {
                    "at_cap": float(np.mean([row["cap"][key] for row in chosen])),
                    "near_floor": float(np.mean([row["low"][key] for row in chosen])),
                    "drive_p05": float(np.percentile(drive, 5)), "drive_p50": float(np.percentile(drive, 50)),
                    "drive_p95": float(np.percentile(drive, 95)), "drive_above_0.9": float((drive > 0.9).mean()),
                    "rms_p50": float(np.median([row["rms"][key] for row in chosen])),
                    "rms_mean": float(np.mean([row["rms"][key] for row in chosen])),
                    "span_mean": float(np.mean([row["span"][key] for row in chosen])),
                    # The drawn reaction over its geometric ceiling (revisions that publish it): above 1 it
                    # sits in the mapping's own soft cap.
                    "react_above_1": float(np.mean([row["react"][key] > 1.0 for row in chosen])),
                }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", type=Path, action="append", required=True)
    parser.add_argument("--preset", type=int, default=1)
    parser.add_argument("--output", type=artifact_paths.evidence_arg, required=True)
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    parameters, nodes = preset_parameters(args.preset)
    rows = play(args.clip, parameters, nodes)
    kicks = kick_responses(rows)
    report = {"clips": [str(p) for p in args.clip], "preset": args.preset, "table": tabulate(kicks),
              "geometry": geometry(rows)}
    if len(args.clip) == 2 and args.clip[0].resolve() == args.clip[1].resolve():
        report["repeat"] = paired_repeat(kicks, 60.0)
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / f"{args.label}_p{args.preset}_kicks.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
