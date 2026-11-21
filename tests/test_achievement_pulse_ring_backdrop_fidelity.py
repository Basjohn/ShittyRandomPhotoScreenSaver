"""Achievement Pulse ring: every ring pixel's colour comes from the backdrop beneath the ring's own band.

The ring is the card surface under an annulus coverage mask (surface_material.frag, borderSurfaceEnabled 2).
A card's edge zone and refraction are sized for a card; on a thin band they pulled colour from the hole inside
the ring and from outside it (a dark-red inner rim on Glass over a navy backdrop). The wallpaper here is navy
exactly under the band and vivid red directly inside and outside it, so any leak shows as red.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtQuick import QQuickItem

from rendering.quick.widgets.surface_material import SURFACE_MATERIALS

pytestmark = pytest.mark.usefixtures("qt_app")

_MATERIALS = [m for m in SURFACE_MATERIALS if m != "normal"]
_MATERIAL_SURFACE_QML = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml" / "MaterialSurface.qml"
_NAVY = (30, 42, 78, 255)
_RED = (255, 48, 16, 255)
_SIZE = (1000, 620)
_IDENTITIES = itertools.count()


@pytest.fixture()
def material_scene(qt_app):
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("hidden GL scene needs the Windows QPA")
    scene = MaterialScene(*_SIZE)
    yield scene
    scene.close()


def _wallpaper(cx: float, cy: float, outer: float, band: float, guard: float):
    """Navy under the band (and a guard beyond its edges), vivid red in the hole and outside."""
    from rendering.quick.image_state import PresentationImage

    width, height = _SIZE
    yy, xx = numpy.mgrid[0:height, 0:width]
    radius = numpy.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
    image = numpy.empty((height, width, 4), numpy.uint8)
    image[:] = _RED
    image[(radius <= outer + guard) & (radius >= outer - band - guard)] = _NAVY
    identity = f"ring-moat-{next(_IDENTITIES)}"
    return PresentationImage(identity, identity, (float(width), float(height)), 1.0, (width, height),
                             width * 4, image.tobytes())


def _ring_frame(scene, tmp_path, material: str, wallpaper_args, origin=(60, 60)):
    from PySide6.QtGui import QColor
    from rendering.quick.widgets.achievement_pulse import (
        AchievementPulsePresentationModel, AchievementPulsePresentationStyle, RetainedAchievementPulsePresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.surface_material import surface_text_color
    from tools import qtquick_achievement_pulse_smoke as smoke
    from widgets.steam_card_models import build_mock_steam_view_model

    art_path = tmp_path / "art.png"
    art = smoke._synthetic_art(art_path, accent=QColor(53, 126, 167), portrait=True)
    config = smoke._config(progress_ring_surface_material=material, progress_pulse=True)
    style = AchievementPulsePresentationStyle.project(config, smoke._shadows("SE"))
    model = AchievementPulsePresentationModel(config, style, parent=scene.scene.owner)
    presentation = RetainedAchievementPulsePresentation(
        host=scene.host, model=model, geometry=OverlayWidgetGeometry(origin[0], origin[1], 600, 334), fade_opacity=1.0)
    presentation.activate()
    model.on_achievement_presentation(smoke._prepared(
        build_mock_steam_view_model("achievement_pulse"), artwork=art, artwork_path=art_path,
        latest_artwork=art, latest_path=art_path), animate=False)
    scene.presentations = [presentation]
    item = presentation.item
    face = item.findChild(QQuickItem, "achievementProgressCircleFace")
    rect = face.mapRectToScene(QRectF(0, 0, face.width(), face.height()))
    cx, cy = rect.center().x(), rect.center().y()
    outer, band = rect.width() / 2.0, float(face.property("ringWidth")) * face.scale()
    scene.set_wallpaper(_wallpaper(cx, cy, outer, band, 0.0 if wallpaper_args is None else wallpaper_args))
    scene.ensure_owner()
    scene.owner.set_materials(frozenset({material}))
    item.setProperty("cardSurfaceMaterial", "normal")
    item.setProperty("cardSurfaceTextColor", surface_text_color())
    item.setProperty("cardSurfaceOpacityAdjust", 0.0)
    outline = item.findChild(QQuickItem, "achievementProgressRingOutline")
    outline.setVisible(False)  # the flat outline would cover the band's outer edge
    tint = item.property("cardBackgroundColor")
    scene.render(10)
    frame = numpy.asarray(scene.read(), numpy.int16)
    presentation.retire()
    scene.render(3)
    scene.presentations = []
    return frame, (cx, cy, outer, band), tint


def _card_surface_frame(scene, material: str, box, tint):
    """The same material on a plain card surface (the product MaterialSurface, no edge in the box)."""
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent
    from rendering.quick.widgets.surface_material import surface_text_color

    text = surface_text_color()
    component = QQmlComponent(scene.scene.qml_context.engine(), QUrl.fromLocalFile(str(_MATERIAL_SURFACE_QML)))
    surface = component.createWithInitialProperties({
        "backdrop": scene.owner.item, "material": material, "cornerRadius": 0.0, "contentInset": 0.0,
        "borderWidth": 0.0, "normalColor": tint, "tintColor": tint, "textColor": text, "legibilityInk": text})
    assert surface is not None, [e.toString() for e in component.errors()]
    surface.setParentItem(scene.scene.root)
    x0, y0, x1, y1 = box
    surface.setX(x0)
    surface.setY(y0)
    surface.setWidth(x1 - x0)
    surface.setHeight(y1 - y0)
    surface.setZ(1000)
    scene.render(8)
    frame = numpy.asarray(scene.read(), numpy.int16)
    surface.setParentItem(None)
    surface.deleteLater()
    return frame


def _ring_vs_card_surface(scene, tmp_path, material: str, reference_material: str | None = None):
    """(max chroma difference, min brightness difference, max brightness difference) of the ring's pixels against
    the plain card surface of ``reference_material`` (default: its own) over the same backdrop region."""
    frame, (cx, cy, outer, band), tint = _ring_frame(scene, tmp_path, material, 0.0)
    box = (int(cx - outer - 4), int(cy - outer - 4), int(cx + outer + 4), int(cy + outer + 4))
    reference = _card_surface_frame(scene, reference_material or material, box, tint)
    height, width, _ = frame.shape
    yy, xx = numpy.mgrid[0:height, 0:width]
    radius = numpy.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
    # Whole-coverage pixels only: the 2 px at each edge blend with the card's flat fill and the outline's place.
    ring = (radius >= outer - band + 2.0) & (radius <= outer - 2.0)
    assert int(ring.sum()) > 200
    a, b = frame[ring][:, :3].astype(float), reference[ring][:, :3].astype(float)
    chroma = numpy.maximum(numpy.abs((a[:, 0] - a[:, 2]) - (b[:, 0] - b[:, 2])),
                           numpy.abs((a[:, 1] - a[:, 2]) - (b[:, 1] - b[:, 2])))
    brightness = a.mean(axis=1) - b.mean(axis=1)
    return float(chroma.max()), float(brightness.min()), float(brightness.max())


@pytest.mark.parametrize("material", _MATERIALS)
def test_ring_pixels_match_the_plain_card_surface_of_their_material(material_scene, tmp_path, material) -> None:
    """Hue and brightness of every ring pixel equal the same material's plain card surface over the same
    backdrop; the only allowed excess is the card's own edge highlight (added light, never a hue)."""
    chroma, darker, lighter = _ring_vs_card_surface(material_scene, tmp_path, material)
    assert chroma <= 10.0, (material, chroma)
    assert darker >= -4.0 and lighter <= 40.0, (material, darker, lighter)


def test_the_comparison_notices_a_ring_that_is_not_its_material(material_scene, tmp_path) -> None:
    """Control: a Glass ring set against Mica's card surface must be out of tolerance on this wallpaper."""
    chroma, darker, lighter = _ring_vs_card_surface(material_scene, tmp_path, "glass", "mica")
    assert chroma > 10.0 or darker < -4.0 or lighter > 40.0, (chroma, darker, lighter)
