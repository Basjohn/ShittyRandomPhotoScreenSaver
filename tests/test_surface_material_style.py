"""Card surface materials, the 6 Nov style pass (Docs/Architecture/Card_Surface_Materials.md 3.3).

What these bars protect:
- the legibility layer is the card's whole face, up to and under the real border, with no inset
  panel or inner rim (12 Nov, 1B.8 M2; superseded the 7 Nov panel 2-3 px inside the border);
  Glass keeps its edge highlight at the real border;
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
@pytest.mark.parametrize("border", [0.0, 3.0])
def test_the_face_reaches_the_border_with_no_inner_rim(material_scene, radius, border) -> None:
    import numpy
    from PySide6.QtGui import QColor

    scene = material_scene
    scene.set_wallpaper(_flat_image(640, 360, (200, 200, 200, 255), "grey"))
    # A transparent ring shows what the material draws under the border: the same face.
    _card(scene, border_width=border, corner_radius=radius, border_color=QColor(0, 0, 0, 0))
    # Acrylic: no edge highlight, so any step near the border would be an inset panel.
    scene.set_material("acrylic")
    scene.render(4)
    frame = numpy.asarray(scene.read(), numpy.float64).sum(axis=2)
    # Columns averaged over 40 rows (the material's static grain is per pixel).
    column = frame[160:200].mean(axis=0)
    centre = column[320]
    for inward in (1, 2, 3, 6):                                    # 1.5 .. 6.5 px in: one even face
        assert abs(column[170 + inward] - centre) <= 4, (inward, column[168:180].round())
    # The corner is the same face up to the arc: 1.5 px inward along the corner's diagonal.
    along = int(round(radius - radius / 2 ** 0.5 + 1.5 / 2 ** 0.5 + 1))
    patch = frame[100 + along - 1:100 + along + 2, 170 + along - 1:170 + along + 2].mean()
    assert abs(patch - centre) <= 10


def test_glass_keeps_its_edge_highlight_at_the_real_border(material_scene) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat_image(640, 360, (60, 60, 60, 255), "dark grey"))
    _card(scene, border_width=0.0, corner_radius=12.0)
    scene.set_material("glass")
    scene.render(4)
    frame = numpy.asarray(scene.read(), numpy.float64).sum(axis=2)
    row = frame[100:140].mean(axis=0)                              # the upper-left (lit) edge
    column = frame[100:104, 200:440].mean(axis=0).mean()
    assert row[170 + 1] > row[170 + 8] + 6                         # brighter right at the border
    assert abs(row[170 + 8] - row[320]) <= 6                       # gone by 8 px: the face
    assert column > frame[150:200, 200:440].mean() + 6             # the top edge too


def test_the_legibility_layer_is_the_whole_face_in_every_surface_shader() -> None:
    for name in ("surface_material.frag", "text_legibility.frag", "text_legibility.vert"):
        shader = (QML / "shaders" / name).read_text(encoding="utf-8")
        block = shader[shader.index("// SURFACE BEGIN"):shader.index("// SURFACE END")]
        assert "plateInset" not in block and "float plate = 1.0;" in block, name
        # The edge highlight is added after the legibility layer, so the panel never flattens it.
        assert block.index("c += vec3(edgeHighlight);") > block.index("panelCeiling * plate"), name


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


def test_a_run_on_its_own_fill_is_judged_on_that_fill(material_scene) -> None:
    # 1B.8 follow-up: a run inside a further fill (a metric panel, a tile) has its ink judged on
    # that fill, not on the card panel, so a run that reads where it sits keeps its authored
    # colour byte for byte; the same run on the card panel itself is still corrected.
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickItem

    scene = material_scene
    scene.set_wallpaper(_flat_image(640, 360, (235, 235, 235, 255), "bright"))
    card = _card(scene)
    component = QQmlComponent(scene.scene.qml_context.engine())
    component.setData(b"""import QtQuick
Item { x: 10; y: 30; width: 280; height: 90
  ShadowedText { objectName: "onCard"; x: 4; y: 0; width: 120; height: 20; text: "CPU LOAD"
                 color: "#d7668cff"; font.pixelSize: 12; shadowEnabled: false }
  Rectangle { id: panel; objectName: "panel"; y: 30; width: 280; height: 60; radius: 8; color: "#ff05060a"
    readonly property Item textLegibilityRow: panelRow
    LegibilityRow { id: panelRow; x: 3; y: 3; width: 274; height: 54; radius: 5
                    underlayColor: panel.color; primaryColor: "#d7668cff" }
    ShadowedText { objectName: "onPanel"; x: 4; y: 20; width: 120; height: 20; text: "CPU LOAD"
                   color: "#d7668cff"; font.pixelSize: 12; shadowEnabled: false }
  }
}""", QUrl.fromLocalFile(str(QML / "_test_underlay.qml")))
    block = component.create(scene.scene.qml_context)
    assert block is not None, component.errorString()
    content = card.item.findChild(QQuickItem, "overlayCardContent")
    block.setParentItem(content)
    block.setParent(content)
    try:
        scene.set_material("glass")
        scene.render(4)
        on_card = block.findChild(QQuickItem, "onCard")
        on_panel = block.findChild(QQuickItem, "onPanel")
        authored = on_card.property("color")
        assert on_card.property("inkColor") != authored                # misses on the card panel
        assert on_panel.property("inkColor") == authored               # reads on its own fill: untouched
        assert on_panel.property("underlayColor") == block.findChild(QQuickItem, "panel").property("color")
    finally:
        block.deleteLater()


def test_every_fill_with_a_legibility_row_names_it_for_its_runs() -> None:
    # The row and the runs on a fill judge against the same surface (ShadowedText finds the row
    # on the run's ancestors as textLegibilityRow and takes its fill and its lift).
    for path in list(QML.glob("*Presentation.qml")) + [QML / "AchievementCapsule.qml"]:
        text = path.read_text(encoding="utf-8")
        rows = len(list(_qml_blocks(text, "LegibilityRow {")))
        assert text.count("readonly property Item textLegibilityRow:") == rows, path.name


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
