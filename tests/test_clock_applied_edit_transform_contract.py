"""Import-free Clock Edit paint dependency contract.

The actual retained-scene mapping and performance-warning gate live in
``test_qtquick_clock_presentation.py``. These checks guard every Clock role
against falling back to early-notifying model inputs or non-bindable lists.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


CLOCK_ROLES = (
    ("ClockDigitalFace.qml", "timeText", "digitalTime", "time_text", True),
    ("ClockDigitalFace.qml", "digitalSeparator", "digitalSeparator", "separator", True),
    ("ClockDigitalFace.qml", "calendarText", "digitalCalendar", "calendar_text", True),
    ("ClockDigitalFace.qml", "timezoneText", "digitalTimezone", "timezone_text", True),
    ("ClockAnalogueFace.qml", "faceCoreEditTarget", "analogueFaceCore", "clock_face", False),
    ("ClockAnalogueFace.qml", "analogueSeparator", "analogueSeparator", "separator", True),
    ("ClockAnalogueFace.qml", "analogueCalendar", "analogueCalendar", "calendar_text", True),
    ("ClockAnalogueFace.qml", "analogueTimezone", "analogueTimezone", "timezone_text", True),
)


def test_clock_roles_observe_applied_transform_objects_with_no_new_layout_owner():
    for filename, target, prefix, role, has_translate in CLOCK_ROLES:
        source = (QML / filename).read_text(encoding="utf-8")
        item = source.split(f"id: {target}\n", 1)[1]
        assert "readonly property string customEditMappingDependency:" in item.split(
            "transform: [", 1
        )[0], (filename, role)
        signature = item.split("customEditMappingDependency:", 1)[1].split(
            '].join("|")', 1
        )[0]
        paint = item.split("transform: [", 1)[1].split("]", 1)[0]
        scale = f"{prefix}AppliedScale"
        assert f"Scale {{ id: {scale};" in paint, (filename, role)
        assert f"{scale}.xScale" in signature and f"{scale}.yScale" in signature
        assert f'childWidthScale("{role}")' in paint
        assert f'childHeightScale("{role}")' in paint
        if has_translate:
            translate = f"{prefix}AppliedTranslation"
            assert f"Translate {{ id: {translate};" in paint
            assert f"{translate}.x" in signature and f"{translate}.y" in signature
            assert f'childOffsetX("{role}")' in paint
            assert f'childOffsetY("{role}")' in paint
        else:
            assert f"{scale}.origin.x" in signature
            assert f"{scale}.origin.y" in signature
        assert "childGeometry" not in signature  # no early model notification
        assert "transform[" not in signature  # non-bindable Qt transform list
    for filename in {role[0] for role in CLOCK_ROLES}:
        source = (QML / filename).read_text(encoding="utf-8")
        assert source.count("customEditMappingDependency:") == 4
        for banned in ("Timer {", "FrameAnimation {", "Connections {", "SettingsManager"):
            assert banned not in source


def test_clock_mode_roles_keep_existing_variant_and_centered_face_contract():
    source = (QML / "ClockPresentation.qml").read_text(encoding="utf-8")
    assert 'if (_isDigital) {' in source
    assert '"roleId": "time_text", "target": digitalFace.customTimeTarget' in source
    assert '"roleId": "clock_face"' in source
    assert '"centeredResize": true' in source
    analog = (QML / "ClockAnalogueFace.qml").read_text(encoding="utf-8")
    assert 'id: faceCoreEditTarget' in analog
    assert 'opacity: 0.0' in analog
    assert 'origin.x: faceCoreEditTarget.width / 2.0' in analog
    assert 'origin.x: staticFace.centerX' in analog
    assert '"clock_face"' in analog


def test_clock_digital_stack_fits_intrinsic_unwrapped_paint_inside_compact_card():
    """A narrow independent outer X/Y edit cannot leave glyph ink beyond its Edit target."""
    digital = (QML / "ClockDigitalFace.qml").read_text(encoding="utf-8")
    stack = digital.split("id: contentColumn", 1)[1].split("ShadowedText {", 1)[0]
    assert "width: Math.max(parent.width, digitalFace.preferredContentWidth)" in stack
    assert "height: digitalFace.preferredContentHeight" in stack
    assert "transformOrigin: Item.Center" in stack
    assert "scale: Math.min(1.0," in stack
    assert "Math.max(1.0, parent.width) / Math.max(1.0, width)" in stack
    assert "Math.max(1.0, parent.height) / Math.max(1.0, height)" in stack
    assert "anchors.centerIn: parent" in stack
    assert "timeText.implicitWidth" in digital.split("preferredContentWidth:", 1)[1].split("readonly property real preferredContentHeight:", 1)[0]
    assert "contentColumn.childrenRect.height" in digital
    for prohibited in ("Timer {", "Connections {", "Qt.callLater", "SettingsManager", "fontSizeMode: Text.Fit"):
        assert prohibited not in digital
    # The change must be family paint only, not a new shared/outer geometry owner.
    clock = (QML / "ClockPresentation.qml").read_text(encoding="utf-8")
    assert "uniformScaleTransform: true" not in clock
    assert '"centeredResize": true' in clock


def test_clock_role_list_is_stable_during_intrinsic_text_size_updates():
    clock = (QML / "ClockPresentation.qml").read_text(encoding="utf-8")
    block = clock.split("customEditableChildRoles: {", 1)[1].split("ClockDigitalFace {", 1)[0]
    assert "roles[i].normalizationTarget = clockRoot" in block
    assert 'roles[i].normalizationWidthProperty = "preferredContentWidth"' in block
    assert 'roles[i].normalizationHeightProperty = "preferredContentHeight"' in block
    assert "clockRoot.preferredContentWidth" not in block
    assert "clockRoot.preferredContentHeight" not in block
    mapper = (QML / "CustomLayoutOverlay.qml").read_text(encoding="utf-8")
    assert "const preferred = source && !live ? source.preferredContentWidth : 0.0" in mapper
    assert "const preferred = source && !live ? source.preferredContentHeight : 0.0" in mapper
    assert "QQuickItem::transform" not in mapper
