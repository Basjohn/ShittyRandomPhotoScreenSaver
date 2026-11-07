"""Card surface materials, the 6 Nov style pass (Docs/Architecture/Card_Surface_Materials.md 3.3).

What these bars protect:
- the legibility layer is one card-wide inner panel 2-3 px inside the border whose corners
  follow the card's configured radius, concentric, never sharp (7 Nov: not a block stopping
  ~8 px in, not a box hugging the text);
- that panel is the card's only darkening: no per-line rows or per-run chips on the card
  itself; a row remains only inside a control's own filled panel (tile, capsule, stats panel);
- every shadowed run follows the light-palette soft shadow (no doubled hard glyphs);
- the Media transport bar's shadow is not cut at the padding and the mute button clears
  the bar's rounded end cap.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


@pytest.fixture
def material_scene(qt_app):
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("hidden GL scene needs the Windows QPA")
    scene = MaterialScene(640, 360)
    yield scene
    scene.close()


def _flat_image(width, height, rgba, identity):
    from rendering.quick.image_state import PresentationImage

    return PresentationImage(identity, identity, (float(width), float(height)), 1.0, (width, height),
                             width * 4, bytes(rgba) * (width * height))


def _card(scene, **style):
    from PySide6.QtGui import QColor
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    card = scene.host.create_widget(object_name="card", model_identity="clock",
                                    geometry=OverlayWidgetGeometry(170, 100, 300, 160),
                                    card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 77),
                                                                shadow_enabled=False, **style))
    scene.presentations = []
    return card


@pytest.mark.parametrize("radius", [12.0, 20.0])
def test_legibility_layer_reaches_within_three_px_of_the_border_with_concentric_corners(material_scene,
                                                                                         radius) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat_image(640, 360, (200, 200, 200, 255), "grey"))
    _card(scene, border_width=0.0, corner_radius=radius)
    scene.set_material("frosted")
    scene.render(4)
    frame = numpy.asarray(scene.read(), numpy.float64).sum(axis=2)
    # Columns averaged over 40 rows (the material's static grain is per pixel).
    column = frame[160:200].mean(axis=0)
    centre = column[320]
    assert abs(column[170 + 3] - centre) <= 4                     # 3.5 px in: inside the panel
    assert column[170 + 1] - centre > 8                           # 1.5 px in: the rim is lighter
    # Concentric corner (this card's own radius): 4 px inward along the corner's diagonal is
    # already inside the panel.
    along = int(round(radius - radius / 2 ** 0.5 + 4 / 2 ** 0.5 + 1))
    patch = frame[100 + along - 1:100 + along + 2, 170 + along - 1:170 + along + 2].mean()
    assert abs(patch - centre) <= 10


def test_legibility_panel_inset_is_two_to_three_px_and_its_corners_are_never_sharp() -> None:
    for name in ("surface_material.frag", "text_legibility.frag", "text_legibility.vert"):
        shader = (QML / "shaders" / name).read_text(encoding="utf-8")
        inset = re.search(r"float plateInset = borderWidth < 0\.0 \? -?[0-9.]+ : borderWidth \+ ([0-9.]+);", shader)
        assert inset is not None and 2.0 <= float(inset.group(1)) <= 3.0, name
        # The panel radius is the card's configured radius less the inset, floored above 0.
        floor = re.search(r"roundedBox\(p, plateHalf, max\(([0-9.]+), r - plateInset\), plateNormal\)", shader)
        assert floor is not None and float(floor.group(1)) >= 1.0, name


def test_a_list_line_gets_one_even_row_that_holds_the_floor_for_every_run(material_scene) -> None:
    import numpy
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickItem
    from rendering.quick.image_state import PresentationImage
    from tools.surface_material_capture import measure_text_legibility

    scene = material_scene
    width, height = 640, 360
    stripes = bytearray()
    for _y in range(height):
        for x in range(width):
            stripes += bytes((250, 240, 150, 255)) if (x // 6) % 2 else bytes((235, 200, 245, 255))
    scene.set_wallpaper(PresentationImage("stripes", "stripes", (640.0, 360.0), 1.0, (width, height),
                                          width * 4, bytes(stripes)))
    card = _card(scene)
    component = QQmlComponent(scene.scene.qml_context.engine())
    component.setData(b"""import QtQuick
Item { x: 10; y: 40; width: 260; height: 24
  Rectangle { anchors.fill: parent; radius: 6; color: "#40303030" }
  LegibilityRow { objectName: "testRow"; x: 0; width: parent.width; height: parent.height
                  primaryColor: "#d0d0d0"; secondaryColor: "#8a8a8a"; underlayColor: "#40303030"; radius: 6 }
  ShadowedText { x: 4; width: 60; height: 24; text: "03D AGO"; color: "#8a8a8a"; font.pixelSize: 12
                 verticalAlignment: Text.AlignVCenter; shadowEnabled: false }
  ShadowedText { x: 146; width: 110; height: 24; text: "Desert Road"; color: "#d0d0d0"
                 font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; shadowEnabled: false }
}""", QUrl.fromLocalFile(str(QML / "_test_row.qml")))
    line = component.create(scene.scene.qml_context)
    assert line is not None, component.errorString()
    content = card.item.findChild(QQuickItem, "overlayCardContent")
    line.setParentItem(content)
    line.setParent(content)
    scene.render(4)
    out = Path(__file__).resolve().parent / "_surface_material_row.png"
    try:
        normal = numpy.asarray(scene.read(), numpy.int16)
        row = line.findChild(QQuickItem, "testRow")
        assert row.property("active") is False                    # Normal: nothing loaded
        scene.set_material("glass")
        scene.render(4)
        assert row.property("active") is True
        runs = [r for r in measure_text_legibility(scene, out) if r["text"] in ("03D AGO", "Desert Road")]
        assert len(runs) == 2 and all(r["p5"] >= 4.5 for r in runs), runs
        scene.set_material("normal")
        scene.render(3)
        assert numpy.array_equal(numpy.asarray(scene.read(), numpy.int16), normal)
    finally:
        out.unlink(missing_ok=True)
        line.deleteLater()


def _qml_blocks(text: str, head: str):
    for match in re.finditer(re.escape(head), text):
        index, depth = match.end(), 1
        while depth:
            depth += {"{": 1, "}": -1}.get(text[index], 0)
            index += 1
        yield text[match.start():index]


def test_the_card_panel_is_the_only_darkening_on_the_card_itself() -> None:
    # 7 Nov (operator): one panel from above the header to below the last element, never a
    # box hugging a line. A LegibilityRow survives only inside a control's own filled panel
    # (it passes that fill as underlayColor); nothing on the card itself and no per-run chips.
    for path in QML.glob("*.qml"):
        text = path.read_text(encoding="utf-8")
        assert "surfacePlateEnabled" not in text, path.name
        if path.name == "LegibilityRow.qml":
            continue
        for block in _qml_blocks(text, "LegibilityRow {"):
            assert "underlayColor:" in block, (path.name, block[:120])
            # Same rule as the card's panel: 2-3 px inside its panel's border, concentric.
            inset = re.search(r"readonly property real inset: [\w.]+ \+ ([0-9.]+)", block)
            assert inset is not None and 2.0 <= float(inset.group(1)) <= 3.0, (path.name, block[:120])
            assert re.search(r"radius: Math\.max\(0\.0, \w+\.radius - inset\)", block), (path.name, block[:120])
    row = (QML / "LegibilityRow.qml").read_text(encoding="utf-8")
    assert "active: surfaceCard !== null && surfaceCard.surfaceMaterialActive" in row


def test_every_shadowed_text_run_follows_the_light_palette_soft_shadow() -> None:
    missing = []
    for path in QML.glob("*.qml"):
        text = path.read_text(encoding="utf-8")
        for block in _qml_blocks(text, "ShadowedText {"):
            if "shadowEnabled" in block and "shadowSoft" not in block:
                missing.append((path.name, block[:80]))
    assert not missing, missing


def test_media_bar_shadow_is_not_cut_and_the_mute_button_clears_the_end_cap() -> None:
    media = (QML / "MediaPresentation.qml").read_text(encoding="utf-8")
    column = media.split('objectName: "mediaContent"', 1)[1].split("Item {", 1)[0]
    assert "clip: false" in column and "clip: true" not in column
    mute = media.split('objectName: "mediaSystemMuteButton"', 1)[1].split("transform:", 1)[0]
    assert "anchors.rightMargin: Math.max(8.0, (parent.height - height) / 2.0)" in mute
