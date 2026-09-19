"""Cheap ownership/performance-neutrality guard for the edit-only bound mapper.

Real transformed rectangles and thin strokes are covered independently by
``test_qtquick_child_mapped_geometry.py`` under Windows/PySide6.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = (ROOT / "rendering/quick/qml/CustomLayoutOverlay.qml").read_text(encoding="utf-8")


def test_one_four_corner_mapper_serves_target_occupied_obstacle_and_containment():
    helper = QML.split("function mappedItemBounds(item) {", 1)[1].split(
        "function itemRectInFrame(item) {", 1
    )[0]
    for corner in (
        "0.0, 0.0", "item.width, 0.0", "0.0, item.height",
        "item.width, item.height",
    ):
        assert f"item.mapToItem(editFrame, {corner})" in helper
    assert "!isFinite(item.width) || !isFinite(item.height)" in helper
    assert "!isFinite(a.x) || !isFinite(a.y)" in helper
    assert "const bounds = mappedItemBounds(item)" in QML
    assert "return mappedItemBounds(surface)" in QML
    assert "childRoleLayer.mappedItemBounds(targetItem)" in QML
    assert "childRoleLayer.mappedItemBounds(occupiedItem)" in QML
    assert "const obstacleRect = itemRectInFrame(target)" in QML
    assert "occupiedItem !== targetItem" in QML  # no duplicate map for the common case


def test_thin_target_editability_uses_positive_mapped_footprint_only():
    readiness = QML.split("readonly property bool targetReady:", 1)[1].split(
        "readonly property rect mappedOccupiedBounds:", 1
    )[0]
    assert "mappedTargetBounds.width > 0.0" in readiness
    assert "mappedTargetBounds.height > 0.0" in readiness
    assert "targetItem.width > 1.0" not in readiness
    assert "targetItem.height > 1.0" not in readiness
    assert "!item.visible" in QML.split("function mappedItemBounds(item) {", 1)[1].split(
        "function itemRectInFrame(item) {", 1
    )[0]


def test_mapper_lifetime_is_selected_edit_only_and_has_no_scheduling_or_new_owner():
    selected_layer = QML.split("id: childRoleLoader", 1)[1].split(
        "sourceComponent: Component {", 1
    )[0]
    assert "active: editFrame.selectedForChildEdit" in selected_layer
    assert "editFrame.hasPresentationItem" in selected_layer
    # The mapper is nested within that Loader's sourceComponent, not a new
    # root-level normal-runtime listener or family-sized geometry cache.
    assert QML.index("function mappedItemBounds(item)") > QML.index(
        "id: childRoleLayer"
    ) > QML.index("id: childRoleLoader")
    mapper = QML.split("function mappedItemBounds(item) {", 1)[1].split(
        "function itemRectInFrame(item) {", 1
    )[0]
    for forbidden in (
        "Qt.callLater", "Timer", "requestUpdate", "update()", "Settings",
        "write", "onWidthChanged", "onHeightChanged", "Connections",
    ):
        assert forbidden not in mapper
