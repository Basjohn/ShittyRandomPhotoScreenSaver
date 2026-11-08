"""Native core P2 work order 4c: the in-process tick's and DSP's cost per tick, per mode (the record of the P2b decision).

In process the main process runs DSP and the logical tick. Each mode runs the shipped Studio clips (native PCM,
production DSP through ``ProductionLaneEngine``); DSP (``accept_feature_frame`` here; the compute pool live) and the
tick are timed apart.

Work order 4c compared this against P2a's main side (the lossless engine snapshot: step + capture + pickle + take) and
decided P2b; that half was deleted with the snapshot layer (work order 5 slice 5.6). It is reproducible at 4df640b7, and
its report is ``.artifacts/evidence/architecture/native_core_p2/20261108_main_cost/main_cost.json``. The live engine's
own cost (capture callbacks, step, analysis, tick, and the take with the worker out of process) is
``live_engine_cost.py``.

    python tools/visualizer_replay/engine_main_cost.py --out <dir> [--seconds 20] [--modes spectrum ...]

Wall time of single-threaded Python stands in for GIL time. Relative numbers on one machine; run on a quiet system.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GENERATION = 7


def _modes() -> tuple[str, ...]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


def _controller(mode, engine):
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    controller = VisualizerRuntimeController(runtime_generation=GENERATION, initial_mode=mode,
                                             engine_factory=lambda _count: engine)
    controller.engine = engine
    configure_offline_controller(controller, mode)
    return controller


def _in_process(frames, mode) -> dict:
    from widgets.spotify_visualizer.feature_replay import ProductionLaneEngine, deterministic_clock
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    dsp, tick = [], []
    with deterministic_clock() as clock:
        engine = ProductionLaneEngine(32)
        controller = _controller(mode, engine)
        for feature in frames:
            clock[0] = feature.timestamp_us / 1e6
            controller.playing = feature.playing
            engine.set_playback_state(feature.playing)
            t0 = time.perf_counter()
            engine.accept_feature_frame(feature)
            t1 = time.perf_counter()
            logical_tick(controller.logical_tick_state)
            t2 = time.perf_counter()
            dsp.append(t1 - t0)
            tick.append(t2 - t1)
    return {"dsp": dsp, "tick": tick}


def _ms(values, q):
    values = sorted(values)
    if not values:
        return 0.0
    return 1000.0 * (statistics.median(values) if q == 50 else values[min(len(values) - 1, int(len(values) * q / 100))])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--modes", nargs="*")
    args = parser.parse_args(argv)
    from PySide6.QtCore import QCoreApplication

    import tools.expanded_visualizer_evidence as evidence

    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
    clips = [evidence.shipped_clip(args.seconds, name) for name in evidence.STUDIO_CLIPS]
    rows = {}
    for mode in args.modes or _modes():
        ref = {"dsp": [], "tick": []}
        for clip in clips:
            measured = _in_process(clip.frames, mode)
            for key in ref:
                ref[key] += measured[key]
        row = {
            "frames": len(ref["tick"]),
            "tick_p50": _ms(ref["tick"], 50), "tick_p90": _ms(ref["tick"], 90),
            "dsp_p50": _ms(ref["dsp"], 50), "dsp_p90": _ms(ref["dsp"], 90),
        }
        rows[mode] = row
        print(f"{mode:18s} tick {row['tick_p50']:.3f}/{row['tick_p90']:.3f}  "
              f"dsp {row['dsp_p50']:.3f}/{row['dsp_p90']:.3f}", flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "main_cost.json").write_text(json.dumps({"seconds": args.seconds, "clips": list(evidence.STUDIO_CLIPS),
                                                    "rows": rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
