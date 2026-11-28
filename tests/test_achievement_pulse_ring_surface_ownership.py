"""Achievement Pulse: the ring and its inner circle own their surface controls; the card does not.

The card is an ordinary card (shared Surface Material row, shared card controls). The pulse ring
and, separately, the ring's inner circle each carry their own persisted material choice, and the
ring is a special object that still draws when Widget Themes' Borderless is on.
"""
from __future__ import annotations

import pytest
from PySide6.QtQuick import QQuickItem

from rendering.quick.widgets.achievement_pulse import (
    AchievementPulsePresentationConfig,
    AchievementPulsePresentationStyle,
)
from rendering.quick.widgets.surface_material import (
    INHERIT,
    SURFACE_MATERIALS,
    resolve_achievement_pulse_child_surface_modes,
    resolve_surface_material,
    with_surface_material,
)
from rendering.quick.widgets.theme_projection import with_borderless
from rendering.widget_descriptors import collect_widget_section_save_result
from ui.tabs.widgets_tab import WidgetsTab
from tests.test_qtquick_achievement_pulse_presentation import (
    _config,
    _create_qml_item,
    _find_visual_item,
    _model,
    _shadow_values,
)
from widgets.steam_achievement_preparation import AchievementPulsePreparedPresentation
from widgets.steam_card_models import build_mock_steam_view_model

_MATERIALS = [m for m in SURFACE_MATERIALS if m != "normal"]
_RING_KEY = "progress_ring_surface_material"
_CIRCLE_KEY = "progress_circle_surface_material"


def _explicit_materials() -> tuple[str, str]:
    """Two distinct non-Normal materials, derived from the canonical list."""
    return _MATERIALS[0], _MATERIALS[1]


def _widgets(**pulse) -> dict:
    return {"achievement_pulse": dict(pulse)}


def test_ring_and_circle_choices_are_their_own_keys_and_never_the_cards() -> None:
    ring, circle = _explicit_materials()
    widgets = _widgets(**{_RING_KEY: ring, _CIRCLE_KEY: circle})
    config = AchievementPulsePresentationConfig.from_widgets_mapping(widgets)
    assert (config.progress_ring_surface_material, config.progress_circle_surface_material) == (ring, circle)
    assert resolve_achievement_pulse_child_surface_modes(widgets) == (ring, circle)
    # The card's own material resolves exactly as it does without the ring/circle keys.
    assert resolve_surface_material(widgets, "achievement_pulse") == resolve_surface_material(
        _widgets(), "achievement_pulse"
    )


def test_old_profiles_without_the_new_keys_follow_the_card_and_garbage_falls_back() -> None:
    legacy = _widgets(progress_circle_material=True, progress_pulse=True)
    config = AchievementPulsePresentationConfig.from_widgets_mapping(legacy)
    assert config.progress_ring_surface_material == INHERIT
    assert config.progress_circle_surface_material == INHERIT
    assert config.progress_circle_material is True  # the legacy bool key still loads
    junk = AchievementPulsePresentationConfig.from_widgets_mapping(
        _widgets(**{_RING_KEY: "no-such-material", _CIRCLE_KEY: 7})
    )
    assert junk.progress_ring_surface_material == INHERIT
    assert junk.progress_circle_surface_material == INHERIT


def test_explicit_child_material_demands_the_backdrop_without_changing_the_card_style() -> None:
    ring, _circle = _explicit_materials()
    config = AchievementPulsePresentationConfig.from_widgets_mapping({})
    style = AchievementPulsePresentationStyle.project(config, _shadow_values())
    plain = with_surface_material(style, _widgets(), "achievement_pulse")
    demanded = with_surface_material(style, _widgets(**{_RING_KEY: ring}), "achievement_pulse")
    assert ring in demanded.card_style.child_surface_modes
    assert plain.card_style.child_surface_modes == ()
    assert demanded.card_style.surface_material == plain.card_style.surface_material
    # A dormant pulse asks for nothing.
    dormant = with_surface_material(
        style, _widgets(**{_RING_KEY: ring, "progress_pulse": False}), "achievement_pulse"
    )
    assert dormant.card_style.child_surface_modes == ()


def test_pulse_circle_is_not_a_border_and_survives_borderless() -> None:
    config = AchievementPulsePresentationConfig.from_widgets_mapping({})
    borderless = with_borderless(config, {"global": {"borderless": True}})
    model = _model(config=borderless)
    assert model.capsuleBorderColor.alpha() == 0  # capsule borders really are hidden
    assert model.progressRingColor.alpha() > 0
    assert model.progressRingColor.rgb() == QColorOf(config.progress_ring_color).rgb()


def QColorOf(rgba):  # noqa: N802 - tiny local helper
    from PySide6.QtGui import QColor

    return QColor(*rgba)


def _prepared_item(config):
    model = _model(config=config)
    model.activate()
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(model=build_mock_steam_view_model("achievement_pulse")),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    return model, engine, component, item


def _teardown(qt_app, model, item, component, engine, backdrop) -> None:
    model.retire()
    item.deleteLater()
    component.deleteLater()
    engine.deleteLater()
    backdrop.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_explicit_ring_material_stands_on_a_normal_card_and_explicit_normal_beats_a_material_card(
    qt_app,
) -> None:
    ring, _circle = _explicit_materials()
    model, engine, component, item = _prepared_item(_config(**{_RING_KEY: ring}))
    backdrop = QQuickItem()
    try:
        ring_material = _find_visual_item(item, "achievementProgressRingMaterial")
        ring_layer = _find_visual_item(item, "achievementProgressRingLayer")
        assert ring_material is not None and ring_layer is not None
        item.setProperty("cardSurfaceBackdrop", backdrop)
        item.setProperty("cardSurfaceMaterial", "normal")
        qt_app.processEvents()
        # The card is Normal; the ring still takes its own material.
        assert ring_material.property("active") is True
        assert ring_layer.isVisible()
    finally:
        _teardown(qt_app, model, item, component, engine, backdrop)

    # A material card with the ring explicitly Normal: the card is untouched, the ring is flat.
    model, engine, component, item = _prepared_item(_config(**{_RING_KEY: "normal"}))
    backdrop = QQuickItem()
    try:
        ring_material = _find_visual_item(item, "achievementProgressRingMaterial")
        ring_layer = _find_visual_item(item, "achievementProgressRingLayer")
        item.setProperty("cardSurfaceBackdrop", backdrop)
        item.setProperty("cardSurfaceMaterial", ring)
        qt_app.processEvents()
        assert ring_material.property("active") is False
        assert not ring_layer.isVisible()
        assert item.property("cardSurfaceMaterial") == ring
    finally:
        _teardown(qt_app, model, item, component, engine, backdrop)


@pytest.mark.qt
def test_circle_material_is_independent_of_the_ring_and_the_card(qt_app) -> None:
    ring, circle = _explicit_materials()
    model, engine, component, item = _prepared_item(
        _config(progress_circle_material=True, **{_RING_KEY: "normal", _CIRCLE_KEY: circle})
    )
    backdrop = QQuickItem()
    try:
        inner = _find_visual_item(item, "achievementProgressCircleMaterial")
        ring_material = _find_visual_item(item, "achievementProgressRingMaterial")
        item.setProperty("cardSurfaceBackdrop", backdrop)
        item.setProperty("cardSurfaceMaterial", "normal")
        qt_app.processEvents()
        assert inner.property("active") is True       # the circle's own material
        assert ring_material.property("active") is False  # the ring chose Normal
    finally:
        _teardown(qt_app, model, item, component, engine, backdrop)

    # The legacy on/off key still gates the circle.
    model, engine, component, item = _prepared_item(
        _config(progress_circle_material=False, **{_CIRCLE_KEY: circle})
    )
    backdrop = QQuickItem()
    try:
        inner = _find_visual_item(item, "achievementProgressCircleMaterial")
        item.setProperty("cardSurfaceBackdrop", backdrop)
        qt_app.processEvents()
        assert inner.property("active") is False
    finally:
        _teardown(qt_app, model, item, component, engine, backdrop)


@pytest.mark.qt
def test_borderless_pulse_ring_still_draws(qt_app) -> None:
    config = with_borderless(_config(), {"global": {"borderless": True}})
    model, engine, component, item = _prepared_item(config)
    backdrop = QQuickItem()
    try:
        face = _find_visual_item(item, "achievementProgressCircleFace")
        assert face is not None
        qt_app.processEvents()
        from PySide6.QtQml import QQmlProperty

        assert QQmlProperty(face, "border.color").read().alpha() > 0
        assert QQmlProperty(face, "border.width").read() > 0
    finally:
        _teardown(qt_app, model, item, component, engine, backdrop)


def test_settings_page_round_trips_the_ring_and_circle_controls(qt_app, settings_manager) -> None:
    from core.dev_gates import force_gate, is_steam_enabled

    ring, circle = _explicit_materials()
    prior = is_steam_enabled()
    force_gate(steam=True)
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            ring_combo = tab.achievement_pulse_progress_ring_surface
            circle_combo = tab.achievement_pulse_progress_circle_surface
            ring_combo.setCurrentIndex(ring_combo.findData(ring))
            circle_combo.setCurrentIndex(circle_combo.findData(circle))
            payload = collect_widget_section_save_result(tab, "steam")[2]
            assert payload[_RING_KEY] == ring
            assert payload[_CIRCLE_KEY] == circle
        finally:
            tab.deleteLater()
    finally:
        force_gate(steam=prior)


def _layer_enabled(item) -> bool:
    # An item with layer.enabled is a texture provider (the shader effect itself is not a layer).
    return bool(item.objectName() != "materialSurface" and item.isTextureProvider())


@pytest.mark.qt
def test_ring_material_is_a_border_only_surface_drawn_in_the_scene_not_through_a_layer(qt_app) -> None:
    """A layer makes the material's backdrop coordinate span the layer's texture (a whole
    wallpaper squeezed into the ring: the blotchy smear). The ring must be the material's own
    border-only annulus with no layered ancestor between it and the card."""
    ring, _circle = _explicit_materials()
    model, engine, component, item = _prepared_item(_config(**{_RING_KEY: ring}))
    backdrop = QQuickItem()
    try:
        ring_material = _find_visual_item(item, "achievementProgressRingMaterial")
        item.setProperty("cardSurfaceBackdrop", backdrop)
        item.setProperty("cardSurfaceMaterial", "normal")
        qt_app.processEvents()
        assert ring_material.property("active") is True
        surface = ring_material.property("item")
        assert surface.property("fillSurfaceEnabled") == 0.0
        # 2.0 = the annulus carries the FULL card surface; 1.0 was the border-stroke recipe,
        # which tinted every material with the ring colour so all of them read as one silver band.
        assert surface.property("borderSurfaceEnabled") == 2.0
        assert surface.property("borderWidth") > 0.0
        # Tinted and guarded exactly as a card is, so a material reads as itself.
        assert surface.property("tintColor") == item.property("cardBackgroundColor")
        # The guard is the ring wrapper's own choice passed through, not a value pinned here.
        assert surface.property("legibilityPanel") == ring_material.property("legibilityPanel")
        node = surface
        while node is not None:
            assert not _layer_enabled(node), node.objectName()
            node = node.parentItem()
    finally:
        _teardown(qt_app, model, item, component, engine, backdrop)


def test_shader_gives_a_child_ring_the_card_surface_not_the_border_stroke_recipe() -> None:
    from pathlib import Path

    shader = (Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml" / "shaders"
              / "surface_material.frag").read_text(encoding="utf-8")
    ring = shader[shader.index("if (ringCoverage > 0.0001) {"):]
    ring = ring[:ring.index("fragColor")]
    assert "borderSurfaceEnabled > 1.5" in ring
    assert ring.index("surfaceAt(") < ring.index("borderAt(")
