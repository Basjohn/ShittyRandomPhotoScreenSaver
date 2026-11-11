"""Now Playing (Fullscreen Edit) beside the Media widget's own Edit: the resize gestures and the four sides, as sheets.

    .venv/Scripts/python tools/now_playing_edit_sheet.py --output .artifacts/evidence/visualizers/expanded/<date>_<name>

Plan 1C.3 (and 1B.7's open evidence gap): the operator's contract is the Media widget's Edit. This harness renders,
off-screen (the hidden ``QQuickRenderControl`` production host of ``tools/expanded_visualizer_evidence.py``; no window is
ever shown):

* ``resize_sheet.png``: one row per owner, one panel per gesture (natural, width given, width taken, height given,
  height taken, a corner). The Media card is the production ``MediaPresentation.qml`` through its retained presentation:
  a side handle is its content extent (what ordinary Edit's Save and preview hand the card), a corner its uniform scale
  (the outer rectangle at a multiple of its preferred size). Now Playing is the production overlays in Fullscreen Edit
  through the real ``QuickCustomLayoutOwner`` and its ordinary handlers (side strips and a corner), then Save, then the
  committed value drawn.
* ``sides_sheet.png``: Now Playing moved by Fullscreen Edit's own drag to the left, right, top and bottom of the
  display, saved, drawn.
* ``geometry.json``: every panel's measured rectangles (the artwork frame, the block, the text group).

It reuses the test doubles the focused tests drive (the Media stand-in, the hidden scene's draw helpers and the
Fullscreen Edit driver), so the sheet shows exactly the paths the tests pin. Offscreen output is not physical acceptance.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WIDTH, HEIGHT = 1280, 720
PANEL = (520, 300)
PHOTO = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET\859804.png")
#: (label, Media content-extent delta (dx, dy) or a uniform scale, Now Playing gesture)
GESTURES = (
    ("natural", (0, 0), None),
    ("width given (+160)", (160, 0), ("side", "right", 160)),
    ("width taken (-50)", (-50, 0), ("side", "right", -50)),
    ("height given (+90)", (0, 90), ("side", "bottom", 90)),
    ("height taken (-24)", (0, -24), ("side", "bottom", -24)),
    ("corner (x1.3)", 1.3, ("corner", "bottom_right", 0)),
)


def _font(size: int):
    from PIL import ImageFont

    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def _panel(frame, rect: tuple[float, float, float, float], label: str):
    """A fixed-size panel: ``frame`` cropped around ``rect`` (a margin kept; shrunk to fit, never enlarged), labelled."""
    from PIL import Image, ImageDraw

    image = Image.fromarray(frame, "RGBA").convert("RGB")
    x, y, w, h = rect
    margin = 24
    box = (int(max(0, x - margin)), int(max(0, y - margin)),
           int(min(image.width, x + w + margin)), int(min(image.height, y + h + margin)))
    crop = image.crop(box)
    room = (PANEL[0] - 8, PANEL[1] - 36)
    factor = min(1.0, room[0] / crop.width, room[1] / crop.height)
    if factor < 1.0:
        crop = crop.resize((max(1, round(crop.width * factor)), max(1, round(crop.height * factor))),
                           Image.Resampling.LANCZOS)
    panel = Image.new("RGB", PANEL, (24, 26, 30))
    panel.paste(crop, ((PANEL[0] - crop.width) // 2, 32 + (room[1] - crop.height) // 2))
    draw = ImageDraw.Draw(panel)
    draw.text((8, 4), label, fill=(235, 238, 242), font=_font(17))
    # Where on the display: a small map of the whole display with the measured rectangle on it.
    mw, mh = 96, round(96 * image.height / max(1, image.width))
    mx, my = PANEL[0] - mw - 6, PANEL[1] - mh - 6
    draw.rectangle((mx, my, mx + mw, my + mh), outline=(150, 156, 166))
    k = mw / image.width
    draw.rectangle((mx + x * k, my + y * k, mx + (x + w) * k, my + (y + h) * k), fill=(90, 160, 240))
    return panel


def _sheet(rows: list[tuple[str, list]], out: Path, title: str) -> None:
    from PIL import Image, ImageDraw

    columns = max(len(panels) for _name, panels in rows)
    head, side = 44, 190
    sheet = Image.new("RGB", (side + columns * (PANEL[0] + 8), head + len(rows) * (PANEL[1] + 8)), (12, 13, 16))
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 10), title, fill=(240, 240, 240), font=_font(22))
    for row, (name, panels) in enumerate(rows):
        y = head + row * (PANEL[1] + 8)
        draw.text((10, y + PANEL[1] // 2 - 12), name, fill=(220, 224, 230), font=_font(18))
        for column, panel in enumerate(panels):
            sheet.paste(panel, (side + column * (PANEL[0] + 8), y))
    sheet.save(out)


def _rect(item, root) -> tuple[float, float, float, float]:
    from PySide6.QtCore import QRectF

    mapped = item.mapRectToItem(root, QRectF(0.0, 0.0, item.width(), item.height()))
    return (round(mapped.x(), 2), round(mapped.y(), 2), round(mapped.width(), 2), round(mapped.height(), 2))


# ---------------------------------------------------------------------------------------------------- Media


def media_row(record: dict) -> list:
    from PySide6.QtGui import QImage
    from PySide6.QtQuick import QQuickItem

    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.media import RetainedMediaPresentation
    from tests.test_qtquick_media_presentation import _FakeMediaRuntime, _image, _model, _snapshot
    from tests.test_visualizer_expansion_overlays import _frame, _run
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    display = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    panels = []
    try:
        runtime = _FakeMediaRuntime()
        model, _service, _provider = _model(display.factory.media_artwork_provider, runtime)
        origin = (60.0, 60.0)
        presentation = RetainedMediaPresentation(host=display.scene.ordinary_widget_host, model=model,
                                                 geometry=OverlayWidgetGeometry(*origin, 620.0, 330.0))
        item = presentation.item
        presentation.activate(object())
        photo = QImage(str(PHOTO)) if PHOTO.is_file() else _image()
        runtime.publish(_snapshot(1, image=photo.scaled(320, 200) if not photo.isNull() else _image()))
        _run(display, 200)
        preferred = (float(item.property("preferredContentWidth")), float(item.property("preferredContentHeight")))
        root = display.window.contentItem()
        art = item.findChild(QQuickItem, "mediaArtworkFrame")
        for label, change, _gesture in GESTURES:
            if isinstance(change, float):
                model.clear_content_extent()
                size = (preferred[0] * change, preferred[1] * change)
            else:
                if change == (0, 0):
                    model.clear_content_extent()
                else:
                    model.set_content_extent(preferred[0] + change[0], preferred[1] + change[1])
                _run(display, 60)
                size = (float(item.property("preferredContentWidth")), float(item.property("preferredContentHeight")))
            presentation.set_geometry(OverlayWidgetGeometry(origin[0], origin[1], size[0], size[1]))
            _run(display, 120)
            frame = _frame(display)
            card = _rect(item, root)
            artwork = _rect(art, root)
            record[label] = {"card": card, "artwork": artwork}
            panels.append(_panel(frame, card, f"{label}: art {artwork[2]:.0f} x {artwork[3]:.0f}"))
        presentation.retire() if hasattr(presentation, "retire") else None
    finally:
        display.close()
    return panels


# ---------------------------------------------------------------------------------------------- Now Playing


def _now_playing_parts(display) -> dict[str, Any]:
    from tests.test_visualizer_expansion_overlays import _named, _slot

    slot = _slot(display, "expandedOverlayNowPlaying")
    root = display.window.contentItem()
    found = {"block": _rect(slot, root)}
    for key, name in (("artwork", "expandedOverlayArtwork"), ("text", "expandedOverlayNowPlayingText")):
        item = _named(slot, name)
        if item is not None:
            found[key] = _rect(item, root)
    found["right_oriented"] = bool(slot.property("contentRightSide"))
    return found


def _fullscreen_display(settings, media, value):
    from tests.test_visualizer_expansion_fullscreen_edit import _projection, _shown_and_settled
    from tests.test_visualizer_expansion_overlays import _draw, _open
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    display = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    _draw(display, media=media, config=_projection(value))
    _open(display)
    _shown_and_settled(display)
    return display


def _media_stand_in():
    from tests.test_visualizer_expansion_overlays import _Media

    source = PHOTO.as_uri() if PHOTO.is_file() else ""
    return _Media(title="Midnight City", artist="M83", artworkSource=source, album="Hurry Up, We're Dreaming")


def now_playing_rows(record: dict, sides: dict, workdir: Path) -> tuple[list, list]:
    from tests.test_visualizer_expansion_fullscreen_edit import _Fullscreen, _manager, _projection, _seed, _value
    from tests.test_visualizer_expansion_overlays import _frame, _run

    resize_panels: list = []
    # Lifted from the bottom edge (a bottom handle has room to grow), at the left: the authored bottom_left corner.
    # Always Show keeps the block drawn after Save (no geometry effect).
    placement = {"offset_x": 0.04, "offset_y": -0.3, "always_show": True}
    for index, (label, _change, gesture) in enumerate(GESTURES):
        settings = _manager(workdir / f"resize_{index}")
        seeded = _seed(settings, now_playing=placement)
        media = _media_stand_in()
        display = _fullscreen_display(settings, media, seeded)
        try:
            if gesture is not None:
                edit = _Fullscreen(display, settings)
                assert edit.start()
                kind, handle, delta = gesture
                if kind == "side":
                    edit.side("now_playing", handle, delta)
                else:
                    frame = edit.item("now_playing").current_global_rect
                    edit.corner("now_playing", handle, round(frame.width() * 0.3), round(frame.height() * 0.3))
                _run(display, 80)
                assert edit.owner.save()
                _run(display, 80)
                display.scene.set_visualizer_expanded_overlay_config(_projection(_value(settings)))
                _run(display, 120)
            frame = _frame(display)
            parts = _now_playing_parts(display)
            parts["stored"] = {k: v for k, v in _value(settings)["now_playing"].items()
                               if k in ("scale", "text_width", "text_height", "child_geometry")}
            record[label] = parts
            artwork = parts.get("artwork", (0, 0, 0, 0))
            resize_panels.append(_panel(frame, parts["block"], f"{label}: art {artwork[2]:.0f} x {artwork[3]:.0f}"))
        finally:
            display.close()

    side_panels: list = []
    moves = {
        # (label, drag delta from the natural bottom_left place, as fractions of the display)
        "left side": (0.0, -0.32),
        "right side": (0.66, -0.32),
        "top side (left half)": (0.18, -0.7),
        "bottom side (right half)": (0.5, 0.0),
    }
    for index, (label, (fx, fy)) in enumerate(moves.items()):
        settings = _manager(workdir / f"side_{index}")
        seeded = _seed(settings, now_playing={"always_show": True})
        display = _fullscreen_display(settings, _media_stand_in(), seeded)
        try:
            edit = _Fullscreen(display, settings)
            assert edit.start()
            edit.drag("now_playing", round(WIDTH * fx), round(HEIGHT * fy), steps=10)
            _run(display, 80)
            assert edit.owner.save()
            _run(display, 80)
            display.scene.set_visualizer_expanded_overlay_config(_projection(_value(settings)))
            _run(display, 120)
            frame = _frame(display)
            parts = _now_playing_parts(display)
            sides[label] = parts
            orientation = "artwork right" if parts["right_oriented"] else "artwork left"
            side_panels.append(_panel(frame, parts["block"], f"{label}: {orientation}"))
        finally:
            display.close()
    return resize_panels, side_panels


def main(argv: list[str] | None = None) -> int:
    from tools import artifact_paths

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=artifact_paths.evidence_arg, required=True)
    parser.add_argument("--label", default="", help="a word for the sheets' titles (before / after)")
    args = parser.parse_args(argv)

    from rendering.quick.bootstrap import configure_quick_graphics

    configure_quick_graphics(reason="now-playing-edit-sheet")
    from PySide6.QtWidgets import QApplication

    app = QApplication(["now-playing-edit-sheet"])
    from tools.evidence_media import evidence_workspace

    with evidence_workspace("now-playing-edit-sheet", Path(args.output)) as work:
        work.mkdir(parents=True, exist_ok=True)
        _run_sheets(work, args.label)
    del app
    return 0


def _run_sheets(out: Path, label: str) -> None:
    import subprocess

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    document: dict[str, Any] = {"commit": commit, "display": [WIDTH, HEIGHT], "dpr": 1.0, "media": {},
                                "now_playing": {}, "sides": {}}
    media_panels = media_row(document["media"])
    with tempfile.TemporaryDirectory(prefix="np_sheet_") as workdir:
        resize_panels, side_panels = now_playing_rows(document["now_playing"], document["sides"], Path(workdir))
    tag = f" ({label})" if label else ""
    _sheet([("Media card\n(ordinary Edit)", media_panels), ("Now Playing\n(Fullscreen Edit)", resize_panels)],
           out / "resize_sheet.png", f"Resize gestures: Media card vs Now Playing{tag}")
    _sheet([("Now Playing\nmoved by Edit", side_panels)], out / "sides_sheet.png",
           f"Now Playing moved to each side of the display{tag}")
    (out / "geometry.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
