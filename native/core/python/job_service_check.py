"""N3.8's proof of the async job service (D9; Current_Plan.md item 8b, section N2b; ``native/core/src/job_service.h``)
through ``rendering.native``: the first job is a photo's upload and its GPU mips into one of N4.a's core-owned textures.

A Crossfade item (N4.a's fullscreen pass, ``fullscreen_pass_check``'s scene, at progress 1: it draws its ``new`` picture
exactly) at 3840 x 2160 is given a sequence of real 4K photos (PERSONALSET wallpapers) while it draws, in a hidden host
(never a window on a screen). Vulkan runs on the module's own instance and devices (D6) with validation; OpenGL is the
in-frame form only (no second context).

Rounds (one child process per API):
  swap      each photo swapped in while drawing, by the device's own route (Vulkan: the job service; OpenGL: in the
            frame) and on Vulkan again under the harness control in_frame (D9 point 5: the measurement both ways):
            - every swap draws the photo exactly, and the job route's frames equal the in-frame route's (async changes
              when, never what);
            - Vulkan: the record that hands the image over draws the previous photo (the latch; nothing vanishes) and
              the frame is not held (frames are drawn while the job runs); the render thread's cost per image change
              (the record's CPU time) of the job route below the in-frame route's at every swap; no fallback;
            - a superseded image (a second photo set before the first one's job is committed) is cancelled: one commit,
              the second photo drawn;
            - nothing at rest: no record, no wake-up of the job thread, no retiring image, no GPU pass;
            - the lost edge: the node made again calls the owner once with both names; sent again, the item draws.
  lifetime  teardown with upload jobs in flight (the item and the host closed in the frame after the hand-over): no
            crash, the jobs dropped, every job count and texture count zero, the instance's teardown accepted.
Facts: the render thread's record time per image change (median and max per route), the job latencies (queued, the
CPU half on the job thread, the GPU wait, submitted to published), the GPU time of the surface's pass on the frames
that change an image, the job thread's thread probe (no Python thread state), validation per phase.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/job_service_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds swap lifetime] [--photos A.jpg B.jpg ...] [--label n38_job_service]
Evidence: .artifacts/evidence/native_core/n3_8/<date>_<label>/ (summary.json; one PNG sheet per API). Exit 0 whenever
the harness ran; the verdict is the last printed line ("N38 VERDICT PASS" or "N38 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

APIS = ("opengl", "vulkan")
ROUNDS = ("swap", "lifetime")
CHILD_TIMEOUT_S = 1800
SIZE = (3840, 2160)                 # the item's device pixels at dpr 1: the 4K measurement
PHOTO_FOLDER = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET")
PHOTOS = tuple(PHOTO_FOLDER / f"theVideoGameGallery_{n}_3840x2160.jpg"
               for n in (27137, 27086, 26861, 26381, 26458, 24499))
MAX_WAIT_FRAMES = 600               # frames drawn while a job runs before the swap is judged stuck
REST_FRAMES = 4
SHEET_TILE = (480, 270)
_ALLOWED_ENV: set[str] = set()


def _fsc():
    import fullscreen_pass_check

    return fullscreen_pass_check


def _photos(paths):
    return _fsc().photos(paths, SIZE)


def _state(scene) -> dict:
    return scene.mode.state()


def _jobs(state: dict) -> dict:
    return dict(state.get("texture_jobs") or {})


def _drawn_equals(pixels, image) -> bool:
    import numpy as np

    return _fsc().compare(pixels, np.asarray(image, dtype=np.uint8))["equal"]


def _tile(pixels):
    from PIL import Image

    return Image.fromarray(pixels[..., :3].copy(), "RGB").resize(SHEET_TILE)


class Swapper:
    """The Crossfade item at progress 1 (its ``new`` picture, exactly) and the record it draws each frame."""

    def __init__(self, core, engine, host, images, folder: Path) -> None:
        fsc = _fsc()
        self.core = core
        self.host = host
        self.scene = fsc.Scene(core, engine, host, 1.0, card=SIZE)
        values = fsc._values("crossfade", {}, images[:2], SIZE, {}, "crossfade")
        _core, self.settings, self.record = fsc.split_values("crossfade", values[1.0])
        self.scene.pictures(images[:2])
        self.scene.program("crossfade", fsc.transition_pass("crossfade", folder / "swap"), self.settings)

    def frame(self) -> None:
        self.scene.stream.publish(self.record)
        self.scene.mode.update()
        self.host.frames(1)

    def show(self):
        return self.scene.show(self.record)

    def timed_frame(self) -> float:
        """One frame's wall time on the calling thread (ms): the hidden host's sync, render and end of frame (which
        waits for the GPU), so it holds every render-thread cost of the frame, Qt's deferred OpenGL commands included."""
        self.scene.stream.publish(self.record)
        self.scene.mode.update()
        started = time.perf_counter()
        self.host.frames(1)
        return (time.perf_counter() - started) * 1000.0

    def timed_swap(self, image, *, in_frame: bool) -> dict:
        """``image`` (with mips) set as ``new``: the hand-over frame's and the commit frame's wall times, and the
        frames drawn between (no readback, nothing else in the frames)."""
        before = _state(self.scene).get("texture_uploads", 0)
        self.scene.mode.texture("new", image.tobytes(), image.size, mips=True, in_frame=in_frame)
        handover = self.timed_frame()
        between: list[float] = []
        commit = None
        if _state(self.scene).get("texture_uploads", 0) <= before:
            for _ in range(MAX_WAIT_FRAMES):
                ms = self.timed_frame()
                if _state(self.scene).get("texture_uploads", 0) > before:
                    commit = ms
                    break
                between.append(ms)
        return {"handover_ms": round(handover, 4), "commit_ms": None if commit is None else round(commit, 4),
                "frames_between": len(between), "between_ms": [round(v, 4) for v in between[:8]]}

    def swap(self, image, *, in_frame: bool) -> dict:
        """``image`` (with its GPU mips: the photo's job) set as ``new`` while drawing: the hand-over frame read back,
        then frames until it is committed, then the committed frame read back."""
        before = _state(self.scene)
        self.scene.mode.texture("new", image.tobytes(), image.size, mips=True, in_frame=in_frame)
        started = time.perf_counter()
        handover = self.show()                     # the record that takes the image
        waited = 0
        state = _state(self.scene)
        while state.get("texture_uploads", 0) <= before.get("texture_uploads", 0) and waited < MAX_WAIT_FRAMES:
            self.frame()
            waited += 1
            state = _state(self.scene)
        committed = self.show()
        return {"handover": handover, "committed": committed, "frames_while_uploading": waited,
                "seconds": round(time.perf_counter() - started, 4), "before": before, "after": _state(self.scene),
                "committed_in_time": state.get("texture_uploads", 0) > before.get("texture_uploads", 0)}

    def close(self, app) -> None:
        self.scene.close(app)


def _change_records(state: dict, since: int = 0) -> list[dict]:
    return list(state.get("image_changes") or [])[since:]


def _ms_stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {"n": len(values), "median_ms": round(statistics.median(values), 4), "max_ms": round(max(values), 4),
            "min_ms": round(min(values), 4)}


def round_swap(core, engine, app, api: str, folder: Path, out: Path, photo_paths) -> dict:
    fsc = _fsc()
    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {}
    images = _photos(photo_paths)
    host = core.hidden_host(SIZE[0] + 2 * fsc.MARGIN, SIZE[1] + 2 * fsc.MARGIN)
    swapper = None
    tiles = []
    try:
        swapper = Swapper(core, engine, host, images, folder)
        first = swapper.show()
        checks["first_pictures_drawn"] = _drawn_equals(first, images[1])
        state = _state(swapper.scene)
        facts["route"] = _jobs(state).get("route")
        checks["route_is_the_devices"] = facts["route"] == ("job" if vulkan else "in_frame")
        routes = ("default", "in_frame") if vulkan else ("default",)
        host.set_gpu_timer(True)
        host.gpu_samples()
        drawn: dict = {}
        per_route: dict = {}
        previous = images[1]
        for route in routes:
            in_frame = route == "in_frame"
            since = len(_change_records(_state(swapper.scene)))
            swaps = []
            for index, image in enumerate(images[2:] + images[1:2]):
                result = swapper.swap(image, in_frame=in_frame)
                key = f"{route}_{index}"
                drawn[key] = fsc.digest(result["committed"])
                swaps.append({"frames_while_uploading": result["frames_while_uploading"],
                              "seconds": result["seconds"], "committed_in_time": result["committed_in_time"],
                              "committed_equals_photo": _drawn_equals(result["committed"], image),
                              "handover_equals_previous": _drawn_equals(result["handover"], previous),
                              "handover_equals_new": _drawn_equals(result["handover"], image)})
                if index < 2:
                    tiles.append(_tile(result["handover"]))
                    tiles.append(_tile(result["committed"]))
                previous = image
            state = _state(swapper.scene)
            records = _change_records(state, since)
            samples = host.gpu_samples()
            surface_ms = [s.nanoseconds / 1e6 for s in samples if s.kind == 2]
            change_edges = {int(r.get("edge", -1)) for r in records}
            per_route[route] = {
                "swaps": swaps,
                "image_changes": records,
                "record_ms_by_kind": {kind: _ms_stats([r["record_ms"] for r in records if r["kind"] == kind])
                                      for kind in sorted({r["kind"] for r in records})},
                "record_ms_all_changes": _ms_stats([r["record_ms"] for r in records]),
                "gpu_surface_ms_change_frames": _ms_stats([s.nanoseconds / 1e6 for s in samples
                                                           if s.kind == 2 and s.frame in change_edges]),
                "gpu_surface_ms_all": _ms_stats(surface_ms),
                "texture_jobs": _jobs(state),
            }
            # The whole frame's cost (OpenGL's QRhi runs an upload at the end of the frame, after the core's record, so
            # the record time alone misses it there): plain frames, then each photo's hand-over and commit frames.
            baseline = [swapper.timed_frame() for _ in range(8)]
            timed = [swapper.timed_swap(image, in_frame=in_frame) for image in images[2:] + images[1:2]]
            change = [t["handover_ms"] for t in timed] + [t["commit_ms"] for t in timed if t["commit_ms"] is not None]
            per_route[route]["frame_ms"] = {"plain": _ms_stats(baseline), "image_change": _ms_stats(change),
                                            "swaps": timed}
            host.gpu_samples()
            checks[f"{route}_every_swap_committed"] = all(s["committed_in_time"] for s in swaps)
            checks[f"{route}_every_swap_draws_its_photo"] = all(s["committed_equals_photo"] for s in swaps)
        facts["routes"] = per_route
        default = per_route["default"]
        if vulkan:
            # The latch: the hand-over record draws the previous photo; the swap lands on a later frame.
            checks["job_handover_keeps_the_previous_photo"] = all(
                s["handover_equals_previous"] and not s["handover_equals_new"] for s in default["swaps"])
            checks["job_frames_drawn_while_uploading"] = all(s["frames_while_uploading"] >= 1 for s in default["swaps"])
            jobs = default["texture_jobs"]
            checks["job_route_committed_by_jobs_no_fallback"] = (
                jobs.get("committed", 0) >= len(default["swaps"]) and jobs.get("fell_back", 0) == 0
                and jobs.get("import_failures", 0) == 0)
            control = per_route["in_frame"]
            checks["in_frame_control_uploads_in_the_frame"] = all(s["handover_equals_new"]
                                                                  for s in control["swaps"])
            checks["job_frames_equal_in_frame_frames"] = all(
                drawn[f"default_{i}"] == drawn[f"in_frame_{i}"] for i in range(len(default["swaps"])))
            job_ms = [r["record_ms"] for r in default["image_changes"]]
            frame_ms = [r["record_ms"] for r in control["image_changes"] if "in_frame" in r["kind"]]
            checks["render_thread_cost_below_in_frame"] = bool(job_ms) and bool(frame_ms) and max(job_ms) < min(frame_ms)
            facts["render_thread_cost_ms"] = {"job": _ms_stats(job_ms), "in_frame": _ms_stats(frame_ms)}
            facts["frame_cost_ms"] = {route: per_route[route]["frame_ms"] for route in routes}
            job_frames = default["frame_ms"]["image_change"]
            control_frames = control["frame_ms"]["image_change"]
            checks["image_change_frames_cheaper_than_in_frame"] = (
                job_frames.get("n", 0) > 0 and control_frames.get("n", 0) > 0
                and job_frames["median_ms"] < control_frames["median_ms"])
            # A superseded image: the first photo's job cancelled, one commit, the second drawn.
            before = _jobs(_state(swapper.scene))
            uploads_before = _state(swapper.scene).get("texture_uploads", 0)
            swapper.scene.mode.texture("new", images[2].tobytes(), images[2].size)
            swapper.frame()                                   # hands the first over to its job
            result = swapper.swap(images[3], in_frame=False)  # supersedes it at once
            after = _jobs(result["after"])
            facts["superseded"] = {"before": before, "after": after,
                                   "frames_while_uploading": result["frames_while_uploading"]}
            checks["superseded_image_cancelled"] = (
                after.get("cancelled", 0) == before.get("cancelled", 0) + 1
                and result["after"].get("texture_uploads", 0) == uploads_before + 1
                and _drawn_equals(result["committed"], images[3]))
        else:
            facts["render_thread_cost_ms"] = {"in_frame": _ms_stats([r["record_ms"] for r in default["image_changes"]])}
            facts["frame_cost_ms"] = {"default": default["frame_ms"]}
        # Nothing at rest (after the last swap's retired image went: its frames were drawn above).
        host.frames(REST_FRAMES)
        rest_before = (_state(swapper.scene), core.job_counts(), swapper.scene.mode.composite.state())
        host.gpu_samples()
        # A timed frame's result is read latched (never waited for), so a late one can arrive during the rest; it
        # carries its own, earlier, frame: only passes of frames after the rest began count (N4.a's timing round).
        rest_start = int((host.state().get("driver") or {}).get("edges", 0))
        host.frames(REST_FRAMES)
        rest_after = (_state(swapper.scene), core.job_counts(), swapper.scene.mode.composite.state())
        rest_samples = [s for s in host.gpu_samples() if s.kind == 2 and s.frame > rest_start]
        host.set_gpu_timer(False)
        checks["nothing_at_rest"] = (
            rest_after[0].get("records") == rest_before[0].get("records")
            and rest_after[1].get("job_wakeups") == rest_before[1].get("job_wakeups")
            and rest_after[1].get("job_images_retiring") == 0 and rest_after[1].get("jobs_queued") == 0
            and rest_after[1].get("jobs_running") == 0
            and rest_after[2]["surface"]["passes_recorded"] == rest_before[2]["surface"]["passes_recorded"]
            and not rest_samples)
        facts["rest"] = {"job_counts": rest_after[1], "records": [rest_before[0].get("records"),
                                                                  rest_after[0].get("records")],
                         "gpu_surface_samples": len(rest_samples)}
        if vulkan:
            services = core.job_services_state(with_log=True)
            facts["job_services"] = services
            log = [entry for service in services.get("services", []) for entry in service.get("log", [])]
            done = [entry for entry in log if entry.get("state") == "done"]
            facts["job_latency"] = {key: _ms_stats([e[key] for e in done if e.get(key, -1) >= 0])
                                    for key in ("queued_ms", "record_ms", "gpu_wait_ms", "latency_ms")}
            checks["job_thread_without_python"] = all(
                s.get("thread_calls_with_python_thread_state") == 0 and s.get("thread_calls_on_gui_thread") == 0
                and s.get("thread_calls", 0) > 0 for s in services.get("services", []))
            checks["job_qrhi_on_the_device_and_job_queue"] = all(
                (s.get("backend") or {}).get("on_our_device_and_queue") is True for s in services.get("services", []))
        # The lost edge: the node made again; the owner called once, on the GUI thread, with both names.
        calls: list[list[str]] = []
        swapper.scene.mode.on_textures_lost(lambda names: calls.append(sorted(names)))
        edges_before = _state(swapper.scene).get("textures_lost_edges", 0)
        swapper.scene.mode.composite.set(rect=[0.0, 0.0, 0.0, 0.0])
        host.frames(2)
        swapper.scene.mode.composite.set(rect=[0.0, 0.0, float(SIZE[0]), float(SIZE[1])])
        lost_frame = swapper.show()
        app.processEvents()
        swapper.frame()
        app.processEvents()
        checks["lost_edge_called_once_with_both_names"] = calls == [["new", "old"]]
        checks["lost_frame_draws_nothing"] = float(lost_frame[..., :3].max()) == 0.0
        swapper.scene.pictures(images[:2])
        again = swapper.show()
        checks["sent_again_draws"] = _drawn_equals(again, images[1])
        swapper.scene.mode.on_textures_lost(None)
        facts["lost"] = {"calls": calls, "edges": [edges_before, _state(swapper.scene).get("textures_lost_edges")]}
    finally:
        if swapper is not None:
            swapper.close(app)
        host.frames(2)
        _flush(app)
        core.wait_jobs_idle(20000)
        facts["host_close"] = host.close()
        _flush(app)
    if tiles:
        _sheet(out / f"job_service_{api}.png", tiles)
    facts["drawn_hashes"] = drawn if "drawn" in locals() else {}
    if vulkan:
        # N3.6: the job QRhi loaded the core's pipeline cache file at its creation and kept its rule at the device's
        # orderly teardown (the run's own directory: child() points the module at it).
        facts["pipeline_cache"] = pipeline_cache_records(facts.get("host_close"))
        facts["pipeline_cache_save_outcomes"] = [pipeline_cache_save_outcome(r.get("pipeline_cache_save") or {})
                                                 for r in facts["pipeline_cache"]]
        checks["pipeline_cache_loaded_and_saved_by_rule"] = pipeline_cache_by_rule(facts["pipeline_cache"])
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def pipeline_cache_records(host_close) -> list[dict]:
    """The job services' stop records in a closed host's device teardown (``job service stopped: <json>``)."""
    prefix = "job service stopped: "
    records = []
    for step in (host_close or {}).get("device_teardown") or []:
        if isinstance(step, str) and step.startswith(prefix):
            try:
                records.append(json.loads(step[len(prefix):]))
            except ValueError:
                records.append({})
    return records


def pipeline_cache_save_outcome(save: dict) -> str:
    """What the teardown did with the core's file: ``saved``, ``nothing to save``, ``skipped: <reason>`` or
    ``missing``. A commit that failed (``save_failed``: on Windows a rename over a file another window's reader holds
    open fails) is a reported skip, not an error (checkpoint audit 11 L3): the file then stays some earlier writer's
    whole file, never a torn one, and the next orderly teardown writes again ("some writer wins"). A lost device's
    teardown saves nothing (``save``: skipped)."""
    if float(save.get("saved_bytes", 0) or 0) > 0:
        return "saved"
    text = str(save.get("save", ""))
    if text.startswith("nothing to save"):
        return "nothing to save"
    if text.startswith("skipped"):
        return text
    if save.get("save_failed"):
        return f"skipped: the commit failed ({save['save_failed']})"
    return "missing"


def pipeline_cache_by_rule(records: list[dict]) -> bool:
    """One service whose QRhi read the core's file at its creation (absent in a fresh directory, else accepted or
    refused with its reason) and, at the orderly teardown, wrote its blob, had nothing to write, or reported why it
    skipped the write (``pipeline_cache_save_outcome``)."""
    if len(records) != 1:
        return False
    load = records[0].get("pipeline_cache_load") or {}
    save = records[0].get("pipeline_cache_save") or {}
    loaded = str(load.get("result", "")).startswith(("absent", "accepted", "rejected: "))
    return loaded and pipeline_cache_save_outcome(save) != "missing"


def round_lifetime(core, engine, app, api: str, folder: Path, photo_paths) -> dict:
    """Teardown with jobs in flight: the item and the host closed right after the hand-over frame."""
    fsc = _fsc()
    checks: dict = {}
    facts: dict = {}
    images = _photos(photo_paths[:2])
    host = core.hidden_host(SIZE[0] + 2 * fsc.MARGIN, SIZE[1] + 2 * fsc.MARGIN)
    scene = fsc.Scene(core, engine, host, 1.0, card=SIZE)
    try:
        scene.pictures(images, settle=False)
        scene.mode.update()
        host.frames(1)                                      # the hand-over: the jobs start
        facts["at_close"] = {"job_counts": core.job_counts(), "texture_jobs": _jobs(_state(scene))}
    finally:
        scene.close(app)
        facts["host_close"] = host.close()                  # the device (and its job service) goes here
        _flush(app)
    counts = core.job_counts()
    live = core.composite_live()
    facts["after"] = {"job_counts": counts, "composites": live}
    if api == "vulkan":
        checks["jobs_were_in_flight_at_close"] = (facts["at_close"]["job_counts"].get("jobs_queued", 0)
                                                  + facts["at_close"]["job_counts"].get("jobs_running", 0)
                                                  + facts["at_close"]["job_counts"].get("job_images", 0)) > 0
        steps = json.dumps(facts["host_close"])
        checks["service_stopped_with_the_device"] = "job service stopped" in steps
    checks["no_job_or_texture_left"] = (
        all(not counts.get(key) for key in ("job_services", "job_threads", "jobs_queued", "jobs_running",
                                            "job_images", "job_releases_pending", "job_images_retiring"))
        and fsc._nothing_left(live))
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _flush(app) -> None:
    import host_check

    host_check._flush_deletes(app)


def _sheet(path: Path, tiles) -> None:
    from PIL import Image

    columns = 4
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (SHEET_TILE[0] * columns, SHEET_TILE[1] * rows))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * SHEET_TILE[0], (index // columns) * SHEET_TILE[1]))
    sheet.save(path)


# --------------------------------------------------------------------------------------------------- the child

def child(args) -> dict:
    import host_check
    import vk_validation

    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    photo_paths = tuple(Path(p) for p in args.photos)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False,
                    "photos": [p.name for p in photo_paths]}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="job-service-check")
        from PySide6.QtWidgets import QApplication

        app = QApplication([sys.argv[0]])
    else:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication([sys.argv[0]])
    from PySide6.QtQml import QQmlEngine
    from rendering.native import NativeCoreUnavailable, load

    try:
        core = load((root / args.module_dir) if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    except NativeCoreUnavailable as exc:
        record["error"] = f"the module did not load: {exc.reason}"
        return record
    record["module_loaded"] = True
    record["runtime"] = dict(core.info)
    vulkan = args.api == "vulkan"
    if vulkan:
        instance = core.vulkan_instance(validation=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    with tempfile.TemporaryDirectory(prefix="srpss_n38_") as scratch:
        folder = Path(scratch)
        if vulkan:
            # N3.6: the job QRhi's pipeline cache file in the run's own directory, never the user's cache.
            record["pipeline_cache_directory"] = core.pipeline_cache_directory(folder / "pipeline_cache")
        try:
            for name in args.rounds:
                if vulkan:
                    core.set_vulkan_phase(f"n38 {name}")
                try:
                    if name == "swap":
                        record[name] = round_swap(core, engine, app, args.api, folder, out, photo_paths)
                    else:
                        record[name] = round_lifetime(core, engine, app, args.api, folder, photo_paths)
                except Exception:
                    record[name] = {"pass": False, "error": traceback.format_exc()}
        finally:
            _flush(app)
            record["live_hosts_at_end"] = core.live_hosts()
            record["composites_at_end"] = core.composite_live()
            record["jobs_at_end"] = core.job_counts()
            record["readers_at_end"] = core.packet_reader_live()
            if vulkan:
                teardown = core.destroy_vulkan_instance()
                messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
                summary = vk_validation.validation_summary(messages)
                record["instance_teardown"] = teardown
                record["validation"] = {"layer_loaded": bool(record["instance"].get("validation_layer_loaded")),
                                        "per_phase": messages.get("per_phase"),
                                        **{k: v for k, v in summary.items() if k != "groups"},
                                        "attribution": summary["groups"]}
            del engine
    return record


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    import host_check

    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        if not _fsc()._nothing_left(record.get("composites_at_end") or {}):
            failed.append(f"{api}: composites or textures left at the end ({record.get('composites_at_end')})")
        jobs = record.get("jobs_at_end") or {}
        left = {k: v for k, v in jobs.items() if k in ("job_services", "job_threads", "jobs_queued", "jobs_running",
                                                        "job_images", "job_releases_pending", "job_images_retiring")
                and v}
        if left:
            failed.append(f"{api}: job work left at the end ({left})")
    return not failed, failed


def main(argv: list[str] | None = None) -> int:
    import host_check
    import vk_validation

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--photos", nargs="+", default=[str(p) for p in PHOTOS],
                        help="real 3840 x 2160 photos, at least four (default: six PERSONALSET wallpapers)")
    parser.add_argument("--label", default="n38_job_service")
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

    missing = [p for p in args.photos if not Path(p).is_file()]
    if missing or len(args.photos) < 4:
        print(f"N38 VERDICT FAIL: four or more photos are needed ({', '.join(missing) or len(args.photos)})")
        return 0
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n3_8", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)  # discard any earlier child record before launch
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds, "--photos", *args.photos]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "rounds": list(args.rounds), "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        results[api] = record

    verdicts = {api: api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "photos": args.photos, "environment": environment,
               "require_validation": args.require_validation,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
        facts = (results[api].get("swap") or {}).get("facts") or {}
        if facts.get("render_thread_cost_ms"):
            print(f"{api} record time per image change at {SIZE[0]}x{SIZE[1]}: {facts['render_thread_cost_ms']}")
        for route, frames in (facts.get("frame_cost_ms") or {}).items():
            print(f"{api} {route} frame time: plain {frames['plain']}, image change {frames['image_change']}")
    print(f"evidence: {out / 'summary.json'}")
    print("N38 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
