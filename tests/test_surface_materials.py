"""Card surface materials (Docs/Architecture/Card_Surface_Materials.md).

What these bars protect:
- the compositor: the wallpaper/transition item stays directly under the scene root
  at z 0 with no layer, capture or redirect; the backdrop only reads what was drawn;
- dormancy: with every surface Normal nothing material-related exists;
- ownership: one owner per display scene, created on the first non-Normal surface,
  parked (GL freed, never traversed) when the last one goes Normal;
- the GL pipeline restores every state it touches and writes an opaque backdrop;
- pixels: Normal stays exactly Normal, a material shows the blurred wallpaper beneath
  the card, follows a running transition, and parking returns Normal pixels exactly.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


# --------------------------------------------------------------------------- resolution


def test_baseline_is_normal_and_a_widget_value_beats_it() -> None:
    from core.settings.default_contract import require_canonical_default
    from rendering.quick.widgets.surface_material import (
        SURFACE_MATERIALS, resolve_global_surface_material, resolve_surface_material,
    )

    from rendering.quick.widgets.surface_material import normalize_surface_material

    assert normalize_surface_material(require_canonical_default("widgets.global.surface_material")) is not None
    assert "normal" in SURFACE_MATERIALS
    assert resolve_global_surface_material({}) == "normal"
    widgets = {"global": {"surface_material": "Acrylic"}, "clock": {"surface_material": "inherit"},
               "weather": {"surface_material": "glass"}, "media": {"surface_material": "nonsense"}}
    assert resolve_surface_material(widgets, "clock") == "acrylic"
    assert resolve_surface_material(widgets, "weather") == "glass"
    assert resolve_surface_material(widgets, "media") == "acrylic"
    assert resolve_global_surface_material({"global": {"surface_material": "bogus"}}) == "normal"


def test_every_ordinary_family_style_passes_through_the_material_projection() -> None:
    binder = (ROOT / "rendering" / "quick" / "widgets" / "family_binder.py").read_text(encoding="utf-8")
    projections = len(re.findall(r"style = \w+\.project\(config, shadow_values", binder))
    assert projections >= 10
    assert binder.count("style = with_surface_material(style, widgets_config, widget_id)") == projections


# --------------------------------------------------------------------------- compositor contract


def test_background_stays_directly_composited_and_the_backdrop_sits_between_dimming_and_cards() -> None:
    scene = (QML / "DisplayScene.qml").read_text(encoding="utf-8")
    controller = (ROOT / "rendering" / "quick" / "scene_controller.py").read_text(encoding="utf-8")
    owner = (ROOT / "rendering" / "quick" / "surface_backdrop_owner.py").read_text(encoding="utf-8")
    code = re.sub(r"//.*?$", "", scene, flags=re.MULTILINE)
    for forbidden in ("ShaderEffectSource", "layer.enabled", "layer.effect"):
        assert forbidden not in code
    assert "BackgroundRenderItem(\n            root," in controller
    assert "self._background_item.setZ(0.0)" in controller
    from rendering.quick.surface_backdrop_owner import BACKDROP_Z

    dimming_z = float(re.search(r'id: backgroundDimming[\s\S]*?z: ([\d.]+)', scene).group(1))
    cards_z = float(re.search(r'id: pixelShiftLayer[\s\S]*?z: ([\d.]+)', scene).group(1))
    guide_z = float(re.search(r'id: customLayoutGuideUnderlay[\s\S]*?z: ([\d.]+)', scene).group(1))
    assert dimming_z < BACKDROP_Z < min(cards_z, guide_z)
    # No timer, frame animation or frame request of its own.
    for source in (owner, (ROOT / "rendering" / "quick" / "render" / "surface_backdrop.py").read_text(encoding="utf-8")):
        for forbidden in ("QTimer", "FrameAnimation", "singleShot", "requestUpdate", "os.environ"):
            assert forbidden not in source


def test_material_shader_is_one_quad_per_surface_with_no_capture_of_its_own() -> None:
    surface = (QML / "MaterialSurface.qml").read_text(encoding="utf-8")
    assert "ShaderEffectSource" not in surface and "layer." not in surface and "MultiEffect" not in surface
    assert 'fragmentShader: "shaders/surface_material.frag.qsb"' in surface
    for name in ("surface_material.vert.qsb", "surface_material.frag.qsb"):
        assert (QML / "shaders" / name).is_file()


# --------------------------------------------------------------------------- GL pipeline


def test_backdrop_pipeline_restores_state_and_writes_an_opaque_two_level_backdrop(qt_app) -> None:
    from OpenGL import GL as gl
    import numpy
    from rendering.quick import gl_query
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.render.surface_backdrop import BackdropPipeline, pyramid_sizes

    target = OffscreenRenderTarget(320, 180, label="surface-backdrop-test")
    pipeline = BackdropPipeline()
    try:
        with target.current():
            target.bind(clear=(0.8, 0.2, 0.1, 1.0))
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(3, 4, 50, 60)
            gl.glViewport(7, 9, 111, 77)
            gl.glEnablei(gl.GL_BLEND, 0)
            before = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_ints(gl.GL_VIEWPORT, 4),
                      gl_query.is_enabled(gl.GL_SCISSOR_TEST), bool(gl.glIsEnabledi(gl.GL_BLEND, 0)),
                      gl_query.get_int(gl.GL_CURRENT_PROGRAM), gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING))
            assert pipeline.refresh(target.fbo, 320, 180) is True
            after = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_ints(gl.GL_VIEWPORT, 4),
                     gl_query.is_enabled(gl.GL_SCISSOR_TEST), bool(gl.glIsEnabledi(gl.GL_BLEND, 0)),
                     gl_query.get_int(gl.GL_CURRENT_PROGRAM), gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING))
            assert after == before
            gl.glBindTexture(gl.GL_TEXTURE_2D, pipeline.output_texture)
            for level, (w, h) in enumerate(pyramid_sizes(320, 180)[1:3]):
                data = gl.glGetTexImage(gl.GL_TEXTURE_2D, level, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
                pixels = numpy.frombuffer(bytes(data), numpy.uint8).reshape(h, w, 4)
                assert (pixels[..., 3] == 255).all()
                # The scissor box must not have limited the blit: the whole target is copied.
                assert abs(int(pixels[h // 2, w // 2, 0]) - 204) <= 2
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            pipeline.release()
            assert pipeline.output_texture == 0
    finally:
        target.close()


# --------------------------------------------------------------------------- ownership


def _controller(qt_app):
    from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from rendering.quick.window import QuickDisplayWindow

    window = QuickDisplayWindow(screen_index=0, runtime_generation=3, screen=qt_app.primaryScreen(),
                                policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    factory = QuickSceneFactory()
    return window, factory, QuickSceneController(window=window, factory=factory)


def _backdrops(root):
    from PySide6.QtQuick import QQuickItem

    return [child for child in root.findChildren(QQuickItem) if child.objectName() == "surfaceBackdropSource"]


def test_all_normal_creates_nothing_and_the_first_material_creates_one_owner(qt_app) -> None:
    from PySide6.QtGui import QColor
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    window, factory, controller = _controller(qt_app)
    try:
        root = controller.scene_root
        host = controller.ordinary_widget_host
        normal = host.create_widget(object_name="normalCard", model_identity="clock",
                                    geometry=OverlayWidgetGeometry(10, 10, 200, 100),
                                    card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 80)))
        assert controller.apply_context_menu_surface_material("normal") is True
        qt_app.processEvents()
        assert controller.surface_backdrop_owner is None
        assert _backdrops(root) == []
        assert normal.item.property("cardSurfaceBackdrop") is None
        loader = normal.item.findChild(type(root), "overlayCardSurfaceMaterial")
        assert loader is not None and loader.property("active") is False

        glass = host.create_widget(object_name="glassCard", model_identity="weather",
                                   geometry=OverlayWidgetGeometry(300, 10, 200, 100),
                                   card_style=OverlayCardStyle(surface_material="glass"))
        owner = controller.surface_backdrop_owner
        assert owner is not None and not owner.parked
        assert _backdrops(root) == [owner.item]
        for widget in (normal, glass):
            assert widget.item.property("cardSurfaceBackdrop") is owner.item
        material_loader = glass.item.findChild(type(root), "overlayCardSurfaceMaterial")
        assert material_loader.property("active") is True
        assert normal.item.findChild(type(root), "overlayCardSurfaceMaterial").property("active") is False

        # The Context Menu inherits the baseline through the same owner (no second one).
        controller.apply_context_menu_surface_material("acrylic")
        assert controller.surface_backdrop_owner is owner
        assert root.property("contextMenuSurfaceBackdrop") is owner.item

        # Edges: a transition run sets continuous refresh, clearing it does a one-shot.
        assert owner.item.armed is True        # the creation one-shot is pending
        controller.apply_context_menu_surface_material("normal")
        host.retire_widget(glass)
        assert owner.parked is True
        assert root.property("contextMenuSurfaceBackdrop") is None
        assert normal.item.property("cardSurfaceBackdrop") is None
        assert owner.item.armed is False

        # A material in the same generation wakes the parked owner instead of making another.
        host.create_widget(object_name="mica", model_identity="media",
                           geometry=OverlayWidgetGeometry(10, 200, 200, 100),
                           card_style=OverlayCardStyle(surface_material="mica"))
        assert controller.surface_backdrop_owner is owner and owner.parked is False
        assert len(_backdrops(root)) == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def test_owner_follows_transition_and_image_edges(qt_app) -> None:
    from rendering.quick.surface_backdrop_owner import SurfaceBackdropOwner
    from PySide6.QtQuick import QQuickItem

    root = QQuickItem()
    root.setWidth(400)
    root.setHeight(300)
    owner = SurfaceBackdropOwner(root, screen_index=0)
    item = owner.item
    owner.set_materials(frozenset({"glass", "mica"}))
    owner.set_transition_active(True)
    assert item._shared.continuous is True
    from rendering.quick.widgets.surface_material import TRANSITION_REFRESH_INTERVAL_S
    assert item._shared.min_interval_s == min(TRANSITION_REFRESH_INTERVAL_S["glass"],
                                              TRANSITION_REFRESH_INTERVAL_S["mica"])
    serial = item._shared.requested_serial
    owner.set_transition_active(False)
    assert item._shared.continuous is False
    assert item._shared.requested_serial == serial + 1   # the final frame / adopted wallpaper
    owner.note_background_changed()
    assert item._shared.requested_serial == serial + 2
    root.setWidth(500)                                    # geometry edge
    assert item._shared.requested_serial == serial + 3 and item.width() == 500
    owner.park()
    owner.note_background_changed()
    owner.set_transition_active(True)
    assert item._shared.requested_serial == serial + 3 and item._shared.continuous is False
    root.deleteLater()
    qt_app.processEvents()


# --------------------------------------------------------------------------- pixels


@pytest.fixture()
def material_scene(qt_app):
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("hidden GL scene needs the Windows QPA")
    scene = MaterialScene(640, 360)
    yield scene
    scene.close()


def _flat_image(width, height, left, right, identity):
    from rendering.quick.image_state import PresentationImage

    row = bytes(left) * (width // 2) + bytes(right) * (width - width // 2)
    return PresentationImage(identity, identity, (float(width), float(height)), 1.0, (width, height),
                             width * 4, row * height)


def test_normal_is_exact_a_material_blurs_what_is_beneath_and_parking_restores_normal(material_scene) -> None:
    import numpy
    from PySide6.QtGui import QColor
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    scene = material_scene
    image = _flat_image(640, 360, (220, 40, 40, 255), (40, 60, 220, 255), "split")
    scene.set_wallpaper(image)
    style = OverlayCardStyle(background_color=QColor(20, 20, 20, 77), border_width=0.0, shadow_enabled=False)
    card = scene.host.create_widget(object_name="card", model_identity="clock",
                                    geometry=OverlayWidgetGeometry(170, 100, 300, 160), card_style=style)
    scene.presentations = []
    scene.render(4)
    normal = numpy.asarray(scene.read(), numpy.int16)

    scene.set_material("acrylic")
    scene.render(1)
    # Fail closed: the frame that creates the backdrop samples no texture yet and shows Normal.
    first = numpy.asarray(scene.read(), numpy.int16)
    # Exact inside the corner radius; the 1 px rim differs only by antialiasing method (vertex AA vs the
    # shader's SDF), which a card border covers.
    assert numpy.array_equal(first[110:250, 180:460], normal[110:250, 180:460])
    assert numpy.abs(first - normal).max() <= 12
    scene.render(3)
    acrylic = numpy.asarray(scene.read(), numpy.int16)
    inside_left, inside_right = acrylic[180, 200], acrylic[180, 440]
    # Outside the card nothing changed; inside, the backdrop's colour follows the wallpaper beneath.
    assert numpy.array_equal(normal[20:90], acrylic[20:90])
    assert inside_left[0] > inside_left[2] and inside_right[2] > inside_right[0]
    # Blurred: across the colour edge under the card the material changes gradually.
    row = acrylic[180, 300:340, 0]
    assert numpy.all(numpy.abs(numpy.diff(row)) < 12)
    assert not numpy.array_equal(normal[110:250, 180:460], acrylic[110:250, 180:460])

    scene.set_material("normal")
    scene.render(3)
    assert numpy.array_equal(numpy.asarray(scene.read(), numpy.int16), normal)
    assert scene.owner.parked is True
    card.item.deleteLater()


def test_material_follows_a_running_transition(material_scene) -> None:
    import numpy
    from PySide6.QtGui import QColor
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    scene = material_scene
    red = _flat_image(640, 360, (220, 40, 40, 255), (220, 40, 40, 255), "red")
    green = _flat_image(640, 360, (40, 200, 60, 255), (40, 200, 60, 255), "green")
    scene.set_wallpaper(red)
    scene.host.create_widget(object_name="card", model_identity="clock",
                             geometry=OverlayWidgetGeometry(170, 100, 300, 160),
                             card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 77),
                                                         shadow_enabled=False))
    scene.presentations = []
    scene.set_material("glass")
    scene.render(4)
    scene.start_transition("crossfade", red, green, 0.0)
    scene.render(2)
    early = numpy.asarray(scene.frame_at("crossfade", red, green, 0.1), numpy.int16)[180, 320]
    late = numpy.asarray(scene.frame_at("crossfade", red, green, 0.9), numpy.int16)[180, 320]
    assert late[1] - early[1] > 60 and early[0] - late[0] > 60


# --------------------------------------------------------------------------- legibility


def _between(text: str, begin: str, end: str) -> str:
    return text[text.index(begin):text.index(end)]


def test_text_plate_evaluates_the_identical_surface_function() -> None:
    card = (QML / "shaders" / "surface_material.frag").read_text(encoding="utf-8")
    plate = (QML / "shaders" / "text_legibility.frag").read_text(encoding="utf-8")
    block = _between(card, "// SURFACE BEGIN", "// SURFACE END")
    assert "vec4 surfaceAt(" in block
    assert block == _between(plate, "// SURFACE BEGIN", "// SURFACE END")
    for name in ("text_legibility.vert.qsb", "text_legibility.frag.qsb"):
        assert (QML / "shaders" / name).is_file()


def test_text_runs_change_only_on_an_active_material() -> None:
    text = (QML / "ShadowedText.qml").read_text(encoding="utf-8")
    header = (QML / "BrandedHeader.qml").read_text(encoding="utf-8")
    # The plate loads only on an active material; the soft halo drops only there.
    assert "active: shadowedText.onSurfaceMaterial && shadowedText.surfacePlateEnabled" in text
    assert "&& !(shadowedText.shadowSoft && shadowedText.onSurfaceMaterial)" in text
    assert "&& !shadowedText.onSurfaceMaterial" in text
    # Header labels sit on the header's own fill and opt out.
    assert header.count("surfacePlateEnabled: false") == 2


def _text_run(scene, card, *, text: str, color: str, pixel_size: int, soft: bool):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickItem

    engine = scene.scene.qml_context.engine()
    component = QQmlComponent(engine)
    component.setData(
        (f'import QtQuick\nShadowedText {{ x: 30; y: 40; width: 220; height: 20; text: "{text}"; '
         f'color: "{color}"; font.pixelSize: {pixel_size}; shadowEnabled: true; '
         f'shadowSoft: {"true" if soft else "false"}; shadowColor: "#96000000" }}').encode(),
        QUrl.fromLocalFile(str(QML / "_test_run.qml")))
    item = component.create(scene.scene.qml_context)
    assert item is not None, component.errorString()
    content = card.item.findChild(QQuickItem, "overlayCardContent")
    item.setParentItem(content)
    item.setParent(content)
    return item


def test_small_text_meets_4_5_on_a_busy_backdrop_and_normal_is_untouched(material_scene) -> None:
    import numpy
    from PySide6.QtGui import QColor
    from PySide6.QtQuick import QQuickItem
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry
    from tools.surface_material_capture import measure_text_legibility

    scene = material_scene
    # Busy, bright stripes under a dim grey 12 px run on a dark-theme Glass card: the card's
    # own 3:1 floor is not enough for it, only the run's plate brings it to 4.5:1.
    width, height = 640, 360
    stripes = bytearray()
    for _y in range(height):
        for x in range(width):
            stripes += bytes((250, 240, 150, 255)) if (x // 6) % 2 else bytes((235, 200, 245, 255))
    from rendering.quick.image_state import PresentationImage

    scene.set_wallpaper(PresentationImage("stripes", "stripes", (640.0, 360.0), 1.0, (width, height),
                                          width * 4, bytes(stripes)))
    card = scene.host.create_widget(object_name="card", model_identity="clock",
                                    geometry=OverlayWidgetGeometry(170, 100, 300, 160),
                                    card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 77),
                                                                shadow_enabled=False))
    scene.presentations = []
    run = _text_run(scene, card, text="03D AGO 25M", color="#9a9a9a", pixel_size=12, soft=True)
    scene.render(4)
    out = Path(__file__).resolve().parent / "_surface_material_run.png"
    try:
        normal_rows = measure_text_legibility(scene, out)
        plate = run.findChild(QQuickItem, "shadowedTextLegibilityPlate")
        shadow = run.findChild(QQuickItem, "shadowedTextShadow")
        assert plate.property("active") is False and shadow.isVisible()
        normal = numpy.asarray(scene.read(), numpy.int16)

        scene.set_material("glass")
        scene.render(4)
        rows = measure_text_legibility(scene, out)
        assert plate.property("active") is True
        assert shadow.isVisible() is False            # no soft halo on a material
        mine = [row for row in rows if row["text"].startswith("03D")]
        assert mine and mine[0]["p5"] >= 4.5, (mine, normal_rows)

        scene.set_material("normal")
        scene.render(3)
        assert plate.property("active") is False and shadow.isVisible()
        assert numpy.array_equal(numpy.asarray(scene.read(), numpy.int16), normal)
    finally:
        out.unlink(missing_ok=True)


# --------------------------------------------------------------------------- per-family row


def test_per_family_row_round_trips_and_a_page_save_keeps_unbuilt_values(qt_app, settings_manager) -> None:
    from core.settings.default_contract import require_canonical_default
    from rendering.quick.widgets.surface_material import INHERIT, normalize_surface_material, resolve_surface_material
    from ui.tabs.widgets_tab import WidgetsTab

    # Every card family declares the key (a valid value or Inherit), so a page save keeps it.
    widgets_defaults = require_canonical_default("widgets")
    for section in ("clock", "weather", "media", "reddit", "gmail", "system_stats", "steam_progress",
                    "achievement_pulse", "abandonment_issues", "friend_pulse", "feeds_custom_1",
                    "feeds_news_world"):
        assert normalize_surface_material(widgets_defaults[section]["surface_material"],
                                          allow_inherit=True) is not None, section

    settings_manager.set("widgets", {
        "weather": {"enabled": True, "surface_material": "glass"},
        "clock": {"enabled": True, "surface_material": "mica"},
        "global": {"surface_material": "acrylic"},
    })
    tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "weather"})
    try:
        combo = tab._surface_material_rows["weather"]
        assert combo.currentData() == "glass"
        combo.setCurrentIndex(combo.findData("frosted"))      # saves through the tab (debounced)
        tab.flush_pending_changes()
        widgets = settings_manager.get("widgets")
        assert widgets["weather"]["surface_material"] == "frosted"
        # The clock page was never built: its value survives the weather page's save.
        assert "clock" not in tab._surface_material_rows
        assert widgets["clock"]["surface_material"] == "mica"
        assert widgets["global"]["surface_material"] == "acrylic"
        assert resolve_surface_material(widgets, "weather") == "frosted"
        assert resolve_surface_material(widgets, "clock2") == "mica"     # instances follow their family
        combo.setCurrentIndex(combo.findData(INHERIT))
        tab.flush_pending_changes()
        widgets = settings_manager.get("widgets")
        assert widgets["weather"]["surface_material"] == INHERIT
        assert resolve_surface_material(widgets, "weather") == "acrylic"
    finally:
        tab.deleteLater()
        qt_app.processEvents()

