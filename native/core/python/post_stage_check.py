"""N3.4's proof of the native core's shared stages (Current_Plan.md item 8b, N3.4; decision D17;
``native/core/src/post_stages.h``): transparency targets with the core's resolve, bloom chains, the composite step with
the HDR tone map, the defocus step and the device gate, through ``rendering.native`` on the harness-only scenes
``native/core/python/post_stages`` (stills: Extruded Bubble's shape, the Oscilloscope's, an opaque scene with glow, and
a one-attachment owner for the sorted fallback).

The module (``release/native_module``, built on GitHub) is loaded the product's way in one child process per graphics
API (OpenGL, then Vulkan on the module's own instance and devices with synchronisation validation and its
shader-access checks), and the Python stages (``SceneTarget``, ``BloomChain``, ``DefocusLayer``) in a child of their
own (an offscreen OpenGL context). No window is ever visible.

Rounds:
  parity   (each API; and the reference) every case's targets read back (the scene's colour and emission, the
           transparency target's accumulation and coverage, the near layer's every mip level) and its composited frame.
           Rule (a): native OpenGL against the Python stages, under the shared pixel tolerance (tools/pixel_tolerance.py,
           D12): the frame's mask is derived from the reference (its translucent pixels, the pixels its glow, its
           transparent layers and its defocus composite blended into), a float texture in units of one float16 ulp
           with every texel in the mask; single-sampled cases gate, multisampled ones are repeat-relative (D8 point 1:
           the native frame repeats exactly; against Python reported) except the per-sample resolve's band pixels.
           Rule (b): native Vulkan against native OpenGL, the defocus layer's mips at every level (odd sizes
           included). Analytic: coverage stored inverted equals the textbook revealage; two draw orders of the discs
           agree within half-float rounding; light past 1 kept to the tone map; no glow without emission; the
           per-sample resolve against the first-sample control (wrong exactly in the partial-coverage bands).
  gate     (each API) the device gate's fallbacks by control: the blendable-format fact forced false (the one-attachment
           owner's sorted pack drawn, recorded once; Extruded Bubble's shape too, its emission borrowed by the sorted
           pack), the sample-shading fact forced false (4x falls back, 1x does not); a program without stages holds no
           stage object.
  rest     (each API) nothing recorded at rest (no record, bloom, defocus, generateMips or resolve); a setting records.
  steady   (each API) a minute of records: no stage object created; the process's private memory.
  retire   (each API) a destroy, a program without the stages, a mode switch, a destroy mid-resize and the scene
           graph's invalidation release to zero; the skipped-release control counted, then released.
  barriers (Vulkan) consecutive records with no readback between them, clean but for Qt's recorded defects; each
           negative control in its own phase, seen to fail: the depth prime skipped, the bloom upsample's prime
           skipped, the bloom chain as levels of one texture, a device without independentBlend with the gate
           bypassed. Then that device with the gate: the one-attachment owner falls back (recorded once), Extruded
           Bubble's shape is refused by N3.1's per-attachment check (the mode-level fallback).
  cost     (each API) the EB scene at 2560x1440 and 3840x2160, one and four samples, each stage's GPU time (the record
           with it less without it), median and p90 of 240 records; on Vulkan under the validation layer.
Run alone:
  python_cost (the reference child, OpenGL) the Python stages on the same loads.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/post_stage_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds parity gate rest steady retire barriers cost python_cost] [--label n34_post_stages]
Evidence: .artifacts/evidence/native_core/n3_4/<date>_<label>/ (summary.json; sheet_<case>.png). Exit 0 whenever the
harness ran; the verdict is the last printed line ("N34 VERDICT PASS" or "N34 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402
import scene_target_check as stc  # noqa: E402
from tools import pixel_tolerance as pt  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("parity", "gate", "rest", "steady", "retire", "barriers", "cost")
PYTHON_ROUNDS = ("python_cost",)
CHILD_TIMEOUT_S = 2400
MARGIN = stc.MARGIN
CARD = (640, 384)                  # bucket-aligned: the defocus layer equals Python's exact-size layer (choice H)
UNALIGNED = (600, 350)             # within one bucket: the near layer's allocation is larger than Python's
BAND = 0.05                        # the first disc's partial-coverage bands (vUv: about 19 rows each)
HALF_ULP = stc.HALF_ULP
# Coverage stored inverted (c' = a + c(1 - a), clear 0) against Python's revealage (r' = r(1 - a), clear 1): each
# blend rounds into float16 once, so after three layers the two differ by at most a few ulps of the larger value.
COVERAGE_ULPS = 3
# The frame's rules. Rule (a): exact outside the reference's mask (opaque content, bare background); one level on the
# mask. Rule (b): the same. The measured worsts and their reasons are recorded in the summary (D12).
FRAME_RULE_A = pt.Tolerance("post stages frame, rule (a)", masked_level=1)
FRAME_RULE_B = pt.Tolerance("post stages frame, rule (b)", masked_level=1)
# A float texture's unit is one float16 ulp (``float_units``; ``DEFOCUS_ULPS`` on defocus-blended texels). Rule (a)
# admits 2 texels a texture at 2 units, isolated or on an edge (measured: 1 texel of the EB scene's colour beside the
# defocus mask, the inverted coverage's ulp carried through the gather).
TEXTURE_RULE_A = pt.Tolerance("post stages texture, rule (a)", masked_level=1, tie_pixels=2)
# Rule (b) admits 36 texels a texture at up to 3 units (the edge class's level), isolated or on an edge: the two
# backends' fp32 sin() differ in the last bits, and on the Oscilloscope trace's steep edge that is up to 3 float16 ulps
# of its emission (measured: 17 texels at 2 and 7 at 3 of 827 differing, with the trace's vUv quantised to the pixel
# grid, which took the interpolation's share out: 5 ulps before). Measured worst 24, times 1.5.
TEXTURE_RULE_B = pt.Tolerance("post stages texture, rule (b)", masked_level=1, tie_pixels=36, tie_level=3,
                              edge_class=True)
# The defocus gather's unit on the texels it blends (in float16 ulps): its 96 bilinear taps land at mirrored subtexel
# positions in the core (rows top first) and the hardware's 8-bit subtexel weights round each apart; measured worst
# 4.84 ulps (OpenGL against Python, the highlight and the disc's edge).
DEFOCUS_ULPS = 5
FLOAT_FLOOR = 2.0 ** -8
REST_FRAMES = 4
STEADY_SECONDS = 60.0
BARRIER_RECORDS = 30
CONTROL_RECORDS = 12
COST_HOSTS = ((2560, 1440), (3840, 2160))
COST_FRAMES = 240
PYTHON_COST_FRAMES = 120
_ALLOWED_ENV: set[str] = set()

# The validation phases whose finding is expected (each control's own): how each is recognised (an id or a text in the
# message; none: any error), whether it is required (False: reported only, the layer cannot show it, see the bloom
# prime's note in D17's As built), and the text that places it (the transparency run's own depth load: EB's
# transparency target holds accumulation, coverage and the borrowed emission, so its depth is attachment 3).
CONTROL_PHASES = {
    "n34 control depth prime": {"expect": ("SYNC-HAZARD-READ-AFTER-WRITE",), "required": True,
                                "placed": "depth aspect of attachment 3"},
    "n34 control bloom prime": {"expect": ("SYNC-HAZARD-READ-AFTER-WRITE",), "required": False, "placed": None},
    "n34 control bloom same texture": {"expect": (), "required": True, "placed": None},
    # The defocus run reads the layer in its vertex (sprites) and fragment (gather) stages; without the core's chain
    # QRhi's next barrier on the layer (generateMips) leaves the fragment reads unordered (targets.h chainShaderReads).
    "n34 control read chain": {"expect": ("SYNC-HAZARD-WRITE-AFTER-READ",), "required": True, "placed": "near."},
    "n34 control no independent blend": {"expect": ("independentBlend", "00605"), "required": True, "placed": None},
}


def _ps():
    import post_stages

    return post_stages


# --------------------------------------------------------------------------------------------------- the cases

@dataclass(frozen=True)
class Case:
    name: str
    scene: str
    card: tuple[int, int] = CARD
    samples: int = 1
    order: tuple[int, ...] = (1, 2, 3)
    band: float = 0.0
    variant: str = "full"
    controls: tuple[str, ...] = ()
    changes: dict = field(default_factory=dict)
    reference: str | None = "same"      # "same": the Python stages; "sorted": the sorted packs; None: native only
    against: str | None = None          # a native-only case's comparison case


DARK = {"u_back_emission": 0.0, "u_l1_light": [0.0, 0.0, 0.0, 3.0], "u_l2_light": [0.0, 0.0, 0.0, 5.0]}

CASES = (
    Case("eb_1x", "eb"),
    Case("eb_4x", "eb", samples=4),
    Case("eb_reversed_1x", "eb", order=(3, 2, 1), reference=None, against="eb_1x"),
    Case("eb_band_4x", "eb", samples=4, band=BAND),
    Case("eb_band_4x_first_sample", "eb", samples=4, band=BAND, controls=("transparency_first_sample",),
         reference=None, against="eb_band_4x"),
    Case("eb_unaligned_1x", "eb", card=UNALIGNED),
    Case("eb_dark_1x", "eb", changes=DARK, reference=None),
    Case("osc_1x", "osc", changes={"u_hdr_exposure": 0.0}),
    Case("tiles_1x", "tiles"),
    Case("tiles_4x", "tiles", samples=4),
    Case("solo_1x", "solo"),
    Case("solo_fallback_1x", "solo", controls=("blend_formats_missing",), reference="sorted"),
)
CASE = {c.name: c for c in CASES}
#: A setting each scene changes to force a record (and back).
BUMP = {"eb": "u_back_gain", "osc": "u_bloom_strength", "tiles": "u_tile_glow", "solo": "u_solo_edge"}


def build(case: Case, packs: dict):
    ps = _ps()
    options = {}
    if case.scene == "eb":
        options = {"samples": case.samples, "variant": case.variant, "order": case.order}
    elif case.scene in ("tiles", "solo"):
        options = {"samples": case.samples}
    passes, targets = ps.program(case.scene, packs, **options)
    changes = dict(case.changes)
    if case.band:
        changes["u_l1_band"] = float(case.band)
    return passes, targets, ps.values_for(passes, None, **changes)


# --------------------------------------------------------------------------------------------------- native scenes

def _host(core, card=CARD):
    return core.hidden_host(card[0] + 2 * MARGIN, card[1] + 2 * MARGIN)


def _frame(host, card):
    from dataclasses import asdict

    from composite_analysis import frame_rows

    rows = frame_rows(asdict(host.read()))
    return rows[MARGIN:MARGIN + card[1], MARGIN:MARGIN + card[0]].copy()


def _entry(array, card, fmt="rgba8"):
    return {"array": array, "content": tuple(card), "size": (array.shape[1], array.shape[0]), "samples": 1,
            "format": fmt}


def _controls(core, names, on: bool) -> None:
    for name in names:
        if not core.module.stage_control(name, bool(on)):
            raise RuntimeError(f"unknown stage control {name!r}")


def _close(scene, host, app) -> None:
    scene.close(app)
    host.frames(2)
    host_check._flush_deletes(app)


def _live(core) -> dict:
    return core.composite_live()


STAGE_KEYS = ("stage_bloom_chains", "stage_defocus_steps", "stage_textures", "stage_bytes", "stage_pipelines")
RECORD_KEYS = ("stage_bloom_records", "stage_defocus_records", "stage_transparency_resolves", "stage_generated_mips")


def run_case(core, engine, app, host, packs: dict, case: Case, *, repeat: bool = False) -> dict:
    """One case's targets and frame (and, ``repeat``, the same record drawn again after a change and back)."""
    _controls(core, case.controls, True)
    try:
        passes, targets, values = build(case, packs)
        scene = stc.Scene(core, engine, host, case.card, 1.0, packs, passes=passes, targets=targets, settings=values)
        try:
            textures = scene.targets(app)
            textures["frame"] = _entry(_frame(host, case.card), case.card)
            state = scene.mode.state()
            again = None
            if repeat:
                bump = BUMP[case.scene]
                scene.mode.settings(dict(values, **{bump: values[bump] * 0.9}))
                scene.targets(app)
                scene.mode.settings(values)
                again = scene.targets(app)
                again["frame"] = _entry(_frame(host, case.card), case.card)
        finally:
            _close(scene, host, app)
    finally:
        _controls(core, case.controls, False)
    return {"textures": textures, "state": state, "again": again}


def _state_facts(state: dict) -> dict:
    targets = state.get("scene_targets") or {}
    return {"error": state.get("content_failure") if state.get("content_failing") else "",
            "refusal": state.get("last_refusal") or "", "fallbacks": targets.get("transparency_fallbacks"),
            "records": state.get("records")}


# --------------------------------------------------------------------------------------------------- comparisons

def _rgb(entry):
    return entry["array"][..., :3]


def judge_texture(candidate: dict, reference: dict, tolerance, unit=None) -> dict:
    """``stc.judged`` (RGBA8 in levels with the reference's translucent texels as the mask; a float texture in float16
    ulps, every texel in the mask), with the largest float difference beside it. ``unit`` (a float texture only): each
    texel's unit in ulps (``DEFOCUS_ULPS`` on the reference's defocus-blended texels, 1 elsewhere)."""
    import numpy as np

    if candidate["format"] == "rgba8" or candidate["array"].shape != reference["array"].shape:
        return stc.judged(candidate, reference, tolerance)
    units = float_units(candidate["array"], reference["array"])
    delta = np.ceil(units / (1.0 if unit is None else unit))
    fy = reference["array"].astype(np.float64)
    edges = pt.content_edges(fy * 255.0, tolerance.edge_contrast)
    result = pt.judge_delta(delta.astype(np.int64), tolerance, mask=np.ones(delta.shape, bool), edges=edges)
    diff = np.abs(candidate["array"].astype(np.float64) - fy)
    result["max_abs"] = float(diff.max()) if diff.size else 0.0
    result["max_ulps"] = round(float(units.max()), 3) if units.size else 0.0
    return result


def float_units(a, b):
    """Per texel (largest channel), the difference in float16 ulps of the larger value, the value floored at
    ``FLOAT_FLOOR``: light under 1/256 of a unit is below one 8-bit output step at any gain up to 1, and there the
    harness fragments' smoothstep tails cancel catastrophically in fp32, differently per compiler and backend."""
    import numpy as np

    fx, fy = np.asarray(a, np.float64), np.asarray(b, np.float64)
    units = np.abs(fx - fy) / (np.maximum(np.maximum(np.abs(fx), np.abs(fy)), FLOAT_FLOOR) * HALF_ULP)
    return units.max(axis=2) if units.ndim == 3 else units


def _allocation_mask(content_mask, entry: dict):
    """A content-sized mask placed where the content lies in ``entry``'s allocation (image rows [H-h, H), columns
    [0, w): D14 point 2)."""
    import numpy as np

    rows, cols = entry["array"].shape[:2]
    full = np.zeros((rows, cols), bool)
    h, w = content_mask.shape
    full[rows - h:, :w] = content_mask
    return full


def judge_frame(candidate: dict, reference: dict, mask, tolerance) -> dict:
    return pt.judge(_rgb(candidate), _rgb(reference), tolerance, mask=mask)


def _grid(card):
    import numpy as np

    width, height = card
    vx = (np.arange(width) + 0.5) / width
    vy = 1.0 - (np.arange(height) + 0.5) / height                 # vUv.y per content row (top first)
    return np.meshgrid(vx, vy)


def _layer_geometry(card, values: dict, n: int):
    """Disc ``n``'s pixels (inside), its visibility against the backdrop's depth, and a guard band round its edges."""
    import numpy as np

    ps = _ps()
    vx, vy = _grid(card)
    cx, cy, radius, depth = values[f"u_l{n}_disc"]
    distance = np.hypot((vx - cx) * ps.ASPECT, vy - cy)
    inside = distance <= radius
    backdrop = np.where(vx <= values["u_back_edge"],
                        values["u_back_near"] + (values["u_back_far"] - values["u_back_near"]) * vx, 1.0)
    visible = inside & (depth < backdrop)
    pixel = 1.0 / card[1]
    guard = (np.abs(distance - radius) > 1.5 * pixel) & (np.abs(backdrop - depth) > 2e-3) & (
        np.abs(vx - values["u_back_edge"]) > 1.5 / card[0])
    return inside, visible, guard


def coverage_analytic(native: dict, reference: dict | None, values: dict, card) -> dict:
    """D17 choice B: the stored coverage (c' = a + c(1 - a) from 0) is the textbook revealage's complement
    (1 - prod(1 - a)) over the visible discs; against Python's own revealage (clear 1, ZERO, ONE_MINUS_SRC_COLOR) when
    the reference is there. Within ``COVERAGE_ULPS`` float16 ulps of the larger value."""
    import numpy as np

    keep = np.ones(card[::-1], bool)
    reveal = np.ones(card[::-1])
    for n in (1, 2, 3):
        _inside, visible, guard = _layer_geometry(card, values, n)
        keep &= guard
        reveal = np.where(visible, reveal * (1.0 - values[f"u_l{n}_colour"][3]), reveal)
    expected = 1.0 - reveal
    got = stc._content(native["glass.coverage"]).astype(np.float64)
    bound = np.maximum(np.abs(got), np.abs(expected)) * (COVERAGE_ULPS * HALF_ULP) + 1e-6
    error = np.abs(got - expected)
    facts = {"max_error": float(error[keep].max()), "pixels_judged": int(keep.sum()),
             "pixels_covered": int((expected > 0)[keep].sum()), "past_bound": int((error > bound)[keep].sum()),
             "layers_max": float(expected.max())}
    ok = facts["past_bound"] == 0 and facts["pixels_covered"] > 0
    if reference is not None and "glass.coverage_textbook" in reference:
        textbook = stc._content(reference["glass.coverage_textbook"]).astype(np.float64)
        vs = np.abs(got - textbook)
        tb = np.maximum(np.abs(got), np.abs(textbook)) * (COVERAGE_ULPS * HALF_ULP) + 1e-6
        facts["python_revealage"] = {"max_error": float(vs.max()), "past_bound": int((vs > tb).sum()),
                                     "max_ulps": float((vs / (np.maximum(np.abs(got), np.abs(textbook)) * HALF_ULP
                                                              + 1e-7)).max())}
        ok = ok and facts["python_revealage"]["past_bound"] == 0
    return {"pass": bool(ok), "bound_ulps": COVERAGE_ULPS, **facts}


def band_masks(card, values: dict, band: float):
    """The first disc's two partial-coverage bands where it is visible (the per-sample proof's pixels), and the rows
    and pixels judged (one row from each band edge and the disc's guard band left out)."""
    import numpy as np

    _inside, visible, guard = _layer_geometry(card, values, 1)
    vx, vy = _grid(card)
    below = values["u_l1_disc"][1] - vy
    first = visible & (below > 0.0) & (below <= band)
    second = visible & (below > band) & (below <= 2.0 * band)
    pixel = 1.0 / card[1]
    for edge in (0.0, band, 2.0 * band):
        guard &= np.abs(below - edge) > 1.5 * pixel
    return first, second, guard


def per_sample_analytic(native: dict, control: dict, reference: dict | None, values: dict, card) -> dict:
    """D17 choice C: the per-sample resolve against Python's at the bands' pixels (float16 ulps), and the control
    (every sample reads sample 0) wrong exactly in the bands: differing from the per-sample frame in them and nowhere
    else."""
    import numpy as np

    first, second, guard = band_masks(card, values, BAND)
    bands = (first | second) & guard
    colour = stc._content(native["scene.colour"]).astype(np.float64)[..., :3]
    wrong = np.abs(stc._content(control["scene.colour"]).astype(np.float64)[..., :3] - colour).max(axis=2) > 1e-3
    facts = {"band_pixels": int(bands.sum()), "control_wrong_in_bands": int((wrong & bands).sum()),
             "control_wrong_elsewhere": int((wrong & ~(first | second) & guard).sum())}
    ok = facts["band_pixels"] > 0 and facts["control_wrong_in_bands"] == facts["band_pixels"] and \
        facts["control_wrong_elsewhere"] == 0
    if reference is not None:
        ref = stc._content(reference["scene.colour"]).astype(np.float64)[..., :3]
        units = np.abs(colour - ref) / (np.maximum(np.abs(colour), np.abs(ref)) * HALF_ULP + 1e-7)
        facts["against_python_in_bands_max_ulps"] = float(units.max(axis=2)[bands].max())
        facts["against_python_in_bands_past_2_ulps"] = int((units.max(axis=2)[bands] > 2.0).sum())
        ok = ok and facts["against_python_in_bands_past_2_ulps"] == 0
    return {"pass": bool(ok), **facts}


def order_analytic(forward: dict, reversed_: dict) -> dict:
    """Two draw orders of the discs: the accumulation and coverage within half-float rounding (2 ulps), the frame
    within one level."""
    import numpy as np

    facts = {}
    ok = True
    for key in ("glass.accum", "glass.coverage", "scene.colour"):
        a, b = forward[key]["array"].astype(np.float64), reversed_[key]["array"].astype(np.float64)
        units = np.abs(a - b) / (np.maximum(np.abs(a), np.abs(b)) * HALF_ULP + 1e-7)
        facts[key] = {"max_ulps": float(units.max()), "differing": int((np.abs(a - b) > 0).sum())}
        ok = ok and facts[key]["max_ulps"] <= 2.0
    diff = pt.levels(_rgb(forward["frame"]), _rgb(reversed_["frame"]))
    facts["frame"] = {"max_level": int(diff.max()), "differing": int((diff > 0).sum())}
    ok = ok and facts["frame"]["max_level"] <= 1
    return {"pass": bool(ok), **facts}


def hdr_and_glow_analytic(eb: dict, dark: dict) -> dict:
    """Light past 1 kept until the tone map (the scene's colour); no glow without emission (with every emission at
    0 the emission holds 0 and the frame is 0 wherever the scene is empty: no glow, no dither)."""
    import numpy as np

    colour = stc._content(eb["scene.colour"]).astype(np.float64)
    emission = stc._content(dark["scene.emission"]).astype(np.float64)
    empty = stc._content(dark["scene.colour"]).astype(np.float64)[..., 3] == 0.0
    frame = dark["frame"]["array"][..., :3]
    facts = {"scene_colour_max": float(colour[..., :3].max()), "dark_emission_max": float(np.abs(emission).max()),
             "dark_empty_pixels": int(empty.sum()), "dark_empty_lit": int((frame.max(axis=2) > 0)[empty].sum())}
    ok = (facts["scene_colour_max"] > 1.5 and facts["dark_emission_max"] == 0.0 and facts["dark_empty_pixels"] > 0
          and facts["dark_empty_lit"] == 0)
    return {"pass": bool(ok), **facts}


MASKS = ("frame", "frame_mask", "defocus_mask", "glass.coverage_textbook")


def _textures_judged(a: dict, b: dict, tolerance, *, skip=MASKS, defocus=None, exclude=None) -> dict:
    """Each texture both sets hold, judged; ``defocus`` (content-sized): the defocus-blended texels, judged in units of
    ``DEFOCUS_ULPS`` on the scene's colour; ``exclude`` (content-sized): texels left out of the verdict (set equal),
    reported apart."""
    import numpy as np

    out = {}
    for key, entry in a.items():
        if key in skip or key not in b or key.endswith(("capture_colour", "capture_depth")):
            continue
        reference = b[key]
        unit = None
        if defocus is not None and key == "scene.colour" and entry["format"] != "rgba8":
            unit = np.where(_allocation_mask(defocus, entry), float(DEFOCUS_ULPS), 1.0)
        if exclude is not None and key.startswith("scene.") and entry["array"].shape == reference["array"].shape:
            left = _allocation_mask(exclude, entry)
            entry = dict(entry, array=np.where(left[..., None] if entry["array"].ndim == 3 else left,
                                               reference["array"], entry["array"]))
        out[key] = judge_texture(entry, reference, tolerance, unit)
    return out


def _odd_source(frames: dict, key: str) -> bool:
    """Whether the mip level ``key`` ("<target>.<attachment>@<level>") descends from a level with an odd side (it, or
    a level it was made from, halved an odd-sized one)."""
    base_key = key.split("@")[0]
    level = int(key.split("@")[1]) if "@" in key else 0
    if level == 0 or base_key not in frames:
        return False
    width, height = frames[base_key]["size"]
    return any(side > 1 and side % 2 == 1 for k in range(level)
               for side in (max(1, width >> k), max(1, height >> k)))


def cross_compare(out: Path) -> dict:
    """Rule (a) (native OpenGL against the Python stages), rule (b) (Vulkan against OpenGL) and the analytic checks
    on each API's frames."""
    gl, vk, ref = stc._load(out, "post_opengl"), stc._load(out, "post_vulkan"), stc._load(out, "post_reference")
    result: dict = {"rule_a": {}, "rule_b": {}, "analytic": {}}
    # Rule (a).
    if gl and ref:
        ok = True
        for case in CASES:
            if case.reference is None or case.name not in gl or case.name not in ref:
                continue
            native, reference = gl[case.name], ref[case.name]
            mask = reference["frame_mask"]["array"].astype(bool)
            defocus = reference["defocus_mask"]["array"].astype(bool) if "defocus_mask" in reference else None
            # Choice H: at the unaligned card Python's layer is the card's exact size and the core's the bucket's, so
            # the defocus-blended pixels are reported apart and left out of the verdict.
            exclude = defocus if case.name == "eb_unaligned_1x" else None
            native_frame = native["frame"]
            if exclude is not None:
                import numpy as np

                native_frame = dict(native_frame, array=np.where(exclude[..., None], reference["frame"]["array"],
                                                                 native_frame["array"]))
            frame = judge_frame(native_frame, reference["frame"], mask, FRAME_RULE_A)
            textures = _textures_judged(native, reference, TEXTURE_RULE_A, skip=MASKS + ("glass.coverage",),
                                        defocus=defocus, exclude=exclude)
            judged = {"frame": frame, **textures}
            if exclude is not None:
                judged["defocus_reported"] = {"frame": judge_frame(native["frame"], reference["frame"], mask,
                                                                   FRAME_RULE_A),
                                              **_textures_judged(native, reference, TEXTURE_RULE_A,
                                                                 skip=MASKS + ("glass.coverage",), defocus=defocus)}
                judged["defocus_reported"]["pass"] = True
            # Gated: single-sampled cases (D8 point 1: multisampled output is repeat-relative, reported here).
            gated = case.samples == 1
            case_ok = all(v.get("pass") for v in judged.values()) if gated else True
            result["rule_a"][case.name] = {"pass": case_ok, "gated": gated, "judged": judged}
            ok = ok and case_ok
        result["rule_a"]["pass"] = ok and any(isinstance(v, dict) and v.get("judged") for v in result["rule_a"].values())
        result["rule_a"]["bounds"] = {"frame": FRAME_RULE_A.bound(), "texture": TEXTURE_RULE_A.bound()}
    else:
        result["rule_a"] = {"pass": False, "error": "a frame set is missing"}
    # Reported, never gated: the native frames against Python's bloom source as the product samples it today (NEAREST,
    # REPEAT; the side defect the designed reference corrects, _bloom_source_as_designed).
    product = stc._load(out, "post_reference_product")
    if gl and product:
        result["rule_a_product_bloom_source"] = {
            case: {k: v for k, v in judge_frame(gl[case]["frame"], product[case]["frame"],
                                                product[case]["frame_mask"]["array"].astype(bool),
                                                FRAME_RULE_A).items() if k != "reasons"}
            for case in product if case in gl}
    # Rule (b).
    if gl and vk:
        ok = True
        for case in CASES:
            if case.name not in gl or case.name not in vk:
                continue
            a, b = vk[case.name], gl[case.name]
            reference = ref.get(case.name if case.reference == "same" else (case.against or ""), {})
            mask = reference.get("frame_mask", {}).get("array")
            if mask is None:
                mask = pt.translucent_by_alpha(b["frame"]["array"], additive=True) | (_rgb(b["frame"]).max(axis=2) > 0)
            defocus = reference["defocus_mask"]["array"].astype(bool) if "defocus_mask" in reference else None
            frame = judge_frame(a["frame"], b["frame"], mask.astype(bool), FRAME_RULE_B)
            textures = _textures_judged(a, b, TEXTURE_RULE_B, defocus=defocus)
            # Choice G: QRhi's generateMips is a linear blit on Vulkan and the driver's own filter on OpenGL; they
            # agree wherever a level halves an even-sized one (the 64 px bucket makes levels 1 to 6 such), while a
            # level made from an odd-sized one is implementation-defined (GL 4.6 section 8.14.4): reported apart.
            odd = {k: textures.pop(k) for k in list(textures) if k.startswith("near.") and _odd_source(a, k)}
            if odd:
                odd["pass"] = True
                textures["odd_source_levels_reported"] = odd
            judged = {"frame": frame, **textures}
            gated = case.samples == 1
            case_ok = all(v.get("pass") for v in judged.values()) if gated else True
            mips = {k: {"pass": v.get("pass"), "max_level": v.get("max_level"), "differing": v.get("differing"),
                        "size": list(a[k]["size"])} for k, v in textures.items() if k.startswith("near.")}
            result["rule_b"][case.name] = {"pass": case_ok, "gated": gated, "judged": judged, "mips": mips}
            ok = ok and case_ok
        result["rule_b"]["pass"] = ok
        result["rule_b"]["bounds"] = {"frame": FRAME_RULE_B.bound(), "texture": TEXTURE_RULE_B.bound()}
    else:
        result["rule_b"] = {"pass": False, "error": "a frame set is missing"}
    # Analytic, per API.
    eb_values = _ps().values_for(build(CASE["eb_1x"], {k: b"" for k in _ps().texts()})[0])
    for api, frames in (("opengl", gl), ("vulkan", vk)):
        if not frames:
            continue
        checks = {}
        try:
            checks["coverage_inverted_is_the_textbook_revealage"] = coverage_analytic(
                frames["eb_1x"], ref.get("eb_1x") if api == "opengl" else None, eb_values, CARD)
            checks["two_orders_agree"] = order_analytic(frames["eb_1x"], frames["eb_reversed_1x"])
            checks["hdr_kept_and_no_glow_without_emission"] = hdr_and_glow_analytic(frames["eb_1x"],
                                                                                   frames["eb_dark_1x"])
            band_values = dict(eb_values, u_l1_band=BAND)
            checks["per_sample_resolve"] = per_sample_analytic(
                frames["eb_band_4x"], frames["eb_band_4x_first_sample"],
                ref.get("eb_band_4x") if api == "opengl" else None, band_values, CARD)
        except Exception:
            checks["error"] = {"pass": False, "error": traceback.format_exc()}
        result["analytic"][api] = {"pass": all(v.get("pass") for v in checks.values()), "checks": checks}
    result["analytic"]["pass"] = bool(result["analytic"]) and all(
        v.get("pass") for k, v in result["analytic"].items() if k != "pass")
    return result


# --------------------------------------------------------------------------------------------------- native rounds

def round_parity(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    checks, facts, frames = {}, {}, {}
    host = _host(core)
    try:
        for case in CASES:
            run = run_case(core, engine, app, host, packs, case, repeat=case.samples > 1)
            frames[case.name] = run["textures"]
            facts[case.name] = _state_facts(run["state"])
            checks[f"{case.name}_drew"] = not facts[case.name]["error"] and \
                int(run["textures"]["frame"]["array"][..., :3].max()) > 0
            if run["again"] is not None:
                same = {k: bool((run["again"][k]["array"] == v["array"]).all()) for k, v in run["textures"].items()
                        if k in run["again"]}
                facts[case.name]["repeat_exact"] = same
                checks[f"{case.name}_repeats_exactly"] = all(same.values())
            if case.name == "solo_fallback_1x":
                checks["solo_fallback_recorded"] = len(facts[case.name]["fallbacks"] or []) == 1
            elif case.scene in ("eb", "solo"):
                checks[f"{case.name}_admitted"] = not facts[case.name]["fallbacks"]
    finally:
        host.close()
        host_check._flush_deletes(app)
    stc._save(out, f"post_{api}", frames)
    _sheets(out, api, frames)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_gate(core, engine, app, api: str, packs: dict) -> dict:
    """The gate's fallbacks by control, each recorded once over several records; a program without stages holds no
    stage object."""
    checks, facts = {}, {}
    host = _host(core)

    def records(case: Case, count: int = 6) -> dict:
        _controls(core, case.controls, True)
        try:
            passes, targets, values = build(case, packs)
            before = _live(core)
            scene = stc.Scene(core, engine, host, case.card, 1.0, packs, passes=passes, targets=targets,
                              settings=values)
            try:
                textures = scene.targets(app)
                bump = BUMP[case.scene]
                for i in range(count):
                    scene.mode.settings(dict(values, **{bump: values[bump] * (0.9 if i % 2 == 0 else 1.0)}))
                    host.frames(1)
                state = scene.mode.state()
                held = _live(core)
                frame = _frame(host, case.card)
            finally:
                _close(scene, host, app)
        finally:
            _controls(core, case.controls, False)
        return {"state": _state_facts(state), "names": sorted(textures),
                "fallbacks_counted": held["stage_fallbacks"] - before["stage_fallbacks"],
                "stage_textures": held["stage_textures"], "frame_max": int(frame[..., :3].max())}

    try:
        solo = records(Case("solo_formats", "solo", controls=("blend_formats_missing",)))
        facts["solo_formats_missing"] = solo
        checks["formats_missing_one_attachment_owner_falls_back_once"] = (
            len(solo["state"]["fallbacks"] or []) == 1 and "COLOR_ATTACHMENT_BLEND" in solo["state"]["fallbacks"][0]
            and solo["fallbacks_counted"] == 1 and not solo["state"]["error"] and solo["frame_max"] > 0
            and not any(n.startswith("solo_glass.") for n in solo["names"]))
        eb = records(Case("eb_formats", "eb", controls=("blend_formats_missing",)))
        facts["eb_formats_missing"] = eb
        checks["formats_missing_eb_shape_falls_back_once"] = (
            len(eb["state"]["fallbacks"] or []) == 1 and eb["fallbacks_counted"] == 1 and not eb["state"]["error"]
            and eb["frame_max"] > 0 and not any(n.startswith("glass.") for n in eb["names"]))
        shading = records(Case("solo_shading_4x", "solo", samples=4, controls=("sample_shading_missing",)))
        facts["sample_shading_missing_4x"] = shading
        checks["sample_shading_missing_falls_back_at_4x"] = (
            len(shading["state"]["fallbacks"] or []) == 1 and "sampleRateShading" in shading["state"]["fallbacks"][0]
            and shading["fallbacks_counted"] == 1 and not shading["state"]["error"])
        single = records(Case("solo_shading_1x", "solo", controls=("sample_shading_missing",)))
        facts["sample_shading_missing_1x"] = single
        checks["sample_shading_missing_admits_1x"] = not single["state"]["fallbacks"] and single["fallbacks_counted"] == 0
        admitted = records(Case("solo_admitted", "solo"))
        facts["solo_admitted"] = admitted
        checks["admitted_records_no_fallback"] = not admitted["state"]["fallbacks"] and admitted["fallbacks_counted"] == 0
        # The defocus read level's cap (the lead, 15 Nov): at the cap drawn, one past it refused with its reason.
        from rendering.native.scene_targets import bucket_pixels

        cap = _ps().read_level_cap((bucket_pixels(CARD[0]), bucket_pixels(CARD[1])))
        at_cap = records(Case("eb_level_cap", "eb", changes={"u_defocus_level": cap}), 2)
        past_cap = records(Case("eb_level_past_cap", "eb", changes={"u_defocus_level": cap + 1}), 2)
        facts["defocus_read_level_cap"] = {"cap": cap, "at_cap": at_cap["state"], "past_cap": past_cap["state"]}
        checks["defocus_read_level_at_the_cap_drawn"] = not at_cap["state"]["error"] and at_cap["frame_max"] > 0
        checks["defocus_read_level_past_the_cap_refused"] = f"read level {cap + 1} is outside 0 to {cap}" in str(
            past_cap["state"]["error"])
        # A program without stages (an owner pass and a plain capture-free surface pass of N3.1's harness scene).
        st = stc._scene_module()
        with tempfile.TemporaryDirectory(prefix="srpss_n34_plain_") as scratch:
            plain = st.bake_all(Path(scratch))
            scene = stc.Scene(core, engine, host, CARD, 1.0, plain)
            try:
                scene.targets(app)
                live = _live(core)
            finally:
                _close(scene, host, app)
        facts["without_stages"] = {k: live.get(k) for k in STAGE_KEYS}
        checks["a_program_without_stages_holds_no_stage_object"] = all(live.get(k) == 0 for k in STAGE_KEYS)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_rest(core, engine, app, api: str, packs: dict) -> dict:
    host = _host(core)
    checks, facts = {}, {}
    try:
        passes, targets, values = build(CASE["eb_1x"], packs)
        scene = stc.Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
        try:
            scene.targets(app)
            host.frames(2)
            before, live_before = scene.mode.state(), _live(core)
            host.frames(REST_FRAMES)
            scene.mode.update()
            host.frames(REST_FRAMES)
            after, live_after = scene.mode.state(), _live(core)
            scene.mode.settings(dict(values, u_back_gain=values["u_back_gain"] * 0.9))
            host.frames(2)
            control, live_control = scene.mode.state(), _live(core)
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    rest = {k: live_after[k] - live_before[k] for k in RECORD_KEYS}
    changed = {k: live_control[k] - live_after[k] for k in RECORD_KEYS}
    facts = {"records": [before.get("records"), after.get("records"), control.get("records")],
             "stage_records_at_rest": rest, "stage_records_after_a_change": changed,
             "objects_created_at_rest": live_after["stage_objects_created"] - live_before["stage_objects_created"]}
    checks["nothing_recorded_at_rest"] = after.get("records") == before.get("records") and all(
        v == 0 for v in rest.values()) and facts["objects_created_at_rest"] == 0
    checks["control_a_setting_change_records_every_stage"] = (control.get("records", 0) > after.get("records", 0)
                                                              and all(v > 0 for v in changed.values()))
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_steady(core, engine, app, api: str, packs: dict) -> dict:
    """A minute of records (a setting alternating each frame): no stage object created after the first records, and
    the process's private memory over the minute."""
    host = _host(core)
    checks, facts = {}, {}
    try:
        passes, targets, values = build(CASE["eb_4x"], packs)
        scene = stc.Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
        try:
            scene.targets(app)
            for i in range(30):
                scene.mode.settings(dict(values, u_back_gain=values["u_back_gain"] + (0.01 if i % 2 else 0.0)))
                host.frames(1)
            before, counters_before = _live(core), core.process_counters()
            state_before = scene.mode.state()
            deadline = time.monotonic() + STEADY_SECONDS
            samples, i = [], 0
            while time.monotonic() < deadline:
                scene.mode.settings(dict(values, u_back_gain=values["u_back_gain"] + (0.01 if i % 2 else 0.0)))
                host.frames(1)
                i += 1
                if i % 200 == 0:
                    samples.append(round(core.process_counters().get("private_mib", 0.0), 2))
            after, counters_after = _live(core), core.process_counters()
            state_after = scene.mode.state()
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    facts = {"frames": i, "records": [state_before.get("records"), state_after.get("records")],
             "objects_created": after["stage_objects_created"] - before["stage_objects_created"],
             "stage_records": {k: after[k] - before[k] for k in RECORD_KEYS},
             # The render thread's record time of a program with stages (EB's shape at 4x, the card's size).
             "record_us_mean": (round((after["stage_record_ns"] - before["stage_record_ns"]) / 1e3
                                      / max(1, after["stage_records_timed"] - before["stage_records_timed"]), 2)
                                if "stage_record_ns" in after else None),
             "private_mib": [round(counters_before.get("private_mib", 0.0), 2),
                             round(counters_after.get("private_mib", 0.0), 2)],
             "private_mib_samples": samples}
    facts["private_mib_growth"] = round(facts["private_mib"][1] - facts["private_mib"][0], 2)
    checks["no_stage_object_created_over_the_minute"] = facts["objects_created"] == 0 and \
        facts["stage_records"]["stage_bloom_records"] > 0
    checks["no_python_thread_state_on_the_render_thread"] = bool(
        state_after.get("syncs_probed") and state_after.get("syncs_with_python_thread_state") == 0)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


ZERO_KEYS = STAGE_KEYS + ("scene_targets", "scene_target_textures", "scene_target_bytes")


def round_retire(core, engine, app, api: str, packs: dict) -> dict:
    checks, facts = {}, {}

    def snapshot() -> dict:
        live = _live(core)
        return {k: live.get(k) for k in ZERO_KEYS + ("stage_left_behind",)}

    def zero(s: dict) -> bool:
        return all(s.get(k) == 0 for k in ZERO_KEYS)

    host = _host(core)
    try:
        passes, targets, values = build(CASE["eb_1x"], packs)
        # Held, then a program without the stages on the live item, then a mode switch, then the destroy.
        scene = stc.Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
        try:
            scene.targets(app)
            facts["held"] = snapshot()
            plain_passes, plain_targets, plain_values = build(Case("plain", "solo"), packs)
            plain_passes = (plain_passes[0], plain_passes[-1])
            plain_targets = (plain_targets[0],)
            scene.mode.program(plain_passes, _ps().values_for(plain_passes), targets=plain_targets)
            host.frames(3)
            facts["without_stages"] = snapshot()
            osc_passes, osc_targets, osc_values = build(CASE["osc_1x"], packs)
            scene.mode.program(osc_passes, osc_values, targets=osc_targets)
            host.frames(3)
            facts["switched_to_osc"] = snapshot()
        finally:
            _close(scene, host, app)
        facts["destroyed"] = snapshot()
        checks["held_while_drawn"] = (facts["held"]["stage_bloom_chains"] == 1 and facts["held"]["stage_defocus_steps"]
                                      == 1 and facts["held"]["stage_textures"] > 0
                                      and facts["held"]["scene_targets"] == 3)
        checks["a_program_without_stages_releases_them"] = all(
            facts["without_stages"][k] == 0 for k in STAGE_KEYS) and facts["without_stages"]["scene_targets"] == 1
        checks["a_mode_switch_keeps_only_what_the_new_program_declares"] = (
            facts["switched_to_osc"]["stage_bloom_chains"] == 1 and facts["switched_to_osc"]["stage_defocus_steps"] == 0
            and facts["switched_to_osc"]["scene_targets"] == 1)
        checks["destroy_leaves_nothing"] = zero(facts["destroyed"])
        # Destroyed mid-resize: the card changed, the item gone before a frame.
        scene = stc.Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
        scene.targets(app)
        scene.resize(UNALIGNED)
        _close(scene, host, app)
        facts["destroyed_mid_resize"] = snapshot()
        checks["destroyed_mid_resize_leaves_nothing"] = zero(facts["destroyed_mid_resize"])
        # The skipped-release control: left behind and counted, then released at the next stage sync.
        _controls(core, ("skip_stage_release",), True)
        try:
            scene = stc.Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
            scene.targets(app)
            _close(scene, host, app)
            facts["control_skipped_release"] = snapshot()
        finally:
            _controls(core, ("skip_stage_release",), False)
        checks["control_skipped_release_is_counted"] = facts["control_skipped_release"]["stage_left_behind"] > 0
        scene = stc.Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
        scene.targets(app)
        _close(scene, host, app)
        facts["after_the_control"] = snapshot()
        checks["the_control_leaves_nothing_after_it"] = zero(facts["after_the_control"]) and \
            facts["after_the_control"]["stage_left_behind"] == 0
    finally:
        host.close()
        host_check._flush_deletes(app)
    # The scene graph's invalidation: the host closed with the item alive.
    host = _host(core)
    scene = stc.Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
    try:
        scene.targets(app)
        host.close()
        host_check._flush_deletes(app)
        facts["host_closed"] = snapshot()
        checks["invalidation_releases_the_stages"] = zero(facts["host_closed"])
    finally:
        scene.mode.composite.destroy()
        host_check._drop_item(app, scene.root)
        host_check._flush_deletes(app)
    facts["end"] = snapshot()
    checks["nothing_left"] = zero(facts["end"])
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _records(core, engine, app, host, packs: dict, case: Case, count: int) -> dict:
    """``count`` consecutive records with no readback between them (a setting alternating)."""
    _controls(core, case.controls, True)
    try:
        passes, targets, values = build(case, packs)
        scene = stc.Scene(core, engine, host, case.card, 1.0, packs, passes=passes, targets=targets, settings=values)
        try:
            host.frames(2)
            bump = BUMP[case.scene]
            for i in range(count):
                scene.mode.settings(dict(values, **{bump: values[bump] * (0.9 if i % 2 == 0 else 1.0)}))
                host.frames(1)
            state = scene.mode.state()
        finally:
            _close(scene, host, app)
    finally:
        _controls(core, case.controls, False)
    return _state_facts(state)


def round_barriers(core, engine, app, api: str, packs: dict) -> dict:
    checks, facts = {}, {}
    vulkan = api == "vulkan"

    def phase(name: str) -> None:
        if vulkan:
            core.set_vulkan_phase(name)

    host = _host(core)
    try:
        phase("n34 barriers")
        for case in (CASE["eb_1x"], CASE["eb_4x"], CASE["osc_1x"], CASE["tiles_4x"], CASE["solo_1x"],
                     CASE["solo_fallback_1x"], Case("eb_band", "eb", samples=4, band=BAND)):
            facts[f"records_{case.name}"] = _records(core, engine, app, host, packs, case, BARRIER_RECORDS)
        if vulkan:
            phase("n34 control depth prime")
            core.scene_depth_prime_control(True)
            try:
                for case in (CASE["eb_1x"], CASE["solo_1x"]):
                    _records(core, engine, app, host, packs, case, CONTROL_RECORDS)
            finally:
                core.scene_depth_prime_control(False)
            phase("n34 control bloom prime")
            facts["control_bloom_prime"] = _records(core, engine, app, host, packs,
                                                    Case("eb", "eb", controls=("skip_bloom_prime",)), CONTROL_RECORDS)
            phase("n34 control bloom same texture")
            facts["control_bloom_same_texture"] = _records(core, engine, app, host, packs,
                                                           Case("osc", "osc", controls=("bloom_same_texture",),
                                                                changes={"u_hdr_exposure": 0.0}), CONTROL_RECORDS)
            phase("n34 control read chain")
            facts["control_read_chain"] = _records(core, engine, app, host, packs,
                                                   Case("eb", "eb", controls=("skip_read_chain",)), CONTROL_RECORDS)
            phase("n34 after controls")
    finally:
        host.close()
        host_check._flush_deletes(app)
    if vulkan:
        # A device without independentBlend: the gate bypassed (the layer's finding), then with the gate.
        _controls(core, ("device_without_independent_blend",), True)
        try:
            phase("n34 control no independent blend")
            host = _host(core)
            try:
                _controls(core, ("skip_blend_gate",), True)
                try:
                    facts["control_no_independent_blend_solo"] = _records(core, engine, app, host, packs,
                                                                          CASE["solo_1x"], 4)
                    facts["control_no_independent_blend_eb"] = _records(core, engine, app, host, packs, CASE["eb_1x"], 4)
                finally:
                    _controls(core, ("skip_blend_gate",), False)
            finally:
                host.close()
                host_check._flush_deletes(app)
            phase("n34 gate no independent blend")
            host = _host(core)
            try:
                before = _live(core)
                solo = run_case(core, engine, app, host, packs, CASE["solo_1x"])
                after = _live(core)
                eb = _records(core, engine, app, host, packs, CASE["eb_1x"], 4)
            finally:
                host.close()
                host_check._flush_deletes(app)
        finally:
            _controls(core, ("device_without_independent_blend",), False)
            phase("n34 after the device control")
        solo_facts = _state_facts(solo["state"])
        facts["gate_no_independent_blend"] = {"solo": solo_facts, "solo_fallbacks_counted":
                                              after["stage_fallbacks"] - before["stage_fallbacks"], "eb": eb}
        checks["no_independent_blend_one_attachment_owner_falls_back_once"] = (
            len(solo_facts["fallbacks"] or []) == 1 and "independentBlend" in solo_facts["fallbacks"][0]
            and not solo_facts["error"] and int(solo["textures"]["frame"]["array"][..., :3].max()) > 0)
        checks["no_independent_blend_eb_shape_refused_by_the_per_attachment_check"] = (
            "per-attachment blending" in str(eb["error"]) and "independentBlend" in str(eb["error"]))
        facts["gate_no_independent_blend_solo_colour"] = {"max": int(solo["textures"]["solo.colour"]["array"].max())}
    checks["barrier_records_ran"] = True
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def split_validation(messages: dict) -> dict:
    """The validation summary outside the control phases (must be clean) and, per control phase, whether its expected
    finding was reported."""
    entries = messages.get("entries", [])
    rest_entries = [e for e in entries if (e.get("phase") or "") not in CONTROL_PHASES]
    rest = dict(messages, entries=rest_entries,
                errors=sum(int(e.get("count", 1)) for e in rest_entries if e.get("severity") == "error"),
                warnings=sum(int(e.get("count", 1)) for e in rest_entries if e.get("severity") == "warning"))
    summary = vk_validation.validation_summary(rest)
    controls = {}
    for phase, rule in CONTROL_PHASES.items():
        expected = rule["expect"]
        found = [e for e in entries if e.get("phase") == phase and e.get("severity") == "error"]
        ids = sorted({str(e.get("id")) for e in found})
        if expected:
            matching = [e for e in found
                        if any(x in str(e.get("id")) or x in str(e.get("message", "")) for x in expected)]
        else:
            matching = found
        placed = [e for e in matching if rule["placed"] is None or rule["placed"] in str(e.get("message", ""))]
        controls[phase] = {"expected": list(expected) or "any error", "required": rule["required"],
                           "placed_by": rule["placed"], "found": ids, "reported": bool(placed),
                           "count": sum(int(e.get("count", 1)) for e in found),
                           "placed_count": sum(int(e.get("count", 1)) for e in placed),
                           "first_message": (placed[0].get("message", "")[:600] if placed else
                                             found[0].get("message", "")[:600] if found else "")}
    return {"outside_controls": {k: v for k, v in summary.items() if k != "groups"},
            "attribution": summary["groups"], "controls": controls}


def round_cost(core, engine, app, api: str, packs: dict) -> dict:
    """Each stage's GPU time: the EB scene's record with every stage less the record without that stage (median and
    p10 of each), at 2560x1440 and 4K, one and four samples."""
    ps = _ps()
    checks, facts = {}, {}
    for size in COST_HOSTS:
        label = f"{size[0]}x{size[1]}"
        facts[label] = {}
        host = core.hidden_host(size[0] + 2 * MARGIN, size[1] + 2 * MARGIN)
        try:
            for samples in (1, 4):
                timings = {}
                for variant in ps.EB_VARIANTS:
                    case = Case(f"cost_{variant}", "eb", card=size, samples=samples, variant=variant)
                    passes, targets, values = build(case, packs)
                    scene = stc.Scene(core, engine, host, size, 1.0, packs, passes=passes, targets=targets,
                                      settings=values)
                    try:
                        host.frames(4)
                        started = time.perf_counter()
                        live = _live(core)
                        timings[variant] = stc._timed(host, scene, values, COST_FRAMES, member="u_back_gain",
                                                      step=0.001)
                        timings[variant]["wall_s"] = round(time.perf_counter() - started, 2)
                        state, after = scene.mode.state(), _live(core)
                        timings[variant]["error"] = _state_facts(state)["error"]
                        # The render thread's record time (CPU), mean over the timed records of a program with stages.
                        timed = after.get("stage_records_timed", 0) - live.get("stage_records_timed", 0)
                        timings[variant]["record_us_mean"] = (round((after["stage_record_ns"] - live["stage_record_ns"])
                                                                    / 1e3 / timed, 2) if timed else None)
                    finally:
                        _close(scene, host, app)
                full = timings["full"]
                stages = {}
                for variant, stage in (("no_transparency", "transparency"), ("no_bloom", "bloom_and_glow_composite"),
                                       ("no_defocus", "defocus")):
                    a, b = full.get("median_ms"), timings[variant].get("median_ms")
                    a10, b10 = full.get("p10_ms"), timings[variant].get("p10_ms")
                    stages[stage] = {"median_ms": None if a is None or b is None else round(a - b, 4),
                                     "p10_ms": None if a10 is None or b10 is None else round(a10 - b10, 4)}
                facts[label][f"x{samples}"] = {"timings": timings, "stages": stages}
                checks[f"{label}_x{samples}_timed"] = all(t.get("samples", 0) >= stc.COST_MIN_SAMPLES
                                                          for t in timings.values())
        finally:
            host.close()
            host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the reference

REFERENCE_VERTEX = stc.REFERENCE_VERTEX


class GLReference:
    """The harness fragments in the reference's own context, each pass's block packed by the module."""

    def __init__(self, core, packs: dict, size) -> None:
        from tools.labs.render_target import OffscreenRenderTarget

        self.core, self.packs = core, packs
        self.target = OffscreenRenderTarget(int(size[0]), int(size[1]), label="n34-reference")
        self.programs: dict = {}
        self.buffers: list[int] = []

    def program(self, name: str) -> int:
        from rendering.quick.render.gl_resources import compile_program

        if name not in self.programs:
            self.programs[name] = compile_program(REFERENCE_VERTEX, _ps().texts()[name], label=f"n34 {name}")
        return self.programs[name]

    def draw(self, name: str, values: dict) -> None:
        import ctypes

        from OpenGL import GL as gl

        ps = _ps()
        data, _facts = self.core.program_block_pack(self.packs[name], ps.BLOCKS[name], ps.members(name, values))
        buffer = (ctypes.c_uint * 1)()
        gl.glCreateBuffers(1, buffer)
        gl.glNamedBufferData(int(buffer[0]), len(data), data, gl.GL_STATIC_DRAW)
        self.buffers.append(int(buffer[0]))
        gl.glUseProgram(self.program(name))
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 18, int(buffer[0]))
        gl.glBindVertexArray(self.target.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

    def release(self) -> None:
        from OpenGL import GL as gl

        from rendering.quick.render.gl_resources import delete_program

        for buffer in self.buffers:
            gl.glDeleteBuffers(1, [buffer])
        for program in self.programs.values():
            delete_program(program)
        self.buffers, self.programs = [], {}


def _read(texture: int, w: int, h: int, fmt: str, level: int = 0, content=None) -> dict:
    """A texture's level read back as the core reads its own (rows flipped to the image's top first)."""
    import numpy as np
    from OpenGL import GL as gl

    if fmt == "rgba8":
        array = np.empty((h, w, 4), np.uint8)
        gl.glGetTextureImage(texture, level, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, array.nbytes, array)
    elif fmt == "rgba16f":
        array = np.empty((h, w, 4), np.float16)
        gl.glGetTextureImage(texture, level, gl.GL_RGBA, gl.GL_HALF_FLOAT, array.nbytes, array)
    elif fmt == "r16f":
        array = np.empty((h, w), np.float16)
        gl.glGetTextureImage(texture, level, gl.GL_RED, gl.GL_HALF_FLOAT, array.nbytes, array)
    else:
        array = np.empty((h, w), np.float32)
        gl.glGetTextureImage(texture, level, gl.GL_RED, gl.GL_FLOAT, array.nbytes, array)
    return {"array": array[::-1].copy(), "content": tuple(content or (w, h)), "size": (w, h), "format": fmt,
            "samples": 1}


def _resolved(fbo: int, attachment: int, w: int, h: int, fmt: str, content) -> dict:
    """A multisampled attachment averaged (a resolve blit, as QRhi's OpenGL resolve) and read."""
    import ctypes

    from OpenGL import GL as gl

    internal = {"rgba8": gl.GL_RGBA8, "rgba16f": gl.GL_RGBA16F, "r16f": gl.GL_R16F}[fmt]
    names = (ctypes.c_uint * 1)()
    gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, names)
    texture = int(names[0])
    gl.glTextureStorage2D(texture, 1, internal, w, h)
    gl.glCreateFramebuffers(1, names)
    resolve = int(names[0])
    gl.glNamedFramebufferTexture(resolve, gl.GL_COLOR_ATTACHMENT0, texture, 0)
    gl.glNamedFramebufferReadBuffer(fbo, gl.GL_COLOR_ATTACHMENT0 + attachment)
    gl.glBlitNamedFramebuffer(fbo, resolve, 0, 0, w, h, 0, 0, w, h, gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
    gl.glNamedFramebufferReadBuffer(fbo, gl.GL_COLOR_ATTACHMENT0)
    gl.glFinish()
    entry = _read(texture, w, h, fmt, content=content)
    gl.glDeleteFramebuffers(1, [resolve])
    gl.glDeleteTextures([texture])
    return entry


def _scene_read(scene, key: str, attachment: int, fmt: str, content) -> dict:
    w, h = scene._key[0], scene._key[1]
    if scene._samples > 1:
        fbo = scene._names["oit_fbo"] if key.startswith("oit_") else scene._names["fbo"]
        return _resolved(fbo, attachment, w, h, fmt, content)
    return _read(scene._names[key], w, h, fmt, content=content)


def _frame_read(ref: GLReference, card) -> dict:
    import numpy as np
    from OpenGL import GL as gl

    w, h = card
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, ref.target.fbo)
    raw = gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    array = np.frombuffer(raw, np.uint8).reshape(h, w, 4)[::-1].copy()
    return _entry(array, card)


def _glow_mask(scene, strength: float, card):
    """The pixels the reference's glow adds to (its half-size level 0 read where each pixel samples it, widened by a
    texel: the dither floor's pixels and their neighbours)."""
    import numpy as np

    from rendering.gl_programs.scene3d import SCENE_DITHER_STEP

    texture, _fbo, gw, gh = scene._bloom._levels[0]
    glow = _read(texture, gw, gh, "rgba16f")["array"].astype(np.float64)[..., :3].max(axis=2) * strength
    lit = glow >= SCENE_DITHER_STEP / 8.0
    lit = pt._neighbourhood(lit.astype(np.uint8), np.maximum).astype(bool)
    full = np.repeat(np.repeat(lit, 2, axis=0), 2, axis=1)
    # Top-first rows of the half-size texture over the allocation; the content is the allocation's bottom-left in GL
    # (its last rows top first).
    rows = full.shape[0]
    return full[rows - card[1]:, :card[0]]


def _bloom_source_as_designed(scene) -> None:
    """The bloom chain's source sampled as its own levels are (LINEAR, CLAMP_TO_EDGE), where ``SceneTarget`` leaves
    the scene's colour, emission and their resolves at ``_allocate_plain_texture``'s NEAREST and GL's default REPEAT
    (target.py:1167-1173): the 13-tap filter is designed for bilinear taps, and REPEAT carries light from the opposite
    edge. The core's chain samples its source LINEAR and CLAMP_TO_EDGE (post_stages.cpp)."""
    from OpenGL import GL as gl

    for key in ("colour", "emission", "resolve_texture", "emission_resolve"):
        texture = scene._names.get(key)
        if not texture or (key in ("colour", "emission") and scene._samples > 1):
            continue
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTextureParameteri(texture, parameter, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)


def _prepare_resolves(scene) -> None:
    """A multisampled scene's resolve textures exist before ``end`` (so their sampling state can be set)."""
    if scene._samples > 1:
        if scene._names["emission"] and not scene._names["emission_resolve"]:
            scene._allocate_emission_resolve()
        if not scene._names["emission"] and not scene._names["resolve_texture"]:
            scene._allocate_resolve()


def _end_with_bloom(scene, frame, resources, values: dict, bloom_source: str) -> None:
    _prepare_resolves(scene)
    if bloom_source == "designed":
        _bloom_source_as_designed(scene)
    scene.end(frame, resources, bloom=float(values["u_bloom_strength"]))


#: How the reference's bloom source is sampled: "designed" (LINEAR, CLAMP_TO_EDGE, as the core's) or "product"
#: (Python's NEAREST and REPEAT as drawn today).
BLOOM_SOURCES = ("designed", "product")


def reference_case(core, packs: dict, case: Case, bloom_source: str = "designed") -> dict:
    """The Python stages drawing ``case``: textures, frame and the frame's explained mask."""
    import numpy as np
    from types import SimpleNamespace

    from OpenGL import GL as gl

    from rendering.quick.scene3d.defocus import DefocusLayer
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.target import SceneTarget

    ps = _ps()
    w, h = case.card
    passes, _targets, values = build(case, packs)
    values = dict(ps.SETTINGS, **values)
    ref = GLReference(core, packs, case.card)
    out: dict = {}
    with ref.target.current():
        resources, scene, layer = MeshResources("n34 reference"), SceneTarget("n34 reference"), DefocusLayer("n34")
        frame = SimpleNamespace(viewport=(0, 0, w, h), logical_size=(w, h),
                                matrix_values=(2 / w, 0, 0, 0, 0, -2 / h, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                quad_vao=ref.target.vao)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, ref.target.fbo)
        gl.glViewport(0, 0, w, h)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClearDepth(1.0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        mask = np.zeros((h, w), bool)
        rect = (0, 0, w, h)
        try:
            if case.scene == "eb":
                scene.begin(frame, case.samples, rect, overlay=1.0, emission=True, depth_texture=True, oit=True,
                            hdr=True)
                scene._exposure = max(float(values["u_hdr_exposure"]), 1e-3)
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDisablei(gl.GL_BLEND, 0)
                gl.glDepthFunc(gl.GL_ALWAYS)
                with scene.emission_writes():
                    ref.draw("backdrop", values)
                scene.background(frame, resources)
                gl.glDepthFunc(gl.GL_LESS)
                with scene.transparent_writes(frame, resources):
                    for n in case.order:
                        ref.draw(f"eb_layer{n}", values)
                content = (w, h)
                before = _scene_read(scene, "colour", 0, "rgba16f", content)
                layer.begin(w, h)
                ref.draw("near", values)
                layer.end()
                layer.composite(float(values["u_defocus_radius"]), float(values["u_defocus_highlight"]))
                gl.glFinish()
                out["scene.colour"] = _scene_read(scene, "colour", 0, "rgba16f", content)
                out["scene.emission"] = _scene_read(scene, "emission", 1, "rgba16f", content)
                spread = np.abs(stc._content(out["scene.colour"]).astype(np.float64)
                                - stc._content(before).astype(np.float64)).max(axis=2) > 0
                spread = pt._neighbourhood(spread.astype(np.uint8), np.maximum).astype(bool)
                mask |= spread
                out["defocus_mask"] = _entry(spread.astype(np.uint8), case.card, "mask")
                if case.samples == 1:
                    aw, ah = scene._key[0], scene._key[1]
                    out["glass.accum"] = _read(scene._names["oit_accum"], aw, ah, "rgba16f", content=content)
                    reveal = _read(scene._names["oit_reveal"], aw, ah, "r16f", content=content)
                    textbook = 1.0 - reveal["array"].astype(np.float64)
                    out["glass.coverage_textbook"] = dict(reveal, array=textbook.astype(np.float32), format="r32f")
                    covered = stc._content(dict(reveal, array=textbook)) > 1.0 / 1024.0
                else:
                    reveal = _resolved(scene._names["oit_fbo"], 1, scene._key[0], scene._key[1], "r16f", content)
                    covered = stc._content(reveal).astype(np.float64) < 1.0 - 1.0 / 1024.0
                mask |= pt._neighbourhood(covered.astype(np.uint8), np.maximum).astype(bool)
                if case.card == CARD:
                    lw, lh = layer._size
                    level, size = 0, (lw, lh)
                    while True:
                        suffix = f"@{level}" if level else ""
                        out[f"near.colour{suffix}"] = _read(layer._colour, size[0], size[1], "rgba16f", level)
                        out[f"near.circle{suffix}"] = _read(layer._circle, size[0], size[1], "rgba16f", level)
                        if size == (1, 1):
                            break
                        level, size = level + 1, (max(1, size[0] // 2), max(1, size[1] // 2))
                _end_with_bloom(scene, frame, resources, values, bloom_source)
                mask |= _glow_mask(scene, float(values["u_bloom_strength"]), case.card)
            elif case.scene == "osc":
                scene.begin(frame, 1, rect, overlay=1.0, emission=True)
                with scene.emission_writes():
                    for i in (0, 1):
                        gl.glEnablei(gl.GL_BLEND, i)
                        gl.glBlendEquationSeparatei(i, gl.GL_MAX, gl.GL_MAX)
                        gl.glBlendFuncSeparatei(i, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
                    for n in ps.TRACES:
                        ref.draw(f"trace{n}", values)
                    for i in (0, 1):
                        gl.glBlendEquationSeparatei(i, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                        gl.glDisablei(gl.GL_BLEND, i)
                gl.glFinish()
                out["scene.colour"] = _scene_read(scene, "colour", 0, "rgba8", (w, h))
                out["scene.emission"] = _scene_read(scene, "emission", 1, "rgba16f", (w, h))
                _end_with_bloom(scene, frame, resources, values, bloom_source)
                mask |= _glow_mask(scene, float(values["u_bloom_strength"]), case.card)
            elif case.scene == "tiles":
                scene.begin(frame, case.samples, rect)
                ref.draw("tiles", values)
                gl.glFinish()
                out["scene.colour"] = _scene_read(scene, "colour", 0, "rgba8", (w, h))
                _end_with_bloom(scene, frame, resources, values, bloom_source)
                mask |= _glow_mask(scene, float(values["u_bloom_strength"]), case.card)
            elif case.scene == "solo" and case.reference == "same":
                scene.begin(frame, case.samples, rect, overlay=1.0, oit=True)
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDepthFunc(gl.GL_ALWAYS)
                ref.draw("solo_back", values)
                gl.glDepthFunc(gl.GL_LESS)
                with scene.transparent_writes(frame, resources):
                    for n in ps.LAYERS:
                        ref.draw(f"solo_layer{n}", values)
                gl.glFinish()
                out["solo.colour"] = _scene_read(scene, "colour", 0, "rgba8", (w, h))
                aw, ah = scene._key[0], scene._key[1]
                out["solo_glass.accum"] = _read(scene._names["oit_accum"], aw, ah, "rgba16f", content=(w, h))
                reveal = _read(scene._names["oit_reveal"], aw, ah, "r16f", content=(w, h))
                covered = stc._content(reveal).astype(np.float64) < 1.0 - 1.0 / 1024.0
                mask |= pt._neighbourhood(covered.astype(np.uint8), np.maximum).astype(bool)
                gl.glDisable(gl.GL_DEPTH_TEST)
                # The plain overlay writes straight colour for the caller's alpha blend (Quick's; the core's surface
                # pass: "alpha"), so the target holds it premultiplied as the core's surface does.
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendEquation(gl.GL_FUNC_ADD)
                gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
                scene.end(frame, resources)
                gl.glDisable(gl.GL_BLEND)
            else:
                # The sorted fallback: the owner's pass, then each disc's sorted pack premultiplied over, in order,
                # depth tested and not written, into an RGBA8 colour and a depth at the bucketed allocation.
                out.update(_sorted_reference(ref, values, case.card))
            gl.glFinish()
            frame_entry = _frame_read(ref, case.card)
            out["frame"] = frame_entry
            mask |= pt.translucent_by_alpha(frame_entry["array"])
            out["frame_mask"] = _entry(mask.astype(np.uint8), case.card, "mask")
        finally:
            scene.release()
            layer.release()
            resources.release_resources()
            ref.release()
    ref.target.close()
    return out


def _sorted_reference(ref: GLReference, values: dict, card) -> dict:
    import ctypes

    from OpenGL import GL as gl

    from rendering.native.scene_targets import bucket_pixels

    ps = _ps()
    aw, ah = bucket_pixels(card[0]), bucket_pixels(card[1])
    names = (ctypes.c_uint * 2)()
    gl.glCreateTextures(gl.GL_TEXTURE_2D, 2, names)
    colour, depth = int(names[0]), int(names[1])
    gl.glTextureStorage2D(colour, 1, gl.GL_RGBA8, aw, ah)
    gl.glTextureStorage2D(depth, 1, gl.GL_DEPTH_COMPONENT32F, aw, ah)
    fbo = (ctypes.c_uint * 1)()
    gl.glCreateFramebuffers(1, fbo)
    fbo = int(fbo[0])
    gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0, colour, 0)
    gl.glNamedFramebufferTexture(fbo, gl.GL_DEPTH_ATTACHMENT, depth, 0)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glViewport(0, 0, aw, ah)
    gl.glClearColor(0.0, 0.0, 0.0, 0.0)
    gl.glClearDepth(1.0)
    gl.glDepthMask(gl.GL_TRUE)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    gl.glViewport(0, 0, card[0], card[1])
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glDepthFunc(gl.GL_ALWAYS)
    gl.glDisable(gl.GL_BLEND)
    ref.draw("solo_back", values)
    gl.glDepthFunc(gl.GL_LESS)
    gl.glDepthMask(gl.GL_FALSE)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendEquation(gl.GL_FUNC_ADD)
    gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
    for n in ps.LAYERS:
        ref.draw(f"solo_layer{n}_sorted", values)
    gl.glDisable(gl.GL_BLEND)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glDepthMask(gl.GL_TRUE)
    gl.glFinish()
    out = {"solo.colour": _read(colour, aw, ah, "rgba8", content=card)}
    # The frame: the plain overlay composite of that colour (straight times the fade, over the cleared target).
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, ref.target.fbo)
    gl.glViewport(0, 0, card[0], card[1])
    gl.glBlitNamedFramebuffer(fbo, ref.target.fbo, 0, 0, card[0], card[1], 0, 0, card[0], card[1],
                              gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
    gl.glDeleteFramebuffers(1, [fbo])
    gl.glDeleteTextures([colour, depth])
    return out


def round_reference(core, packs: dict, out: Path) -> dict:
    errors = {}
    for source in BLOOM_SOURCES:
        frames = {}
        for case in CASES:
            if case.reference is None or (source == "product" and case.scene not in ("eb", "osc", "tiles")):
                continue
            try:
                frames[case.name] = reference_case(core, packs, case, source)
            except Exception:
                errors[f"{case.name} ({source})"] = traceback.format_exc()
        name = "post_reference" if source == "designed" else "post_reference_product"
        stc._save(out, name, frames)
        if source == "designed":
            _sheets(out, "reference", frames)
    return {"pass": not errors, "errors": errors}


def python_cost(core, packs: dict, size, samples: int, variant: str, frames: int) -> dict:
    """The Python stages' GPU time on the EB load (``variant`` leaves stages out as the native cost round does), GL
    TIME_ELAPSED around the whole scope, one query a frame (read before the next: a counted loop, no sleep)."""
    import ctypes
    from types import SimpleNamespace

    from OpenGL import GL as gl

    from rendering.quick.scene3d.defocus import DefocusLayer
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.target import SceneTarget

    ps = _ps()
    w, h = size
    case = Case("cost", "eb", card=size, samples=samples, variant=variant)
    passes, _targets, values = build(case, packs)
    values = dict(ps.SETTINGS, **values)
    transparency = variant in ("full", "no_bloom", "no_defocus")
    bloom = variant in ("full", "no_transparency", "no_defocus")
    defocus = variant in ("full", "no_transparency", "no_bloom")
    ref = GLReference(core, packs, size)
    times: list[int] = []
    with ref.target.current():
        resources, scene, layer = MeshResources("n34 cost"), SceneTarget("n34 cost"), DefocusLayer("n34 cost")
        frame = SimpleNamespace(viewport=(0, 0, w, h), logical_size=(w, h),
                                matrix_values=(2 / w, 0, 0, 0, 0, -2 / h, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                quad_vao=ref.target.vao)
        query = (ctypes.c_uint * 1)()
        gl.glGenQueries(1, query)
        try:
            for index in range(frames + 4):
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, ref.target.fbo)
                gl.glBeginQuery(gl.GL_TIME_ELAPSED, int(query[0]))
                scene.begin(frame, samples, (0, 0, w, h), overlay=1.0, emission=bloom, depth_texture=True,
                            oit=transparency, hdr=bloom)
                scene._exposure = 1.0 if bloom else 0.0
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDisablei(gl.GL_BLEND, 0)
                gl.glDepthFunc(gl.GL_ALWAYS)
                with scene.emission_writes():
                    ref.draw("backdrop", dict(values, u_back_gain=values["u_back_gain"] + 0.001 * (index % 2)))
                scene.background(frame, resources)
                gl.glDepthFunc(gl.GL_LESS)
                if transparency:
                    with scene.transparent_writes(frame, resources):
                        for n in ps.LAYERS:
                            ref.draw(f"eb_layer{n}", values)
                if defocus:
                    layer.begin(w, h)
                    ref.draw("near", values)
                    layer.end()
                    layer.composite(float(values["u_defocus_radius"]), float(values["u_defocus_highlight"]))
                gl.glDisable(gl.GL_DEPTH_TEST)
                scene.end(frame, resources, bloom=float(values["u_bloom_strength"]) if bloom else 0.0)
                gl.glEndQuery(gl.GL_TIME_ELAPSED)
                value = (ctypes.c_uint64 * 1)()
                gl.glGetQueryObjectui64v(int(query[0]), gl.GL_QUERY_RESULT, value)
                if index >= 4:
                    times.append(int(value[0]))
                for buffer in ref.buffers:
                    gl.glDeleteBuffers(1, [buffer])
                ref.buffers = []
        finally:
            gl.glDeleteQueries(1, query)
            scene.release()
            layer.release()
            resources.release_resources()
            ref.release()
    ref.target.close()
    times.sort()
    return stc._time_summary(times)


def round_python_cost(core, packs: dict) -> dict:
    ps = _ps()
    facts = {}
    for size in COST_HOSTS:
        label = f"{size[0]}x{size[1]}"
        facts[label] = {}
        for samples in (1, 4):
            timings = {v: python_cost(core, packs, size, samples, v, PYTHON_COST_FRAMES) for v in ps.EB_VARIANTS}
            stages = {}
            for variant, stage in (("no_transparency", "transparency"), ("no_bloom", "bloom_and_glow_composite"),
                                   ("no_defocus", "defocus")):
                a, b = timings["full"]["median_ms"], timings[variant]["median_ms"]
                stages[stage] = {"median_ms": None if a is None or b is None else round(a - b, 4)}
            facts[label][f"x{samples}"] = {"timings": timings, "stages": stages}
    return {"pass": True, "facts": facts}


# --------------------------------------------------------------------------------------------------- the sheets

def _sheets(out: Path, api: str, frames: dict) -> None:
    """One look sheet per API: each case's frame (and the reference's mask), 320 px wide."""
    import numpy as np
    from PIL import Image

    tiles = []
    for case, textures in frames.items():
        if "frame" not in textures:
            continue
        rgb = textures["frame"]["array"][..., :3]
        tile = Image.fromarray(np.ascontiguousarray(rgb)).resize((320, 192))
        tiles.append(tile)
        if "frame_mask" in textures:
            m = (textures["frame_mask"]["array"] > 0).astype(np.uint8) * 255
            tiles.append(Image.fromarray(np.ascontiguousarray(np.repeat(m[..., None], 3, axis=2))).resize((320, 192)))
    if not tiles:
        return
    columns = 4
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (320 * columns, 192 * rows))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, (320 * (index % columns), 192 * (index // columns)))
    sheet.save(out / f"sheet_{api}.png")


# --------------------------------------------------------------------------------------------------- the child

def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api in ("opengl", "reference"):
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="post-stage-check")
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
        instance = core.vulkan_instance(validation=True, shader_accesses=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        if not (instance.get("instance") or {}).get("synchronisation_shader_accesses"):
            record["error"] = ("the layer's shader-access hazard checks did not load: "
                               f"{(instance.get('instance') or {}).get('synchronisation_shader_accesses_note')}")
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    with tempfile.TemporaryDirectory(prefix="srpss_n34_") as scratch:
        packs = _ps().bake_all(Path(scratch))
        try:
            if args.api == "reference":
                if "parity" in args.rounds:
                    try:
                        record["reference"] = round_reference(core, packs, out)
                    except Exception:
                        record["reference"] = {"pass": False, "error": traceback.format_exc()}
                if "python_cost" in args.rounds:
                    try:
                        record["python_cost"] = round_python_cost(core, packs)
                    except Exception:
                        record["python_cost"] = {"pass": False, "error": traceback.format_exc()}
                record["rounds"] = [r for r in ("reference", "python_cost") if r in record]
            else:
                rounds = {"parity": lambda: round_parity(core, engine, app, args.api, packs, out),
                          "gate": lambda: round_gate(core, engine, app, args.api, packs),
                          "rest": lambda: round_rest(core, engine, app, args.api, packs),
                          "steady": lambda: round_steady(core, engine, app, args.api, packs),
                          "retire": lambda: round_retire(core, engine, app, args.api, packs),
                          "barriers": lambda: round_barriers(core, engine, app, args.api, packs),
                          "cost": lambda: round_cost(core, engine, app, args.api, packs)}
                for name in args.rounds:
                    if vulkan:
                        core.set_vulkan_phase(f"n34 {name}")
                    try:
                        record[name] = rounds[name]()
                    except Exception:
                        record[name] = {"pass": False, "error": traceback.format_exc()}
        finally:
            host_check._flush_deletes(app)
            record["live_hosts_at_end"] = core.live_hosts()
            record["composites_at_end"] = core.composite_live()
            if vulkan:
                teardown = core.destroy_vulkan_instance()
                messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
                split = split_validation(messages)
                record["instance_teardown"] = teardown
                record["validation"] = {"layer_loaded": bool(record["instance"].get("validation_layer_loaded")),
                                        "per_phase": messages.get("per_phase"), **split["outside_controls"],
                                        "controls": split["controls"], "attribution": split["attribution"]}
            del engine
    return record


def api_verdict(api: str, record: dict, require_validation: bool, rounds) -> tuple[bool, list[str]]:
    if api == "reference":
        names = [n for n in ("reference", "python_cost") if n in record]
        failed = [f"{n}: {json.dumps(record[n].get('errors') or record[n].get('error') or 'failed')[-1500:]}"
                  for n in names if not record[n].get("pass")]
        if not names:
            failed.append(f"reference: {record.get('error')}")
        return not failed, failed
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if api == "vulkan" and "barriers" in rounds and record.get("instance_created"):
        for phase, c in ((record.get("validation") or {}).get("controls") or {}).items():
            if c.get("required") and not c.get("reported"):
                failed.append(f"vulkan: the control phase '{phase}' reported no {c.get('expected')} ({c.get('found')})")
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        left = {k: live.get(k) for k in ("items", "mode_sources", "mode_resources", *ZERO_KEYS, "stage_left_behind")
                if live.get(k)}
        if left:
            failed.append(f"{api}: left at the end ({left})")
    return not failed, failed


def _machine_state() -> dict:
    """The GPU's load and the displays (nvidia-smi), and any other SRPSS process (the figures' conditions)."""
    state = {}
    for key, command in (("nvidia_smi", ["nvidia-smi", "--query-gpu=name,driver_version,pstate,utilization.gpu,"
                                         "memory.used,display_active,display_mode,clocks.gr",
                                         "--format=csv,noheader"]),
                         ("srpss_processes", ["tasklist", "/FI", "IMAGENAME eq SRPSS.exe", "/FO", "CSV", "/NH"])):
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
            state[key] = proc.stdout.strip()
        except Exception as exc:
            state[key] = f"unavailable: {exc}"
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=(*ROUNDS, *PYTHON_ROUNDS))
    parser.add_argument("--label", default="n34_post_stages")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=(*APIS, "reference"), help=argparse.SUPPRESS)
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

    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n3_4", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    machine = {"before": _machine_state()}
    results: dict = {}
    native_rounds = [r for r in args.rounds if r not in PYTHON_ROUNDS]
    children = [a for a in APIS if a in args.apis and native_rounds]
    if ("parity" in args.rounds and "opengl" in args.apis) or "python_cost" in args.rounds:
        children.append("reference")
    for api in children:
        child_json = out / f"child_{api}.json"
        rounds = [r for r in args.rounds if r in ("parity", "python_cost")] if api == "reference" else native_rounds
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *rounds]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "rounds": rounds, "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        results[api] = record
    machine["after"] = _machine_state()

    verdicts = {api: api_verdict(api, record, args.require_validation, args.rounds) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    cross = None
    if "parity" in args.rounds:
        cross = cross_compare(out)
        needs = {"rule_a": "opengl" in args.apis, "rule_b": "vulkan" in args.apis and "opengl" in args.apis,
                 "analytic": True}
        for rule, needed in needs.items():
            if needed and not cross[rule].get("pass"):
                failing = {k: v for k, v in cross[rule].items() if isinstance(v, dict) and v.get("pass") is False}
                failed.append(f"{rule}: " + json.dumps(failing, default=str)[:2500])
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment, "machine": machine,
               "require_validation": args.require_validation, "cross": cross,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if cross is not None:
        print("cross: " + json.dumps({rule: v.get("pass") for rule, v in cross.items()}))
    print(f"evidence: {out / 'summary.json'} (the work folder holds the frames: delete it once judged)")
    print("N34 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
