"""Native core P2b gates on the live-engine rig: the live engine in process equals the live engine in the worker.

    python tools/visualizer_replay/live_engine_gate.py --out <dir> [--scenarios ...] [--order production|settled]
        [--seconds 60] [--modes ...] [--clips ...] [--stress]
    python tools/visualizer_replay/live_engine_gate.py --out <dir> --paced [--paced-seconds 3] [--modes ...]

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
``--paced`` (work order 5, slice 5.1; instead of the scenarios): per mode, a worker-paced session in the
``WorkerType.VISUALIZER`` process (``EngineSession(cadence="worker")``: its own logical runtime cadence, the shipped
clip's PCM paced on the audio clock at the cadence's edges) free-running for ``--paced-seconds``, the reader taking
frames on its own wake thread and stalling after each take (a slow GUI). Gated (``paced_ok``): no exception or step
failure; one frame per cadence step, the cadence's own rate (its steps over its run time) within 5% of the authored
rate; coalescing (taken < published) and latest wins (every take after a stall is the newest frame published before
it, with at least one such take); the newest frame reached by a wake after the stop (never stranded); revisions only
advance; 0 torn reads; the audio reached the engine on the audio clock (checkpoint audit 6, A6-M1: the source
delivered >= 97% of the paced time, the paced time at least 80% of the run, the audio worker's capture callback
published every offered block into the engine, >= 97% of the paced time, the engine committed an analysis on at least
half the steps, and at least half the frames taken carry energy). Not frame identity: the commits race the tick, as
live.
Runs at below-normal priority; exit 1 on any mismatch or stress/paced failure.
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


#: The reader's stall after each take in the paced gate (a GUI busy ~40 ms per frame: ~25 Hz against a 90 Hz cadence).
PACED_STALL_S = 0.04
#: The cadence's rate within this share of the authored rate (A6-L6; the evidence shows 89.5-90.1 Hz of 90).
PACED_RATE_TOLERANCE = 0.05
#: Engine-side audio evidence (A6-M1): the engine's analysis commits per cadence step, and the share of taken frames
#: with energy above zero (the clip's opening is music, not silence).
PACED_MIN_COMMITS_PER_STEP = 0.8
PACED_MIN_ENERGETIC = 0.5


class PacedReader:
    """The main process's side of a worker-paced session: the reader mapping, its wake listener (the owner's wake
    emitter: it only sets an event, so repeated wakes coalesce) and a consumer thread that takes the newest frame per
    wake and then stalls ``stall_s`` (a slow GUI). Never a poll: the consumer blocks on the wake event."""

    def __init__(self, stall_s: float = PACED_STALL_S) -> None:
        import multiprocessing
        import threading

        from core.visualizer_engine.packet_mailbox import PacketMailbox

        self.mailbox = PacketMailbox(role="reader")
        self.receiver, self.sender = multiprocessing.Pipe(duplex=False)
        self._woke, self._done, self._reached = threading.Event(), threading.Event(), threading.Event()
        self._lock = threading.Lock()
        self._target: int | None = None
        self.taken: list[int] = []
        self.errors: list[str] = []
        self._stall = threading.Event()               # never set: a bounded stall, not a wait for anything
        self._stall_s = float(stall_s)
        self.energetic = 0                            # frames taken whose overall energy is above zero (A6-M1)
        self.latest_checks = 0                        # takes after a stall with newer frames published (A6-L6)
        self.stale_takes: list[tuple[int, int]] = []  # (taken, newest published before the take): latest-wins broken
        self.mailbox.set_wake_callback(self._woke.set)
        self.mailbox.listen_for_wakes(self.receiver)
        self._thread = threading.Thread(target=self._consume, name="paced-gate-reader", daemon=True)
        self._thread.start()

    def _consume(self) -> None:
        while True:
            self._woke.wait()
            if self._done.is_set():
                return
            self._woke.clear()
            try:
                newest = self.newest_published()          # the header's newest frame, read before the take
                publication = self.mailbox.take()
            except Exception as exc:                      # noqa: BLE001 - reported, the run fails
                self.errors.append(repr(exc))
                continue
            if publication is not None:
                with self._lock:
                    previous = self.taken[-1] if self.taken else 0
                    self.taken.append(publication.revision)
                    if newest > previous + 1:             # several frames published during the stall
                        self.latest_checks += 1
                    if publication.revision < newest:     # latest wins: never a frame older than the newest
                        self.stale_takes.append((publication.revision, newest))
                    if self._target is not None and publication.revision >= self._target:
                        self._reached.set()
                common = getattr(publication.state, "common", None)
                if common is not None and float(common.energy.overall) > 0.0:
                    self.energetic += 1
            self._stall.wait(self._stall_s)

    def newest_published(self) -> int:
        """The revision of the newest frame the writer has published (the mapping header's ``latest``), 0 if none."""
        from core.visualizer_engine.packet_abi import FIRST_SEQUENCE

        latest = struct.unpack_from("<Q", self.mailbox._reader._view, 32)[0]
        return 0 if latest < FIRST_SEQUENCE else (latest - FIRST_SEQUENCE) // 2 + 1

    def wait_for(self, revision: int, timeout_s: float = 5.0) -> bool:
        """Whether the consumer takes ``revision`` (the last published) through its wakes alone."""
        with self._lock:
            self._target = int(revision)
            if self.taken and self.taken[-1] >= revision:
                self._reached.set()
        return self._reached.wait(timeout_s)

    def close(self) -> None:
        self._done.set()
        self._woke.set()
        self._thread.join(5.0)
        self.mailbox.close()


def paced_verdict(report: dict, reader: PacedReader, *, seconds: float, reached: bool) -> dict:
    """The paced gate's checks on a finished session's report and its reader (module docstring)."""
    cadence, audio, engine = report["cadence"] or {}, report["audio"], report["engine"]
    published, steps = report["revision"], cadence.get("steps", 0)
    interval_s = cadence.get("interval_ms", 0.0) / 1000.0
    taken = list(reader.taken)
    rate_hz = published / seconds if seconds > 0 else 0.0
    authored_hz = 1.0 / interval_s if interval_s else 0.0
    # The cadence's own rate: the last runtime's steps over its run time, less its parked time (A6-L6).
    running_s = report["cadence_s"] - cadence.get("parked_seconds", 0.0)
    cadence_hz = steps / running_s if running_s > 0 else 0.0
    paced_s = audio["paced_s"]
    delivered_ratio = audio["delivered_s"] / paced_s if paced_s else 0.0
    accepted_ratio = engine["accepted_s"] / paced_s if paced_s else 0.0
    energetic = reader.energetic / len(taken) if taken else 0.0
    verdict = {
        "seconds": seconds, "published": published, "steps": steps,
        "skipped_deadlines": cadence.get("skipped_deadlines"), "step_failures": cadence.get("step_failures"),
        "published_hz": round(rate_hz, 2), "cadence_hz": round(cadence_hz, 2), "authored_hz": round(authored_hz, 2),
        "taken": len(taken), "last_taken": taken[-1] if taken else None,
        "torn_reads": reader.mailbox._reader.torn_reads,
        "advancing": all(b > a for a, b in zip(taken, taken[1:])), "stranded": not reached,
        "latest_checks": reader.latest_checks, "stale_takes": list(reader.stale_takes),
        "audio": audio, "delivered_over_paced": round(delivered_ratio, 4), "engine": engine,
        "accepted_over_paced": round(accepted_ratio, 4), "energetic_share": round(energetic, 4),
        "capture": report.get("capture"), "reader_errors": list(reader.errors),
    }
    verdict["cadence_ok"] = bool(published > 0 and abs(cadence_hz - authored_hz) <= PACED_RATE_TOLERANCE * authored_hz)
    verdict["audio_ok"] = bool(
        delivered_ratio >= 0.97 and audio["delivered_s"] <= paced_s + 0.05 and paced_s >= 0.8 * seconds
        and accepted_ratio >= 0.97 and engine["accepted_blocks"] == engine["offered_blocks"]
        and engine["analysis_commits"] >= PACED_MIN_COMMITS_PER_STEP * steps and energetic >= PACED_MIN_ENERGETIC)
    verdict["paced_ok"] = bool(
        not reader.errors and cadence.get("step_failures") == 0 and published == steps and verdict["cadence_ok"]
        and len(taken) < published and reached and verdict["advancing"] and verdict["torn_reads"] == 0
        and verdict["latest_checks"] > 0 and not verdict["stale_takes"] and verdict["audio_ok"])
    return verdict


def paced_pcm(seconds: float = 3.0, clip: str | None = None):
    """The shipped clip's continuous PCM (the paced source loops it)."""
    import tools.expanded_visualizer_evidence as evidence
    from core.visualizer_engine.recorded_capture import pcm_from_capture_histories

    frames = evidence.shipped_clip(seconds, clip).frames if clip else evidence.shipped_clip(seconds).frames
    return pcm_from_capture_histories(frames)


def paced_in_process(pcm, rate: int, mode: str, *, seconds: float, stall_s: float = PACED_STALL_S,
                     between=None) -> dict:
    """A worker-paced session in this process (its cadence thread here): the gate's checks; ``between(session)``
    runs mid-run (a park, a play edge) when given."""
    import threading

    from core.visualizer_engine.engine_worker import EngineSession

    reader = PacedReader(stall_s)
    session = None
    try:
        session = EngineSession(mapping=reader.mailbox.mapping_name, mode=mode, runtime_generation=GENERATION,
                                inputs="live", order="free", cadence="worker", pcm=pcm, pcm_rate=rate,
                                wake=reader.sender)
        run = threading.Event()
        started = time.perf_counter()
        session.start(True)
        if between is not None:
            run.wait(seconds / 2)
            between(session)
            run.wait(max(0.0, seconds - (time.perf_counter() - started)))
        else:
            run.wait(seconds)
        report = session.finish()
        elapsed = time.perf_counter() - started
        reached = reader.wait_for(report["revision"])
        return paced_verdict(report, reader, seconds=elapsed, reached=reached)
    finally:
        if session is not None:
            session.close()
        reader.close()


def paced_in_worker(supervisor, pcm, rate: int, mode: str, *, seconds: float,
                    stall_s: float = PACED_STALL_S) -> dict:
    """The same in the ``WorkerType.VISUALIZER`` process (VIS_CONFIGURE ``cadence="worker"``, VIS_START, VIS_STOP)."""
    import threading

    from core.process.types import MessageType, WorkerType

    reader = PacedReader(stall_s)
    try:
        configure_worker(supervisor, reader.mailbox, mode, order="free", cadence="worker", pcm=pcm, pcm_rate=rate,
                         wake=reader.sender, seed=None)
        reader.sender.close()                         # the worker holds its own end now
        started = time.perf_counter()
        response = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_START,
                                                              {"playing": True}, timeout_ms=30_000)
        if response is None or not response.success:
            raise RuntimeError(f"start: {response and response.error}")
        threading.Event().wait(seconds)
        stopped = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                             timeout_ms=30_000)
        if stopped is None or not stopped.success:
            raise RuntimeError(f"stop: {stopped and stopped.error}")
        elapsed = time.perf_counter() - started
        report = stopped.payload["report"]
        reached = reader.wait_for(report["revision"])
        return paced_verdict(report, reader, seconds=elapsed, reached=reached)
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
    parser.add_argument("--paced", action="store_true")
    parser.add_argument("--paced-seconds", type=float, default=3.0)
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
    if args.paced:
        return _main_paced(args, supervisor, modes, report, started)
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


def _main_paced(args, supervisor, modes, report, started) -> int:
    pcm, rate = paced_pcm(args.paced_seconds)
    report.update(paced={}, paced_failures=0, paced_seconds=args.paced_seconds, paced_stall_s=PACED_STALL_S)
    try:
        for mode in modes:
            verdict = paced_in_worker(supervisor, pcm, rate, mode, seconds=args.paced_seconds)
            report["paced"][mode] = verdict
            report["paced_failures"] += 0 if verdict["paced_ok"] else 1
            engine = verdict["engine"]
            print(f"[PACED] {mode:18s} {'OK' if verdict['paced_ok'] else 'FAILED'} published {verdict['published']} "
                  f"(cadence {verdict['cadence_hz']} Hz of {verdict['authored_hz']}) steps {verdict['steps']} skipped "
                  f"{verdict['skipped_deadlines']} failures {verdict['step_failures']} taken {verdict['taken']} last "
                  f"{verdict['last_taken']} latest-wins {verdict['latest_checks']} checks "
                  f"{len(verdict['stale_takes'])} stale torn {verdict['torn_reads']} audio paced "
                  f"{verdict['audio']['paced_s']:.3f} delivered {verdict['audio']['delivered_s']:.3f} engine "
                  f"{engine['accepted_s']:.3f} s commits {engine['analysis_commits']} energetic "
                  f"{verdict['energetic_share']}", flush=True)
    finally:
        supervisor.shutdown()
    report["elapsed_s"] = time.time() - started
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "paced_gate.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"[PACED] {len(modes)} modes, {report['paced_failures']} failing, {report['elapsed_s']:.0f} s", flush=True)
    return 1 if report["paced_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
