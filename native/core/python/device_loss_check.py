"""N3.6's lifetime proofs: the device-loss rebuild and the release timing (Current_Plan.md item 8b, "N3.6 Lifetime";
research ``Docs/Future_Work/Native_Core_QRhi_Research_N3.md`` sections 11 and 12; ``native/core/src/host_adapter.cpp``,
``frame_driver.cpp``, ``vulkan_context.cpp``).

The core owns the ``VkDevice`` Qt adopts and Qt's recovery re-adopts the device it was given, so after a loss the core
hands the window a new device from ``sceneGraphInvalidated`` (the render thread) before Qt's next QRhi, destroys the lost
one once Qt's QRhi on it is gone, and every core object is made again by its owner. A real loss cannot be caused here
(a TDR resets the whole GPU), so the hidden host's harness-only entry ``HiddenHost.force_device_loss`` sends a frame
down the same path a lost device takes (no environment flag). The scene is N4.a's Crossfade item at progress 0.5
(``fullscreen_pass_check``'s scene: two real photos, so both textures show), never a window on a screen.

Rounds (one child process per API):
  rebuild   LOSSES forced losses in a row on one host. Each: the frame after the loss is drawn with nothing published
            (the stream's last record), the item's textures reported lost once to their owner, which sends them again
            (the product owner's lost edge), and the next frame equals the frame before the loss exactly. Vulkan: each
            loss handed the window a new device from the invalidation on the render thread, Qt's new QRhi runs on it
            (``setGraphicsDevice`` from that slot takes effect for the rebuild: the threading the plan asked settled
            first), the lost device was destroyed (its job service stopped first), one device and one job service live
            after every loss, and the images sent again went through the new device's job service. The frame driver
            stays attached and records again.
  control   (Vulkan) the same loss with ``swap_device=False``: Qt's new QRhi adopts the old device again. With the
            rebuild round this shows that the slot's store is what moves Qt's rebuild to the new device.
  release   (each API; the release-timing box, research section 12, ``rhi_owned.h``) the GPU timer timing the probe
            pass every frame, then a detach released inside the next frame (``detach(at_frame_edge=True)``, a window
            host's release): no wait inside that frame, and on Vulkan the timer's raw query pool handed to the device's
            deferred queue; a driver attached again destroys it at a later edge, once Qt's frames waited for its last
            use; a second pool left with no later frame goes at the host's close, its device idle; the scene graph
            invalidated outside any frame (no frame follows) is met by QRhi::finish() at that edge. On Vulkan the
            round's power is pool_deferred_not_destroyed with the frames really overlapping (Qt's offscreen frame waits
            only for readbacks, so two are in flight and validation would see a pool destroyed early); the tests hold
            each reading changed. No older module was run as its control (ABI 29 has no in-frame detach). On OpenGL no
            frame ever waits for a queue, so the timer's release_waits there is a fact (opengl_release_waits), not a
            check (checkpoint audit 11 L4).
  scenes    (checkpoint audit 11 M3) the same forced losses, LOSSES in a row, across the owners the Crossfade never
            crosses one with, each frame after a loss equal to the frame before (nothing published): "program", one mode
            program with a compute kernel writing mode storage, a scene target with depth, a mesh, a bloom step and the
            composite (mix_spec; the mesh sent again by its owner, which has no lost edge; the storage's lost edge told
            once a loss); "spectrum", the native Spectrum on a frame the Python renderer drew (captured by the OpenGL
            child, spectrum_check's capture, shared with the Vulkan child); "background", the background layer with a
            backdrop pyramid and material cards over it (the layer sends its photo again through its own lost edge).
  lost      (Vulkan; checkpoint audit 11 M1) the rebuild round's LOSSES losses, each a real one Qt's own QRhi reports
            (``HiddenHost.inject_device_loss``: Qt's queue answers its next ``vkQueueSubmit`` with
            ``VK_ERROR_DEVICE_LOST``, harness only): the frame after the injected submit takes the lost path by itself
            (reason "lost", ``qrhi_lost``), the ``VK_EXT_device_fault`` report runs once for the lost device, the frame
            driver skips its finish on the lost QRhi, and the lost device's job service is told before its stop (L2:
            ``told_device_lost``, its cache save skipped); every check of the rebuild round holds too.
  retry     (Vulkan; M2) a sticky injected loss (every submit lost, as a really lost device's) with RETRY_FAILURES
            forced device creation failures: each frame until the replacement is made fails with its reason (the host
            stays open, the lost device never handed to Qt again), then the replacement is made, the lost device goes
            (its job service told), and the frame after the re-send equals the frame before the loss.
Every round with a loss also checks L1: no core wrapper (``rhi_owned.h``) is live on the old QRhi right after its scene
graph's invalidation (``core_wrappers_live_after_invalidation``), where it held some before.
On Vulkan the instance has the Khronos validation layer with synchronisation validation (``--layer-path``); every message
is attributed (``vk_validation.py``).

Not proved here: a TDR itself (the injected submit leaves the device alive; the queue is let idle first, since a lost
device runs nothing), Qt's threaded render loop's own recovery on a shown window (the window host's slots,
``WindowHost::create``; no window is shown here), and OpenGL's real loss (a failed ``makeCurrent``).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/device_loss_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds rebuild control release scenes lost retry] [--scenes program spectrum background]
  [--photos A.png B.png] [--label n36_device_loss]
Evidence: .artifacts/evidence/native_core/n3_6/<date>_<label>/ (summary.json; one PNG sheet per API: the frame before
each loss, the lost frame, the frame after). Exit 0 whenever the harness ran; the verdict is the last printed line
("N36 LOSS VERDICT PASS" or "N36 LOSS VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
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
ROUNDS = ("rebuild", "control", "release", "scenes", "lost", "retry")
VULKAN_ONLY = ("control", "lost", "retry")
RETRY_FAILURES = 2      # the retry round's forced device creation failures (frames refused before the replacement)
CHILD_TIMEOUT_S = 900
LOSSES = 2              # in a row on one host: a second loss proves the first rebuild left a host that can lose again
TIMED_FRAMES = 8        # the release round's frames with the timer writing its pool
EDGE_FRAMES = 4         # frames after the detach: more than Vulkan's two frames in flight
RELEASE_HOST = (64, 64)
PROGRESS = 0.5          # both pictures show
LOST_EDGE_FRAMES = 4    # frames waited for the lost edge's queued call to reach the owner
SHEET_TILE = (320, 180)
_ALLOWED_ENV: set[str] = set()


def _fsc():
    import fullscreen_pass_check

    return fullscreen_pass_check


def teardown_ok(steps) -> bool:
    """A destroyed device's steps: its job service stopped first (when it had one), then the device itself."""
    steps = [str(s) for s in (steps or [])]
    tail = [s for s in steps if not s.startswith("job service stopped: ")]
    stopped_first = all(not s.startswith("job service stopped: ") for s in steps[1:])
    return (stopped_first and len(tail) == 3 and tail[0].startswith("vkDeviceWaitIdle: ")
            and tail[1] == "vkDestroyDevice" and tail[2] == "resetDeviceFunctions")


def resent_through_jobs(services: dict, device, count: int) -> bool:
    """The one live job service is the rebuilt QRhi's device's (``vulkan_context.cpp`` labels it ``device <VkDevice>``)
    and it uploaded at least the ``count`` images the owner sent again."""
    live = list((services or {}).get("services") or [])
    if len(live) != 1 or not device:
        return False
    service = live[0]
    return (service.get("label") == f"device {device}"
            and float((service.get("backend") or {}).get("uploads", 0)) >= count
            and float(service.get("published", 0)) >= count)


def job_stop_record(steps) -> dict | None:
    """The job service's stop record in a destroyed device's steps (``job service stopped: <json>``), or None."""
    prefix = "job service stopped: "
    for step in steps or []:
        if isinstance(step, str) and step.startswith(prefix):
            try:
                return json.loads(step[len(prefix):])
            except ValueError:
                return {}
    return None


def judge_loss(loss: dict, state: dict, *, vulkan: bool, swap: bool, reason: str = "forced") -> dict:
    """One loss record (``state["device_losses"][-1]``) and the host's state after its rebuild, judged. GPU-free (the
    tests hold every check against a record with that one fact changed). ``reason``: "forced" (the harness's forced
    path, the device alive) or "lost" (a loss Qt's own QRhi reported: checkpoint audit 11 M1)."""
    checks = {
        "qrhi_recreated": loss.get("qrhi_recreated") is True and not loss.get("error"),
        "invalidated_on_render_thread": loss.get("invalidated_on_render_thread") is True
        and loss.get("invalidated_on_gui_thread") is False,
        "no_lost_device_left": state.get("lost_device_alive") is False,
        # Audit 11 L1: every core wrapper on the old QRhi retired by its scene graph's invalidation (there were some).
        "no_core_wrapper_outlives_the_invalidation": loss.get("core_wrappers_live_after_invalidation") == 0
        and int(loss.get("core_wrappers_live_before") or 0) > 0,
    }
    if reason == "forced":
        checks["forced"] = loss.get("reason") == "forced"
    else:
        checks["lost_reported_by_qrhi"] = loss.get("reason") == "lost" and loss.get("qrhi_lost") is True
    if not vulkan:
        checks["no_device_of_ours"] = "device_swapped" not in loss and not state.get("device_alive")
        return checks
    if reason == "lost":
        # The fault detail of the lost device, read once (a replacement retried later meets the same device again).
        fault = loss.get("fault") or {}
        checks["fault_reported"] = fault.get("queried") is True or (
            "fault" in loss and not (state.get("device") or {}).get("device_fault"))
    if swap:
        # Audit 11 L2: the lost device's job service is told whether the device was lost before its stop, and a lost
        # device's teardown saves nothing of it.
        stop = job_stop_record(loss.get("lost_device_teardown"))
        really = loss.get("qrhi_lost") is True
        told = stop is not None and stop.get("told_device_lost") is really and stop.get("device_lost") is really
        if told and really and "pipeline_cache_save" in stop:
            told = str((stop["pipeline_cache_save"] or {}).get("save", "")).startswith("skipped")
        checks["job_service_told_whether_the_device_was_lost"] = told
    old, new = loss.get("old_device"), loss.get("new_device")
    before, after = loss.get("qrhi_device_before"), loss.get("qrhi_device")
    checks["one_device_live"] = state.get("vulkan_live_devices") == 1 and state.get("device_alive") is True
    checks["qrhi_before_on_old_device"] = bool(before) and before not in ("0", None) and (not swap or before == old)
    if swap:
        checks["device_swapped"] = loss.get("device_swapped") is True and bool(old) and bool(new) and old != new
        checks["qrhi_rebuilt_on_new_device"] = after == new and loss.get("rebuilt_on_new_device") is True
        checks["host_reports_new_device"] = (state.get("device") or {}).get("vk_device") == new
        checks["lost_device_destroyed"] = teardown_ok(loss.get("lost_device_teardown"))
    else:
        checks["device_kept"] = loss.get("device_swapped") is False and "lost_device_teardown" not in loss
        checks["qrhi_rebuilt_on_same_device"] = after == before and loss.get("rebuilt_on_new_device") is False
    return checks


def _tile(pixels):
    from PIL import Image

    return Image.fromarray(pixels[..., :3].copy(), "RGB").resize(SHEET_TILE)


def _sheet(path: Path, tiles) -> None:
    from PIL import Image

    columns = 3
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (SHEET_TILE[0] * columns, SHEET_TILE[1] * max(rows, 1)))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * SHEET_TILE[0], (index // columns) * SHEET_TILE[1]))
    sheet.save(path)


def take_lost_path(core, host, mode: str, swap: bool) -> dict:
    """Sends the host down its lost path: "forced" (the harness's forced path), "lost" (M1: Qt's queue answers its next
    submit with VK_ERROR_DEVICE_LOST, and that frame is drawn), "retry" (M2: every submit lost, RETRY_FAILURES device
    creations failing; the frames until the replacement is made are refused). Returns the refused frames' reasons."""
    if mode == "forced":
        host.force_device_loss(swap_device=swap)
        return {}
    if mode == "lost":
        host.inject_device_loss()
        host.frames(1)                          # the frame whose submit meets the loss
        return {}
    core.device_create_failures(RETRY_FAILURES)
    host.inject_device_loss(sticky=True)
    host.frames(1)
    refused = []
    for _ in range(RETRY_FAILURES):             # each frame retries the replacement; each creation fails, forced
        try:
            host.frames(1)
        except RuntimeError as exc:
            refused.append(str(exc))
    return {"refused": refused}


def judge_retry(loss: dict, state: dict, refused: list, remaining: int) -> dict:
    """M2's loss record: the frames refused while the replacement could not be made, each with its reason, then the
    replacement made (the rebuild round's checks hold the rest), the fault reported only at the first attempt."""
    failures = loss.get("replacement_failures") or []
    return {
        "frames_refused_until_replaced": len(refused) == RETRY_FAILURES
        and all("no new device" in r and "forced" in r for r in refused),
        "replacement_retried_until_made": loss.get("replacement_attempts") == RETRY_FAILURES + 1
        and len(failures) == RETRY_FAILURES and loss.get("device_swapped") is True
        and loss.get("replacement_pending") is False,
        "fault_not_reported_again": "fault" in loss and loss.get("device_already_lost") is True,
        "host_not_pending": state.get("replacement_pending") is False and remaining == 0,
    }


def round_losses(core, engine, app, api: str, folder: Path, photo_paths, *, swap: bool, tiles: list,
                 mode: str = "forced") -> dict:
    fsc = _fsc()
    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {"losses": [], "mode": mode}
    images = fsc.photos(photo_paths, fsc.CARD)
    host = core.hidden_host(fsc.CARD[0] + 2 * fsc.MARGIN, fsc.CARD[1] + 2 * fsc.MARGIN)
    scene = None
    try:
        scene = fsc.Scene(core, engine, host, 1.0)
        values = fsc._values("crossfade", {}, images, fsc.CARD, {}, "crossfade")
        _core, settings, record = fsc.split_values("crossfade", values[PROGRESS])
        # The program first: a frame of the item with pictures and no program records the driver's error "the mode has
        # no program", which would then stand for every later reading of the driver's error.
        scene.program("crossfade", fsc.transition_pass("crossfade", folder / "loss"), settings)
        scene.pictures(images)
        before = scene.show(record)
        checks["drawn_before_the_loss"] = float(before[..., :3].max()) > 0.0
        checks["no_driver_error_before_the_loss"] = not (host.state().get("driver") or {}).get("error")
        calls: list[list[str]] = []

        def lost(names) -> None:
            # The product owner's lost edge (N5.7a's presenter, N5.2a's transitions): its pixels sent again.
            calls.append(sorted(names))
            scene.pictures(images, settle=False)

        scene.mode.on_textures_lost(lost)
        published = scene.stream.step
        for index in range(LOSSES):
            driver_before = host.state().get("driver") or {}
            edges_before = int(driver_before.get("edges", 0))
            met = take_lost_path(core, host, mode, swap)
            lost_frame = scene.read()               # the lost path at this frame's start; nothing is published
            for _ in range(LOST_EDGE_FRAMES):       # the lost edge reaches the owner on the GUI thread (queued)
                app.processEvents()
                if len(calls) > index:
                    break
                host.frames(1)
            scene.settle()                          # the images sent again, handed to their jobs and waited for
            app.processEvents()                     # the jobs' frame requests (queued to the item on the GUI thread)
            scene.mode.update()
            after = scene.read()                    # the commit's frame
            state = host.state()
            losses = state.get("device_losses") or []
            loss = losses[-1] if losses else {}
            prefix = f"loss_{index}_"
            checks[prefix + "recorded"] = len(losses) == index + 1
            reason = "forced" if mode == "forced" else "lost"
            for key, ok in judge_loss(loss, state, vulkan=vulkan, swap=swap, reason=reason).items():
                checks[prefix + key] = ok
            if mode != "forced":
                # The frame driver met a QRhi that reports its device lost: no finish at its invalidation.
                driver_now = state.get("driver") or {}
                checks[prefix + "frame_driver_skipped_its_finish"] = (
                    driver_now.get("no_frame_finishes") == driver_before.get("no_frame_finishes"))
            if mode == "retry":
                remaining = int(core.device_create_failures().get("remaining", -1))
                for key, ok in judge_retry(loss, state, met.get("refused") or [], remaining).items():
                    checks[prefix + key] = ok
            checks[prefix + "lost_frame_draws_nothing_stale"] = float(lost_frame[..., :3].max()) == 0.0
            checks[prefix + "owner_called_once"] = len(calls) == index + 1 and calls[-1] == ["new", "old"]
            comparison = fsc.compare(after, before)
            checks[prefix + "frame_equals_the_one_before"] = comparison["equal"]
            driver = state.get("driver") or {}
            checks[prefix + "driver_attached_and_recording"] = (
                driver.get("released") is False and not driver.get("error")
                and int(driver.get("edges", 0)) > edges_before)
            jobs_after = dict(scene.mode.state().get("texture_jobs") or {})
            services = core.job_services_state() if vulkan else {}
            if vulkan:
                checks[prefix + "one_job_service"] = core.job_counts().get("job_services") == 1
                checks[prefix + "resent_through_the_devices_jobs"] = resent_through_jobs(
                    services, loss.get("qrhi_device"), len(images))
            facts["losses"].append({"loss": loss, "comparison": comparison, "texture_jobs": jobs_after, "met": met,
                                    "injection": core.device_create_failures() if vulkan else None,
                                    "driver": {k: driver.get(k) for k in ("released", "error", "edges",
                                                                          "frames_recorded", "detach_requested")},
                                    "edges_before": edges_before,
                                    "job_services": services, "job_counts": core.job_counts(),
                                    "vulkan_live_devices": state.get("vulkan_live_devices")})
            tiles.extend([_tile(before), _tile(lost_frame), _tile(after)])
        checks["nothing_published_across_the_losses"] = scene.stream.step == published
        scene.mode.on_textures_lost(None)
        facts["calls"] = calls
        if vulkan:
            facts["job_services"] = core.job_services_state()
    finally:
        if vulkan:
            core.device_create_failures(0)
        if scene is not None:
            scene.close(app)
        host.frames(1)
        _flush(app)
        core.wait_jobs_idle(20000)
        facts["host_close"] = host.close()
        _flush(app)
    # L1 at the close too: nothing of the core's outlived the closing invalidation.
    checks["no_core_wrapper_outlives_the_close"] = (facts["host_close"] or {}).get(
        "core_wrappers_live_after_invalidation") == 0
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "facts": facts}


# ----------------------------------------------------------------------- M3: the other owners across a loss

#: Checkpoint audit 11 M3: the owners the Crossfade round never crosses a loss with. "program": one mode program with
#: mode storage and its compute kernel, a scene target with depth, a mesh, a bloom step and the composite (owners:
#: ModeStorage and compute, SceneTargets, ModeMeshes, PostStages); "spectrum": the native Spectrum (SpectrumContent);
#: "background": the background layer with a backdrop pyramid and material cards over it (BackdropPyramid, the
#: layer's own lost edge); "transition" (N5.2c audit): a Cube Turn run on the background layer, its box mesh told lost
#: once a loss (``mesh:<name>``) and sent again by the layer, with a control that has no listener and stays waiting.
SCENES =("program", "spectrum", "background", "transition")
MIX_CODE = 239                 # outside the product's mode table and every harness scene's code
SCENE_SETTLE_FRAMES = 6        # frames after the re-send: the commit, the pyramid's rebuild, Spectrum's record
SPECTRUM_RECORD_INDEX = 45     # the captured Spectrum frame (its bars up)


def mix_packs(folder: Path) -> dict:
    """The mix program's four shaders, baked by tools/regen_qrc.py's baker (compute_passes' and mesh_buffers' own)."""
    import compute_passes as cp
    import mesh_buffers as mb
    import probe_rings

    folder.mkdir(parents=True, exist_ok=True)
    return {"field.comp": probe_rings.bake(cp.FIELD_COMP, "field.comp", folder),
            "sample.frag": probe_rings.bake(cp.SAMPLE_FRAG, "sample.frag", folder),
            "box.vert": probe_rings.bake(mb.compose(mb.BOX_VERT), "box.vert", folder),
            "box.frag": probe_rings.bake(mb.compose(mb.BOX_FRAG), "box.frag", folder)}


def mix_spec(packs: dict, api: str):
    """compute_passes' field (a compute kernel writing a storage image from a stream) sampled into a scene target with
    depth, mesh_buffers' box bars (a mesh, instances from a stream) drawn over it with the depth test, a bloom chain of
    the target and the composite of both onto the card."""
    import compute_passes as cp
    import mesh_buffer_check as mbc
    import mesh_buffers as mb
    import post_stages as ps
    from rendering.native.mode import (BloomStep, CompositeStep, ComputeBinding, ComputePass, ModePass, ModeStream,
                                       ModeTarget, PassGeometry, PassSampler, StorageImage, TargetAttachment)

    target = ModeTarget("scene", (TargetAttachment("colour", "rgba8"),), depth=True)
    box = PassGeometry(packs["box.vert"], mesh="box", instances="bar_count", storage=(("Bars", "bars"),), cull="back",
                       front_face="u_front_cw")
    passes = (
        ComputePass("field", packs["field.comp"], bindings=(ComputeBinding("Knots", "knots", "stream"),
                                                            ComputeBinding("uField", "field", "image", "write")),
                    over="field"),
        ModePass("sample", packs["sample.frag"], "replace", target="scene",
                 samplers=(PassSampler("uImage", "field", filter="nearest"),)),
        ModePass("box", packs["box.frag"], "replace", target="scene", depth_test="less", depth_write=True, geometry=box),
        BloomStep("bloom", "scene.colour"),
        CompositeStep("show", "opaque_glow", "scene.colour", "bloom.glow"))
    entries = (("knot_rows", "f32", 4 * cp.KNOTS), ("knot_floats", "u32", 1), ("u_frame", "f64", 1),
               ("bar_rows", "f32", 4 * 64), ("bar_count", "u32", 1), ("bar_floats", "u32", 1))
    checks = (("knot_floats", "at_most", 4 * cp.KNOTS), ("bar_count", "at_most", 64), ("bar_floats", "at_most", 4 * 64))
    settings = {"u_field": [0.5, 0.25, 0.0, 0.0], "u_scale": [0.125, 0.125, 0.125, 0.0],
                "u_box": [11.3, 249.71, 0.6, 0.55], "u_light": [0.4, -0.6, 0.7, 0.0], "u_front_cw": mbc._front_cw(api),
                "u_bloom_strength": ps.SETTINGS["u_bloom_strength"]}
    record = {"knot_rows": cp._f32(cp.knots()), "knot_floats": 4 * cp.KNOTS, "u_frame": 0.0,
              "bar_rows": mb._f32(mb.bars()), "bar_count": mb.BARS, "bar_floats": 4 * mb.BARS}
    return cp.SceneSpec("loss_mix", passes, (target,),
                        (ModeStream("knots", "knot_rows", used="knot_floats"),
                         ModeStream("bars", "bar_rows", used="bar_floats")),
                        settings, mb.schema("loss_mix", entries, checks, code=MIX_CODE), record,
                        images=(StorageImage("field", cp.FIELD_SIZE, "rgba32f"),),
                        meshes=(("box", mb.box_mesh(), mb.box_layout(), None, None),))


def _item_rows(host, card, margin: int):
    """The item's device pixels in one frame the host renders and reads (nothing published)."""
    from dataclasses import asdict

    from composite_analysis import frame_rows

    rows = frame_rows(asdict(host.read()))
    return rows[margin:margin + card[1], margin:margin + card[0]].copy()


def cross_losses(host, app, *, read, resend, settle, vulkan: bool, tiles: list) -> tuple[dict, dict]:
    """LOSSES forced losses in a row on a drawn scene: after each, the owner's re-send (``resend``: what no lost edge
    sends by itself), ``settle`` and a frame that must equal the frame before the losses (nothing published), the loss
    judged as the rebuild round judges it."""
    fsc = _fsc()
    checks: dict = {}
    facts: dict = {"losses": []}
    before = read()
    checks["drawn_before_the_loss"] = float(before[..., :3].max()) > 0.0
    checks["no_driver_error_before_the_loss"] = not (host.state().get("driver") or {}).get("error")
    for index in range(LOSSES):
        prefix = f"loss_{index}_"
        edges_before = int((host.state().get("driver") or {}).get("edges", 0))
        host.force_device_loss(swap_device=True)
        lost_frame = read()
        for _ in range(LOST_EDGE_FRAMES):        # queued lost edges reach their owners on the GUI thread
            app.processEvents()
            host.frames(1)
        resend()
        settle()
        after = read()
        state = host.state()
        losses = state.get("device_losses") or []
        loss = losses[-1] if losses else {}
        checks[prefix + "recorded"] = len(losses) == index + 1
        for key, ok in judge_loss(loss, state, vulkan=vulkan, swap=True).items():
            checks[prefix + key] = ok
        comparison = fsc.compare(after, before)
        checks[prefix + "frame_equals_the_one_before"] = comparison["equal"]
        driver = state.get("driver") or {}
        checks[prefix + "driver_attached_and_recording"] = (
            driver.get("released") is False and not driver.get("error") and int(driver.get("edges", 0)) > edges_before)
        facts["losses"].append({"loss": loss, "comparison": comparison, "lost_frame_lit": float(lost_frame[..., :3].max()),
                                "driver": {k: driver.get(k) for k in ("released", "error", "edges", "frames_recorded")},
                                "vulkan_live_devices": state.get("vulkan_live_devices")})
        tiles.extend([_tile(before), _tile(lost_frame), _tile(after)])
    return checks, facts


def scene_program(core, engine, app, api: str, folder: Path, tiles: list) -> dict:
    import compute_pass_check as cpc
    import compute_passes as cp
    import mesh_buffer_check as mbc

    spec = mix_spec(mix_packs(folder / "mix_packs"), api)
    host = mbc._host(core, 1.0, cp.CARD)
    scene = None
    facts: dict = {}
    try:
        scene = cpc.Scene(core, engine, host, spec)
        scene.send_meshes()                        # the mesh owner's copy, uploaded at the next record
        states_lost: list = []
        textures_lost: list = []
        scene.mode.on_state_lost(lambda names: states_lost.append(sorted(names)))
        scene.mode.on_textures_lost(lambda names: textures_lost.append(sorted(names)))
        scene.draw(1)
        host.frames(2)

        def resend() -> None:
            scene.send_meshes()                    # meshes have no lost edge: their owner sends them again
            scene.mode.update()

        checks, facts = cross_losses(host, app, read=lambda: _item_rows(host, cp.CARD, mbc.MARGIN), resend=resend,
                                     settle=lambda: host.frames(SCENE_SETTLE_FRAMES), vulkan=api == "vulkan",
                                     tiles=tiles)
        state = scene.mode.state()
        facts.update(states_lost=states_lost, textures_lost=textures_lost, records_published=scene.step,
                     storage=state.get("storage"), meshes=state.get("meshes"), scene_targets=state.get("scene_targets"),
                     last_reason=state.get("last_reason"))
        # The storage's owner was told once per loss that its contents went (zeroed, dispatched fresh).
        checks["storage_lost_edge_each_loss"] = len(states_lost) == LOSSES and all(
            "field" in "".join(names) for names in states_lost)
        checks["nothing_published_across_the_losses"] = scene.step == 1
    finally:
        if scene is not None:
            mbc._close(scene, host, app)
        core.wait_jobs_idle(20000)
        facts["host_close"] = host.close()
        _flush(app)
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "facts": facts}


def spectrum_capture(out: Path) -> Path:
    """One Spectrum frame of the Python renderer (spectrum_check's capture, its first run only, the frame
    SPECTRUM_RECORD_INDEX): the record and the card, saved for both APIs' children (the OpenGL child runs it)."""
    import base64

    from core.visualizer_engine import spectrum_native_schema
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.implementations import spectrum as python_spectrum
    from tools import conventions_identity
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    clip = evidence.shipped_clip(5.5)
    found: dict = {}
    renderer = python_spectrum.QuickSpectrumRenderer
    original = renderer.render
    seen = {"index": 0}

    def capturing(self, frame):
        original(self, frame)
        if found:
            return
        logical = frame.snapshot.logical
        if int(logical.common.bar_count) <= 0:
            return
        if seen["index"] < SPECTRUM_RECORD_INDEX:
            seen["index"] += 1
            return
        presentation = frame.snapshot.presentation
        dpr = float(presentation.dpr)
        pixels = (int(frame.viewport[2]), int(frame.viewport[3]))
        card = spectrum_presentation(presentation, composite_geometry(presentation),
                                     window_size=(pixels[0] / dpr, pixels[1] / dpr), window_pixels=pixels)
        card["settings"] = python_spectrum.spectrum_settings_values(
            logical, presentation, item_size=card["item_size"], oriented_size=card["oriented_size"],
            content_rotation_quarters=card["quarters"], content_rect=card["content_rect"],
            item_from_window=card["item_from_window"], window_from_target=card["window_from_target"],
            target_px=card["target_size"])
        found.update(card=card, record=base64.b64encode(spectrum_native_schema.encode(logical)).decode("ascii"))

    renderer.render = capturing
    try:
        _suffix, settings = conventions_identity.mode_runs("spectrum", False)[0]
        engine_worker_link.reset_run_state_for_testing()
        script = parity.parity_script(clip.frames, "spectrum")
        with parity.single_sample_scene_targets():
            gate.identity_run("spectrum", script, worker=False, supervisor=None, namespace=None, settings=settings,
                              scene_mirror=parity.SceneMirror())
    finally:
        renderer.render = original
    if not found:
        raise RuntimeError("the Python Spectrum renderer drew no frame with bars to capture")
    path = out / "work" / "spectrum_frame.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, default=list), encoding="utf-8")
    return path


def scene_spectrum(core, engine, app, api: str, out: Path, tiles: list) -> dict:
    import base64

    import spectrum_check as sc

    path = out / "work" / "spectrum_frame.json"
    if api == "opengl" or not path.is_file():
        path = spectrum_capture(out)
    captured = json.loads(path.read_text(encoding="utf-8"))
    record = base64.b64decode(captured["record"])
    host = core.hidden_host(*sc.HOST_PIXELS)
    scene = stream = None
    facts: dict = {}
    try:
        card = sc._card_for_item(captured["card"])
        host.set_device_pixel_ratio(float(card["dpr"]))
        scene = sc.Scene(core, engine, host)
        stream = sc.Stream()
        scene.spectrum.bind(stream.name, expect=stream.expect)
        scene.place(card)
        stream.publish(record, 1.0)
        scene.spectrum.update()
        host.frames(2)
        checks, facts = cross_losses(host, app, read=lambda: scene.read(card).copy(), resend=lambda: None,
                                     settle=lambda: (scene.spectrum.update(), host.frames(SCENE_SETTLE_FRAMES)),
                                     vulkan=api == "vulkan", tiles=tiles)
        facts["spectrum_state"] = {k: v for k, v in scene.spectrum.composite.state().items()
                                   if k in ("refused_frames", "last_refusal", "content_failures", "shown")}
        checks["one_record_published"] = stream.consumed() >= 1
    finally:
        if stream is not None:
            stream.close()
        if scene is not None:
            scene.close(app)
        host.frames(2)
        _flush(app)
        core.wait_jobs_idle(20000)
        facts["host_close"] = host.close()
        _flush(app)
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "facts": facts}


def scene_background(core, engine, app, api: str, photo_paths, tiles: list) -> dict:
    import background_layer_check as blc
    import backdrop_pyramid_check as bpc

    photo = blc.processed(Path(photo_paths[0]), "fill", blc.DISPLAY)[0]
    host = bpc._host(core, blc.WINDOW, 1.0)
    scene = None
    facts: dict = {}
    try:
        scene = bpc.BackdropScene(core, engine, host, 1.0, blc.DISPLAY, background="layer", backdrop="native")
        scene.add_cards()                          # the material cards read the backdrop's pyramid
        scene.present(photo)
        scene.settle()
        scene.frames(2)
        checks, facts = cross_losses(host, app, read=scene.read, resend=lambda: None,   # the layer's own lost edge
                                     settle=lambda: (scene.settle(), scene.frames(SCENE_SETTLE_FRAMES)),
                                     vulkan=api == "vulkan", tiles=tiles)
        layer = scene.base.layer
        facts["layer_resent"] = getattr(layer, "resent", None)
        facts["backdrop_state"] = scene.native.state() if scene.native is not None else None
        checks["layer_sent_its_image_again_each_loss"] = int(getattr(layer, "resent", 0) or 0) >= LOSSES
    finally:
        if scene is not None:
            scene.close(app)
        facts["host_close"] = bpc._close_host(app, host)
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "facts": facts}


def _transition_scene(core, engine, photo_paths):
    """A Cube Turn run (single-sampled, its box a mesh of the run) held at half way on the background layer."""
    import background_layer_check as blc
    import transition_route_check as trc

    photos = [blc.processed(Path(path), "fill", blc.DISPLAY) for path in photo_paths[:2]]
    host = blc._host(core, blc.WINDOW, 1.0)
    scene = blc.Scene(core, engine, host, 1.0, blc.DISPLAY, kind="layer")
    clock = trc.Clock()
    scene.layer._clock_ns = clock
    run = trc.production_run("cube_turn_options", [image for image, _rows in photos], 1)
    scene.present(photos[0][0])
    scene.settle()
    clock.at(run, PROGRESS)
    scene.layer.transition(run)
    scene.settle()
    scene.frames(2)
    return host, scene


def scene_transition(core, engine, app, api: str, photo_paths, tiles: list) -> dict:
    """N5.2c (audit): a content made again mid-run tells the run's owner, once a loss, the one mesh it has nothing to
    upload from (``mesh:<name>`` on the lost edge); the background layer sends it again and the frame after the resend is
    the frame before. Control: with no ``on_meshes_lost`` listener the content stays waiting for the mesh."""
    facts: dict = {}
    host, scene = _transition_scene(core, engine, photo_paths)
    try:
        layer = scene.layer
        told: list = []

        def listener(names) -> None:
            told.append(list(names))
            layer._meshes_lost(names)              # the layer's own handler: the scene's meshes sent again

        layer.mode.on_meshes_lost(listener)
        read = lambda: scene.display_rows(scene.read())                                   # noqa: E731
        checks, facts = cross_losses(host, app, read=read, resend=lambda: None,   # the layer's own lost edges
                                     settle=lambda: (scene.settle(), scene.frames(SCENE_SETTLE_FRAMES)),
                                     vulkan=api == "vulkan", tiles=tiles)
        meshes = sorted(layer._meshes)
        facts.update(meshes_told=told, run_meshes=meshes, layer_resent=layer.resent)
        checks["one_mesh_lost_edge_each_loss"] = len(told) == LOSSES and all(sorted(n) == meshes for n in told)
        checks["the_run_has_exactly_one_mesh"] = len(meshes) == 1
        checks["run_still_drawn"] = layer.state().get("run") is not None
    finally:
        scene.close(app)
        facts["host_close"] = _close_host(app, host)
    # Control: the same loss with no listener: nothing sends the mesh, the content waits for it (named), undrawn.
    host, scene = _transition_scene(core, engine, photo_paths)
    try:
        scene.layer.mode.on_meshes_lost(None)
        before = scene.display_rows(scene.read())
        host.force_device_loss(swap_device=True)
        for _ in range(LOST_EDGE_FRAMES):
            app.processEvents()
            host.frames(1)
        scene.settle()
        after = scene.display_rows(scene.read())
        reason = str(scene.mode_state().get("last_reason") or "")
        facts["control"] = {"last_reason": reason}
        checks["control_without_a_listener_waits_for_the_mesh"] = reason.startswith("lost: mesh(es)")
        checks["control_without_a_listener_is_not_drawn_again"] = not _fsc().compare(after, before)["equal"]
    finally:
        scene.close(app)
        facts["control_host_close"] = _close_host(app, host)
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "facts": facts}


def _close_host(app, host) -> dict:
    import background_layer_check as blc

    return blc._close_host(app, host)


def round_scenes(core, engine, app, api: str, out: Path, folder: Path, photo_paths, scenes) -> dict:
    """M3: each scene of ``scenes`` across LOSSES forced losses, each frame after a loss equal to the frame before."""
    results: dict = {}
    for name in scenes:
        tiles: list = []
        try:
            if name == "program":
                results[name] = scene_program(core, engine, app, api, folder, tiles)
            elif name == "spectrum":
                results[name] = scene_spectrum(core, engine, app, api, out, tiles)
            elif name == "transition":
                results[name] = scene_transition(core, engine, app, api, photo_paths, tiles)
            else:
                results[name] = scene_background(core, engine, app, api, photo_paths, tiles)
        except Exception:
            results[name] = {"pass": False, "checks": {"ran": False}, "error": traceback.format_exc()}
        if tiles:
            _sheet(out / f"device_loss_{api}_{name}.png", tiles)
    checks = {f"{name}_{key}": ok for name, result in results.items() for key, ok in result.get("checks", {}).items()}
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "scenes": results}


def _counts_delta(after: dict, before: dict) -> dict:
    return {key: after.get(key, 0) - before.get(key, 0) for key in after if key != "raw_vulkan_pending"}


def judge_release(steps: dict, *, vulkan: bool) -> dict:
    """The release round's readings, judged (GPU-free: the tests change one reading per check). ``steps``: the
    previous driver's state after the in-frame detach (``detached``), the raw counts' deltas and pending after it
    (``deferred``), after the edges of a driver attached again (``edges``), after a host's close (``closed``), and the
    driver's state after an invalidation outside any frame (``invalidated``)."""
    detached = steps.get("detached") or {}
    last = detached.get("gpu_timer_last") or {}
    checks = {
        "released_inside_the_next_frame": detached.get("released") is True
        and str(detached.get("release_reason", "")).startswith("detached: released at the frame edge"),
        "finish_where_no_frame_follows": (steps.get("invalidated") or {}).get("no_frame_finishes") == 1,
    }
    if vulkan:
        # Audit 11 L4: only Vulkan's release could wait for its queue; OpenGL never does (round_release keeps its count
        # as the fact opengl_release_waits).
        checks["no_wait_inside_the_frame"] = last.get("release_waits") == 0
        deferred, edges, closed = (steps.get(k) or {} for k in ("deferred", "edges", "closed"))
        checks["pool_deferred_not_destroyed"] = (last.get("deferred_releases") == 1
                                                 and deferred.get("raw_vulkan_deferred") == 1
                                                 and deferred.get("pending") == 1)
        checks["pool_destroyed_at_a_later_edge"] = (edges.get("raw_vulkan_released_at_edges") == 1
                                                    and edges.get("pending") == 0
                                                    and edges.get("driver_raw_vulkan_released") == 1)
        checks["pool_left_goes_at_the_close"] = (closed.get("raw_vulkan_released_at_idle") == 1
                                                 and closed.get("pending") == 0)
    return checks


def round_release(core, app, api: str) -> dict:
    vulkan = api == "vulkan"
    facts: dict = {}
    steps: dict = {}
    host = core.hidden_host(*RELEASE_HOST)
    try:
        start = core.raw_vulkan_counts()
        host.set_probe()
        host.set_gpu_timer(True)
        host.frames(TIMED_FRAMES)
        host.detach(at_frame_edge=True)
        host.frames(1)                                   # the old driver's release, inside this frame
        steps["detached"] = host.state().get("previous_driver") or {}
        after_detach = core.raw_vulkan_counts()
        steps["deferred"] = dict(_counts_delta(after_detach, start), pending=after_detach.get("raw_vulkan_pending"))
        host.attach()                                    # a driver on the same window: its edges drain the queue
        host.frames(EDGE_FRAMES)
        after_edges = core.raw_vulkan_counts()
        steps["edges"] = dict(_counts_delta(after_edges, after_detach), pending=after_edges.get("raw_vulkan_pending"),
                              driver_raw_vulkan_released=(host.state().get("driver") or {}).get("raw_vulkan_released"))
        # A second pool, left with no later frame: it goes at the host's close (its device idle).
        host.set_probe()
        host.set_gpu_timer(True)
        host.frames(TIMED_FRAMES)
        host.detach(at_frame_edge=True)
        host.frames(1)
        before_close = core.raw_vulkan_counts()
        facts["pending_before_close"] = before_close.get("raw_vulkan_pending")
        facts["host_close"] = host.close()
        after_close = core.raw_vulkan_counts()
        steps["closed"] = dict(_counts_delta(after_close, before_close), pending=after_close.get("raw_vulkan_pending"))
        # No frame follows: the scene graph invalidated outside any frame, the driver still attached.
        host = core.hidden_host(*RELEASE_HOST)
        host.set_probe()
        host.frames(2)
        host.invalidate_scene_graph()
        steps["invalidated"] = host.state().get("driver") or {}
    finally:
        if not host.closed:
            facts["last_host_close"] = host.close()
        _flush(app)
    checks = judge_release(steps, vulkan=vulkan)
    if not vulkan:
        facts["opengl_release_waits"] = ((steps.get("detached") or {}).get("gpu_timer_last") or {}).get("release_waits")
    facts["steps"] = steps
    facts["raw_counts_at_end"] = core.raw_vulkan_counts()
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "facts": facts}


def _flush(app) -> None:
    import host_check

    host_check._flush_deletes(app)


# --------------------------------------------------------------------------------------------------- the child

def child(args) -> dict:
    import host_check
    import vk_validation

    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    photo_paths = tuple(Path(p) for p in args.photos)
    rounds = [r for r in args.rounds if r not in VULKAN_ONLY or args.api == "vulkan"]
    record: dict = {"api": args.api, "rounds": rounds, "module_loaded": False, "instance_created": False,
                    "photos": [p.name for p in photo_paths]}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="device-loss-check")
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
    tiles: list = []
    with tempfile.TemporaryDirectory(prefix="srpss_n36_") as scratch:
        folder = Path(scratch)
        if vulkan:
            # The job QRhi's pipeline cache file (N3.6) in the run's own directory, never the user's cache.
            record["pipeline_cache_directory"] = core.pipeline_cache_directory(folder / "pipeline_cache")
        try:
            for name in rounds:
                if vulkan:
                    core.set_vulkan_phase(f"n36 {name}")
                try:
                    if name == "release":
                        record[name] = round_release(core, app, args.api)
                    elif name == "scenes":
                        record[name] = round_scenes(core, engine, app, args.api, out, folder, photo_paths,
                                                    args.scenes)
                    else:
                        record[name] = round_losses(core, engine, app, args.api, folder, photo_paths,
                                                    swap=name != "control", tiles=tiles,
                                                    mode=name if name in ("lost", "retry") else "forced")
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
    if tiles:
        _sheet(out / f"device_loss_{args.api}.png", tiles)
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
    parser.add_argument("--scenes", nargs="+", default=list(SCENES), choices=SCENES,
                        help="the scenes round's scenes (checkpoint audit 11 M3)")
    parser.add_argument("--photos", nargs=2, default=[str(p) for p in _fsc().PHOTOS],
                        help="two real photos (default: fullscreen_pass_check's PERSONALSET pair)")
    parser.add_argument("--label", default="n36_device_loss")
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
    if missing:
        print(f"N36 LOSS VERDICT FAIL: the photos are missing ({', '.join(missing)})")
        return 0
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n3_6", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds, "--scenes", *args.scenes, "--photos", *args.photos]
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

    import shutil

    shutil.rmtree(out / "work", ignore_errors=True)   # the captured Spectrum frame the children shared
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
    print(f"evidence: {out / 'summary.json'}")
    print("N36 LOSS VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
