"""N3.6's proof of the device-loss rebuild (Current_Plan.md item 8b, "N3.6 Lifetime", the device-loss box; research
``Docs/Future_Work/Native_Core_QRhi_Research_N3.md`` section 11; ``native/core/src/host_adapter.cpp``).

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
On Vulkan the instance has the Khronos validation layer with synchronisation validation (``--layer-path``); every message
is attributed (``vk_validation.py``).

Not proved here: a real ``VK_ERROR_DEVICE_LOST`` (the fault report's query runs only on a really lost device), Qt's
threaded render loop's own recovery on a shown window (the window host's slots, ``WindowHost::create``), and OpenGL's
real loss (a failed ``makeCurrent``).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/device_loss_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds rebuild control] [--photos A.png B.png] [--label n36_device_loss]
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
ROUNDS = ("rebuild", "control")
CHILD_TIMEOUT_S = 900
LOSSES = 2              # in a row on one host: a second loss proves the first rebuild left a host that can lose again
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


def judge_loss(loss: dict, state: dict, *, vulkan: bool, swap: bool) -> dict:
    """One loss record (``state["device_losses"][-1]``) and the host's state after its rebuild, judged. GPU-free (the
    tests hold every check against a record with that one fact changed)."""
    checks = {
        "forced": loss.get("reason") == "forced",
        "qrhi_recreated": loss.get("qrhi_recreated") is True and not loss.get("error"),
        "invalidated_on_render_thread": loss.get("invalidated_on_render_thread") is True
        and loss.get("invalidated_on_gui_thread") is False,
        "no_lost_device_left": state.get("lost_device_alive") is False,
    }
    if not vulkan:
        checks["no_device_of_ours"] = "device_swapped" not in loss and not state.get("device_alive")
        return checks
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


def round_losses(core, engine, app, api: str, folder: Path, photo_paths, *, swap: bool, tiles: list) -> dict:
    fsc = _fsc()
    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {"losses": []}
    images = fsc.photos(photo_paths, fsc.CARD)
    host = core.hidden_host(fsc.CARD[0] + 2 * fsc.MARGIN, fsc.CARD[1] + 2 * fsc.MARGIN)
    scene = None
    try:
        scene = fsc.Scene(core, engine, host, 1.0)
        values = fsc._values("crossfade", {}, images, fsc.CARD, {}, "crossfade")
        _core, settings, record = fsc.split_values("crossfade", values[PROGRESS])
        scene.pictures(images)
        scene.program("crossfade", fsc.transition_pass("crossfade", folder / "loss"), settings)
        before = scene.show(record)
        checks["drawn_before_the_loss"] = float(before[..., :3].max()) > 0.0
        calls: list[list[str]] = []

        def lost(names) -> None:
            # The product owner's lost edge (N5.7a's presenter, N5.2a's transitions): its pixels sent again.
            calls.append(sorted(names))
            scene.pictures(images, settle=False)

        scene.mode.on_textures_lost(lost)
        published = scene.stream.step
        for index in range(LOSSES):
            edges_before = int((host.state().get("driver") or {}).get("edges", 0))
            host.force_device_loss(swap_device=swap)
            lost_frame = scene.read()               # the lost path at this frame's start; nothing is published
            for _ in range(LOST_EDGE_FRAMES):       # the lost edge reaches the owner on the GUI thread (queued)
                app.processEvents()
                if len(calls) > index:
                    break
                host.frames(1)
            scene.settle()                          # the images sent again, committed
            after = scene.read()
            state = host.state()
            losses = state.get("device_losses") or []
            loss = losses[-1] if losses else {}
            prefix = f"loss_{index}_"
            checks[prefix + "recorded"] = len(losses) == index + 1
            for key, ok in judge_loss(loss, state, vulkan=vulkan, swap=swap).items():
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
            facts["losses"].append({"loss": loss, "comparison": comparison, "texture_jobs": jobs_after,
                                    "job_services": services, "job_counts": core.job_counts(),
                                    "vulkan_live_devices": state.get("vulkan_live_devices")})
            tiles.extend([_tile(before), _tile(lost_frame), _tile(after)])
        checks["nothing_published_across_the_losses"] = scene.stream.step == published
        scene.mode.on_textures_lost(None)
        facts["calls"] = calls
        if vulkan:
            facts["job_services"] = core.job_services_state()
    finally:
        if scene is not None:
            scene.close(app)
        host.frames(1)
        _flush(app)
        core.wait_jobs_idle(20000)
        facts["host_close"] = host.close()
        _flush(app)
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
    rounds = [r for r in args.rounds if r != "control" or args.api == "vulkan"]
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
        try:
            for name in rounds:
                if vulkan:
                    core.set_vulkan_phase(f"n36 {name}")
                try:
                    record[name] = round_losses(core, engine, app, args.api, folder, photo_paths,
                                                swap=name == "rebuild", tiles=tiles)
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
    print(f"evidence: {out / 'summary.json'}")
    print("N36 LOSS VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
