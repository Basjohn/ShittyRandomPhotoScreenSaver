"""Hidden capture of the Studio's shape instrument (the node curve with its frequency lanes) in its states.

No window is shown: the real Studio shell renders through QQuickRenderControl into a GL texture (the hidden
``OffscreenStudioSurface``) against an in-memory store, so nothing is saved. The pointer is real mouse events sent to
that hidden window. For each shape instrument of the mode it writes the instrument alone and at twice its pixels
(nearest neighbour: what the pixels are), at rest and with a node hovered, a node held mid-drag (before release), a
node selected, a lane's strength held, and the hint where a click would add a node; the whole Studio too at rest and
mid-drag (``--whole`` names the states).

A theme with a native material is rendered with its alpha and laid over Settings' own material stand-in
(``ui.settings_material_underlay``), since a hidden surface has no desktop behind it.

    .venv\\Scripts\\python.exe tools\\studio_shape_capture.py --mode spectrum
    .venv\\Scripts\\python.exe tools\\studio_shape_capture.py --mode shockwave_grid --theme "themes\\Pearl Blush [Three-Tone] [Frosted].srtheme" --dpr 1.5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402
from tools.waveform_studio_capture import MemoryStore, NoPresence  # noqa: E402

STATES = ("rest", "hover", "drag", "selected", "strength", "add_hint")
WHOLE = ("rest", "drag")         # the states also kept as the whole Studio (the others: the instrument alone)


def _named(root, name: str) -> list:
    found, stack = [], [root]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            found.append(item)
        stack.extend(reversed(item.childItems()))
    return found


def _shown(item) -> bool:
    while item is not None:
        if not item.isVisible():
            return False
        item = item.parentItem()
    return True


class Pointer:
    """Real mouse events on the hidden Studio window, in the coordinates of one item."""

    def __init__(self, surface, item) -> None:
        self.window, self.item, self.clock = surface.window, item, 1000

    def _send(self, kind, x: float, y: float, button=None) -> None:
        from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        pos = self.item.mapToScene(QPointF(x, y))
        button = button or Qt.MouseButton.LeftButton
        held = Qt.MouseButton.NoButton if kind in (QEvent.Type.MouseButtonRelease, "hover") else button
        if kind == "hover":
            kind, button = QEvent.Type.MouseMove, Qt.MouseButton.NoButton
        elif kind == QEvent.Type.MouseMove:
            button = Qt.MouseButton.NoButton
        event = QMouseEvent(kind, pos, pos, pos, button, held, Qt.KeyboardModifier.NoModifier)
        self.clock += 4
        event.setTimestamp(self.clock)
        QCoreApplication.sendEvent(self.window, event)

    def hover(self, x: float, y: float) -> None:
        self._send("hover", x, y)

    def press(self, x: float, y: float, button=None) -> None:
        from PySide6.QtCore import QEvent
        self._send(QEvent.Type.MouseButtonPress, x, y, button)

    def move(self, x: float, y: float) -> None:
        from PySide6.QtCore import QEvent
        self._send(QEvent.Type.MouseMove, x, y)

    def release(self, x: float, y: float, button=None) -> None:
        from PySide6.QtCore import QEvent
        self._send(QEvent.Type.MouseButtonRelease, x, y, button)


def node_point(row, index: int) -> tuple[float, float]:
    """Where node ``index`` is drawn, in the row's well: the shell's own handle item (never a second mapping)."""
    item = _named(row, "shapeNode")[index]
    return float(item.x()), float(item.y())


def lane_point(row, index: int) -> tuple[float, float]:
    """Where lane ``index``'s strength marker is drawn, in the row's well."""
    item = _named(row, "shapeLaneMarker")[index]
    return float(item.x() + item.width() / 2.0), float(item.y() + item.height() / 2.0)


def reveal(row) -> None:
    """Scroll the row's panel so the instrument starts at the top of what the panel shows (as a user would)."""
    from PySide6.QtCore import QPointF
    scroll = row.parentItem()
    while scroll is not None and scroll.objectName() != "inspectorScroll":
        scroll = scroll.parentItem()
    if scroll is None:
        return
    flick = scroll.property("contentItem")
    top = row.mapToItem(flick.property("contentItem"), QPointF(0.0, 0.0)).y()
    limit = max(0.0, float(flick.property("contentHeight")) - flick.height())
    flick.setProperty("contentY", max(0.0, min(limit, top - 4.0)))


def settle(surface, seconds: float = 0.35) -> None:
    """Pump frames for a while of wall time (the shell's fades run on the animation clock)."""
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        surface.pump()
        time.sleep(0.012)
    surface.pump()


def composed(pixels, underlay):
    """The grabbed frame (premultiplied alpha) over ``underlay`` (r, g, b in 0..255), opaque."""
    import numpy
    rgb = pixels[..., :3].astype(numpy.float32)
    alpha = pixels[..., 3:4].astype(numpy.float32) / 255.0
    out = rgb + numpy.asarray(underlay, dtype=numpy.float32) * (1.0 - alpha)
    return numpy.clip(out + 0.5, 0, 255).astype(numpy.uint8)


def capture(output: Path, *, mode: str = "spectrum", theme: Path | None = None, dpr: float = 1.0,
            size: tuple[int, int] = (1600, 900), preset: int = 1, overrides: dict | None = None,
            states: tuple[str, ...] = STATES, whole: tuple[str, ...] = WHOLE, tag: str = "") -> dict:
    """Render ``mode``'s shape instruments in ``states`` into ``output`` (created); returns the record written
    beside them. Needs a QApplication; never shows a window."""
    from PIL import Image
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem
    from core.settings.visualizer_mode_settings import mode_settings
    from core.settings.visualizer_presets import get_preset_names, resolve_visualizer_activation_payload
    from ui.settings_material_underlay import material_underlay
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.schema import SHAPE
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.theme import studio_theme

    original = get_active_settings_theme()
    if theme is not None:
        from ui.settings_theme_io import load_settings_theme_file
        set_active_settings_theme(load_settings_theme_file(theme))
    active = get_active_settings_theme()
    underlay = material_underlay(active)
    underlay = (underlay.r, underlay.g, underlay.b)
    tokens = studio_theme(active)
    values = dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": preset - 1},
                                                        mode=mode).resolved_config)
    spec = mode_settings(mode)
    if spec is not None:
        values.update({c.key: c.admit(values[c.key], values[c.key]) for c in spec.controls if c.key in values})
    values.update(overrides or {})
    store = MemoryStore(values, get_preset_names(mode)[preset - 1])
    adapter = create_adapter(mode)
    adapter.recorded_clips = lambda: ()                  # the held fixture: no clip analysis in the background
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=size, dpr=dpr, present_on_show=False,
                                               transparent=True))
        return surfaces[0]

    controller = StudioController(adapter, store, NoPresence(), factory, theme_provider=studio_theme)
    if not controller.open():
        raise RuntimeError("Studio did not open")
    surface, bridge = surfaces[0], controller.bridge
    name = (theme.stem if theme is not None else "active").split(" [")[0].replace(" ", "_").lower()
    stem = f"{mode}_{name}_dpr{dpr:g}".replace(".", "p") + (f"_{tag}" if tag else "")
    record = {"mode": mode, "theme": theme.name if theme is not None else "active", "backdrop": tokens["backdrop"],
              "light": tokens["light"], "dpr": dpr, "size": list(size), "underlay": list(underlay), "images": []}
    output.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(8000):                        # the fixture's analysis lands (a worker, up to ~40 s)
            surface.pump()
            if bridge.viewportStatus != "preparing" and not getattr(controller.evaluator, "analysing", False) \
                    and not getattr(controller.evaluator, "converging", False):
                break
            time.sleep(0.005)
        schema = controller.session.schema
        rows = [schema.find(shape.property) for shape in schema.shapes]
        if not rows or any(prop.instrument != SHAPE for prop in rows):
            raise RuntimeError(f"{mode} has no shape instrument")

        def save(label: str, row_item, studio: bool) -> None:
            frame = composed(surface.grab(), underlay)
            origin = row_item.mapToScene(QPointF(0.0, 0.0))
            x0, y0 = max(0, int((origin.x() - 8) * dpr)), max(0, int((origin.y() - 8) * dpr))
            x1 = min(frame.shape[1], int((origin.x() + row_item.width() + 8) * dpr))
            y1 = min(frame.shape[0], int((origin.y() + row_item.height() + 8) * dpr))
            crop = Image.fromarray(frame[y0:y1, x0:x1])
            paths = {"instrument": output / f"{label}_instrument.png",
                     "instrument_2x": output / f"{label}_instrument_2x.png"}
            if studio:
                paths["studio"] = output / f"{label}_studio.png"
                Image.fromarray(frame).save(paths["studio"])
            crop.save(paths["instrument"])
            crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST).save(paths["instrument_2x"])
            record["images"].extend(str(path) for path in paths.values())

        for prop in rows:
            bridge.setWorkspace(prop.workspace)
            settle(surface, 0.2)
            row = next((item for item in _named(surface.host.root, "shapeRow")
                        if _shown(item) and item.property("row")["id"] == prop.id), None)
            if row is None:
                raise RuntimeError(f"{prop.id}: its instrument is not shown")
            well = next(item for item in _named(row, "shapeWell"))
            if not isinstance(well, QQuickItem):
                raise RuntimeError("the shape well is not an item")
            reveal(row)
            settle(surface, 0.2)
            pointer, away = Pointer(surface, well), Pointer(surface, surface.host.root)
            label = f"{stem}_{prop.id}"
            index = min(1, len(row.property("nodes")) - 1)
            x, y = node_point(row, index)
            for number, state in enumerate(states):
                if number:                               # (the first state is the untouched instrument)
                    pointer.press(2.0, 2.0)              # the well's empty corner: nothing selected
                    pointer.release(2.0, 2.0)
                away.hover(6.0, 6.0)                     # the pointer off the panels (no tooltip, no hover)
                settle(surface, 0.25)
                thinned, commits = False, controller.session.commit_count
                if state == "hover":
                    pointer.hover(x + 2.0, y + 1.0)
                elif state == "drag":
                    pointer.press(x, y)
                    for step in range(1, 9):
                        pointer.move(x - 4.0 * step, y + 3.5 * step)
                        surface.pump()
                elif state == "selected":
                    pointer.press(x, y)
                    pointer.release(x, y)
                    away.hover(6.0, 6.0)
                elif state == "strength":
                    lane = min(1, len(row.property("lanes")) - 1)
                    lx, ly = lane_point(row, lane)
                    pointer.press(lx, ly)
                    for step in range(1, 7):
                        pointer.move(lx, ly - 2.0 * step)
                        surface.pump()
                elif state == "add_hint":
                    shape = schema.shape(prop.id)
                    if not row.property("shown")["canAdd"] and shape.remove:
                        bridge.runAction(f"{shape.remove}1")     # a full curve offers no add: free a slot
                        thinned = True
                        settle(surface, 0.3)
                    pointer.hover(well.width() * 0.27, well.height() * 0.42)
                settle(surface, 0.3)
                save(f"{label}_{state}", row, state in whole)
                if state in ("drag", "strength"):
                    record.setdefault("held", {})[f"{prop.id}:{state}"] = {
                        "gesture_active": controller.session.gesture_active,
                        "commits_while_held": controller.session.commit_count - commits}
                    pointer.release(x, y)
                    settle(surface, 0.15)
                    bridge.undo()                    # the next state starts from the stored shape
                    settle(surface, 0.15)
                elif thinned:
                    bridge.undo()
                    settle(surface, 0.3)
        (output / f"{stem}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    finally:
        controller.close()
        set_active_settings_theme(original)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=artifact_paths.evidence_arg,
                        default=artifact_paths.default_evidence("studio", "shape_instrument"))
    parser.add_argument("--mode", default="spectrum", help="A registered Studio mode with a shape instrument")
    parser.add_argument("--theme", type=Path, default=None, help="A .srtheme to activate for this capture")
    parser.add_argument("--dpr", type=float, default=1.0, help="Device pixel ratio of the hidden surface")
    parser.add_argument("--size", default="1600x900")
    parser.add_argument("--preset", type=int, default=1)
    parser.add_argument("--states", default=",".join(STATES))
    parser.add_argument("--whole", default=",".join(WHOLE), help="States also kept as the whole Studio window")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON",
                        help="Override one value of the in-memory store (evidence only; nothing is saved)")
    parser.add_argument("--tag", default="", help="Suffix for output names")
    args = parser.parse_args()
    evidence_media.redirect_output(args, "output", "studio_shape_capture")
    width, height = (int(v) for v in args.size.split("x"))
    overrides = {}
    for override in args.set:
        key, _, text = override.partition("=")
        overrides[key.strip()] = json.loads(text)

    from rendering.quick.bootstrap import configure_quick_graphics
    configure_quick_graphics(reason="studio-shape-capture")
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    record = capture(args.output, mode=args.mode, theme=args.theme, dpr=args.dpr, size=(width, height),
                     preset=args.preset, overrides=overrides, states=tuple(args.states.split(",")),
                     whole=tuple(args.whole.split(",")), tag=args.tag)
    app.processEvents()
    print(json.dumps(record, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main()))
