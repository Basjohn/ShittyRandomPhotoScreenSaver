"""N2.4's proof (Current_Plan.md item 8b): the composite as a scene-graph texture node carrying the card's coverage, through
``rendering.native``.

The module (``release/native_module``, built on GitHub) is loaded the product's way and driven in one child process per
graphics API (Qt Quick's API is process-wide): OpenGL, Vulkan on the module's own instance and devices (D6), D3D11 and
D3D12. No window is ever visible: the hidden host never shows one, and the window round's window is kept off screen by
the tests' pattern (``tests/_invisible_windows.py``).

The scene stands for the product's card (``VisualizerPresentation.qml``): a display background with a top-left marker,
the card at its drawn rect (``resolve_card_drawn_rect``) with its surface below the content and its frame above
(radius and border as the record gives them; ``tools/card_clip_contract.CONTRACT_CARD``'s half-transparent green
border), and the composite item in the content host, placed by ``rendering.native.composite.composite_geometry`` from
the same record. The composite's surface holds each texel's own index, or opaque white.

Rounds (each per API, at 100 %, 125 % and 150 % on one hidden host of HOST_PIXELS device pixels):
  texels    one to one: every covered pixel shows exactly the texel the decided geometry maps there, none repeated, and
            nothing changes outside the coverage (composite_analysis.py), for the card off the device-pixel grid, under
            pixel shift (whole logical pixels, off the device grid at 125 and 150 %), under uniform CUSTOM scales, at each
            quarter turn and for a frameless shell; the surface records once per change and nothing at rest; the node's
            device pixel ratio is Qt's at render time. Negative controls: the item at the record's raw (unsnapped) rect
            under a CUSTOM scale, and a turned frame read as unturned, both fail.
  contract  plan 1C.4's clip contract (tools/card_clip_contract.py, the reading tests/test_visualizer_card_clip_contract.py
            makes of the Python node) on the native item: the steady card, pixel shift, a CUSTOM scale and the
            display-wide card in each display style (1D.2: Default, Borders To Edge, Hide Borders); white content and the
            texel pattern against the composite hidden. Negative controls, each must break the contract: the pre-1C.4
            clip (the card unsnapped, coverage the record's content rect), the one-pixel inset (a seam), the coverage
            skipped on a Default card.
  overflow  a renderer's declared overflow (each registered mode that has one): held to the display rect in the
            non-Default styles (nothing changes past the display), admitted at Default (the one exception: the coverage is
            skipped and the target reaches past the card); negative control: the pre-1D.2 decision (never held) draws past
            the display.
  window    a real Qt Quick window rendered by Qt's render loop, kept off screen: the composite's surface recorded once on
            Qt's render thread with no Python thread state and never again at rest while the window animates; the window
            destroyed while it animates releases the surface on the render thread.
After every round the process holds no composite surface or QRhi object of the core's. On Vulkan the instance has the
Khronos validation layer with synchronisation validation when --layer-path gives it; every message is attributed and only
Qt 6.12.0's recorded defects are excused, by id (vk_validation.py).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/composite_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan d3d11 d3d12] [--rounds texels contract overflow window] [--label n24_composite]
Evidence: .artifacts/evidence/native_core/n2_4/<date>_<label>/ (summary.json; one PNG sheet per API of the contract's reads
at 125 %). Exit 0 whenever the harness ran; the verdict is the last printed line ("N24 VERDICT PASS" or
"N24 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402

APIS = host_check.APIS
ROUNDS = ("texels", "contract", "overflow", "window")
HOST_PIXELS = (1440, 900)          # whole logical sizes at 100, 125 and 150 % (1440 x 900, 1152 x 720, 960 x 600)
DPRS = (1.0, 1.25, 1.5)
SHEET_DPR = 1.25
CHILD_TIMEOUT_S = 900
REST_FRAMES = 3
MARKER = (255, 0, 255)
MARKER_PX = 6                      # logical
ORIGIN = (24.0, 40.0)              # the ordinary card's requested origin (plus the contract's off-grid offset)
PIXEL_SHIFTS = (1, 2, 3)           # logical pixels, as pixel shift moves cards
CUSTOM_SCALES = (0.85, 1.37)
_ALLOWED_ENV: set[str] = set()

SCENE_QML = b"""import QtQuick
Rectangle {
    id: root
    color: "#203040"
    Rectangle { objectName: "marker"; x: 0; y: 0; width: %(marker)d; height: %(marker)d; color: "#ff00ff" }
    Item {
        id: card
        objectName: "card"
        property bool shell: true
        property bool frameShown: true
        property real cornerRadius: 0
        property real borderWidth: 0
        property color surfaceColor: "#000000"
        property color borderColor: "#8000ff00"
        Rectangle {
            anchors.fill: parent; z: 1
            visible: card.shell
            color: card.surfaceColor
            radius: card.cornerRadius
        }
        Item { objectName: "contentHost"; anchors.fill: parent; z: 2 }
        Rectangle {
            anchors.fill: parent; z: 3
            visible: card.shell && card.frameShown
            color: "transparent"
            radius: card.cornerRadius
            border.color: card.borderColor
            border.width: card.borderWidth
        }
    }
    Rectangle {
        objectName: "spinner"
        x: 300; y: 160; width: 8; height: 8; color: "#405060"; visible: false
        RotationAnimation on rotation { from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
    }
}
""" % {b"marker": MARKER_PX}


# --------------------------------------------------------------------------------------------------------- the scene

def _qml_colour(rgba) -> str:
    r, g, b, a = (int(v) for v in rgba)
    return f"#{a:02x}{r:02x}{g:02x}{b:02x}"


class Scene:
    """The card scene in the hidden host, with one composite in its content host."""

    def __init__(self, core, engine, host) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem
        from tools.card_clip_contract import CONTRACT_CARD

        self.core, self.host = core, host
        self.component = QQmlComponent(engine)
        self.component.setData(SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        self.card = self.root.findChild(QQuickItem, "card")
        self.content = self.root.findChild(QQuickItem, "contentHost")
        self.card.setProperty("surfaceColor", _qml_colour(CONTRACT_CARD["background_color"]))
        self.card.setProperty("borderColor", _qml_colour(CONTRACT_CARD["border_color"]))
        host.set_content(self.root)
        self.composite = core.composite(self.content)
        self.dpr = 1.0

    def set_dpr(self, dpr: float) -> None:
        self.host.set_device_pixel_ratio(dpr)
        self.dpr = float(dpr)

    @property
    def logical(self) -> tuple[float, float]:
        return (HOST_PIXELS[0] / self.dpr, HOST_PIXELS[1] / self.dpr)

    def show_card(self, presentation, card_rect=None) -> tuple:
        """The card's chrome where the scene draws it (the record's drawn rect unless ``card_rect`` says otherwise)."""
        from core.settings.visualizer_mode_registry import VisualizerShellPolicy
        from widgets.spotify_visualizer.presentation_geometry import resolve_card_drawn_rect

        rect = tuple(card_rect) if card_rect is not None else resolve_card_drawn_rect(presentation)
        self.card.setX(rect[0])
        self.card.setY(rect[1])
        self.card.setWidth(rect[2])
        self.card.setHeight(rect[3])
        self.card.setProperty("shell", presentation.shell_policy is VisualizerShellPolicy.CARD)
        self.card.setProperty("cornerRadius", float(presentation.shell_style["corner_radius"]))
        self.card.setProperty("borderWidth", float(presentation.border_width))
        return rect

    def read(self):
        import numpy as np
        from composite_analysis import frame_rows

        frame = self.host.read()
        rows = frame_rows(asdict(frame))
        return rows, frame

    def reads(self, geometry, card_rect, *, patterns=("texel_id",), raw_rect=None, coverage="decided") -> dict:
        """Frames of the composite placed by ``geometry`` (or at ``raw_rect`` for a control), one per pattern, then
        hidden."""
        config = geometry.item_config(card_rect[:2])
        if raw_rect is not None:
            config["rect"] = [raw_rect[0] - card_rect[0], raw_rect[1] - card_rect[1], raw_rect[2], raw_rect[3]]
        if coverage != "decided":
            config["coverage"] = coverage
        frames = {}
        for pattern in patterns:
            self.composite.set(**config, pattern=pattern, visible=True)
            frames[pattern] = self.read()[0]
        self.composite.set(visible=False)
        frames["hidden"] = self.read()[0]
        return frames

    def close(self, app) -> None:
        self.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


def _card_record(dpr: float, *, logical, shift: float = 0.0, scale: float = 1.0, quarters: int = 0, policy=None):
    """The ordinary card the contract is read on, requested off the device-pixel grid."""
    from core.settings.visualizer_mode_registry import (
        VisualizerClipPolicy,
        VisualizerModePresentationPolicy,
        VisualizerShellPolicy,
    )
    from tools.card_clip_contract import CONTRACT_CARD, OFF_GRID
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    policy = policy or VisualizerModePresentationPolicy(
        shell_policy=VisualizerShellPolicy.CARD, clip_policy=VisualizerClipPolicy.CARD_INTERIOR,
        viewport_resize_capable=True, content_rotation_capable=True)
    return resolve_visualizer_presentation(
        policy=policy, display_size=logical,
        outer_origin=(ORIGIN[0] + OFF_GRID + shift, ORIGIN[1] + OFF_GRID + shift), dpr=dpr,
        uniform_visual_scale=scale, content_rotation_quarters=quarters, **CONTRACT_CARD)


def _frameless_policy():
    from core.settings.visualizer_mode_registry import VisualizerShellPolicy, iter_all_visualizer_mode_descriptors

    return next(d.presentation_policy for d in iter_all_visualizer_mode_descriptors()
                if d.presentation_policy.shell_policy is VisualizerShellPolicy.FRAMELESS)


def _expanded(dpr: float, logical, style: str, ordinary_policy=None):
    from widgets.spotify_visualizer.presentation_geometry import resolve_expanded_visualizer_presentation

    return resolve_expanded_visualizer_presentation(_card_record(dpr, logical=logical, policy=ordinary_policy),
                                                    display_size=logical, dpr=dpr, display_style=style)


def _item_state(scene) -> dict:
    return scene.composite.state()


def _live_clean(core) -> bool:
    live = core.composite_live()
    return live.get("surfaces") == 0 and live.get("surface_resources") == 0


# --------------------------------------------------------------------------------------------------------- texels

def round_texels(core, engine, app, api: str, host, out: Path) -> dict:
    from composite_analysis import analyse_texels, geometry_px, oriented_marker
    from rendering.native import composite_geometry

    record: dict = {"cases": {}}
    checks: dict = {}
    scene = Scene(core, engine, host)
    # The card's frame is drawn over the content (z 3) and anti-aliases its inner arc against it in the corners (build
    # round 1: 16 corner pixels at 100 %, 20 at 125 %): the frame is the contract round's subject, so here it is off and
    # every covered pixel is the composite's alone.
    scene.card.setProperty("frameShown", False)
    try:
        for dpr in DPRS:
            scene.set_dpr(dpr)
            logical = scene.logical
            cases = {"card": _card_record(dpr, logical=logical)}
            cases.update({f"pixel_shift_{k}": _card_record(dpr, logical=logical, shift=float(k)) for k in PIXEL_SHIFTS})
            cases.update({f"custom_scale_{s}": _card_record(dpr, logical=logical, scale=s) for s in CUSTOM_SCALES})
            cases.update({f"quarter_turn_{q}": _card_record(dpr, logical=logical, quarters=q) for q in (1, 2, 3)})
            cases["frameless"] = _card_record(dpr, logical=logical, policy=_frameless_policy())
            for name, presentation in cases.items():
                key = f"{name}@{dpr}"
                geometry = composite_geometry(presentation)
                card_rect = scene.show_card(presentation)
                passes_before = (_item_state(scene).get("surface") or {}).get("passes_recorded", 0)
                frames = scene.reads(geometry, card_rect)
                decided = geometry_px(geometry.rect, geometry.pixel_size, geometry.coverage, geometry.quarters, dpr)
                analysis = analyse_texels(frames["texel_id"], frames["hidden"], decided)
                state = _item_state(scene)
                sync = state.get("sync", {})
                scene.composite.set(visible=True)              # drawn again, nothing changed: nothing is recorded
                host.frames(REST_FRAMES)
                rest = _item_state(scene)
                scene.composite.set(visible=False)
                case = {"analysis": analysis, "geometry": decided, "sync": sync, "draws": state.get("draws"),
                        "dpr_mismatches": state.get("dpr_mismatches"), "render_dpr": state.get("render_dpr"),
                        "surface": state.get("surface"), "error": state.get("error")}
                case["checks"] = {
                    "one_to_one": analysis["pass"],
                    "frame_right_way_up": oriented_marker(frames["hidden"], MARKER, int(MARKER_PX * dpr)),
                    "sync_at_the_hosts_dpr": abs(float(sync.get("dpr", 0.0)) - dpr) < 1e-6,
                    "render_at_the_syncs_dpr": state.get("dpr_mismatches") == 0 and abs(
                        float(state.get("render_dpr", 0.0)) - dpr) < 1e-4,
                    "item_on_whole_device_pixels": sync.get("device_size_exact") is True,
                    "texture_is_the_items_pixels_turned": sync.get("texture_size") == list(geometry.texture_size),
                    "recorded_once_for_the_change": (state.get("surface") or {}).get("passes_recorded", 0)
                    - passes_before <= 1,
                    "nothing_recorded_at_rest": (rest.get("surface") or {}).get("passes_recorded")
                    == (state.get("surface") or {}).get("passes_recorded"),
                    "no_error": not state.get("error"),
                }
                record["cases"][key] = case
                for check, ok in case["checks"].items():
                    checks[f"{check}[{key}]"] = bool(ok)

        # Negative controls.
        dpr = SHEET_DPR
        scene.set_dpr(dpr)
        presentation = _card_record(dpr, logical=scene.logical, scale=CUSTOM_SCALES[0])
        geometry = composite_geometry(presentation)
        card_rect = scene.show_card(presentation)
        decided = geometry_px(geometry.rect, geometry.pixel_size, geometry.coverage, geometry.quarters, dpr)
        raw = tuple(presentation.outer_rect)
        unsnapped = scene.reads(geometry, card_rect, raw_rect=raw)
        control = analyse_texels(unsnapped["texel_id"], unsnapped["hidden"], decided)
        record["negative_unsnapped_rect"] = dict(control, raw_rect=list(raw),
                                                 raw_device_size=[raw[2] * dpr, raw[3] * dpr])
        checks["negative_control_unsnapped_rect_fails"] = not control["pass"]
        turned = _card_record(dpr, logical=scene.logical, quarters=1)
        geometry = composite_geometry(turned)
        card_rect = scene.show_card(turned)
        frames = scene.reads(geometry, card_rect)
        unturned = geometry_px(geometry.rect, geometry.pixel_size, geometry.coverage, 0, dpr)
        control = analyse_texels(frames["texel_id"], frames["hidden"], unturned)
        record["negative_turn_read_unturned"] = control
        checks["negative_control_turn_read_unturned_fails"] = not control["pass"]
    finally:
        scene.close(app)
        host.frames(2)                                 # Qt Quick deletes the node at the next sync
    checks["no_surface_left"] = _live_clean(core)
    record["live_after"] = core.composite_live()
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- contract

def _save_sheet(images: list, path: Path) -> str | None:
    import numpy as np
    from PySide6.QtGui import QImage

    if not images:
        return None
    height = max(i.shape[0] for i in images)
    sheet = np.concatenate([np.pad(i, ((0, height - i.shape[0]), (0, 4), (0, 0))) for i in images], axis=1)
    sheet = np.ascontiguousarray(sheet)
    sheet[..., 3] = 255
    image = QImage(sheet.tobytes(), sheet.shape[1], sheet.shape[0], sheet.shape[1] * 4,
                   QImage.Format.Format_RGBA8888).copy()
    return str(path) if image.save(str(path), "PNG") else None


def _contract_holds(reading) -> bool:
    gaps_ok = reading.gaps is None or all(gap == 0 for gap in reading.gaps.values())
    return (reading.escapes == 0 and (reading.under_frame in (None, 0)) and gaps_ok and reading.lit > 0)


def round_contract(core, engine, app, api: str, host, out: Path) -> dict:
    from core.settings.fullscreen_overlays import DISPLAY_STYLES
    from rendering.native import composite_geometry
    from tools.card_clip_contract import CONTRACT_CARD, read_contract

    record: dict = {"cases": {}}
    checks: dict = {}
    sheet: list = []
    scene = Scene(core, engine, host)
    alpha = CONTRACT_CARD["border_color"][3]
    try:
        for dpr in DPRS:
            scene.set_dpr(dpr)
            logical = scene.logical
            cases = {"steady": _card_record(dpr, logical=logical),
                     "pixel_shift": _card_record(dpr, logical=logical, shift=1.0),
                     "custom_scale": _card_record(dpr, logical=logical, scale=CUSTOM_SCALES[0])}
            cases.update({f"expanded_{style}": _expanded(dpr, logical, style) for style in DISPLAY_STYLES})
            for name, presentation in cases.items():
                key = f"{name}@{dpr}"
                geometry = composite_geometry(presentation)
                card_rect = scene.show_card(presentation)
                frames = scene.reads(geometry, card_rect, patterns=("texel_id", "white"))
                reading = read_contract(frames["texel_id"], frames["white"], frames["hidden"], card_rect=card_rect,
                                        presentation=presentation, dpr=dpr, border_alpha=alpha)
                record["cases"][key] = asdict(reading)
                checks[f"contract[{key}]"] = _contract_holds(reading)
                if dpr == SHEET_DPR and name in ("steady", "expanded_borders_to_edge"):
                    sheet += [frames["hidden"], frames["white"]]

        # Negative controls at 125 %, on the steady card: each must break the contract.
        dpr = SHEET_DPR
        scene.set_dpr(dpr)
        presentation = _card_record(dpr, logical=scene.logical)
        geometry = composite_geometry(presentation)
        controls: dict = {}
        # The pre-1C.4 clip (R-191): the card where the layout put it (unsnapped) and the clip at the record's content
        # rect.
        raw = tuple(presentation.outer_rect)
        card_rect = scene.show_card(presentation, card_rect=raw)
        cx, cy, cw, ch = presentation.content_rect
        frames = scene.reads(geometry, card_rect, patterns=("texel_id", "white"), raw_rect=raw,
                             coverage={"rect": [cx - raw[0], cy - raw[1], cw, ch],
                                       "radius": float(presentation.shell_style["inner_corner_radius"])})
        controls["pre_1c4_clip"] = read_contract(frames["texel_id"], frames["white"], frames["hidden"],
                                                 card_rect=card_rect, presentation=presentation, dpr=dpr,
                                                 border_alpha=alpha)
        # The one-pixel inset (938aee6f): the clip one device pixel inside the frame leaves a seam.
        card_rect = scene.show_card(presentation)
        (ix, iy, iw, ih), radius = geometry.coverage
        step = 1.0 / dpr
        frames = scene.reads(geometry, card_rect, patterns=("texel_id", "white"),
                             coverage={"rect": [ix + step, iy + step, iw - 2 * step, ih - 2 * step],
                                       "radius": max(0.0, radius - step)})
        controls["one_pixel_inset"] = read_contract(frames["texel_id"], frames["white"], frames["hidden"],
                                                    card_rect=card_rect, presentation=presentation, dpr=dpr,
                                                    border_alpha=alpha)
        # The coverage skipped on an ordinary card (what only an admitted overflow may do).
        frames = scene.reads(geometry, card_rect, patterns=("texel_id", "white"), coverage=None)
        controls["coverage_skipped"] = read_contract(frames["texel_id"], frames["white"], frames["hidden"],
                                                     card_rect=card_rect, presentation=presentation, dpr=dpr,
                                                     border_alpha=alpha)
        record["negative_controls"] = {name: asdict(reading) for name, reading in controls.items()}
        for name, reading in controls.items():
            checks[f"negative_control_{name}_breaks_the_contract"] = not _contract_holds(reading)
    finally:
        scene.close(app)
        host.frames(2)
    record["sheet_png"] = _save_sheet(sheet, out / f"n24_contract_{api}_{int(SHEET_DPR * 100)}.png")
    checks["no_surface_left"] = _live_clean(core)
    record["live_after"] = core.composite_live()
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- overflow

def round_overflow(core, engine, app, api: str, host, out: Path) -> dict:
    """1D.2, lead's decision 3: no style draws past the visible rect. The display is the host's top-left quarter, so the
    rest of the window stands for what lies past it (R-63's overscan)."""
    from composite_analysis import changed_outside
    from core.settings.fullscreen_overlays import DISPLAY_STYLE_DEFAULT, DISPLAY_STYLE_HIDE_BORDERS, DISPLAY_STYLES
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    from rendering.native import composite_geometry
    from widgets.spotify_visualizer import presentation_geometry

    record: dict = {"cases": {}}
    checks: dict = {}
    scene = Scene(core, engine, host)
    dpr = SHEET_DPR
    overflow_modes = [d for d in iter_all_visualizer_mode_descriptors() if d.renderer_overflow_setting]
    checks["a_mode_declares_an_overflow"] = bool(overflow_modes)
    try:
        scene.set_dpr(dpr)
        window = scene.logical
        display = (window[0] / 2.0, window[1] / 2.0)
        display_px = [0, 0, int(round(display[0] * dpr)), int(round(display[1] * dpr))]
        for descriptor in overflow_modes:
            for style in DISPLAY_STYLES:
                key = f"{descriptor.mode_id}:{style}"
                presentation = _expanded(dpr, display, style, ordinary_policy=descriptor.presentation_policy)
                geometry = composite_geometry(presentation, overflow_requested=True,
                                              overflow_rect=(0.0, 0.0, window[0], window[1]))
                card_rect = scene.show_card(presentation)
                frames = scene.reads(geometry, card_rect, patterns=("white",))
                outside, inside = changed_outside(frames["white"], frames["hidden"], display_px)
                held = style != DISPLAY_STYLE_DEFAULT
                record["cases"][key] = {"outside_display": outside, "inside_display": inside,
                                        "overflow_admitted": geometry.overflow_admitted}
                checks[f"drew_on_the_display[{key}]"] = inside > 0
                if held:
                    checks[f"held_to_the_display[{key}]"] = outside == 0 and not geometry.overflow_admitted
                else:
                    # The one admitted exception: the coverage skipped, the target reaching past the card.
                    checks[f"admitted_at_default[{key}]"] = outside > 0 and geometry.overflow_admitted
            # Negative control: the pre-1D.2 decision (overflow never held) draws past the display in a held style.
            presentation = _expanded(dpr, display, DISPLAY_STYLE_HIDE_BORDERS,
                                     ordinary_policy=descriptor.presentation_policy)
            with patch.object(presentation_geometry, "renderer_overflow_held", lambda _card: False):
                geometry = composite_geometry(presentation, overflow_requested=True,
                                              overflow_rect=(0.0, 0.0, window[0], window[1]))
            card_rect = scene.show_card(presentation)
            frames = scene.reads(geometry, card_rect, patterns=("white",))
            outside, _inside = changed_outside(frames["white"], frames["hidden"], display_px)
            record["cases"][f"{descriptor.mode_id}:negative_never_held"] = {"outside_display": outside}
            checks[f"negative_control_never_held_draws_past[{descriptor.mode_id}]"] = outside > 0
    finally:
        scene.close(app)
        host.frames(2)
    checks["no_surface_left"] = _live_clean(core)
    record["live_after"] = core.composite_live()
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- window

def round_window(core, engine, app, api: str, out: Path) -> dict:
    import shiboken6
    from PySide6.QtCore import QSizeF, QUrl
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickItem

    record: dict = {}
    checks: dict = {}
    component = QQmlComponent(engine)
    component.setData(SCENE_QML, QUrl())
    root = component.create()
    if root is None:
        raise RuntimeError(f"the scene did not load: {component.errorString()}")
    root.findChild(QQuickItem, "spinner").setVisible(True)   # Qt's render loop keeps rendering frames
    window = host_check._off_screen_window()
    root.setParentItem(window.contentItem())
    root.setSize(QSizeF(*host_check.HOST_SIZE))
    content = root.findChild(QQuickItem, "contentHost")
    card = root.findChild(QQuickItem, "card")
    card.setX(20.0)
    card.setY(20.0)
    card.setWidth(160.0)
    card.setHeight(100.0)
    host = core.attach_host(window)       # before the window is first shown (D6 on Vulkan)
    composite = core.composite(content)
    try:
        composite.set(rect=[0.0, 0.0, 160.0, 100.0], coverage={"rect": [5.0, 5.0, 150.0, 90.0], "radius": 3.0},
                      pattern="white", visible=True)
        host_check._show(window)
        drawn = host_check._wait_until(app, lambda: window.isExposed() and composite.state().get("draws", 0) >= 5)
        state = composite.state()
        driver = host_check._driver(host.state())
        record["first"] = {"composite": state, "driver": driver}
        edges = driver.get("edges", 0)
        host_check._wait_until(app, lambda: host_check._driver(host.state()).get("edges", 0) >= edges + 10)
        rest = composite.state()
        driver_rest = host_check._driver(host.state())
        record["rest"] = {"composite": rest, "driver": driver_rest}
        checks["composite_drawn_in_qts_render_loop"] = drawn and state.get("nodes") == 1
        checks["surface_recorded_once"] = (state.get("surface") or {}).get("passes_recorded") == 1
        checks["nothing_recorded_at_rest_while_the_window_animates"] = (
            (rest.get("surface") or {}).get("passes_recorded") == 1
            and driver_rest.get("surface_passes_recorded") == 1 and driver_rest.get("edges", 0) >= edges + 10)
        checks["frame_edge_on_qts_render_thread"] = driver_rest.get("edges_on_gui_thread") == 0
        checks["no_python_thread_state_on_the_frame_edge"] = driver_rest.get("edges_with_python_thread_state") == 0
        checks["render_at_the_syncs_dpr"] = rest.get("dpr_mismatches") == 0
        checks["no_error"] = not rest.get("error") and not driver_rest.get("error")
        # Destroyed while it animates: the scene graph's invalidation deletes the node on Qt's render thread.
        shiboken6.delete(window)
        window = None
        host_check._flush_deletes(app)
        record["after_destroy"] = core.composite_live()
        checks["window_destroyed_released_the_surface"] = _live_clean(core)
    finally:
        if window is not None and shiboken6.isValid(window):
            shiboken6.delete(window)
        composite.destroy()
        record["close"] = host.close()
        host_check._drop_item(app, root)
    record["live_after"] = core.composite_live()
    checks["no_composite_left"] = record["live_after"].get("items") == 0 and _live_clean(core)
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- child

def child(args) -> dict:
    root = host_check._root(args.repo)
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    api_enum = QSGRendererInterface.GraphicsApi
    QQuickWindow.setGraphicsApi({"opengl": api_enum.OpenGL, "vulkan": api_enum.Vulkan,
                                 "d3d11": api_enum.Direct3D11, "d3d12": api_enum.Direct3D12}[args.api])
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlEngine

    app = QGuiApplication([sys.argv[0]])
    from rendering.native import NativeCoreUnavailable, load

    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    try:
        core = load((root / args.module_dir) if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    except NativeCoreUnavailable as exc:
        record["error"] = f"the module did not load: {exc.reason}"
        return record
    record["module_loaded"] = True
    record["runtime"] = dict(core.info)
    out = Path(args.out_dir)
    vulkan = args.api == "vulkan"
    if vulkan:
        instance = core.vulkan_instance(validation=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    host = None
    try:
        hidden_rounds = [name for name in args.rounds if name != "window"]
        if hidden_rounds:
            # One hidden host for every hidden round (an OpenGL hidden host is created once and kept: facts J1).
            host = core.hidden_host(*HOST_PIXELS)
            record["host"] = host.state()
        for name in args.rounds:
            if vulkan:
                core.set_vulkan_phase(f"n24 {name}")
            try:
                if name == "texels":
                    record[name] = round_texels(core, engine, app, args.api, host, out)
                elif name == "contract":
                    record[name] = round_contract(core, engine, app, args.api, host, out)
                elif name == "overflow":
                    record[name] = round_overflow(core, engine, app, args.api, host, out)
                else:
                    record[name] = round_window(core, engine, app, args.api, out)
            except Exception:
                record[name] = {"pass": False, "error": traceback.format_exc()}
    finally:
        if host is not None:
            if vulkan:
                core.set_vulkan_phase("n24 close")
            record["host_close"] = host.close()
        host_check._flush_deletes(app)
        record["live_hosts_at_end"] = core.live_hosts()
        record["composites_at_end"] = core.composite_live()
        if vulkan:
            teardown = core.destroy_vulkan_instance()
            messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
            summary = vk_validation.validation_summary(messages)
            layer = bool(record["instance"].get("validation_layer_loaded"))
            record["instance_teardown"] = teardown
            record["validation"] = {"layer_loaded": layer, "per_phase": messages.get("per_phase"),
                                    **{k: v for k, v in summary.items() if k != "groups"},
                                    "attribution": summary["groups"]}
        del engine
    return record


# --------------------------------------------------------------------------------------------------------- verdict

def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    """host_check's verdict (what failed on one API; a child that stopped early reports that one reason alone), plus no
    composite item, surface or QRhi object of the core's left at the end."""
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        if any(live.get(key) for key in ("items", "surfaces", "surface_resources")):
            failed.append(f"{api}: composites left at the end ({live})")
    return not failed, failed


def _failed_checks(record: dict) -> list[str]:
    """The failed checks of every round, for the summary's first screen."""
    failed = []
    for name in record.get("rounds", []):
        entry = record.get(name, {})
        failed += [f"{name}: {k}" for k, v in entry.get("checks", {}).items() if not v]
    return failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--label", default="n24_composite")
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

    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)   # inherited by the children
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n2_4", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in args.apis:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", (exc.stderr or b"").decode(errors="replace") if isinstance(
                exc.stderr, bytes) else str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "rounds": list(args.rounds), "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        record["failed_checks"] = _failed_checks(record)
        results[api] = record

    verdicts = {api: api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "require_validation": args.require_validation,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "failed_checks": {api: record.get("failed_checks", []) for api, record in results.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
        v = results[api].get("validation")
        if v:
            print(f"  validation: layer {'loaded' if v.get('layer_loaded') else 'NOT loaded'}, "
                  f"excused {v.get('recorded_qt_defects_excused')}, unexplained errors {v.get('unexplained_errors')}, "
                  f"warnings {v.get('unexplained_warnings')}")
    print(f"evidence: {out / 'summary.json'}")
    print("N24 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
