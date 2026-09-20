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


def test_retained_mapper_observes_bindable_transform_inputs_and_inherited_paint_state():
    # QQuickItem.transform is a non-bindable Qt list: introspecting it within
    # the mapping binding flooded actual Windows logs with 42,624 warnings.
    # The real transform coordinates and clipping are asserted in Qt scene tests.
    mapper = QML.split("id: childRoleLayer", 1)[1].split(
        "function itemRectInFrame(item) {", 1
    )[0]
    assert "function appendMappingChain(values, start)" in mapper
    assert "node = node.parent" in mapper
    # Do NOT read a QQuickItem's non-bindable transform list in QML bindings.
    # Real QML Scale/Translate owners expose their ordinary bindable inputs.
    executable = mapper.split("function appendMappingChain(values, start) {", 1)[1]
    executable = executable.split("// Project a target quad", 1)[0]
    import re
    assert re.search(r"\bnode\.transform\b", executable) is None
    bounds = QML.split("function mappedItemBounds(item) {", 1)[1].split(
        "function itemRectInFrame(item) {", 1
    )[0]
    assert "ancestor.transform" not in bounds
    weather = (ROOT / "rendering/quick/qml/WeatherPresentation.qml").read_text(
        encoding="utf-8",
    )
    media = (ROOT / "rendering/quick/qml/MediaPresentation.qml").read_text(
        encoding="utf-8",
    )
    display = (ROOT / "rendering/quick/qml/DisplayScene.qml").read_text(
        encoding="utf-8",
    )
    assert "paintScale0.xScale, paintScale0.yScale" in weather
    assert "paintTranslate0.x, paintTranslate0.y" in weather
    assert "mutePaintTranslation.x, mutePaintTranslation.y" in media
    assert "pixelShiftPaintTranslation.x, pixelShiftPaintTranslation.y" in display
    # Multiple semantic targets share an ancestor chain. Never subscribe to
    # the same node repeatedly during one selected-Edit mapping evaluation.
    assert "values._mappingSeen" in mapper
    assert "seen.indexOf(node) !== -1" in mapper
    for component in (
        "node.scale", "node.rotation", "node.transformOrigin",
        "node.visible", "node.clip", "node.customEditMappingDependency",
    ):
        assert component in mapper, component
    assert "clipMappedPolygon(points, ancestor)" in mapper
    assert "clipItem.mapToItem(" in mapper
    assert "childRoleLayer.appendMappingChain(values, editFrame)" in QML
    assert "childRoleLayer.appendMappingChain(values, targetItem)" in QML
    assert "modelData.targetSource" in QML
    assert "modelData.alternateTarget" in QML
    # Semantic edit targets may themselves have zero opacity but represent
    # separately painted descendants/siblings. Do not gate on opacity alone.
    assert "!(ancestor.opacity > 0.0)" not in mapper


def test_static_semantic_roles_survive_visibility_and_provider_transitions():
    families = (
        "AchievementPulse", "AbandonmentIssues", "Weather", "Media",
        "FriendPulse", "Reddit", "Gmail", "SystemStats",
    )
    for name in families:
        qml = (ROOT / f"rendering/quick/qml/{name}Presentation.qml").read_text(
            encoding="utf-8",
        )
        # A family may declare a literal stable role array (System Stats' three
        # structural roles) or construct a stable one in a QML binding block.
        role_declaration = qml.split("customEditableChildRoles:", 1)[1].lstrip()
        if role_declaration.startswith("["):
            role_binding = role_declaration.split("\n    ]", 1)[0]
        else:
            role_binding = role_declaration.split("return roles", 1)[0]
        assert not any(gate in role_binding for gate in (
            "if (normalContent.visible", "if (artworkFrame.visible",
            "if (weatherModel.viewState", "if (visibleMetricCount",
            "if (refreshTarget.visible", "if (appVolumeSlider.visible",
            "if (trackMetadata.visible", "if (friendPulseModel.viewMode",
            "if (activitySummary.visible", "if (customFriendFrameRoleTarget.visible",
            "if (ledgerRepeater.count", "if (systemStatsModel.showCpu",
        )), name
    pulse = (ROOT / "rendering/quick/qml/AchievementPulsePresentation.qml").read_text(
        encoding="utf-8",
    )
    assert '"targetSource": unlockRepeater' in pulse
    weather = (ROOT / "rendering/quick/qml/WeatherPresentation.qml").read_text(
        encoding="utf-8",
    )
    ready_roles = weather.split("customEditableChildRoles: {", 1)[1].split(
        "return roles", 1
    )[0]
    assert '"roleId": "location_text", "target": locationText' in ready_roles
    assert '"alternateTarget": rightConditionIcon' in ready_roles
    assert "statusTitle" not in ready_roles


def test_transformed_paint_targets_subscribe_to_applied_transform_properties():
    """A source-input signature can run before Qt updates its painted transform.

    The selected mapping must observe changed properties on each real Scale /
    Translate object, with no QQuickItem.transform-list binding or model-JSON
    fan-out.  The retained Qt scene independently verifies actual coordinates.
    """
    weather = (ROOT / "rendering/quick/qml/WeatherPresentation.qml").read_text(
        encoding="utf-8",
    )
    import re
    scale_ids = re.findall(r"Scale \{ id: (paintScale\d+);", weather)
    translate_ids = re.findall(r"Translate \{ id: (paintTranslate\d+);", weather)
    assert len(scale_ids) == len(translate_ids) == 14
    assert len(set(scale_ids)) == len(set(translate_ids)) == 14
    for index in range(14):
        assert f"paintScale{index}.xScale, paintScale{index}.yScale" in weather
        assert f"paintTranslate{index}.x, paintTranslate{index}.y" in weather
    assert "JSON.stringify(childGeometry" not in weather

    fixture = (ROOT / "tests/test_qtquick_child_mapped_geometry.py").read_text(
        encoding="utf-8",
    )
    assert "outerTranslation.x, outerTranslation.y" in fixture
    assert "innerTranslation.x, innerTranslation.y" in fixture
    # Direct mutation must stay *inside QML*: PySide cannot convert the
    # QQuickTranslate* alias returned by Python QObject.property().
    assert "function setAppliedTranslationX(ancestor, value)" in fixture
    assert "outerTranslation.x = value" in fixture
    assert "innerTranslation.x = value" in fixture
    assert "QQmlExpression(" in fixture
    assert 'probe.property("localTranslationObject")' not in fixture
    assert 'transform.setProperty("x", x_value)' not in fixture

    media = (ROOT / "rendering/quick/qml/MediaPresentation.qml").read_text(
        encoding="utf-8",
    )
    display = (ROOT / "rendering/quick/qml/DisplayScene.qml").read_text(
        encoding="utf-8",
    )
    assert "mutePaintTranslation.x, mutePaintTranslation.y" in media
    assert "pixelShiftPaintTranslation.x, pixelShiftPaintTranslation.y" in display
