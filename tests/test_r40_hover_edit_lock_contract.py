"""R40 Qt-free regression: event-ordered Lock, unique fade and hover layout."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def test_edit_opacity_property_has_exactly_one_behavior():
    source = (QML / "CustomLayoutOverlay.qml").read_text(encoding="utf-8")
    assert source.count("Behavior on parentGlyphControlsOpacity") == 1
    assert "duration: editChromeHover.hovered ? 700 : 1200" in source


def test_lock_handoff_deferred_until_real_delegate_ready_without_timer():
    source = (QML / "CustomLayoutOverlay.qml").read_text(encoding="utf-8")
    for term in (
        'property string pendingChildLockWidgetId: ""',
        'property var pendingChildLockModel: null',
        'pendingChildLockModel !== sessionModel',
        'onSessionModelChanged: clearPendingChildLock()',
        'onEditActiveChanged: if (!editActive) clearPendingChildLock()',
        'onItemAdded: function(index, item)',
        'onHasPresentationItemChanged: customLayoutOverlay.deliverPendingChildLock(editFrame)',
        'frame.toggleChildEditLock()',
        'clearPendingChildLock() // one-shot',
    ):
        assert term in source, term
    assert 'Timer {' not in source


def test_ordinary_and_visualizer_glyph_row_use_same_bottom_left_layout_and_x_is_larger():
    shared = (QML / "WidgetHoverEditGlyphs.qml").read_text(encoding="utf-8")
    assert 'anchors.left: parent.left' in shared
    assert 'anchors.bottom: parent.bottom' in shared
    assert 'anchors.top: parent.top' not in shared
    assert 'anchors.right: parent.right' not in shared
    # Stable string delegates and an accurately centred vector X. The artwork
    # shrinks 10% by operator request; its 24px button and hitbox do not change.
    assert 'visible: actionKind === "close"' in shared
    assert 'ctx.moveTo(5.14, 5.14)' in shared
    assert 'ctx.lineTo(14.86, 14.86)' in shared
    assert 'ctx.lineWidth = 2.3' in shared
    assert 'width: visible ? 24 : 0' in shared
    assert 'height: 24' in shared
    for root in ('OverlayWidget.qml', 'VisualizerPresentation.qml'):
        assert 'sourceComponent: WidgetHoverEditGlyphs {' in (QML / root).read_text(encoding='utf-8')
