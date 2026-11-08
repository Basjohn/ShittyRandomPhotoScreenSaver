"""Native core P2b slice 1: what P2b removes from the main process, measured on the live engine.

Today the main process runs the live ``_SpotifyBeatEngine``: every capture callback (the audio worker's mono mix,
capture history and publication), the engine step, one analysis on the compute lane per consumed block (FFT, bars,
smoothing, transient bus; then the commit callback) and the logical tick. Under P2b all of it moves to the worker and
the main process keeps the frame take (read + decode + acknowledge). This tool measures both on the shipped Studio
clips with the P2b rig (``EngineSession(inputs="live")``, recorded PCM through the real capture callback):

* ``live``: in process, per tick: push (all callbacks of the tick), step, analysis (the compute lane's own execution
  and commit-callback time, from its diagnostics), tick. Per callback and per analysis too. Ticks a garbage
  collection overlapped are counted and reported apart (checkpoint audit 2, A2-M4).
* ``take``: the main side of P2b with the session in a real ``WorkerType.VISUALIZER`` process, so no worker tick runs
  in the timed process (the 4c confound).
* ``gil``: how much of the DSP holds the GIL. A pure-Python counter thread runs against (a) a pure-Python loop (the
  GIL-bound calibration), (b) a sleep (the released calibration), (c) ``numpy.fft.rfft`` at the capture block sizes
  and at a large size, (d) the production analysis (``compute_bars_from_samples`` on a configured worker state, the
  clip's blocks). The counter's progress interpolated between (a) and (b) estimates the share of the work's wall time
  that holds the GIL.

    python tools/visualizer_replay/live_engine_cost.py --out <dir> [--seconds 20] [--modes spectrum ...]
        [--sections live take gil]

Runs at below-normal priority. Relative numbers on one machine; record the system's load next to them.
"""
from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

GENERATION = 7
#: The GIL switch interval the held-share estimate runs at (see ``_counter_share``).
FINE_SWITCH_S = 2e-5


def _modes() -> tuple[str, ...]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


def _ms(values, q):
    values = sorted(values)
    if not values:
        return 0.0
    return 1000.0 * (statistics.median(values) if q == 50 else values[min(len(values) - 1, int(len(values) * q / 100))])


class _GcWatch:
    """Collections that ran, as (start, end) perf_counter spans (gc.callbacks; on only while this tool measures)."""

    def __init__(self) -> None:
        self.spans: list[tuple[float, float]] = []
        self._start = 0.0

    def __call__(self, phase, _info) -> None:
        if phase == "start":
            self._start = time.perf_counter()
        else:
            self.spans.append((self._start, time.perf_counter()))

    def __enter__(self):
        gc.callbacks.append(self)
        return self

    def __exit__(self, *exc) -> None:
        gc.callbacks.remove(self)

    def overlaps(self, start: float, end: float) -> bool:
        return any(a < end and b > start for a, b in self.spans[-8:])


def _lane_totals(engine) -> tuple[float, float, int]:
    snapshot = engine._analysis_lane.diagnostic_snapshot()
    return (float(snapshot["execution_ms_total"]), float(snapshot["callback_ms_total"]),
            int(snapshot["logical_steps_completed"]))


def _live(frames, mode) -> dict:
    """The live session's own per-input sequence (``EngineSession._tick_live``), timed piece by piece."""
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    out = {key: [] for key in ("push", "step", "analysis", "tick", "total", "per_callback", "per_analysis",
                               "callbacks", "analyses", "gc_overlap")}
    reader = PacketMailbox(role="reader")
    session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION, inputs="live")
    engine, state = session._engine, session._controller.logical_tick_state
    try:
        session.tick(frames[0])                       # opens capture; not timed
        reader.take()
        with _GcWatch() as watch:
            for feature in frames[1:]:
                session.clock[0] = feature.timestamp_us / 1e6
                backend = session._backend
                blocks = session._stream.blocks(feature.capture_history, feature.timestamp_us, backend.block_size)
                lane0 = _lane_totals(engine)
                t0 = time.perf_counter()
                for block in blocks:
                    c0 = time.perf_counter()
                    backend.push(block)
                    out["per_callback"].append(time.perf_counter() - c0)
                t1 = time.perf_counter()
                session._settled.clear()
                engine.tick()
                t2 = time.perf_counter()
                if engine.has_analysis_in_flight() and not session._settled.wait(30.0):
                    raise RuntimeError("analysis never settled")
                t3 = time.perf_counter()
                if logical_tick(state) is None:
                    raise RuntimeError("no frame")
                t4 = time.perf_counter()
                lane1 = _lane_totals(engine)
                reader.take()
                analysis = ((lane1[0] - lane0[0]) + (lane1[1] - lane0[1])) / 1000.0
                analyses = lane1[2] - lane0[2]
                if analyses:
                    out["per_analysis"].append(analysis / analyses)
                out["push"].append(t1 - t0)
                out["step"].append(t2 - t1)
                out["analysis"].append(analysis)
                out["tick"].append(t4 - t3)
                out["total"].append((t1 - t0) + (t2 - t1) + analysis + (t4 - t3))
                out["callbacks"].append(len(blocks))
                out["analyses"].append(analyses)
                out["gc_overlap"].append(watch.overlaps(t0, t4))
            out["gc_ms"] = sum(b - a for a, b in watch.spans) * 1000.0
            out["gc_count"] = len(watch.spans)
    finally:
        session.close()
        reader.close()
    return out


def _take(clips, modes) -> dict:
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import MessageType, WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    if not supervisor.start(WorkerType.VISUALIZER):
        raise RuntimeError("the engine worker did not start")
    _below_normal(supervisor.get_detailed_health(WorkerType.VISUALIZER).get("pid"))
    rows = {}
    try:
        for mode in modes:
            takes, overlap, gc_ms = [], [], 0.0
            for clip in clips:
                reader = PacketMailbox(role="reader")
                try:
                    ok = supervisor.send_request_and_await_response(
                        WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
                        {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": GENERATION,
                         "inputs": "live"}, timeout_ms=60_000)
                    if ok is None or not ok.success:
                        raise RuntimeError(f"{mode}: {ok and ok.error}")
                    with _GcWatch() as watch:
                        for feature in clip.frames:
                            response = supervisor.send_request_and_await_response(
                                WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"frame": feature}, timeout_ms=30_000)
                            if response is None or not response.success:
                                raise RuntimeError(f"{mode}: {response and response.error}")
                            t0 = time.perf_counter()
                            reader.take()
                            t1 = time.perf_counter()
                            takes.append(t1 - t0)
                            overlap.append(watch.overlaps(t0, t1))
                        gc_ms += sum(b - a for a, b in watch.spans) * 1000.0
                    supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                               timeout_ms=30_000)
                finally:
                    reader.close()
            clean = [t for t, o in zip(takes, overlap) if not o]
            rows[mode] = {"frames": len(takes), "take_p50": _ms(takes, 50), "take_p90": _ms(takes, 90),
                          "take_p50_no_gc": _ms(clean, 50), "take_p90_no_gc": _ms(clean, 90),
                          "gc_overlapped": sum(overlap), "gc_ms": gc_ms}
            print(f"[take] {mode:18s} {rows[mode]['take_p50']:.3f}/{rows[mode]['take_p90']:.3f} ms "
                  f"(no-GC {rows[mode]['take_p50_no_gc']:.3f}/{rows[mode]['take_p90_no_gc']:.3f}, "
                  f"{rows[mode]['gc_overlapped']} overlapped)", flush=True)
    finally:
        supervisor.shutdown()
    return rows


def _counter_share(work, seconds: float = 1.5, *, switch_interval: float | None = None) -> dict:
    """A pure-Python counter's progress while ``work()`` loops on another thread, relative to running alone, and the
    work's own rate with and without the counter. ``switch_interval`` (restored after) is the GIL's forced-switch
    interval while both run: the default 5 ms lets a thread that dropped the GIL for a short C call wait a whole
    interval to get it back (the convoy effect), so the held share is measured at a fine interval."""
    def count(stop, out):
        n = 0
        while not stop.is_set():
            n += 1
        out.append(n)

    def run(with_work: bool) -> tuple[float, int]:
        stop, counted, calls = threading.Event(), [], [0]
        counter = threading.Thread(target=count, args=(stop, counted))

        def worker():
            while not stop.is_set():
                work()
                calls[0] += 1

        other = threading.Thread(target=worker) if with_work else None
        counter.start()
        if other is not None:
            other.start()
        stop.wait(seconds)
        stop.set()
        counter.join()
        if other is not None:
            other.join()
        return counted[0] / seconds, calls[0]

    def work_alone() -> float:
        calls, end = 0, time.perf_counter() + seconds / 3
        while time.perf_counter() < end:
            work()
            calls += 1
        return calls / (seconds / 3)

    saved = sys.getswitchinterval()
    try:
        if switch_interval is not None:
            sys.setswitchinterval(switch_interval)
        alone, _ = run(False)
        shared, calls = run(True)
    finally:
        sys.setswitchinterval(saved)
    solo = work_alone()
    return {"counter_progress": shared / alone, "calls_per_s": calls / seconds, "calls_per_s_alone": solo,
            "work_progress": (calls / seconds) / solo if solo else None}


def _gil(frames) -> dict:
    import numpy as np

    from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples
    from widgets.spotify_visualizer.feature_replay import ProductionLaneEngine, configure_offline_controller
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    def pure_python():
        total = 0
        for i in range(20_000):
            total += i * i
        return total

    works = {
        "pure_python (GIL held)": pure_python,
        "sleep 1 ms (GIL released)": lambda: time.sleep(0.001),
    }
    rng = np.random.default_rng(1)
    for size in (480, 1024, 2048, 1 << 20):
        data = rng.standard_normal(size).astype(np.float32)
        works[f"numpy.fft.rfft n={size}"] = lambda d=data: np.fft.rfft(d)
    # The production analysis on a configured worker state (Spectrum: shaping on; Bubble: off), the clip's blocks.
    history = [np.frombuffer(f.capture_history.pcm_f32le, dtype="<f4")[-480:].copy() for f in frames]
    for mode in ("spectrum", "bubble"):
        engine = ProductionLaneEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=GENERATION, initial_mode=mode,
                                                 engine_factory=lambda _c: engine)
        controller.engine = engine
        configure_offline_controller(controller, mode)
        state = engine._audio_worker.make_compute_snapshot()
        state._np = np
        index = [0]

        def analyse(state=state):
            compute_bars_from_samples(state, history[index[0] % len(history)])
            index[0] += 1

        works[f"compute_bars_from_samples ({mode})"] = analyse
    rows = {}
    for name, work in works.items():
        row = _counter_share(work, switch_interval=FINE_SWITCH_S)
        default = _counter_share(work)
        row["default_interval_work_progress"] = default["work_progress"]
        row["default_interval_counter_progress"] = default["counter_progress"]
        rows[name] = row
    held, released = rows["pure_python (GIL held)"]["counter_progress"], rows["sleep 1 ms (GIL released)"][
        "counter_progress"]
    for row in rows.values():
        span = released - held
        row["gil_held_share"] = max(0.0, min(1.0, (released - row["counter_progress"]) / span)) if span > 0 else None
    for name, row in rows.items():
        print(f"[gil] {name:40s} alone {row['calls_per_s_alone']:8.0f}/s  fine: counter "
              f"{row['counter_progress']:.2f} work {row['work_progress']:.2f} held ~{row['gil_held_share']:.2f}  "
              f"default 5 ms: counter {row['default_interval_counter_progress']:.2f} work "
              f"{row['default_interval_work_progress']:.2f}", flush=True)
    return rows


def _below_normal(pid=None) -> None:
    try:
        import psutil
        (psutil.Process(int(pid)) if pid else psutil.Process()).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass


def _system() -> dict:
    try:
        import psutil
        return {"cpu_percent_1s": psutil.cpu_percent(interval=1.0), "cpu_count": psutil.cpu_count(),
                "load_note": "system-wide CPU % sampled for 1 s before the run"}
    except Exception:
        return {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--modes", nargs="*")
    parser.add_argument("--sections", nargs="*", default=["live", "take", "gil"])
    args = parser.parse_args(argv)
    _below_normal()
    from PySide6.QtCore import QCoreApplication

    import tools.expanded_visualizer_evidence as evidence

    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
    clips = [evidence.shipped_clip(args.seconds, name) for name in evidence.STUDIO_CLIPS]
    modes = tuple(args.modes or _modes())
    report = {"seconds": args.seconds, "clips": list(evidence.STUDIO_CLIPS), "system_before": _system()}
    if "live" in args.sections:
        rows = {}
        for mode in modes:
            acc: dict = {}
            for clip in clips:
                for key, values in _live(clip.frames, mode).items():
                    if isinstance(values, list):
                        acc.setdefault(key, []).extend(values)
                    else:
                        acc[key] = acc.get(key, 0) + values
            clean = [t for t, o in zip(acc["total"], acc["gc_overlap"]) if not o]
            ticks = len(acc["total"])
            row = {
                "ticks": ticks,
                "callbacks_per_tick": sum(acc["callbacks"]) / ticks, "analyses_per_tick": sum(acc["analyses"]) / ticks,
                "per_callback_p50": _ms(acc["per_callback"], 50), "per_callback_p90": _ms(acc["per_callback"], 90),
                "per_analysis_p50": _ms(acc["per_analysis"], 50), "per_analysis_p90": _ms(acc["per_analysis"], 90),
                "push_p50": _ms(acc["push"], 50), "step_p50": _ms(acc["step"], 50),
                "tick_p50": _ms(acc["tick"], 50), "tick_p90": _ms(acc["tick"], 90),
                "total_p50": _ms(acc["total"], 50), "total_p90": _ms(acc["total"], 90),
                "total_mean": 1000.0 * statistics.fmean(acc["total"]),
                "total_p50_no_gc": _ms(clean, 50), "total_p90_no_gc": _ms(clean, 90),
                "gc_overlapped_ticks": ticks - len(clean), "gc_ms": acc["gc_ms"], "gc_count": acc["gc_count"],
            }
            rows[mode] = row
            print(f"[live] {mode:18s} total {row['total_p50']:.3f}/{row['total_p90']:.3f} (mean "
                  f"{row['total_mean']:.3f}; no-GC {row['total_p50_no_gc']:.3f}) = callbacks "
                  f"{row['callbacks_per_tick']:.2f} x {row['per_callback_p50']:.3f} + step {row['step_p50']:.3f} + "
                  f"analyses {row['analyses_per_tick']:.2f} x {row['per_analysis_p50']:.3f} + tick "
                  f"{row['tick_p50']:.3f}  (gc {row['gc_overlapped_ticks']} ticks, {row['gc_ms']:.0f} ms)",
                  flush=True)
        report["live"] = rows
    if "take" in args.sections:
        report["take"] = _take(clips, modes)
    if "gil" in args.sections:
        report["gil"] = _gil(clips[0].frames)
    report["system_after"] = _system()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "live_cost.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
