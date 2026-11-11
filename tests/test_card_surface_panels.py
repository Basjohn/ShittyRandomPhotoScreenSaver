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
    # ...up to the real border: no lighter rim of bare material just inside it (12 Nov, M2); at
    # most Glass's own edge highlight, which fades within a few pixels of the border.
    card = _rect(media.item)
    rim = _tone(frame, x, card.top() + 1.5 + float(media.item.property("cardBorderWidth") or 0.0))
    assert -6 <= rim - above_header <= 12, (rim, above_header)


def test_media_volume_and_mute_children_take_the_card_material(material_scene, tmp_path) -> None:
    import numpy

    scene = material_scene
    scene.set_wallpaper(_flat(900, 520, (205, 205, 205, 255), "grey"))
    _media(scene, tmp_path)
    root = scene.scene.root
    track = _find(root, "mediaAppVolumeTrackMaterial")
    level = _find(root, "mediaAppVolumeFillMaterial")       # the volume's adjustable part (operator, 8 Nov)
    mute = _find(root, "mediaSystemMuteMaterial")
    controls = _find(root, "mediaControlsRowMaterial")
    loaders = (track, level, mute, controls)
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
    # The level inside it is material too, tinted by its own fill colour, and reads above the track.
    filled = level.property("item")
    assert filled.property("glassLegibility").z() == 0.0
    assert filled.property("tintColor").alphaF() > volume.property("tintColor").alphaF()
    assert _find(root, "mediaAppVolumeFill").property("color").alpha() == 0     # it drops its flat colour
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


def test_mute_button_has_no_inner_border_on_a_material(qt_app, tmp_path) -> None:
    import numpy
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("hidden GL scene needs the Windows QPA")
    k = 3.0                                     # device pixels per logical px: the rim is ~2.5 px
    scene = MaterialScene(900, 520, dpr=k)
    try:
        scene.set_wallpaper(_flat(900, 520, (205, 205, 205, 255), "grey"))
        _media(scene, tmp_path)
        scene.set_material("glass")
        scene.render(6)
        frame = numpy.asarray(scene.read(), numpy.float64)
        button = _find(scene.scene.root, "mediaSystemMuteButton")
        icon = _find(scene.scene.root, "mediaSystemMuteIcon")
        rect, glyph = _rect(button), _rect(icon)
        material = _find(scene.scene.root, "mediaSystemMuteMaterial")
        assert material is not None and material.property("item") is not None   # on the material
        y = int(rect.center().y() * k)
        # Brightness across the face from past the outline's antialiased edge (2.5 px) to the
        # icon, averaged over 5 rows: one even face, no lighter inner rim.
        profile = frame[y - 2:y + 3].sum(axis=2).mean(axis=0)
        start, stop = int((rect.left() + 2.5) * k), int(glyph.left() * k) - 2
        face = profile[start:stop]
        assert stop - start >= 4 and face.max() - face.min() <= 24,             profile[int(rect.left() * k):stop].round()
    finally:
        scene.close()


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


def _busy(width, height):
    """A busy, colourful backdrop: seeded 40 px blocks of random colour (what real wallpapers do
    to the blurred backdrop under a card)."""
    import numpy
    from rendering.quick.image_state import PresentationImage

    rng = numpy.random.default_rng(670483)
    blocks = rng.integers(0, 256, size=(height // 40 + 1, width // 40 + 1, 3), dtype=numpy.uint8)
    rgb = numpy.repeat(numpy.repeat(blocks, 40, axis=0), 40, axis=1)[:height, :width]
    rgba = numpy.concatenate([rgb, numpy.full((height, width, 1), 255, numpy.uint8)], axis=2)
    return PresentationImage("busy", "busy", (float(width), float(height)), 1.0, (width, height),
                             width * 4, numpy.ascontiguousarray(rgba).tobytes())


def _faint_small_runs(scene, card_item):
    """WCAG contrast (p5 over the glyph pixels) of every small run drawn below 80 % of its colour's
    opacity, as drawn: the run's colour composited at its effective opacity over the pixels the frame
    has there with every glyph hidden."""
    import numpy
    from PySide6.QtCore import QRectF
    from tools.surface_material_capture import _relative_luminance, _text_runs

    scene.render(3)
    full = numpy.asarray(scene.read(), numpy.float64)
    runs = _text_runs(scene)
    saved = []
    for _item, main, shadow, _rect, _size in runs:
        saved.append((main.opacity(), shadow.opacity() if shadow is not None else None))
        main.setOpacity(0.0)
        if shadow is not None:
            shadow.setOpacity(0.0)
    scene.render(3)
    bare = numpy.asarray(scene.read(), numpy.float64)
    for (_item, main, shadow, _rect, _size), (main_opacity, shadow_opacity) in zip(runs, saved):
        main.setOpacity(main_opacity)
        if shadow is not None:
            shadow.setOpacity(shadow_opacity)
    rows = []
    for item, _main, _shadow, rect, size in runs:
        colour = item.property("color")
        alpha = colour.alphaF()
        node = item
        while node is not None and node is not card_item:
            alpha *= node.opacity()
            node = node.parentItem()
        if size >= 18.0 or not 0.2 <= alpha < 0.8:
            continue
        l, t = max(0, int(rect.left())), max(0, int(rect.top()))
        r, b = int(rect.right()) + 1, int(rect.bottom()) + 1
        mask = numpy.abs(full[t:b, l:r] - bare[t:b, l:r]).max(axis=2) > 24
        if mask.sum() < 6:
            continue
        background = bare[t:b, l:r][mask]
        text = numpy.array([colour.red(), colour.green(), colour.blue()], numpy.float64)
        drawn = alpha * text + (1.0 - alpha) * background
        lt, lb = _relative_luminance(drawn), _relative_luminance(background)
        contrast = (numpy.maximum(lt, lb) + 0.05) / (numpy.minimum(lt, lb) + 0.05)
        rows.append((str(item.property("text"))[:24], round(alpha, 2), float(numpy.percentile(contrast, 5))))
    return rows


@pytest.mark.parametrize("family", ["gmail", "media"])
def test_card_panel_holds_faint_small_runs_at_4_5(material_scene, tmp_path, family) -> None:
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from tools.surface_material_capture import settle_animations

    scene = material_scene
    scene.set_wallpaper(_busy(900, 520))
    art = foundry._gradient_art(tmp_path / "art.png", (240, 240), ("#27336e", "#e7678a"), 1)
    presentation = (foundry._preview_gmail if family == "gmail" else foundry._preview_media)(scene.scene, art)
    item = presentation.item
    presentation.set_geometry(OverlayWidgetGeometry(60.0, 60.0, item.width(), item.height()))
    scene.presentations = [presentation]
    settle_animations(scene, 1.4)
    scene.set_material("glass")
    rows = _faint_small_runs(scene, item)
    # Gmail's dates and menu glyph, Media's playback state: drawn at 55-76 % of their colour.
    assert rows, "the fixture has faint runs"
    assert all(p5 >= 4.5 for _text, _alpha, p5 in rows), rows


def test_a_run_at_opacity_zero_loads_no_ink_plate_and_a_crossfade_keeps_one_ink(material_scene, tmp_path) -> None:
    """1B.8 M2b audit: the ink rule runs on every theme, so a refresh glyph's resting crossfade twin
    (own opacity 0) must not hold a text-local plate, and the twins solve their ink at the glyph's
    resting opacity, not at the crossfade's (no per-frame re-solve, no plate loaded mid-fade)."""
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from tools.surface_material_capture import settle_animations

    scene = material_scene
    scene.set_wallpaper(_busy(900, 520))
    art = foundry._gradient_art(tmp_path / "art.png", (240, 240), ("#27336e", "#e7678a"), 1)
    presentation = foundry._preview_gmail(scene.scene, art)
    item = presentation.item
    presentation.set_geometry(OverlayWidgetGeometry(60.0, 60.0, item.width(), item.height()))
    scene.presentations = [presentation]
    settle_animations(scene, 1.4)
    scene.set_material("glass")
    scene.render(3)
    runs, pending = [], [item]
    while pending:
        node = pending.pop()
        pending.extend(node.childItems())
        if node.property("inkNeedsPlate") is not None:
            runs.append(node)
    assert runs, "the fixture has shadowed runs"
    resting = [run for run in runs if run.opacity() == 0.0 and run.isVisible()]
    assert resting, "the refresh glyph keeps a resting crossfade twin"
    for run in runs:
        plate = _find(run, "shadowedTextInkPlate")
        if run.opacity() == 0.0:
            assert plate is None or not plate.property("active"), run.property("text")
    glyphs = [run for run in runs if run.property("text") in ("↻", "◌")]
    assert len(glyphs) >= 2
    assert len({run.property("inkColor").name() for run in glyphs}) == 1
    assert all(run.property("inkOpacity") > 0.0 for run in glyphs)


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
