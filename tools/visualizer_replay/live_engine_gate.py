"""Native core P2b slice 1 gate: the live engine in process equals the live engine in the worker, every mode, every
shipped Studio clip, whole; plus how the live engine's frames differ from ``ProductionLaneEngine``'s (reported, not
gated: the lanes engine re-analyses each frame's history synchronously, the live engine analyses the newest capture
block on its compute lane).

    python tools/visualizer_replay/live_engine_gate.py --out <dir> [--seconds 60] [--modes ...] [--clips ...]

Per (clip, mode): frames, digests identical in process vs worker (the gate), and against the lanes engine the equal
frames, the first differing frame, the mean absolute difference of the common bars and of the common overall energy,
and the lag (in ticks, -3..3) that best aligns the two overall-energy series. Runs at below-normal priority; exit 1 on
any mismatch.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GENERATION = 9001


def _modes() -> tuple[str, ...]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


def _summary(frame) -> tuple:
    common = frame.common
    return tuple(float(v) for v in common.bars), float(common.energy.overall)


def _in_process(frames, mode, inputs):
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED
    import tools.expanded_visualizer_evidence as evidence

    reader = PacketMailbox(role="reader")
    session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION, inputs=inputs,
                            seed=REPLAY_SEED if inputs == "live" else None)
    digests, summaries = [], []
    try:
        for feature in frames:
            session.tick(feature)
            state = reader.take().state
            digests.append(evidence.frame_digest(state))
            summaries.append(_summary(state))
    finally:
        session.close()
        reader.close()
    return digests, summaries


def _worker(supervisor, frames, mode):
    from core.process.types import MessageType, WorkerType
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED
    import tools.expanded_visualizer_evidence as evidence

    reader = PacketMailbox(role="reader")
    try:
        ok = supervisor.send_request_and_await_response(
            WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
            {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": GENERATION, "inputs": "live",
             "seed": REPLAY_SEED}, timeout_ms=60_000)
        if ok is None or not ok.success:
            raise RuntimeError(f"configure: {ok and ok.error}")
        digests = []
        for feature in frames:
            response = supervisor.send_request_and_await_response(
                WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"frame": feature}, timeout_ms=30_000)
            if response is None or not response.success:
                raise RuntimeError(f"input: {response and response.error}")
            digests.append(evidence.frame_digest(reader.take().state))
        supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {}, timeout_ms=30_000)
        return digests
    finally:
        reader.close()


def _versus_lanes(live, lanes, live_digests, lane_digests) -> dict:
    n = min(len(live), len(lanes))
    equal = sum(a == b for a, b in zip(live_digests, lane_digests))
    first = next((i for i, (a, b) in enumerate(zip(live_digests, lane_digests)) if a != b), None)
    bars = [abs(x - y) for (a, _), (b, _) in zip(live, lanes) for x, y in zip(a, b)]
    overall_live = [o for _, o in live[:n]]
    overall_lanes = [o for _, o in lanes[:n]]

    def mad(lag: int) -> float:
        pairs = [(overall_live[i + lag], overall_lanes[i]) for i in range(max(0, -lag), min(n, n - lag))]
        return sum(abs(a - b) for a, b in pairs) / max(1, len(pairs))

    lags = {lag: mad(lag) for lag in range(-3, 4)}
    return {"equal_frames": equal, "first_difference": first,
            "bars_mean_abs_diff": sum(bars) / max(1, len(bars)),
            "overall_mean_abs_diff": lags[0], "overall_best_lag": min(lags, key=lags.get),
            "overall_mean_live": sum(overall_live) / max(1, n), "overall_mean_lanes": sum(overall_lanes) / max(1, n)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--modes", nargs="*")
    parser.add_argument("--clips", nargs="*")
    args = parser.parse_args(argv)
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    from PySide6.QtCore import QCoreApplication

    import tools.expanded_visualizer_evidence as evidence
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
    names = args.clips or sorted(p.stem for p in (ROOT / "assets" / "production" / "studio_clips").glob("*.srclip"))
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    if not supervisor.start(WorkerType.VISUALIZER):
        print("[GATE] the engine worker did not start", file=sys.stderr)
        return 2
    try:
        import psutil
        pid = supervisor.get_detailed_health(WorkerType.VISUALIZER).get("pid")
        if pid:
            psutil.Process(int(pid)).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    report = {"seconds": args.seconds, "clips": {}, "mismatches": 0, "frames": 0, "pairs": 0}
    started = time.time()
    try:
        for name in names:
            frames = evidence.shipped_clip(args.seconds, name).frames
            rows = {}
            for mode in args.modes or _modes():
                live_digests, live = _in_process(frames, mode, "live")
                worker_digests = _worker(supervisor, frames, mode)
                lane_digests, lanes = _in_process(frames, mode, "lanes")
                identical = worker_digests == live_digests
                row = {"frames": len(frames), "identical": identical,
                       "mismatching_frames": sum(a != b for a, b in zip(live_digests, worker_digests)),
                       "versus_lanes": _versus_lanes(live, lanes, live_digests, lane_digests)}
                rows[mode] = row
                report["frames"] += len(frames)
                report["pairs"] += 1
                report["mismatches"] += 0 if identical else 1
                v = row["versus_lanes"]
                print(f"[GATE] {name:14s} {mode:18s} {'IDENTICAL' if identical else 'MISMATCH '} {len(frames)} "
                      f"frames | vs lanes: equal {v['equal_frames']} first diff {v['first_difference']} bars "
                      f"{v['bars_mean_abs_diff']:.4f} overall {v['overall_mean_abs_diff']:.4f} (live "
                      f"{v['overall_mean_live']:.3f} lanes {v['overall_mean_lanes']:.3f}) best lag "
                      f"{v['overall_best_lag']}", flush=True)
            report["clips"][name] = rows
    finally:
        supervisor.shutdown()
    report["elapsed_s"] = time.time() - started
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "live_gate.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[GATE] {report['pairs']} pairs, {report['frames']} frames, {report['mismatches']} mismatching, "
          f"{report['elapsed_s']:.0f} s", flush=True)
    return 1 if report["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
