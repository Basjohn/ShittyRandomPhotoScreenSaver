"""N3.1's proof of the native core's scene targets (Current_Plan.md item 8b, N3.1; decision D14;
``native/core/src/scene_targets.h``), through ``rendering.native``, on the harness-only scene
``native/core/python/scene_targets`` (a still item: a surface-sized ``scene`` target with an RGBA16F colour, an RGBA16F
emission and a D32F depth, Extruded Bubble's shape; an explicit-size ``ambient`` target with an RGBA8 coverage and an
RGBA16F light, Bubble's shape; a capture step between the scene's passes; a surface pass sampling both).

The module (``release/native_module``, built on GitHub) is loaded the product's way in one child process per graphics
API (OpenGL, then Vulkan on the module's own instance and devices, D6), and the Python reference in a child of its own
(an offscreen OpenGL context). No window is ever visible.

Rounds:
  parity     (each API; and the reference) every readable texture of both targets read back at dpr 1 and 1.5 and with
             the ambient light off: the scene's colour and emission, its capture's colour and nearest window depth, the
             ambient coverage and light. Analytic checks on the native frames: the captured depth is the tilted plane's
             and the nearer plane's (the nearer wins), the slack holds the clear (far plane), the pass after the capture
             changes only where the loaded depth is at or behind it (the depth is loaded across the split; a cleared
             depth would let it cover everything), colour past white is kept (the HDR intermediate), the emission pass's
             attachment is masked where a pass writes none, the light holds its clear with nothing glowing. Then rule (a):
             native OpenGL against the Python reference (``SceneTarget`` with ``depth_texture``, ``background()`` and
             ``hdr``; a GL target with the ambient owner's states); rule (b): native Vulkan against native OpenGL.
  msaa       (each API) the scene requested at 2x, 4x and 8x: the effective count reported (the count created), the
             frames repeat exactly; without partial coverage every resolve equals the single-sampled frame; with the
             nearer plane's two bands of partial coverage (gl_SampleMask) the core's nearest resolve (D14 point 10:
             the capture's depth, the depth a sampler reads, and an R32F attachment declared "nearest") is the analytic
             nearest depth; the negative control (sample 0 alone) is wrong exactly in the first band; the clamp's
             control (8 taken out: 8 drawn as 4, reported). ``QRhi::ResolveDepthStencil`` is recorded as a fact only.
  rest       (each API) nothing recorded and nothing allocated over frames at rest; control: a setting change records.
  resize     (each API) the card dragged 800 -> 1000 -> 800 px wide in 1 px steps: the scene's allocation after each
             step equals D14's rule (grown at once, shrunk only two buckets below), the reallocations counted against a
             true one-pixel buckets (resize_control), the explicit-size target never reallocated; after the
             drag the content equals a fresh item's at that size.
  retire     (each API) a program without targets releases them on a live item (counts to zero) and one with targets
             makes them again; destruction between attachment steps and actual scene-graph invalidation release the
             targets before host close; skipped edges fail the same retirement predicate; with Vulkan
             validation (synchronisation validation) through every round.
  scissor    (each API) an actual four-vertex quad at 1x and 4x: natural content viewport, deliberately enlarged
             allocation viewport with the same content scissor, then natural again. Content is drawn, colour/depth
             slack keeps its clear, captures match, and changing the viewport allocates nothing.
  cost       (each API) at 2560x1440 and 3840x2160: the surface's GPU time (the content's whole record: every target
             pass) median and p90, single-sampled and 4x (the 4x minus 1x difference bounds the resolves: choice G's
             budget, 0.3 ms at 2560x1440 and 0.6 ms at 4K); the light attachment's clear (the ambient target at 2048 x
             1152 with and without its light attachment, nothing glowing: choice F); the first frame's wall time with a
             new allocation against a steady one; the thread probe (no Python thread state on the render thread). On
             Vulkan it is the gate's synchronisation proof (audit 2, H1: its runs of consecutive multisampled records
             have no readback between them to order a resolve), so a Vulkan cost round without the validation layer
             fails.
Run alone (not in the default set):
  readback_metadata (each API) complete enumeration beyond the former fixed callback capacity, then bounded
             readbacks with unaligned content and odd mip extents. Checks normalized-UV mip metadata and byte shapes,
             subsequent readback and release; no non-base pixel parity or filtering-fringe containment claim.
  scissor_control (each API) the same enlarged viewport and quad, with UsesScissor disabled: actual colour and depth
             writes fill the slack and fail the positive predicate. Restoring scissor on the same item restores the
             frame (pipeline flags must rebuild), without reallocating targets. Controls reset in finally.
  placement_control (--apis opengl) put content at the image top; rule (a) rejects the edge reads against the unchanged
             independent Python renderer. Parity includes an aligned 512x320 scene beside 480x270 and 720x405.
  resize_control (each API) the native owner uses a true one-pixel allocation bucket, including two-pixel shrink
             hysteresis; its allocations match the independent control oracle and fail the normal 64px rule.
  partial_retire_control / invalidation_control (each API, separate runs) skip the destruction between steps or the
             scene-graph invalidation; actual held resources fail the positive round's zero-resource predicate.
  prime_control  (--apis vulkan) rule C for depth's negative control: the scene with the depth prime skipped, then with
             it, at one sample and at 4x; synchronisation validation shows read-after-write hazards on the depth load
             only where it was skipped. Then the resolves' prime (audit 2, H1): 40 consecutive 4x records with it
             skipped show write-after-write hazards on the resolves (defect B's UNDEFINED transition), none with it.
  cost_parts (each API) where the four-sample time goes at 4K: a clearing draw and plane, three passes, a colour read,
             the capture split; each at 1x and 4x.
  python_cost (the reference child, OpenGL) the Python renderer's ``SceneTarget`` on the same load at 2560x1440 and 4K,
             1x and 4x (the lead's measure for the native four-sample figure: accepted when no worse).
N5.4 (ABI 33; Waveform's five C++ boxes; ``native/core/python/waveform_primitives``), alone or together, evidence
under .artifacts/evidence/native_core/n5_4/ when run without the N3.1 rounds:
  wave_floor (each API, and the reference child) the floor scene: an exact, mipped, drawable reflection at odd sizes
             (two-output passes into its one attachment), the exact pre-pass, the RGBA16F slope map's GPU levels, the
             floor's anisotropic taps; rule (a) per texture against the Python reference, every reflection level
             against Python's glGenerateTextureMipmap (the odd-built ones reported apart), the controls (one read at
             1x, the bucketed reflection, the slope stored as RGBA8) leaving the bound, the taps against Python's
             hardware anisotropy reported (wave_sheet_<api>.png); nothing at rest; the new declarations' refusals.
  wave_limits (each API) Waveform's shape (28 passes, 9 storage images, 4 targets) admitted and built, nothing at
             rest; one pass, one image and one target past the limits refused with their reasons.
  wave_filter (each API) linear_filter_formats in the device facts, an RGBA32F storage image read linearly drawn, the
             faked device without linear 32-bit float filtering (compute_control no_float32_linear) refusing it with
             its reason, and drawing again once the control is off.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/scene_target_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds parity msaa rest resize retire cost] [--label n31_scene_targets]
Evidence: .artifacts/evidence/native_core/n3_1/<date>_<label>/ (summary.json; sheet_<api>.png). Exit 0 whenever the
harness ran; the verdict is the last printed line ("N31 VERDICT PASS" or "N31 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402
from tools import pixel_tolerance as pt  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("parity", "msaa", "rest", "resize", "retire", "scissor", "cost")
# Run on its own (its skipped phase is expected to show hazards): --apis vulkan --rounds prime_control
CONTROL_ROUNDS = ("prime_control", "cost_parts", "placement_control", "resize_control",
                  "partial_retire_control", "invalidation_control", "scissor_control", "readback_metadata")
# The Python renderer's cost on the same load (the reference child, OpenGL): --rounds python_cost
PYTHON_ROUNDS = ("python_cost",)
CHILD_TIMEOUT_S = 1500
MARGIN = 8
CARD = (480, 270)                  # the item's logical size (parity, msaa, rest, retire)
ALIGNED_CARD = (512, 320)           # no scene slack on either axis (one independent parity case)
DPRS = (1.0, 1.5)
AMBIENT = (300, 170)               # the ambient target's explicit size (parity)
REST_FRAMES = 4
HALF_ULP = 2.0 ** -10              # one float16 ulp, relative
RULE_A_LEVELS = 1                  # RGBA8 (the tie budget of D13: a NativeFragmentPass within 1 level)
RULE_A_TIE_PIXELS = 8
DEPTH_TOLERANCE = 2e-7             # N0.3 scene 2's bound
# Rules (a) and (b), judged by the shared pixel tolerance (tools/pixel_tolerance.py, D12 "The pixel tolerance"):
# an RGBA8 texture may sit 1 level off only where the reference is translucent (its alpha strictly between 0 and 255);
# a float texture's unit is its own rounding (one float16 ulp of the larger value, or the depth bound), which every
# texel may reach (each renderer rounds its fp32 value into the format). Past that, rule (a) admits RULE_A_TIE_PIXELS
# texels a texture at 2 units at most, isolated or on an edge (measured: 3 texels of scene.colour at 1.41 ulps, dpr 1),
# rule (b) none.
SCENE_RULE_A = pt.Tolerance("scene target, rule (a)", masked_level=1, tie_pixels=RULE_A_TIE_PIXELS)
SCENE_RULE_B = pt.Tolerance("scene target, rule (b)", masked_level=1)
DRAG = (800, 1000, 1)              # the resize round's widths (start, end, step); its card is 400 px high
DRAG_HEIGHT = 400
COST_HOSTS = ((2560, 1440), (3840, 2160))
COST_AMBIENT = (2048, 1152)
COST_FRAMES = 240                   # the records timed at least
COST_MIN_SAMPLES = 30               # Qt's OpenGL backend reports a GPU time only for frames whose query was ready
COST_MAX_FRAMES = 1200              # ... so the records go on until this many times arrived, at most this many records
RESOLVE_CONTROL_FRAMES = 40         # prime_control's consecutive 4x records per phase (audit 2, H1)
PYTHON_COST_FRAMES = 120            # the Python path's timed frames per size and count (python_cost)
RESOLVE_BUDGET_MS = {(2560, 1440): 0.3, (3840, 2160): 0.6}   # choice G (D7's budgets, until the lead sets another)
CLEAR_BUDGET_MS = 0.05             # choice F: "negligible" (the lead's word), stated here as 0.05 ms at 2048 x 1152
_ALLOWED_ENV: set[str] = set()


# --------------------------------------------------------------------------------------------------- the scene

def _scene_module():
    import scene_targets

    return scene_targets


SCENE_QML = b"""import QtQuick
Rectangle {
    color: "#000000"
    Item { objectName: "contentHost"; x: %(margin)d; y: %(margin)d; width: 4; height: 4 }
}
""" % {b"margin": MARGIN}


class Scene:
    """An opaque black display with one still item drawing the harness scene, at (MARGIN, MARGIN)."""

    def __init__(self, core, engine, host, card: tuple[int, int], dpr: float, packs: dict, *, samples: int = 1,
                 ambient: tuple[int, int] = AMBIENT, glow: float = 1.0, passes=None, targets=None,
                 settings: dict | None = None) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        st = _scene_module()
        self.host = host
        self.card = card
        self.dpr = float(dpr)
        self.component = QQmlComponent(engine)
        self.component.setData(SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        self.content = self.root.findChild(QQuickItem, "contentHost")
        host.set_content(self.root)
        self.mode = core.mode(self.content)
        self.mode.composite.set(rect=[0.0, 0.0, float(card[0]), float(card[1])], coverage=None, quarters=0,
                                visible=True)
        self.mode.still()
        values = settings if settings is not None else dict(st.settings(ambient_size=ambient), u_glow=float(glow))
        self.mode.program(passes if passes is not None else st.passes(packs),
                          values, targets=targets if targets is not None else st.targets(samples=samples,
                                                                                         ambient_size=ambient))
        self.mode.card(_card(card, self.dpr))

    def resize(self, card: tuple[int, int]) -> None:
        self.card = card
        self.mode.composite.set(rect=[0.0, 0.0, float(card[0]), float(card[1])])
        self.mode.card(_card(card, self.dpr))

    def targets(self, app, frames: int = 3, timeout_s: float = 10.0) -> dict:
        """Every readable texture of the item's targets as this record leaves them: name -> numpy array (rows top
        first) with its content size and allocation."""
        self.mode.read_targets()
        self.mode.update()
        deadline = time.monotonic() + timeout_s
        while True:
            self.host.frames(1)
            pixels = self.mode.target_pixels()
            if pixels is not None or time.monotonic() > deadline:
                break
        if pixels is None:
            raise RuntimeError("the target readback did not complete")
        return {p["name"]: _array(p) for p in pixels}

    def close(self, app) -> None:
        self.mode.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


def _card(card: tuple[int, int], dpr: float) -> dict:
    import probe_rings

    return probe_rings.harness_card(card, dpr)


def _array(p: dict):
    import numpy as np

    width, height = p["size"]
    data = p["data"]
    if p["format"] == "rgba8":
        array = np.frombuffer(data, np.uint8)[:width * height * 4].reshape(height, width, 4)
    elif p["format"] == "rgba16f":
        array = np.frombuffer(data, np.float16)[:width * height * 4].reshape(height, width, 4)
    elif p["format"] == "r32f":
        array = np.frombuffer(data, np.float32)[:width * height].reshape(height, width)
    else:                                            # r16f
        array = np.frombuffer(data, np.float16)[:width * height].reshape(height, width)
    return {"array": array.copy(), "content": tuple(p["content"]), "size": (width, height), "format": p["format"],
            "samples": p["samples"]}


def _pixels(card: tuple[int, int], dpr: float) -> tuple[int, int]:
    return (int(round(card[0] * dpr)), int(round(card[1] * dpr)))


def _host_size(cards, dprs=(1.0,)) -> tuple[int, int]:
    return (int(math.ceil((max(c[0] for c in cards) + 2 * MARGIN) * max(dprs))),
            int(math.ceil((max(c[1] for c in cards) + 2 * MARGIN) * max(dprs))))


# --------------------------------------------------------------------------------------------------- comparisons

def compare(a: dict, b: dict) -> dict:
    """Two readbacks of one texture: shape, exact equality, the largest difference (levels for RGBA8, values else),
    pixels past the tolerance (one level, one float16 ulp, the depth bound)."""
    import numpy as np

    x, y = a["array"], b["array"]
    if x.shape != y.shape:
        return {"shape": [list(x.shape), list(y.shape)], "exact": False, "past": -1, "max": None}
    if a["format"] == "rgba8":
        diff = np.abs(x.astype(np.int16) - y.astype(np.int16))
        past = diff.reshape(diff.shape[0], diff.shape[1], -1).max(axis=2) > RULE_A_LEVELS
        return {"exact": bool((diff == 0).all()), "max": int(diff.max()), "past": int(past.sum())}
    fx, fy = x.astype(np.float64), y.astype(np.float64)
    diff = np.abs(fx - fy)
    if a["format"] == "r32f":
        tolerance = np.full(diff.shape, DEPTH_TOLERANCE)
    else:
        tolerance = np.maximum(np.abs(fx), np.abs(fy)) * HALF_ULP + 1e-7
    past = diff > tolerance
    if past.ndim == 3:
        past = past.any(axis=2)
    return {"exact": bool((diff == 0).all()), "max": float(diff.max()), "past": int(past.sum())}


def judged(candidate: dict, reference: dict, tolerance) -> dict:
    """``tolerance`` (``SCENE_RULE_A`` or ``SCENE_RULE_B``) over two readbacks of one texture: RGBA8 in levels with the
    reference's translucent texels as the mask; a float texture in its own units (``compare``'s tolerance), every texel
    in the mask."""
    import numpy as np

    x, y = candidate["array"], reference["array"]
    if x.shape != y.shape:
        return {"pass": False, "reasons": ["shapes differ"], "differing": -1}
    if candidate["format"] == "rgba8":
        return pt.judge(x, y, tolerance, mask=pt.translucent_by_alpha(y))
    fx, fy = x.astype(np.float64), y.astype(np.float64)
    if candidate["format"] == "r32f":
        units = np.abs(fx - fy) / DEPTH_TOLERANCE
    else:
        units = np.abs(fx - fy) / (np.maximum(np.abs(fx), np.abs(fy)) * HALF_ULP + 1e-7)
    delta = np.ceil(units)
    if delta.ndim == 3:
        delta = delta.max(axis=2)
    edges = pt.content_edges(fy * 255.0, tolerance.edge_contrast)
    return pt.judge_delta(delta.astype(np.int64), tolerance, mask=np.ones(delta.shape, bool), edges=edges)


def _content(entry: dict):
    """The content region of a readback: image rows [H-h, H), columns [0, w) (D14 point 2)."""
    width, height = entry["content"]
    rows = entry["array"].shape[0]
    return entry["array"][rows - height:, :width]


def readback_metadata_contract(pixels: list[dict], names, allocation, content) -> dict:
    """Exact RGBA8 mip enumeration and nominal bottom-anchored content metadata, not pixel/filter validity."""
    levels = max(allocation).bit_length()
    expected = {}
    for name in names:
        for level in range(levels):
            size = tuple(max(1, dimension >> level) for dimension in allocation)
            projected = tuple(min(size[axis], (content[axis] * size[axis] + allocation[axis] - 1)
                                  // allocation[axis]) for axis in range(2))
            expected[name + (f"@{level}" if level else "")] = (level, size, projected)
    well_formed = isinstance(pixels, list) and all(isinstance(p, dict) and isinstance(p.get("name"), str)
                                                  for p in pixels)
    actual = {p["name"]: p for p in pixels} if well_formed else {}
    checks = {"complete_unique_enumeration": bool(expected) and well_formed and len(pixels) == len(expected)
              and len(actual) == len(pixels) and actual.keys() == expected.keys(),
              "level_relative_size_and_normalized_content": True, "rgba8_byte_shapes": True,
              "base_metadata_preserved": True, "nominal_bottom_anchored_rects_in_bounds": True}
    facts = {"expected_entries": len(expected), "actual_entries": len(pixels) if well_formed else None,
             "levels_per_attachment": levels, "allocation": allocation, "content": content,
             "missing_names": sorted(expected.keys() - actual.keys()),
             "unexpected_names": sorted(actual.keys() - expected.keys()), "entries": []}
    for name, (level, size, projected) in expected.items():
        p = actual.get(name, {})
        metadata_ok = (p.get("level") == level and type(p.get("level")) is int
                       and p.get("size") in (size, list(size)) and p.get("content") in (projected, list(projected)))
        checks["level_relative_size_and_normalized_content"] &= metadata_ok
        data = p.get("data")
        shape_ok = (p.get("format") == "rgba8" and p.get("samples") == 1
                    and isinstance(data, (bytes, bytearray, memoryview)) and len(data) == size[0] * size[1] * 4)
        checks["rgba8_byte_shapes"] &= shape_ok
        if level == 0:
            checks["base_metadata_preserved"] &= metadata_ok
        # This describes the nominal slice only; no claim that mip filtering cannot bleed beyond it.
        rows = (size[1] - projected[1], size[1])
        checks["nominal_bottom_anchored_rects_in_bounds"] &= (metadata_ok and 0 <= rows[0] < rows[1]
                                                            and 0 < projected[0] <= size[0])
        facts["entries"].append({"name": name, "level": p.get("level"), "size": p.get("size"),
                                 "content": p.get("content"), "content_image_rows": rows,
                                 "content_image_columns": (0, projected[0]),
                                 "format": p.get("format"), "samples": p.get("samples"),
                                 "data_bytes": len(data) if isinstance(data, (bytes, bytearray, memoryview)) else None})
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def analytic(frames: dict, settings: dict) -> dict:
    """The native frame's own checks (see the module notes)."""
    import numpy as np

    checks, facts = {}, {}
    depth = frames["scene.capture_depth"]
    width, height = depth["content"]
    grid_x = (np.arange(width) + 0.5) / width
    grid_up = 1.0 - (np.arange(height) + 0.5) / height              # vUv.y per content row (top first)
    vx, vy = np.meshgrid(grid_x, grid_up)
    plane = settings["u_near_depth"] + (settings["u_far_depth"] - settings["u_near_depth"]) * vx
    nearer = (vy <= 0.5) & (settings["u_nearer_depth"] < plane)
    expected = np.where(nearer, settings["u_nearer_depth"], plane)
    captured = _content(depth).astype(np.float64)
    error = np.abs(captured - expected)
    checks["captured_depth_is_the_planes_and_the_nearer_wins"] = bool(error.max() <= 1e-5)
    facts["captured_depth_max_error"] = float(error.max())
    whole = depth["array"]
    slack = np.ones(whole.shape, bool)
    slack[whole.shape[0] - height:, :width] = False
    checks["slack_holds_the_far_plane"] = bool(not slack.any() or (whole[slack] == 1.0).all())
    facts["slack_texels"] = int(slack.sum())
    colour = _content(frames["scene.colour"]).astype(np.float64)
    before = _content(frames["scene.capture_colour"]).astype(np.float64)
    changed = np.abs(colour - before).max(axis=2) > 1e-6
    behind = captured > settings["u_after_depth"] + 1e-4
    ahead = captured < settings["u_after_depth"] - 1e-4
    checks["after_changes_only_at_or_behind_the_loaded_depth"] = bool(
        ahead.any() and behind.any() and not changed[ahead].any() and changed[behind].all())
    facts["after"] = {"ahead": int(ahead.sum()), "behind": int(behind.sum()),
                      "changed_ahead": int(changed[ahead].sum()), "changed_behind": int(changed[behind].sum())}
    checks["colour_past_white_kept"] = bool(before[..., :2].max() > 1.5)
    facts["colour_max"] = float(before[..., :2].max())
    emission = _content(frames["scene.emission"]).astype(np.float64)
    expected_emission = np.stack([settings["u_emission"] * vy, np.zeros_like(vy), settings["u_emission"] * (1.0 - vy),
                                  np.ones_like(vy)], axis=2)
    checks["emission_masked_where_a_pass_writes_none"] = bool(np.abs(emission - expected_emission).max() <= 2e-3)
    facts["emission_max_error"] = float(np.abs(emission - expected_emission).max())
    cover = _content(frames["ambient.coverage"])
    light = _content(frames["ambient.light"]).astype(np.float64)
    if settings["u_glow"] > 0.0:
        checks["ambient_coverage_and_light_drawn"] = bool(cover[..., 3].max() > 200 and light[..., :3].max() > 1.0)
    else:
        checks["light_holds_its_clear_when_nothing_glows"] = bool((light == 0.0).all() and cover[..., 3].max() > 200)
    facts["light_max"] = float(light[..., :3].max())
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the rounds

def _readback_metadata_program(packs: dict, target_count: int):
    from rendering.native.mode import ModePass, ModeTarget, PassSampler, TargetAttachment

    targets = tuple(ModeTarget(f"readback{index}", tuple(TargetAttachment(f"colour{channel}", "rgba8")
                                                      for channel in range(4)), mips=True)
                    for index in range(target_count))
    passes = tuple(ModePass(f"write{index}", packs["readback_metadata"], "replace", target=target.name)
                   for index, target in enumerate(targets))
    passes += tuple(ModePass(f"show{index}", packs["show_colour"], "replace",
                            samplers=(PassSampler("u_scene", f"{target.name}.{target.colour[0].name}", "nearest"),))
                    for index, target in enumerate(targets))
    return passes, targets


def _metadata_readback(scene, timeout_s: float = 10.0) -> list[dict]:
    """Keep the list intact: converting to name->array would hide duplicate callbacks."""
    scene.mode.read_targets()
    scene.mode.update()
    deadline = time.monotonic() + timeout_s
    while True:
        scene.host.frames(1)
        pixels = scene.mode.target_pixels()
        if pixels is not None:
            return pixels
        if time.monotonic() > deadline:
            raise RuntimeError("metadata readback did not complete within its bound")


def round_readback_metadata(core, engine, app, packs: dict, folder: Path) -> dict:
    """Audit 6: metadata/completeness beyond the old fixed callback capacity, never non-base pixel parity."""
    import probe_rings
    from rendering.native.scene_targets import next_allocation

    packs = dict(packs, readback_metadata=probe_rings.bake(_scene_module().shader_text("readback_metadata.frag"),
                                                         "readback_metadata.frag", folder))
    cases = (("large", (1024, 1024), 4), ("bounded_after_large", (83, 47), 1),
             ("odd_mip_extents", (321, 257), 1))
    host = core.hidden_host(*_host_size([case[1] for case in cases]))
    checks, facts = {}, {"scope": "metadata/completeness only; non-base mips not generated or pixel-judged"}
    try:
        for label, card, target_count in cases:
            passes, targets = _readback_metadata_program(packs, target_count)
            names = tuple(f"{target.name}.{attachment.name}" for target in targets for attachment in target.colour)
            allocation, _ = next_allocation((0, 0), card)
            scene = Scene(core, engine, host, card, 1.0, packs, passes=passes, targets=targets, settings={})
            try:
                result = readback_metadata_contract(_metadata_readback(scene), names, allocation, card)
                facts[label] = result["facts"]
                checks.update({f"{label}_{key}": value for key, value in result["checks"].items()})
                live = core.composite_live()
                facts[label]["readbacks_pending_after_completion"] = live.get("scene_target_readbacks")
                checks[f"{label}_callbacks_complete"] = live.get("scene_target_readbacks") == 0
                if label == "bounded_after_large":
                    repeated = readback_metadata_contract(_metadata_readback(scene), names, allocation, card)
                    checks[f"{label}_subsequent_readback_succeeds"] = repeated["pass"]
                    facts[label]["subsequent_readback"] = repeated["facts"]
                    checks[f"{label}_subsequent_callbacks_complete"] = core.composite_live().get(
                        "scene_target_readbacks") == 0
            finally:
                scene.close(app)
                host.frames(3)
                host_check._flush_deletes(app)
            gone = core.composite_live()
            facts[label]["released"] = {key: gone.get(key) for key in
                ("scene_targets", "scene_target_textures", "scene_target_bytes", "scene_target_readbacks",
                 "mode_resources", "mode_sources")}
            checks[f"{label}_resources_released"] = _targets_retired(gone) and gone.get("mode_sources") == 0
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


PARITY_CASES = (("dpr1", CARD, 1.0, 1.0), ("dpr1.5", CARD, 1.5, 1.0),
                ("aligned", ALIGNED_CARD, 1.0, 1.0), ("glow_off", CARD, 1.0, 0.0))


def _save(out: Path, name: str, frames: dict) -> None:
    import numpy as np

    arrays = {}
    for case, textures in frames.items():
        for texture, entry in textures.items():
            key = f"{case}|{texture}"
            arrays[key] = entry["array"]
            arrays[key + "|meta"] = np.array([*entry["content"], *entry["size"], entry["samples"]], np.int32)
            arrays[key + "|format"] = np.array(entry["format"])
    np.savez_compressed(_work(out) / f"{name}.npz", **arrays)


def _load(out: Path, name: str) -> dict:
    import numpy as np

    path = _work(out) / f"{name}.npz"
    if not path.exists():
        return {}
    data = np.load(path)
    frames: dict = {}
    for key in data.files:
        if key.endswith("|meta") or key.endswith("|format"):
            continue
        case, texture = key.split("|")
        meta = data[key + "|meta"]
        frames.setdefault(case, {})[texture] = {"array": data[key], "content": (int(meta[0]), int(meta[1])),
                                                "size": (int(meta[2]), int(meta[3])), "samples": int(meta[4]),
                                                "format": str(data[key + "|format"])}
    return frames


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def round_parity(core, engine, app, api: str, packs: dict, out: Path, *, top_control: bool = False) -> dict:
    st = _scene_module()
    host = core.hidden_host(*_host_size([CARD, ALIGNED_CARD], DPRS))
    checks, facts, frames = {}, {}, {}
    try:
        for case, card, dpr, glow in PARITY_CASES:
            host.set_device_pixel_ratio(dpr)
            scene = Scene(core, engine, host, card, dpr, packs, glow=glow)
            try:
                frames[case] = scene.targets(app)
                state = scene.mode.state()
                facts[f"{case}_state"] = state.get("scene_targets")
                result = analytic(frames[case], dict(st.settings(ambient_size=AMBIENT), u_glow=glow))
                facts[f"{case}_analytic"] = result
                checks[f"{case}_analytic"] = result["pass"]
                content = frames[case]["scene.colour"]["content"]
                checks[f"{case}_scene_content_is_the_surface"] = content == _pixels(card, dpr)
                if case == "aligned":
                    checks["aligned_scene_has_no_slack"] = tuple(frames[case]["scene.colour"]["size"]) == content
                checks[f"{case}_ambient_content_is_its_explicit_size"] = (
                    frames[case]["ambient.coverage"]["content"] == AMBIENT)
            finally:
                scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
        host.set_device_pixel_ratio(1.0)
        if not top_control:
            result = _previous_frame(core, engine, app, host, packs)
            facts["previous_frame"] = result["facts"]
            checks.update({f"previous_frame_{k}": v for k, v in result["checks"].items()})
    finally:
        host.close()
        host_check._flush_deletes(app)
    _save(out, "placement_control" if top_control else f"parity_{api}", frames)
    _sheet(out, api, frames)
    # The broken form's pixel verdict belongs to the parent, against its independent Python child.
    return {"pass": True if top_control else all(checks.values()), "checks": {} if top_control else checks,
            "facts": {**facts, **({"broken_analytic_checks": checks} if top_control else {})}}


def scissor_contract(frames: dict, requested_samples: int = 1) -> dict:
    """One predicate for guarded frames and their broken control; placement is the independent image-row rule."""
    import numpy as np

    colour, capture, depth = (frames[name] for name in ("scene.colour", "scene.capture_colour", "scene.capture_depth"))
    width, height = colour["content"]
    pixels = colour["array"]
    slack = np.ones(pixels.shape[:2], bool)
    slack[pixels.shape[0] - height:, :width] = False
    quad = np.array([255, 0, 255, 255], dtype=np.uint8)
    checks = {
        "actual_sample_count_is_requested": all(entry.get("samples") == requested_samples
                                                for entry in (colour, capture, depth)),
        "slack_on_both_axes": pixels.shape[1] > width > 0 and pixels.shape[0] > height > 0,
        "content_is_the_quad": bool((_content(colour) == quad).all()),
        "content_depth_is_the_quad": bool((_content(depth) == 0.25).all()),
        "slack_colour_keeps_clear": bool(slack.any() and (pixels[slack] == 0).all()),
        "slack_depth_keeps_far_plane": bool(slack.any() and (depth["array"][slack] == 1.0).all()),
        "capture_is_the_scene": bool(np.array_equal(pixels, capture["array"])),
    }
    written_colour = np.all(pixels[slack] == quad, axis=-1)
    written_depth = depth["array"][slack] == 0.25
    return {"pass": all(checks.values()), "checks": checks,
            "facts": {"allocation": colour["size"], "content": colour["content"],
                      "requested_samples": requested_samples,
                      "actual_samples": {key: frames[key].get("samples") for key in frames},
                      "slack_texels": int(slack.sum()), "slack_quad_colour_texels": int(written_colour.sum()),
                      "slack_quad_depth_texels": int(written_depth.sum())}}


def _scissor_program(folder: Path, samples: int):
    import probe_rings
    from rendering.native.mode import CapturePass, ModePass, ModeTarget, PassGeometry, TargetAttachment

    st = _scene_module()
    vertex = probe_rings.bake(st.shader_text("scissor_quad.vert"), "scissor_quad.vert", folder)
    fragment = probe_rings.bake(st.shader_text("scissor_quad.frag"), "scissor_quad.frag", folder)
    quad = ModePass("quad", fragment, "replace", target="scene", depth_test="always", depth_write=True,
                    geometry=PassGeometry(vertex, topology="triangle_strip", vertices=4))
    return (quad, CapturePass("background", "scene")), (
        ModeTarget("scene", (TargetAttachment("colour", "rgba8"),), depth=True, samples=samples),)


def round_scissor(core, engine, app, api: str, folder: Path, out: Path, *, skip_control: bool = False) -> dict:
    """The enlarged viewport is explicit harness instrumentation, not a claim that clipped triangles exceed it."""
    import numpy as np

    card = (83, 47)             # slack on both axes; deliberately independent of authorable settings
    host = core.hidden_host(*_host_size([card]))
    checks, facts, sheet = {}, {}, {}
    try:
        for samples in (1, 4):
            core.scene_target_control("oversize_viewport", 0)
            core.scene_target_control("skip_scissor", 0)
            passes, targets = _scissor_program(folder, samples)
            scene = Scene(core, engine, host, card, 1.0, {}, passes=passes, targets=targets, settings={})
            try:
                natural = scene.targets(app)
                initial = core.composite_live()
                natural_result = scissor_contract(natural, samples)
                checks[f"x{samples}_natural"] = natural_result["pass"]
                facts[f"x{samples}_natural"] = natural_result
                core.scene_target_control("oversize_viewport", 1)
                if skip_control:
                    core.scene_target_control("skip_scissor", 1)
                enlarged = scene.targets(app)
                judged = scissor_contract(enlarged, samples)
                facts[f"x{samples}_enlarged"] = judged
                checks[f"x{samples}_enlarged_uses_requested_samples"] = judged["checks"][
                    "actual_sample_count_is_requested"]
                sheet[f"x{samples}_natural"] = natural
                sheet[f"x{samples}_enlarged_{'unguarded' if skip_control else 'guarded'}"] = enlarged
                if skip_control:
                    f = judged["facts"]
                    checks[f"x{samples}_positive_predicate_rejects_missing_scissor"] = not judged["pass"]
                    checks[f"x{samples}_quad_actually_writes_all_colour_and_depth_slack"] = (
                        f["slack_texels"] > 0
                        and f["slack_quad_colour_texels"] == f["slack_quad_depth_texels"] == f["slack_texels"])
                    # Same item, same program: restoring the flag must rebuild the pipeline before its next draw.
                    core.scene_target_control("skip_scissor", 0)
                    guarded = scene.targets(app)
                    guarded_result = scissor_contract(guarded, samples)
                    checks[f"x{samples}_restored_scissor"] = guarded_result["pass"]
                    facts[f"x{samples}_restored_scissor"] = guarded_result
                    sheet[f"x{samples}_restored_scissor"] = guarded
                else:
                    checks[f"x{samples}_enlarged_viewport_keeps_slack_clear"] = judged["pass"]
                core.scene_target_control("oversize_viewport", 0)
                restored = scene.targets(app)
                restored_result = scissor_contract(restored, samples)
                checks[f"x{samples}_restored_natural"] = restored_result["pass"]
                facts[f"x{samples}_restored_natural"] = restored_result
                checks[f"x{samples}_natural_frame_restored_exactly"] = all(
                    np.array_equal(natural[key]["array"], restored[key]["array"]) for key in natural)
                final = core.composite_live()
                checks[f"x{samples}_targets_not_reallocated"] = all(
                    initial[key] == final[key] for key in ("scene_target_allocations", "scene_target_steps",
                                                           "scene_target_bytes", "scene_target_textures"))
                facts[f"x{samples}_allocation_counts"] = {
                    key: [initial[key], final[key]] for key in ("scene_target_allocations", "scene_target_steps")}
            finally:
                scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
    finally:
        core.scene_target_control("oversize_viewport", 0)
        core.scene_target_control("skip_scissor", 0)
        host.close()
        host_check._flush_deletes(app)
    _scissor_sheet(out, api, sheet, control=skip_control)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _scissor_sheet(out: Path, api: str, frames: dict, *, control: bool) -> None:
    """One labelled sheet of full allocations; raw frames are not retained."""
    from PIL import Image, ImageDraw
    import numpy as np

    rows = []
    for name, textures in frames.items():
        row = Image.new("RGB", (512, 154), "#202020")
        ImageDraw.Draw(row).text((4, 3), name, fill="white")
        for index, key in enumerate(("scene.colour", "scene.capture_depth")):
            pixels = textures[key]["array"]
            if pixels.ndim == 2:
                pixels = np.repeat((pixels[..., None] * 255).astype(np.uint8), 3, axis=-1)
            tile = Image.fromarray(pixels[..., :3]).resize((256, 128), Image.Resampling.NEAREST)
            row.paste(tile, (index * 256, 24))
        rows.append(row)
    sheet = Image.new("RGB", (512, 154 * len(rows)))
    for index, row in enumerate(rows):
        sheet.paste(row, (0, index * 154))
    sheet.save(out / f"scissor_{'control_' if control else ''}{api}.png")


def _previous_frame(core, engine, app, host, packs: dict) -> dict:
    """Audit 2, M4: a pass sampling a target before any pass of the frame drew it. Refused unless the target declares
    ``previous_frame``, and refused when that target is multisampled. Declared at one sample, it reads the frame
    before: the probe pass writes what it sampled into a target of its own, so the proof is the pass's own read and
    never a readback's forced resolve. Three readback records, the nearer plane's colour changed between each: the
    probe of each equals the scene of the record before (clamped as the probe writes it) and, the control, differs
    from its own record's scene."""
    import numpy as np

    st = _scene_module()
    checks, facts = {}, {}

    def refused(passes, targets) -> str:
        try:
            core.mode_program_layout(passes, targets)
        except ValueError as exc:
            return str(exc)
        return ""

    undeclared = refused(*st.previous_frame_program(packs, declared=False)[:2])
    multisampled = refused(*st.previous_frame_program(packs, samples=4)[:2])
    admitted = refused(*st.previous_frame_program(packs)[:2])
    facts["refusals"] = {"undeclared": undeclared, "declared_at_4x": multisampled, "declared_at_1x": admitted}
    checks["undeclared_read_before_any_draw_refused"] = "before any pass of the frame drew" in undeclared
    checks["declared_at_4x_refused"] = "only single-sampled" in multisampled
    checks["declared_at_1x_admitted"] = admitted == ""
    passes, targets, values = st.previous_frame_program(packs)
    colours = ([0.1, 0.6, 0.9, 1.0], [0.6, 0.2, 0.3, 1.0], [0.1, 0.6, 0.9, 1.0])
    scene = Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets,
                  settings=dict(values, u_nearer_colour=colours[0]))
    reads = []
    try:
        reads.append(scene.targets(app))
        for colour in colours[1:]:
            scene.mode.settings(dict(values, u_nearer_colour=colour))
            reads.append(scene.targets(app))
    finally:
        scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)

    def rgb(entry):
        return np.clip(_content(entry).astype(np.float32)[..., :3], 0.0, 1.0)

    equal, control = [], []
    for before, now in zip(reads, reads[1:]):
        probe = _content(now["probe.colour"]).astype(np.float32)[..., :3]
        equal.append(float(np.abs(probe - rgb(before["scene.colour"])).max()))
        control.append(int((np.abs(probe - rgb(now["scene.colour"])).max(axis=2) > 1e-3).sum()))
    facts["probe_minus_the_scene_before_max"] = equal
    facts["probe_pixels_off_its_own_records_scene"] = control
    checks["declared_at_1x_reads_the_frame_before"] = all(e == 0.0 for e in equal)
    checks["control_the_frames_differ"] = all(c > 0 for c in control)
    return {"checks": checks, "facts": facts}


MASK_BAND = 0.08                   # D14 point 10's proof: each partial-coverage band's height (vUv)
MSAA_COUNTS = (2, 4, 8)


def _nearest_expected(entry: dict, settings: dict, band: float):
    """D14 point 10: the nearest window depth each content pixel must resolve to (analytic): the nearer plane where a
    sample holds it and it is nearer (its half and, with ``band``, both partial-coverage bands), else the tilted
    plane. Also the rows judged (rows whose centre lies within one row of an edge are left out) and the first band's
    informative pixels (every sample but 0 covered, the nearer plane nearer: what sample 0 alone gets wrong)."""
    import numpy as np

    width, height = entry["content"]
    vx = (np.arange(width) + 0.5) / width
    vy = 1.0 - (np.arange(height) + 0.5) / height                 # vUv.y per content row (top first)
    plane = np.repeat((settings["u_near_depth"]
                       + (settings["u_far_depth"] - settings["u_near_depth"]) * vx)[None, :], height, axis=0)
    covered = (vy <= 0.5 + 2.0 * band)[:, None]
    expected = np.where(covered, np.minimum(plane, settings["u_nearer_depth"]), plane)
    guard = np.ones(height, bool)
    for edge in [0.5] + ([0.5 + band, 0.5 + 2.0 * band] if band > 0 else []):
        guard &= np.abs(vy - edge) > 1.0 / height
    first_band = ((vy > 0.5) & (vy <= 0.5 + band))[:, None] & (settings["u_nearer_depth"] < plane)
    return expected, guard, first_band


def _depth_error(entry: dict, expected, guard) -> float:
    import numpy as np

    got = _content(entry).astype(np.float64)
    return float(np.abs(got - expected)[guard].max())


def round_msaa(core, engine, app, api: str, packs: dict) -> dict:
    """The multisampled scene (D14 points 7, 8 and 10): the clamp and the count created; without partial coverage the
    resolves equal the single-sampled frame (every sample of a pixel is the same); with the nearer plane's two bands
    of partial coverage the nearest resolve (the capture's depth and the depth a sampler reads) is the analytic nearest
    depth, by means (a) (the multisampled D32F read per sample) and (b) (an R32F attachment declared "nearest"); the
    negative control (sample 0 alone) is wrong exactly in the first band; the clamp's control."""
    st = _scene_module()
    host = core.hidden_host(*_host_size([CARD]))
    checks, facts = {}, {}
    base = st.settings(ambient_size=AMBIENT)

    def run(samples: int, band: float, lin: bool = False):
        if lin:
            passes, targets, values = st.lin_program(packs, samples=samples, mask_band=band)
            scene = Scene(core, engine, host, CARD, 1.0, packs, passes=passes, targets=targets, settings=values)
            changed = dict(values, u_far_depth=values["u_far_depth"] + 0.01)
        else:
            values = dict(base, u_mask_band=float(band))
            scene = Scene(core, engine, host, CARD, 1.0, packs, samples=samples, settings=values)
            changed = dict(values, u_hdr_gain=2.4)
        try:
            first = scene.targets(app)
            scene.mode.settings(changed)
            scene.targets(app)
            scene.mode.settings(values)
            second = scene.targets(app)
            state = scene.mode.state()["scene_targets"]
        finally:
            scene.close(app)
            host.frames(2)
            host_check._flush_deletes(app)
        return first, second, state, values

    try:
        single, _second, _state, _values = run(1, 0.0)
        for samples in MSAA_COUNTS:
            label = f"x{samples}"
            first, second, state, _values = run(samples, 0.0)
            target = state["targets"][0]
            facts[label] = {"requested": target["requested_samples"], "effective": target["effective_samples"],
                            "supported": state["supported_samples"],
                            "resolve_depth_stencil": state["resolve_depth_stencil"]}
            checks[f"{label}_effective_is_the_clamp"] = target["effective_samples"] == max(
                [c for c in state["supported_samples"] if c <= samples] or [1])
            # QRhi rounds an unsupported count UP silently (research N3 Q1): the core hands it only a count in its own
            # supported list, so the count reported is the count created.
            checks[f"{label}_effective_is_one_qrhi_lists"] = (target["effective_samples"] == 1
                                                              or target["effective_samples"]
                                                              in state["supported_samples"])
            checks[f"{label}_repeats_exactly"] = all(compare(first[k], second[k])["exact"] for k in first)
            # No partial coverage: every sample of a pixel holds the same values, so every resolve (QRhi's average,
            # the core's nearest) equals the single-sampled frame.
            same = {key: compare(single[key], first[key]) for key in ("scene.colour", "scene.capture_colour",
                                                                       "scene.capture_depth")}
            same["scene.depth"] = compare(single["scene.capture_depth"], first["scene.depth"]) \
                if "scene.depth" in first else {"past": -1}
            facts[label]["without_partial_coverage"] = same
            checks[f"{label}_equals_single_sampled_without_partial_coverage"] = all(
                c.get("past") == 0 for c in same.values())
            # Partial coverage: the nearest resolve against the analytic depth, means (a) and (b).
            banded, _second, _state, _values = run(samples, MASK_BAND)
            expected, guard, first_band = _nearest_expected(banded["scene.capture_depth"], base, MASK_BAND)
            errors = {key: _depth_error(banded[key], expected, guard) for key in ("scene.capture_depth",
                                                                                  "scene.depth")}
            lin, _second, _state, lin_values = run(samples, MASK_BAND, lin=True)
            lin_expected, lin_guard, _band = _nearest_expected(lin["lin.lin"], lin_values, MASK_BAND)
            errors.update({key: _depth_error(lin[key], lin_expected, lin_guard) for key in ("lin.lin", "lin.depth")})
            facts[label]["nearest_max_error"] = errors
            facts[label]["first_band_pixels"] = int(first_band[guard].sum())
            checks[f"{label}_nearest_is_the_analytic_nearest_depth_a_and_b"] = (
                all(e <= DEPTH_TOLERANCE for e in errors.values()) and int(first_band[guard].sum()) > 0)
        # The negative control: sample 0 alone, wrong exactly where the first band left sample 0 on the far plane.
        import numpy as np

        core.scene_nearest_first_sample_control(True)
        try:
            control, _second, state, _values = run(4, MASK_BAND)
        finally:
            core.scene_nearest_first_sample_control(False)
        expected, guard, first_band = _nearest_expected(control["scene.capture_depth"], base, MASK_BAND)
        wrong = np.abs(_content(control["scene.capture_depth"]).astype(np.float64) - expected) > DEPTH_TOLERANCE
        rows = guard[:, None] & np.ones_like(wrong)
        facts["control_sample_0"] = {"wrong_pixels": int(wrong[rows].sum()),
                                     "first_band_pixels": int(first_band[rows].sum()),
                                     "control_reported": bool(state.get("nearest_first_sample_control"))}
        checks["control_sample_0_is_wrong_exactly_in_the_first_band"] = (
            bool(state.get("nearest_first_sample_control")) and int(first_band[rows].sum()) > 0
            and bool((wrong[rows] == first_band[rows]).all()))
        # The clamp's control: 8 taken out of the supported set.
        core.scene_sample_counts_control([8])
        try:
            scene = Scene(core, engine, host, CARD, 1.0, packs, samples=8)
            try:
                scene.targets(app)
                state = scene.mode.state()["scene_targets"]
            finally:
                scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
        finally:
            core.scene_sample_counts_control([])
        target = state["targets"][0]
        facts["clamp_control"] = {"supported": state["supported_samples"], "removed": state["removed_samples"],
                                  "effective": target["effective_samples"]}
        checks["control_8_taken_out_draws_as_4_and_says_so"] = (8 not in state["supported_samples"]
                                                                 and state["removed_samples"] == [8]
                                                                 and target["effective_samples"] == 4)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_rest(core, engine, app, packs: dict) -> dict:
    host = core.hidden_host(*_host_size([CARD]))
    try:
        scene = Scene(core, engine, host, CARD, 1.0, packs)
        try:
            scene.targets(app)
            host.frames(2)
            before, live_before = scene.mode.state(), core.composite_live()
            host.frames(REST_FRAMES)
            scene.mode.update()
            host.frames(REST_FRAMES)
            after, live_after = scene.mode.state(), core.composite_live()
            scene.mode.settings(dict(_scene_module().settings(ambient_size=AMBIENT), u_hdr_gain=2.0))
            host.frames(2)
            control = scene.mode.state()
            checks = {
                "nothing_recorded_at_rest": after.get("records") == before.get("records"),
                "nothing_allocated_at_rest": (live_after["scene_target_allocations"]
                                              == live_before["scene_target_allocations"]
                                              and live_after["scene_target_steps"] == live_before["scene_target_steps"]),
                "control_a_setting_change_records": control.get("records", 0) > after.get("records", 0),
                "no_python_thread_state_on_the_render_thread": bool(
                    after.get("syncs_probed") and after.get("syncs_with_python_thread_state") == 0
                    and after.get("syncs_on_gui_thread") == 0),
            }
            facts = {"records": [before.get("records"), after.get("records"), control.get("records")],
                     "allocations": [live_before["scene_target_allocations"], live_after["scene_target_allocations"]],
                     "probe": {k: after.get(k) for k in ("syncs_probed", "syncs_with_python_thread_state",
                                                         "syncs_on_gui_thread")}}
        finally:
            scene.close(app)
            host.frames(2)
            host_check._flush_deletes(app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_resize(core, engine, app, packs: dict, *, one_pixel_control: bool = False) -> dict:
    from rendering.native.scene_targets import next_allocation

    start, end, step = DRAG
    widths = list(range(start, end + 1, step)) + list(range(end - step, start - 1, -step))
    host = core.hidden_host(*_host_size([(end, DRAG_HEIGHT)]))
    observed, expected = [], []
    current = (0, 0)
    checks, facts = {}, {}
    try:
        scene = Scene(core, engine, host, (start, DRAG_HEIGHT), 1.0, packs)
        try:
            ambient_generation = None
            ambient_changes = 0
            for width in widths:
                scene.resize((width, DRAG_HEIGHT))
                host.frames(1)
                state = scene.mode.state()["scene_targets"]
                target, ambient = state["targets"][0], state["targets"][1]
                observed.append(tuple(target["allocation"]))
                current, _reason = next_allocation(current, (width, DRAG_HEIGHT))
                expected.append(current)
                if ambient_generation is not None and ambient["generation"] != ambient_generation:
                    ambient_changes += 1
                ambient_generation = ambient["generation"]
            dragged = scene.targets(app)
        finally:
            scene.close(app)
            host.frames(2)
            host_check._flush_deletes(app)
        fresh_scene = Scene(core, engine, host, (start, DRAG_HEIGHT), 1.0, packs)
        try:
            fresh = fresh_scene.targets(app)
        finally:
            fresh_scene.close(app)
            host.frames(2)
            host_check._flush_deletes(app)
    finally:
        host.close()
        host_check._flush_deletes(app)

    def reallocations(sequence) -> int:
        return sum(1 for a, b in zip(sequence, sequence[1:]) if a != b) + 1

    control = []
    previous = (0, 0)
    for width in widths:
        # Independent one-pixel-bucket oracle: the same two-bucket hysteresis is now two pixels.
        previous = tuple(need if have <= 0 or need > have or have - need >= 2 else have
                         for have, need in zip(previous, (width, DRAG_HEIGHT)))
        control.append(previous)
    checks["allocation_follows_the_rule_at_every_step"] = observed == expected
    checks["fewer_reallocations_than_one_pixel_buckets"] = reallocations(observed) < reallocations(control)
    checks["the_explicit_target_never_reallocated"] = ambient_changes == 0
    content_equal = {}
    for key in ("scene.colour", "scene.emission", "scene.capture_colour", "scene.capture_depth", "ambient.coverage",
                "ambient.light"):
        a = {**dragged[key], "array": _content(dragged[key])}
        b = {**fresh[key], "array": _content(fresh[key])}
        content_equal[key] = compare(a, b)
    checks["after_the_drag_the_content_equals_a_fresh_items"] = all(v["exact"] for v in content_equal.values())
    facts.update({"widths": [widths[0], widths[len(widths) // 2], widths[-1]], "steps": len(widths),
                  "reallocations": reallocations(observed), "control_reallocations": reallocations(control),
                  "first_mismatch": next(([w, o, e] for w, o, e in zip(widths, observed, expected) if o != e), None),
                  "allocations_seen": sorted(set(observed)), "content_equal": content_equal,
                  "final_allocation": [list(dragged["scene.colour"]["size"]), list(fresh["scene.colour"]["size"])]})
    if one_pixel_control:
        facts["normal_rule_checks_on_broken_form"] = checks
        checks = {"native_control_is_a_true_one_pixel_bucket": observed == control,
                  "normal_rule_rejects_one_pixel_buckets": observed != expected,
                  "one_pixel_buckets_reallocate_more": reallocations(observed) > reallocations(expected)}
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


FLAT_FRAGMENT = """#version 440
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 18) uniform Flat {
    vec4 u_flat;
};
void main()
{
    fragColor = u_flat;
}
"""


def round_retire(core, engine, app, packs: dict, folder: Path) -> dict:
    host = core.hidden_host(*_host_size([CARD]))
    checks, facts = {}, {}
    try:
        baseline = core.composite_live()
        scene = Scene(core, engine, host, CARD, 1.0, packs)
        try:
            scene.targets(app)
            held = core.composite_live()
            import probe_rings
            from rendering.native.mode import ModePass

            flat = probe_rings.bake(FLAT_FRAGMENT, "flat.frag", folder)
            try:
                scene.mode.program((ModePass("flat", flat, "replace"),), {"u_flat": [0.2, 0.3, 0.4, 1.0]},
                                   targets=())
                ok = True
            except ValueError as exc:
                ok, facts["no_target_program_refused"] = False, str(exc)
            host.frames(3)
            released = core.composite_live()
            st = _scene_module()
            scene.mode.program(st.passes(packs), dict(st.settings(ambient_size=AMBIENT), u_glow=1.0),
                               targets=st.targets())
            host.frames(3)
            again = core.composite_live()
        finally:
            scene.close(app)
            host.frames(3)
            host_check._flush_deletes(app)
        gone = core.composite_live()
    finally:
        host.close()
        host_check._flush_deletes(app)
    keys = ("scene_targets", "scene_target_textures", "scene_target_bytes", "scene_target_readbacks")
    facts.update({"baseline": {k: baseline.get(k) for k in keys}, "held": {k: held.get(k) for k in keys},
                  "released": {k: released.get(k) for k in keys}, "again": {k: again.get(k) for k in keys},
                  "gone": {k: gone.get(k) for k in keys}})
    checks["targets_held_while_drawn"] = held["scene_targets"] == 2 and held["scene_target_bytes"] > 0
    checks["a_program_without_targets_releases_them_on_a_live_item"] = ok and released["scene_targets"] == 0 \
        and released["scene_target_textures"] == 0 and released["scene_target_bytes"] == 0
    checks["a_program_with_targets_makes_them_again"] = again["scene_targets"] == 2
    checks["the_items_destruction_leaves_nothing"] = all(gone.get(k) == 0 for k in keys) and gone.get(
        "mode_resources") == 0 and gone.get("mode_sources") == 0
    for case in ("mid_allocation", "scene_graph_invalidated"):
        result = _retire_edge(core, engine, app, packs, case)
        facts[case] = result["facts"]
        checks.update({f"{case}_{key}": value for key, value in result["checks"].items()})
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _targets_retired(live: dict) -> bool:
    return all(live.get(key) == 0 for key in ("scene_targets", "scene_target_textures", "scene_target_bytes",
                                             "scene_target_readbacks", "mode_resources"))


def _retire_edge(core, engine, app, packs: dict, case: str, *, skip_control: bool = False) -> dict:
    """Measure the actual edge before host close; a separately run control deliberately skips that edge."""
    host = core.hidden_host(*_host_size([CARD]))
    scene = None
    checks, facts = {}, {}
    try:
        if case == "mid_allocation":
            core.scene_target_control("allocation_steps", 1)
        scene = Scene(core, engine, host, CARD, 1.0, packs)
        if case == "mid_allocation":
            states = []
            for index in range(2):
                # A real input edge makes the still's surface dirty for the next bounded record. update() alone
                # merely asks Qt for sync and correctly does no native work when the source is unchanged.
                scene.mode.settings(dict(_scene_module().settings(ambient_size=AMBIENT), u_glow=1.0 - index * 0.125))
                scene.mode.update()
                host.frames(1)
                states.append(scene.mode.state()["scene_targets"])
            first, second = states
            checks["one_attachment_step_per_record"] = second["steps"] == first["steps"] + 1
            checks["same_allocation_plan_between_records"] = (
                second["allocations"] == first["allocations"]
                and [t["generation"] for t in second["targets"]] == [t["generation"] for t in first["targets"]])
            checks["destroyed_while_targets_are_incomplete"] = not all(t["ready"] for t in second["targets"])
            facts["states_before_destruction"] = states
        else:
            scene.targets(app)
        held = core.composite_live()
        checks["live_target_objects_are_counted_before_the_edge"] = (
            held["scene_target_textures"] > 0 and held["scene_target_bytes"] > 0)
        if skip_control:
            # Broken form: omit this edge, leaving the actual native objects alive. Apply the positive round's
            # predicate before cleanup; a synthetic edited counter is never the negative control.
            checks["skipped_release_is_rejected"] = not _targets_retired(held) and held["scene_target_textures"] > 0
            facts["skipped_release_live"] = held
            facts["normal_retirement_predicate_pass"] = _targets_retired(held)
            return {"pass": all(checks.values()), "checks": checks, "facts": facts}
        if case == "mid_allocation":
            scene.close(app)
            scene = None
            host.frames(2)
            host_check._flush_deletes(app)
        else:
            host.invalidate_scene_graph()
            state = host.state()
            facts["host_before_close"] = state
            driver = state.get("driver") or {}
            checks["actual_scene_graph_signal_released_on_render_thread"] = (
                driver.get("release_reason") == "scene graph invalidated"
                and driver.get("released_on_gui_thread") is False)
            checks["invalidation_keeps_the_item_alive"] = core.composite_live()["mode_sources"] > 0
        gone = core.composite_live()  # before host.close: close cannot supply the proof
        facts.update({"held_before_edge": held, "released_before_host_close": gone})
        checks["edge_retires_all_target_resources"] = _targets_retired(gone)
    finally:
        core.scene_target_control("allocation_steps", 0)
        if scene is not None:
            scene.close(app)
        host.close()
        host_check._flush_deletes(app)
    return {"checks": checks, "facts": facts}


def round_prime_control(core, engine, app, packs: dict) -> dict:
    """Rule C for depth's negative control (Vulkan, its own run): the scene drawn twice with the depth's prime skipped,
    then twice with it; the run's validation messages, per phase, say whether synchronisation validation shows the
    hazard the prime prevents (QRhi's depth barrier is write-only at the late tests while a preserved depth's load
    reads at the early ones: research N3, Q3)."""
    host = core.hidden_host(*_host_size([CARD]))
    facts = {}
    try:
        for label, skip in (("skipped", True), ("primed", False)):
            core.set_vulkan_phase(f"n31 prime {label}")
            core.scene_depth_prime_control(skip)
            before = core.composite_live()["scene_target_depth_primes"]
            try:
                # One sample, and 4x: the multisampled depth is read by the nearest resolve before the capture and
                # loaded after it (research N3 Q3: the same hazard class).
                for samples in (1, 4):
                    scene = Scene(core, engine, host, CARD, 1.0, packs, samples=samples)
                    try:
                        scene.targets(app)
                        scene.mode.settings(dict(_scene_module().settings(ambient_size=AMBIENT), u_hdr_gain=2.2))
                        scene.targets(app)
                    finally:
                        scene.close(app)
                        host.frames(2)
                        host_check._flush_deletes(app)
            finally:
                core.scene_depth_prime_control(False)
            facts[label] = {"depth_primes": core.composite_live()["scene_target_depth_primes"] - before}
        # Audit 2, H1: the resolves' prime. Consecutive 4x records with no readback between them (a readback orders the
        # resolve and hides the hazard), the resolves' prime skipped, then with it.
        base = _scene_module().settings(ambient_size=AMBIENT)
        for label, skip in (("skipped", True), ("primed", False)):
            core.set_vulkan_phase(f"n31 resolve prime {label}")
            core.scene_resolve_prime_control(skip)
            before = core.composite_live()["scene_target_resolve_primes"]
            try:
                scene = Scene(core, engine, host, CARD, 1.0, packs, samples=4)
                try:
                    host.frames(2)
                    for index in range(RESOLVE_CONTROL_FRAMES):
                        scene.mode.settings(dict(base, u_hdr_gain=2.0 + (0.2 if index % 2 else 0.0)))
                        host.frames(1)
                    records = scene.mode.state().get("records")
                finally:
                    scene.close(app)
                    host.frames(2)
                    host_check._flush_deletes(app)
            finally:
                core.scene_resolve_prime_control(False)
            facts[f"resolve_{label}"] = {"resolve_primes": core.composite_live()["scene_target_resolve_primes"] - before,
                                         "records": records}
    finally:
        host.close()
        host_check._flush_deletes(app)
    checks = {"the_control_records_no_prime_and_the_product_path_does":
              facts["skipped"]["depth_primes"] == 0 and facts["primed"]["depth_primes"] > 0,
              "the_resolve_control_records_no_prime_and_the_product_path_does":
              facts["resolve_skipped"]["resolve_primes"] == 0 and facts["resolve_primed"]["resolve_primes"] > 0}
    return {"pass": all(checks.values()), "facts": facts, "checks": checks}


COST_PARTS = ("clear", "planes2", "draws", "read", "capture")


def round_cost_parts(core, engine, app, packs: dict) -> dict:
    """Where the four-sample time goes at 4K (the lead, 15 Nov): each of ``scene_targets.cost_part_program``'s programs
    single-sampled and at 4x, the surface's GPU time (median, p90); a part's 4x minus 1x against the part before it
    says what that step adds (the clearing draw and plane; two more passes; a colour resolve and the surface pass; the
    capture split with its depth read and second run)."""
    st = _scene_module()
    size = COST_HOSTS[-1]
    facts = {}
    host = core.hidden_host(size[0] + 2 * MARGIN, size[1] + 2 * MARGIN)
    try:
        for part in COST_PARTS:
            timings = {}
            for samples in (1, 4):
                passes, targets, settings = st.cost_part_program(packs, part, samples=samples)
                scene = Scene(core, engine, host, size, 1.0, packs, passes=passes, targets=targets, settings=settings)
                try:
                    host.frames(4)
                    timings[f"x{samples}"] = _timed(host, scene, settings, COST_FRAMES)
                    state = scene.mode.state()
                    timings[f"x{samples}"]["effective_samples"] = state["scene_targets"]["targets"][0][
                        "effective_samples"]
                    if state.get("error") or state.get("failure"):
                        timings[f"x{samples}"]["error"] = state.get("error") or state.get("failure")
                finally:
                    scene.close(app)
                    host.frames(2)
                    host_check._flush_deletes(app)
            single, multi = timings["x1"]["median_ms"], timings["x4"]["median_ms"]
            timings["four_minus_one_ms"] = None if single is None or multi is None else round(multi - single, 4)
            low1, low4 = timings["x1"]["p10_ms"], timings["x4"]["p10_ms"]
            timings["four_minus_one_p10_ms"] = None if low1 is None or low4 is None else round(low4 - low1, 4)
            facts[part] = timings
    finally:
        host.close()
        host_check._flush_deletes(app)
    ok = all(facts[p]["four_minus_one_ms"] is not None for p in COST_PARTS)
    return {"pass": ok, "facts": facts, "size": list(size)}


def _ambient_cover_only(packs: dict, folder: Path):
    """The ambient pass and target without the light attachment (choice F's comparison)."""
    import probe_rings
    from rendering.native.mode import ModeTarget, PassOutput, TargetAttachment

    st = _scene_module()
    text = st.shader_text("ambient_light.frag")
    for old, new in (("layout(location = 1) out vec4 light;\n", ""),
                     ("    light = vec4(u_disc_colour.rgb * (u_glow * 2.5 * a), 0.0);\n", "")):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    pack = probe_rings.bake(text, "ambient_cover.frag", folder)
    target = ModeTarget("ambient", (TargetAttachment("coverage", "rgba8"),), size=COST_AMBIENT)
    from dataclasses import replace

    ambient_pass = replace(st.passes(packs, with_show=False)[-1], pack=pack, outputs=(PassOutput(True, "premultiplied"),))
    return target, ambient_pass


def _timed(host, scene, settings: dict, frames: int, member: str = "u_hdr_gain", step: float = 0.001) -> dict:
    """The surface's GPU time (kind 2) over at least ``frames`` records, each forced by a setting (``member``) that
    alternates. Qt's OpenGL backend reads a TIME_ELAPSED result only once it is ready and drops it when the timer's ring
    wraps first (never a wait), so the records go on past ``frames`` until COST_MIN_SAMPLES times have arrived, at most
    COST_MAX_FRAMES records: counted, never slept (audit 2, M1; generic_mode_check's timer control)."""
    host.set_gpu_timer(True)
    host.frames(4)
    host.gpu_samples()
    times: list[int] = []
    drawn = 0
    while drawn < COST_MAX_FRAMES and (drawn < frames or len(times) < COST_MIN_SAMPLES):
        scene.mode.settings(dict(settings, **{member: settings[member] + (step if drawn % 2 else 0.0)}))
        host.frames(1)
        drawn += 1
        times.extend(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
    host.frames(4)
    times.extend(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
    timer = (host.state().get("driver") or {}).get("gpu_timer") or {}
    host.set_gpu_timer(False)
    summary = _time_summary(sorted(times))
    summary["records"] = drawn
    # R-223: the timer's own counts (slots given up on, frames left untimed) beside the figure.
    summary["abandoned_slots"] = timer.get("abandoned_slots")
    summary["slot_busy_frames"] = timer.get("slot_busy_frames")
    return summary


def _time_summary(times: list[int]) -> dict:
    """GPU times (ns, sorted) as ms: the median and p90, and the p10 (the figure least touched by another process
    sharing the GPU: the operator's machine is never idle; record its load beside the figures)."""
    if not times:
        return {"samples": 0, "median_ms": None, "p90_ms": None, "p10_ms": None}
    return {"samples": len(times), "median_ms": round(times[len(times) // 2] / 1e6, 4),
            "p90_ms": round(times[int(len(times) * 0.9)] / 1e6, 4),
            "p10_ms": round(times[int(len(times) * 0.1)] / 1e6, 4)}


def round_cost(core, engine, app, packs: dict, folder: Path) -> dict:
    st = _scene_module()
    checks, facts = {}, {}
    for size in COST_HOSTS:
        label = f"{size[0]}x{size[1]}"
        host = core.hidden_host(size[0] + 2 * MARGIN, size[1] + 2 * MARGIN)
        try:
            timings = {}
            for samples in (1, 4):
                settings = dict(st.settings(ambient_size=COST_AMBIENT), u_glow=1.0)
                started = time.perf_counter()
                scene = Scene(core, engine, host, size, 1.0, packs, samples=samples, ambient=COST_AMBIENT,
                              settings=settings)
                try:
                    host.frames(1)
                    first_ms = (time.perf_counter() - started) * 1000.0
                    host.frames(3)
                    steady_started = time.perf_counter()
                    scene.mode.settings(dict(settings, u_hdr_gain=2.6))
                    host.frames(1)
                    steady_ms = (time.perf_counter() - steady_started) * 1000.0
                    timings[f"x{samples}"] = _timed(host, scene, settings, COST_FRAMES)
                    timings[f"x{samples}"].update({"first_frame_wall_ms": round(first_ms, 2),
                                                   "steady_frame_wall_ms": round(steady_ms, 2)})
                    timings[f"x{samples}"]["effective_samples"] = scene.mode.state()["scene_targets"]["targets"][0][
                        "effective_samples"]
                finally:
                    scene.close(app)
                    host.frames(2)
                    host_check._flush_deletes(app)
            facts[label] = timings
            single, multi = timings["x1"]["median_ms"], timings["x4"]["median_ms"]
            bound = None if single is None or multi is None else round(multi - single, 4)
            facts[label]["resolve_bound_ms"] = bound
            low1, low4 = timings["x1"]["p10_ms"], timings["x4"]["p10_ms"]
            facts[label]["resolve_bound_p10_ms"] = None if low1 is None or low4 is None else round(low4 - low1, 4)
            checks[f"{label}_timed"] = all(timings[key]["samples"] >= COST_MIN_SAMPLES for key in ("x1", "x4"))
            # R-223: with the host's frames finished on every backend the times arrive well inside the cap (at most
            # twice the minimum records), and no slot is given up on.
            checks[f"{label}_timed_well_inside_the_cap"] = all(
                timings[key]["records"] <= 2 * COST_FRAMES and not timings[key].get("abandoned_slots")
                for key in ("x1", "x4"))
            checks[f"{label}_4x_minus_1x_within_the_resolve_budget"] = bound is not None and bound <= RESOLVE_BUDGET_MS[
                size]
        finally:
            host.close()
            host_check._flush_deletes(app)
    # Choice F: the light attachment's clear (nothing glows) at the ambient cap.
    host = core.hidden_host(COST_AMBIENT[0] + 2 * MARGIN, COST_AMBIENT[1] + 2 * MARGIN)
    try:
        cover_target, cover_pass = _ambient_cover_only(packs, folder)
        light_target = st.targets(ambient_size=COST_AMBIENT)[1]
        light_pass = st.passes(packs, with_show=False)[-1]
        clear = {}
        for label, target, mode_pass in (("with_light", light_target, light_pass),
                                         ("coverage_only", cover_target, cover_pass)):
            settings = {"u_disc_colour": [0.9, 0.5, 0.2, 1.0], "u_glow": 0.0, "u_radius": 0.08, "u_hdr_gain": 0.0}
            # u_hdr_gain is no member of the ambient pass: _timed alternates u_radius instead.
            settings = {k: v for k, v in settings.items() if k != "u_hdr_gain"}
            scene = Scene(core, engine, host, COST_AMBIENT, 1.0, packs, passes=(mode_pass,), targets=(target,),
                          settings=settings)
            try:
                host.frames(3)
                timed = _timed(host, scene, settings, COST_FRAMES, member="u_radius", step=0.0001)
                clear[label] = {"samples": timed["samples"], "median_ms": timed["median_ms"],
                                "records": timed["records"]}
            finally:
                scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
        facts["light_clear"] = clear
        if clear["with_light"]["median_ms"] is not None and clear["coverage_only"]["median_ms"] is not None:
            difference = round(clear["with_light"]["median_ms"] - clear["coverage_only"]["median_ms"], 4)
            facts["light_clear"]["difference_ms"] = difference
            checks["light_attachment_clear_negligible"] = difference <= CLEAR_BUDGET_MS
        else:
            checks["light_attachment_clear_negligible"] = False
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the reference

REFERENCE_VERTEX = """#version 440
layout(location = 0) out vec2 vUv;
void main()
{
    vec2 p = vec2(gl_VertexID == 1 ? 3.0 : -1.0, gl_VertexID == 2 ? 3.0 : -1.0);
    vUv = p * 0.5 + 0.5;
    gl_Position = vec4(p, 0.0, 1.0);
}
"""


def reference_frames(core, packs: dict, case_dpr: float, glow: float, card: tuple[int, int] = CARD) -> dict:
    """The Python renderer's owners drawing the same fragments: SceneTarget (depth_texture, background(), hdr: Extruded
    Bubble's scope) and a GL target with the ambient owner's formats and blend states; read back as the core reads its
    own (rows flipped to the image's top first)."""
    import ctypes
    from types import SimpleNamespace

    import numpy as np
    from OpenGL import GL as gl

    from rendering.native.scene_targets import bucket_pixels
    from rendering.quick.render.gl_resources import compile_program, delete_program
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.target import SceneTarget
    from tools.labs.render_target import OffscreenRenderTarget

    st = _scene_module()
    width, height = _pixels(card, case_dpr)
    settings = dict(st.settings(ambient_size=AMBIENT, with_show=False), u_glow=float(glow))
    target_gl = OffscreenRenderTarget(width, height, label="n31-reference")
    frames: dict = {}
    with target_gl.current():
        programs = {name: compile_program(REFERENCE_VERTEX, st.shader_text(file), label=f"n31 {name}")
                    for name, file in st.FRAGMENTS if name in ("planes", "nearer", "after", "ambient")}
        blocks = {}
        names = {"planes": "ScenePlanes", "nearer": "SceneNearer", "after": "SceneAfter", "ambient": "AmbientLight"}
        for name, block in names.items():
            members = {k: v for k, v in settings.items()
                       if k in st.shader_text(dict(st.FRAGMENTS)[name])}
            data, _facts = core.program_block_pack(packs[name], block, members)
            buffer = (ctypes.c_uint * 1)()
            gl.glCreateBuffers(1, buffer)
            gl.glNamedBufferData(int(buffer[0]), len(data), data, gl.GL_STATIC_DRAW)
            blocks[name] = int(buffer[0])

        def draw(name: str) -> None:
            gl.glUseProgram(programs[name])
            gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 18, blocks[name])
            gl.glBindVertexArray(target_gl.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

        def read(texture: int, w: int, h: int, fmt: str, content):
            if fmt == "rgba8":
                array = np.empty((h, w, 4), np.uint8)
                gl.glGetTextureImage(texture, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, array.nbytes, array)
            elif fmt == "rgba16f":
                array = np.empty((h, w, 4), np.float16)
                gl.glGetTextureImage(texture, 0, gl.GL_RGBA, gl.GL_HALF_FLOAT, array.nbytes, array)
            else:
                array = np.empty((h, w), np.float32)
                gl.glGetTextureImage(texture, 0, gl.GL_RED, gl.GL_FLOAT, array.nbytes, array)
            return {"array": array[::-1].copy(), "content": content, "size": (w, h), "format": fmt, "samples": 1}

        # The scene: SceneTarget over the whole capture (its item rect), as Extruded Bubble opens it.
        resources, scene = MeshResources("n31 reference"), SceneTarget("n31 reference")
        frame = SimpleNamespace(viewport=(0, 0, width, height), logical_size=(width, height),
                                matrix_values=(2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                quad_vao=target_gl.vao)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target_gl.fbo)
        scene.begin(frame, 1, overlay=1.0, emission=True, depth_texture=True, hdr=True)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisablei(gl.GL_BLEND, 0)
        gl.glDepthFunc(gl.GL_ALWAYS)
        with scene.emission_writes():
            draw("planes")
        gl.glDepthFunc(gl.GL_LESS)
        draw("nearer")
        background_colour, background_depth = scene.background(frame, resources)
        gl.glEnablei(gl.GL_BLEND, 0)
        gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparatei(0, gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glDepthMask(gl.GL_FALSE)
        draw("after")
        gl.glDisablei(gl.GL_BLEND, 0)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glFinish()
        aw, ah = scene._key[0], scene._key[1]
        content = (width, height)
        frames["scene.colour"] = read(scene._names["colour"], aw, ah, "rgba16f", content)
        frames["scene.emission"] = read(scene._names["emission"], aw, ah, "rgba16f", content)
        frames["scene.capture_colour"] = read(background_colour, aw, ah, "rgba16f", content)
        frames["scene.capture_depth"] = read(background_depth, aw, ah, "r32f", content)
        scene._restore_inherited(frame)
        scene.release()
        resources.release_resources()

        # The ambient target: RGBA8 coverage (premultiplied over) and RGBA16F light (ONE, ONE), bucketed as the core's.
        cw, ch = AMBIENT
        bw, bh = bucket_pixels(cw), bucket_pixels(ch)
        names = (ctypes.c_uint * 2)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 2, names)
        cover, light = int(names[0]), int(names[1])
        gl.glTextureStorage2D(cover, 1, gl.GL_RGBA8, bw, bh)
        gl.glTextureStorage2D(light, 1, gl.GL_RGBA16F, bw, bh)
        fbo = (ctypes.c_uint * 1)()
        gl.glCreateFramebuffers(1, fbo)
        fbo = int(fbo[0])
        gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0, cover, 0)
        gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT1, light, 0)
        gl.glNamedFramebufferDrawBuffers(fbo, 2, [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, bw, bh)
        gl.glClearBufferfv(gl.GL_COLOR, 0, (0.0, 0.0, 0.0, 0.0))
        gl.glClearBufferfv(gl.GL_COLOR, 1, (0.0, 0.0, 0.0, 0.0))
        gl.glViewport(0, 0, cw, ch)
        for index in (0, 1):
            gl.glEnablei(gl.GL_BLEND, index)
            gl.glBlendEquationSeparatei(index, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glBlendFuncSeparatei(1, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
        draw("ambient")
        for index in (0, 1):
            gl.glDisablei(gl.GL_BLEND, index)
        gl.glFinish()
        frames["ambient.coverage"] = read(cover, bw, bh, "rgba8", AMBIENT)
        frames["ambient.light"] = read(light, bw, bh, "rgba16f", AMBIENT)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target_gl.fbo)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([cover, light])
        for buffer in blocks.values():
            gl.glDeleteBuffers(1, [buffer])
        for program in programs.values():
            delete_program(program)
    target_gl.close()
    return frames


def python_cost(core, packs: dict, size: tuple[int, int], samples: int, frames: int) -> dict:
    """The Python renderer's GPU time for the harness scene's load at ``size`` and ``samples`` (OpenGL, the
    production owner ``SceneTarget``): begin, planes, nearer, ``background()``, after, ``end()`` (the overlay composite,
    reading the samples when multisampled), timed with GL_TIME_ELAPSED around the whole scope, one query a frame."""
    import ctypes
    from types import SimpleNamespace

    from OpenGL import GL as gl

    from rendering.quick.render.gl_resources import compile_program, delete_program
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.target import SceneTarget
    from tools.labs.render_target import OffscreenRenderTarget

    st = _scene_module()
    width, height = size
    settings = dict(st.settings(ambient_size=COST_AMBIENT, with_show=False), u_glow=1.0)
    target_gl = OffscreenRenderTarget(width, height, label="n31-python-cost")
    times: list[int] = []
    with target_gl.current():
        programs = {name: compile_program(REFERENCE_VERTEX, st.shader_text(file), label=f"n31 cost {name}")
                    for name, file in st.FRAGMENTS if name in ("planes", "nearer", "after")}
        blocks = {}
        for name, block in (("planes", "ScenePlanes"), ("nearer", "SceneNearer"), ("after", "SceneAfter")):
            members = {k: v for k, v in settings.items() if k in st.shader_text(dict(st.FRAGMENTS)[name])}
            data, _facts = core.program_block_pack(packs[name], block, members)
            buffer = (ctypes.c_uint * 1)()
            gl.glCreateBuffers(1, buffer)
            gl.glNamedBufferData(int(buffer[0]), len(data), data, gl.GL_STATIC_DRAW)
            blocks[name] = int(buffer[0])

        def draw(name: str) -> None:
            gl.glUseProgram(programs[name])
            gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 18, blocks[name])
            gl.glBindVertexArray(target_gl.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

        resources, scene = MeshResources("n31 python cost"), SceneTarget("n31 python cost")
        frame = SimpleNamespace(viewport=(0, 0, width, height), logical_size=(width, height),
                                matrix_values=(2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                quad_vao=target_gl.vao)
        query = (ctypes.c_uint * 1)()
        gl.glGenQueries(1, query)
        try:
            for index in range(frames + 4):
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target_gl.fbo)
                gl.glBeginQuery(gl.GL_TIME_ELAPSED, int(query[0]))
                scene.begin(frame, samples, overlay=1.0, emission=True, depth_texture=True, hdr=True)
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDisablei(gl.GL_BLEND, 0)
                gl.glDepthFunc(gl.GL_ALWAYS)
                with scene.emission_writes():
                    draw("planes")
                gl.glDepthFunc(gl.GL_LESS)
                draw("nearer")
                scene.background(frame, resources)
                gl.glEnablei(gl.GL_BLEND, 0)
                gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                gl.glBlendFuncSeparatei(0, gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE,
                                        gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDepthFunc(gl.GL_LEQUAL)
                gl.glDepthMask(gl.GL_FALSE)
                draw("after")
                gl.glDisablei(gl.GL_BLEND, 0)
                scene.end(frame, resources)
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glEndQuery(gl.GL_TIME_ELAPSED)
                value = (ctypes.c_uint64 * 1)()
                gl.glGetQueryObjectui64v(int(query[0]), gl.GL_QUERY_RESULT, value)
                if index >= 4:                       # the allocation's and the programs' first frames left out
                    times.append(int(value[0]))
        finally:
            gl.glDeleteQueries(1, query)
            scene.release()
            resources.release_resources()
            for buffer in blocks.values():
                gl.glDeleteBuffers(1, [buffer])
            for program in programs.values():
                delete_program(program)
    target_gl.close()
    times.sort()
    return _time_summary(times)


def round_python_cost(core, packs: dict) -> dict:
    """The lead's measure for the 4K four-sample cost (15 Nov): the Python path's 4x minus 1x on the same load, OpenGL;
    the native figure (the cost round's ``resolve_bound_ms``) is accepted when no worse."""
    facts = {}
    for size in COST_HOSTS:
        label = f"{size[0]}x{size[1]}"
        timings = {f"x{n}": python_cost(core, packs, size, n, PYTHON_COST_FRAMES) for n in (1, 4)}
        single, multi = timings["x1"]["median_ms"], timings["x4"]["median_ms"]
        timings["four_minus_one_ms"] = None if single is None or multi is None else round(multi - single, 4)
        timings["four_minus_one_p10_ms"] = round(timings["x4"]["p10_ms"] - timings["x1"]["p10_ms"], 4)
        facts[label] = timings
    ok = all(facts[f"{s[0]}x{s[1]}"]["four_minus_one_ms"] is not None for s in COST_HOSTS)
    return {"pass": ok, "facts": facts}


def round_reference(core, packs: dict, out: Path) -> dict:
    frames = {}
    for case, card, dpr, glow in PARITY_CASES:
        frames[case] = reference_frames(core, packs, dpr, glow, card)
    _save(out, "parity_reference", frames)
    return {"pass": True, "cases": [c for c, _card, _d, _g in PARITY_CASES]}


def cross_compare(out: Path) -> dict:
    """Rule (a): native OpenGL against the reference; rule (b): native Vulkan against native OpenGL."""
    gl, vk, ref = _load(out, "parity_opengl"), _load(out, "parity_vulkan"), _load(out, "parity_reference")
    result: dict = {}
    for rule, a, b in (("rule_a", gl, ref), ("rule_b", vk, gl)):
        if not a or not b:
            result[rule] = {"pass": False, "error": "a frame set is missing"}
            continue
        per = {}
        ok = True
        for case in a:
            for texture in a[case]:
                if texture not in b.get(case, {}):
                    continue                              # the surface's own textures (show) are not in the reference
                c = compare(a[case][texture], b[case][texture])
                tolerance = SCENE_RULE_A if rule == "rule_a" else SCENE_RULE_B
                c["tolerance"] = judged(a[case][texture], b[case][texture], tolerance)
                per[f"{case}|{texture}"] = c
                ok = ok and c["tolerance"]["pass"]
        result[rule] = {"pass": ok and bool(per), "compared": per,
                        "bound": (SCENE_RULE_A if rule == "rule_a" else SCENE_RULE_B).bound(),
                        "exact": sorted(k for k, v in per.items() if v["exact"])}
    return result


def placement_control_verdict(out: Path) -> dict:
    """Hold the native content-at-top broken form to the unchanged Python renderer's edge reads."""
    import numpy as np

    candidate, reference = _load(out, "placement_control"), _load(out, "parity_reference")
    compared = {}
    for case in (name for name, _card, _dpr, _glow in PARITY_CASES if name != "aligned"):
        for texture, expected in reference.get(case, {}).items():
            actual = candidate.get(case, {}).get(texture)
            if actual is None:
                return {"pass": False, "error": f"missing broken-form frame: {case}|{texture}"}
            width, height = expected["content"]
            aw, ah = expected["size"]
            # The correct content's first/last row, the slack beside it, and the right edge. Derive solely from
            # the independent oracle; never shift either frame into agreement with the candidate.
            mask = np.zeros((ah, aw), dtype=bool)
            for row in (ah - height - 1, ah - height, ah - 1):
                if 0 <= row < ah:
                    mask[row, :min(aw, width + 1)] = True
            mask[ah - height:, max(0, width - 1):min(aw, width + 1)] = True
            channels = actual["array"].shape[2:]  # keep a two-dimensional pixel grid for shared tolerance masks
            a = {**actual, "array": actual["array"][mask].reshape((-1, 1, *channels))}
            b = {**expected, "array": expected["array"][mask].reshape((-1, 1, *channels))}
            compared[f"{case}|{texture}"] = judged(a, b, SCENE_RULE_A)
    rejected = [name for name, result in compared.items() if not result["pass"]]
    return {"pass": bool(rejected), "edge_reads_rejected_by_rule_a": rejected, "compared": compared,
            "bound": SCENE_RULE_A.bound()}


def _sheet(out: Path, api: str, frames: dict) -> None:
    """One look sheet: per case, the scene's colour (clamped), its captured depth and the ambient coverage and light."""
    import numpy as np
    from PIL import Image

    rows = []
    for case, textures in frames.items():
        tiles = []
        for key in ("scene.colour", "scene.capture_depth", "scene.emission", "ambient.coverage", "ambient.light"):
            array = textures[key]["array"].astype(np.float32)
            if array.ndim == 2:
                array = np.repeat(array[..., None], 3, axis=2)
            if textures[key]["format"] == "rgba8":
                array = array / 255.0
            rgb = np.clip(array[..., :3], 0.0, 1.0)
            tile = Image.fromarray((rgb * 255.0 + 0.5).astype(np.uint8)).resize((320, 180))
            tiles.append(tile)
        row = Image.new("RGB", (320 * len(tiles), 180))
        for index, tile in enumerate(tiles):
            row.paste(tile, (320 * index, 0))
        rows.append(row)
    if rows:
        sheet = Image.new("RGB", (rows[0].width, 180 * len(rows)))
        for index, row in enumerate(rows):
            sheet.paste(row, (0, 180 * index))
        sheet.save(out / f"sheet_{api}.png")


# --------------------------------------------------------------------------------------------------- N5.4 (ABI 33)
# Waveform's five C++ boxes on the harness scenes native/core/python/waveform_primitives (Current_Plan.md N5.4):
# - wave_floor: the floor scene (an exact, mipped, drawable reflection at odd sizes with two-output passes; the
#   exact pre-pass; the RGBA16F slope map's GPU levels; the floor's anisotropic taps), native frames per variant: taps
#   (the means chosen), plain (box 2's control: one read at 1x), bucket (box 1's control: the reflection bucketed),
#   slope_rgba8 (box 3's control: the slope map stored as RGBA8); the state (allocation, self mips, the chains counted,
#   nothing at rest). The reference child draws the same text (waveform_primitives.reference_frames). The parent judges
#   (wave_verdict): rule (a) per texture against the reference on each API, every reflection level reported (odd
#   levels apart on Vulkan), the controls failing where their box says, and the taps against Python's hardware
#   anisotropy reported as a fact.
# - wave_limits: Waveform's shape (28 passes, 9 storage images, 4 targets) admitted and built (its objects counted,
#   the first record's wall time, nothing at rest); one pass, one image and one target past the limits refused with
#   their reasons.
# - wave_filter: the device facts (linear_filter_formats on both backends), an RGBA32F storage image read linearly
#   drawn, the faked device (compute_control no_float32_linear) refusing it with its reason, and recovery.
WAVE_ROUNDS = ("wave_floor", "wave_limits", "wave_filter")
WAVE_NATIVE_VARIANTS = ("taps", "plain", "bucket", "slope_rgba8")
WAVE_SETTLE_S = 15.0


def _wave_module():
    import waveform_primitives

    return waveform_primitives


class WaveScene:
    """One item drawing a waveform_primitives program at (MARGIN, MARGIN), with its textures: a still, or (``schema``)
    a streamed item whose records the harness publishes (a still draws no compute: N3.3), the record's fields
    ``unread`` (ABI 26: the shape's stand-ins read none)."""

    def __init__(self, core, engine, host, card: tuple[int, int], passes, settings: dict, *, targets=(), images=(),
                 textures: tuple = (), schema=None, unread: tuple = ()) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        self.host = host
        self.component = QQmlComponent(engine)
        self.component.setData(SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        self.content = self.root.findChild(QQuickItem, "contentHost")
        host.set_content(self.root)
        self.mode = core.mode(self.content)
        self.mode.composite.set(rect=[0.0, 0.0, float(card[0]), float(card[1])], coverage=None, quarters=0,
                                visible=True)
        self.stream = None
        self.schema = schema
        self.step = 0
        if schema is None:
            self.mode.still()
        self.mode.program(passes, settings, targets=targets, images=images, unread=unread)
        self.mode.card(_card(card, 1.0))
        if schema is not None:
            import mesh_buffer_check as mbc

            self.stream = mbc.Stream(schema)
            self.mode.bind(self.stream.name, schema, expect=self.stream.expect)
        for name, pixels, size, fmt in textures:
            self.mode.texture(name, pixels, size, mips=True, format=fmt)
        self.expected_textures = len(textures)

    def publish(self) -> None:
        """A new record (streamed items only): u_frame counts them."""
        if self.stream is not None:
            self.stream.publish(self.schema.encode({"u_frame": float(self.step)}), float(self.step))
            self.step += 1

    def settle(self, timeout_s: float = WAVE_SETTLE_S) -> dict:
        """Frames until every texture is resident and no upload job is pending (the passes draw); the state then."""
        deadline = time.monotonic() + timeout_s
        while True:
            self.publish()
            self.mode.update()
            self.host.frames(1)
            state = self.mode.state()
            if (state.get("textures_resident", 0) >= self.expected_textures
                    and (state.get("texture_jobs") or {}).get("pending", 0) == 0) or time.monotonic() > deadline:
                self.host.frames(2)
                return self.mode.state()

    def targets(self, timeout_s: float = 10.0) -> dict:
        self.mode.read_targets()
        self.mode.update()
        deadline = time.monotonic() + timeout_s
        while True:
            self.host.frames(1)
            pixels = self.mode.target_pixels()
            if pixels is not None or time.monotonic() > deadline:
                break
        if pixels is None:
            raise RuntimeError("the target readback did not complete")
        return {p["name"]: _array(p) for p in pixels}

    def close(self, app) -> None:
        self.mode.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)
        if self.stream is not None:
            self.stream.close()


def _wave_floor_scene(core, engine, host, packs: dict, variant: str) -> WaveScene:
    wp = _wave_module()
    passes, targets = wp.floor_program(packs, reflection_allocation="bucket" if variant == "bucket" else "exact")
    settings = wp.floor_settings(u_taps=0.0 if variant == "plain" else 1.0,
                                 u_slope_encoded=1.0 if variant == "slope_rgba8" else 0.0)
    slope, fmt = wp.slope_texture(variant == "slope_rgba8")
    textures = (("checker", wp.checker_pixels().tobytes(), (wp.CHECKER, wp.CHECKER), "rgba8"),
                ("slope", slope, (wp.SLOPE, wp.SLOPE), fmt))
    return WaveScene(core, engine, host, wp.FLOOR, passes, settings, targets=targets, textures=textures)


def round_wave_floor(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    wp = _wave_module()
    host = core.hidden_host(*_host_size([wp.FLOOR]))
    checks, facts, frames = {}, {}, {}
    try:
        for variant in WAVE_NATIVE_VARIANTS:
            mips_before = core.composite_live().get("scene_target_mips", 0)
            scene = _wave_floor_scene(core, engine, host, packs, variant)
            try:
                state = scene.settle()
                frames[variant] = scene.targets()
                targets = {t["name"]: t for t in (state.get("scene_targets") or {}).get("targets", [])}
                reflection = targets.get("reflection", {})
                facts[variant] = {
                    "content_failing": state.get("content_failing"), "content_failure": state.get("content_failure"),
                    "last_reason": state.get("last_reason"),
                    "textures": [{k: t.get(k) for k in ("name", "format", "mips", "size")}
                                 for t in state.get("textures", [])],
                    "texture_route": (state.get("texture_jobs") or {}).get("route"),
                    "reflection": {k: reflection.get(k) for k in ("allocation", "content", "self_mips", "mips",
                                                                 "depth", "last_reason")},
                    "chains_generated": core.composite_live().get("scene_target_mips", 0) - mips_before,
                    "levels_read": sorted(name for name in frames[variant] if name.startswith("reflection.colour")),
                }
                checks[f"{variant}_drew"] = not state.get("content_failing") and all(
                    name in frames[variant] for name in ("floor.checker", "floor.mean", "slope_levels.colour"))
                checks[f"{variant}_reflection_is_self_mipped"] = reflection.get("self_mips") is True
                checks[f"{variant}_the_chain_was_generated"] = facts[variant]["chains_generated"] >= 1
                if variant == "bucket":
                    checks["bucket_control_allocates_a_bucket"] = (
                        tuple(reflection.get("allocation") or ()) == tuple(bucket_pixels_pair(wp.REFLECTION)))
                else:
                    checks[f"{variant}_reflection_is_exact"] = (
                        tuple(reflection.get("allocation") or ()) == tuple(wp.REFLECTION)
                        == tuple(reflection.get("content") or ()))
                    checks[f"{variant}_every_level_read"] = len(facts[variant]["levels_read"]) == 1 + int(
                        math.floor(math.log2(max(wp.REFLECTION))))
                slope_state = [t for t in facts[variant]["textures"] if t["name"] == "slope"]
                checks[f"{variant}_slope_format"] = bool(slope_state) and slope_state[0]["format"] == (
                    "rgba8" if variant == "slope_rgba8" else "rgba16f")
                if variant == "taps":
                    # Nothing at rest: no record, no allocation, no chain over frames with nothing changed.
                    host.frames(2)
                    before, live_before = scene.mode.state(), core.composite_live()
                    host.frames(REST_FRAMES)
                    after, live_after = scene.mode.state(), core.composite_live()
                    checks["nothing_recorded_at_rest"] = after.get("records") == before.get("records")
                    checks["no_chain_at_rest"] = (live_after.get("scene_target_mips")
                                                  == live_before.get("scene_target_mips"))
                    checks["nothing_allocated_at_rest"] = (live_after["scene_target_allocations"]
                                                           == live_before["scene_target_allocations"])
            finally:
                scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
        # The declarations the core refuses (GPU-free admission through the same face).
        facts["refusals"] = _wave_floor_refusals(core, engine, app, host, packs)
        checks.update({f"refused_{k}": v.startswith("refused") for k, v in facts["refusals"].items()})
    finally:
        host.close()
        host_check._flush_deletes(app)
    _save(out, f"wave_{api}", frames)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def bucket_pixels_pair(size: tuple[int, int]) -> tuple[int, int]:
    from rendering.native.scene_targets import bucket_pixels

    return bucket_pixels(size[0]), bucket_pixels(size[1])


def _wave_floor_refusals(core, engine, app, host, packs: dict) -> dict:
    """What the core refuses of the new declarations: two outputs into one attachment without "extra_outputs"; mips of
    a target without mips; an unknown allocation."""
    from rendering.native.mode import ModePass, ModeTarget

    wp = _wave_module()
    passes, targets = wp.floor_program(packs)
    cases = {}
    no_discard, _ = wp.floor_program(packs, extra_outputs=False)
    cases["two_outputs_into_one_attachment"] = (no_discard, targets)
    flat = tuple(ModeTarget(t.name, t.colour, size=t.size, depth=t.depth, allocation="exact")
                 if t.name == "reflection" else t for t in targets)
    cases["mips_of_a_target_without_mips"] = (passes, flat)
    unknown = '{"name": "x", "size": [4, 4], "colour": [{"name": "c", "format": "rgba8"}], "allocation": "tight"}'
    results = {}
    scene = WaveScene(core, engine, host, wp.FLOOR, (ModePass("show", packs["shape_out1"], "replace"),), {})
    try:
        for label, (case_passes, case_targets) in cases.items():
            try:
                scene.mode.program(case_passes, wp.floor_settings(), targets=case_targets)
                results[label] = "admitted"
            except ValueError as exc:
                results[label] = f"refused: {exc}"
        try:
            scene.mode._module.composite_mode_program(scene.mode._handle(), json.dumps(
                {"passes": [{"name": "p", "blend": "replace", "target": "x"}], "targets": [json.loads(unknown)]}),
                [packs["prepass"]])
            results["unknown_allocation"] = "admitted"
        except ValueError as exc:
            results["unknown_allocation"] = f"refused: {exc}"
    finally:
        scene.close(app)
    return results


def round_wave_reference(out: Path) -> dict:
    wp = _wave_module()
    frames = {variant: wp.reference_frames(variant) for variant in wp.REFERENCE_VARIANTS}
    _save(out, "wave_reference", frames)
    again = wp.reference_frames("taps")
    import numpy as np

    repeat = all(np.array_equal(again[k]["array"], frames["taps"][k]["array"]) for k in again)
    return {"pass": repeat, "checks": {"reference_repeats_exactly": repeat},
            "facts": {"textures": sorted(frames["taps"])}}


WAVE_JUDGED = ("floor.checker", "floor.reflection", "floor.relief", "floor.mean", "prepass.colour",
               "slope_levels.colour")
#: Each control's textures that must leave rule (a)'s bound (the box's negative control), against the taps reference.
WAVE_CONTROLS = {"plain": ("floor.checker", "floor.reflection"), "bucket": ("floor.mean",),
                 "slope_rgba8": ("floor.relief", "slope_levels.colour")}


def wave_verdict(out: Path, apis) -> dict:
    """Rule (a) of every judged texture of each API's taps frames against the reference's taps frames; every
    reflection level against Python's glGenerateTextureMipmap (reported per level, the odd-built ones apart); each
    control failing where its box says; Python's hardware anisotropy against the taps (a fact)."""
    import numpy as np

    wp = _wave_module()
    reference = _load(out, "wave_reference")
    result: dict = {"pass": True, "apis": {}, "reasons": []}
    if not reference:
        return {"pass": False, "reasons": ["no reference frames"]}
    taps = reference["taps"]
    for api in apis:
        native = _load(out, f"wave_{api}")
        if not native:
            result["pass"] = False
            result["reasons"].append(f"{api}: no native frames")
            continue
        record: dict = {"rule_a": {}, "levels": {}, "controls": {}}
        for name in WAVE_JUDGED:
            judged_result = judged(native["taps"][name], taps[name], SCENE_RULE_A)
            record["rule_a"][name] = {k: judged_result.get(k) for k in ("pass", "differing", "reasons")}
            if not judged_result.get("pass"):
                result["pass"] = False
                result["reasons"].append(f"{api} {name}: rule (a)")
        size = wp.REFLECTION
        for level in range(1 + int(math.floor(math.log2(max(size))))):
            name = "reflection.colour" + (f"@{level}" if level else "")
            parent = (max(1, size[0] >> (level - 1)), max(1, size[1] >> (level - 1))) if level else size
            judged_result = judged(native["taps"][name], taps[name], SCENE_RULE_A)
            diff = np.abs(native["taps"][name]["array"].astype(np.float64) - taps[name]["array"].astype(np.float64))
            record["levels"][name] = {"pass": judged_result.get("pass"), "differing": judged_result.get("differing"),
                                      "max_abs": float(diff.max()),
                                      "made_from_odd": level > 0 and (parent[0] % 2 == 1 or parent[1] % 2 == 1)}
        if api == "opengl":
            failed_levels = [n for n, v in record["levels"].items() if not v["pass"]]
            if failed_levels:
                result["pass"] = False
                result["reasons"].append(f"opengl levels {failed_levels}: Python's own call should match")
        for variant, names in WAVE_CONTROLS.items():
            for name in names:
                judged_result = judged(native[variant][name], taps[name], SCENE_RULE_A)
                record["controls"][f"{variant}:{name}"] = {"fails_the_bound": not judged_result.get("pass"),
                                                           "differing": judged_result.get("differing")}
                if judged_result.get("pass"):
                    result["pass"] = False
                    result["reasons"].append(f"{api} control {variant} {name} stayed inside the bound")
        result["apis"][api] = record
        wp.sheet({"python taps": taps, f"{api} taps": native["taps"], f"{api} 1x (control)": native["plain"],
                  "python hardware": reference["hardware"]}, out / f"wave_sheet_{api}.png", reference="python taps")
    facts = {}
    for name in ("floor.checker", "floor.reflection", "floor.relief"):
        x, y = reference["taps"][name]["array"], reference["hardware"][name]["array"]
        diff = np.abs(x.astype(np.float64) - y.astype(np.float64))
        judged_result = judged(reference["taps"][name], reference["hardware"][name], SCENE_RULE_A)
        facts[name] = {"inside_rule_a": judged_result.get("pass"), "differing": judged_result.get("differing"),
                       "mean_abs": float(diff.mean()), "max_abs": float(diff.max())}
    result["taps_against_pythons_hardware_anisotropy"] = facts
    return result


def round_wave_limits(core, engine, app, packs: dict, folder: Path) -> dict:
    import post_stages

    wp = _wave_module()
    layer_packs = post_stages.bake_all(folder / "post_stages")
    host = core.hidden_host(*_host_size([CARD]))
    checks, facts = {}, {}
    try:
        passes, targets, images = wp.shape_program(packs, layer_packs)
        settings = _wave_shape_settings()
        facts["counts"] = {"passes": len(passes), "images": len(images), "targets": len(targets)}
        checks["the_shape_is_waveforms"] = (len(passes), len(images), len(targets)) == (
            wp.SHAPE_PASSES, wp.SHAPE_IMAGE_COUNT, 4)
        live_before = core.composite_live()
        started = time.perf_counter()
        import compute_passes

        schema = compute_passes.schema("state", (("u_frame", "f64", 1),))
        scene = WaveScene(core, engine, host, CARD, passes, settings, targets=targets, images=images, schema=schema,
                          unread=("u_frame",))
        try:
            state = scene.settle()
            facts["first_record_wall_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
            live = core.composite_live()
            facts["content_failure"] = state.get("content_failure")
            facts["last_reason"] = state.get("last_reason")
            facts["mode_resources_built"] = live.get("mode_resources", 0) - live_before.get("mode_resources", 0)
            facts["storage_images"] = live.get("compute_images")
            facts["records"] = state.get("records")
            checks["admitted_and_drawn"] = not state.get("content_failing") and state.get("records", 0) > 0
            checks["pipelines_built"] = facts["mode_resources_built"] > len(passes)
            host.frames(2)
            before, live_before_rest = scene.mode.state(), core.composite_live()
            host.frames(REST_FRAMES)
            after, live_after = scene.mode.state(), core.composite_live()
            checks["nothing_recorded_at_rest"] = after.get("records") == before.get("records")
            facts["dispatches_per_record"] = live_after.get("compute_dispatches", 0) - live_before_rest.get(
                "compute_dispatches", 0)
            checks["nothing_dispatched_at_rest"] = facts["dispatches_per_record"] == 0
            checks["nothing_built_at_rest"] = live_after.get("mode_resources") == live_before_rest.get("mode_resources")
            refusals = {}
            for label, options in (("one_pass_past", {"extra_pass": True}), ("one_image_past", {"extra_image": True})):
                case_passes, case_targets, case_images = wp.shape_program(packs, layer_packs, **options)
                try:
                    scene.mode.program(case_passes, settings, targets=case_targets, images=case_images,
                                       unread=("u_frame",))
                    refusals[label] = "admitted"
                except ValueError as exc:
                    refusals[label] = f"refused: {exc}"
            fifth = targets + (type(targets[3])("fifth", targets[3].colour, size=(8, 8)),)
            try:
                scene.mode.program(passes, settings, targets=fifth, images=images, unread=("u_frame",))
                refusals["one_target_past"] = "admitted"
            except ValueError as exc:
                refusals["one_target_past"] = f"refused: {exc}"
            facts["refusals"] = refusals
            checks["one_pass_past_refused_with_its_reason"] = "28 passes" in refusals["one_pass_past"]
            checks["one_image_past_refused_with_its_reason"] = "at most 9 storage images" in refusals["one_image_past"]
            checks["one_target_past_refused_with_its_reason"] = "at most 4 targets" in refusals["one_target_past"]
            host.frames(2)
            checks["the_drawn_program_kept"] = not scene.mode.state().get("content_failing")
        finally:
            scene.close(app)
            host.frames(2)
            host_check._flush_deletes(app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _wave_shape_settings() -> dict:
    """The shape's settings: the members of the transparent layer's block (post_stages' ``eb_layer1``, drawn as the
    ribbon body) and the overlay_glow composite's, from post_stages' values; its stand-ins have no block."""
    import re

    import post_stages

    names = set(re.findall(r"\bu_\w+", post_stages.texts()["eb_layer1"])) | set(post_stages.STAGE_MEMBERS["overlay_glow"])
    return {k: v for k, v in post_stages.SETTINGS.items() if k in names}


def round_wave_filter(core, engine, app, packs: dict) -> dict:
    wp = _wave_module()
    host = core.hidden_host(*_host_size([CARD]))
    checks, facts = {}, {}
    try:
        passes, images = wp.float_filter_program(packs)
        scene = WaveScene(core, engine, host, CARD, passes, {}, images=images)
        try:
            state = scene.settle()
            device = (state.get("storage") or {}).get("device") or {}
            facts["device_facts"] = {k: device.get(k) for k in ("linear_filter_formats", "float32_linear_control")}
            facts["drawn"] = {k: state.get(k) for k in ("content_failing", "content_failure", "records")}
            checks["the_device_reports_linear_filtering_of_rgba32f"] = (
                (device.get("linear_filter_formats") or {}).get("rgba32f") is True)
            checks["the_device_reports_linear_filtering_of_r32f"] = (
                (device.get("linear_filter_formats") or {}).get("r32f") is True)
            checks["rgba32f_read_linearly_draws"] = not state.get("content_failing")
            core.module.compute_control(json.dumps({"no_float32_linear": True}))
            try:
                passes32, images32 = wp.float_filter_program(packs)
                scene.mode.program(passes32, {}, images=images32)
                refused = scene.settle()
                facts["faked_device"] = {k: refused.get(k) for k in ("content_failing", "content_failure")}
                checks["the_faked_device_refuses_it_with_its_reason"] = bool(refused.get("content_failing")) and (
                    "filters the storage image 'field' linearly" in (refused.get("content_failure") or ""))
                passes16, images16 = wp.float_filter_program(packs, fmt="rgba16f")
                scene.mode.program(passes16, {}, images=images16)
                half = scene.settle()
                facts["faked_device_rgba16f"] = {k: half.get(k) for k in ("content_failing", "content_failure")}
                checks["the_faked_device_draws_rgba16f"] = not half.get("content_failing")
            finally:
                core.module.compute_control(json.dumps({"no_float32_linear": False}))
            passes_again, images_again = wp.float_filter_program(packs)
            scene.mode.program(passes_again, {}, images=images_again)
            again = scene.settle()
            facts["recovered"] = {k: again.get(k) for k in ("content_failing", "content_failure")}
            checks["the_real_device_draws_it_again"] = not again.get("content_failing")
        finally:
            scene.close(app)
            host.frames(2)
            host_check._flush_deletes(app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the child

def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api in ("opengl", "reference"):
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="scene-target-check")
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
    with tempfile.TemporaryDirectory(prefix="srpss_n31_") as scratch:
        folder = Path(scratch)
        packs = _scene_module().bake_all(folder)
        # N5.4: the waveform_primitives scenes' packs, only when one of its rounds runs.
        wave_packs = _wave_module().bake_all(folder / "wave") if set(args.rounds) & set(WAVE_ROUNDS) else {}
        try:
            if args.api == "reference":
                if "wave_floor" in args.rounds:
                    try:
                        record["wave_reference"] = round_wave_reference(out)
                    except Exception:
                        record["wave_reference"] = {"pass": False, "error": traceback.format_exc()}
                if "parity" in args.rounds or "placement_control" in args.rounds:
                    record["reference"] = round_reference(core, packs, out)
                if "python_cost" in args.rounds:
                    try:
                        record["python_cost"] = round_python_cost(core, packs)
                    except Exception:
                        record["python_cost"] = {"pass": False, "error": traceback.format_exc()}
            else:
                for name in args.rounds:
                    if vulkan:
                        core.set_vulkan_phase(f"n31 {name}")
                    try:
                        if name == "parity":
                            record[name] = round_parity(core, engine, app, args.api, packs, out)
                        elif name == "placement_control":
                            core.scene_target_control("content_at_top", 1)
                            try:
                                record[name] = round_parity(core, engine, app, args.api, packs, out, top_control=True)
                            finally:
                                core.scene_target_control("content_at_top", 0)
                        elif name == "msaa":
                            record[name] = round_msaa(core, engine, app, args.api, packs)
                        elif name == "rest":
                            record[name] = round_rest(core, engine, app, packs)
                        elif name == "resize":
                            record[name] = round_resize(core, engine, app, packs)
                        elif name == "resize_control":
                            core.scene_target_control("one_pixel_bucket", 1)
                            try:
                                record[name] = round_resize(core, engine, app, packs, one_pixel_control=True)
                            finally:
                                core.scene_target_control("one_pixel_bucket", 0)
                        elif name == "retire":
                            record[name] = round_retire(core, engine, app, packs, folder)
                        elif name == "readback_metadata":
                            record[name] = round_readback_metadata(core, engine, app, packs, folder)
                        elif name in ("scissor", "scissor_control"):
                            record[name] = round_scissor(core, engine, app, args.api, folder, out,
                                                         skip_control=name == "scissor_control")
                        elif name in ("partial_retire_control", "invalidation_control"):
                            case = "mid_allocation" if name == "partial_retire_control" else "scene_graph_invalidated"
                            record[name] = _retire_edge(core, engine, app, packs, case, skip_control=True)
                        elif name == "cost":
                            record[name] = round_cost(core, engine, app, packs, folder)
                        elif name == "prime_control" and vulkan:
                            record[name] = round_prime_control(core, engine, app, packs)
                        elif name == "cost_parts":
                            record[name] = round_cost_parts(core, engine, app, packs)
                        elif name == "wave_floor":
                            record[name] = round_wave_floor(core, engine, app, args.api, wave_packs, out)
                        elif name == "wave_limits":
                            record[name] = round_wave_limits(core, engine, app, wave_packs, folder)
                        elif name == "wave_filter":
                            record[name] = round_wave_filter(core, engine, app, wave_packs)
                    except Exception:
                        record[name] = {"pass": False, "error": traceback.format_exc()}
        finally:
            host_check._flush_deletes(app)
            record["live_hosts_at_end"] = core.live_hosts()
            record["composites_at_end"] = core.composite_live()
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
    if args.api == "reference":
        record["rounds"] = [name for name in ("reference", "python_cost", "wave_reference") if name in record]
    return record


def prime_control_validation(record: dict) -> dict:
    """The depth prime's negative control read from the run's validation: synchronisation hazards on the depth load
    where the prime was skipped, none where it ran, and nothing else unexplained (Qt's recorded defects excused)."""
    groups = (record.get("validation") or {}).get("attribution") or []

    def hazards(phase: str) -> int:
        return sum(int(g.get("count", 0)) for g in groups
                   if g.get("phase") == phase and str(g.get("id", "")).startswith("SYNC-HAZARD"))

    skipped_phases = ("n31 prime skipped", "n31 resolve prime skipped")
    other = sorted({str(g.get("id")) for g in groups if g.get("severity") == "error" and not g.get("qt_defect")
                    and g.get("phase") not in skipped_phases})
    # Anything unexcused outside the skipped phases (a recorded Qt defect included: B is excused only in 'discard').
    elsewhere = sorted({f"{g.get('phase')}: {g.get('id')}" for g in groups
                        if g.get("severity") == "error" and g.get("phase") not in skipped_phases
                        and not g.get("excused") and g.get("qt_defect") != "A"})
    skipped, primed = hazards("n31 prime skipped"), hazards("n31 prime primed")
    resolve_skipped, resolve_primed = hazards("n31 resolve prime skipped"), hazards("n31 resolve prime primed")
    return {"hazards_with_the_prime_skipped": skipped, "hazards_with_the_prime": primed,
            "hazards_with_the_resolve_prime_skipped": resolve_skipped,
            "hazards_with_the_resolve_prime": resolve_primed,
            "other_unexplained_errors": other, "unexcused_outside_the_skipped_phases": elsewhere,
            "pass": skipped > 0 and primed == 0 and resolve_skipped > 0 and resolve_primed == 0 and not other
            and not elsewhere and bool((record.get("validation") or {}).get("layer_loaded"))}


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    if record.get("exit_code", 0) != 0:
        return False, [f"{api}: child process failed ({record['exit_code']})"]
    if api == "reference":
        rounds = [name for name in ("reference", "python_cost", "wave_reference") if name in record]
        failed = [f"{name}: {record[name].get('error') or 'failed'}"[:1500] for name in rounds
                  if not record[name].get("pass")]
        if not rounds:
            failed.append(f"reference: {record.get('error')}")
        return not failed, failed
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if (api == "vulkan" and "cost" in (record.get("rounds") or []) and record.get("instance_created")
            and not (record.get("validation") or {}).get("layer_loaded")):
        # Audit 2, H1: the cost round draws the only long runs of consecutive multisampled records (no readback between
        # them to order a resolve), so it is the gate's synchronisation proof: never judged without the layer.
        failed.append("vulkan cost: the validation layer did not load (the cost round's consecutive multisampled "
                      "records are the gate's synchronisation proof; pass --layer-path)")
    if api == "vulkan" and "prime_control" in (record.get("rounds") or []):
        # The negative control is expected to make validation unclean in its skipped phase, and only there.
        control = prime_control_validation(record)
        record.setdefault("prime_control", {})["validation_control"] = control
        failed = [reason for reason in failed if not reason.startswith(f"{api}: validation not clean")]
        if not control["pass"]:
            failed.append(f"{api} prime control: {json.dumps(control)}")
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        if any(live.get(key) for key in ("items", "surfaces", "surface_resources", "mode_sources", "mode_resources",
                                         "scene_targets", "scene_target_textures", "scene_target_bytes")):
            failed.append(f"{api}: composites or scene targets left at the end ({live})")
    return not failed, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS),
                        choices=(*ROUNDS, *CONTROL_ROUNDS, *PYTHON_ROUNDS, *WAVE_ROUNDS))
    parser.add_argument("--label", default=None, help="default n31_scene_targets (n54_waveform_primitives for the "
                                                      "wave rounds alone)")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=(*APIS, "reference"), help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if not args.child and "placement_control" in args.rounds and args.apis != ["opengl"]:
        parser.error("placement_control uses --apis opengl (its oracle is the Python OpenGL renderer)")
    for control in ("placement_control", "resize_control", "partial_retire_control", "invalidation_control",
                    "scissor_control", "readback_metadata"):
        if control in args.rounds and len(args.rounds) != 1:
            parser.error(f"{control} runs alone in its own child process")

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

    wave_only = set(args.rounds) <= set(WAVE_ROUNDS)   # N5.4's rounds alone: their own topic
    label = args.label or ("n54_waveform_primitives" if wave_only else "n31_scene_targets")
    out = artifact_paths.evidence_dir("native_core", "n5_4" if wave_only else "n3_1", label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    children = [a for a in APIS if a in args.apis and set(args.rounds) - set(PYTHON_ROUNDS)]
    if (("parity" in args.rounds or "placement_control" in args.rounds) and "opengl" in args.apis) \
            or "python_cost" in args.rounds or "wave_floor" in args.rounds:
        children.append("reference")
    for api in children:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)  # an interrupted earlier run cannot supply this child's proof
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *(args.rounds if api == "reference"
                                 else [r for r in args.rounds if r not in PYTHON_ROUNDS])]
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
    cross = None
    placement_control = placement_control_verdict(out) if "placement_control" in args.rounds else None
    if placement_control is not None and not placement_control["pass"]:
        failed.append("content-at-top control: the Python oracle did not reject the broken edge reads")
    if "parity" in args.rounds:
        cross = cross_compare(out)
        for rule in ("rule_a", "rule_b"):
            needed = ("opengl" in args.apis) if rule == "rule_a" else ("vulkan" in args.apis and "opengl" in args.apis)
            if needed and not cross[rule].get("pass"):
                failed.append(f"{rule}: " + json.dumps({k: v for k, v in cross[rule].get("compared", {}).items()
                                                        if v.get("past", 0) != 0} or cross[rule])[:1500])
    wave = None
    if "wave_floor" in args.rounds:
        # N5.4: rule (a) of the floor scene per API against the Python reference, the levels, the controls.
        wave = wave_verdict(out, [api for api in APIS if api in args.apis])
        if not wave["pass"]:
            failed.append("wave_floor: " + "; ".join(wave.get("reasons", []))[:1500])
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment, "wave_floor": wave,
               "require_validation": args.require_validation, "cross": cross, "placement_control": placement_control,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if cross is not None:
        print("cross: " + json.dumps({rule: {"pass": v.get("pass"), "exact": len(v.get("exact", []))}
                                      for rule, v in cross.items()}))
    print(f"evidence: {out / 'summary.json'} (the work folder holds the frames: delete it once judged)")
    print("N31 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
