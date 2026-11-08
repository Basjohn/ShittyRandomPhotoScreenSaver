"""Native core P2 work order 4c: the main process's cost per tick, in process vs. the snapshot path, per mode.

In process the main process runs the logical tick. With P2a it instead steps the engine and captures a snapshot
(``EngineSnapshotSource.capture``), pickles it for the worker, and takes the worker's frame (read + decode +
acknowledge). DSP (``accept_feature_frame`` here; the compute pool live) is the same on both paths and is reported
apart. Each mode runs the shipped Studio clips (native PCM, production DSP through ``ProductionLaneEngine``); the
worker side runs in this process but is not timed. Also reported: which captured values the mode's tick reads, and
the capture cost of only those (a per-mode capture set, audit H1).

    python tools/visualizer_replay/engine_main_cost.py --out <dir> [--seconds 20] [--modes spectrum ...]

Wall time of single-threaded Python stands in for GIL time. Relative numbers on one machine; run on a quiet system.
"""
from __future__ import annotations

import argparse
import copy
import json
import pickle
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


def _snapshot_path(frames, mode) -> dict:
    from core.visualizer_engine.engine_snapshot import CAPTURED_GETTERS, EngineSnapshotSource, SnapshotBeatEngine
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from widgets.spotify_visualizer.feature_replay import (
        REPLAY_SEED, ProductionLaneEngine, deterministic_clock,
    )

    read = set()
    original = SnapshotBeatEngine.__getattr__

    def spy(self, name):
        if name in CAPTURED_GETTERS:
            read.add(name)
        return original(self, name)

    out = {"dsp": [], "capture": [], "pickle": [], "take": [], "snapshot_bytes": [], "per_getter": {}}
    per = {name: [] for name in CAPTURED_GETTERS}
    SnapshotBeatEngine.__getattr__ = spy
    try:
        with deterministic_clock():
            engine = ProductionLaneEngine(32)
            _controller(mode, engine)
            source = EngineSnapshotSource(engine, mode)
            reader = PacketMailbox(role="reader")
            session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION,
                                    inputs="snapshot", initial_snapshot=source.capture(0.0, playing=True, step=False),
                                    seed=REPLAY_SEED)
            try:
                for feature in frames:
                    session.clock[0] = feature.timestamp_us / 1e6
                    engine.set_playback_state(feature.playing)
                    t0 = time.perf_counter()
                    engine.accept_feature_frame(feature)
                    t1 = time.perf_counter()
                    snapshot = source.capture(session.clock[0], playing=feature.playing)
                    t2 = time.perf_counter()
                    blob = pickle.dumps(snapshot, protocol=pickle.HIGHEST_PROTOCOL)
                    t3 = time.perf_counter()
                    session.tick_snapshot(pickle.loads(blob))        # the worker's side: not timed
                    t4 = time.perf_counter()
                    reader.take()
                    t5 = time.perf_counter()
                    for name in CAPTURED_GETTERS:                     # each value's own capture cost (pure reads)
                        g0 = time.perf_counter()
                        copy.deepcopy(getattr(engine, name)())
                        per[name].append(time.perf_counter() - g0)
                    out["dsp"].append(t1 - t0)
                    out["capture"].append(t2 - t1)
                    out["pickle"].append(t3 - t2)
                    out["take"].append(t5 - t4)
                    out["snapshot_bytes"].append(len(blob))
            finally:
                session.close()
                reader.close()
    finally:
        SnapshotBeatEngine.__getattr__ = original
    out["read"] = sorted(read)
    out["per_getter"] = per
    return out


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
        snap = {"dsp": [], "capture": [], "pickle": [], "take": [], "snapshot_bytes": [], "read": set(),
                "per_getter": {}}
        for clip in clips:
            frames = clip.frames
            a = _in_process(frames, mode)
            b = _snapshot_path(frames, mode)
            for key in ref:
                ref[key] += a[key]
            for key in ("dsp", "capture", "pickle", "take", "snapshot_bytes"):
                snap[key] += b[key]
            snap["read"] |= set(b["read"])
            for name, values in b["per_getter"].items():
                snap["per_getter"].setdefault(name, []).extend(values)
        total = [c + p + t for c, p, t in zip(snap["capture"], snap["pickle"], snap["take"])]
        all_getters = sum(_ms(v, 50) for v in snap["per_getter"].values())
        read_getters = sum(_ms(v, 50) for n, v in snap["per_getter"].items() if n in snap["read"])
        row = {
            "frames": len(ref["tick"]),
            "tick_p50": _ms(ref["tick"], 50), "tick_p90": _ms(ref["tick"], 90),
            "capture_p50": _ms(snap["capture"], 50), "pickle_p50": _ms(snap["pickle"], 50),
            "take_p50": _ms(snap["take"], 50), "take_p90": _ms(snap["take"], 90),
            "snapshot_path_p50": _ms(total, 50), "snapshot_path_p90": _ms(total, 90),
            "getters_all_p50": all_getters, "getters_read_p50": read_getters,
            "snapshot_kib_p50": statistics.median(snap["snapshot_bytes"]) / 1024.0,
            "dsp_p50": _ms(ref["dsp"], 50), "read": sorted(snap["read"]),
        }
        row["gain_p50"] = row["tick_p50"] - row["snapshot_path_p50"]
        row["gain_p50_read_only_capture"] = row["gain_p50"] + (all_getters - read_getters)
        rows[mode] = row
        print(f"{mode:18s} tick {row['tick_p50']:.3f}/{row['tick_p90']:.3f}  snapshot path "
              f"{row['snapshot_path_p50']:.3f}/{row['snapshot_path_p90']:.3f} (capture {row['capture_p50']:.3f} "
              f"pickle {row['pickle_p50']:.3f} take {row['take_p50']:.3f})  gain {row['gain_p50']:+.3f}  "
              f"read-only-capture gain {row['gain_p50_read_only_capture']:+.3f}  reads {len(row['read'])}", flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "main_cost.json").write_text(json.dumps({"seconds": args.seconds, "clips": list(evidence.STUDIO_CLIPS),
                                                    "rows": rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
