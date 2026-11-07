"""Card surface acceptance pass, 7 Nov (Docs/Architecture/Card_Surface_Materials.md 3.3, 3.4).

What these bars protect (operator, 7 Nov):
- on a material each card's darker legibility panel runs from above the header to below the
  last element (Media: header to below the seek track), not a box hugging the track text;
- the Visualizer card uses the theme's surface material like every other card (its authored
  Fill tints it); with Normal it adds no item and its pixels are unchanged;
- Media's transport bar, mute button and volume track take the card's material with no inner
  rim (the control's outline is its only border); the volume track lets more backdrop through;
  Normal adds no item;
- the transport glyphs are vector glyphs: centred in their segments, one ink height, a real
  stroke weight (7 Nov: "arrows are misaligned and thin, same for pause");
- the card panel's floor carries faint runs (60-76 % of the text colour) to 4.5:1;
- Achievement Pulse's capsules never run into its artwork or metric;
- the scene controller counts the Visualizer's material as backdrop demand only while its
  presentation root exists.
"""
from __future__ import annotations

from pathlib import Path
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
    controls = _find(root, "mediaControlsRowMaterial")
    loaders = (track, mute, controls)
    assert all(loader is not None for loader in loaders)
    assert all(loader.property("item") is None for loader in loaders)   # Normal: no item
    normal = numpy.asarray(scene.read(), numpy.int16)
    scene.set_material("acrylic")
    scene.render(6)
    for loader in loaders:
        surface = loader.property("item")
        assert surface is not None and surface.objectName() == "materialSurface"
        assert surface.property("material") == "acrylic"
        # The control's own outline is its only border: no inner rim (negative border width).
        assert surface.property("borderWidth") < 0.0
    # The volume track lets more backdrop through and carries no darker panel (no text on it).
    volume = track.property("item")
    fill = volume.property("normalColor")
    assert volume.property("tintColor").alphaF() < fill.alphaF()
    assert volume.property("glassLegibility").z() == 0.0
    scene.set_material("normal")
    scene.render(4)
    assert all(loader.property("item") is None for loader in loaders)
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


def test_mute_button_has_no_inner_border_on_a_material(material_scene, tmp_path) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat(900, 520, (205, 205, 205, 255), "grey"))
    _media(scene, tmp_path)
    scene.set_material("glass")
    scene.render(6)
    frame = numpy.asarray(scene.read(), numpy.float64)
    button = _find(scene.scene.root, "mediaSystemMuteButton")
    icon = _find(scene.scene.root, "mediaSystemMuteIcon")
    rect, glyph = _rect(button), _rect(icon)
    y = rect.center().y()
    # Just inside the outline vs the face between the outline and the icon: one face, no rim.
    rim = _tone(frame, rect.left() + 2.0 + 1.5, y)
    face = _tone(frame, (rect.left() + glyph.left()) / 2.0 + 1.0, y)
    assert abs(rim - face) <= 8, (rim, face)


def _ink_box(frame, rect):
    """The bright glyph pixels inside a segment (the bar's own fill is the dark majority)."""
    import numpy

    left, top = int(round(rect.left())) + 2, int(round(rect.top())) + 3
    right, bottom = int(round(rect.right())) - 2, int(round(rect.bottom())) - 3
    region = frame[top:bottom, left:right].sum(axis=2)
    threshold = (numpy.median(region) + region.max()) / 2.0
    ys, xs = numpy.nonzero(region > threshold)
    assert len(xs) > 10, "no glyph ink"
    return left, top, region > threshold, (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)


def test_transport_glyphs_are_centred_equal_and_stroked(material_scene, tmp_path) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat(900, 520, (30, 30, 34, 255), "dark"))
    _media(scene, tmp_path)
    frame = numpy.asarray(scene.read(), numpy.float64)
    root = scene.scene.root
    heights = []
    for name in ("mediaPreviousButton", "mediaPlayPauseButton", "mediaNextButton"):
        segment = _rect(_find(root, name))
        left, top, mask, (x0, y0, x1, y1) = _ink_box(frame, segment)
        centre_x, centre_y = left + (x0 + x1) / 2.0, top + (y0 + y1) / 2.0
        assert abs(centre_x - segment.center().x()) <= 1.0, (name, centre_x, segment.center().x())
        assert abs(centre_y - segment.center().y()) <= 1.0, (name, centre_y, segment.center().y())
        heights.append(y1 - y0)
        # Stroke weight: the thinnest ink run across the glyph's middle column/row.
        if name == "mediaPlayPauseButton":
            row = mask[(y0 + y1) // 2, x0:x1]
            runs = numpy.diff(numpy.flatnonzero(numpy.diff(numpy.r_[0, row.astype(int), 0])))[::2]
        else:
            column = mask[y0:y1, (x0 + x1) // 2]
            runs = numpy.diff(numpy.flatnonzero(numpy.diff(numpy.r_[0, column.astype(int), 0])))[::2]
        assert len(runs) and runs.min() >= 2, (name, runs)
    # One ink height for previous, pause and next.
    assert max(heights) - min(heights) <= 1, heights


def test_card_panel_holds_faint_small_runs_at_4_5(material_scene) -> None:
    import numpy
    from PySide6.QtCore import QRectF, QUrl
    from PySide6.QtGui import QColor
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickItem
    from rendering.quick.image_state import PresentationImage
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry
    from tools.surface_material_capture import _relative_luminance

    scene = material_scene
    width, height = 900, 520
    stripes = bytearray()
    for _y in range(height):
        for x in range(width):
            stripes += bytes((250, 240, 150, 255)) if (x // 6) % 2 else bytes((235, 200, 245, 255))
    scene.set_wallpaper(PresentationImage("stripes", "stripes", (900.0, 520.0), 1.0, (width, height),
                                          width * 4, bytes(stripes)))
    card = scene.host.create_widget(object_name="card", model_identity="clock",
                                    geometry=OverlayWidgetGeometry(170, 100, 300, 160),
                                    card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 77),
                                                                shadow_enabled=False))
    scene.presentations = []
    component = QQmlComponent(scene.scene.qml_context.engine())
    # A faint run: the card text colour at 62 % (Media's playback state, Gmail's dates).
    component.setData(b'import QtQuick\nShadowedText { x: 30; y: 40; width: 220; height: 20; text: "PLAYING 27/08";'
                      b' color: "white"; opacity: 0.62; font.pixelSize: 12; font.bold: true; shadowEnabled: false }',
                      QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"
                                             / "_test_faint.qml")))
    run = component.create(scene.scene.qml_context)
    assert run is not None, component.errorString()
    content = card.item.findChild(QQuickItem, "overlayCardContent")
    run.setParentItem(content)
    run.setParent(content)
    scene.set_material("glass")
    scene.render(6)
    full = numpy.asarray(scene.read(), numpy.float64)
    main = run.findChild(QQuickItem, "shadowedTextMain")
    main.setOpacity(0.0)
    scene.render(3)
    bare = numpy.asarray(scene.read(), numpy.float64)
    rect = main.mapRectToScene(QRectF(0.0, 0.0, main.width(), main.height()))
    l, t, r, b = int(rect.left()), int(rect.top()), int(rect.right()) + 1, int(rect.bottom()) + 1
    mask = numpy.abs(full[t:b, l:r] - bare[t:b, l:r]).max(axis=2) > 24
    assert mask.sum() > 20
    background = bare[t:b, l:r][mask]
    text = 0.62 * 255.0 + 0.38 * background          # what the faint run actually draws
    lt, lb = _relative_luminance(text), _relative_luminance(background)
    contrast = (numpy.maximum(lt, lb) + 0.05) / (numpy.minimum(lt, lb) + 0.05)
    assert float(numpy.percentile(contrast, 5)) >= 4.5, float(numpy.percentile(contrast, 5))
    run.deleteLater()


def test_achievement_capsules_never_run_into_the_artwork_or_metric(material_scene, tmp_path) -> None:
    from tools import card_surface_capture as capture

    scene = material_scene
    scene.set_wallpaper(_flat(900, 520, (30, 30, 34, 255), "dark"))
    art = tmp_path / "art.png"
    # The shared Steam fixture carries more capsule fields than the default config enables.
    presentation = capture._achievement(scene.scene, art)
    scene.presentations = [presentation]
    from tools.surface_material_capture import settle_animations

    settle_animations(scene, 1.0)
    root = scene.scene.root
    artwork = _rect(_find(root, "achievementArtworkFrame"))
    metric = _rect(_find(root, "achievementMetric"))
    group = _find(root, "achievementFieldGroup")
    fields = [child for child in group.childItems() if child.objectName().startswith("achievementField_")]
    assert fields
    for field in fields:
        box = _rect(field)
        for other, label in ((artwork, "artwork"), (metric, "metric")):
            assert not box.intersects(other), (field.objectName(), label, box, other)
