"""N5.2a's proof of the seven fullscreen transitions on the display's background layer (Current_Plan.md section N2b;
``rendering/quick/render/native_background.py``), in hidden hosts only (never a window on a screen), widened by N5.2b to
the five item-quad programs that are one fragment between two pictures (``N52B_VARIANTS``: Chromatic Shear, Liquid
Lens, Melt Drip, Surface Tension, VHS; ``--topic n5_2b``) and to Beam, whose sparks follow its fragment as instanced
quads of their own vertex stage (``BEAM_VARIANTS``, N5.2b's leftover), and by N5.2c to the 3D transitions drawn as
scenes (``N52C_VARIANTS``: Blinds in both styles, Cube Turn, Depth Card Cascade, Jigsaw; N4.j's photo environment, the
scene target and the opaque composite; ``--topic n5_2c``), whose photo environment must be drawn exactly once a run
(``environment_once_per_photo``). The Python reference is the product's frame at the run's dpr
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

ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import background_layer_check as blc  # noqa: E402  (native/core/python)
import fullscreen_pass_check as fsc  # noqa: E402
from tools import pixel_tolerance as pt  # noqa: E402

APIS = ("opengl", "vulkan")
CHILD_TIMEOUT_S = 1800
PHOTO_FOLDER = blc.PHOTO_FOLDER
#: The old photo (dark) and the new one (bright).
PHOTOS = (PHOTO_FOLDER / "Usu_Underwater_Lab_1440p.png", PHOTO_FOLDER / "Alice.(Deemo).full.1971568.jpg")
DPRS = blc.DPRS
PROGRESS = fsc.PROGRESS
DURATION_MS = fsc.DURATION_MS
VULKAN_TOLERANCE = 1
#: Lead decision (14 Nov, N5.2b), judged by the shared pixel tolerance (``tools/pixel_tolerance.py``, D12 "The pixel
#: tolerance"; checkpoint audit 4 M2): a NativeFragmentPass fragment, whose pack the core compiles from translated
#: GLSL, may differ from its Python renderer (rule a) by single levels where the two compilers round a value within
#: float error of a half level (scatter: the measured worst 48 pixels a frame, Surface Tension with options at 0.80 and
#: dpr 1.5, times 1.5), at most TIE_PIXELS pixels a frame past that at 2 levels at most, isolated or on an edge, and
#: the one specular flip where pools pinch (Surface Tension with options at 0.80: one pixel a frame, a value its
#: neighbours hold). N5.2a's seven stay exact under rule (a).
TIE_PIXELS = 8
FRAGMENT_PASS_RULE_A = pt.Tolerance("native fragment pass against its Python renderer (rule a)", scatter_pixels=72,
                                    tie_pixels=TIE_PIXELS, flip_pixels=1)
#: Rule (b), Vulkan against OpenGL, both native on one pack: the two drivers round single values differently (scatter;
#: measured worst 736 pixels a frame of N5.2a's seven, Warp at dpr 1, and 1,317 of the five, VHS at dpr 1, times
#: 1.5). The seven have no pixel past one level; the five at most TIE_PIXELS a frame at 2 levels (measured 5, Liquid
#: Lens Flood at dpr 1).
SEVEN_RULE_B = pt.Tolerance("fullscreen transition, Vulkan against OpenGL (rule b)", scatter_pixels=1100)
FRAGMENT_PASS_RULE_B = pt.Tolerance("native fragment pass, Vulkan against OpenGL (rule b)", scatter_pixels=2000,
                                    tie_pixels=TIE_PIXELS)
#: Beam's rule (b), PROPOSED (agent, 21 Nov; flips need the lead's decision, ``tools/pixel_tolerance.py``): the fragment
#: pass's bound and one flip a frame. Measured over the 54 frames of BEAM_VARIANTS (twice): one pixel in one frame
#: (beam_sparks, dpr 1.5, progress 0.35), 3 levels in every channel, isolated on a spark streak's edge, where the two
#: APIs' rasterisers decide a dim spark's coverage of a pixel differently; native OpenGL holds Python's value there
#: (rule a passes), and no other pixel of any frame is past 2 levels.
BEAM_RULE_B = pt.Tolerance("Beam (fragment and sparks), Vulkan against OpenGL (rule b)", scatter_pixels=2000,
                           tie_pixels=TIE_PIXELS, flip_pixels=1)
REST_FRAMES = 4
#: The variants driven through the product's route: each of these the run drew (N5.2b's: arrays in its block; Beam's:
#: its sparks pass in the program the route builds at the run's start).
ROUTE_VARIANTS = ("burn_options", "surface_tension_options", "beam_sparks", "cube_turn", "jigsaw_options")
_ALLOWED_ENV: set[str] = set()
#: N5.2b: the item-quad programs that are one fragment between two pictures (``NativeFragmentPass``), at their
#: production defaults and with their options.
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
#: N5.2b's leftover: Beam, its fragment between the two pictures and then its sparks, the item quad drawn once a spark
#: from its own vertex stage, light added (``NativeQuadInstances``; only while Sparks is on). Its production defaults,
#: the sparks on a diagonal at full glow with the quickest cure (the longest sweep: sparks on most frames), and the
#: sparks off at the other extremes. Each keeps its frames at 0.50 and 0.65 apart (the control): the beam still
#: sweeping, or the scorch still curing (no scorch with the slowest cure would show the clean picture at both).
BEAM_VARIANTS = {
    "beam": {},
    "beam_sparks": {"request_direction": "diag_tr_bl", "sparks": True, "color": (0.25, 0.65, 1.0), "glow": 1.0,
                    "scorch": 0.0, "cure": 0.0},
    "beam_plain": {"request_direction": "up", "sparks": False, "glow": 0.0, "scorch": 1.0, "cure": 1.0},
}
#: N5.2c: the 3D transitions drawn as scenes (``NativeScenePasses``: a scene target, its passes and meshes, N4.j's photo
#: environment, the opaque composite). Each at its production defaults (the tier's 4 samples), and with options at the
#: other extremes, single-sampled (``samples`` 0: Python draws straight into Quick's framebuffer), the path rule (a)
#: proves exact; Blinds in both styles.
N52C_TRANSITIONS = ("blinds", "cube_turn", "depth_cascade", "jigsaw")
N52C_VARIANTS = {
    "cube_turn": {},
    "cube_turn_options": {"request_direction": "up", "gloss": 1.0, "samples": 0},
    # Blinds' production default is the flat style, whose request carries no slat values: 3D Slats as High draws them.
    "blinds": {"style": "slats", "slats": 16, "gloss": 0.5, "samples": 4, "request_direction": "horizontal"},
    "blinds_slats": {"style": "slats", "slats": 48, "gloss": 1.0, "request_direction": "vertical", "samples": 0},
    "blinds_slats_few": {"style": "slats", "slats": 6, "gloss": 0.0, "request_direction": "horizontal", "samples": 0},
    "blinds_flat": {"style": "flat", "feather": 0.5, "request_direction": "diagonal"},
    "depth_cascade": {},
    "depth_cascade_options": {"request_direction": "up", "cards": 14, "gloss": 1.0, "shadows": False, "seed": 7,
                              "samples": 0},
    "jigsaw": {},
    "jigsaw_options": {"pieces": 150, "order": "unordered", "seed": 9, "detail": "Performance", "samples": 0},
}
#: N5.2c's rule (a), the lead's decision (21 Nov) on r3's measurement (the ABI 36 build, 068be1f26):
#: - Single-sampled scenes (``samples`` 0): at most N52C_SCATTER_PIXELS isolated pixels a frame one level off, nothing
#:   past one level. Measured worst 1,152 a frame (Cube Turn with options), scattered over the textured faces and none in
#:   the environment's backdrop: the translated packs and Python's compiler round the faces' UVs and lighting within
#:   float error of a half level differently (N5.2b's fragment-pass scatter, on more pixels because a face fills much of
#:   the frame); the bound is the worst times 1.5. Not every one is alone (the agent's "isolated" was loose): over r3's
#:   single-sampled frames the largest group of touching one-level pixels is 19 (Cube Turn with options at 0.80, dpr
#:   1.5), so a group may hold N52C_SCATTER_GROUP (19 times 1.5) and a compact one-level patch still fails.
#: - Multisampled scenes (the tier's 4 samples) are not judged against Python (D8 point 1): the core draws its targets top
#:   row first and Python bottom row first (F1), so the driver's standard 4x pattern, (0.375, 0.125), (0.875, 0.375),
#:   (0.125, 0.625), (0.625, 0.875) and not symmetric under a vertical flip, lands mirrored on the picture: a slanted
#:   edge's pixel covers a different one of four samples (a quarter of the edge's contrast, measured up to about 2,260
#:   pixels a frame along slanted silhouettes; horizontal edges and single-sampled frames agree). The core's row order
#:   is not changed for it. Their rule (a) is their single-sampled forms' (the same geometry: ``*_options`` and
#:   ``blinds_slats*`` at ``samples`` 0); the 4x frames are judged by rule (b), Vulkan against OpenGL, both native.
N52C_SCATTER_PIXELS = 1750
N52C_SCATTER_GROUP = 28
N52C_RULE_A = pt.Tolerance("3D transition scene, single-sampled, against its Python renderer (rule a)",
                           scatter_pixels=N52C_SCATTER_PIXELS, scatter_cluster_pixels=N52C_SCATTER_GROUP)
MULTISAMPLED_RULE_A = ("a multisampled scene: rule (b) only (D8 point 1: the sample pattern lands mirrored on Python's "
                       "bottom-first rows); rule (a) is its single-sampled form's")
#: Blinds' slats are edge-on at exactly half the run: a slat's side then covers a row only by float error, and Python
#: itself draws that row differently a hair either side (measured: row 267 grey at 0.49999, 0.5 and 0.50001, the picture
#: at 0.4999, another colour at 0.5001). Their check takes 0.4999 and 0.5001 in place of 0.5 (the lead, 21 Nov), never a
#: pose exception.
SLAT_PROGRESS = (0.4999, 0.5001)
SLAT_VARIANTS = ("blinds", "blinds_slats", "blinds_slats_few")
#: Rule (b)'s flips (lead's instruction 21 Nov, as BEAM_RULE_B): measured on the ABI 36 build (068be1f26, r3) at most 3
#: pixels a frame past 2 levels, each isolated on a geometry edge, where the two APIs' rasterisers decide a pixel centre
#: within float error of the edge differently (Vulkan's clip space is OpenGL's with z halved and y flipped, so the edge
#: equations differ in their last bits): Cube Turn's slanted silhouette (up to 233 levels: the box against the
#: backdrop), a Jigsaw piece's outline, and Depth Card Cascade's card edges (options: 3 a frame at x 249-253, one card's
#: left edge, its fwidth ramp).
N52C_RULE_B = pt.Tolerance("3D transition scene, Vulkan against OpenGL (rule b)", scatter_pixels=2000,
                           tie_pixels=TIE_PIXELS, flip_pixels=3)
TRANSITIONS = fsc.FULLSCREEN_TRANSITIONS + N52B_TRANSITIONS + ("beam",) + N52C_TRANSITIONS
VARIANTS = {**fsc.VARIANTS, **N52B_VARIANTS, **BEAM_VARIANTS, **N52C_VARIANTS}
#: The variants a sheet shows (each transition's defaults and one with options).
SHEET_VARIANTS = ("burn", "particle_swirl", "ripple", "slide_push", "warp", "wipe", "crossfade",
                  *N52B_TRANSITIONS, "chromatic_shear_options", "liquid_lens_flood", "melt_drip_center_in",
                  "surface_tension_options", "vhs_options", *BEAM_VARIANTS, *N52C_VARIANTS)


def variant_progress(variant: str) -> tuple[float, ...]:
    """The progress values ``variant`` is drawn at: PROGRESS, Blinds' slats with 0.5 replaced by SLAT_PROGRESS."""
    if variant.split("@", 1)[0] not in SLAT_VARIANTS:
        return tuple(PROGRESS)
    half = PROGRESS.index(0.5)
    return tuple(PROGRESS[:half]) + SLAT_PROGRESS + tuple(PROGRESS[half + 1:])


def progress_key(progress: float) -> str:
    """A frame's progress in its key: two places (the stored keys), four where two would merge two values."""
    return f"{progress:.2f}" if round(progress, 2) == progress else f"{progress:.4f}"


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
            for progress in variant_progress(variant):
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
                # N5.2c: a scene's samples (rule a's form) and its photo environment's copies over the run.
                entry["scene"] = variant_transition(variant) in N52C_TRANSITIONS
                entry["samples"] = int(run.request.parameter_dict().get("samples", 0) or 0)
                copies_before = _environment_copies(core)
                clock.at(run, PROGRESS[0])
                started = time.perf_counter()
                scene.layer.transition(run)
                entry["gui_start_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
                scene.settle()                                   # the destination's upload job committed
                ticks_before = scene.layer.ticks
                scene.frames(2)
                entry["clock_edge_ticks_over_2_frames"] = scene.layer.ticks - ticks_before
                progresses = variant_progress(variant)
                entry["progress"] = list(progresses)
                for progress in progresses:
                    clock.at(run, progress)
                    scene.layer.tick()
                    scene.frames(1)
                    rows = scene.display_rows(scene.read())
                    frames[f"dpr{dpr}_{variant}_{progress_key(progress)}"] = rows
                    if not vulkan:
                        reference = expected[(variant, progress)]
                        rule = _rule_a(variant, entry)
                        judged = entry[progress_key(progress)] = blc.compare(rows, reference)
                        judged["over_tolerance"] = _over(rows, reference, VULKAN_TOLERANCE)
                        # N5.2c: a multisampled scene is judged by rule (b) only (rule a: its single-sampled form).
                        judged["tolerance"] = (pt.judge(rows[..., :3], reference[..., :3], rule) if rule is not None
                                               else {"pass": True, "judged": False, "reason": MULTISAMPLED_RULE_A})
                if not vulkan:
                    # Another progress's reference differs (the pair two thirds into the run's values).
                    here, there = progresses[-5], progresses[-4]
                    entry["control_next_progress_differs"] = not blc.compare(
                        frames[f"dpr{dpr}_{variant}_{progress_key(here)}"], expected[(variant, there)])["equal"]
                # N5.2c: N4.j's copy drawn once over the run (a scene reading it), never for any other run.
                reads = entry["scene"] and _reads_environment(run)
                entry["environment_copies"] = _environment_copies(core) - copies_before
                entry["environment_once_per_photo"] = entry["environment_copies"] == (1 if reads else 0)
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
                    tiles.append([blc._tile(frames[f"dpr{dpr}_{variant}_{progress_key(p)}"])
                                  for p in variant_progress(variant)[2:-2:2]][:3])
            facts[f"layer_dpr_{dpr}"] = scene.layer.state()
        finally:
            scene.close(app)
            facts.setdefault("host_close", []).append(blc._close_host(app, host))
    keys = list(facts["variants"])
    if not vulkan:
        # Exact for the seven; the shared tolerance for a NativeFragmentPass (FRAGMENT_PASS_RULE_A).
        judged = [(k, p, facts["variants"][k][progress_key(p)]) for k in keys
                  for p in facts["variants"][k]["progress"]]
        checks["rule_a_equal_to_the_python_renderer"] = all(
            e["tolerance"]["pass"] and (_rule_a(k, facts["variants"][k]) is not pt.EXACT or e["equal"])
            for k, _p, e in judged)
        facts["rule_a_tolerance"] = {
            "bounds": [FRAGMENT_PASS_RULE_A.bound(), pt.EXACT.bound(), N52C_RULE_A.bound()],
            "not_judged": sorted({k for k, _p, e in judged if e["tolerance"].get("judged") is False}),
            **pt.summarise(e["tolerance"] for _k, _p, e in judged if e["tolerance"].get("judged") is not False)}
        checks["control_another_progress_differs"] = all(facts["variants"][k]["control_next_progress_differs"]
                                                         for k in keys)
        worst = max(((k, p, e) for k, p, e in judged if e["tolerance"].get("judged") is not False),
                    key=lambda e: e[2].get("max_level", 0), default=("", 0.0, {}))
        facts["rule_a_worst"] = {"variant": worst[0], "progress": worst[1], **worst[2]}
    for name in ("end_is_the_destination", "end_uploads_nothing", "clock_disconnected", "nothing_at_rest",
                 "environment_once_per_photo"):
        checks[name] = all(facts["variants"][k][name] for k in keys)
    if vulkan:
        checks.update(_route_on_vulkan(core, engine, app, frames, facts))
    np.savez_compressed(work / f"route_{api}.npz", **frames)
    if tiles:                                            # a selection without a sheet variant draws no sheet
        blc._sheet(out / f"transition_route_{api}.png", tiles)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


#: The performance step's cost (``--cost``; Native_Parity_And_Timing_Proof.md section 3, "A transition port": C per pass
#: at 2560 x 1440 and 4K on both backends): the layer's record of the run (the environment's copy and chain once, the
#: scene's passes, the composite) timed by the core's GPU timer over COST_FRAMES frames of the effect, median and p90;
#: OpenGL also times the Python renderer (``TransitionCapture.benchmark``, 12 frames) for context. Frames run back to
#: back (no readback between them, which let the GPU idle and downclock: the first run's 4K figures were below its
#: 1440p ones); Crossfade, timed in the same run, is the control the others are read against.
COST_SIZES = ((2560, 1440), (3840, 2160))
COST_FRAMES = 240


def round_cost(core, engine, app, api: str, variants) -> dict:
    from PIL import Image

    facts: dict = {}
    checks: dict = {}
    for size in COST_SIZES:
        label = f"{size[0]}x{size[1]}"
        photos = [blc.processed(path, "fill", size) for path in PHOTOS]
        host = blc._host(core, (size[0] + 4, size[1] + 6), 1.0, timestamps=True)
        scene = blc.Scene(core, engine, host, 1.0, size, kind="layer")
        clock = Clock()
        scene.layer._clock_ns = clock
        try:
            for index, variant in enumerate(variants):
                run = production_run(variant, [image for image, _rows in photos], index + 1)
                scene.present(photos[0][0])
                scene.settle()
                clock.at(run, 0.1)
                scene.layer.transition(run)
                scene.settle()
                scene.frames(4)
                host.set_gpu_timer(True)
                host.gpu_samples()
                walls = []
                for frame in range(COST_FRAMES):
                    clock.at(run, 0.1 + 0.8 * frame / (COST_FRAMES - 1))  # the effect, never the plain ends
                    started = time.perf_counter()
                    scene.layer.tick()
                    scene.frames(1)
                    walls.append((time.perf_counter() - started) * 1000.0)
                scene.frames(4)
                samples = host.gpu_samples()
                host.set_gpu_timer(False)
                surface = [s.nanoseconds / 1e6 for s in samples if s.kind == 2]
                frame_gpu = [s.nanoseconds / 1e6 for s in samples if s.kind == 0]
                facts[f"{label}_{variant}"] = {"core_record_gpu": blc._ms_stats(surface),
                                               "qrhi_frame_gpu": blc._ms_stats(frame_gpu),
                                               "gui_tick_and_frame_wall": blc._ms_stats(walls),
                                               "samples": int(run.request.parameter_dict().get("samples", 0) or 0)}
                checks[f"{label}_{variant}_timed"] = len(surface) >= COST_FRAMES // 2
                scene.layer.transition(None)
                scene.present(photos[1][0])
                scene.settle()
        finally:
            scene.close(app)
            facts.setdefault("host_close", []).append(blc._close_host(app, host))
        if api == "opengl":
            pictures = [Image.fromarray(rows, "RGBA") for _image, rows in photos]
            capture = product_capture(size[0], size[1], *pictures, 1.0)
            try:
                for index, variant in enumerate(variants):
                    run = production_run(variant, [image for image, _rows in photos], index + 1)
                    capture.render(run, 0.5)                     # its per-run resources made before the timing
                    facts[f"{label}_{variant}"]["python_opengl"] = capture.benchmark(run)
            finally:
                capture.close()
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _route_on_vulkan(core, engine, app, frames, facts) -> dict:
    """The product's route: ``BackgroundRenderItem.set_transition_run`` on the native backend draws the run through its
    layer, the same pixels as the layer driven directly; the run's end draws the destination. Each ``ROUTE_VARIANTS``
    entry the run drew, in its own host."""
    dpr = 1.5
    drawn = [v for v in ROUTE_VARIANTS if f"dpr{dpr}_{v}_{progress_key(PROGRESS[0])}" in frames]
    if not drawn:
        return {"route_variant_drawn": False}
    facts["route_variants"] = drawn
    checks: dict = {}
    for route_variant in drawn:
        for name, ok in _route_variant_on_vulkan(core, engine, app, frames, facts, route_variant, dpr).items():
            checks[name] = checks.get(name, True) and ok
    return checks


def _route_variant_on_vulkan(core, engine, app, frames, facts, route_variant: str, dpr: float) -> dict:
    from rendering.quick import bootstrap

    owner = bootstrap._owner
    # The run is resolved before the backend is the native one: N5.2c's scenes are drawn natively before Vulkan offers
    # them (registration comes last, playbook checklist 18), so the resolver would refuse them on Vulkan.
    photos = [blc.processed(path, "fill", blc.DISPLAY) for path in PHOTOS]
    run = production_run(route_variant, [image for image, _rows in photos], 1)
    saved = (owner.core, owner.backend)
    owner.core, owner.backend = core, bootstrap.QuickBackend(api="vulkan", requested="vulkan")
    checks: dict = {}
    host = blc._host(core, blc.WINDOW, dpr)
    scene = blc.Scene(core, engine, host, dpr, blc.DISPLAY, kind="python")
    try:
        scene.present(photos[0][0])
        scene.settle()
        layer = scene.item.native_layer
        clock = Clock()
        layer._clock_ns = clock
        clock.at(run, PROGRESS[0])
        scene.item.set_transition_run(run)
        scene.settle()
        same = {}
        for progress in variant_progress(route_variant):
            clock.at(run, progress)
            layer.tick()
            scene.frames(1)
            rows = scene.display_rows(scene.read())
            same[progress_key(progress)] = blc.compare(rows,
                                                       frames[f"dpr{dpr}_{route_variant}_{progress_key(progress)}"])
        scene.item.set_transition_run(None)
        scene.item.set_presentation_image(photos[1][0])
        scene.settle()
        end = scene.display_rows(scene.read())
        checks["route_draws_the_run_as_the_layer_does"] = all(c["equal"] for c in same.values())
        checks["route_ends_on_the_destination"] = blc.compare(end, photos[1][1])["equal"]
        checks["route_ran_one_run"] = layer.state().get("runs") == 1
        facts.setdefault("route", {})[route_variant] = {"frames": same, "layer": layer.state()}
    finally:
        scene.close(app)
        facts.setdefault("host_close", []).append(blc._close_host(app, host))
        owner.core, owner.backend = saved
    return checks


def _over(a, b, level: int) -> int:
    """How many pixels of ``a`` differ from ``b`` by more than ``level`` in any channel."""
    import numpy as np

    if a.shape[:2] != b.shape[:2]:
        return a.shape[0] * a.shape[1]
    difference = np.abs(a[..., :3].astype(np.int16) - b[..., :3].astype(np.int16)).max(axis=2)
    return int(np.count_nonzero(difference > level))


#: N5.2c variants that are one authored fragment between the two pictures (Blinds' flat style: no scene, no target),
#: judged as N5.2b's fragment passes (PROPOSED, agent 21 Nov: measured 125 pixels a frame at 1 level on the ABI 36
#: build, the two compilers' rounding; the bound is the lead's).
N52C_FRAGMENT_VARIANTS = ("blinds_flat",)


def _is_fragment_pass(variant: str) -> bool:
    drawn = variant.split("@", 1)[0]
    return drawn in N52B_VARIANTS or drawn in BEAM_VARIANTS or drawn in N52C_FRAGMENT_VARIANTS


def _multisampled_scene(entry: dict) -> bool:
    """N5.2c: a scene drawn with more than one sample (rule b only: MULTISAMPLED_RULE_A)."""
    return bool(entry.get("scene")) and int(entry.get("samples", 0)) > 1


def _rule_a(variant: str, entry: dict):
    """Rule (a)'s tolerance for ``variant`` (None: not judged by rule a, a multisampled scene)."""
    if _multisampled_scene(entry):
        return None
    if _is_fragment_pass(variant):
        return FRAGMENT_PASS_RULE_A
    return N52C_RULE_A if entry.get("scene") else pt.EXACT


def _environment_copies(core) -> int:
    """N5.2c: the photo environments' copies drawn in the process so far (``composite_live``)."""
    live = core.composite_live()
    return int((live or {}).get("stage_environment_copies", 0)) if isinstance(live, dict) else 0


def _reads_environment(run) -> bool:
    from rendering.quick.render.native_background import native_transition_renderer

    renderer = native_transition_renderer(run.request.transition_id)
    return bool(renderer is not None and getattr(renderer, "native_scene", None)
                and renderer.native_scene(run, blc.DISPLAY).environment)


def vulkan_against_opengl(work: Path) -> dict:
    import numpy as np

    vk_path, gl_path = work / "route_vulkan.npz", work / "route_opengl.npz"
    if not (vk_path.exists() and gl_path.exists()):
        return {"pass": False, "error": "both APIs' frames are needed"}
    vk, gl = np.load(vk_path), np.load(gl_path)
    per_variant: dict = {}
    worst = 0
    judged: dict = {}
    for key in sorted(set(vk.files) & set(gl.files)):
        result = blc.compare(vk[key], gl[key])
        variant = key.rsplit("_", 1)[0]
        entry = per_variant.setdefault(variant, {"frames": 0, "max_pixels": 0, "max_level": 0, "max_over": 0})
        entry["frames"] += 1
        entry["max_pixels"] = max(entry["max_pixels"], result.get("differing_pixels", 0))
        entry["max_level"] = max(entry["max_level"], result.get("max_level", 0))
        entry["max_over"] = max(entry["max_over"], _over(vk[key], gl[key], VULKAN_TOLERANCE))
        worst = max(worst, result.get("max_level", 255))
        drawn = variant.split("_", 1)[1]
        tolerance = (BEAM_RULE_B if drawn in BEAM_VARIANTS else
                     N52C_RULE_B if drawn in N52C_VARIANTS else
                     FRAGMENT_PASS_RULE_B if _is_fragment_pass(drawn) else SEVEN_RULE_B)
        judged.setdefault(variant, []).append(pt.judge(vk[key][..., :3], gl[key][..., :3], tolerance))
    for variant, frames in judged.items():
        per_variant[variant]["tolerance"] = pt.summarise(frames)
    ok = bool(per_variant) and all(e["tolerance"]["pass"] for e in per_variant.values())
    return {"pass": ok, "worst_level": worst, "variants": per_variant,
            "bounds": [SEVEN_RULE_B.bound(), FRAGMENT_PASS_RULE_B.bound(), BEAM_RULE_B.bound(), N52C_RULE_B.bound()]}


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
            if args.cost:
                record["draw"] = round_cost(core, engine, app, args.api, args.variants)
            else:
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
    parser.add_argument("--cost", action="store_true",
                        help="the performance step instead of the draw: GPU time per run at COST_SIZES (round_cost)")
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
        child_json.unlink(missing_ok=True)  # discard any earlier child record before launch
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--variants", *args.variants, *(["--cost"] if args.cost else [])]
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
    if set(APIS) <= set(args.apis) and not args.cost:
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
