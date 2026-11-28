"""N5.7a's proof of the display's background layer on the native core (D7 point 1; Current_Plan.md section N2b) and of
the N3.8 audit's fixes it builds on, through ``rendering.native`` and the product's own route
(``rendering/quick/render/native_background.py``), in hidden hosts only (never a window on a screen).

Real photos (PERSONALSET wallpapers) are processed by the product's own worker arithmetic
(``AsyncImageProcessor.process_qimage``: FILL, and FIT for the portrait and the odd aspect) into the display's device
pixels and detached as the runtime detaches them (``presentation_image_from_processed_qimage``). The display lies in
the window as the product lays it out: its scene root at a whole device pixel inside an overscanned window (one device
pixel right, two down), at dpr 1 and 1.5.

Rounds (one child process per API; OpenGL first, its frames kept for Vulkan's comparison):
  draw      every photo and fit at both dprs: OpenGL's Python presenter (the product's ``BackgroundRenderItem``, its
            retained ``QSGImageNode``) is the reference, drawn in a hidden host of its own; the native layer in another
            (the frame driver's probe clean of Python): rule (a) OpenGL native equal to the Python presenter, pixel for
            pixel over the whole window; rule (b) Vulkan native equal to OpenGL native under VULKAN_RULE_B (and, as a fact, of the
            Python reference); a stale image (processed for dpr 1, shown at 1.5: both stretch it by the one placement
            owner) recorded against the Python presenter's (a fact); the negative control: a native frame against
            another photo's reference differs.
            Vulkan also through the product's route (``BackgroundRenderItem`` on the native backend makes the layer at
            its first image): the same pixels as the layer drawn directly.
  change    4K photos changed while drawing, each through the device's route (Vulkan: N3.8's job service): the
            hand-over frame keeps the previous photo and records no pass (the still keeps its target), frames go on
            while the job runs, the commit frame draws the new photo exactly and records one pass; the render thread's
            record time and the GUI thread's hand-over per change; every change committed by a job, none fell back.
  rest      after the last change: no pass, no record, no job wake-up, no GPU surface sample; the replaced photo's
            output released once its frames completed, with the retire list's own frame requests (audit M2); nothing
            retiring and one output held (the front).
  edges     audit M1 on a real render: a host detached and attached in one GUI turn, then frames: the window's edge
            count moves by one per frame, and the module's GPU-free count of two drivers' edges in one frame
            (window_edges_self_test: the hidden host releases a detached driver at once, so only that count has two
            drivers in one frame; its control, the count before M1, was [1, 2, 3, 4]).
  cost      at 2560 x 1440: QRhi's whole-frame GPU time and the frame's wall time at rest, the native layer against the
            protected retained-background path (the Python presenter, OpenGL) and an empty scene (control).
  lifetime  the lost edge (the node made again: the layer sends its photo again and draws it); teardown with the upload
            job in flight; nothing left (items, surfaces, textures, jobs).
Facts: the frame driver's and the job thread's thread probes (no Python thread state), validation per phase (Vulkan).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/background_layer_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds draw change rest edges cost lifetime] [--label n57a_background_layer]
Evidence: .artifacts/evidence/native_core/n5_7a/<date>_<label>/ (summary.json; one PNG sheet per API; the OpenGL frames
for Vulkan's comparison in work/). Exit 0 whenever the harness ran; the verdict is the last printed line
("N57A VERDICT PASS" or "N57A VERDICT FAIL: ...").
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
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import pixel_tolerance as pt  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("draw", "change", "rest", "edges", "cost", "lifetime")
CHILD_TIMEOUT_S = 1800
PHOTO_FOLDER = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET")
#: (label, file, fits): a landscape at the display's aspect, a landscape FILL crops, a portrait, an odd aspect (3:1).
PHOTOS = (
    ("landscape", "Usu_Underwater_Lab_1440p.png", ("fill",)),
    ("landscape_crop", "UsuScene1.png", ("fill",)),
    ("portrait", "05.04.2013.jpg", ("fill", "fit")),
    ("odd_aspect", "13.03.2011.jpg", ("fill", "fit")),
)
CHANGE_PHOTOS = tuple(PHOTO_FOLDER / f"theVideoGameGallery_{n}_3840x2160.jpg" for n in (27137, 27086, 26861, 26381))
DISPLAY = (1284 - 4, 726 - 6)       # the display's device pixels (1280 x 720)
WINDOW = (1284, 726)                # the overscanned window's (whole logical pixels at dpr 1.5: 856 x 484)
OFFSET = (1, 2)                     # the display's origin in the window, in device pixels (the R-63 overscan)
DPRS = (1.0, 1.5)
CHANGE_SIZE = (3840, 2160)
COST_SIZE = (2560, 1440)
#: Rule (b), judged pixel by pixel by the shared tolerance (``tools/pixel_tolerance.py``, D12 "The pixel tolerance"):
#: the layer draws an opaque photo unfiltered, and the two APIs' frames are bit for bit the same (measured: 0 differing
#: pixels in every one of the 13 frames), so the bound is exact: no mask, no scatter, no tie.
VULKAN_RULE_B = pt.EXACT
STALE_TOLERANCE = 1                 # a stretched stale image, native against the Python presenter
MAX_WAIT_FRAMES = 600
REST_FRAMES = 6
TIMED_FRAMES = 120
SHEET_TILE = (320, 180)
_ALLOWED_ENV: set[str] = set()

SCENE_QML = b"""import QtQuick
Rectangle {
    color: "#000000"
    Item { objectName: "sceneRoot" }
}
"""


# --------------------------------------------------------------------------------------------------- the photos


def processed(path: Path, fit: str, size: tuple[int, int]):
    """``path`` processed as the image worker does for a display of ``size`` device pixels, detached as the runtime
    detaches it: (the PresentationImage, its RGBA rows as an array)."""
    import numpy as np
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage

    from rendering.display_modes import DisplayMode
    from rendering.image_processor_async import AsyncImageProcessor
    from rendering.quick.display_image_route import presentation_image_from_processed_qimage

    source = QImage(str(path))
    if source.isNull():
        raise RuntimeError(f"{path} does not load")
    mode = DisplayMode.FILL if fit == "fill" else DisplayMode.FIT
    image = AsyncImageProcessor.process_qimage(source, QSize(*size), mode, "smooth", False)
    presentation = presentation_image_from_processed_qimage(image, image_path=f"{path}#{fit}")
    rows = np.frombuffer(presentation.rgba8, dtype=np.uint8).reshape(size[1], size[0], 4).copy()
    return presentation, rows


def display_rows(rows, display: tuple[int, int]):
    """The display's own pixels in a window frame (its scene root at OFFSET device pixels)."""
    x, y = OFFSET
    return rows[y:y + display[1], x:x + display[0]]


def compare(a, b) -> dict:
    import numpy as np

    if a.shape[:2] != b.shape[:2]:
        return {"equal": False, "shape": [list(a.shape), list(b.shape)], "max_level": 255, "differing_pixels": -1}
    difference = np.abs(a[..., :3].astype(np.int16) - b[..., :3].astype(np.int16))
    differing = int(np.count_nonzero(difference.max(axis=2)))
    return {"equal": differing == 0, "differing_pixels": differing, "max_level": int(difference.max())}


# --------------------------------------------------------------------------------------------------- the scene


class Scene:
    """A black window with the display's scene root on whole device pixels at OFFSET (the overscan placement), and in
    it one background: the product's ``BackgroundRenderItem`` (the Python presenter, or on the native backend its
    route), or a plain item the native layer is made in."""

    def __init__(self, core, engine, host, dpr: float, display: tuple[int, int], *, kind: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        self.core = core
        self.host = host
        self.dpr = float(dpr)
        self.display = display
        self.kind = kind
        self.component = QQmlComponent(engine)
        self.component.setData(SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        host.set_content(self.root)
        scene = self.root.findChild(QQuickItem, "sceneRoot")
        scene.setX(OFFSET[0] / self.dpr)
        scene.setY(OFFSET[1] / self.dpr)
        scene.setWidth(display[0] / self.dpr)
        scene.setHeight(display[1] / self.dpr)
        self.layer = None
        if kind == "layer":
            from rendering.quick.render.native_background import NativeBackgroundLayer

            self.item = QQuickItem(scene)
            self.item.setWidth(scene.width())
            self.item.setHeight(scene.height())
            self.layer = NativeBackgroundLayer(core, self.item)
        else:
            from rendering.quick.render.background_item import BackgroundRenderItem
            from rendering.quick.render.telemetry import RenderNodeTelemetry

            if kind not in ("python", "route"):
                raise ValueError(f"unknown scene kind {kind!r}")
            self.item = BackgroundRenderItem(scene, telemetry=RenderNodeTelemetry(), screen_index=0)
            if kind == "python":
                # The Python presenter as the reference (N5.2h: the product draws natively on both APIs; the harness
                # keeps today's Python drawing until the references are cached, the switch's cache box).
                self.item._renderers_on_backend = True
                self.item._native_layer_wanted = False
            self.item.setWidth(scene.width())
            self.item.setHeight(scene.height())

    def present(self, image) -> float:
        """The image handed over (the product's call); returns the GUI thread's milliseconds for it."""
        started = time.perf_counter()
        if self.layer is not None:
            self.layer.present(image)
        else:
            self.item.set_presentation_image(image)
            if self.item.native_layer is not None:
                self.layer = self.item.native_layer      # the route made it (the native backend)
        return (time.perf_counter() - started) * 1000.0

    def frames(self, count: int = 1) -> None:
        """``count`` frames, the GUI thread's queued events delivered before each (as the product's event loop does: the
        job's frame request is a queued ``update()`` of the item, the layer's fade is a GUI-thread animation)."""
        from PySide6.QtCore import QCoreApplication

        for _ in range(count):
            QCoreApplication.processEvents()
            self.host.frames(1)

    def settle(self) -> None:
        """The image committed and the layer's fade done before the next read: one frame hands the image over, the jobs
        are waited for (a harness's wait, never the product's), frames commit it, and the fade-in (the layer's first
        photo) is let run to its end."""
        from PySide6.QtCore import QCoreApplication, QEventLoop

        self.frames(1)
        if not self.core.wait_jobs_idle(20000):
            raise RuntimeError("the upload jobs did not finish within 20 s")
        self.frames(2)
        deadline = time.monotonic() + 10.0
        while self.layer is not None and self.layer.mode is not None and time.monotonic() < deadline:
            if not self.layer.mode.composite.state().get("fading"):
                break
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 16)
        self.frames(2)

    def read(self):
        from PySide6.QtCore import QCoreApplication

        from composite_analysis import frame_rows

        QCoreApplication.processEvents()
        return frame_rows(asdict(self.host.read()))

    def display_rows(self, rows):
        return display_rows(rows, self.display)

    def mode_state(self) -> dict:
        return self.layer.mode.state() if self.layer is not None and self.layer.mode is not None else {}

    def composite_state(self) -> dict:
        return self.layer.mode.composite.state() if self.layer is not None and self.layer.mode is not None else {}

    def close(self, app) -> None:
        import host_check

        if self.layer is not None:
            self.layer.close()
        if hasattr(self.item, "close_native_layer"):
            self.item.close_native_layer()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


def _host(core, size, dpr: float = 1.0, timestamps: bool = False):
    return core.hidden_host(size[0], size[1], dpr=dpr, timestamps=timestamps)


def _driver(host) -> dict:
    return dict((host.state().get("driver") or {}))


def _flush(app) -> None:
    import host_check

    host_check._flush_deletes(app)


def _close_host(app, host) -> dict:
    _flush(app)
    result = host.close()
    _flush(app)
    return result


def _ms_stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {"n": len(values), "median_ms": round(statistics.median(values), 4),
            "p90_ms": round(ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))], 4),
            "max_ms": round(max(values), 4)}


def _tile(rows):
    from PIL import Image

    return Image.fromarray(rows[..., :3].copy(), "RGB").resize(SHEET_TILE)


def _sheet(path: Path, rows_of_tiles) -> None:
    from PIL import Image

    columns = max(len(row) for row in rows_of_tiles)
    sheet = Image.new("RGB", (SHEET_TILE[0] * columns, SHEET_TILE[1] * len(rows_of_tiles)))
    for r, row in enumerate(rows_of_tiles):
        for c, tile in enumerate(row):
            sheet.paste(tile, (c * SHEET_TILE[0], r * SHEET_TILE[1]))
    sheet.save(path)


# --------------------------------------------------------------------------------------------------- draw


def _variants():
    for label, name, fits in PHOTOS:
        for fit in fits:
            yield f"{label}_{fit}", PHOTO_FOLDER / name, fit


def round_draw(core, engine, app, api: str, work: Path, out: Path) -> dict:
    import numpy as np

    checks: dict = {}
    facts: dict = {"variants": {}}
    vulkan = api == "vulkan"
    images = {}
    for key, path, fit in _variants():
        for dpr in DPRS:
            images[(key, dpr)] = processed(path, fit, DISPLAY)
    # The stale image: processed for a dpr-1 display of the same logical size, shown at 1.5 (both paths stretch it).
    stale_size = (round(DISPLAY[0] / 1.5), round(DISPLAY[1] / 1.5))
    stale = processed(PHOTO_FOLDER / PHOTOS[0][1], "fill", stale_size)
    native: dict = {}
    reference: dict = {}
    tiles = []
    for dpr in DPRS:
        if not vulkan:
            # The reference: the Python presenter, in a host of its own (Python runs at its sync there).
            host = _host(core, WINDOW, dpr)
            scene = Scene(core, engine, host, dpr, DISPLAY, kind="python")
            try:
                for key, _path, _fit in _variants():
                    scene.present(images[(key, dpr)][0])
                    host.frames(2)
                    reference[(key, dpr)] = scene.read()
                if dpr == 1.5:
                    scene.present(stale[0])
                    host.frames(2)
                    reference[("stale", dpr)] = scene.read()
            finally:
                scene.close(app)
                facts.setdefault("host_close", []).append(_close_host(app, host))
        host = _host(core, WINDOW, dpr)
        scene = Scene(core, engine, host, dpr, DISPLAY, kind="layer")
        try:
            for key, _path, _fit in _variants():
                scene.present(images[(key, dpr)][0])
                scene.settle()
                native[(key, dpr)] = scene.read()
            if dpr == 1.5:
                scene.present(stale[0])
                scene.settle()
                native[("stale", dpr)] = scene.read()
            facts[f"driver_dpr_{dpr}"] = _driver(host)
            facts[f"composite_dpr_{dpr}"] = scene.composite_state()
            facts[f"mode_dpr_{dpr}"] = {k: v for k, v in scene.mode_state().items()
                                        if k in ("still", "texture_uploads", "texture_jobs", "still_kept", "records",
                                                 "draws", "last_reason")}
        finally:
            scene.close(app)
            facts.setdefault("host_close", []).append(_close_host(app, host))
    keys = [(key, dpr) for key, _p, _f in _variants() for dpr in DPRS]
    for (key, dpr) in keys:
        drawn = native[(key, dpr)]
        photo_rows = images[(key, dpr)][1]
        entry = {"photo": compare(display_rows(drawn, DISPLAY), photo_rows)}
        if not vulkan:
            entry["python"] = compare(drawn, reference[(key, dpr)])
            entry["python_equals_photo"] = compare(display_rows(reference[(key, dpr)], DISPLAY), photo_rows)["equal"]
        facts["variants"][f"{key}@{dpr}"] = entry
        if len(tiles) < 4:
            tiles.append([_tile(drawn)] + ([_tile(reference[(key, dpr)])] if not vulkan else []))
    np.savez_compressed(work / f"frames_{api}.npz", **{f"{key}@{dpr}": rows for (key, dpr), rows in native.items()})
    if not vulkan:
        np.savez_compressed(work / "frames_python.npz",
                            **{f"{key}@{dpr}": rows for (key, dpr), rows in reference.items()})
        checks["rule_a_native_equals_python_presenter"] = all(
            facts["variants"][f"{k}@{d}"]["python"]["equal"] for k, d in keys)
        checks["python_presenter_draws_the_photo_exactly"] = all(
            facts["variants"][f"{k}@{d}"]["python_equals_photo"] for k, d in keys)
        # A fact (both paths stretch a stale image by the one owner's rule, each through its own interpolation).
        facts["stale"] = dict(compare(native[("stale", 1.5)], reference[("stale", 1.5)]),
                              within_tolerance=None)
        facts["stale"]["within_tolerance"] = facts["stale"]["max_level"] <= STALE_TOLERANCE
        # Negative control: a native frame against another photo's reference differs.
        first, second = keys[0], keys[2]
        control = compare(native[first], reference[second])
        facts["control_other_photo"] = control
        checks["control_other_photo_differs"] = not control["equal"]
    checks["native_draws_the_photo_exactly"] = all(facts["variants"][f"{k}@{d}"]["photo"]["equal"] for k, d in keys)
    checks["frame_driver_without_python"] = all(
        facts[f"driver_dpr_{d}"].get("edges_with_python_thread_state", 1) == 0 for d in DPRS)
    checks["layer_is_opaque_background"] = all(
        (facts[f"composite_dpr_{d}"].get("sync") or {}).get("material_blending") is False
        and (facts[f"composite_dpr_{d}"].get("sync") or {}).get("layer") == "background" for d in DPRS)
    if vulkan:
        checks.update(_route_on_vulkan(core, engine, app, images, facts))
    _sheet(out / f"background_layer_{api}.png", tiles)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _route_on_vulkan(core, engine, app, images, facts) -> dict:
    """The product's route: ``BackgroundRenderItem`` on the native backend makes its layer at its first image and draws
    the same pixels as the layer drawn directly."""
    from rendering.quick import bootstrap

    owner = bootstrap._owner
    saved = (owner.core, owner.backend)
    owner.core, owner.backend = core, bootstrap.QuickBackend(api="vulkan", requested="vulkan")
    checks: dict = {}
    host = _host(core, WINDOW, 1.5)
    scene = Scene(core, engine, host, 1.5, DISPLAY, kind="route")
    try:
        key = next(iter(_variants()))[0]
        scene.present(images[(key, 1.5)][0])
        made = scene.item.native_layer is not None
        scene.settle()
        rows = scene.read()
        checks["route_makes_the_layer_at_the_first_image"] = made
        checks["route_draws_the_photo_exactly"] = compare(scene.display_rows(rows), images[(key, 1.5)][1])["equal"]
        facts["route"] = {"made": made, "layer": scene.item.native_layer.state() if made else None}
    finally:
        scene.close(app)
        facts.setdefault("host_close", []).append(_close_host(app, host))
        owner.core, owner.backend = saved
    return checks


def vulkan_against_opengl(work: Path) -> dict:
    import numpy as np

    vk_path, gl_path, py_path = (work / "frames_vulkan.npz", work / "frames_opengl.npz", work / "frames_python.npz")
    if not (vk_path.exists() and gl_path.exists()):
        return {"pass": False, "error": "both APIs' frames are needed"}
    vk, gl = np.load(vk_path), np.load(gl_path)
    py = np.load(py_path) if py_path.exists() else None
    results = {}
    judged: list[dict] = []
    for key in sorted(set(vk.files) & set(gl.files)):
        results[key] = {"opengl_native": compare(vk[key], gl[key])}
        if py is not None and key in py.files:
            results[key]["python"] = compare(vk[key], py[key])
        # A frame of another shape fails (judge reports it): compare() above has already said so.
        judged.append(pt.judge(vk[key][..., :3], gl[key][..., :3], VULKAN_RULE_B))
    worst = max((r["opengl_native"]["max_level"] for r in results.values()), default=255)
    tolerance = pt.summarise(judged)
    return {"pass": bool(results) and tolerance["pass"], "worst_level": worst, "tolerance": tolerance,
            "bound": VULKAN_RULE_B.bound(), "frames": results}


# --------------------------------------------------------------------------------------------------- change and rest


def _uploads(scene) -> int:
    return int(scene.mode_state().get("texture_uploads", 0))


def _passes(scene) -> int:
    return int((scene.composite_state().get("surface") or {}).get("passes_recorded", 0))


def round_change(core, engine, app, api: str, out: Path, rounds) -> dict:
    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {"changes": []}
    photos = [processed(path, "fill", CHANGE_SIZE) for path in CHANGE_PHOTOS]
    host = _host(core, (CHANGE_SIZE[0] + 4, CHANGE_SIZE[1] + 6))   # the display under the overscan placement
    scene = Scene(core, engine, host, 1.0, CHANGE_SIZE, kind="layer")
    tiles = []
    try:
        scene.present(photos[0][0])
        scene.settle()
        checks["first_photo_drawn"] = compare(scene.display_rows(scene.read()), photos[0][1])["equal"]
        host.set_gpu_timer(True)
        host.gpu_samples()
        previous = photos[0]
        since = len(scene.mode_state().get("image_changes") or [])
        requests_before = int(_driver(host).get("window_retire_frame_requests", 0))
        for photo in photos[1:] + photos[:1]:
            uploads, passes = _uploads(scene), _passes(scene)
            gui_ms = scene.present(photo[0])
            handover = scene.display_rows(scene.read())
            handover_passes = _passes(scene) - passes
            waited = 0
            while _uploads(scene) <= uploads and waited < MAX_WAIT_FRAMES:
                scene.frames(1)
                waited += 1
            committed = scene.display_rows(scene.read())
            facts["changes"].append({
                "gui_present_ms": round(gui_ms, 4), "frames_while_uploading": waited,
                "handover_equals_previous": compare(handover, previous[1])["equal"],
                "handover_equals_new": compare(handover, photo[1])["equal"],
                "committed_equals_new": compare(committed, photo[1])["equal"],
                "passes_at_handover": handover_passes, "passes_through_commit": _passes(scene) - passes})
            if len(tiles) < 4:
                tiles.append([_tile(handover), _tile(committed)])
            previous = photo
        state = scene.mode_state()
        records = list(state.get("image_changes") or [])[since:]
        facts["image_changes"] = records
        facts["record_ms"] = {kind: _ms_stats([r["record_ms"] for r in records if r["kind"] == kind])
                              for kind in sorted({r["kind"] for r in records})}
        facts["gui_present_ms"] = _ms_stats([c["gui_present_ms"] for c in facts["changes"]])
        facts["texture_jobs"] = state.get("texture_jobs")
        facts["still_kept"] = state.get("still_kept")
        checks["every_change_committed_and_drawn_exactly"] = all(
            c["committed_equals_new"] for c in facts["changes"])
        if vulkan:
            jobs = state.get("texture_jobs") or {}
            checks["changes_committed_by_jobs_none_fell_back"] = (
                jobs.get("route") == "job" and jobs.get("committed", 0) >= len(facts["changes"])
                and jobs.get("fell_back", 0) == 0 and jobs.get("import_failures", 0) == 0)
            checks["handover_keeps_the_previous_photo"] = all(
                c["handover_equals_previous"] and not c["handover_equals_new"] for c in facts["changes"])
            checks["handover_records_no_pass_commit_records_one"] = all(
                c["passes_at_handover"] == 0 and c["passes_through_commit"] == 1 for c in facts["changes"])
            checks["frames_drawn_while_uploading"] = all(c["frames_while_uploading"] >= 1 for c in facts["changes"])
            checks["still_kept_its_target_at_each_handover"] = int(state.get("still_kept", 0)) >= len(facts["changes"])
        else:
            checks["in_frame_change_records_one_pass"] = all(
                c["passes_through_commit"] == 1 for c in facts["changes"])
        if "rest" in rounds:
            rest_checks, rest_facts = _rest(core, host, scene, requests_before, vulkan)
            checks.update(rest_checks)
            facts["rest"] = rest_facts
        host.set_gpu_timer(False)
        if vulkan:
            services = core.job_services_state(with_log=True)
            facts["job_services"] = services
            checks["job_thread_without_python"] = all(
                s.get("thread_calls_with_python_thread_state") == 0 and s.get("thread_calls_on_gui_thread") == 0
                for s in services.get("services", []))
        checks["frame_driver_without_python"] = _driver(host).get("edges_with_python_thread_state", 1) == 0
    finally:
        scene.close(app)
        core.wait_jobs_idle(20000)
        facts["host_close"] = _close_host(app, host)
    _sheet(out / f"background_layer_change_{api}.png", tiles)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _rest(core, host, scene, requests_before: int, vulkan: bool) -> tuple[dict, dict]:
    """After the last change: the replaced output released once its frames completed (M2: the retire list asked for
    those frames itself), then nothing at rest."""
    checks: dict = {}
    scene.frames(4)                                   # FramesInFlight + 2: the replaced output's frames completed
    core.wait_jobs_idle(20000)
    after_change = (core.job_counts(), _driver(host))
    host.gpu_samples()
    rest_start = int(_driver(host).get("edges", 0))
    before = (scene.mode_state(), core.job_counts(), scene.composite_state())
    scene.frames(REST_FRAMES)
    after = (scene.mode_state(), core.job_counts(), scene.composite_state())
    samples = [s for s in host.gpu_samples() if s.kind == 2 and s.frame > rest_start]
    checks["nothing_at_rest"] = (
        after[0].get("records") == before[0].get("records")
        and after[1].get("job_wakeups") == before[1].get("job_wakeups")
        and (after[2].get("surface") or {}).get("passes_recorded") == (before[2].get("surface") or {}).get(
            "passes_recorded")
        and not samples)
    checks["nothing_retiring_at_rest"] = (after_change[0].get("job_images_retiring", 1) == 0
                                          and after_change[1].get("window_retiring") is False)
    if vulkan:
        checks["only_the_front_output_held"] = after_change[0].get("job_images") == 1
        checks["retire_list_asked_for_its_frames"] = (
            int(after_change[1].get("window_retire_frame_requests", 0)) > requests_before)
    return checks, {"after_change": {"jobs": after_change[0],
                                     "retire_frame_requests": after_change[1].get("window_retire_frame_requests")},
                    "rest_jobs": after[1], "gpu_surface_samples": len(samples)}


# --------------------------------------------------------------------------------------------------- edges (M1)


def round_edges(core, engine, app) -> dict:
    host = _host(core, (64, 64))
    scene = Scene(core, engine, host, 1.0, (60, 58), kind="layer")
    try:
        host.frames(2)
        before = int(_driver(host).get("window_edges", 0))
        host.detach()
        host.attach()                                # two drivers on the window until the old one's next edge
        host.frames(5)
        after = int(_driver(host).get("window_edges", 0))
        host.frames(3)
        later = int(_driver(host).get("window_edges", 0))
    finally:
        scene.close(app)
        closed = _close_host(app, host)
    counted = json.loads(core.module.window_edges_self_test())
    checks = {"window_edges_one_per_frame_across_a_reattach": after - before == 5,
              "window_edges_one_per_frame_after": later - after == 3,
              "two_drivers_count_a_frame_once": counted == {"edges": [1, 1, 2, 2], "total": 2}}
    return {"pass": all(checks.values()), "checks": checks,
            "facts": {"edges": [before, after, later], "self_test": counted, "host_close": closed}}


# --------------------------------------------------------------------------------------------------- cost


def round_cost(core, engine, app, api: str) -> dict:
    """QRhi's whole-frame GPU time and the frame's wall time at rest at COST_SIZE: the native layer against the
    protected retained-background path (OpenGL's Python presenter) and an empty scene."""
    vulkan = api == "vulkan"
    photo = processed(PHOTO_FOLDER / PHOTOS[0][1], "fill", COST_SIZE)[0]
    results: dict = {}
    kinds = ("empty", "layer") if vulkan else ("empty", "python", "layer")
    for kind in kinds:
        host = _host(core, COST_SIZE, 1.0, timestamps=True)
        scene = Scene(core, engine, host, 1.0, COST_SIZE, kind="layer" if kind == "layer" else "python")
        try:
            if kind != "empty":
                scene.present(photo)
                scene.settle()
            host.frames(4)
            host.set_gpu_timer(True)
            host.gpu_samples()
            walls = []
            for _ in range(TIMED_FRAMES):
                started = time.perf_counter()
                host.frames(1)
                walls.append((time.perf_counter() - started) * 1000.0)
            host.frames(4)
            samples = host.gpu_samples()
            host.set_gpu_timer(False)
            results[kind] = {"qrhi_frame_gpu": _ms_stats([s.milliseconds for s in samples if s.kind == 0]),
                             "core_surface_passes": len([s for s in samples if s.kind == 2]),
                             "frame_wall": _ms_stats(walls)}
        finally:
            scene.close(app)
            _close_host(app, host)
    checks = {"layer_records_nothing_at_rest": results["layer"]["core_surface_passes"] == 0}
    if not vulkan:
        # A fact for the lead, not a pass gate: the layer's rest frame against the protected path's, same session.
        results["layer_minus_python_gpu_median_ms"] = round(
            results["layer"]["qrhi_frame_gpu"].get("median_ms", 0.0) - results["python"]["qrhi_frame_gpu"].get(
                "median_ms", 0.0), 4)
    return {"pass": all(checks.values()), "checks": checks, "facts": results}


# --------------------------------------------------------------------------------------------------- lifetime


def round_lifetime(core, engine, app, api: str) -> dict:
    import fullscreen_pass_check as fsc

    checks: dict = {}
    facts: dict = {}
    photos = [processed(path, "fill", DISPLAY) for path in (PHOTO_FOLDER / PHOTOS[0][1], PHOTO_FOLDER / PHOTOS[1][1])]
    host = _host(core, WINDOW)
    scene = Scene(core, engine, host, 1.0, DISPLAY, kind="layer")
    try:
        scene.present(photos[0][0])
        scene.settle()
        # The lost edge: the node made again (the item at no size, then back); the layer sends its photo again.
        resent = scene.layer.resent
        scene.item.setWidth(0.0)
        scene.layer.geometry_changed()
        scene.frames(2)
        scene.item.setWidth(DISPLAY[0])
        scene.layer.geometry_changed()
        scene.frames(1)
        app.processEvents()
        scene.settle()
        app.processEvents()
        scene.settle()
        checks["lost_photo_sent_again"] = scene.layer.resent == resent + 1
        checks["drawn_again_after_the_loss"] = compare(scene.display_rows(scene.read()), photos[0][1])["equal"]
        # Teardown with the job in flight: closed in the frame after the hand-over.
        scene.present(photos[1][0])
        scene.frames(1)
        facts["at_close"] = {"jobs": core.job_counts(), "texture_jobs": scene.mode_state().get("texture_jobs")}
    finally:
        scene.close(app)
        facts["host_close"] = _close_host(app, host)
    counts, live = core.job_counts(), core.composite_live()
    facts["after"] = {"jobs": counts, "composites": live}
    checks["nothing_left"] = (fsc._nothing_left(live) and all(
        not counts.get(k) for k in ("job_threads", "jobs_queued", "jobs_running", "job_images",
                                    "job_releases_pending", "job_images_retiring")))
    if api == "vulkan":
        checks["service_stopped_with_the_device"] = "job service stopped" in json.dumps(facts["host_close"])
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the child


def child(args) -> dict:
    import host_check
    import vk_validation

    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="background-layer-check")
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
    try:
        for name in args.rounds:
            if name == "rest":
                # Measured inside the change round, after its last change (its checks are the change round's).
                record[name] = {"pass": True, "checks": {}, "measured_in": "change"}
                continue
            if vulkan:
                core.set_vulkan_phase(f"n57a {name}")
            try:
                if name == "draw":
                    record[name] = round_draw(core, engine, app, args.api, work, out)
                elif name == "change":
                    record[name] = round_change(core, engine, app, args.api, out, args.rounds)
                elif name == "edges":
                    record[name] = round_edges(core, engine, app)
                elif name == "cost":
                    record[name] = round_cost(core, engine, app, args.api)
                else:
                    record[name] = round_lifetime(core, engine, app, args.api)
            except Exception:
                record[name] = {"pass": False, "error": traceback.format_exc()}
    finally:
        _flush(app)
        record["live_hosts_at_end"] = core.live_hosts()
        record["composites_at_end"] = core.composite_live()
        record["jobs_at_end"] = core.job_counts()
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
    import fullscreen_pass_check as fsc
    import host_check

    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        if not fsc._nothing_left(record.get("composites_at_end") or {}):
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
    parser.add_argument("--label", default="n57a_background_layer")
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

    missing = [str(PHOTO_FOLDER / name) for _l, name, _f in PHOTOS if not (PHOTO_FOLDER / name).is_file()]
    missing += [str(p) for p in CHANGE_PHOTOS if not p.is_file()]
    if missing:
        print(f"N57A VERDICT FAIL: photos missing ({', '.join(missing)})")
        return 0
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n5_7a", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)  # discard any earlier child record before launch
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds]
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
    for api, record in results.items():
        for name in args.rounds:
            entry = record.get(name)
            if isinstance(entry, dict) and not entry.get("pass", False):
                bad = [k for k, v in (entry.get("checks") or {}).items() if not v]
                failed.append(f"{api} {name}: {bad or entry.get('error', 'failed')}"[:1500])
    comparison = None
    if "draw" in args.rounds and set(APIS) <= set(args.apis):
        comparison = vulkan_against_opengl(out / "work")
        if not comparison.get("pass"):
            failed.append(f"rule (b): Vulkan against OpenGL native, worst {comparison.get('worst_level')} levels")
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "require_validation": args.require_validation,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "vulkan_against_opengl": comparison, "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
        change = (results[api].get("change") or {}).get("facts") or {}
        if change.get("record_ms"):
            print(f"{api} record time per change at {CHANGE_SIZE[0]}x{CHANGE_SIZE[1]}: {change['record_ms']}; "
                  f"GUI hand-over {change.get('gui_present_ms')}")
        cost = (results[api].get("cost") or {}).get("facts") or {}
        for kind in ("empty", "python", "layer"):
            if kind in cost:
                print(f"{api} rest {kind}: QRhi frame GPU {cost[kind]['qrhi_frame_gpu']}, wall {cost[kind]['frame_wall']}")
    print(f"evidence: {out / 'summary.json'}")
    print("N57A VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
