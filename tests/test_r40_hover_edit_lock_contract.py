"""Minimal Qt-free guards for one edit-glyph owner and deferred Lock handoff.

The glyph's vector strokes and fade durations are subjective, not contracts.
"""
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "rendering/quick/qml"


def test_parent_glyph_opacity_has_one_behavior_owner():
    source = (QML / "CustomLayoutOverlay.qml").read_text(encoding="utf-8")
    assert source.count("Behavior on parentGlyphControlsOpacity") == 1


def test_lock_handoff_waits_for_real_delegate_without_timer():
    source = (QML / "CustomLayoutOverlay.qml").read_text(encoding="utf-8")
    for term in (
        'property string pendingChildLockWidgetId: ""',
        'property var pendingChildLockModel: null',
        'pendingChildLockModel !== sessionModel',
        'onSessionModelChanged: clearPendingChildLock()',
        'onEditActiveChanged: if (!editActive) clearPendingChildLock()',
        'onHasPresentationItemChanged: customLayoutOverlay.deliverPendingChildLock(editFrame)',
        'frame.toggleChildEditLock()',
        'clearPendingChildLock() // one-shot',
    ):
        assert term in source, term
    assert "Timer {" not in source


def test_ordinary_and_visualizer_glyph_rows_use_one_component():
    for root in ("OverlayWidget.qml", "VisualizerPresentation.qml"):
        assert 'sourceComponent: WidgetHoverEditGlyphs {' in (QML / root).read_text(encoding="utf-8")
    shared = (QML / "WidgetHoverEditGlyphs.qml").read_text(encoding="utf-8")
    assert 'visible: actionKind === "close"' in shared
