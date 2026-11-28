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


def test_baseline_follows_the_theme_and_a_widget_value_beats_it() -> None:
    from dataclasses import replace
    from core.settings.default_contract import require_canonical_default
    from rendering.quick.widgets.surface_material import (
        SURFACE_MATERIALS, THEME, resolve_global_surface_material, resolve_surface_material,
        normalize_surface_material,
    )
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME

    # Authored defaults may change; validate the domain rather than today's choice.
    authored = require_canonical_default("widgets.global.surface_material")
    assert normalize_surface_material(authored, allow_theme=True) in {*SURFACE_MATERIALS, THEME}
    assert "normal" in SURFACE_MATERIALS
    # Test-controlled theme with no material ensures the fallback is Normal.
    no_material_theme = replace(DEFAULT_DARK_WIDGET_THEME, surface_material=None)
    assert resolve_global_surface_material({}, theme=no_material_theme) == "normal"
    assert resolve_global_surface_material(
        {"global": {"surface_material": "theme"}}, theme=no_material_theme
    ) == "normal"
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

    found, stack = [], list(root.childItems())       # the visual tree: the core's item has no QObject parent
    while stack:
        item = stack.pop()
        if isinstance(item, QQuickItem):
            if item.objectName() == "surfaceBackdropSource":
                found.append(item)
            stack.extend(item.childItems())
    return found


def test_all_normal_creates_nothing_and_the_first_material_creates_one_owner(qt_app, monkeypatch) -> None:
    from PySide6.QtGui import QColor
    from rendering.quick.render import native_surface_backdrop as nsb
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry
    from tests.test_native_backdrop import _FakeCore

    # N5.2h: the backdrop is the core's on every backend; a stand-in core makes it (its pixels: test_native_backdrop
    # and backdrop_pyramid_check).
    core = _FakeCore()
    monkeypatch.setattr(nsb, "native_backdrop_core", lambda: core)
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
        assert owner is not None and not owner.parked and owner.native
        assert len(core.made) == 1 and owner.item is core.made[0].item
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

        # The last material gone: the consumers are unbound and the core's item parked (its QRhi objects go).
        controller.apply_context_menu_surface_material("normal")
        host.retire_widget(glass)
        assert owner.parked is True and core.made[0].calls[-1] == ("parked", True)
        assert root.property("contextMenuSurfaceBackdrop") is None
        assert normal.item.property("cardSurfaceBackdrop") is None

        # A material in the same generation wakes the parked owner instead of making another.
        host.create_widget(object_name="mica", model_identity="media",
                           geometry=OverlayWidgetGeometry(10, 200, 200, 100),
                           card_style=OverlayCardStyle(surface_material="mica"))
        assert controller.surface_backdrop_owner is owner and owner.parked is False
        assert ("parked", False) in core.made[0].calls and len(core.made) == 1
        assert len(_backdrops(root)) == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


# --------------------------------------------------------------------------- pixels


# N5.2h: the backdrop is the core's on every backend. Its pixels (Normal exact before the first photo and when
# parked, the material over what is beneath, following a running transition) are judged on the native route by
# native/core/python/backdrop_pyramid_check.py (test_the_native_backdrop_rounds_pass_on_opengl below) and against
# the Python blit on the same frames by its "blit" round; the Python blit's own pixel tests went with the switch.


def test_the_native_backdrop_rounds_pass_on_opengl(tmp_path) -> None:
    """The check's OpenGL rounds in their own process (Qt Quick's graphics API is process-wide), hidden hosts only:
    Normal exact before the first photo and when parked, one build per change and none at rest, the cards following a
    running transition, the owner's route native, and the native backdrop against the blit on the same frames. Needs
    the built module (only GitHub builds it); skipped where this checkout has none."""
    import json
    import os
    import subprocess
    import sys

    from rendering.native import loader

    module_dir = ROOT / "release" / "native_module"
    if os.name != "nt" or not (module_dir / f"{loader.MODULE_NAME}.pyd").is_file():
        pytest.skip(f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd")
    record_path = tmp_path / "child.json"
    rounds = ("rest", "transition", "route", "blit")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "native" / "core" / "python" / "backdrop_pyramid_check.py"), "--child", "--api",
         "opengl", "--rounds", *rounds, "--repo", str(ROOT), "--module-dir", str(module_dir), "--out-dir",
         str(tmp_path), "--child-json", str(record_path)],
        capture_output=True, text=True, timeout=1800, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr[-2000:]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert not record.get("error"), record.get("error")
    for name in rounds:
        entry = record[name]
        assert entry["pass"], {k: v for k, v in entry.get("checks", {}).items() if not v} or entry.get("error")
    assert record["live_hosts_at_end"] == 0


# --------------------------------------------------------------------------- legibility


def _between(text: str, begin: str, end: str) -> str:
    return text[text.index(begin):text.index(end)]


def test_text_plate_evaluates_the_identical_surface_function() -> None:
    card = (QML / "shaders" / "surface_material.frag").read_text(encoding="utf-8")
    plate = (QML / "shaders" / "text_legibility.frag").read_text(encoding="utf-8")
    row = (QML / "shaders" / "text_legibility.vert").read_text(encoding="utf-8")
    block = _between(card, "// SURFACE BEGIN", "// SURFACE END")
    assert "vec4 surfaceAt(" in block
    assert block == _between(plate, "// SURFACE BEGIN", "// SURFACE END")
    # The row's even tone is computed in the vertex stage from the same surface function.
    assert block == _between(row, "// SURFACE BEGIN", "// SURFACE END")
    for name in ("text_legibility.vert.qsb", "text_legibility.frag.qsb"):
        assert (QML / "shaders" / name).is_file()


def test_text_runs_change_only_on_an_active_material() -> None:
    text = (QML / "ShadowedText.qml").read_text(encoding="utf-8")
    # The card's legibility panel holds the floor: a run loads a plate of its own only when its
    # corrected dark ink still cannot read on the bounded panel (an item-opacity fade), never
    # as a per-run chip on every run; the soft halo drops only on an active material.
    assert text.count("Loader {") == 1 and text.count("TextLegibilityPlate {") == 1
    assert "active: shadowedText.inkNeedsPlate &&" in text
    # It fades in from its edge (a glow under the run, not a sticker); rows keep 1.5 px.
    assert "edgeSoftness: inkPlate.soft" in text
    plate = (QML / "TextLegibilityPlate.qml").read_text(encoding="utf-8")
    assert "property real edgeSoftness: 1.5" in plate
    assert "readonly property bool inkNeedsPlate: _inkSolution !== null && !_inkSolution[4]" in text
    assert "&& !(shadowedText.shadowSoft && shadowedText.onSurfaceMaterial)" in text
    assert "&& !shadowedText.onSurfaceMaterial" in text


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

