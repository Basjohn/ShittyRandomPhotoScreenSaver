"""Native core P2b gates on the live-engine rig: the live engine in process equals the live engine in the worker.

    python tools/visualizer_replay/live_engine_gate.py --out <dir> [--scenarios ...] [--order production|settled]
        [--seconds 60] [--modes ...] [--clips ...] [--stress]

Scenarios (every shipped Studio clip; ``steps`` below):

- ``steady`` (slice 1): the clip as recorded. Also reports how the live engine's frames differ from
  ``ProductionLaneEngine``'s (not gated: the lanes engine re-analyses each frame's history synchronously).
- ``pause_warm`` / ``pause_cold`` (slice 2, audit H3): Media paused once 1.5 s have played, for 2 s (capture stays
  warm: the 6 s grace) or 7 s (the grace expires and capture stops), then resumed (``recorded_capture
  .synthesise_pause``: paused ticks and two resume ticks carry no new capture, as the recorder would record them).
  The resume arms the warm re-entry fence (the owner's ``set_playing``).
- ``reentry``: display power parked once 1.5 s have played (no ticks for 1 s, the music goes on), then unparked:
  capture reopens, the fence is armed and the clocks rebased (the owner's ``set_display_power``); the first two
  ticks after it carry no new capture.
- ``switch``: an in-session mode switch to a partner mode at 1.5 s, a pause at 3 s for 2 s with a switch back in its
  middle, then resume (``VIS_SET_MODE``, applied at the next tick boundary). Run per (mode, partner) pair.

Every tick records the frame digest and the newest slot's head (identity and flags) read with plain ``struct`` from
an independent attach of the mapping; the gate is in-process == worker for both. ``--order``: the rig's commit order
(``EngineSession.ORDERS``; ``production``, the tick reads the previous commit as live, is the reference; ``settled``
is slice 1's portability order). Reported, not gated: how often capture restarted (``wake``'s stale path reads the
wall clock, so whether a warm resume restarts depends on how long the rig took; a restart is frame-neutral).
``--stress``: per clip and mode, the worker in ``free`` order (commits race the tick) with the reader taking frames
on its own wake thread: no exceptions, no stranded or torn frames, revisions advance (a non-identity check).
Runs at below-normal priority; exit 1 on any mismatch or stress failure.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import struct
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GENERATION = 9001
SCENARIOS = ("steady", "pause_warm", "pause_cold", "reentry", "switch")
#: (mode, partner) pairs for the in-session switch scenario (Spectrum <-> Extruded Bubble both ways; a sample-drawing
#: mode into Bubble's RNG spawn; spectrum readers into and out of the 3D modes).
SWITCH_PAIRS = (("spectrum", "extruded_bubble"), ("extruded_bubble", "spectrum"), ("oscilloscope", "bubble"),
                ("sphere", "waveform_ribbon"), ("devcurve", "shockwave_grid"), ("extruded_spectrum", "oscilloscope"))


def _modes() -> tuple[str, ...]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


def _after(frames, seconds: float) -> int:
    start = frames[0].timestamp_us
    return next(i for i, frame in enumerate(frames) if frame.timestamp_us - start >= seconds * 1e6)


def steps(scenario: str, frames, mode: str, partner: str | None = None) -> list[tuple[str, Any]]:
    """The scenario as control steps: ("input", FeatureFrame), ("mode", mode id), ("display", on)."""
    from core.visualizer_engine.recorded_capture import synthesise_pause

    frames = tuple(frames)
    if scenario == "steady":
        return [("input", frame) for frame in frames]
    if scenario in ("pause_warm", "pause_cold"):
        paused = synthesise_pause(frames, at_s=1.5, pause_s=2.0 if scenario == "pause_warm" else 7.0)
        return [("input", frame) for frame in paused]
    if scenario == "reentry":
        park, unpark = _after(frames, 1.5), _after(frames, 2.5)
        held = frames[park - 1].capture_history
        resumed = [dataclasses.replace(frame, capture_history=held) for frame in frames[unpark:unpark + 2]]
        return ([("input", frame) for frame in frames[:park]] + [("display", False), ("display", True)]
                + [("input", frame) for frame in resumed] + [("input", frame) for frame in frames[unpark + 2:]])
    if scenario == "switch":
        if partner is None:
            raise ValueError("the switch scenario needs a partner mode")
        paused = synthesise_pause(frames, at_s=3.0, pause_s=2.0)
        out = [("input", frame) for frame in paused]
        first_paused = next(i for i, frame in enumerate(paused) if not frame.playing)
        last_paused = max(i for i, frame in enumerate(paused) if not frame.playing)
        out.insert((first_paused + last_paused) // 2, ("mode", mode))       # back to the configured mode, paused
        out.insert(_after(paused, 1.5), ("mode", partner))
        return out
    raise ValueError(f"unknown scenario {scenario!r}")


def newest_slot_head(buffer) -> tuple[int, ...]:
    """(flags, runtime generation, engine generation, activation id, mode code) of the newest slot, read with plain
    ``struct`` at the ABI's offsets (what a native reader reads; no Python codec)."""
    from core.visualizer_engine import packet_abi as abi

    slot_bytes = struct.unpack_from("<I", buffer, 24)[0]
    latest = struct.unpack_from("<Q", buffer, 32)[0]
    for slot in range(abi.SLOT_COUNT):
        base = abi.HEADER_BYTES + slot * slot_bytes
        if struct.unpack_from("<Q", buffer, base)[0] == latest:
            return (struct.unpack_from("<I", buffer, base + 32)[0], *struct.unpack_from("<IIII", buffer, base + 40))
    raise AssertionError("no slot holds the latest sequence")


class _Tap:
    """An independent attach of the reader's mapping (plain bytes, as a native reader sees them)."""

    def __init__(self, name: str) -> None:
        from multiprocessing.shared_memory import SharedMemory

        self._memory = SharedMemory(name=name)

    def head(self) -> tuple[int, ...]:
        return newest_slot_head(self._memory.buf)

    def close(self) -> None:
        self._memory.close()


def run_in_process(script, mode: str, *, order: str = "production", inputs: str = "live", summaries=None) -> dict:
    """Drive one in-process session through ``script``; per tick the frame digest and the newest slot head."""
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED
    import tools.expanded_visualizer_evidence as evidence

    reader = PacketMailbox(role="reader")
    tap = _Tap(reader.mapping_name)
    session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION, inputs=inputs,
                            seed=REPLAY_SEED if inputs == "live" else None,
                            **({"order": order} if inputs == "live" else {}))
    digests, heads, restarts = [], [], 0
    try:
        for kind, value in script:
            if kind == "input":
                session.tick(value)
                state = reader.take().state
                digests.append(evidence.frame_digest(state))
                heads.append(tap.head())
                if summaries is not None:
                    summaries.append(_summary(state))
            elif kind == "mode":
                session.request_mode(value)
            elif kind == "display":
                session.set_display_power(value)
        restarts = session.capture_counts[1] if inputs == "live" else 0
    finally:
        session.close()
        tap.close()
        reader.close()
    return {"digests": digests, "heads": heads, "restarts": restarts}


def configure_worker(supervisor, reader, mode: str, *, order: str = "production", **extra) -> Any:
    from core.process.types import MessageType, WorkerType
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED

    configured = supervisor.send_request_and_await_response(
        WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
        {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": GENERATION, "inputs": "live",
         "seed": REPLAY_SEED, "order": order, **extra}, timeout_ms=60_000)
    if configured is None or not configured.success:
        raise RuntimeError(f"configure: {configured and configured.error}")
    if not configured.payload.get("device_refused"):
        raise RuntimeError("the worker's live session does not refuse an audio device")
    return configured


def run_in_worker(supervisor, script, mode: str, *, order: str = "production") -> dict:
    """The same script through a ``WorkerType.VISUALIZER`` process (VIS_INPUT / VIS_SET_MODE /
    VIS_SET_DISPLAY_POWER)."""
    from core.process.types import MessageType, WorkerType
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    import tools.expanded_visualizer_evidence as evidence

    reader = PacketMailbox(role="reader")
    tap = _Tap(reader.mapping_name)
    try:
        configure_worker(supervisor, reader, mode, order=order)
        digests, heads = [], []
        for kind, value in script:
            if kind == "input":
                message, payload = MessageType.VIS_INPUT, {"frame": value}
            elif kind == "mode":
                message, payload = MessageType.VIS_SET_MODE, {"mode": value}
            else:
                message, payload = MessageType.VIS_SET_DISPLAY_POWER, {"on": value}
            response = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, message, payload,
                                                                  timeout_ms=30_000)
            if response is None or not response.success:
                raise RuntimeError(f"{kind}: {response and response.error}")
            if kind == "input":
                digests.append(evidence.frame_digest(reader.take().state))
                heads.append(tap.head())
        supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {}, timeout_ms=30_000)
        return {"digests": digests, "heads": heads}
    finally:
        tap.close()
        reader.close()


def stress_in_worker(supervisor, frames, mode: str) -> dict:
    """``free`` order in the worker (commits race the tick) with the reader taking frames on its own wake thread."""
    import multiprocessing
    import threading

    from core.process.types import MessageType, WorkerType
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    reader = PacketMailbox(role="reader")
    receiver, sender = multiprocessing.Pipe(duplex=False)
    taken, errors, lock = [], [], threading.Lock()

    def on_wake() -> None:
        try:
            publication = reader.take()
        except Exception as exc:                          # noqa: BLE001 - reported, the run fails
            errors.append(repr(exc))
            return
        if publication is not None:
            with lock:
                taken.append(publication.revision)

    reader.set_wake_callback(on_wake)
    reader.listen_for_wakes(receiver)
    try:
        configure_worker(supervisor, reader, mode, order="free", wake=sender)
        sender.close()
        last = 0
        for feature in frames:
            response = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_INPUT,
                                                                  {"frame": feature}, timeout_ms=30_000)
            if response is None or not response.success:
                errors.append(f"input: {response and response.error}")
                break
            last = response.payload["revision"]
        supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {}, timeout_ms=30_000)
        final = reader.take()                             # anything the wake thread has not taken yet
        with lock:
            if final is not None:
                taken.append(final.revision)
            seen = list(taken)
        advancing = all(b > a for a, b in zip(seen, seen[1:]))
        stranded = not seen or seen[-1] != last
        return {"ticks": len(frames), "taken": len(seen), "last_revision": last, "advancing": advancing,
                "stranded": stranded, "torn_reads": reader._reader.torn_reads, "errors": errors,
                "ok": advancing and not stranded and not errors}
    finally:
        reader.close()


def _summary(frame) -> tuple:
    common = frame.common
    return tuple(float(v) for v in common.bars), float(common.energy.overall)


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
    parser.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    parser.add_argument("--order", default="production")
    parser.add_argument("--stress", action="store_true")
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
    report = {"seconds": args.seconds, "order": args.order, "scenarios": {}, "mismatches": 0, "frames": 0,
              "pairs": 0, "stress": {}, "stress_failures": 0}
    started = time.time()
    modes = args.modes or _modes()
    try:
        for name in names:
            frames = evidence.shipped_clip(args.seconds, name).frames
            for scenario in args.scenarios:
                runs = ([(a, b) for a, b in SWITCH_PAIRS if not args.modes or a in args.modes]
                        if scenario == "switch" else [(mode, None) for mode in modes])
                rows = report["scenarios"].setdefault(scenario, {}).setdefault(name, {})
                for mode, partner in runs:
                    script = steps(scenario, frames, mode, partner)
                    summaries = [] if scenario == "steady" else None
                    local = run_in_process(script, mode, order=args.order, summaries=summaries)
                    worker = run_in_worker(supervisor, script, mode, order=args.order)
                    identical = local["digests"] == worker["digests"]
                    heads = local["heads"] == worker["heads"]
                    row = {"frames": len(local["digests"]), "identical": identical, "slot_heads_identical": heads,
                           "mismatching_frames": sum(a != b for a, b in zip(local["digests"], worker["digests"])),
                           "capture_restarts_in_process": local["restarts"]}
                    if scenario == "steady":
                        lane_summaries = []
                        lanes = run_in_process(script, mode, inputs="lanes", summaries=lane_summaries)
                        row["versus_lanes"] = _versus_lanes(summaries, lane_summaries, local["digests"],
                                                            lanes["digests"])
                    key = mode if partner is None else f"{mode}->{partner}"
                    rows[key] = row
                    report["frames"] += row["frames"]
                    report["pairs"] += 1
                    report["mismatches"] += 0 if identical and heads else 1
                    print(f"[GATE] {scenario:10s} {name:14s} {key:34s} "
                          f"{'IDENTICAL' if identical and heads else 'MISMATCH '} {row['frames']} frames "
                          f"restarts {local['restarts']}", flush=True)
            if args.stress:
                for mode in modes:
                    result = stress_in_worker(supervisor, frames, mode)
                    report["stress"].setdefault(name, {})[mode] = result
                    report["stress_failures"] += 0 if result["ok"] else 1
                    print(f"[STRESS] {name:14s} {mode:18s} {'OK' if result['ok'] else 'FAILED'} taken "
                          f"{result['taken']}/{result['ticks']} torn {result['torn_reads']} {result['errors']}",
                          flush=True)
    finally:
        supervisor.shutdown()
    report["elapsed_s"] = time.time() - started
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "live_gate.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[GATE] {report['pairs']} pairs, {report['frames']} frames, {report['mismatches']} mismatching, "
          f"{report['stress_failures']} stress failures, {report['elapsed_s']:.0f} s", flush=True)
    return 1 if report["mismatches"] or report["stress_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
