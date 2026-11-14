"""N5.2a's proof of the seven fullscreen transitions on the display's background layer (Current_Plan.md section N2b;
``rendering/quick/render/native_background.py``), in hidden hosts only (never a window on a screen), widened by N5.2b to
the five item-quad programs that are one fragment between two pictures (``N52B_VARIANTS``: Chromatic Shear, Liquid
Lens, Melt Drip, Surface Tension, VHS; ``--topic n5_2b``). The Python reference is the product's frame at the run's dpr
(``product_capture``: the item's logical size over the display's device pixels, as the runtime gives it).

A photo change runs the configured transition natively over N5.7a's background layer: the transition's own product
pack (baked from the Python renderer's fragment, ``tools/regen_qrc.py --shaders``), its values the Python renderer's
own (``FullscreenPassRenderer.block_values``), the two photos the layer's two texture slots (the destination uploaded
by its job), its progress given every frame by the run's clock (``NativeBackgroundLayer.tick``, the window's
``afterAnimating``). Real photos (the dark Usu_Underwater_Lab_1440p.png to a bright PERSONALSET photo) are processed by
the product's worker arithmetic into the display's device pixels; the display lies in the window under the overscan
placement (its scene root one device pixel right, two down), at dpr 1 and 1.5 (``background_layer_check.Scene``).

Rounds (one child process per API; OpenGL first, its frames kept for Vulkan's comparison):
  draw   every variant of ``fullscreen_pass_check.VARIANTS`` (the seven at their production defaults and with their
         options) at the widened progress values: the layer's run with its clock held at the progress, the display's
         pixels read. Rule (a) (OpenGL): equal pixel for pixel to the Python renderer (the production GL host,
         ``TransitionCapture``) drawing the same run at the same progress; its negative control (the next progress's
         reference) differs. Each run's end: the destination drawn exactly (the slots swapped, no second upload), the
         clock disconnected, and nothing at rest (no record, no pass, no tick over rest frames).
         Vulkan also through the product's route (``BackgroundRenderItem.set_transition_run`` on the native backend):
         the same pixels as the layer driven directly.
  Then rule (b): Vulkan's frames against OpenGL's (within VULKAN_TOLERANCE levels; both native).
Facts: whether the hidden host's frames fire the clock's edge (``afterAnimating``) by themselves; the run's start and
its first frame's record; validation per phase (Vulkan).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/transition_route_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--variants burn burn_options ...] [--label n52a_transition_route]
Evidence: .artifacts/evidence/native_core/n5_2a/<date>_<label>/ (summary.json; one PNG sheet per API; the frames for the
comparison in work/: delete it once judged). Exit 0 whenever the harness ran; the verdict is the last printed line
("N52A VERDICT PASS" or "N52A VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import background_layer_check as blc  # noqa: E402  (native/core/python)
import fullscreen_pass_check as fsc  # noqa: E402

APIS = ("opengl", "vulkan")
CHILD_TIMEOUT_S = 1800
PHOTO_FOLDER = blc.PHOTO_FOLDER
#: The old photo (dark) and the new one (bright).
PHOTOS = (PHOTO_FOLDER / "Usu_Underwater_Lab_1440p.png", PHOTO_FOLDER / "Alice.(Deemo).full.1971568.jpg")
DPRS = blc.DPRS
PROGRESS = fsc.PROGRESS
DURATION_MS = fsc.DURATION_MS
VULKAN_TOLERANCE = 1
REST_FRAMES = 4
#: The variant driven through the product's route: the first of these the run drew (N5.2b's: arrays in its block).
ROUTE_VARIANTS = ("burn_options", "surface_tension_options")
_ALLOWED_ENV: set[str] = set()
#: N5.2b: the item-quad programs that are one fragment between two pictures (``NativeFragmentPass``), at their
#: production defaults and with their options (Beam is not one: its sparks are a second pass of their own geometry).
N52B_TRANSITIONS = ("chromatic_shear", "liquid_lens", "melt_drip", "surface_tension", "vhs")
N52B_VARIANTS = {
    "chromatic_shear": {},
    "chromatic_shear_options": {"request_direction": "diagonal", "spread": 1.0, "slices": 14},
    "liquid_lens": {},
    "liquid_lens_flood": {"stops": 1, "refraction": 1.0, "dispersion": 1.0},
    "liquid_lens_stops": {"stops": 8, "refraction": 0.0, "dispersion": 0.0},
    "melt_drip": {},
    "melt_drip_center_in": {"request_direction": "center_in", "detail": 2.0, "depth": 1.0, "gloss": 1.0},
    "melt_drip_top_left": {"request_direction": "top_left", "detail": 0.5, "depth": 0.0, "gloss": 0.0},
    "surface_tension": {},
    "surface_tension_options": {"pools": 20, "gloss": 1.0},
    "vhs": {},
    "vhs_options": {"request_direction": "down", "tracking": 1.0, "bleed": 1.0, "noise": 1.0},
}
TRANSITIONS = fsc.FULLSCREEN_TRANSITIONS + N52B_TRANSITIONS
VARIANTS = {**fsc.VARIANTS, **N52B_VARIANTS}
#: The variants a sheet shows (each transition's defaults and one with options).
SHEET_VARIANTS = ("burn", "particle_swirl", "ripple", "slide_push", "warp", "wipe", "crossfade",
                  *N52B_TRANSITIONS, "chromatic_shear_options", "liquid_lens_flood", "melt_drip_center_in",
                  "surface_tension_options", "vhs_options")


def variant_transition(variant: str) -> str:
    """The transition a variant of ``VARIANTS`` draws (the longest id that names it)."""
    for transition_id in sorted(TRANSITIONS, key=len, reverse=True):
        if variant == transition_id or variant.startswith(transition_id + "_"):
            return transition_id
    raise ValueError(f"no transition draws the variant {variant!r}")


def product_capture(width: int, height: int, old, new, dpr: float):
    """The production GL host (``TransitionCapture``) drawing the product's frame at ``dpr``: the item's logical size
    is the target's device pixels over ``dpr`` (its ``uItemSize``), its own pixels the target's (``item_pixels``), as
    the runtime's render frame gives them on a window of that ratio."""
    from tools.transition_contact_sheet import TransitionCapture

    class _ProductFrameCapture(TransitionCapture):
        def frame(self, run, progress: float):
            from rendering.quick.transitions.render_contract import QuickTransitionRenderFrame

            w, h = self.width, self.height
            lw, lh = w / dpr, h / dpr
            sample = run.sample(run.start_ns + round(progress * (run.end_ns - run.start_ns)))
            return QuickTransitionRenderFrame(run, sample, (0, 0, w, h), (lw, lh),
                                              (2 / lw, 0, 0, 0, 0, -2 / lh, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                              self.vao, self.textures[0], self.textures[1], device_pixel_ratio=dpr)

    return _ProductFrameCapture(width, height, old, new)


class Clock:
    """The run's clock held at one progress (a harness's control; the product's is ``time.monotonic_ns``)."""

    def __init__(self) -> None:
        self.now = 0

    def at(self, run, progress: float) -> None:
        # TransitionCapture.frame's own sampling of the run at a progress.
        self.now = run.start_ns + round(progress * (run.end_ns - run.start_ns))

    def __call__(self) -> int:
        return self.now


def production_run(variant: str, images, run_id: int):
    """The production run of ``variant`` from the old photo to the new one (``fullscreen_pass_check``'s overrides)."""
    from rendering.quick.transitions.state import TransitionRun
    from tools.transition_contact_sheet import production_transition_spec

    transition_id = variant_transition(variant)
    spec = production_transition_spec(transition_id, DURATION_MS)
    request = spec.build_request(runtime_generation=0, source_image=images[0], destination_image=images[1])
    overrides = VARIANTS[variant]
    if overrides:
        request = fsc.overridden(request, overrides)
    return TransitionRun.start(run_id=run_id, request=request, start_ns=1_000_000_000)


def references(variants, photos, dpr: float) -> dict:
    """The Python renderer's frames (the production GL host) of each variant's run at each progress, at the display's
    pixels, in the product's frame at ``dpr`` (``product_capture``)."""
    import numpy as np
    from PIL import Image

    pictures = [Image.fromarray(rows, "RGBA") for _image, rows in photos]
    width, height = blc.DISPLAY
    capture = product_capture(width, height, *pictures, dpr)
    out = {}
    try:
        for index, variant in enumerate(variants):
            run = production_run(variant, [image for image, _rows in photos], index + 1)
            for progress in PROGRESS:
                image, _ms = capture.render(run, progress)
                out[(variant, progress)] = np.asarray(image, dtype=np.uint8).copy()
    finally:
        capture.close()
    return out


def _mode_counts(scene) -> dict:
    state = scene.mode_state()
    surface = (scene.composite_state().get("surface") or {})
    return {"records": state.get("records"), "passes": surface.get("passes_recorded"),
            "uploads": state.get("texture_uploads"), "ticks": scene.layer.ticks if scene.layer else None}


def round_draw(core, engine, app, api: str, variants, work: Path, out: Path) -> dict:
    import numpy as np

    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {"variants": {}}
    frames: dict = {}
    tiles = []
    for dpr in DPRS:
        photos = [blc.processed(path, "fill", blc.DISPLAY) for path in PHOTOS]
        expected = {} if vulkan else references(variants, photos, dpr)
        host = blc._host(core, blc.WINDOW, dpr)
        scene = blc.Scene(core, engine, host, dpr, blc.DISPLAY, kind="layer")
        clock = Clock()
        scene.layer._clock_ns = clock
        try:
            for index, variant in enumerate(variants):
                run = production_run(variant, [image for image, _rows in photos], index + 1)
                scene.present(photos[0][0])
                scene.settle()
                entry: dict = {}
                clock.at(run, PROGRESS[0])
                started = time.perf_counter()
                scene.layer.transition(run)
                entry["gui_start_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
                scene.settle()                                   # the destination's upload job committed
                ticks_before = scene.layer.ticks
                scene.frames(2)
                entry["clock_edge_ticks_over_2_frames"] = scene.layer.ticks - ticks_before
                for progress in PROGRESS:
                    clock.at(run, progress)
                    scene.layer.tick()
                    scene.frames(1)
                    rows = scene.display_rows(scene.read())
                    frames[f"dpr{dpr}_{variant}_{progress:.2f}"] = rows
                    if not vulkan:
                        entry[f"{progress:.2f}"] = blc.compare(rows, expected[(variant, progress)])
                if not vulkan:
                    entry["control_next_progress_differs"] = not blc.compare(
                        frames[f"dpr{dpr}_{variant}_{PROGRESS[4]:.2f}"], expected[(variant, PROGRESS[5])])["equal"]
                # The run's end: the item ends the run, then hands over the destination (the runtime's order).
                uploads = _mode_counts(scene)["uploads"]
                scene.layer.transition(None)
                scene.present(photos[1][0])
                scene.settle()
                end = scene.display_rows(scene.read())
                entry["end_is_the_destination"] = blc.compare(end, photos[1][1])["equal"]
                entry["end_uploads_nothing"] = _mode_counts(scene)["uploads"] == uploads
                entry["clock_disconnected"] = not scene.layer.state().get("clock_connected")
                before = _mode_counts(scene)
                scene.frames(REST_FRAMES)
                after = _mode_counts(scene)
                entry["nothing_at_rest"] = before == after
                entry["rest"] = [before, after]
                facts["variants"][f"{variant}@{dpr}"] = entry
                if dpr == 1.0 and variant in SHEET_VARIANTS:
                    tiles.append([blc._tile(frames[f"dpr{dpr}_{variant}_{p:.2f}"]) for p in (0.2, 0.5, 0.8)])
            facts[f"layer_dpr_{dpr}"] = scene.layer.state()
        finally:
            scene.close(app)
            facts.setdefault("host_close", []).append(blc._close_host(app, host))
    keys = list(facts["variants"])
    if not vulkan:
        checks["rule_a_equal_to_the_python_renderer"] = all(
            facts["variants"][k][f"{p:.2f}"]["equal"] for k in keys for p in PROGRESS)
        checks["control_another_progress_differs"] = all(facts["variants"][k]["control_next_progress_differs"]
                                                         for k in keys)
        worst = max(((k, p, facts["variants"][k][f"{p:.2f}"]) for k in keys for p in PROGRESS),
                    key=lambda e: e[2].get("max_level", 0))
        facts["rule_a_worst"] = {"variant": worst[0], "progress": worst[1], **worst[2]}
    for name in ("end_is_the_destination", "end_uploads_nothing", "clock_disconnected", "nothing_at_rest"):
        checks[name] = all(facts["variants"][k][name] for k in keys)
    if vulkan:
        checks.update(_route_on_vulkan(core, engine, app, frames, facts))
    np.savez_compressed(work / f"route_{api}.npz", **frames)
    blc._sheet(out / f"transition_route_{api}.png", tiles)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _route_on_vulkan(core, engine, app, frames, facts) -> dict:
    """The product's route: ``BackgroundRenderItem.set_transition_run`` on the native backend draws the run through its
    layer, the same pixels as the layer driven directly; the run's end draws the destination."""
    from rendering.quick import bootstrap

    owner = bootstrap._owner
    saved = (owner.core, owner.backend)
    owner.core, owner.backend = core, bootstrap.QuickBackend(api="vulkan", requested="vulkan")
    checks: dict = {}
    dpr = 1.5
    route_variant = next((v for v in ROUTE_VARIANTS if f"dpr{dpr}_{v}_{PROGRESS[0]:.2f}" in frames), None)
    if route_variant is None:
        return {"route_variant_drawn": False}
    facts["route_variant"] = route_variant
    host = blc._host(core, blc.WINDOW, dpr)
    scene = blc.Scene(core, engine, host, dpr, blc.DISPLAY, kind="python")
    try:
        photos = [blc.processed(path, "fill", blc.DISPLAY) for path in PHOTOS]
        run = production_run(route_variant, [image for image, _rows in photos], 1)
        scene.present(photos[0][0])
        scene.settle()
        layer = scene.item.native_layer
        clock = Clock()
        layer._clock_ns = clock
        clock.at(run, PROGRESS[0])
        scene.item.set_transition_run(run)
        scene.settle()
        same = {}
        for progress in PROGRESS:
            clock.at(run, progress)
            layer.tick()
            scene.frames(1)
            rows = scene.display_rows(scene.read())
            same[f"{progress:.2f}"] = blc.compare(rows, frames[f"dpr{dpr}_{route_variant}_{progress:.2f}"])
        scene.item.set_transition_run(None)
        scene.item.set_presentation_image(photos[1][0])
        scene.settle()
        end = scene.display_rows(scene.read())
        checks["route_draws_the_run_as_the_layer_does"] = all(c["equal"] for c in same.values())
        checks["route_ends_on_the_destination"] = blc.compare(end, photos[1][1])["equal"]
        checks["route_ran_one_run"] = layer.state().get("runs") == 1
        facts["route"] = {"frames": same, "layer": layer.state()}
    finally:
        scene.close(app)
        facts.setdefault("host_close", []).append(blc._close_host(app, host))
        owner.core, owner.backend = saved
    return checks


def vulkan_against_opengl(work: Path) -> dict:
    import numpy as np

    vk_path, gl_path = work / "route_vulkan.npz", work / "route_opengl.npz"
    if not (vk_path.exists() and gl_path.exists()):
        return {"pass": False, "error": "both APIs' frames are needed"}
    vk, gl = np.load(vk_path), np.load(gl_path)
    per_variant: dict = {}
    worst = 0
    for key in sorted(set(vk.files) & set(gl.files)):
        result = blc.compare(vk[key], gl[key])
        variant = key.rsplit("_", 1)[0]
        entry = per_variant.setdefault(variant, {"frames": 0, "max_pixels": 0, "max_level": 0})
        entry["frames"] += 1
        entry["max_pixels"] = max(entry["max_pixels"], result.get("differing_pixels", 0))
        entry["max_level"] = max(entry["max_level"], result.get("max_level", 0))
        worst = max(worst, result.get("max_level", 255))
    return {"pass": bool(per_variant) and worst <= VULKAN_TOLERANCE, "worst_level": worst, "variants": per_variant}


# --------------------------------------------------------------------------------------------------- the child


def child(args) -> dict:
    import host_check
    import vk_validation

    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    record: dict = {"api": args.api, "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="transition-route-check")
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
        core.set_vulkan_phase("n52a draw")
    engine = QQmlEngine()
    try:
        try:
            record["draw"] = round_draw(core, engine, app, args.api, args.variants, work, out)
        except Exception:
            record["draw"] = {"pass": False, "error": traceback.format_exc()}
    finally:
        blc._flush(app)
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


def main(argv: list[str] | None = None) -> int:
    import host_check
    import vk_validation

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    parser.add_argument("--label", default="n52a_transition_route")
    parser.add_argument("--topic", default="n5_2a", help="the evidence topic (n5_2b for N5.2b's runs)")
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

    missing = [str(p) for p in PHOTOS if not p.is_file()]
    if missing:
        print(f"N52A VERDICT FAIL: photos missing ({', '.join(missing)})")
        return 0
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", args.topic, args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--variants", *args.variants]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        results[api] = record

    verdicts = {api: blc.api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    for api, record in results.items():
        entry = record.get("draw")
        if isinstance(entry, dict) and not entry.get("pass", False):
            bad = [k for k, v in (entry.get("checks") or {}).items() if not v]
            failed.append(f"{api} draw: {bad or entry.get('error', 'failed')}"[:1500])
    comparison = None
    if set(APIS) <= set(args.apis):
        comparison = vulkan_against_opengl(out / "work")
        if not comparison.get("pass"):
            failed.append(f"rule (b): Vulkan against OpenGL native, worst {comparison.get('worst_level')} levels")
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "variants": args.variants, "environment": environment,
               "require_validation": args.require_validation,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "vulkan_against_opengl": comparison, "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if comparison is not None:
        print(f"vulkan against opengl: worst {comparison.get('worst_level')} levels; "
              + json.dumps(comparison.get("variants")))
    print(f"evidence: {out / 'summary.json'}")
    print("N52A VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
