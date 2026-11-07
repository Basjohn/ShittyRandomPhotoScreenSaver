"""Measure the GUI-thread cost of Spectrum Studio exact replays, frame by frame, as the Studio drives them.

Worst case: the longest shipped clip, at its end, after Spectrum-owned commits (discrete and after a drag), an undo,
a backward seek and an engine-owned landing. For each event the tool reports every evaluation's wall time until the
exact frame lands and checks that frame against the production replay (``extract``) under the same values. With
``--budget 0`` it measures the previous behaviour (the whole replay in one evaluation). Never shows a window.

    .venv\\Scripts\\python.exe tools/spectrum_studio_replay_budget.py --budget 0.008 --out <json>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[1]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from tools import artifact_paths  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--budget", type=float, default=0.008, help="seconds per evaluation; 0 = unbounded")
    parser.add_argument("--out", type=artifact_paths.evidence_arg, default=None)
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    from ui.studio.spectrum_adapter import SHAPE_NODES, SpectrumStudioEvaluator, engine_key
    from ui.studio.spectrum_recorded_inputs import extract, frame_digest, to_inputs
    from ui.studio.waveform_adapter import recordings_directory
    from ui.studio.waveform_recorded_inputs import studio_clips

    spec = require_mode_settings("spectrum")
    values = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in spec.controls:
        values[control.key] = control.admit(values[control.key], values[control.key])
    clip = max(studio_clips(recordings_directory()), key=lambda c: c.duration)
    records: dict = {}

    def record(vals):
        key = json.dumps(sorted((k, repr(v)) for k, v in vals.items()))
        if key not in records:
            records[key] = extract(clip.description, vals, seconds=None)
        return records[key]

    def expected(vals, at):
        data = record(vals)
        steps = [s for s in data["steps"] if s["now_ts"] - data["origin"] <= at + 1e-9 and s["frame_sha256"]]
        return steps[-1]["frame_sha256"]

    pending = []

    def loader(fixture, vals, finished):
        data = record(vals)
        pending.append((finished, to_inputs(data, replace(fixture, duration=float(data["duration"])))))

        class Job:
            def cancel(self):
                pass
        return Job()

    evaluator = SpectrumStudioEvaluator(loader=loader)
    data = record(values)
    evaluator.add_recorded(to_inputs(data, replace(clip, duration=float(data["duration"]))))
    evaluator.select(clip.id)
    evaluator.set_frame_budget(args.budget or None)
    end = evaluator.fixture.duration
    report = {"clip": clip.label, "ticks": len(data["steps"]), "duration_s": end, "budget_s": args.budget,
              "events": []}

    def frames_until_exact(name, vals, at, *, exact=True, first_live=False):
        times, digests = [], []
        while True:
            started = time.perf_counter()
            frame = evaluator.evaluate(at, vals, exact=exact)
            times.append((time.perf_counter() - started) * 1000.0)
            digests.append(frame_digest(frame))
            if not evaluator.converging or len(times) > 2000:
                break
        ok = digests[-1] == expected(vals, at)
        report["events"].append({"event": name, "frames": len(times), "worst_ms": round(max(times), 2),
                                 "median_ms": round(sorted(times)[len(times) // 2], 2),
                                 "first_ms": round(times[0], 2), "exact": ok})
        print(f"{name:42s} frames={len(times):3d} worst={max(times):7.2f} ms first={times[0]:7.2f} ms exact={ok}")
        return ok

    evaluator.set_frame_budget(None)
    frames_until_exact("open (first replay, lifecycle)", values, end)
    evaluator.set_frame_budget(args.budget or None)
    edits = (("spectrum_ghost_decay", spec.control("spectrum_ghost_decay").low),
             ("spectrum_visual_smoothing", 0.9), ("spectrum_bar_fill_color", [200, 40, 90, 255]),
             ("spectrum_rainbow_ghost", not values["spectrum_rainbow_ghost"]))
    all_exact = True
    history = [dict(values)]
    for key, value in edits:
        edited = dict(history[-1])
        edited[key] = value
        all_exact &= frames_until_exact(f"commit {key}", edited, end)
        history.append(edited)
    # A drag: live frames, then the gesture end's exact replay.
    dragged = dict(history[-1])
    for step in (0.3, 0.5, 0.7):
        dragged["spectrum_visual_smoothing"] = step
        started = time.perf_counter()
        evaluator.evaluate(end, dragged, exact=False)
        report["events"].append({"event": f"drag frame smoothing={step}",
                                 "worst_ms": round((time.perf_counter() - started) * 1000.0, 2)})
    all_exact &= frames_until_exact("drag end (exact)", dragged, end)
    history.append(dragged)
    all_exact &= frames_until_exact("undo (previous values)", history[-2], end)
    all_exact &= frames_until_exact("seek back to 60%", history[-2], end * 0.6)
    all_exact &= frames_until_exact("seek back to the end", history[-2], end)
    # An engine-owned edit: previous answers stay until its analysis lands, then the new answers replay.
    engine_edit = dict(history[-2])
    nodes = [list(n) for n in engine_edit[SHAPE_NODES]]
    nodes[0][1] = 0.0 if nodes[0][1] > 0.5 else 1.0
    engine_edit[SHAPE_NODES] = nodes
    evaluator.evaluate(end, engine_edit)
    finished, result = pending.pop()
    finished(result, "")
    all_exact &= frames_until_exact("engine-owned analysis landed", engine_edit, end)
    report["all_exact"] = bool(all_exact)
    report["worst_after_commit_ms"] = max(e["worst_ms"] for e in report["events"]
                                          if not e["event"].startswith(("open", "engine-owned")))
    print("worst GUI-thread evaluation after a Spectrum-owned commit:", report["worst_after_commit_ms"], "ms")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    evaluator.release()
    del app, engine_key
    return 0 if all_exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
