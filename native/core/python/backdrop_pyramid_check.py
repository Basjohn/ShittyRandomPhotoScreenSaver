"""N5.7b's proof of the card-material backdrop pyramid on the native core (D7 points 2 to 6; Current_Plan.md section
N2b), through ``rendering.native`` and the product's own route (``SurfaceBackdropOwner`` on the native background's
backend, ``rendering/quick/render/native_surface_backdrop.py``), in hidden hosts only (never a window on a screen).

The display lies in the window as the product lays it out (background_layer_check's scene: its root at a whole device
pixel inside an overscanned window), at dpr 1 and 1.5, on real PERSONALSET wallpapers: a dark one
(Usu_Underwater_Lab_1440p.png) and a bright one (670483.jpg), processed by the product's worker arithmetic.

Rounds (one child process per API; OpenGL first, its levels and stills kept for Vulkan's comparison):
  levels    every level of the pyramid (1/2 .. 1/32, the 1/16 scratch, the output's light and heavy levels) read back
            from the core and, on OpenGL, from the Python pyramid in the same scene (its ``BackdropPipeline`` read on the
            render thread right after its refresh): rule (a) OpenGL native against Python under LEVEL_RULE_A, pixel by
            pixel (exact recorded as a fact), with no dimming; dimming 0.35 recorded against Python (the Python pyramid
            reads the 8-bit blend, the core blends once: a fact); rule (b) Vulkan native against OpenGL native under
            LEVEL_RULE_B (main); a negative control (another photo's level differs). Rows normalised top-down.
  cards     each material's card (Acrylic, Glass, Frosted, Mica, Smoked: the product's MaterialSurface.qml, unchanged)
            over both photos: OpenGL with the Python pyramid (today's), OpenGL with the native pyramid, Vulkan with the
            native pyramid. OpenGL native against today's exact (CARD_RULE_A) inside the cards; Vulkan against OpenGL
            native: the one-level pixels per material under CARD_RULE_B, and the share of card pixels more than 1 level
            apart (the material's float grain hash, accepted 14 Nov on the composite) at most CARD_OUTLIER_SHARE. One sheet per photo for the lead's look review.
  cost      the build's GPU time (the core's GPU timer, kind 4 "backdrop") and render-thread CPU time at 2560 x 1440 and
            3840 x 2160, against D7 point 3's budgets (0.3 ms and 0.6 ms, p90).
  rest      nothing at rest (no build, no GPU sample); a photo change builds once (at the commit's frame: on Vulkan the
            hand-over frame builds nothing); a dimming change builds once, the same dimming none; before any photo the
            cards are exactly Normal (fail closed); parked (demand 0): no QRhi object, no build on a photo change, the
            frame driver sees no pyramid; woken: one build.
  transition D7 point 3: a Crossfade drawn on the layer (N5.2a), its clock held: one build per layer frame, the glass
            card changing with every step, nothing after the run.
  route     ``SurfaceBackdropOwner`` on the product route: native on Vulkan (its item draws a card's material over the
            native layer), Python on OpenGL; retire destroys the native item.
  lifetime  the item destroyed (its pyramid released on the render thread), and the host closed with a pyramid alive
            (the scene graph's invalidation releases it); nothing left.
Facts: the frame driver's thread probe (no Python thread state), validation per phase (Vulkan).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/backdrop_pyramid_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds levels cards cost rest route lifetime] [--label n57b_backdrop_pyramid]
Evidence: .artifacts/evidence/native_core/n5_7b/<date>_<label>/ (summary.json; level and card sheets; the OpenGL arrays
for Vulkan's comparison in work/). Exit 0 whenever the harness ran; the verdict is the last printed line
("N57B VERDICT PASS" or "N57B VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import statistics
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

from tools import pixel_tolerance as pt  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("levels", "cards", "cost", "rest", "transition", "route", "lifetime")
CHILD_TIMEOUT_S = 1800
PHOTO_FOLDER = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET")
PHOTOS = (("dark", "Usu_Underwater_Lab_1440p.png"), ("bright", "670483.jpg"))
CHANGE_PHOTO = "UsuScene1.png"
DPRS = (1.0, 1.5)
DIMMING_FACT = 0.35
#: The product's own placement (rendering/quick/window.py, R-63): one logical pixel of overscan on one exterior edge,
#: so the window is one device pixel taller than the display at dpr 1 and its halving is not exact.
PRODUCT_WINDOW = (1280, 721)
PRODUCT_OFFSET = (0, 1)
MATERIALS = ("acrylic", "glass", "frosted", "mica", "smoked")
#: Cards in display-logical pixels at dpr 1: one per material, over busy and flat regions, one near the display's edge.
CARD_RECTS = ((24, 24, 300, 180), (360, 70, 300, 180), (700, 260, 300, 180), (960, 520, 300, 180),
              (90, 430, 300, 180))
CARD_INSET = 4                      # device pixels kept off the card's anti-aliased edge in the comparison
CARD_NORMAL = "#80204060"           # the cards' Normal fill (premultiplied over black: 16, 32, 48)
COST_SIZES = ((2560, 1440), (3840, 2160))
BUDGET_MS = {(2560, 1440): 0.3, (3840, 2160): 0.6}   # D7 point 3, per build, the development GPU
TIMED_BUILDS = 60
MAX_TIMED_BUILDS = 600           # the cost round's bound while OpenGL's GPU times are still arriving
CARD_OUTLIER_SHARE = 0.001          # Vulkan cards: share of card pixels more than 1 level from OpenGL's


def _cap(measured: int) -> int:
    """A scatter cap: the measured worst times 1.5, rounded up (D12, "The pixel tolerance")."""
    return -(-measured * 3 // 2)


#: The pyramid's levels are judged pixel by pixel by the shared tolerance (``tools/pixel_tolerance.py``, D12 "The
#: pixel tolerance"), each level against its own measured worst: the levels differ in size by a factor of 1000, so one
#: pixel count for all would let a whole small level shift. Every level is opaque (no mask). The pixels that differ are
#: single values within float error of a half level (scatter), exactly one level off.
#: Rule (a), OpenGL native against the Python pyramid, undimmed (the dimmed case stays a fact: the Python pyramid reads
#: the 8-bit blend, the core blends once). Measured worst a frame over both photos at three placements: eighth 545,
#: half 9,759 (and one tie, 2 levels, at the product's odd window: the GL blit's fixed-point positions put a first-level
#: texel on a sharp edge), heavy 493, light 2,123, quarter 2,257, scratch 121, sixteenth 147, thirty_second 34.
LEVEL_RULE_A_WORST = {"eighth": 545, "half": 9759, "heavy": 493, "light": 2123, "quarter": 2257, "scratch": 121,
                      "sixteenth": 147, "thirty_second": 34}
LEVEL_RULE_A_TIES = {"half": 1}
LEVEL_RULE_A = {name: pt.Tolerance(f"backdrop level {name}, OpenGL native against Python (rule a)",
                                   scatter_pixels=_cap(worst), tie_pixels=_cap(LEVEL_RULE_A_TIES.get(name, 0)))
                for name, worst in LEVEL_RULE_A_WORST.items()}
#: Rule (b), Vulkan native against OpenGL native (all seven cases): eighth 305, half 2, heavy 790, light 1,328, quarter
#: 1,125, scratch 192, sixteenth 80, thirty_second 35; no tie.
LEVEL_RULE_B_WORST = {"eighth": 305, "half": 2, "heavy": 790, "light": 1328, "quarter": 1125, "scratch": 192,
                      "sixteenth": 80, "thirty_second": 35}
LEVEL_RULE_B = {name: pt.Tolerance(f"backdrop level {name}, Vulkan against OpenGL (rule b)", scatter_pixels=_cap(worst))
                for name, worst in LEVEL_RULE_B_WORST.items()}
#: The cards. OpenGL native against today's (rule (a)): bit for bit the same (measured: 0 differing pixels in all ten
#: card regions). Vulkan against OpenGL native (rule (b)): the one-level pixels are scatter, per material (measured
#: worst a card region of 50,224 pixels: acrylic 1,565, glass 549, frosted 1,238, mica 809, smoked 605); the pixels
#: past one level (the material's float grain hash, accepted 14 Nov on the composite, measured up to 12 levels, at most
#: 8 pixels a region) stay bounded only by CARD_OUTLIER_SHARE: the shared tolerance has no class for them (its ties
#: stop at 2 levels), so routing them is the lead's decision (D12).
CARD_RULE_A = pt.EXACT
CARD_RULE_B_WORST = {"acrylic": 1565, "glass": 549, "frosted": 1238, "mica": 809, "smoked": 605}
CARD_RULE_B = {name: pt.Tolerance(f"backdrop card {name}, Vulkan against OpenGL (rule b, one-level pixels)",
                                  scatter_pixels=_cap(worst)) for name, worst in CARD_RULE_B_WORST.items()}
MAX_WAIT_FRAMES = 30
REST_FRAMES = 6
SHEET_TILE = (320, 180)
_ALLOWED_ENV: set[str] = set()

#: The Python pyramid's levels as read on the render thread right after a refresh (OpenGL only, harness only).
_PYTHON_CAPTURE: dict = {"armed": False, "levels": None}


# --------------------------------------------------------------------------------------------------- comparisons


def compare(a, b) -> dict:
    import numpy as np

    if a.shape[:2] != b.shape[:2]:
        return {"equal": False, "shape": [list(a.shape), list(b.shape)], "max_level": 255, "differing_pixels": -1}
    difference = np.abs(a[..., :3].astype(np.int16) - b[..., :3].astype(np.int16)).max(axis=2)
    return {"equal": int(difference.max()) == 0, "max_level": int(difference.max()),
            "differing_pixels": int(np.count_nonzero(difference)),
            "over_1": int(np.count_nonzero(difference > 1)), "pixels": int(difference.size)}


def _level_name(name: str) -> str:
    """The pyramid level of a stored name (``<case>|<level>`` in the level sets; a bare ``<level>`` in a case's dict)."""
    return name.rsplit("|", 1)[-1]


def judge_levels_rule_a(native: dict, reference: dict, cases) -> dict:
    """Rule (a): every level of each case (``native[case][level]`` against ``reference[case][level]``, top-down RGBA
    rows) under its own ``LEVEL_RULE_A`` bound, pixel by pixel. A level with no bound fails."""
    judged = []
    for case in cases:
        for name, rows in native[case].items():
            tolerance = LEVEL_RULE_A.get(name)
            judged.append(pt.judge(rows[..., :3], reference[case][name][..., :3], tolerance) if tolerance is not None
                          else {"pass": False, "reasons": [f"no bound for level {name}"]})
    return pt.summarise(judged)


def judge_cards_rule_a(native_regions: dict, today_regions: dict) -> dict:
    """Rule (a) in the cards: every material's card region of the native pyramid against today's (Python pyramid),
    exact; ``native_regions[photo][material]``."""
    return pt.summarise(pt.judge(native_regions[label][m][..., :3], today_regions[label][m][..., :3], CARD_RULE_A)
                        for label in native_regions for m in MATERIALS)


def _levels_top_down(levels: dict, rows_up: bool) -> dict:
    return {name: (rows[::-1].copy() if rows_up else rows) for name, rows in levels.items()}


def _native_levels(backdrop) -> dict | None:
    import numpy as np

    read = backdrop.levels()
    if read is None:
        return None
    return {level.name: np.frombuffer(level.rgba, np.uint8)[: level.width * level.height * 4].reshape(
        level.height, level.width, 4).copy() for level in read}


def _install_python_capture() -> None:
    """The Python pyramid's levels read on the render thread right after its refresh (its GL context current there)."""
    from rendering.quick.render import surface_backdrop as sb

    original = sb.BackdropPipeline.refresh
    if getattr(original, "_n57b_capture", False):
        return

    def refresh(self, read_framebuffer, width, height):
        ok = original(self, read_framebuffer, width, height)
        if ok and _PYTHON_CAPTURE["armed"]:
            _PYTHON_CAPTURE["levels"] = _python_levels(self)
            _PYTHON_CAPTURE["armed"] = False
        return ok

    refresh._n57b_capture = True
    sb.BackdropPipeline.refresh = refresh


def _python_levels(pipeline) -> dict:
    import numpy as np
    from OpenGL import GL as gl
    from rendering.quick.render.surface_backdrop import pyramid_sizes

    names = ("half", "quarter", "eighth", "sixteenth", "thirty_second")
    out: dict = {}
    prior_unit = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    prior = int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D))
    try:
        def read(texture: int, level: int, w: int, h: int):
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            data = gl.glGetTexImage(gl.GL_TEXTURE_2D, level, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            return np.frombuffer(bytes(data), np.uint8)[: w * h * 4].reshape(h, w, 4).copy()

        for name, (texture, _fbo, w, h) in zip(names, pipeline._levels):
            out[name] = read(texture, 0, w, h)
        texture, _fbo, w, h = pipeline._scratch[0]
        out["scratch"] = read(texture, 0, w, h)
        light, heavy = pyramid_sizes(*pipeline._size)[1:3]
        out["light"] = read(pipeline.output_texture, 0, *light)
        out["heavy"] = read(pipeline.output_texture, 1, *heavy)
    finally:
        gl.glBindTexture(gl.GL_TEXTURE_2D, prior)
        gl.glActiveTexture(prior_unit)
    return out


# --------------------------------------------------------------------------------------------------- the scene


def _host(core, size, dpr: float = 1.0, timestamps: bool = False):
    return core.hidden_host(size[0], size[1], dpr=dpr, timestamps=timestamps)


class BackdropScene:
    """background_layer_check's scene (the display at its overscan placement), with the display's dimming rectangle
    (DisplayScene's ``backgroundDimming``, z 1), a backdrop (z 2: the Python ``SurfaceBackdropSource`` or the core's)
    and material cards (z 5, the product's ``MaterialSurface.qml``)."""

    def __init__(self, core, engine, host, dpr: float, display, *, background: str, backdrop: str,
                 dimming: float = 0.0, offset=None) -> None:
        import background_layer_check as blc
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        self.core, self.engine, self.host, self.dpr, self.display = core, engine, host, float(dpr), display
        self.base = blc.Scene(core, engine, host, dpr, display, kind=background)
        self.scene = self.base.root.findChild(QQuickItem, "sceneRoot")
        self.offset = tuple(offset) if offset is not None else tuple(blc.OFFSET)
        if offset is not None:
            self.scene.setX(self.offset[0] / self.dpr)
            self.scene.setY(self.offset[1] / self.dpr)
        self.dimming_component = QQmlComponent(engine)
        self.dimming_component.setData(b'import QtQuick\nRectangle { color: "black"; z: 1 }', QUrl())
        self.dimming = self.dimming_component.create()
        self.dimming.setParentItem(self.scene)
        self.dimming.setWidth(self.scene.width())
        self.dimming.setHeight(self.scene.height())
        self.set_dimming(dimming)
        self.kind = backdrop
        self.native = None
        self.python = None
        if backdrop == "native":
            self.native = core.backdrop(self.scene)
            self.backdrop_item = self.native.item
            if dimming:
                self.native.set_dimming(dimming)
        else:
            from rendering.quick.render.surface_backdrop import SurfaceBackdropSource

            self.python = SurfaceBackdropSource(self.scene, screen_index=0)
            self.backdrop_item = self.python
        self.backdrop_item.setZ(2.0)
        self.backdrop_item.setWidth(self.scene.width())
        self.backdrop_item.setHeight(self.scene.height())
        self.cards: list = []
        self.card_component = None

    # -- the display

    def set_dimming(self, opacity: float) -> None:
        self.dimming.setProperty("opacity", float(opacity))
        self.dimming.setVisible(opacity > 0.0)
        if getattr(self, "native", None) is not None:
            self.native.set_dimming(opacity)

    def present(self, image) -> None:
        self.base.present(image)

    def frames(self, count: int = 1) -> None:
        self.base.frames(count)

    def settle(self) -> None:
        if self.base.layer is not None:
            self.base.settle()
        else:
            self.frames(2)

    def read(self):
        return self.base.read()

    # -- the backdrop

    def refresh_python(self) -> None:
        if self.python is not None:
            self.python.request_refresh()
            self.frames(2)

    def native_levels(self) -> dict:
        self.native.request_build(readback=True)
        for _ in range(MAX_WAIT_FRAMES):
            self.frames(1)
            levels = _native_levels(self.native)
            if levels is not None:
                rows_up = bool((self.native.state().get("pyramid") or {}).get("rows_up"))
                return _levels_top_down(levels, rows_up)
        raise RuntimeError(f"the native levels were not read back within {MAX_WAIT_FRAMES} frames: "
                           f"{self.native.state()}")

    def python_levels(self) -> dict:
        _PYTHON_CAPTURE.update(armed=True, levels=None)
        self.refresh_python()
        levels = _PYTHON_CAPTURE["levels"]
        if levels is None:
            raise RuntimeError("the Python pyramid did not refresh")
        return _levels_top_down(levels, True)   # OpenGL memory order: bottom-up

    # -- the cards

    def add_cards(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from rendering.quick.bootstrap import quick_qml_root

        self.card_component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(quick_qml_root() / "MaterialSurface.qml")))
        if self.card_component.isError():
            raise RuntimeError(f"MaterialSurface.qml did not load: {self.card_component.errorString()}")
        for material, (x, y, w, h) in zip(MATERIALS, CARD_RECTS):
            card = self.card_component.create()
            if card is None:
                raise RuntimeError(f"a MaterialSurface did not create: {self.card_component.errorString()}")
            card.setParentItem(self.scene)
            card.setZ(5.0)
            for name, value in (("x", x), ("y", y), ("width", w), ("height", h), ("material", material),
                                ("cornerRadius", 14.0), ("normalColor", CARD_NORMAL), ("tintColor", CARD_NORMAL)):
                card.setProperty(name, value)
            card.setProperty("backdrop", self.backdrop_item)
            self.cards.append(card)

    def normal_regions(self) -> dict:
        """The cards' interiors drawn exactly Normal: the same cards with no backdrop bound (read, then bound again)."""
        self.bind_cards(None)
        self.frames(2)
        regions = self.card_regions(self.read())
        self.bind_cards(self.backdrop_item)
        self.frames(2)
        return regions

    def bind_cards(self, item) -> None:
        """The product's order (Card_Surface_Materials.md section 3.2): consumers unbound before a park, bound again
        after a wake."""
        for card in self.cards:
            card.setProperty("backdrop", item)

    def card_regions(self, rows) -> dict:
        """Each card's interior in a read frame (device pixels, CARD_INSET off its edge)."""
        import background_layer_check as blc

        x0, y0 = getattr(self, "offset", blc.OFFSET)
        regions = {}
        for material, (x, y, w, h) in zip(MATERIALS, CARD_RECTS):
            left, top = x0 + round(x * self.dpr) + CARD_INSET, y0 + round(y * self.dpr) + CARD_INSET
            right, bottom = x0 + round((x + w) * self.dpr) - CARD_INSET, y0 + round((y + h) * self.dpr) - CARD_INSET
            regions[material] = rows[top:bottom, left:right]
        return regions

    def close(self, app) -> None:
        import host_check

        for card in self.cards:
            host_check._drop_item(app, card)
        self.cards = []
        if self.native is not None:
            self.native.destroy()
        host_check._drop_item(app, self.dimming)
        if not self.host.closed:
            self.base.close(app)
            return
        # The host went first (the lifetime round): the scene's own parts only.
        if self.base.layer is not None:
            self.base.layer.close()
        if hasattr(self.base.item, "close_native_layer"):
            self.base.item.close_native_layer()
        host_check._drop_item(app, self.base.root)


def _close_host(app, host) -> dict:
    import background_layer_check as blc

    return blc._close_host(app, host)


def _photos(display) -> dict:
    import background_layer_check as blc

    return {label: blc.processed(PHOTO_FOLDER / name, "fill", display) for label, name in PHOTOS}


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
    import background_layer_check as blc

    blc._sheet(path, rows_of_tiles)


# --------------------------------------------------------------------------------------------------- levels


def round_levels(core, engine, app, api: str, work: Path, out: Path) -> dict:
    import background_layer_check as blc
    import numpy as np

    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {"cases": {}}
    native: dict = {}
    reference: dict = {}
    if not vulkan:
        _install_python_capture()
    # (key, photo, dpr, dimming, window, display, offset): both photos at both dprs at background_layer_check's
    # overscan placement, the product's own placement, and one dimmed case (a fact).
    cases = [(f"{label}@{dpr}@dim0.0", label, dpr, 0.0, blc.WINDOW, blc.DISPLAY, blc.OFFSET)
             for label, _n in PHOTOS for dpr in DPRS]
    product_display = (PRODUCT_WINDOW[0] - PRODUCT_OFFSET[0], PRODUCT_WINDOW[1] - PRODUCT_OFFSET[1])
    cases += [(f"{label}@product@dim0.0", label, 1.0, 0.0, PRODUCT_WINDOW, product_display, PRODUCT_OFFSET)
              for label, _n in PHOTOS]
    cases.append((f"{PHOTOS[0][0]}@1.0@dim{DIMMING_FACT}", PHOTOS[0][0], 1.0, DIMMING_FACT, blc.WINDOW, blc.DISPLAY,
                  blc.OFFSET))
    photos = {display: _photos(display) for display in {c[5] for c in cases}}
    for key, label, dpr, dimming, window, display, offset in cases:
        photo = photos[display][label]
        if not vulkan:
            host = _host(core, window, dpr)
            scene = BackdropScene(core, engine, host, dpr, display, background="python", backdrop="python",
                                  dimming=dimming, offset=offset)
            try:
                scene.present(photo[0])
                scene.frames(2)
                reference[key] = scene.python_levels()
            finally:
                scene.close(app)
                facts.setdefault("host_close", []).append(_close_host(app, host))
        host = _host(core, window, dpr)
        scene = BackdropScene(core, engine, host, dpr, display, background="layer", backdrop="native",
                              dimming=dimming, offset=offset)
        try:
            scene.present(photo[0])
            scene.settle()
            native[key] = scene.native_levels()
            facts["cases"][key] = {"pyramid": scene.native.state().get("pyramid"),
                                   "driver": {k: v for k, v in (host.state().get("driver") or {}).items()
                                              if k in ("backdrop_builds", "window_backdrops",
                                                       "edges_with_python_thread_state", "error")}}
        finally:
            scene.close(app)
            facts.setdefault("host_close", []).append(_close_host(app, host))
    np.savez_compressed(work / f"levels_{api}.npz",
                        **{f"{key}|{name}": rows for key, levels in native.items() for name, rows in levels.items()})
    tiles = []
    if not vulkan:
        np.savez_compressed(work / "levels_python.npz", **{f"{key}|{name}": rows for key, levels in reference.items()
                                                            for name, rows in levels.items()})
        comparisons = {}
        for key in native:
            comparisons[key] = {name: compare(native[key][name], reference[key][name]) for name in native[key]}
        facts["rule_a"] = comparisons
        undimmed = [key for key in native if key.endswith("dim0.0")]
        # Every level (the outputs the cards sample included) under LEVEL_RULE_A, pixel by pixel (at the product's odd
        # window the GL blit's own fixed-point positions put single first-level texels on a sharp edge 2 levels from
        # any shader tap: emulated with five coordinate forms before round 2, none closer; the one tie of 'half').
        facts["rule_a_tolerance"] = judge_levels_rule_a(native, reference, undimmed)
        facts["rule_a_bounds"] = [t.bound() for t in LEVEL_RULE_A.values()]
        checks["rule_a_every_level_within_the_shared_tolerance"] = facts["rule_a_tolerance"]["pass"]
        facts["rule_a_levels_over_tolerance"] = {
            f"{key}|{name}": c["over_1"] for key in undimmed for name, c in comparisons[key].items() if c["over_1"]}
        facts["rule_a_exact"] = all(c["equal"] for key in undimmed for c in comparisons[key].values())
        facts["dimmed_against_python_worst"] = max(c["max_level"] for key in native if key not in undimmed
                                                   for c in comparisons[key].values())
        first, second = f"{PHOTOS[0][0]}@1.0@dim0.0", f"{PHOTOS[1][0]}@1.0@dim0.0"
        control = compare(native[first]["light"], reference[second]["light"])
        facts["control_other_photo"] = control
        checks["control_other_photo_differs"] = control["max_level"] > 8
        for label, _n in PHOTOS:
            key = f"{label}@1.0@dim0.0"
            tiles.append([_tile(reference[key]["light"]), _tile(native[key]["light"]),
                          _tile(reference[key]["heavy"]), _tile(native[key]["heavy"])])
    else:
        for label, _n in PHOTOS:
            key = f"{label}@1.0@dim0.0"
            tiles.append([_tile(native[key]["light"]), _tile(native[key]["heavy"])])
    checks["every_level_read_back"] = all(len(levels) == 8 for levels in native.values())
    checks["levels_opaque"] = all(int(rows[..., 3].min()) == 255 for levels in native.values()
                                  for name, rows in levels.items() if name != "half")
    checks["frame_driver_without_python"] = all(
        (c["driver"].get("edges_with_python_thread_state", 1) == 0) for c in facts["cases"].values())
    _sheet(out / f"levels_{api}.png", tiles)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def vulkan_levels_against_opengl(work: Path) -> dict:
    import numpy as np

    vk_path, gl_path, py_path = work / "levels_vulkan.npz", work / "levels_opengl.npz", work / "levels_python.npz"
    if not (vk_path.exists() and gl_path.exists()):
        return {"pass": False, "error": "both APIs' levels are needed"}
    vk, gl = np.load(vk_path), np.load(gl_path)
    py = np.load(py_path) if py_path.exists() else None
    results = {}
    judged: list[dict] = []
    for key in sorted(set(vk.files) & set(gl.files)):
        results[key] = {"opengl_native": compare(vk[key], gl[key])}
        if py is not None and key in py.files:
            results[key]["python"] = compare(vk[key], py[key])
        # Stored as ``<case>|<level>``: each level against its own bound; a level this harness does not know fails.
        tolerance = LEVEL_RULE_B.get(_level_name(key))
        judged.append(pt.judge(vk[key][..., :3], gl[key][..., :3], tolerance) if tolerance is not None else
                      {"pass": False, "reasons": [f"no bound for level {key}"]})
    worst = max((r["opengl_native"]["max_level"] for r in results.values()), default=255)
    tolerance = pt.summarise(judged)
    return {"pass": bool(results) and tolerance["pass"], "worst_level": worst, "tolerance": tolerance,
            "bounds": [t.bound() for t in LEVEL_RULE_B.values()], "levels": results}


# --------------------------------------------------------------------------------------------------- cards


def round_cards(core, engine, app, api: str, work: Path, out: Path) -> dict:
    import background_layer_check as blc
    import numpy as np

    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {}
    frames: dict = {}
    normals: dict = {}
    kinds = (("native",) if vulkan else ("python", "native"))
    photos = _photos(blc.DISPLAY)
    for kind in kinds:
        for label, _n in PHOTOS:
            host = _host(core, blc.WINDOW, 1.0)
            scene = BackdropScene(core, engine, host, 1.0, blc.DISPLAY,
                                  background="python" if kind == "python" else "layer", backdrop=kind)
            try:
                scene.add_cards()
                scene.present(photos[label][0])
                scene.settle()
                scene.refresh_python()
                scene.frames(2)
                if kind == "python":
                    # Today's steady backdrop: a second refresh. The first publish against it is a fact (Qt's one-time
                    # generateMips overwrote the heavy level until R-NEW's fix; 0 levels since).
                    first = scene.read()
                    scene.refresh_python()
                    scene.frames(2)
                    frames[f"python_first|{label}"] = first
                frames[f"{kind}|{label}"] = scene.read()
                normals[f"{kind}|{label}"] = scene.normal_regions()
            finally:
                scene.close(app)
                facts.setdefault("host_close", []).append(_close_host(app, host))
    np.savez_compressed(work / f"cards_{api}.npz", **frames)
    np.savez_compressed(work / f"normals_{api}.npz",
                        **{f"{key}|{m}": rows for key, per in normals.items() for m, rows in per.items()})
    regions_of = lambda rows: BackdropScene.card_regions(_RegionsOnly(1.0), rows)  # noqa: E731
    if not vulkan:
        comparison = {}
        today_regions, native_regions = {}, {}
        for label, _n in PHOTOS:
            today, native = regions_of(frames[f"python|{label}"]), regions_of(frames[f"native|{label}"])
            today_regions[label], native_regions[label] = today, native
            comparison[label] = {m: compare(native[m], today[m]) for m in MATERIALS}
        facts["native_against_today"] = comparison
        facts["native_against_today_tolerance"] = judge_cards_rule_a(native_regions, today_regions)
        checks["opengl_native_cards_equal_todays"] = facts["native_against_today_tolerance"]["pass"]
        facts["todays_first_publish_against_steady"] = {
            label: {m: compare(regions_of(frames[f"python_first|{label}"])[m], regions_of(frames[f"python|{label}"])[m])[
                "max_level"] for m in MATERIALS} for label, _n in PHOTOS}
    facts["material_against_normal_mean"] = {
        key: {m: round(float(np.abs(regions_of(frames[key])[m][..., :3].astype(int)
                                    - normals[key][m][..., :3].astype(int)).mean()), 2) for m in MATERIALS}
        for key in normals}
    checks["materials_drawn_not_normal"] = all(
        v > 4.0 for key, per in facts["material_against_normal_mean"].items() if key.startswith("native")
        for v in per.values())
    for label, _n in PHOTOS:
        row = [_tile(frames[f"{k}|{label}"]) for k in kinds]
        _sheet(out / f"cards_{label}_{api}.png", [row])
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


class _RegionsOnly:
    """card_regions without a scene (a read frame of a dpr's scene)."""

    def __init__(self, dpr: float) -> None:
        self.dpr = dpr


def review_sheets(work: Path, out: Path) -> list[str]:
    """The lead's look review, one sheet per photo: a row per material, each card's interior at full resolution:
    today's (OpenGL, the Python pyramid) | native on OpenGL | native on Vulkan | the same card Normal."""
    import numpy as np
    from PIL import Image, ImageDraw

    files = {name: work / f"{name}.npz" for name in ("cards_opengl", "cards_vulkan", "normals_opengl")}
    if not all(path.exists() for path in files.values()):
        return []
    gl, vk, normals = (np.load(files[n]) for n in ("cards_opengl", "cards_vulkan", "normals_opengl"))
    written = []
    for label, name in PHOTOS:
        columns = [("today (OpenGL, Python)", gl, f"python|{label}"), ("native OpenGL", gl, f"native|{label}"),
                   ("native Vulkan", vk, f"native|{label}")]
        crops = []
        for _title, data, key in columns:
            crops.append(BackdropScene.card_regions(_RegionsOnly(1.0), data[key]))
        h, w = crops[0][MATERIALS[0]].shape[:2]
        pad, head = 8, 22
        sheet = Image.new("RGB", (4 * (w + pad) + pad + 70, len(MATERIALS) * (h + pad) + pad + head), (24, 24, 24))
        draw = ImageDraw.Draw(sheet)
        titles = [c[0] for c in columns] + ["Normal"]
        for c, title in enumerate(titles):
            draw.text((70 + pad + c * (w + pad), 4), title, fill=(230, 230, 230))
        for r, material in enumerate(MATERIALS):
            y = head + pad + r * (h + pad)
            draw.text((6, y + h // 2), material, fill=(230, 230, 230))
            tiles = [crop[material] for crop in crops] + [normals[f"native|{label}|{material}"]]
            for c, tile in enumerate(tiles):
                sheet.paste(Image.fromarray(np.ascontiguousarray(tile[..., :3])), (70 + pad + c * (w + pad), y))
        path = out / f"cards_review_{label}.png"
        sheet.save(path)
        written.append(str(path))
    return written


def vulkan_cards_against_opengl(work: Path) -> dict:
    import numpy as np

    vk_path, gl_path = work / "cards_vulkan.npz", work / "cards_opengl.npz"
    if not (vk_path.exists() and gl_path.exists()):
        return {"pass": False, "error": "both APIs' card frames are needed"}
    vk, gl = np.load(vk_path), np.load(gl_path)
    results, outliers, pixels = {}, 0, 0
    judged: list[dict] = []
    for label, _n in PHOTOS:
        key = f"native|{label}"
        if key not in vk.files or key not in gl.files:
            continue
        vk_regions = BackdropScene.card_regions(_RegionsOnly(1.0), vk[key])
        gl_regions = BackdropScene.card_regions(_RegionsOnly(1.0), gl[key])
        per = {m: compare(vk_regions[m], gl_regions[m]) for m in MATERIALS}
        results[label] = per
        outliers += sum(c["over_1"] for c in per.values())
        pixels += sum(c["pixels"] for c in per.values())
        for m in MATERIALS:
            if vk_regions[m].shape != gl_regions[m].shape:
                judged.append({"pass": False, "reasons": [f"{label} {m}: card regions differ in shape"]})
                continue
            # The one-level pixels (scatter) per material; the delta is clipped to one level so that the grain hash's
            # pixels past it stay with the share rule below (see CARD_RULE_B).
            one = np.minimum(pt.levels(vk_regions[m][..., :3], gl_regions[m][..., :3]), 1)
            judged.append(pt.judge_delta(one, CARD_RULE_B[m]))
        if "python|" + label in gl.files:
            results[label + "_against_today"] = {
                m: compare(vk_regions[m], BackdropScene.card_regions(_RegionsOnly(1.0), gl["python|" + label])[m])
                for m in MATERIALS}
    share = outliers / pixels if pixels else 1.0
    tolerance = pt.summarise(judged)
    return {"pass": bool(results) and share <= CARD_OUTLIER_SHARE and tolerance["pass"], "outlier_share": share,
            "tolerance": tolerance, "bounds": [t.bound() for t in CARD_RULE_B.values()], "cards": results}


# --------------------------------------------------------------------------------------------------- cost


def round_cost(core, engine, app, api: str) -> dict:
    import background_layer_check as blc

    results: dict = {}
    checks: dict = {}
    for size in COST_SIZES:
        display = (size[0] - 4, size[1] - 6)
        photo = blc.processed(PHOTO_FOLDER / PHOTOS[0][1], "fill", display)[0]
        host = _host(core, size, 1.0)
        scene = BackdropScene(core, engine, host, 1.0, display, background="layer", backdrop="native")
        try:
            scene.present(photo)
            scene.settle()
            scene.frames(2)
            host.set_gpu_timer(True)
            host.gpu_samples()
            # Vulkan reads every build's timestamps; OpenGL's latched TIME_ELAPSED queries drop a result that is not
            # ready before the timer's ring wraps (the N2.6 timer's rule, never a wait), so the builds go on past
            # TIMED_BUILDS until enough GPU times have arrived, at most MAX_TIMED_BUILDS: counted, never slept.
            required = TIMED_BUILDS - 2 if api == "vulkan" else TIMED_BUILDS // 3
            cpu, samples, builds = [], [], 0
            while builds < MAX_TIMED_BUILDS and (builds < TIMED_BUILDS or len(samples) < required):
                scene.native.request_build()
                scene.frames(1)
                builds += 1
                cpu.append(float((scene.native.state().get("pyramid") or {}).get("last_build_ms", 0.0)))
                samples.extend(s.milliseconds for s in host.gpu_samples() if s.kind == 4)
            scene.frames(4)
            samples.extend(s.milliseconds for s in host.gpu_samples() if s.kind == 4)
            host.set_gpu_timer(False)
            gpu = _ms_stats(samples)
            name = f"{size[0]}x{size[1]}"
            results[name] = {"build_gpu": gpu, "build_render_thread_cpu": _ms_stats(cpu),
                             "budget_ms": BUDGET_MS[size]}
            checks[f"build_within_budget_{name}"] = bool(samples) and gpu["p90_ms"] <= BUDGET_MS[size]
            results[name]["samples"] = len(samples)
            results[name]["builds"] = builds
            checks[f"enough_builds_measured_{name}"] = len(samples) >= required
        finally:
            scene.close(app)
            _close_host(app, host)
    return {"pass": all(checks.values()), "checks": checks, "facts": results}


# --------------------------------------------------------------------------------------------------- rest and demand


def _builds(scene) -> int:
    return int((scene.native.state().get("pyramid") or {}).get("builds", 0))


def round_rest(core, engine, app, api: str) -> dict:
    import background_layer_check as blc
    import numpy as np

    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {}
    photos = _photos(blc.DISPLAY)
    change = blc.processed(PHOTO_FOLDER / CHANGE_PHOTO, "fill", blc.DISPLAY)
    host = _host(core, blc.WINDOW, 1.0)
    scene = BackdropScene(core, engine, host, 1.0, blc.DISPLAY, background="layer", backdrop="native")
    try:
        # Fail closed: before any photo the cards are exactly their Normal fill (the output transparent or absent).
        scene.add_cards()
        scene.frames(3)
        regions = scene.card_regions(scene.read())
        normal = scene.normal_regions()
        facts["before_photo"] = {m: compare(regions[m], normal[m])["max_level"] for m in regions}
        facts["before_photo_state"] = scene.native.state()
        checks["cards_normal_before_the_first_photo"] = all(v == 0 for v in facts["before_photo"].values())
        scene.present(photos["dark"][0])
        scene.settle()
        scene.frames(2)
        # Nothing at rest.
        host.set_gpu_timer(True)
        host.gpu_samples()
        before = (_builds(scene), int((host.state().get("driver") or {}).get("backdrop_builds", 0)))
        scene.frames(REST_FRAMES)
        after = (_builds(scene), int((host.state().get("driver") or {}).get("backdrop_builds", 0)))
        samples = [s for s in host.gpu_samples() if s.kind == 4]
        checks["nothing_at_rest"] = before == after and not samples
        # A photo change builds once, at the commit's frame.
        uploads = int(scene.base.mode_state().get("texture_uploads", 0))
        builds = _builds(scene)
        scene.present(photos["bright"][0])
        scene.frames(1)
        at_handover = _builds(scene) - builds
        waited = 0
        while int(scene.base.mode_state().get("texture_uploads", 0)) <= uploads and waited < 600:
            scene.frames(1)
            waited += 1
        scene.frames(REST_FRAMES)
        facts["photo_change"] = {"builds_at_handover": at_handover, "builds": _builds(scene) - builds,
                                 "frames_while_uploading": waited}
        checks["photo_change_builds_once"] = _builds(scene) - builds == 1
        if vulkan:
            checks["handover_builds_nothing"] = at_handover == 0
        # Dimming: one build on a change, none for the same value.
        builds = _builds(scene)
        scene.set_dimming(0.4)
        scene.frames(3)
        once = _builds(scene) - builds
        scene.set_dimming(0.4)
        scene.frames(3)
        checks["dimming_change_builds_once"] = once == 1 and _builds(scene) - builds == 1
        host.set_gpu_timer(False)
        # Demand 0: parked, no QRhi object, the frame driver sees no pyramid, a photo change builds nothing. The
        # consumers are unbound first, as the owner does.
        scene.bind_cards(None)
        scene.frames(1)
        scene.native.set_parked(True)
        scene.frames(2)
        live = core.composite_live()
        driver = host.state().get("driver") or {}
        driver_builds = int(driver.get("backdrop_builds", 0))
        scene.present(photos["dark"][0])
        scene.settle()
        scene.frames(2)
        driver_after = host.state().get("driver") or {}
        facts["parked"] = {"live": live, "window_backdrops": driver.get("window_backdrops"),
                           "state": scene.native.state()}
        checks["parked_holds_no_qrhi_object"] = live.get("backdrop_resources") == 0
        checks["parked_is_not_recorded"] = driver.get("window_backdrops") == 0
        checks["demand_zero_builds_nothing"] = int(driver_after.get("backdrop_builds", 0)) == driver_builds
        # Woken: one build from the layer as it is.
        builds = _builds(scene)
        scene.native.set_parked(False)
        scene.frames(2)
        scene.bind_cards(scene.backdrop_item)
        scene.frames(2)
        state = scene.native.state().get("pyramid") or {}
        facts["woken"] = state
        checks["woken_builds_once_and_is_ready"] = bool(state.get("ready")) and _builds(scene) - builds == 1
        checks["frame_driver_without_python"] = (host.state().get("driver") or {}).get(
            "edges_with_python_thread_state", 1) == 0
    finally:
        scene.close(app)
        facts["host_close"] = _close_host(app, host)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- transition


TRANSITION_PROGRESS = (0.15, 0.3, 0.45, 0.6, 0.75, 0.9)


def round_transition(core, engine, app, api: str) -> dict:
    """D7 point 3: the pyramid follows every frame the layer draws of a transition (N5.2a's Crossfade on the layer,
    its clock held by the harness): one build per layer pass, the backdrop changing with the picture, nothing after."""
    import background_layer_check as blc
    import numpy as np
    import transition_route_check as trc

    checks: dict = {}
    facts: dict = {}
    photos = [_photos(blc.DISPLAY)[label] for label, _n in PHOTOS]
    host = _host(core, blc.WINDOW, 1.0)
    scene = BackdropScene(core, engine, host, 1.0, blc.DISPLAY, background="layer", backdrop="native")
    try:
        scene.add_cards()
        layer = scene.base.layer
        scene.present(photos[0][0])
        scene.settle()
        clock = trc.Clock()
        run = trc.production_run("crossfade", [photos[0][0], photos[1][0]], 1)
        clock.at(run, 0.0)
        scene.present(photos[0][0])
        layer = scene.base.layer
        layer._clock_ns = clock
        layer.transition(run)
        scene.settle()                                   # the destination's upload committed
        before = (_builds(scene), int((scene.base.composite_state().get("surface") or {}).get("passes_recorded", 0)))
        cards = []
        for progress in TRANSITION_PROGRESS:
            clock.at(run, progress)
            layer.tick()
            scene.frames(1)
            cards.append(scene.card_regions(scene.read())["glass"][..., :3].astype(int))
        after = (_builds(scene), int((scene.base.composite_state().get("surface") or {}).get("passes_recorded", 0)))
        builds, passes = after[0] - before[0], after[1] - before[1]
        facts["during_run"] = {"builds": builds, "layer_passes": passes, "progress_steps": len(TRANSITION_PROGRESS)}
        checks["one_build_per_layer_frame"] = builds == passes and passes >= len(TRANSITION_PROGRESS)
        steps = [float(np.abs(a - b).mean()) for a, b in zip(cards, cards[1:])]
        facts["glass_card_mean_change_per_step"] = [round(s, 2) for s in steps]
        checks["cards_follow_the_transition"] = all(s > 0.5 for s in steps)
        layer.transition(None)
        scene.present(photos[1][0])
        scene.settle()
        rest = _builds(scene)
        scene.frames(REST_FRAMES)
        checks["nothing_after_the_run"] = _builds(scene) == rest
    finally:
        scene.close(app)
        facts["host_close"] = _close_host(app, host)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- route


def round_route(core, engine, app, api: str) -> dict:
    import background_layer_check as blc
    import numpy as np
    from rendering.quick import bootstrap
    from rendering.quick.surface_backdrop_owner import SurfaceBackdropOwner

    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {}
    owner_state = bootstrap._owner
    saved = (owner_state.core, owner_state.backend)
    owner_state.core, owner_state.backend = core, bootstrap.QuickBackend(api=api, requested=api)
    host = _host(core, blc.WINDOW, 1.0)
    scene = BackdropScene(core, engine, host, 1.0, blc.DISPLAY, background="python", backdrop="python")
    owner = None
    try:
        # The scene's own Python source stands aside: the owner makes the display's backdrop as the product does.
        scene.python.set_parked(True)
        owner = SurfaceBackdropOwner(scene.scene, screen_index=0)
        checks["native_on_vulkan_python_on_opengl"] = owner.native is vulkan
        scene.backdrop_item = owner.item
        scene.add_cards()
        scene.present(_photos(blc.DISPLAY)["dark"][0])
        if scene.base.item.native_layer is not None:
            scene.base.layer = scene.base.item.native_layer
        scene.settle()
        owner.note_background_changed()
        scene.frames(3)
        regions = scene.card_regions(scene.read())
        normal = scene.normal_regions()
        facts["owner"] = {"native": owner.native, "source_state": owner.source.state() if owner.native else None}
        facts["material_against_normal_mean"] = {m: round(float(np.abs(regions[m][..., :3].astype(int)
                                                                     - normal[m][..., :3].astype(int)).mean()), 2)
                                                 for m in regions}
        checks["route_draws_the_material"] = all(v > 4.0 for v in facts["material_against_normal_mean"].values())
        for card in scene.cards:
            card.setProperty("backdrop", None)
        owner.retire()
        scene.frames(2)
        if vulkan:
            checks["retire_destroys_the_native_item"] = owner.source.backdrop.destroyed
    finally:
        scene.close(app)
        facts["host_close"] = _close_host(app, host)
        owner_state.core, owner_state.backend = saved
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- lifetime


def round_lifetime(core, engine, app, api: str) -> dict:
    import background_layer_check as blc

    checks: dict = {}
    facts: dict = {}
    photo = _photos(blc.DISPLAY)["dark"][0]
    # The item destroyed in a live scene: its pyramid goes on the render thread at the next sync.
    host = _host(core, blc.WINDOW, 1.0)
    scene = BackdropScene(core, engine, host, 1.0, blc.DISPLAY, background="layer", backdrop="native")
    try:
        scene.present(photo)
        scene.settle()
        scene.frames(2)
        facts["built"] = core.composite_live()
        scene.native.destroy()
        scene.frames(2)
        facts["destroyed"] = core.composite_live()
        checks["destroy_releases_the_pyramid"] = (facts["destroyed"].get("backdrop_pyramids") == 0
                                                  and facts["destroyed"].get("backdrop_resources") == 0)
    finally:
        scene.close(app)
        facts["host_close_1"] = _close_host(app, host)
    # The host closed with a pyramid alive: the scene graph's invalidation releases it.
    host = _host(core, blc.WINDOW, 1.0)
    scene = BackdropScene(core, engine, host, 1.0, blc.DISPLAY, background="layer", backdrop="native")
    try:
        scene.present(photo)
        scene.settle()
        scene.frames(2)
        facts["host_close_2"] = _close_host(app, host)
        facts["after_close"] = core.composite_live()
        checks["invalidation_releases_the_pyramid"] = (facts["after_close"].get("backdrop_pyramids") == 0
                                                       and facts["after_close"].get("backdrop_resources") == 0)
    finally:
        scene.close(app)
    import fullscreen_pass_check as fsc

    live = core.composite_live()
    facts["after"] = live
    checks["nothing_left"] = fsc._nothing_left(live) and _no_backdrop_left(live)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _no_backdrop_left(live: dict) -> bool:
    return all(not live.get(key) for key in ("backdrop_items", "backdrop_pyramids", "backdrop_resources"))


# --------------------------------------------------------------------------------------------------- the child


def child(args) -> dict:
    import host_check
    import vk_validation
    import background_layer_check as blc

    host_check._root(args.repo)
    out = Path(args.out_dir)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="backdrop-pyramid-check")
        from PySide6.QtWidgets import QApplication

        app = QApplication([sys.argv[0]])
    else:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication([sys.argv[0]])
    from PySide6.QtQml import QQmlEngine
    from rendering.native import NativeCoreUnavailable, load

    root = host_check._root(args.repo)
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
            if vulkan:
                core.set_vulkan_phase(f"n57b {name}")
            try:
                if name == "levels":
                    record[name] = round_levels(core, engine, app, args.api, work, out)
                elif name == "cards":
                    record[name] = round_cards(core, engine, app, args.api, work, out)
                elif name == "cost":
                    record[name] = round_cost(core, engine, app, args.api)
                elif name == "rest":
                    record[name] = round_rest(core, engine, app, args.api)
                elif name == "transition":
                    record[name] = round_transition(core, engine, app, args.api)
                elif name == "route":
                    record[name] = round_route(core, engine, app, args.api)
                else:
                    record[name] = round_lifetime(core, engine, app, args.api)
            except Exception:
                record[name] = {"pass": False, "error": traceback.format_exc()}
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


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    import background_layer_check as blc

    ok, failed = blc.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        if not _no_backdrop_left(live):
            failed.append(f"{api}: backdrop items, pyramids or QRhi objects left at the end ({live})")
    return not failed, failed


def main(argv: list[str] | None = None) -> int:
    import host_check
    import vk_validation

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--label", default="n57b_backdrop_pyramid")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--compare-only", action="store_true",
                        help="no child: Vulkan against OpenGL (levels, cards) and the review sheets from the label's "
                             "existing work folder (each API run alone under the same label first)")
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

    missing = [str(PHOTO_FOLDER / name) for _l, name in PHOTOS if not (PHOTO_FOLDER / name).is_file()]
    if not (PHOTO_FOLDER / CHANGE_PHOTO).is_file():
        missing.append(str(PHOTO_FOLDER / CHANGE_PHOTO))
    if missing:
        print(f"N57B VERDICT FAIL: photos missing ({', '.join(missing)})")
        return 0
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n5_7b", args.label)
    out.mkdir(parents=True, exist_ok=True)
    if args.compare_only:
        levels = vulkan_levels_against_opengl(out / "work")
        cards = vulkan_cards_against_opengl(out / "work")
        cards["review_sheets"] = review_sheets(out / "work", out)
        (out / "comparisons.json").write_text(json.dumps({"levels": levels, "cards": cards}, indent=2, default=str),
                                              encoding="utf-8")
        failed = ([] if levels.get("pass") else [f"rule (b): Vulkan levels against OpenGL native, worst "
                                                 f"{levels.get('worst_level')} levels"])
        failed += ([] if cards.get("pass") else [f"Vulkan cards against OpenGL native: {cards.get('outlier_share')}"])
        print(f"review sheets: {cards['review_sheets']}")
        print("N57B COMPARE " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)))
        return 0
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
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
    comparisons: dict = {}
    if set(APIS) <= set(args.apis):
        if "levels" in args.rounds:
            comparisons["levels"] = vulkan_levels_against_opengl(out / "work")
            if not comparisons["levels"].get("pass"):
                failed.append(f"rule (b): Vulkan levels against OpenGL native, worst "
                              f"{comparisons['levels'].get('worst_level')} levels")
        if "cards" in args.rounds:
            comparisons["cards"] = vulkan_cards_against_opengl(out / "work")
            comparisons["cards"]["review_sheets"] = review_sheets(out / "work", out)
            if not comparisons["cards"].get("pass"):
                failed.append(f"Vulkan cards against OpenGL native: {comparisons['cards'].get('outlier_share')} of "
                              "card pixels more than 1 level apart, "
                              f"{(comparisons['cards'].get('tolerance') or {}).get('first_reasons')}")
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "require_validation": args.require_validation,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "vulkan_against_opengl": comparisons, "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
        cost = (results[api].get("cost") or {}).get("facts") or {}
        for name, figures in cost.items():
            print(f"{api} build at {name}: GPU {figures['build_gpu']}, render thread {figures['build_render_thread_cpu']}"
                  f" (budget {figures['budget_ms']} ms)")
        levels = (results[api].get("levels") or {}).get("facts") or {}
        if "rule_a_exact" in levels:
            print(f"{api} rule (a) levels exact: {levels['rule_a_exact']}; dimmed worst "
                  f"{levels.get('dimmed_against_python_worst')} levels")
    print(f"evidence: {out / 'summary.json'}")
    print("N57B VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
