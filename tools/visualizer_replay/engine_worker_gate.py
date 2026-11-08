"""Native core P2 identity gate: the engine worker against the in-process tick, on the operator's recordings.

For each recording in ``logs/visualizer_recordings`` (read only) and each mode, the first ``--seconds`` of post-DSP
inputs are ticked twice: in this process by ``EngineSession`` (whose frames equal the production owner's, see
``tests/test_visualizer_engine_worker.py``) and in a ``WorkerType.VISUALIZER`` process under ``ProcessSupervisor``;
every frame read back through the packet ABI must have the same digest. Runs at below-normal priority, one worker,
one recording at a time.

    python tools/visualizer_replay/engine_worker_gate.py --seconds 30 --out <report.json>
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

RECORDINGS = ROOT / "logs" / "visualizer_recordings"
GENERATION = 7


def _modes() -> tuple[str, ...]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


def _head(clip, seconds: float):
    first = clip.frames[0].timestamp_us
    return [frame for frame in clip.frames if frame.timestamp_us - first <= seconds * 1_000_000]


def _in_process(frames, mode: str) -> list[str]:
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from tools.expanded_visualizer_evidence import frame_digest

    reader = PacketMailbox(role="reader")
    session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION)
    try:
        digests = []
        for frame in frames:
            session.tick(frame)
            digests.append(frame_digest(reader.take().state))
        return digests
    finally:
        session.close()
        reader.close()


def _worker(supervisor, frames, mode: str) -> list[str]:
    from core.process.types import MessageType, WorkerType
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from tools.expanded_visualizer_evidence import frame_digest

    reader = PacketMailbox(role="reader")
    try:
        configured = supervisor.send_request_and_await_response(
            WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
            {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": GENERATION}, timeout_ms=120_000)
        if configured is None or not configured.success:
            raise RuntimeError(f"configure failed: {configured and configured.error}")
        digests = []
        for frame in frames:
            response = supervisor.send_request_and_await_response(
                WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"frame": frame}, timeout_ms=60_000)
            if response is None or not response.success:
                raise RuntimeError(f"tick failed: {response and response.error}")
            digests.append(frame_digest(reader.take().state))
        supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {}, timeout_ms=60_000)
        return digests
    finally:
        reader.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--recording", action="append", help="limit to these recording stems")
    args = parser.parse_args(argv)
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    from PySide6.QtCore import QCoreApplication
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main
    from widgets.spotify_visualizer.feature_frame import load_jsonl

    app = QCoreApplication.instance() or QCoreApplication([])
    paths = sorted(RECORDINGS.glob("*.jsonl"))
    if args.recording:
        paths = [path for path in paths if path.stem in set(args.recording)]
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    if not supervisor.start(WorkerType.VISUALIZER):
        print("[GATE] the engine worker did not start", file=sys.stderr)
        return 2
    report = {"seconds": args.seconds, "recordings": {}, "mismatches": 0, "frames": 0}
    started = time.time()
    try:
        try:
            import psutil
            pid = supervisor.get_detailed_health(WorkerType.VISUALIZER).get("pid")
            if pid:
                psutil.Process(int(pid)).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception:
            pass
        for path in paths:
            clip = load_jsonl(path)
            frames = _head(clip, args.seconds)
            del clip
            rows = {}
            for mode in _modes():
                try:
                    expected = _in_process(frames, mode)
                    actual = _worker(supervisor, frames, mode)
                    first = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b), None)
                    same = first is None and len(expected) == len(actual)
                    rows[mode] = {"frames": len(expected), "identical": same, "first_mismatch": first}
                    report["frames"] += len(expected)
                    report["mismatches"] += 0 if same else 1
                except Exception as exc:                       # a failure is a gate result, not a crash
                    rows[mode] = {"error": f"{type(exc).__name__}: {exc}"}
                    report["mismatches"] += 1
                print(f"[GATE] {path.stem} {mode}: {rows[mode]}", flush=True)
            report["recordings"][path.stem] = rows
            Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        supervisor.shutdown()
        app.processEvents()
    report["elapsed_s"] = round(time.time() - started, 1)
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[GATE] {report['frames']} frames, {report['mismatches']} mismatching (recording, mode) pairs, "
          f"{report['elapsed_s']} s", flush=True)
    return 0 if report["mismatches"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
