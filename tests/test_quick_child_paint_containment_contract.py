"""Source-only regression gate for the ordinary-widget unconditional paint containment and edit lock.

The Qt scene/physical acceptance matrix remains independent; this intentionally
requires no PySide6 and does not claim that clipping repairs authored reflow.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'rendering' / 'quick' / 'qml'
FAMILIES = (
    'AbandonmentIssuesPresentation.qml', 'AchievementPulsePresentation.qml',
    'ClockPresentation.qml', 'FriendPulsePresentation.qml',
    'GmailPresentation.qml', 'MediaPresentation.qml',
    'RedditPresentation.qml', 'SystemStatsPresentation.qml',
    'WeatherPresentation.qml',
)


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_paint_boundary_is_inside_card_but_outside_card_contents() -> None:
    card = _text(QML / 'OverlayCard.qml')
    assert 'default property alias content: contentArea.data' in card
    assert 'objectName: "overlayCardShadow"' in card
    assert 'objectName: "overlayCardBackground"' in card
    assert 'objectName: "overlayCardChildPaintBoundary"' in card
    assert 'clip: true' in card.split('id: contentPaintBoundary', 1)[1].split('id: contentArea', 1)[0]
    assert card.index('id: contentPaintBoundary') < card.index('id: contentArea')
    assert card.index('id: cardShadow') < card.index('id: contentPaintBoundary')
    assert card.index('id: background') < card.index('id: contentPaintBoundary')
    assert 'clip: false' in card.split('id: contentArea', 1)[1]


def test_accessory_has_its_own_boundary_and_the_card_shadow_is_not_clipped() -> None:
    widget = _text(QML / 'OverlayWidget.qml')
    assert 'property bool childPaintContainmentActive' not in widget
    assert 'paintContainmentActive:' not in widget
    assert 'objectName: "overlayAccessoryLayer"' in widget
    accessory = widget.split('id: accessoryLayer', 1)[1]
    assert 'clip: true' in accessory
    assert 'property alias accessoryContent: accessoryLayer.data' in widget
    assert 'clip: false' in widget.split('id: overlayWidget', 1)[1].split('default property alias content:', 1)[0]


def test_all_nine_ordinary_presentations_use_the_same_unconditional_card_boundary() -> None:
    card = _text(QML / 'OverlayCard.qml')
    assert 'clip: true' in card.split('id: contentPaintBoundary', 1)[1].split('id: contentArea', 1)[0]
    for family in FAMILIES:
        source = _text(QML / family)
        assert 'childPaintContainmentActive' not in source, family
        assert 'OverlayWidget {' in source, family
    # The Visualizer is not an ordinary-card child editor; it retains its own
    # independent render/viewport contract.
    assert 'childPaintContainmentActive' not in _text(QML / 'VisualizerPresentation.qml')


def test_edit_lock_hides_only_child_overlay_and_never_changes_card_paint() -> None:
    editor = _text(QML / 'CustomLayoutOverlay.qml')
    widget = _text(QML / 'OverlayWidget.qml')
    card = _text(QML / 'OverlayCard.qml')
    assert 'property bool childEditingLocked: true' in editor
    assert 'objectName: "customLayoutChildEditLock-" + editFrame.widgetId' in editor
    assert 'childEditingLocked = !childEditingLocked' in editor
    assert 'editFrame.toggleChildEditLock()' in editor
    child_loader = editor.split('id: childRoleLoader', 1)[1].split('sourceComponent:', 1)[0]
    assert '&& !editFrame.childEditingLocked' not in child_loader
    assert 'visible: !editFrame.childEditingLocked' in editor.split('id: childRoleLayer', 1)[1].split('NumberAnimation on opacity', 1)[0]
    assert 'visible: targetReady && roleId.length > 0' in editor
    assert 'editFrame.syncChildRequirementNow()' not in editor
    assert 'id: childRoleRepeater' in editor
    assert 'customLayoutOverlay.sessionModel.cancelChildGesture(editFrame.index)' in editor
    # Neither the card nor the QML family binds paint to the edit lock.
    assert 'childEditingLocked' not in widget + card
    assert 'childEditingLocked' not in ''.join(_text(QML / family) for family in FAMILIES)
    assert 'property bool customLayoutInputBlocked' in widget
    # The glyph may repaint when toggled, but may not mutate the shared
    # geometry/session or spawn a second model lifecycle owner.
    repaint = editor.split('function onChildEditingLockedChanged()', 1)[1].split('}', 1)[0]
    assert 'childEditLockShackle.requestPaint()' in repaint
    assert 'sessionModel' not in repaint and 'syncChildRequirement' not in repaint


def test_dense_models_do_not_scan_saved_child_tuples_to_control_paint() -> None:
    for module in ('abandonment_issues', 'achievement_pulse', 'friend_pulse'):
        source = _text(ROOT / 'rendering' / 'quick' / 'widgets' / (module + '.py'))
        assert 'customChildPaintContainmentActive' not in source


def test_media_volume_is_bounded_by_accessory_not_by_card_or_canonical_height() -> None:
    media = _text(QML / 'MediaPresentation.qml')
    track = media.split('id: appVolumeTrack', 1)[1]
    assert 'readonly property real requestedTrackY:' in track
    assert 'customVolumeYOffset' in track
    assert 'y: Math.max(0.0, Math.min(requestedTrackY, Math.max(0.0, parent.height - height)))' in track
    assert 'readonly property real requestedTrackX:' in track
    assert 'x: Math.max(0.0, Math.min(requestedTrackX, Math.max(0.0, parent.width - width)))' in track
    assert 'customEditPlacementCompensationX: x - requestedTrackX' in track
    assert 'customEditPlacementCompensationY: y - requestedTrackY' in track
    assert 'readonly property real requestedTrackY:' in track
    assert 'height: mediaRoot.customVolumeTrackHeight' in track
    slider = media.split('id: appVolumeSlider', 1)[1].split('id: appVolumeTrack', 1)[0]
    assert 'clip: true' in slider
    assert 'accessoryContent:' in media and 'accessoryExtent: volumeAccessoryExtent' in media


def test_wheel_from_child_body_and_resize_handles_uses_parent_owner_once() -> None:
    editor = _text(QML / 'CustomLayoutOverlay.qml')
    assert editor.count('function resizeParentByWheel(deltaY)') == 1
    helper = editor.split('function resizeParentByWheel(deltaY)', 1)[1].split('\n            MouseArea {', 1)[0]
    assert 'editFrame.syncChildRequirementNow()' not in helper
    assert 'sessionModel.resizeWheel(' in helper
    assert editor.count('wheel.accepted = editFrame.resizeParentByWheel(wheel.angleDelta.y)') == 5
    # The same owner services parent, child body/edge/corner, and lock glyph wheel.
    assert editor.count('sessionModel.resizeWheel(') == 1


def test_clock_keeps_special_variant_font_payload_not_an_unreviewed_mode_migration() -> None:
    source = _text(QML / 'ClockPresentation.qml')
    descriptors = _text(ROOT / 'rendering' / 'widget_descriptors.py')
    for clock in ('clock', 'clock2', 'clock3'):
        assert f'widget_id="{clock}"' in descriptors or f'identity="{clock}"' in descriptors or f'"{clock}"' in descriptors
    assert descriptors.count('custom_layout_resize_mode="clock_font"') == 3
    assert 'uniformScaleTransform: true' not in source
    assert '"centeredResize": true' in source


def test_parent_boundary_handles_keep_priority_over_selected_child_overlays() -> None:
    editor = _text(QML / 'CustomLayoutOverlay.qml')
    parent_corner = editor.split('objectName: "customLayoutResize-"', 1)[1].split('MouseArea {', 1)[0]
    parent_edge = editor.split('objectName: "customLayoutViewportEdge-"', 1)[1].split('MouseArea {', 1)[0]
    child = editor.split('id: childRoleLoader', 1)[1].split('sourceComponent:', 1)[0]
    assert 'z: 70' in parent_corner
    assert 'z: 65' in parent_edge
    assert 'z: 60' in child
    assert 'sessionModel.beginResize(' in editor  # parent corner/edge use one owner


def test_clock_payload_ratio_scales_intrinsic_footer_without_changing_owner() -> None:
    model = _text(ROOT / 'rendering' / 'quick' / 'widgets' / 'clock.py')
    analogue = _text(QML / 'ClockAnalogueFace.qml')
    digital = _text(QML / 'ClockDigitalFace.qml')
    clock = _text(QML / 'ClockPresentation.qml')
    assert 'def fontResizeFactor(self) -> float:' in model
    assert 'def update_authored_font_reference(self, font_size: int) -> None:' in model
    assert 'self._model.update_authored_font_reference(config.font_size)' in model
    assert 'fontResizeFactor: clockModel.fontResizeFactor' in analogue
    assert 'fontResizeFactor: clockModel.fontResizeFactor' in digital
    for face in (analogue, digital):
        assert face.count('font.pointSize: ' ) >= 2
        assert 'calendarFontSize * ' in face
        # Unlike the independent Settings calendar font, secondaryFontSize
        # already derives from the resized primary font. No second factor.
        assert 'font.pointSize: ' + ('analogueFace' if face is analogue else 'digitalFace') + '.clockModel.secondaryFontSize\n' in face
        assert 'font.pointSize: ' + ('analogueFace' if face is analogue else 'digitalFace') + '.clockModel.secondaryFontSize * ' not in face
        assert 'spacing: 4.0 * ' in face
        assert 'clockModel.separatorThickness * ' in face
    assert 'footerHeight:' in analogue and '* fontResizeFactor' in analogue
    assert 'Math.max(18.0 * fontResizeFactor, clockModel.secondaryFontSize * 1.4)' in analogue
    assert 'uniformScaleTransform: true' not in clock
    assert 'custom_layout_resize_mode="clock_font"' in _text(ROOT / 'rendering' / 'widget_descriptors.py')


def test_reset_adjacent_lock_has_fixed_circle_small_mark_and_top_chrome_priority() -> None:
    editor = _text(QML / 'CustomLayoutOverlay.qml')
    def section(control_id: str, after: str) -> str:
        return editor.split('id: ' + control_id, 1)[1].split(after, 1)[0]

    lock = section('childEditLockControl', 'id: parentGlyphControlWedge')
    reset = section('restoreSizeControl', 'id: childEditLockControl')
    close = section('closeControl', 'id: rotateContentControl')
    child = section('childRoleLoader', 'sourceComponent:')
    corner = editor.split('objectName: "customLayoutResize-"', 1)[1].split('MouseArea {', 1)[0]
    edge = editor.split('objectName: "customLayoutViewportEdge-"', 1)[1].split('MouseArea {', 1)[0]
    # The 22px ring/hitbox does not shrink with the icon.
    assert 'width: 22' in lock and 'height: 22' in lock
    assert 'scale: 0.9' in lock.split('id: childEditLockMark', 1)[1]
    assert 'x: restoreSizeControl.visible' in lock
    assert 'restoreSizeControl.x + restoreSizeControl.width + 6' in lock
    assert 'y: restoreSizeControl.y' in lock
    assert 'editFrame.parentGlyphControlsOpacity' in lock
    assert 'z: 121' in lock and 'z: 120' in reset and 'z: 120' in close
    assert 'z: 60' in child and 'z: 70' in corner and 'z: 65' in edge
    # Layout and always-on clipping must not acquire a dependency on edit chrome.
    assert 'childEditingLocked' not in _text(QML / 'OverlayCard.qml')
    assert 'childEditingLocked' not in _text(QML / 'OverlayWidget.qml')
