"""Achievement Pulse children stay inside the card at every size (operator defect, 22 Nov: shelves cut out)."""

from __future__ import annotations

import pytest

from core.settings.default_contract import require_canonical_default  # noqa: F401
from tests.test_qtquick_achievement_pulse_presentation import (
    AchievementPulsePreparedPresentation, _config, _create_qml_item, _find_visual_item, _model,
    build_mock_steam_view_model,
)

# Stored records as an edit leaves them after the card was made bigger and the children moved into the new room
# (test input, not a default): the shelves and the progress circle sit in the extra area.
PLACED = {"field_group": {"x_offset": 0.22, "y_offset": 0.12},
          "progress_circle": {"x_offset": 0.30, "y_offset": 0.10, "width_scale": 1.2, "height_scale": 1.2}}
CHILDREN = ("achievementFieldGroup", "achievementProgressPulse")


def _inside(item, name: str, width: float, height: float):
    node = _find_visual_item(item, name)
    assert node is not None, name
    scale = float(node.scale())
    right, bottom = node.x() + node.width() * scale, node.y() + node.height() * scale
    return node.x() >= -0.5 and node.y() >= -0.5 and right <= width + 0.5 and bottom <= height + 0.5, (
        name, node.x(), node.y(), right, bottom, width, height)


@pytest.mark.qt
@pytest.mark.parametrize("shelf", [True, False])
def test_children_placed_in_a_larger_card_stay_inside_it_when_the_card_is_made_smaller(qt_app, shelf) -> None:
    model = _model(config=_config(shelf_style=shelf))
    model.activate()
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(model=build_mock_steam_view_model("achievement_pulse")), animate=False)
    base_width, base_height = float(model.baseAuthoredWidth), float(model.baseAuthoredHeight)
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        assert model.set_custom_child_geometry(PLACED) in (True, False)
        # Bigger, then back down through several sizes to the authored minimum.
        for grow_x, grow_y in ((260.0, 160.0), (140.0, 90.0), (60.0, 30.0), (0.0, 0.0)):
            assert model.set_content_extent(base_width + grow_x, base_height + grow_y) in (True, False)
            item.setWidth(model.authoredWidth)
            item.setHeight(model.authoredHeight)
            qt_app.processEvents()
            for name in CHILDREN:
                node = _find_visual_item(item, name)
                if node is None or not node.isVisible():
                    continue
                ok, detail = _inside(item, name, float(model.authoredWidth), float(model.authoredHeight))
                assert ok, (shelf, grow_x, grow_y, detail)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


@pytest.mark.qt
@pytest.mark.parametrize("shelf", [True, False])
def test_a_grown_progress_circle_does_not_push_the_shelves_out_of_the_card(qt_app, shelf) -> None:
    model = _model(config=_config(shelf_style=shelf))
    model.activate()
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(model=build_mock_steam_view_model("achievement_pulse")), animate=False)
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        for scale in (1.0, 1.3, 1.7):
            model.set_custom_child_geometry({"progress_circle": {"width_scale": scale, "height_scale": scale}})
            qt_app.processEvents()
            ok, detail = _inside(item, "achievementFieldGroup", float(model.authoredWidth), float(model.authoredHeight))
            assert ok, (shelf, scale, detail)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
