"""N2.6's proof (Current_Plan.md item 8b): the per-pass GPU timer service (D8 plus 2), through ``rendering.native``.

The module (``release/native_module``, built on GitHub) is loaded the product's way and driven in one child process per
graphics API (Qt Quick's API is process-wide): OpenGL, Vulkan on the module's own instance and devices (D6), D3D11 and
D3D12. No window is ever visible: the hidden hosts never show one, and the window round's window is kept off screen by
the tests' pattern (``tests/_invisible_windows.py``). The timer brackets each whole pass the frame driver records
(``native/core/src/gpu_timer.h``): raw timestamps on Vulkan, ``GL_TIME_ELAPSED`` on OpenGL; on D3D11 and D3D12 QRhi gives
only the whole frame (``lastCompletedGpuTime``), which the timer reads on every backend whose QRhi has timestamps.

Rounds (each per API):
  off      off is free: a hidden host (its QRhi without timestamps) recording the probe every frame, the timer never on:
           the driver holds no timer, no edge touched one, nothing queued, and the process holds no timer and no query
           object (counted by the module). Switched on: a timer, query objects on Vulkan and OpenGL (none on D3D, whose
           per-pass form does not exist), the probe timed every frame and its image unchanged, no Python thread state on
           the edge. Switched off again: everything released without a wait, then the same counts as never-on.
           Negative control: the timer switched off with keep_when_off holds its objects and fails those counts.
  scaling  correctness against a known-cost pass (load_pass.h): one pass of N full-target draws of a fixed fragment loop,
           N in DRAWS, on a hidden host whose QRhi has timestamps. The per-pass figure lies on a line in N (fit, a
           measurable per-draw cost, every N on the line); QRhi's frame figure, where it exists, agrees with the
           pass's at the largest N; results are read latched (at a later frame edge, never waited for). Negative control:
           the bracket recorded empty in front of the same pass does not grow with N.
  window   a real Qt Quick window rendered by Qt's render loop (frames in flight), kept off screen, its QRhi with
           timestamps: the load pass made GPU-bound (about WINDOW_PASS_MS per frame, from the scaling round's per-draw
           cost), at a quarter, half and all of it. The frame figure (every backend) and the per-pass figure (Vulkan,
           OpenGL) scale; results arrive latched, a result not ready at the next edge is read at a later one, no read
           waits, the reads cost little CPU and every frame is timed. Negative control: the same frames read with a
           blocking wait show the stall (Vulkan: every earlier frame's results waited for at the edge; OpenGL: the naive
           read right after the pass in its own frame, since Qt's OpenGL loop has finished the previous frame on the
           GPU by the next edge, where build round 1's wait cost 0.025 ms). The window destroyed while it animates
           releases the timer on the render thread.
  (environment) before the window round, an off-screen window with Qt alone must present frames on this API
           (host_check.qt_alone_window_frames); otherwise the verdict names the display, not the core.
  trace    the figures reach the frame trace as its other durations do: drained samples written through
           ``rendering.native.gpu_timing.write_to_frame_trace`` into a ``FrameTraceSink``, read back by
           ``tools/frame_trace_report.py``, whose medians equal the samples'. Negative control: a trace without the
           timer's records has no GPU lines.
Across APIs: the Vulkan and OpenGL forms time the same pass alike (per-draw cost within timer_analysis.FORMS_RATIO).
On Vulkan the instance has the Khronos validation layer with synchronisation validation when --layer-path gives it; every
message is attributed and only Qt 6.12.0's recorded defects are excused, by id (vk_validation.py).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/timer_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan d3d11 d3d12] [--rounds off scaling window trace] [--label n26_timer]
Evidence: .artifacts/evidence/native_core/n2_6/<date>_<label>/ (summary.json, one frame-trace report per API). Exit 0
whenever the harness ran; the verdict is the last printed line ("N26 VERDICT PASS" or "N26 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import host_check  # noqa: E402  (native/core/python)
import timer_analysis as ta  # noqa: E402
import vk_validation  # noqa: E402

APIS = host_check.APIS
ROUNDS = ("off", "scaling", "window", "trace")
PER_PASS_APIS = ("opengl", "vulkan")      # the service's two native forms (D5.3)
HOST_PIXELS = (320, 180)
OFF_FRAMES = 30
DRAIN_FRAMES = 12                         # more than the timer's ring (8): a stopped timer's objects have gone by then
LOAD = {"width": 1024, "height": 1024, "iterations": 128}
DRAWS = (1, 2, 4, 8, 16)
WARM_FRAMES = 6
MEASURE_FRAMES = 40
WINDOW_PASS_MS = 12.0                     # the window round's GPU-bound pass: longer than a frame at 60 to 165 Hz
WINDOW_DEFAULT_DRAWS = 192                # when the scaling round gave no per-draw cost
WINDOW_MAX_DRAWS = 1024
WINDOW_SAMPLES = 40
WINDOW_WAIT_S = 30.0
FRAME_FIGURE_MARGIN = 4                   # edges: QRhi's frame figure is read a few frames after its frame
TRACE_DRAWS = 8
CHILD_TIMEOUT_S = 900
KIND = {"frame": 0, "probe": 1, "surface": 2, "load": 3}
_ALLOWED_ENV: set[str] = set()


# --------------------------------------------------------------------------------------------------------- helpers

def _driver(host) -> dict:
    return host_check._driver(host.state())


def _of_kind(samples, kind: str) -> list:
    return [s for s in samples if s.kind == KIND[kind]]


def _measure(host, draws: int, timing: str = "pass") -> dict:
    """One draw count on a hidden host: warm, drain, measure, drain."""
    host.set_load(**LOAD, draws=int(draws), timing=timing)
    host.frames(WARM_FRAMES)
    host.gpu_samples()
    host.frames(MEASURE_FRAMES)
    samples = host.gpu_samples()
    load = _of_kind(samples, "load")
    frame = _of_kind(samples, "frame")
    return {"draws": int(draws), "timing": timing, "load_n": len(load), "frame_n": len(frame),
            "load_median_ms": ta.median_ms(s.nanoseconds for s in load),
            "frame_median_ms": ta.median_ms(s.nanoseconds for s in frame),
            "latencies": sorted({s.latency for s in load if s.latency is not None}),
            "_samples": samples}


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith("_")}


# --------------------------------------------------------------------------------------------------------- off

def round_off(core, engine, app, api: str, out: Path) -> dict:
    from probe_analysis import analyse

    record: dict = {}
    checks: dict = {}
    per_pass = api in PER_PASS_APIS
    item, _component = host_check._content(engine)
    host = core.hidden_host(*HOST_PIXELS)          # its QRhi without timestamps: no query object of Qt's either
    try:
        host.set_content(item)
        host.set_probe()                            # the driver records a pass every frame
        host.frames(OFF_FRAMES)
        driver = _driver(host)
        never = ta.off_verdict(driver, core.gpu_timer_live(), edges_before=0, samples=len(host.gpu_samples()))
        record["never_on"] = {"verdict": never, "driver_passes": driver.get("passes_recorded")}
        checks["never_on_holds_nothing"] = never["pass"] and driver.get("passes_recorded", 0) >= OFF_FRAMES

        passes_before = int(driver.get("passes_recorded", 0))
        host.set_gpu_timer(True)
        host.frames(OFF_FRAMES)
        on = _driver(host)
        live_on = core.gpu_timer_live()
        samples_on = host.gpu_samples()
        timer = on.get("gpu_timer") or {}
        probe_samples = _of_kind(samples_on, "probe")
        probe_passes = int(on.get("passes_recorded", 0)) - passes_before
        record["on"] = {"live": live_on, "timer": timer, "probe_samples": len(probe_samples),
                        "probe_passes": probe_passes,
                        "probe_median_ms": ta.median_ms(s.nanoseconds for s in probe_samples)}
        checks["on_holds_one_timer"] = bool(timer) and int(live_on.get("timers", 0)) == 1
        if per_pass:
            checks["on_holds_query_objects"] = int(live_on.get("queries", 0)) > 0
            # Every probe pass recorded while on was bracketed, or left untimed because its slot still held unread
            # results (counted; a result is never overwritten, the frame never waits). A hidden host's frames are not
            # paced, so on OpenGL, whose offscreen frames only flush, they run ahead of the results: build round 1,
            # 27 timed and 3 slot-busy of 30 with 4 slots (rerun on that module: 19 and 11, results 1 to 8+ frames
            # late). The paced real window (the window round) must time every frame.
            checks["every_probe_pass_timed_or_its_slot_busy"] = (
                int(timer.get("timed_passes", -1)) + int(timer.get("slot_busy_frames", 0)) == probe_passes
                and int(timer.get("over_capacity", -1)) == 0 and probe_passes >= OFF_FRAMES)
            checks["probe_figures_positive"] = bool(probe_samples) and all(s.nanoseconds > 0 for s in probe_samples)
        else:
            checks["no_per_pass_form_on_this_backend"] = (int(live_on.get("queries", -1)) == 0 and not probe_samples
                                                          and "unavailable" in str(timer.get("per_pass", "")))
        readback, analysis = host_check._probe_hidden(host, analyse)
        record["probe_with_the_timer_on"] = analysis
        checks["probe_image_unchanged_with_the_timer_on"] = bool(analysis.get("pass"))
        checks["no_python_thread_state_on_the_frame_edge"] = on.get("edges_with_python_thread_state") == 0
        checks["no_timer_error"] = not timer.get("error")

        host.set_gpu_timer(False)
        host.frames(DRAIN_FRAMES)
        edges = int(_driver(host).get("gpu_timer_edges", 0))
        tail = _of_kind(host.gpu_samples(), "probe")      # the readback's frame and the results still in flight
        host.frames(OFF_FRAMES)
        rest = _driver(host)
        again = ta.off_verdict(rest, core.gpu_timer_live(), edges_before=edges, samples=len(host.gpu_samples()))
        last = rest.get("gpu_timer_last") or {}
        record["off_again"] = {"verdict": again, "last_timer": last, "probe_samples_after_on": len(tail)}
        checks["switched_off_holds_nothing"] = again["pass"]
        checks["switched_off_without_a_wait"] = int(last.get("release_waits", -1)) == 0
        if per_pass:
            # Switched off, the objects go only once every bracket's result was read: none is lost.
            checks["every_timed_pass_read_before_release"] = (
                int(last.get("results", -1)) == int(last.get("timed_passes", -2))
                == len(probe_samples) + len(tail))

        # Negative control: the objects kept when switched off must fail the same counts.
        host.set_gpu_timer(True, keep_when_off=True)
        host.frames(10)
        host.set_gpu_timer(False)
        host.frames(DRAIN_FRAMES)
        edges = int(_driver(host).get("gpu_timer_edges", 0))
        host.gpu_samples()
        host.frames(OFF_FRAMES)
        control = ta.off_verdict(_driver(host), core.gpu_timer_live(), edges_before=edges,
                                 samples=len(host.gpu_samples()))
        record["negative_kept_when_off"] = control
        checks["negative_control_kept_objects_fail_the_off_counts"] = not control["pass"]
        host.detach()                                # the kept timer goes with the driver, outside a frame
        live = core.gpu_timer_live()
        record["after_detach"] = live
        checks["detach_released_the_kept_timer"] = live == {"timers": 0, "query_pools": 0, "queries": 0}
    finally:
        record["close"] = host.close()
        host_check._drop_item(app, item)
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- scaling

def round_scaling(core, engine, app, api: str, out: Path, shared: dict) -> dict:
    record: dict = {"draws": list(DRAWS), "load": LOAD, "tolerances": {
        "scaling_min_r2": ta.SCALING_MIN_R2, "scaling_residual": ta.SCALING_RESIDUAL,
        "scaling_residual_floor_ms": ta.SCALING_RESIDUAL_FLOOR_MS, "flat_max_slope_ratio": ta.FLAT_MAX_SLOPE_RATIO,
        "agreement_ratio": ta.AGREEMENT_RATIO, "agreement_floor_ms": ta.AGREEMENT_FLOOR_MS}}
    checks: dict = {}
    per_pass = api in PER_PASS_APIS
    host = core.hidden_host(*HOST_PIXELS, timestamps=True)
    try:
        record["host"] = {k: host.state().get(k) for k in ("backend", "qrhi_timestamps", "device_name")}
        host.set_gpu_timer(True)
        rows = {"pass": [_measure(host, n) for n in DRAWS], "before": [_measure(host, n, "before") for n in DRAWS]}
        timer = _driver(host).get("gpu_timer") or {}
        record["timer"] = timer
        record["rows"] = {k: [_public(r) for r in v] for k, v in rows.items()}
        shared["samples"] = [s for r in rows["pass"] for s in r["_samples"]]
        frames_present = all(r["frame_n"] > 0 for r in rows["pass"])
        record["qrhi_frame_figure_in_offscreen_frames"] = frames_present
        if frames_present:
            frame_scaling = ta.scaling_verdict({r["draws"]: r["frame_median_ms"] for r in rows["pass"]})
            record["frame_scaling"] = frame_scaling
            checks["qrhi_frame_figure_scales"] = frame_scaling["pass"]
        if per_pass:
            scaling = ta.scaling_verdict({r["draws"]: r["load_median_ms"] for r in rows["pass"]})
            flat = ta.flat_verdict({r["draws"]: r["load_median_ms"] for r in rows["before"]},
                                   scaling["fit"]["slope"])
            latencies = [lat for r in rows["pass"] + rows["before"] for lat in r["latencies"]]
            latched = ta.latched_verdict(timer, latencies, require_late_read=False)
            record.update(scaling=scaling, negative_empty_bracket=flat, latched=latched)
            shared["slope_ms"] = scaling["fit"]["slope"]
            checks["pass_figure_scales_with_its_draws"] = scaling["pass"]
            checks["every_count_timed"] = all(r["load_n"] >= MEASURE_FRAMES - 4 for r in rows["pass"])
            checks["negative_control_empty_bracket_does_not_scale"] = flat["pass"]
            checks["read_latched_never_waited"] = latched["pass"]
            if frames_present:
                top = rows["pass"][-1]
                agreement = ta.agreement_verdict(top["load_median_ms"], top["frame_median_ms"])
                record["agreement_with_the_frame"] = agreement
                checks["pass_figure_agrees_with_qrhis_frame"] = agreement["pass"]
        else:
            if frames_present:
                shared["slope_ms"] = record["frame_scaling"]["fit"]["slope"]
            checks["no_per_pass_figure_on_this_backend"] = all(r["load_n"] == 0 for r in rows["pass"])
        checks["no_timer_error"] = not timer.get("error")
        host.clear_load()
        host.set_gpu_timer(False)
        host.frames(DRAIN_FRAMES)
        host.gpu_samples()
        checks["switched_off_holds_nothing"] = core.gpu_timer_live() == {"timers": 0, "query_pools": 0, "queries": 0}
    finally:
        record["close"] = host.close()
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- window

def _collect(app, host, after_edge: int, counts: dict) -> dict:
    """Drains the window host's samples until ``counts[kind]`` of each kind recorded after ``after_edge`` arrived (a
    frame figure, whose frame Qt does not name, counts when read FRAME_FIGURE_MARGIN edges after it)."""
    got: dict = {kind: [] for kind in counts}

    def enough() -> bool:
        for s in host.gpu_samples():
            for kind in counts:
                if s.kind != KIND[kind]:
                    continue
                if (s.frame > after_edge) if s.frame >= 0 else (s.read_at > after_edge + FRAME_FIGURE_MARGIN):
                    got[kind].append(s)
        return all(len(got[kind]) >= count for kind, count in counts.items())

    host_check._wait_until(app, enough, timeout=WINDOW_WAIT_S)
    return got


def round_window(core, engine, app, api: str, out: Path, shared: dict) -> dict:
    import shiboken6

    record: dict = {}
    checks: dict = {}
    per_pass = api in PER_PASS_APIS
    slope = shared.get("slope_ms")
    heavy = (WINDOW_DEFAULT_DRAWS if not slope or slope <= 0
             else max(16, min(WINDOW_MAX_DRAWS, int(math.ceil(WINDOW_PASS_MS / slope)))))
    record["heavy_draws"] = heavy
    record["per_draw_ms_from_scaling"] = slope
    item, _component = host_check._content(engine)    # it animates: Qt's render loop renders frame after frame
    window = host_check._off_screen_window()
    config = window.graphicsConfiguration()
    config.setTimestamps(True)                           # Qt's QRhi times its whole frames (read before the first show)
    window.setGraphicsConfiguration(config)
    item.setParentItem(window.contentItem())
    host = core.attach_host(window)                      # before the window is first shown (D6 on Vulkan)
    try:
        host.set_gpu_timer(True)
        host_check._show(window)
        checks["frames_arrive"] = host_check._wait_until(app, lambda: window.isExposed()
                                                         and _driver(host).get("edges", 0) >= 10)
        steps = {}
        wanted = {"frame": WINDOW_SAMPLES, **({"load": WINDOW_SAMPLES} if per_pass else {})}
        for share in (4, 2, 1):
            draws = max(1, heavy // share)
            host.set_load(**LOAD, draws=draws)
            got = _collect(app, host, int(_driver(host).get("edges", 0)), wanted)
            frames = got["frame"]
            row = {"draws": draws, "frame_n": len(frames), "frame_median_ms": ta.median_ms(s.nanoseconds for s in frames)}
            if per_pass:
                loads = got["load"]
                row.update(load_n=len(loads), load_median_ms=ta.median_ms(s.nanoseconds for s in loads),
                           latencies=sorted(s.latency for s in loads))
            steps[draws] = row
        record["steps"] = {str(k): {kk: vv for kk, vv in v.items() if kk != "latencies"} for k, v in steps.items()}
        driver = _driver(host)
        timer = dict(driver.get("gpu_timer") or {})
        record["timer_latched"] = timer
        record["driver"] = {k: driver.get(k) for k in ("edges", "edges_on_gui_thread", "edges_with_python_thread_state",
                                                      "load_passes_recorded", "gpu_timer_edges", "gpu_samples_dropped")}
        frame_ok = all(row["frame_n"] >= WINDOW_SAMPLES for row in steps.values())
        checks["qrhi_frame_figures_arrive"] = frame_ok
        if frame_ok:
            frame_scaling = ta.scaling_verdict({d: row["frame_median_ms"] for d, row in steps.items()})
            record["frame_scaling"] = frame_scaling
            checks["qrhi_frame_figure_scales"] = frame_scaling["pass"]
        checks["frame_edge_on_qts_render_thread"] = driver.get("edges_on_gui_thread") == 0
        checks["no_python_thread_state_on_the_frame_edge"] = driver.get("edges_with_python_thread_state") == 0
        checks["no_timer_error"] = not timer.get("error")
        if per_pass:
            load_ok = all(row.get("load_n", 0) >= WINDOW_SAMPLES for row in steps.values())
            checks["pass_figures_arrive"] = load_ok
            if load_ok:
                scaling = ta.scaling_verdict({d: row["load_median_ms"] for d, row in steps.items()})
                record["scaling"] = scaling
                checks["pass_figure_scales"] = scaling["pass"]
                top = steps[max(steps)]
                agreement = ta.agreement_verdict(top["load_median_ms"], top["frame_median_ms"])
                record["agreement_with_the_frame"] = agreement
                checks["pass_figure_agrees_with_qrhis_frame"] = agreement["pass"]
            latencies = [lat for row in steps.values() for lat in row.get("latencies", [])]
            latched = ta.latched_verdict(timer, latencies, require_late_read=True)
            record["latched"] = latched
            record["latency_histogram"] = timer.get("latency_histogram")
            checks["read_latched_never_waited"] = latched["pass"]
            # Paced by Qt's render loop, no frame's slot is still busy: every frame is timed.
            checks["every_frame_timed"] = (int(timer.get("slot_busy_frames", -1)) == 0
                                           and int(timer.get("over_capacity", -1)) == 0)

            # Negative control: the same frames, every result read with a blocking wait.
            host.set_gpu_timer(True, wait_for_results=True)
            control_samples = _collect(app, host, int(_driver(host).get("edges", 0)),
                                       {"load": WINDOW_SAMPLES // 2})["load"]
            control_timer = dict(_driver(host).get("gpu_timer") or {})
            stall = ta.stall_control_verdict(control_timer, timer)
            record["negative_waiting_read"] = dict(stall, samples=len(control_samples))
            checks["negative_control_waiting_read_shows_the_stall"] = stall["pass"]
            host.set_gpu_timer(True, wait_for_results=False)
        else:
            checks["no_query_object_of_ours"] = int(core.gpu_timer_live().get("queries", -1)) == 0

        # Destroyed while it animates: the scene graph's invalidation releases the timer on Qt's render thread.
        shiboken6.delete(window)
        window = None
        host_check._flush_deletes(app)
        live = core.gpu_timer_live()
        record["after_destroy"] = live
        checks["window_destroyed_released_the_timer"] = live == {"timers": 0, "query_pools": 0, "queries": 0}
    finally:
        if window is not None and shiboken6.isValid(window):
            shiboken6.delete(window)
        record["close"] = host.close()
        host_check._drop_item(app, item)
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- trace

_REPORT_LINE = re.compile(r"^screen=(?P<screen>-?\d+) (?:gpu_frame|gpu_pass=(?P<kind>\w+)) n=(?P<n>\d+) "
                          r"median_ms=(?P<median>[\d.]+)")


def _report(trace: Path) -> str:
    """tools/frame_trace_report.py on one trace, as the lead runs it."""
    from tools import frame_trace_report

    text = io.StringIO()
    with patch.object(sys, "argv", ["frame_trace_report.py", str(trace)]), contextlib.redirect_stdout(text):
        frame_trace_report.main()
    return text.getvalue()


def _gpu_lines(report: str) -> dict:
    found = {}
    for line in report.splitlines():
        match = _REPORT_LINE.match(line)
        if match:
            found[match.group("kind") or "frame"] = {"n": int(match.group("n")),
                                                     "median_ms": float(match.group("median"))}
    return found


def _write_trace(path: Path, samples) -> tuple[int, dict]:
    from core.performance.frame_trace import FrameTraceSink
    from rendering.native.gpu_timing import write_to_frame_trace

    sink = FrameTraceSink(path)
    written = write_to_frame_trace(sink, samples, screen_index=0)
    return written, sink.close()


def round_trace(core, engine, app, api: str, out: Path, shared: dict) -> dict:
    record: dict = {}
    checks: dict = {}
    samples = shared.get("samples")
    if not samples:
        host = core.hidden_host(*HOST_PIXELS, timestamps=True)
        try:
            host.set_gpu_timer(True)
            samples = _measure(host, TRACE_DRAWS)["_samples"]
            host.clear_load()
            host.set_gpu_timer(False)
            host.frames(DRAIN_FRAMES)
            host.gpu_samples()
        finally:
            host.close()
    expected = {}
    for name, kind in KIND.items():
        values = [s.nanoseconds / 1e6 for s in samples if s.kind == kind]
        if values:
            expected[name] = {"n": len(values), "median_ms": round(statistics.median(values), 3)}
    trace = out / f"n26_trace_{api}.bin"
    written, sink = _write_trace(trace, samples)
    report = _report(trace)
    (out / f"n26_trace_report_{api}.txt").write_text(report, encoding="utf-8")
    found = _gpu_lines(report)
    record.update(samples=len(samples), written=written, sink=sink, expected=expected, report_gpu_lines=found)
    checks["every_sample_written"] = written == len(samples) and sink.get("dropped_records") == 0
    checks["the_report_reads_every_figure"] = all(
        name in found and found[name]["n"] == want["n"] and abs(found[name]["median_ms"] - want["median_ms"]) < 5e-4
        for name, want in expected.items())
    record["figures"] = sorted(expected)   # on D3D only QRhi's frame figure, where its offscreen frames carry one
    if api in PER_PASS_APIS:
        checks["the_pass_figure_is_in_the_trace"] = "load" in found
    # Negative control: a trace without the timer's records has no GPU line.
    empty = out / f"n26_trace_{api}_empty.bin"
    _write_trace(empty, [])
    control = _gpu_lines(_report(empty))
    record["negative_no_timer_records"] = control
    checks["negative_control_no_records_no_gpu_lines"] = control == {}
    for path in (trace, empty):
        path.unlink(missing_ok=True)
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- child

def child(args) -> dict:
    root = host_check._root(args.repo)
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    api_enum = QSGRendererInterface.GraphicsApi
    QQuickWindow.setGraphicsApi({"opengl": api_enum.OpenGL, "vulkan": api_enum.Vulkan,
                                 "d3d11": api_enum.Direct3D11, "d3d12": api_enum.Direct3D12}[args.api])
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlEngine

    app = QGuiApplication([sys.argv[0]])
    from rendering.native import NativeCoreUnavailable, load

    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    try:
        core = load((root / args.module_dir) if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    except NativeCoreUnavailable as exc:
        record["error"] = f"the module did not load: {exc.reason}"
        return record
    record["module_loaded"] = True
    record["runtime"] = dict(core.info)
    out = Path(args.out_dir)
    vulkan = args.api == "vulkan"
    if vulkan:
        instance = core.vulkan_instance(validation=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    shared: dict = {}
    try:
        if "window" in args.rounds:
            if vulkan:
                core.set_vulkan_phase("n26 environment")
            record["qt_alone_window_frames"] = host_check.qt_alone_window_frames(app, engine)
        for name in args.rounds:
            if vulkan:
                core.set_vulkan_phase(f"n26 {name}")
            try:
                if name == "off":
                    record[name] = round_off(core, engine, app, args.api, out)
                elif name == "scaling":
                    record[name] = round_scaling(core, engine, app, args.api, out, shared)
                elif name == "window":
                    record[name] = round_window(core, engine, app, args.api, out, shared)
                else:
                    record[name] = round_trace(core, engine, app, args.api, out, shared)
            except Exception:
                record[name] = {"pass": False, "error": traceback.format_exc()}
        record["per_draw_ms"] = shared.get("slope_ms")
    finally:
        host_check._flush_deletes(app)
        record["live_hosts_at_end"] = core.live_hosts()
        record["timers_at_end"] = core.gpu_timer_live()
        if vulkan:
            teardown = core.destroy_vulkan_instance()
            messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
            summary = vk_validation.validation_summary(messages)
            layer = bool(record["instance"].get("validation_layer_loaded"))
            record["instance_teardown"] = teardown
            record["validation"] = {"layer_loaded": layer, "per_phase": messages.get("per_phase"),
                                    **{k: v for k, v in summary.items() if k != "groups"},
                                    "attribution": summary["groups"]}
        del engine
    return record


# --------------------------------------------------------------------------------------------------------- verdict

def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    """host_check's verdict (what failed on one API; a child that stopped early reports that one reason alone), plus no
    timer or query object of the core's left at the end."""
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("timers_at_end") or {}
        if any(live.get(key) for key in ("timers", "query_pools", "queries")):
            failed.append(f"{api}: timers left at the end ({live})")
    return not failed, failed


def forms_check(results: dict) -> dict | None:
    """The two native forms against each other, when both ran the scaling round."""
    slopes = {api: (results.get(api, {}).get("scaling") or {}).get("scaling", {}).get("fit", {}).get("slope")
              for api in PER_PASS_APIS}
    if not all(api in results and "scaling" in results[api].get("rounds", []) for api in PER_PASS_APIS):
        return None
    return ta.forms_verdict(slopes["vulkan"], slopes["opengl"])


def _failed_checks(record: dict) -> list[str]:
    failed = []
    for name in record.get("rounds", []):
        entry = record.get(name, {})
        failed += [f"{name}: {k}" for k, v in entry.get("checks", {}).items() if not v]
    return failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--label", default="n26_timer")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=APIS, help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child:
        try:
            record = child(args)
        except Exception:
            text = traceback.format_exc()
            record = {"api": args.api, "error": text.strip().splitlines()[-1], "traceback": text}
        args.child_json.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return 0

    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)   # inherited by the children
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n2_6", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in args.apis:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", (exc.stderr or b"").decode(errors="replace") if isinstance(
                exc.stderr, bytes) else str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "rounds": list(args.rounds), "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        record["failed_checks"] = _failed_checks(record)
        results[api] = record

    verdicts = {api: api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    forms = forms_check(results)
    if forms is not None and not forms["pass"]:
        failed.append(f"forms: the Vulkan and OpenGL per-draw costs disagree ({forms})")
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "require_validation": args.require_validation, "forms": forms,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "failed_checks": {api: record.get("failed_checks", []) for api, record in results.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
        print(f"  per draw: {results[api].get('per_draw_ms')} ms")
        v = results[api].get("validation")
        if v:
            print(f"  validation: layer {'loaded' if v.get('layer_loaded') else 'NOT loaded'}, "
                  f"excused {v.get('recorded_qt_defects_excused')}, unexplained errors {v.get('unexplained_errors')}, "
                  f"warnings {v.get('unexplained_warnings')}")
    if forms is not None:
        print(f"forms: {'PASS' if forms['pass'] else 'FAIL'} (Vulkan over OpenGL per draw: {forms.get('ratio')})")
    print(f"evidence: {out / 'summary.json'}")
    print("N26 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
