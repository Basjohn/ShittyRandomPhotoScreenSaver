"""Card surface acceptance pass, 7 Nov (Docs/Architecture/Card_Surface_Materials.md 3.3, 3.4).

What these bars protect (operator, 7 Nov):
- on a material each card's darker legibility panel runs from above the header to below the
  last element (Media: header to below the seek track), not a box hugging the track text;
- the Visualizer card uses the theme's surface material like every other card (its authored
  Fill tints it); with Normal it adds no item and its pixels are unchanged;
- Media's volume track and mute button take the card's material; Normal adds no item;
- the scene controller counts the Visualizer's material as backdrop demand only while its
  presentation root exists.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def material_scene(qt_app):
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("hidden GL scene needs the Windows QPA")
    scene = MaterialScene(900, 520)
    yield scene
    scene.close()


def _flat(width, height, rgba, identity):
    from rendering.quick.image_state import PresentationImage

    return PresentationImage(identity, identity, (float(width), float(height)), 1.0, (width, height),
                             width * 4, bytes(rgba) * (width * height))


def _rect(item):
    from PySide6.QtCore import QRectF

    return item.mapRectToScene(QRectF(0.0, 0.0, item.width(), item.height()))


def _find(root, name):
    pending = [root]
    while pending:
        node = pending.pop()
        if node.objectName() == name and node.isVisible():
            return node
        pending.extend(node.childItems())
    return None


def _tone(frame, x, y):
    """Mean brightness of a 3x3 patch (the material grain is per pixel)."""
    return float(frame[int(y) - 1:int(y) + 2, int(x) - 1:int(x) + 2].sum(axis=2).mean())


def _media(scene, tmp_path):
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    art = foundry._gradient_art(tmp_path / "art.png", (240, 240), ("#27336e", "#e7678a"), 1)
    media = foundry._preview_media(scene.scene, art)
    item = media.item
    media.set_geometry(OverlayWidgetGeometry(120.0, 80.0, item.width(), item.height()))
    scene.presentations = [media]
    # Let the artwork crossfade and fade-ins finish (wall-time animations).
    from tools.surface_material_capture import settle_animations

    settle_animations(scene, 1.6)
    return media


def test_media_panel_runs_from_above_the_header_to_below_the_seek_track(material_scene, tmp_path) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat(900, 520, (205, 205, 205, 255), "grey"))
    media = _media(scene, tmp_path)
    scene.set_material("glass")
    scene.render(6)
    frame = numpy.asarray(scene.read(), numpy.float64)
    root = scene.scene.root
    header = _rect(_find(root, "mediaHeaderFrame"))
    metadata = _rect(_find(root, "mediaTrackMetadata"))
    track = _rect(_find(root, "mediaProgressTrack"))
    # One column clear of glyphs (the right end of the metadata column, the fixture's title is
    # short) through the gap above the header, the track text, and the gap below the seek track.
    x = metadata.right() - 6.0
    above_header = _tone(frame, x, header.top() - 3.0)
    in_text_block = _tone(frame, x, metadata.top() + 3.0)
    below_track = _tone(frame, x, track.bottom() + 4.0)
    # One even panel: the text block is not darker than the gaps above and below it.
    assert abs(in_text_block - above_header) <= 6, (above_header, in_text_block, below_track)
    assert abs(in_text_block - below_track) <= 6, (above_header, in_text_block, below_track)
    # ...and it is the darker panel, not the bare material: the rim just inside the border is lighter.
    card = _rect(media.item)
    rim = _tone(frame, x, card.top() + 1.5 + float(media.item.property("cardBorderWidth") or 0.0))
    assert rim - above_header > 20


def test_media_volume_and_mute_children_take_the_card_material(material_scene, tmp_path) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat(900, 520, (205, 205, 205, 255), "grey"))
    _media(scene, tmp_path)
    root = scene.scene.root
    track = _find(root, "mediaAppVolumeTrackMaterial")
    mute = _find(root, "mediaSystemMuteMaterial")
    assert track is not None and mute is not None
    assert track.property("item") is None and mute.property("item") is None   # Normal: no item
    normal = numpy.asarray(scene.read(), numpy.int16)
    scene.set_material("acrylic")
    scene.render(6)
    for loader in (track, mute):
        surface = loader.property("item")
        assert surface is not None and surface.objectName() == "materialSurface"
        assert surface.property("material") == "acrylic"
    scene.set_material("normal")
    scene.render(4)
    assert track.property("item") is None and mute.property("item") is None
    # Normal pixels return exactly, except the seek track (the fixture is playing: its
    # position advances with wall time between the two reads).
    changed = numpy.argwhere(numpy.abs(numpy.asarray(scene.read(), numpy.int16) - normal).max(axis=2) > 0)
    seek = _rect(_find(root, "mediaProgressTrack")).adjusted(-12.0, -12.0, 12.0, 12.0)
    outside = [(y, x) for y, x in changed if not seek.contains(float(x), float(y))]
    assert not outside, outside[:10]


def test_visualizer_card_binds_the_material_and_normal_adds_nothing(material_scene) -> None:
    import numpy
    from PySide6.QtGui import QColor
    from PySide6.QtQuick import QQuickItem

    scene = material_scene
    scene.set_wallpaper(_flat(900, 520, (205, 205, 205, 255), "grey"))
    loader = scene.scene.find("visualizerPresentationLoader")
    loader.setProperty("active", True)
    root = loader.property("item")
    assert isinstance(root, QQuickItem)
    loader.setX(100.0); loader.setY(80.0); loader.setWidth(500.0); loader.setHeight(240.0)
    root.setWidth(500.0); root.setHeight(240.0)
    root.setProperty("cardShellEnabled", True)
    root.setProperty("cardBackgroundColor", QColor(35, 35, 35, 76))
    root.setProperty("presentationActive", True)
    scene.render(4)
    surface = root.findChild(QQuickItem, "visualizerCardSurfaceMaterial")
    background = root.findChild(QQuickItem, "visualizerCardBackground")
    assert surface is not None and surface.property("item") is None and background.isVisible()
    normal = numpy.asarray(scene.read(), numpy.int16)

    scene.ensure_owner()
    scene.owner.set_materials(frozenset({"glass"}))
    root.setProperty("cardSurfaceMaterial", "glass")
    root.setProperty("cardSurfaceBackdrop", scene.owner.item)
    scene.render(6)
    material = surface.property("item")
    assert material is not None and material.objectName() == "materialSurface"
    assert material.property("material") == "glass"
    # The authored Fill tints the material.
    assert material.property("tintColor") == QColor(35, 35, 35, 76)
    assert background.isVisible() is False
    glass = numpy.asarray(scene.read(), numpy.int16)
    assert not numpy.array_equal(glass[120:300, 140:560], normal[120:300, 140:560])

    root.setProperty("cardSurfaceMaterial", "normal")
    root.setProperty("cardSurfaceBackdrop", None)
    scene.drop_owner()
    scene.render(4)
    assert surface.property("item") is None and background.isVisible()
    assert numpy.array_equal(numpy.asarray(scene.read(), numpy.int16), normal)
    loader.setProperty("active", False)


def test_visualizer_material_is_backdrop_demand_only_while_its_root_exists() -> None:
    from rendering.quick.scene_controller import QuickSceneController

    controller = SimpleNamespace(_ordinary_widget_host=None, _context_menu_surface_material="normal",
                                 _visualizer_surface_material="glass", _visualizer_root=None)
    assert QuickSceneController._surface_materials_in_use(controller) == frozenset()
    controller._visualizer_root = object()
    assert QuickSceneController._surface_materials_in_use(controller) == frozenset({"glass"})
    controller._visualizer_surface_material = "normal"
    assert QuickSceneController._surface_materials_in_use(controller) == frozenset()
