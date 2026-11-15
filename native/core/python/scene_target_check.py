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
  resize     (each API) the card dragged 800 -> 1000 -> 800 px wide in 2 px steps: the scene's allocation after each
             step equals D14's rule (grown at once, shrunk only two buckets below), the reallocations counted against a
             rule that re-buckets at every change (the control), the explicit-size target never reallocated; after the
             drag the content equals a fresh item's at that size.
  retire     (each API) a program without targets releases them on a live item (counts to zero) and one with targets
             makes them again; the item's destruction leaves nothing (targets, textures, bytes, readbacks); with Vulkan
             validation (synchronisation validation) through every round.
  cost       (each API) at 2560x1440 and 3840x2160: the surface's GPU time (the content's whole record: every target
             pass) median and p90, single-sampled and 4x (the 4x minus 1x difference bounds the resolves: choice G's
             budget, 0.3 ms at 2560x1440 and 0.6 ms at 4K); the light attachment's clear (the ambient target at 2048 x
             1152 with and without its light attachment, nothing glowing: choice F); the first frame's wall time with a
             new allocation against a steady one; the thread probe (no Python thread state on the render thread).
Run alone (not in the default set):
  prime_control  (--apis vulkan) rule C for depth's negative control: the scene with the depth prime skipped, then with
             it, at one sample and at 4x; synchronisation validation shows read-after-write hazards on the depth load
             only where it was skipped.
  cost_parts (each API) where the four-sample time goes at 4K: a clearing draw and plane, three passes, a colour read,
             the capture split; each at 1x and 4x.
  python_cost (the reference child, OpenGL) the Python renderer's ``SceneTarget`` on the same load at 2560x1440 and 4K,
             1x and 4x (the lead's measure for the native four-sample figure: accepted when no worse).

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

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("parity", "msaa", "rest", "resize", "retire", "cost")
# Run on its own (its skipped phase is expected to show hazards): --apis vulkan --rounds prime_control
CONTROL_ROUNDS = ("prime_control", "cost_parts")
# The Python renderer's cost on the same load (the reference child, OpenGL): --rounds python_cost
PYTHON_ROUNDS = ("python_cost",)
CHILD_TIMEOUT_S = 1500
MARGIN = 8
CARD = (480, 270)                  # the item's logical size (parity, msaa, rest, retire)
DPRS = (1.0, 1.5)
AMBIENT = (300, 170)               # the ambient target's explicit size (parity)
REST_FRAMES = 4
HALF_ULP = 2.0 ** -10              # one float16 ulp, relative
RULE_A_LEVELS = 1                  # RGBA8 (the tie budget of D13: a NativeFragmentPass within 1 level)
RULE_A_TIE_PIXELS = 8
DEPTH_TOLERANCE = 2e-7             # N0.3 scene 2's bound
DRAG = (800, 1000, 2)              # the resize round's widths (start, end, step); its card is 400 px high
DRAG_HEIGHT = 400
COST_HOSTS = ((2560, 1440), (3840, 2160))
COST_AMBIENT = (2048, 1152)
COST_FRAMES = 240
COST_MIN_SAMPLES = 30               # Qt's OpenGL backend reports a GPU time only for frames whose query was ready
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


def _content(entry: dict):
    """The content region of a readback: image rows [H-h, H), columns [0, w) (D14 point 2)."""
    width, height = entry["content"]
    rows = entry["array"].shape[0]
    return entry["array"][rows - height:, :width]


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

PARITY_CASES = (("dpr1", 1.0, 1.0), ("dpr1.5", 1.5, 1.0), ("glow_off", 1.0, 0.0))


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


def round_parity(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    st = _scene_module()
    host = core.hidden_host(*_host_size([CARD], DPRS))
    checks, facts, frames = {}, {}, {}
    try:
        for case, dpr, glow in PARITY_CASES:
            host.set_device_pixel_ratio(dpr)
            scene = Scene(core, engine, host, CARD, dpr, packs, glow=glow)
            try:
                frames[case] = scene.targets(app)
                state = scene.mode.state()
                facts[f"{case}_state"] = state.get("scene_targets")
                result = analytic(frames[case], dict(st.settings(ambient_size=AMBIENT), u_glow=glow))
                facts[f"{case}_analytic"] = result
                checks[f"{case}_analytic"] = result["pass"]
                content = frames[case]["scene.colour"]["content"]
                checks[f"{case}_scene_content_is_the_surface"] = content == _pixels(CARD, dpr)
                checks[f"{case}_ambient_content_is_its_explicit_size"] = (
                    frames[case]["ambient.coverage"]["content"] == AMBIENT)
                # D14 point 12: both targets share one clear value and do not persist, so their first runs clear
                # through the load op (the parity above is drawn that way).
                checks[f"{case}_targets_clear_through_their_load_op"] = all(
                    t.get("clear_target") and t.get("fast_clear") for t in state["scene_targets"]["targets"])
            finally:
                scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
        host.set_device_pixel_ratio(1.0)
        # D14 point 12's control: the same targets declared "persist" keep the load and the clearing draw, and draw
        # the same pixels as the fast clear (single-sampled and at 4x).
        from dataclasses import replace

        for samples in (1, 4):
            fast_scene = Scene(core, engine, host, CARD, 1.0, packs, samples=samples)
            try:
                fast = fast_scene.targets(app)
            finally:
                fast_scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
            kept = tuple(replace(t, persist=True) for t in st.targets(samples=samples, ambient_size=AMBIENT))
            persist_scene = Scene(core, engine, host, CARD, 1.0, packs, targets=kept)
            try:
                persisted = persist_scene.targets(app)
                persist_state = persist_scene.mode.state()["scene_targets"]["targets"]
            finally:
                persist_scene.close(app)
                host.frames(2)
                host_check._flush_deletes(app)
            same = {key: compare(fast[key], persisted[key])["exact"] for key in fast}
            facts[f"persist_control_x{samples}"] = same
            checks[f"persist_control_x{samples}_draws_the_same_through_the_clearing_draw"] = (
                all(same.values()) and set(fast) == set(persisted)
                and not any(t.get("clear_target") for t in persist_state))
    finally:
        host.close()
        host_check._flush_deletes(app)
    _save(out, f"parity_{api}", frames)
    _sheet(out, api, frames)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


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


def round_resize(core, engine, app, packs: dict) -> dict:
    from rendering.native.scene_targets import bucket_pixels, next_allocation

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

    control, previous = [], None
    for width in widths:
        previous = (bucket_pixels(width), bucket_pixels(DRAG_HEIGHT))
        control.append(previous)
    checks["allocation_follows_the_rule_at_every_step"] = observed == expected
    checks["fewer_reallocations_than_rebucketing_every_change"] = reallocations(observed) < reallocations(control)
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
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


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
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": facts["skipped"]["depth_primes"] == 0 and facts["primed"]["depth_primes"] > 0, "facts": facts,
            "checks": {"the_control_records_no_prime_and_the_product_path_does":
                       facts["skipped"]["depth_primes"] == 0 and facts["primed"]["depth_primes"] > 0}}


COST_PARTS = ("clear", "clear_persist", "planes2", "draws", "read", "capture", "capture_persist")


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


def _timed(host, scene, settings: dict, frames: int) -> dict:
    """The surface's GPU time (kind 2) over ``frames`` records, each forced by a setting that alternates."""
    host.set_gpu_timer(True)
    host.frames(4)
    host.gpu_samples()
    for index in range(frames):
        scene.mode.settings(dict(settings, u_hdr_gain=settings["u_hdr_gain"] + (0.001 if index % 2 else 0.0)))
        host.frames(1)
    host.frames(4)
    times = sorted(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
    host.set_gpu_timer(False)
    return _time_summary(times)


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
                host.set_gpu_timer(True)
                host.frames(4)
                host.gpu_samples()
                for index in range(COST_FRAMES):
                    scene.mode.settings(dict(settings, u_radius=0.08 + (0.0001 if index % 2 else 0.0)))
                    host.frames(1)
                host.frames(4)
                times = sorted(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
                host.set_gpu_timer(False)
                clear[label] = {"samples": len(times),
                                "median_ms": round(times[len(times) // 2] / 1e6, 4) if times else None}
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


def reference_frames(core, packs: dict, case_dpr: float, glow: float) -> dict:
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
    width, height = _pixels(CARD, case_dpr)
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
    for case, dpr, glow in PARITY_CASES:
        frames[case] = reference_frames(core, packs, dpr, glow)
    _save(out, "parity_reference", frames)
    return {"pass": True, "cases": [c for c, _d, _g in PARITY_CASES]}


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
                per[f"{case}|{texture}"] = c
                ok = ok and c["past"] <= (RULE_A_TIE_PIXELS if rule == "rule_a" else 0) and c["past"] >= 0
        result[rule] = {"pass": ok and bool(per), "compared": per,
                        "exact": sorted(k for k, v in per.items() if v["exact"])}
    return result


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
        try:
            if args.api == "reference":
                if "parity" in args.rounds:
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
                        elif name == "msaa":
                            record[name] = round_msaa(core, engine, app, args.api, packs)
                        elif name == "rest":
                            record[name] = round_rest(core, engine, app, packs)
                        elif name == "resize":
                            record[name] = round_resize(core, engine, app, packs)
                        elif name == "retire":
                            record[name] = round_retire(core, engine, app, packs, folder)
                        elif name == "cost":
                            record[name] = round_cost(core, engine, app, packs, folder)
                        elif name == "prime_control" and vulkan:
                            record[name] = round_prime_control(core, engine, app, packs)
                        elif name == "cost_parts":
                            record[name] = round_cost_parts(core, engine, app, packs)
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
        record["rounds"] = [name for name in ("reference", "python_cost") if name in record]
    return record


def prime_control_validation(record: dict) -> dict:
    """The depth prime's negative control read from the run's validation: synchronisation hazards on the depth load
    where the prime was skipped, none where it ran, and nothing else unexplained (Qt's recorded defects excused)."""
    groups = (record.get("validation") or {}).get("attribution") or []

    def hazards(phase: str) -> int:
        return sum(int(g.get("count", 0)) for g in groups
                   if g.get("phase") == phase and str(g.get("id", "")).startswith("SYNC-HAZARD"))

    other = sorted({str(g.get("id")) for g in groups if g.get("severity") == "error" and not g.get("qt_defect")
                    and g.get("phase") != "n31 prime skipped"})
    skipped, primed = hazards("n31 prime skipped"), hazards("n31 prime primed")
    return {"hazards_with_the_prime_skipped": skipped, "hazards_with_the_prime": primed,
            "other_unexplained_errors": other, "pass": skipped > 0 and primed == 0 and not other
            and bool((record.get("validation") or {}).get("layer_loaded"))}


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    if api == "reference":
        rounds = [name for name in ("reference", "python_cost") if name in record]
        failed = [f"{name}: {record[name].get('error') or 'failed'}"[:1500] for name in rounds
                  if not record[name].get("pass")]
        if not rounds:
            failed.append(f"reference: {record.get('error')}")
        return not failed, failed
    ok, failed = host_check.api_verdict(api, record, require_validation)
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
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=(*ROUNDS, *CONTROL_ROUNDS, *PYTHON_ROUNDS))
    parser.add_argument("--label", default="n31_scene_targets")
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

    out = artifact_paths.evidence_dir("native_core", "n3_1", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    children = [a for a in APIS if a in args.apis and set(args.rounds) - set(PYTHON_ROUNDS)]
    if ("parity" in args.rounds and "opengl" in args.apis) or "python_cost" in args.rounds:
        children.append("reference")
    for api in children:
        child_json = out / f"child_{api}.json"
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
    if "parity" in args.rounds:
        cross = cross_compare(out)
        for rule in ("rule_a", "rule_b"):
            needed = ("opengl" in args.apis) if rule == "rule_a" else ("vulkan" in args.apis and "opengl" in args.apis)
            if needed and not cross[rule].get("pass"):
                failed.append(f"{rule}: " + json.dumps({k: v for k, v in cross[rule].get("compared", {}).items()
                                                        if v.get("past", 0) != 0} or cross[rule])[:1500])
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "require_validation": args.require_validation, "cross": cross,
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
