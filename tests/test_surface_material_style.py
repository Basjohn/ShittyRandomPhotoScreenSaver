"""Card surface materials, the 6 Nov style pass (Docs/Architecture/Card_Surface_Materials.md 3.3).

What these bars protect:
- the legibility layer is one inner panel 2.5 px inside the border with concentric corners
  (not a block stopping ~8 px in with a 12 px feather and near-square corners);
- a list line gets ONE even rounded row that holds the contrast floor for every run on it
  (not a chip per run), and every list family is wired that way;
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


def test_legibility_layer_reaches_within_three_px_of_the_border_with_concentric_corners(material_scene) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat_image(640, 360, (200, 200, 200, 255), "grey"))
    _card(scene, border_width=0.0, corner_radius=12.0)
    scene.set_material("frosted")
    scene.render(4)
    frame = numpy.asarray(scene.read(), numpy.float64).sum(axis=2)
    # Columns averaged over 40 rows (the material's static grain is per pixel).
    column = frame[160:200].mean(axis=0)
    centre = column[320]
    assert abs(column[170 + 4] - centre) <= 4                     # 4 px in: inside the layer
    assert column[170 + 1] - centre > 8                           # the rim right inside is lighter
    # Concentric corner: 4 px inward along the corner's diagonal is already inside the layer.
    along = int(round(12 - 12 / 2 ** 0.5 + 4 / 2 ** 0.5 + 1))
    patch = frame[100 + along - 1:100 + along + 2, 170 + along - 1:170 + along + 2].mean()
    assert abs(patch - centre) <= 10
    shader = (QML / "shaders" / "surface_material.frag").read_text(encoding="utf-8")
    assert "float plateInset = max(0.0, borderWidth) + 2.5;" in shader
    assert "max(0.0, r - plateInset)" in shader


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
  LegibilityRow { objectName: "testRow"; x: -4; width: parent.width + 8; height: parent.height
                  primaryColor: "#d0d0d0"; secondaryColor: "#8a8a8a" }
  ShadowedText { x: 0; width: 60; height: 24; text: "03D AGO"; color: "#8a8a8a"; font.pixelSize: 12
                 verticalAlignment: Text.AlignVCenter; surfacePlateEnabled: false; shadowEnabled: false }
  ShadowedText { x: 150; width: 110; height: 24; text: "Desert Road"; color: "#d0d0d0"
                 font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; surfacePlateEnabled: false
                 shadowEnabled: false }
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
        glass = numpy.asarray(scene.read(), numpy.int16)
        runs = [r for r in measure_text_legibility(scene, out) if r["text"] in ("03D AGO", "Desert Road")]
        assert len(runs) == 2 and all(r["p5"] >= 4.5 for r in runs), runs
        scene.set_material("normal")
        scene.render(3)
        assert numpy.array_equal(numpy.asarray(scene.read(), numpy.int16), normal)
    finally:
        out.unlink(missing_ok=True)
        line.deleteLater()
    # Card content origin: card (170, 100) + padding 8; the line at (10, 40). The empty stretch
    # between the runs carries the row's tone; just below the row it does not.
    left, top = 170 + 8 + 10, 100 + 8 + 40
    gap = glass[top + 12, left + 100].sum()
    below = glass[top + 24 + 6, left + 100].sum()
    assert gap < below - 30


def _qml_blocks(text: str, head: str):
    for match in re.finditer(re.escape(head), text):
        index, depth = match.end(), 1
        while depth:
            depth += {"{": 1, "}": -1}.get(text[index], 0)
            index += 1
        yield text[match.start():index]


def test_every_list_family_draws_rows_not_per_run_chips() -> None:
    expected = {
        "RedditPresentation.qml": 1, "GmailPresentation.qml": 1, "FeedPresentation.qml": 2,
        "SystemStatsPresentation.qml": 1, "FriendPulsePresentation.qml": 2,
        "GamesYouFollowPresentation.qml": 1, "AbandonmentIssuesPresentation.qml": 1,
        "AchievementCapsule.qml": 3, "WeatherPresentation.qml": 3, "MediaPresentation.qml": 1,
    }
    for name, rows in expected.items():
        text = (QML / name).read_text(encoding="utf-8")
        assert text.count("LegibilityRow {") == rows, name
        assert "surfacePlateEnabled: false" in text, name
    metadata = (QML / "MediaMetadataColumn.qml").read_text(encoding="utf-8")
    assert all("surfacePlateEnabled: false" in block for block in _qml_blocks(metadata, "ShadowedText {"))
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
