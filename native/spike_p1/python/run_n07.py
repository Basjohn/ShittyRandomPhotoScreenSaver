"""N0.7 driver (D9's proof, Current_Plan.md item 8b): async GPU jobs beside Qt Quick on the module's Vulkan device.

Harness only, nothing ships. Decision: Docs/Future_Work/Native_Core_P3_Decisions.md D9 (with the lead's 12 Nov
amendment); Qt facts and build order: Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md (sections B, C, H). Built on
N0.6's context (run_n06.py): our VkInstance and VkDevice with the second queue in Qt's graphics family (family 0,
index 1). Never shows a window (the host is QQuickRenderControl, never shown) and never sets an environment variable.

The module's side (src/vk_n07.cpp): one job thread (parked on a condition variable, every return from the wait
counted) with its own QRhi on our device and the second queue; self-contained jobs (an upload: a 4K photo generated
on the job thread, uploaded, its mips generated; the heavy job: the edge field's five compute stages ported from
rendering/quick/scene3d/edge_field.py, at the field size, repeated) writing a back slot, the completion edge
QRhi::finish() on the job thread, then one atomic generation edge (the latch); the frame driver of the hidden host
reads the edge at frame start and swaps (Qt's QRhi imports the slot with createFrom and copies a region of it out).
The in-frame form records the same bodies into Qt's frame command buffer. Frames are paced at the display's period
and completed with QRhi::finish() each (so completion is measurable); Qt's frame GPU time comes from Qt's own
timestamps (QQuickGraphicsConfiguration::setTimestamps; QRhiVulkan reports an offscreen frame's time two frames
later, at the next begin of the same frame slot, and the driver realigns it).

Rounds (one GitHub build of the module serves all of them):
  jobs     round 1: the probe (a second QRhi on our VkDevice with the second queue: created, on our device, its queue
           distinct from Qt's, an upload read back on it); the upload job against the in-frame upload (mip 0 and
           mip 4 hashed through Qt's import of the slot; mip 0 against the photo's own hash; another seed as the
           negative control); the edge field job against the in-frame edge field (D9 ii; other thresholds as the
           negative control); the latch never holds a frame; no Python thread state on the job thread or in the
           frame driver (D9 iii); validation (D9 iv) recorded as owed when the layer is not installed.
  measure  D9 (i): the heavy job (--repeat edge-field builds at --field-size, every --every frames) in-frame and as
           a job, beside a no-job baseline, --passes times each in turn, --frames frames per pass at the display's
           period: Qt's frame GPU time median, p90 and p99, completion latency, late frames (complete after the
           next grid point) and missed periods; the job's own timeline; system conditions before and after every
           pass (other processes' CPU, nvidia-smi, and the per-process GPU engine counters: who else uses the GPU).
  retire   D9 (v): --cycles cycles of context, host, service, a heavy job running, then retirement while its GPU work
           is in flight: through n07_retire (render side, then quiesce with abandon) on even cycles and through the
           context's own teardown (the quiesce hook before vkDeviceWaitIdle) on odd ones; no crash, the job dropped
           unpublished, teardown order exact, handles back to the baseline plus the driver's 3 per device (N0.6
           round 5), threads and GPU heaps back, private bytes a plateau.
  rest     D9 (vi): the job thread at rest for --rest-seconds while the host renders at the display's period (the
           frame driver reads the latch every frame): zero wake-ups and zero CPU cycles on the job thread; one
           upload job afterwards as the negative control (one wake-up, cycles spent).
  owners   whose handles (D9 v, N0.6 round 5's method): --cycles cycles of each kind (host; + job service; + jobs;
           + abandon through n07_retire; + abandon through the teardown hook), the handle count after every step
           and a census after every cycle (handles by kernel object type, threads by start module and name,
           python/n07_census.py) diffed cycle to cycle; the retire round records the same per cycle.

With the Khronos validation layer installed outside the registry, add --layer-path <folder with
VkLayer_khronos_validation.json> (VK_ADD_LAYER_PATH for this process only, reported as allowed): D9 (iv) is then
checked in every round, each error grouped by id, phase, instance, thread and caller modules ("attribution").

Usage (repository venv, the module built on GitHub):
  python native/spike_p1/python/run_n07.py --module-dir release/native_module --round jobs --label n07_jobs
  python native/spike_p1/python/run_n07.py --module-dir release/native_module --round measure --label n07_measure
  python native/spike_p1/python/run_n07.py --module-dir release/native_module --round retire --label n07_retire
  python native/spike_p1/python/run_n07.py --module-dir release/native_module --round rest --label n07_rest
Evidence: .artifacts/evidence/native_core/n07/<date>_<label>/summary.json. Exit 0 whenever the probe ran; the
verdict is in the JSON and the last printed line ("N07 VERDICT ...").
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import n07_census  # noqa: E402
from run_n06 import (  # noqa: E402
    DRIVER_HANDLES_PER_DEVICE,
    EXPECTED_TEARDOWN,
    GPU_HEAP_TOLERANCE_MIB,
    HANDLE_TOLERANCE,
    PRIVATE_PLATEAU_TOLERANCE_MIB,
    THREAD_TOLERANCE,
    _counters,
    _delta,
    _slope,
    environment_record,
    messenger_errors_unexplained,
    use_layer_path,
    validation_summary,
    validation_warnings,
)
from run_spike import HEIGHT, NATIVE_QML, WIDTH, _import_native, _ptr  # noqa: E402

FIELD_SIZE = (3840, 2160)   # "the edge field at 4K": the field and its photograph at 4K (the product's is 768 long)
UPLOAD_SEED = 11            # the upload job's photo; UPLOAD_SEED + 1 is the negative control
LOW, HIGH = 0.04, 0.20      # edge thresholds; LOW + NEGATIVE_LOW_STEP is the negative control
NEGATIVE_LOW_STEP = 0.05
LATCH_BOUND_US = 2000.0     # the latch read and swap per frame (a swap imports a view and records a copy; no wait)
FLAG_TRIGGER, FLAG_SWAP, FLAG_INFRAME, FLAG_READBACK = 1, 2, 4, 8
GPU_REPORT_LAG = 2          # QRhiVulkan: an offscreen frame's GPU time is read at the next begin of its slot (2 slots)
REQUIRED = ("n06_context_create", "n06_context_destroy", "n07_attach_window", "n07_service_start", "n07_run",
            "n07_retire", "n07_photo_hash", "n07_service_stats")


def _evidence_dir(label: str) -> Path:
    sys.path.insert(0, str(REPO_ROOT))
    from tools import artifact_paths

    folder = artifact_paths.evidence_dir("native_core", "n07", label)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# --------------------------------------------------------------------- statistics

def _q(ordered: list[float], q: float) -> float:
    return ordered[min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))]


def describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {"n": len(values), "median": round(statistics.median(ordered), 4), "p90": round(_q(ordered, 0.9), 4),
            "p99": round(_q(ordered, 0.99), 4), "max": round(ordered[-1], 4),
            "mean": round(statistics.fmean(ordered), 4)}


def analyse_run(run: dict) -> dict:
    """Per-frame figures of one n07_run: Qt's frame GPU time realigned to its frame, completion latency from the
    frame's grid point, late frames (completed after the next grid point), the latch's cost, the jobs' timelines."""
    period = run.get("period_ms", 0.0)
    driver = run.get("driver", {})
    scheduled, start, complete = run.get("scheduled_ms", []), run.get("start_ms", []), run.get("complete_ms", [])
    reported = driver.get("qt_gpu_reported_ms", [])
    flags = driver.get("flags", [])
    n = min(len(scheduled), len(complete))
    # reported[i] is frame i - 2's GPU time; the first two belong to the previous run's last frames.
    gpu_by_frame = {i - GPU_REPORT_LAG: v for i, v in enumerate(reported) if i >= GPU_REPORT_LAG and v > 0.0}
    latency = [complete[i] - scheduled[i] for i in range(n)]
    late = [i for i in range(n) if complete[i] > scheduled[i] + period]
    trigger_frames = [i for i, f in enumerate(flags) if f & FLAG_TRIGGER]
    inframe_frames = [i for i, f in enumerate(flags) if f & FLAG_INFRAME]
    jobs = run.get("jobs", [])
    swaps = driver.get("swaps", [])
    triggers = {t.get("request_id"): t for t in driver.get("triggers", []) if "request_id" in t}
    timeline = []
    for job in jobs:
        t = triggers.get(job.get("id"))
        swap = next((s for s in swaps if s.get("kind") == job.get("kind")
                     and s.get("generation") == job.get("generation") and job.get("generation")), None)
        timeline.append({
            "id": job.get("id"), "kind": job.get("kind"), "abandoned": job.get("abandoned"),
            "queue_wait_ms": round(job["started_ms"] - job["submitted_ms"], 3),
            "cpu_half_ms": round(job["cpu_done_ms"] - job["started_ms"], 3),
            "record_ms": round(job["gpu_submitted_ms"] - job["cpu_done_ms"], 3),
            "gpu_wait_ms": round(job["complete_ms"] - job["gpu_submitted_ms"], 3),
            "submit_to_publish_ms": round(job["published_ms"] - job["submitted_ms"], 3) if job.get("generation") else None,
            "trigger_frame": t.get("frame") if t else None,
            "swap_frame": swap.get("frame") if swap else None,
            "frames_trigger_to_swap": (swap["frame"] - t["frame"]) if (swap and t) else None,
            "job_qrhi_gpu_reported_ms": job.get("gpu_reported_ms"),
            "error": job.get("error"),
        })
    gpu_trigger = [gpu_by_frame[i] for i in inframe_frames if i in gpu_by_frame]
    gpu_other = [v for i, v in gpu_by_frame.items() if i not in inframe_frames]
    return {
        "frames": n, "period_ms": period, "missed_periods": run.get("missed_periods"),
        "high_resolution_timer": run.get("high_resolution_timer"),
        "qt_frame_gpu_ms": describe(list(gpu_by_frame.values())),
        "qt_frame_gpu_ms_inframe_job_frames": describe(gpu_trigger),
        "qt_frame_gpu_ms_other_frames": describe(gpu_other),
        "completion_latency_ms": describe(latency),
        "start_lag_ms": describe([start[i] - scheduled[i] for i in range(min(len(start), n))]),
        "late_frames": len(late), "late_fraction": round(len(late) / n, 5) if n else None,
        "late_frame_indices": late[:200],
        "triggers": len(trigger_frames), "inframe_jobs_recorded": len(inframe_frames),
        "inframe_record_cpu_ms": describe(driver.get("inframe_record_ms", [])),
        "latch_us": describe(driver.get("latch_us", [])),
        "hook_us": describe(driver.get("hook_us", [])),
        "swaps": len(swaps),
        "jobs": timeline,
        "job_gpu_wait_ms": describe([j["gpu_wait_ms"] for j in timeline if not j["abandoned"]]),
        "job_submit_to_publish_ms": describe([j["submit_to_publish_ms"] for j in timeline
                                              if j["submit_to_publish_ms"] is not None]),
        "errors": driver.get("errors", []),
    }


# --------------------------------------------------------------------- system conditions

def gpu_engine_processes() -> dict:
    """The per-process GPU engine utilisation Windows counts (\\GPU Engine(*)\\Utilization Percentage, one sample):
    which other processes use the GPU, and on which engine."""
    command = ("(Get-Counter -Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction SilentlyContinue)"
               ".CounterSamples | Select-Object InstanceName, CookedValue | ConvertTo-Json -Compress")
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                              capture_output=True, text=True, timeout=60,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        samples = json.loads(proc.stdout) if proc.stdout.strip() else []
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"error": str(exc)}
    if isinstance(samples, dict):
        samples = [samples]
    per_pid: dict[int, dict[str, float]] = {}
    for s in samples:
        m = re.search(r"pid_(\d+)_.*engtype_([A-Za-z0-9]+)", str(s.get("InstanceName", "")))
        if not m:
            continue
        pid, engine = int(m.group(1)), m.group(2)
        per_pid.setdefault(pid, {})
        per_pid[pid][engine] = per_pid[pid].get(engine, 0.0) + float(s.get("CookedValue") or 0.0)
    own = os.getpid()
    names: dict[int, str] = {}
    try:
        import psutil

        for pid in per_pid:
            try:
                names[pid] = psutil.Process(pid).name()
            except Exception:  # noqa: BLE001 - a process that ended between the sample and the lookup
                names[pid] = "?"
    except ImportError:
        pass
    others = [{"pid": pid, "name": names.get(pid, "?"),
               "engines_percent": {k: round(v, 2) for k, v in engines.items() if v >= 0.05}}
              for pid, engines in per_pid.items() if pid != own and sum(engines.values()) >= 1.0]
    return {"own_pid": own, "own_engines_percent": {k: round(v, 2) for k, v in per_pid.get(own, {}).items()},
            "other_processes_using_gpu": sorted(others, key=lambda o: -sum(o["engines_percent"].values())),
            "another_process_uses_gpu": bool(others)}


def nvidia_smi() -> dict:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"available": False}
    fields = "utilization.gpu,utilization.memory,clocks.gr,clocks.mem,temperature.gpu,power.draw,pstate"
    try:
        out = subprocess.run([smi, f"--query-gpu={fields}", "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        values = [v.strip() for v in out.stdout.splitlines()[0].split(",")]
        return {"available": True, **dict(zip(fields.split(","), values))}
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        return {"available": True, "error": str(exc)}


class Conditions:
    def __init__(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from tools.bench_stability import SystemSampler

            self._sampler = SystemSampler()
        except Exception as exc:  # noqa: BLE001 - conditions are recorded, never required
            self._sampler = None
            self._error = str(exc)

    def sample(self) -> dict:
        record = {"at": time.strftime("%H:%M:%S"), "nvidia_smi": nvidia_smi(), "gpu_engines": gpu_engine_processes()}
        if self._sampler is not None:
            record["system"] = self._sampler.sample()
        else:
            record["system_error"] = self._error
        return record


# --------------------------------------------------------------------- the hidden host

class Host:
    """The spike scene in a hidden Qt Quick host (QQuickRenderControl, never shown) on our device, Qt's GPU
    timestamps on; frames are driven by n07_run."""

    def __init__(self, native) -> None:
        self.native = native
        self.handle = None
        self.session: dict = {}
        self.error = None

    def begin(self) -> bool:
        from PySide6.QtCore import QSizeF, QUrl
        from PySide6.QtQml import QQmlComponent, QQmlEngine
        from PySide6.QtQuick import QQuickRenderControl, QQuickWindow

        self.control = QQuickRenderControl()
        self.window = QQuickWindow(self.control)  # never shown
        self.engine = QQmlEngine()
        self.component = QQmlComponent(self.engine)
        self.root = None
        self.native.n07_attach_window(_ptr(self.window))
        self.component.setData(NATIVE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            self.error = self.component.errorString()
            return False
        self.root.setParentItem(self.window.contentItem())
        self.window.setGeometry(0, 0, WIDTH, HEIGHT)
        self.window.contentItem().setSize(QSizeF(WIDTH, HEIGHT))
        self.root.setSize(QSizeF(WIDTH, HEIGHT))
        try:
            # The offscreen target keeps its contents between frames (PreserveColorContents): without it Qt 6.12's
            # offscreen render pass (initialLayout UNDEFINED, no external subpass dependency) is a WRITE_AFTER_WRITE
            # hazard between frames under synchronisation validation (src/gui_helpers.h). Same pixels.
            self.session = self.native.quick_session_begin(_ptr(self.control), _ptr(self.window), WIDTH, HEIGHT, True,
                                                           True)
        except RuntimeError as exc:
            self.error = f"quick_session_begin: {exc}"
            return False
        self.handle = self.session["handle"]
        return True

    def run(self, frames: int, period_ms: float, config: dict) -> dict:
        return json.loads(self.native.n07_run(self.handle, _ptr(self.root), frames, period_ms, json.dumps(config)))

    def release_render_side(self) -> dict:
        return json.loads(self.native.n07_release_render_side(self.handle)) if self.handle is not None else {}

    def end(self) -> None:
        import gc

        import shiboken6
        from PySide6.QtCore import QCoreApplication, QEvent

        if self.handle is not None:
            self.native.quick_session_end(self.handle)  # releases the frame driver's wrappers first (vk_n07)
            self.handle = None
        shiboken6.delete(self.control)  # Qt's QRhi goes with it
        if self.root is not None:
            self.root.setParentItem(None)
            self.root.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.root = None
        shiboken6.delete(self.window)
        del self.component
        del self.engine
        gc.collect()


def _app():
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
    app = QGuiApplication([sys.argv[0]])  # no window is ever shown
    return app


def _display_period(app, override: float | None) -> dict:
    screen = app.primaryScreen()
    rate = float(screen.refreshRate()) if screen is not None else 60.0
    period = override if override else 1000.0 / (rate if rate > 1.0 else 60.0)
    return {"primary_screen_refresh_hz": rate, "period_ms": round(period, 4), "overridden": bool(override)}


def _field_size(text: str) -> tuple[int, int]:
    w, h = text.lower().split("x")
    return int(w), int(h)


def _validation(ctx: dict) -> tuple[bool, str]:
    inst = ctx.get("instance", {})
    return bool(inst.get("validation_layer_loaded")), inst.get("validation") or "validation owed"


def _validation_record(ctx: dict, teardowns: list[dict]) -> dict:
    """D9 (iv): the layer's status and, per context torn down, the messages grouped (whose call, which phase)."""
    layer, status = _validation(ctx)
    messages = [t.get("messages", {}) for t in teardowns]
    summaries = [validation_summary(m) for m in messages]
    recorded: dict = {}
    for s in summaries:
        for k, v in s["recorded_qt_defects_excused"].items():
            recorded[k] = recorded.get(k, 0) + v
    return {"layer_loaded": layer, "status": status,
            "synchronisation_validation": bool(ctx.get("instance", {}).get("synchronisation_validation")),
            "errors": sum(m.get("errors", 0) for m in messages),
            "warnings": sum(validation_warnings(m) for m in messages),
            "loader_messages": sum(m.get("warnings", 0) - validation_warnings(m) for m in messages),
            "recorded_qt_defects_excused": recorded,
            "unexplained_errors": sum(s["unexplained_errors"] for s in summaries),
            "unexplained_warnings": sum(s["unexplained_warnings"] for s in summaries),
            "per_phase": [m.get("per_phase", {}) for m in messages],
            "attribution": [g for s in summaries for g in s["groups"]]}


def _validation_checks(record: dict, checks: dict, owed: list) -> None:
    """D9 (iv): synchronisation validation on, and no error or warning apart from the recorded Qt 6.12.0 defects
    excused where they are (run_n06.QT_DEFECTS; their counts are in the record)."""
    if record["layer_loaded"]:
        checks["synchronisation_validation_on"] = record["synchronisation_validation"]
        checks["validation_clean"] = record["unexplained_errors"] == 0 and record["unexplained_warnings"] == 0
    else:
        owed.append(f"D9 (iv): {record['status']}")


def _run_until_swap(host: Host, period: float, config: dict, kind: str, frames: int = 60, rounds: int = 8) -> dict:
    """Runs `config` (one job trigger at frame 0), then plain frames until the frame driver swapped to that job's
    generation of `kind`. Returns the runs and the swap."""
    runs = [host.run(frames, period, config)]
    ids = {t["request_id"] for t in runs[0].get("driver", {}).get("triggers", []) if "request_id" in t}
    job: dict | None = None
    for _ in range(rounds + 1):
        records = _job_records(host.native, ids)
        job = records[-1] if records else None
        swaps = [s for r in runs for s in r.get("driver", {}).get("swaps", []) if s.get("kind") == kind]
        if job and job.get("generation") and any(s.get("generation") == job["generation"] for s in swaps):
            break
        runs.append(host.run(frames, period, {"mode": "none"}))
    target = job.get("generation") if job else None
    swaps = [s for r in runs for s in r.get("driver", {}).get("swaps", []) if s.get("kind") == kind]
    swap = next((s for s in swaps if target and s.get("generation") == target), None)
    return {"runs": runs, "jobs": _job_records(host.native, ids), "generation": target, "swap": swap,
            "swapped": swap is not None}


def _job_records(native, ids: set) -> list:
    """The job log's records of these request ids (a job is logged when it completes, maybe after its run)."""
    log = json.loads(native.n07_service_stats(True)).get("log", [])
    return [j for j in log if j.get("id") in ids]


def _readback(host: Host, period: float, what: str, extra: dict | None = None) -> dict:
    run = host.run(1, period, {"mode": "none", "readback": what, **(extra or {})})
    return run.get("driver", {}).get("readback", {"error": "no readback record"})


def _slim(run: dict) -> dict:
    """A run's analysis and its raw arrays (kept for the record)."""
    return {"analysis": analyse_run(run), "raw": run}


# --------------------------------------------------------------------- round 1: jobs

def round_jobs(native, out: Path, args) -> dict:
    app = _app()
    timing = _display_period(app, args.period_ms)
    period = timing["period_ms"]
    w, h = args.field_size
    ctx = json.loads(native.n06_context_create(True, "second"))
    host = Host(native)
    record: dict = {"context_ok": bool(ctx.get("ok")), "display": timing}
    start: dict = {}
    steps: dict = {}
    if ctx.get("ok") and host.begin():
        native.n06_set_phase("n07_service_start")
        start = json.loads(native.n07_service_start(w, h))
        if start.get("ok"):
            native.n06_set_phase("n07_jobs_warm")
            host.run(10, period, {"mode": "none"})
            # The upload job against the in-frame upload.
            native.n06_set_phase("n07_upload")
            steps["upload_inframe_run"] = _slim(host.run(3, period, {"mode": "inframe", "kind": "upload",
                                                                      "seed": UPLOAD_SEED, "count": 1}))
            steps["upload_inframe_hash"] = _readback(host, period, "upload_inframe", {"kind": "upload"})
            up = _run_until_swap(host, period, {"mode": "job", "kind": "upload", "seed": UPLOAD_SEED, "count": 1},
                                 "upload")
            steps["upload_job"] = {"swapped": up["swapped"], "generation": up["generation"], "swap": up["swap"],
                                   "jobs": up["jobs"], "analysis": [analyse_run(r) for r in up["runs"]]}
            steps["upload_job_hash"] = _readback(host, period, "upload_job")
            neg = _run_until_swap(host, period, {"mode": "job", "kind": "upload", "seed": UPLOAD_SEED + 1,
                                                 "count": 1}, "upload")
            steps["upload_negative_swapped"] = neg["swapped"]
            steps["upload_negative_hash"] = _readback(host, period, "upload_job")
            steps["photo_hash"] = json.loads(native.n07_photo_hash(w, h, UPLOAD_SEED))
            # The edge field job against the in-frame edge field (D9 ii).
            native.n06_set_phase("n07_field")
            field_cfg = {"kind": "field", "repeat": 1, "low": LOW, "high": HIGH}
            steps["field_inframe_run"] = _slim(host.run(3, period, {"mode": "inframe", "count": 1, **field_cfg}))
            steps["field_inframe_hash"] = _readback(host, period, "field_inframe", field_cfg)
            fj = _run_until_swap(host, period, {"mode": "job", "count": 1, **field_cfg}, "field")
            steps["field_job"] = {"swapped": fj["swapped"], "generation": fj["generation"], "swap": fj["swap"],
                                  "jobs": fj["jobs"], "analysis": [analyse_run(r) for r in fj["runs"]]}
            steps["field_job_hash"] = _readback(host, period, "field_job")
            fn = _run_until_swap(host, period, {"mode": "job", "count": 1, **{**field_cfg,
                                                "low": LOW + NEGATIVE_LOW_STEP}}, "field")
            steps["field_negative_swapped"] = fn["swapped"]
            steps["field_negative_hash"] = _readback(host, period, "field_job")
            # A short look at rest (the minute is the rest round).
            s0 = json.loads(native.n07_service_stats(False))
            host.run(int(round(2000.0 / period)), period, {"mode": "none"})
            s1 = json.loads(native.n07_service_stats(False))
            steps["short_rest"] = {"seconds": 2, "wakeups": s1.get("wakeups", -1) - s0.get("wakeups", 0),
                                   "cpu_cycles_delta": int(s1.get("cpu_cycles", "0")) - int(s0.get("cpu_cycles", "0"))}
            steps["service_stats"] = json.loads(native.n07_service_stats(True))
        host.release_render_side()
    record["host_error"] = host.error
    if host.handle is not None or getattr(host, "control", None) is not None:
        host.end()
    stop = json.loads(native.n07_service_stop(False))
    teardown = json.loads(native.n06_context_destroy())
    del app

    probe = start.get("start", {}).get("probe", {})
    stats = steps.get("service_stats", {})
    up_in, up_job, up_neg = (steps.get("upload_inframe_hash", {}), steps.get("upload_job_hash", {}),
                             steps.get("upload_negative_hash", {}))
    f_in, f_job, f_neg = (steps.get("field_inframe_hash", {}), steps.get("field_job_hash", {}),
                          steps.get("field_negative_hash", {}))
    level_k = "level4_fnv1a64"

    def same(a: dict, b: dict, key: str) -> bool:
        return bool(a.get(key)) and a.get(key) == b.get(key)

    job_runs = steps.get("upload_job", {}).get("analysis", []) + steps.get("field_job", {}).get("analysis", [])
    latch_max = max((a.get("latch_us", {}).get("max", 0.0) for a in job_runs), default=None)
    driver_probes = [r.get("raw", {}).get("driver", {}).get("frame_driver_probe", {})
                     for r in (steps.get("upload_inframe_run", {}), steps.get("field_inframe_run", {}))]
    checks = {
        "context_with_second_queue": bool(ctx.get("ok")) and ctx.get("device", {}).get("second_queue", {})
        .get("same_family_as_graphics") is True,
        "host_rendered_on_our_device": host.error is None and bool(host.session.get("vk_device"))
        and host.session.get("vk_device") == ctx.get("device", {}).get("vk_device")
        and host.session.get("vk_queue_index") == 0,
        "host_target_primed_for_load": str(host.session.get("target_prime", "")).startswith("primed"),
        "service_started": bool(start.get("ok")),
        "second_qrhi_works": probe.get("second_qrhi_works") is True,
        "second_qrhi_on_queue_family_0_index_1": probe.get("queue_family") == 0 and probe.get("queue_index") == 1,
        "upload_job_published_and_swapped": steps.get("upload_job", {}).get("swapped") is True,
        "upload_mip0_equals_photo": bool(steps.get("photo_hash", {}).get("fnv1a64"))
        and up_job.get("level0_fnv1a64") == steps["photo_hash"]["fnv1a64"],
        "upload_job_equals_inframe_mip0": same(up_job, up_in, "level0_fnv1a64"),
        "upload_job_equals_inframe_mip4": same(up_job, up_in, level_k),
        "upload_negative_control_differs": steps.get("upload_negative_swapped") is True
        and bool(up_neg.get("level0_fnv1a64")) and up_neg.get("level0_fnv1a64") != up_job.get("level0_fnv1a64")
        and up_neg.get(level_k) != up_job.get(level_k),
        "field_job_published_and_swapped": steps.get("field_job", {}).get("swapped") is True,
        "field_job_equals_inframe": same(f_job, f_in, "level0_fnv1a64")
        and f_job.get("level0_size") == [w, h],
        "field_negative_control_differs": steps.get("field_negative_swapped") is True
        and bool(f_neg.get("level0_fnv1a64")) and f_neg.get("level0_fnv1a64") != f_job.get("level0_fnv1a64"),
        "latch_never_holds_a_frame": latch_max is not None and latch_max <= LATCH_BOUND_US,
        "no_python_thread_state_on_job_thread": stats.get("thread_probe", {}).get("calls", 0) > 0
        and stats.get("thread_probe", {}).get("calls_with_python_thread_state", -1) == 0
        and stats.get("thread_probe", {}).get("calls_on_gui_thread", -1) == 0,
        "no_python_thread_state_in_frame_driver": all(p.get("calls", 0) > 0
                                                      and p.get("calls_with_python_thread_state", -1) == 0
                                                      for p in driver_probes),
        "service_stopped": stop.get("state_after") == "stopped",
        "teardown_ok": bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok") is True
        and teardown.get("steps") == EXPECTED_TEARDOWN,
        "no_messenger_errors": bool(teardown.get("messages"))
        and messenger_errors_unexplained(teardown["messages"]) == 0,
        "environment_clean": environment_record()["clean"],
    }
    owed: list = []
    validated = _validation_record(ctx, [teardown])
    _validation_checks(validated, checks, owed)
    record.update({"round": "jobs", "checks": checks, "pass": all(checks.values()), "owed": owed,
                   "probe": probe, "bodies": start.get("start", {}).get("bodies"),
                   "hashes": {"photo": steps.get("photo_hash"), "upload_inframe": up_in, "upload_job": up_job,
                              "upload_negative": up_neg, "field_inframe": f_in, "field_job": f_job,
                              "field_negative": f_neg},
                   "latch_us_max_in_job_runs": latch_max, "short_rest": steps.get("short_rest"),
                   "validation": validated,
                   "steps": steps, "service_start": start, "service_stop": stop, "teardown": teardown,
                   "context": {"device": ctx.get("device", {}).get("vk_device"),
                               "second_queue": ctx.get("device", {}).get("second_queue")},
                   "environment": environment_record()})
    return record


# --------------------------------------------------------------------- round 2: the measurements (D9 i)

MODES = ("none", "inframe", "job")


def round_measure(native, out: Path, args) -> dict:
    app = _app()
    timing = _display_period(app, args.period_ms)
    period = timing["period_ms"]
    w, h = args.field_size
    conditions = Conditions()
    ctx = json.loads(native.n06_context_create(True, "second"))
    host = Host(native)
    passes: list = []
    warm: dict = {}
    start: dict = {}
    if ctx.get("ok") and host.begin():
        start = json.loads(native.n07_service_start(w, h))
        if start.get("ok"):
            heavy = {"kind": "field", "repeat": args.repeat, "low": LOW, "high": HIGH}
            native.n06_set_phase("n07_measure_warm")
            host.run(60, period, {"mode": "none"})
            # Untimed: the in-frame body and pipelines, one build each way.
            warm["inframe"] = analyse_run(host.run(30, period, {"mode": "inframe", "count": 1, "first": 5, **heavy}))
            warm["job"] = analyse_run(_run_until_swap(host, period, {"mode": "job", "count": 1, **heavy},
                                                      "field")["runs"][0])
            schedule = {"first": args.first, "every": args.every, "count": max(1, args.frames // max(1, args.every))}
            for p in range(args.passes):
                for mode in MODES:
                    native.n06_set_phase(f"n07_measure_{mode}")
                    before = conditions.sample()
                    run = host.run(args.frames, period, {"mode": mode, **heavy, **(schedule if mode != "none"
                                                                                  else {"count": 0})})
                    # Let a job still in flight land before the next pass (not part of the pass's frames); its
                    # record and its swap join the pass.
                    tail = host.run(int(round(500.0 / period)), period, {"mode": "none"})
                    ids = {t["request_id"] for t in run.get("driver", {}).get("triggers", []) if "request_id" in t}
                    if ids:
                        run["jobs"] = _job_records(native, ids)
                        offset = len(run.get("scheduled_ms", []))
                        run.setdefault("driver", {}).setdefault("swaps", []).extend(
                            {**s, "frame": s["frame"] + offset, "in_tail": True}
                            for s in tail.get("driver", {}).get("swaps", []))
                    after = conditions.sample()
                    passes.append({"pass": p, "mode": mode, "analysis": analyse_run(run), "conditions_before": before,
                                   "conditions_after": after, "raw": run})
        host.release_render_side()
    record: dict = {"display": timing, "host_error": host.error}
    if getattr(host, "control", None) is not None:
        host.end()
    stop = json.loads(native.n07_service_stop(False))
    teardown = json.loads(native.n06_context_destroy())
    del app

    by_mode: dict = {}
    for mode in MODES:
        runs = [p for p in passes if p["mode"] == mode]
        gpu, latency, late, frames, missed = [], [], 0, 0, 0
        trigger_gpu = []
        job_wait, job_total, swap_frames = [], [], []
        for p in runs:
            raw, a = p["raw"], p["analysis"]
            d = raw.get("driver", {})
            reported = d.get("qt_gpu_reported_ms", [])
            gpu += [v for i, v in enumerate(reported) if i >= GPU_REPORT_LAG and v > 0.0]
            sched, comp = raw.get("scheduled_ms", []), raw.get("complete_ms", [])
            latency += [comp[i] - sched[i] for i in range(min(len(sched), len(comp)))]
            late += a["late_frames"]
            frames += a["frames"]
            missed += a.get("missed_periods") or 0
            flags = d.get("flags", [])
            trigger_gpu += [reported[i + GPU_REPORT_LAG] for i, f in enumerate(flags)
                            if f & FLAG_INFRAME and i + GPU_REPORT_LAG < len(reported)]
            job_wait += [j["gpu_wait_ms"] for j in a["jobs"] if not j["abandoned"]]
            job_total += [j["submit_to_publish_ms"] for j in a["jobs"] if j["submit_to_publish_ms"] is not None]
            swap_frames += [j["frames_trigger_to_swap"] for j in a["jobs"] if j["frames_trigger_to_swap"] is not None]
        by_mode[mode] = {"passes": len(runs), "frames": frames, "qt_frame_gpu_ms": describe(gpu),
                         "completion_latency_ms": describe(latency), "late_frames": late,
                         "late_fraction": round(late / frames, 5) if frames else None, "missed_periods": missed,
                         "qt_frame_gpu_ms_frames_with_inframe_job": describe(trigger_gpu),
                         "job_gpu_wait_ms": describe(job_wait), "job_submit_to_publish_ms": describe(job_total),
                         "job_frames_trigger_to_swap": describe(swap_frames),
                         "triggers": sum(p["analysis"]["triggers"] for p in runs)}
    others = sorted({o["name"] for p in passes for c in (p["conditions_before"], p["conditions_after"])
                     for o in c.get("gpu_engines", {}).get("other_processes_using_gpu", [])})
    inframe, job, none = by_mode.get("inframe", {}), by_mode.get("job", {}), by_mode.get("none", {})

    def p99(m: dict, key: str) -> float | None:
        return m.get(key, {}).get("p99")

    comparison = {
        "late_frames": {"none": none.get("late_frames"), "inframe": inframe.get("late_frames"),
                        "job": job.get("late_frames")},
        "qt_frame_gpu_p99_ms": {m: p99(by_mode.get(m, {}), "qt_frame_gpu_ms") for m in MODES},
        "completion_p99_ms": {m: p99(by_mode.get(m, {}), "completion_latency_ms") for m in MODES},
        "heavy_job_gpu_ms_in_frame_estimate": (
            round(inframe["qt_frame_gpu_ms_frames_with_inframe_job"]["median"]
                  - none["qt_frame_gpu_ms"]["median"], 4)
            if inframe.get("qt_frame_gpu_ms_frames_with_inframe_job", {}).get("n") and none.get("qt_frame_gpu_ms",
                                                                                                  {}).get("n")
            else None),
        "job_gpu_wait_median_ms": job.get("job_gpu_wait_ms", {}).get("median"),
    }
    # The draft gain rule (the lead decides): the job form keeps frames on time where the in-frame form does not.
    gain = (inframe.get("late_frames") is not None and job.get("late_frames") is not None
            and inframe["late_frames"] > 0 and job["late_frames"] <= max(none.get("late_frames", 0),
                                                                        inframe["late_frames"] // 4)
            and (p99(job, "completion_latency_ms") or 1e9) < (p99(inframe, "completion_latency_ms") or 0.0))
    validated = _validation_record(ctx, [teardown])
    checks = {
        "context_and_service": bool(ctx.get("ok")) and bool(start.get("ok")),
        "all_passes_ran": len(passes) == args.passes * len(MODES) and all(p["raw"].get("ok") for p in passes),
        "qt_gpu_timestamps_reported": all(by_mode[m]["qt_frame_gpu_ms"].get("n", 0) > 0 for m in MODES),
        "inframe_jobs_recorded": inframe.get("qt_frame_gpu_ms_frames_with_inframe_job", {}).get("n", 0) > 0,
        "jobs_published": job.get("job_gpu_wait_ms", {}).get("n", 0) > 0,
        "high_resolution_timer": all(p["analysis"].get("high_resolution_timer") for p in passes),
        "teardown_ok": bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok") is True,
        "no_messenger_errors": bool(teardown.get("messages"))
        and messenger_errors_unexplained(teardown["messages"]) == 0,
        "environment_clean": environment_record()["clean"],
    }
    owed: list = []
    _validation_checks(validated, checks, owed)
    record.update({
        "round": "measure", "checks": checks, "pass": all(checks.values()), "owed": owed, "validation": validated,
        "timing_caveat": ("validation layer loaded: the layer's own CPU and GPU work is in every figure; the timing "
                          "verdict comes from a run without the layer") if validated["layer_loaded"] else None,
        "settings": {"field_size": [w, h], "repeat": args.repeat, "every": args.every, "first": args.first,
                     "frames_per_pass": args.frames, "passes": args.passes},
        "by_mode": by_mode, "comparison": comparison,
        "draft_verdict": "jobs for compute on this vendor" if gain else "uploads only (no measured gain for compute)",
        "other_processes_using_gpu_during_run": others,
        "warm": warm, "passes": passes, "service_start": start, "service_stop": stop, "teardown": teardown,
        "environment": environment_record(),
    })
    return record


# --------------------------------------------------------------------- round 3: retirement mid-job (D9 v)

CYCLE_KINDS = ("host", "service_idle", "service_jobs", "retire_api", "retire_hook")


def _service_cycle(native, index: int, args, kind: str, before: dict | None = None) -> dict:
    """One create/use/destroy cycle of a kind (owners style: each kind adds one owner to the one before):
    host          our context (second queue) and the hidden host, 20 frames; no job service;
    service_idle  + the job service started and stopped (the job thread, the second QRhi, the bodies);
    service_jobs  + an upload job and an edge-field job published and swapped, then a normal stop;
    retire_api    + a heavy job running, then retirement through n07_retire (render side, quiesce, abandon);
    retire_hook   + a heavy job running, the render side released, the host ended and the context's teardown
                    quiescing the job thread (the hook before vkDeviceWaitIdle).
    The process handle count after every step, the counters after the teardown, and a census (handles by type,
    threads by start module) diffed against `before` (the previous cycle's census)."""
    import gc

    period = args.period_value
    w, h = args.field_size
    rec: dict = {"cycle": index, "kind": kind, "via": {"retire_api": "n07_retire",
                                                      "retire_hook": "context_teardown_hook"}.get(kind)}
    steps: list = []

    def mark(name: str) -> None:
        steps.append([name, native.n06_handle_count()])

    mark("cycle start")
    ctx = json.loads(native.n06_context_create(True, "second"))
    mark("context created (instance, device with the second queue)")
    rec["context_ok"] = bool(ctx.get("ok"))
    host = Host(native)
    devices = int(bool(ctx.get("device", {}).get("vk_device")))
    rec["service_ok"] = kind == "host"
    rec["frames_while_job_ran_ok"] = kind in ("host", "service_idle", "service_jobs")
    if ctx.get("ok") and host.begin():
        mark("host begun (render thread, Qt's QRhi on our device)")
        native.n06_set_phase(f"n07_{kind}_{index:02d}")
        host.run(20, period, {"mode": "none"})
        mark("20 frames")
        if kind != "host":
            start = json.loads(native.n07_service_start(w, h))
            mark("job service started (thread, second QRhi, probe, bodies)")
            rec["service_ok"] = bool(start.get("ok"))
            rec["service_start_handles"] = start.get("start", {}).get("handles")
            if start.get("ok"):
                host.run(5, period, {"mode": "none"})
                heavy = {"kind": "field", "repeat": args.retire_repeat, "low": LOW, "high": HIGH}
                if kind == "service_jobs":
                    up = _run_until_swap(host, period, {"mode": "job", "kind": "upload", "seed": UPLOAD_SEED,
                                                        "count": 1}, "upload", frames=30)
                    fj = _run_until_swap(host, period, {"mode": "job", "kind": "field", "repeat": 1, "low": LOW,
                                                        "high": HIGH, "count": 1}, "field", frames=30)
                    rec["jobs_swapped"] = up["swapped"] and fj["swapped"]
                    mark("an upload job and an edge-field job published and swapped")
                elif kind in ("retire_api", "retire_hook"):
                    busy = host.run(4, period, {"mode": "job", "count": 1, **heavy})
                    rec["frames_while_job_ran_ok"] = bool(busy.get("ok"))
                    mark("a heavy job running")
                if kind == "retire_hook":
                    host.run(1, period, {"mode": "job", "count": 1, **heavy})
                    rec["render_side"] = host.release_render_side()
                    mark("another heavy job submitted, render side released")
                elif kind == "retire_api":
                    rec["retire"] = json.loads(native.n07_retire(host.handle, args.retire_repeat))
                    rec["service_stop_handles"] = rec["retire"].get("stop", {}).get("handles")
                    mark("retired through n07_retire (render side, quiesce, abandon)")
                else:
                    host.release_render_side()
                    stop = json.loads(native.n07_service_stop(False))
                    rec["service_stop_handles"] = stop.get("handles")
                    rec["service_stopped"] = stop.get("state_after") == "stopped"
                    mark("render side released, job service stopped")
    if getattr(host, "control", None) is not None:
        host.end()
        mark("host ended (session, render control and Qt's QRhi, window)")
    teardown = json.loads(native.n06_context_destroy())
    mark("context destroyed" + (" (the hook quiesced the job thread)" if teardown.get("job_quiesce") else ""))
    rec["service_stop_handles"] = rec.get("service_stop_handles") or (teardown.get("job_quiesce") or {}).get("handles")
    rec["teardown_steps"] = teardown.get("steps", [])
    rec["teardown_handles"] = teardown.get("teardown_handles")
    rec["job_quiesce"] = teardown.get("job_quiesce")
    rec["teardown_ok"] = bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok") is True
    rec["messages"] = teardown.get("messages", {})
    rec["validation_layer_loaded"] = bool(ctx.get("instance", {}).get("validation_layer_loaded"))
    rec["validation"] = ctx.get("instance", {}).get("validation")
    rec["synchronisation_validation"] = bool(ctx.get("instance", {}).get("synchronisation_validation"))
    rec["devices_created"] = devices
    del ctx, teardown
    gc.collect()
    mark("gc")
    rec["steps"] = [[steps[i][0], steps[i][1] - steps[i - 1][1]] for i in range(1, len(steps))]
    rec["counters_after"] = _counters(native)
    census = n07_census.census()  # after the counters: the census opens thread handles while it runs
    rec["census_diff"] = n07_census.diff(before, census) if before else None
    rec["census_threads"] = len(census.get("threads", []))
    by_start: dict = {}
    for t in census.get("threads", []):
        key = f"{t.get('start_module', '?')} | {t.get('description') or ''}"
        by_start[key] = by_start.get(key, 0) + 1
    rec["threads_by_start"] = dict(sorted(by_start.items()))
    rec["_census"] = census
    return rec


# Cycles before the baseline. Build round 2's retire run: threads appeared asynchronously after the first cycle's
# counters were read (the counters said 18 threads, the census taken a moment later already had 41, and the next
# cycle's counters 41; private bytes 345 then 1061 MiB), so the first cycle's reading is not yet a baseline; the
# second cycle's is (N0.6 round 5 also warms up twice).
WARMUP_CYCLES = 2


def _attribution(records: list) -> dict:
    """Owners-style figures over a list of cycles of one kind: handles per cycle (the first WARMUP_CYCLES are the
    warm-up, the last of them the baseline), the cycles whose growth was not the driver's 3 per device, with their
    census diff, the mean handle delta of every step, the handle kinds and threads gained over the measured
    cycles."""
    base = min(WARMUP_CYCLES, len(records)) - 1
    measured = records[base + 1:]
    handles_all = [r["counters_after"]["handles"] for r in records]
    handles = handles_all[base:]
    deltas = [handles[i] - handles[i - 1] for i in range(1, len(handles))]
    expected = [DRIVER_HANDLES_PER_DEVICE * r["devices_created"] for r in measured]
    off = [{"cycle": r["cycle"], "delta": d, "expected": e, "census_diff": r.get("census_diff")}
           for r, d, e in zip(measured, deltas, expected) if d != e]
    type_totals: dict = {}
    for r in measured:
        for k, v in ((r.get("census_diff") or {}).get("handles_by_type") or {}).items():
            type_totals[k] = type_totals.get(k, 0) + v
    first, last = records[base].get("_census", {}), records[-1].get("_census", {})
    persistent = n07_census.diff(first, last) if first and last else {}
    step_names: list = []
    step_sum: dict = {}
    for r in measured:
        for name, d in r.get("steps", []):
            if name not in step_sum:
                step_names.append(name)
                step_sum[name] = []
            step_sum[name].append(d)
    half = len(handles) // 2
    pooled = [r.get("threads_by_start", {}).get("Qt6Core.dll | Thread (pooled)", 0) for r in records]
    return {"handles_series": handles_all, "baseline_cycle": base, "per_cycle_deltas": deltas,
            "qt_pooled_threads_series": pooled,
            "threads_by_start_first_and_last": [records[base].get("threads_by_start"),
                                                records[-1].get("threads_by_start")],
            "expected_per_cycle": expected,
            "second_half_handles_per_cycle": round((handles[-1] - handles[half]) / max(1, len(handles) - 1 - half), 3),
            "cycles_off_driver_cost": off,
            "handle_types_gained_over_measured_cycles": {k: v for k, v in sorted(type_totals.items()) if v},
            "first_to_last_census_diff": {"handles_by_type": persistent.get("handles_by_type"),
                                          "threads_new": persistent.get("threads_new"),
                                          "threads_gone": persistent.get("threads_gone")},
            "mean_step_deltas": [[n, round(sum(step_sum[n]) / len(step_sum[n]), 3)] for n in step_names],
            "threads_series": [r["counters_after"]["threads"] for r in records]}


def _run_cycles(native, args, kinds: list) -> list:
    records: list = []
    census_before = None
    for i, kind in enumerate(kinds):
        r = _service_cycle(native, i, args, kind, census_before)
        census_before = r["_census"]
        records.append(r)
    return records


def round_retire(native, out: Path, args) -> dict:
    app = _app()
    timing = _display_period(app, args.period_ms)
    args.period_value = timing["period_ms"]
    start = _counters(native)
    records = _run_cycles(native, args, ["retire_hook" if i % 2 else "retire_api" for i in range(args.cycles)])
    del app
    attribution = _attribution(records)
    base = min(WARMUP_CYCLES, len(records)) - 1
    after = [r["counters_after"] for r in records][base:]  # after[0] is the baseline (the last warm-up cycle)
    baseline, last = after[0], after[-1]
    devices_after_baseline = sum(r["devices_created"] for r in records[base + 1:])
    expected = DRIVER_HANDLES_PER_DEVICE * devices_after_baseline
    handle_delta = _delta(after, "handles")
    heap_deltas = [round(b.get("usage_mib", 0.0) - a.get("usage_mib", 0.0), 3)
                   for a, b in zip(baseline.get("gpu_heaps", []), last.get("gpu_heaps", []))]
    private = [a.get("private_mib", 0.0) for a in after]
    third = max(1, len(private) // 3)
    plateau = {"min_first_third": round(min(private[:third]), 1), "min_last_third": round(min(private[-third:]), 1),
               "slope_per_cycle": _slope(private)}

    def cycle_ok(r: dict) -> bool:
        if not (r.get("context_ok") and r.get("service_ok") and r.get("teardown_ok")
                and r.get("frames_while_job_ran_ok")):
            return False
        if r["via"] == "n07_retire":
            ret = r.get("retire", {})
            job = ret.get("retired_job") or {}
            return (ret.get("ok") is True and ret.get("job_gpu_work_in_flight_at_retirement") is True
                    and job.get("abandoned") is True and not job.get("generation")
                    and ret.get("stop", {}).get("state_after") == "stopped"
                    and r["teardown_steps"] == EXPECTED_TEARDOWN)
        q = r.get("job_quiesce") or {}
        return (q.get("state_after") == "stopped" and q.get("abandon") is True
                and r["teardown_steps"] == ["job thread quiesced"] + EXPECTED_TEARDOWN)

    in_flight_via_hook = [(r.get("job_quiesce") or {}).get("state_at_stop") for r in records
                          if r["via"] == "context_teardown_hook"]
    checks = {
        "every_cycle_retired_mid_job_and_tore_down": all(cycle_ok(r) for r in records),
        "teardown_hook_found_the_job_in_flight": bool(in_flight_via_hook)
        and all(s in ("recording", "waiting_on_gpu") for s in in_flight_via_hook),
        "handles_baseline_plus_driver_cost": handle_delta is not None and abs(handle_delta - expected) <= HANDLE_TOLERANCE,
        "threads_back_to_baseline": _delta(after, "threads") is not None
        and abs(_delta(after, "threads")) <= THREAD_TOLERANCE,
        "gpu_heaps_back_to_baseline": bool(baseline.get("gpu_budget_supported"))
        and all(abs(d) <= GPU_HEAP_TOLERANCE_MIB for d in heap_deltas),
        "private_bytes_plateau": plateau["min_last_third"] <= plateau["min_first_third"] + PRIVATE_PLATEAU_TOLERANCE_MIB,
        "no_messenger_errors": all(messenger_errors_unexplained(r["messages"]) == 0 for r in records),
        "no_qt_pooled_threads_started": len(set(attribution["qt_pooled_threads_series"][base:])) <= 1,
        "environment_clean": environment_record()["clean"],
    }
    validated = _validation_record({"instance": {"validation_layer_loaded": all(r["validation_layer_loaded"]
                                                                                for r in records),
                                                 "validation": records[0].get("validation") if records else None,
                                                 "synchronisation_validation": all(
                                                     r["synchronisation_validation"] for r in records)}},
                                   [{"messages": r["messages"]} for r in records])
    owed: list = []
    _validation_checks(validated, checks, owed)
    for r in records:
        r.pop("_census", None)
    return {
        "round": "retire", "checks": checks, "pass": all(checks.values()), "owed": owed, "validation": validated,
        "attribution": attribution,
        "cycles": args.cycles, "retire_repeat": args.retire_repeat,
        "counters": {"start": start, "after_each_cycle": after,
                     "handles_expected_delta": {"devices_after_baseline": devices_after_baseline,
                                                "driver_handles_per_device": DRIVER_HANDLES_PER_DEVICE,
                                                "expected": expected, "measured": handle_delta},
                     "threads_delta": _delta(after, "threads"), "gpu_heap_delta_mib": heap_deltas,
                     "private_plateau_mib": plateau},
        "state_at_retirement": [((r.get("retire") or {}).get("state_at_retirement")
                                 or (r.get("job_quiesce") or {}).get("state_at_stop")) for r in records],
        "records": records, "display": timing, "environment": environment_record(),
    }


# --------------------------------------------------------------------- whose handles (owners style, for D9 v)

def round_owners(native, out: Path, args) -> dict:
    """The retire round's extra handles attributed: --cycles cycles of each kind in CYCLE_KINDS, each kind adding
    one owner (the job service and its second QRhi, jobs, the abandon path through either route)."""
    app = _app()
    timing = _display_period(app, args.period_ms)
    args.period_value = timing["period_ms"]
    start = _counters(native)
    kinds: dict = {}
    for kind in CYCLE_KINDS:
        kinds[kind] = _run_cycles(native, args, [kind] * args.cycles)
    del app
    summaries = {kind: _attribution(records) for kind, records in kinds.items()}
    rate = {kind: s["second_half_handles_per_cycle"] for kind, s in summaries.items()}
    attribution = {
        "context and host (the driver's 3 per device expected)": rate["host"],
        "job service: thread, second QRhi, probe, bodies": round(rate["service_idle"] - rate["host"], 3),
        "jobs published and swapped": round(rate["service_jobs"] - rate["service_idle"], 3),
        "abandon through n07_retire": round(rate["retire_api"] - rate["service_idle"], 3),
        "abandon through the context teardown hook": round(rate["retire_hook"] - rate["service_idle"], 3),
    }
    all_records = [r for records in kinds.values() for r in records]
    for r in all_records:
        r.pop("_census", None)
    checks = {
        "every_cycle_created_and_tore_down": all(r["context_ok"] and r["teardown_ok"] and r["service_ok"]
                                                 for r in all_records),
        "jobs_swapped": all(r.get("jobs_swapped") for r in kinds["service_jobs"]),
        "no_messenger_errors": all(messenger_errors_unexplained(r["messages"]) == 0 for r in all_records),
        "environment_clean": environment_record()["clean"],
        "host_only_driver_cost": abs(rate["host"] - DRIVER_HANDLES_PER_DEVICE) <= 0.05,
        "service_adds_no_handles": abs(attribution["job service: thread, second QRhi, probe, bodies"]) <= 0.05,
        "jobs_add_no_handles": abs(attribution["jobs published and swapped"]) <= 0.05,
        "no_qt_pooled_threads_started": all(
            len(set(s["qt_pooled_threads_series"][s["baseline_cycle"]:])) <= 1 for s in summaries.values()),
        "abandon_adds_no_handles": abs(attribution["abandon through n07_retire"]) <= 0.05
        and abs(attribution["abandon through the context teardown hook"]) <= 0.05,
    }
    return {"round": "owners", "checks": checks, "pass": all(checks.values()), "owed": [],
            "cycles_per_kind": args.cycles, "handles_per_cycle_by_kind": rate, "attribution": attribution,
            "summaries": summaries, "start_counters": start, "records": kinds, "display": timing,
            "environment": environment_record()}


# --------------------------------------------------------------------- round 4: rest (D9 vi)

def round_rest(native, out: Path, args) -> dict:
    app = _app()
    timing = _display_period(app, args.period_ms)
    period = timing["period_ms"]
    w, h = args.field_size
    ctx = json.loads(native.n06_context_create(True, "second"))
    host = Host(native)
    rec: dict = {"display": timing}
    start: dict = {}
    if ctx.get("ok") and host.begin():
        start = json.loads(native.n07_service_start(w, h))
        if start.get("ok"):
            host.run(30, period, {"mode": "none"})
            used = _run_until_swap(host, period, {"mode": "job", "kind": "upload", "seed": UPLOAD_SEED, "count": 1},
                                   "upload")
            rec["used_before_rest"] = used["swapped"]
            host.run(30, period, {"mode": "none"})
            s0 = json.loads(native.n07_service_stats(False))
            frames = int(round(args.rest_seconds * 1000.0 / period))
            t0 = time.perf_counter()
            run = host.run(frames, period, {"mode": "none"})
            rec["rest_wall_s"] = round(time.perf_counter() - t0, 3)
            s1 = json.loads(native.n07_service_stats(False))
            rec["rest_run"] = analyse_run(run)
            neg = _run_until_swap(host, period, {"mode": "job", "kind": "upload", "seed": UPLOAD_SEED + 1,
                                                 "count": 1}, "upload")
            s2 = json.loads(native.n07_service_stats(False))
            rec["stats"] = {"before_rest": s0, "after_rest": s1, "after_negative_control": s2}
            rec["rest"] = {"frames": frames, "wakeups": s1["wakeups"] - s0["wakeups"],
                           "cpu_cycles": int(s1.get("cpu_cycles", "0")) - int(s0.get("cpu_cycles", "0")),
                           "user_ms": round(s1.get("user_ms", 0.0) - s0.get("user_ms", 0.0), 3),
                           "kernel_ms": round(s1.get("kernel_ms", 0.0) - s0.get("kernel_ms", 0.0), 3),
                           "state_after": s1.get("state"),
                           "latch_reads": rec["rest_run"]["frames"]}
            rec["negative_control"] = {"swapped": neg["swapped"], "wakeups": s2["wakeups"] - s1["wakeups"],
                                       "cpu_cycles": int(s2.get("cpu_cycles", "0")) - int(s1.get("cpu_cycles", "0"))}
        host.release_render_side()
    rec["host_error"] = host.error
    if getattr(host, "control", None) is not None:
        host.end()
    stop = json.loads(native.n07_service_stop(False))
    teardown = json.loads(native.n06_context_destroy())
    del app
    rest, neg = rec.get("rest", {}), rec.get("negative_control", {})
    validated = _validation_record(ctx, [teardown])
    checks = {
        "context_and_service": bool(ctx.get("ok")) and bool(start.get("ok")),
        "job_thread_used_before_rest": rec.get("used_before_rest") is True,
        "rest_lasted": rec.get("rest_wall_s", 0.0) >= args.rest_seconds * 0.95,
        "zero_wakeups_at_rest": rest.get("wakeups") == 0,
        "zero_cpu_cycles_at_rest": rest.get("cpu_cycles") == 0,
        "parked_after_rest": rest.get("state_after") == "parked",
        "negative_control_wakes_and_spends_cycles": neg.get("swapped") is True and neg.get("wakeups", 0) >= 1
        and neg.get("cpu_cycles", 0) > 0,
        "teardown_ok": bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok") is True,
        "no_messenger_errors": bool(teardown.get("messages"))
        and messenger_errors_unexplained(teardown["messages"]) == 0,
        "environment_clean": environment_record()["clean"],
    }
    owed: list = []
    _validation_checks(validated, checks, owed)
    rec.update({"round": "rest", "checks": checks, "pass": all(checks.values()), "validation": validated,
                "owed": owed, "rest_seconds": args.rest_seconds,
                "service_start": start, "service_stop": stop, "teardown": teardown,
                "environment": environment_record()})
    return rec


ROUNDS = {"jobs": round_jobs, "measure": round_measure, "retire": round_retire, "rest": round_rest,
          "owners": round_owners}
SHOWN = {
    "jobs": ("probe", "hashes", "latch_us_max_in_job_runs", "short_rest"),
    "measure": ("settings", "by_mode", "comparison", "draft_verdict", "other_processes_using_gpu_during_run"),
    "retire": ("counters", "state_at_retirement", "attribution"),
    "rest": ("rest", "negative_control", "rest_wall_s"),
    "owners": ("handles_per_cycle_by_kind", "attribution"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--round", default="jobs", choices=sorted(ROUNDS))
    parser.add_argument("--label", default="n07")
    parser.add_argument("--field-size", type=_field_size, default=FIELD_SIZE, help="WxH of the field and its photo")
    parser.add_argument("--period-ms", type=float, default=None,
                        help="frame period (default: the primary screen's refresh period)")
    parser.add_argument("--repeat", type=int, default=4, help="measure: edge-field builds per heavy job")
    parser.add_argument("--frames", type=int, default=600, help="measure: frames per pass")
    parser.add_argument("--every", type=int, default=30, help="measure: frames between heavy jobs")
    parser.add_argument("--first", type=int, default=15, help="measure: the frame of a pass's first heavy job")
    parser.add_argument("--passes", type=int, default=2, help="measure: passes of none, in-frame and job in turn")
    parser.add_argument("--cycles", type=int, default=6,
                        help="retire: cycles (the first two warm up, the second is the baseline); owners: cycles per "
                             "kind (the same warm-up per kind)")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json: sets VK_ADD_LAYER_PATH for this "
                             "process only; reported, allowed by the environment check")
    parser.add_argument("--retire-repeat", type=int, default=32, help="retire: edge-field builds of the retired job")
    parser.add_argument("--rest-seconds", type=float, default=60.0, help="rest: seconds at rest")
    args = parser.parse_args()

    use_layer_path(args.layer_path)  # before the module or Qt loads the Vulkan loader
    native = _import_native(args.module_dir.resolve())
    missing = [name for name in REQUIRED if not hasattr(native, name)]
    if missing:
        print(f"N07 VERDICT FAIL: the module has no {', '.join(missing)} (an older build in --module-dir)")
        return 0
    out = _evidence_dir(args.label)
    summary = {"runtime": native.runtime_info(), "python": sys.version, "args": {k: (str(v) if isinstance(v, Path)
                                                                                     else v)
                                                                                 for k, v in vars(args).items()}}
    summary.update(ROUNDS[args.round](native, out, args))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in SHOWN[args.round] if k in summary}, indent=2))
    validated = summary.get("validation") or {}
    if validated.get("layer_loaded"):
        print(json.dumps({"validation": {k: validated.get(k) for k in ("status", "errors", "warnings",
                                                                        "loader_messages")},
                          "groups": [{k: g.get(k) for k in ("id", "phase", "source", "count", "threads",
                                                            "caller_modules")}
                                     for g in validated.get("attribution", [])]}, indent=2))
    print(json.dumps({k: summary[k] for k in ("round", "checks", "pass", "owed") if k in summary}, indent=2))
    failed = [k for k, v in summary["checks"].items() if not v]
    print(f"\nevidence: {out / 'summary.json'}")
    print("N07 VERDICT " + ("PASS" if summary["pass"] else "FAIL: " + ", ".join(failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
