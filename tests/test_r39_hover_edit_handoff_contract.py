"""R39 Qt-free contracts for one-owner hover glyph routing and the lock."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def source(file):
    return (ROOT / file).read_text(encoding='utf-8')


def test_hover_glyphs_require_existing_interaction_admission():
    ordinary = source('rendering/quick/qml/OverlayWidget.qml')
    visualizer = source('rendering/quick/qml/VisualizerPresentation.qml')
    glue = source('rendering/quick/scene_controller.py')
    manager = source('engine/display_manager.py')
    assert 'hoverEditGlyphRequested(action)' in ordinary
    assert 'hoverEditGlyphRequested(action)' in visualizer
    assert 'not (state.interaction_mode_enabled or state.ctrl_held)' in glue
    assert 'not state.always_show_glyphs' in glue
    assert 'not (state.interaction_mode_enabled or state.ctrl_held)' in manager
    assert 'self._start_quick_custom_layout_session()' in manager
    assert 'session.select_item(target)' in manager
    assert 'model.closeItem(row)' in manager
    assert 'model.restoreSize(row)' in manager
    assert 'model.rotateContent(row)' in manager
    assert 'model.requestToggleChildEditLockForWidget(widget_id)' in manager


def test_lock_is_visible_on_hover_without_parent_selection():
    edit = source('rendering/quick/qml/CustomLayoutOverlay.qml')
    lock = edit.split('id: childEditLockControl', 1)[1].split('id: childEditLockMark', 1)[0]
    assert 'visible: editFrame.hasPresentationItem' in lock
    assert 'selectedForChildEdit' not in lock
    assert 'parentGlyphControlsOpacity' in lock
    assert 'id: editChromeHover' in edit
    assert 'duration: editChromeHover.hovered ? 700 : 1200' in edit
    assert 'toggleChildEditLockForWidget(widgetId)' in edit
    model = source('rendering/quick/custom_layout_overlay.py')
    assert 'toggleChildEditLockForWidgetRequested = Signal(str)' in model
    assert 'self.toggleChildEditLockForWidgetRequested.emit(widget_id)' in model


def test_shared_glyph_has_no_polling_and_edit_hide_wedge_stays_edit_only():
    glyph = source('rendering/quick/qml/WidgetHoverEditGlyphs.qml')
    assert 'duration: chrome.hovered ? 700 : 1200' in glyph
    assert 'chrome.canLock' in glyph
    assert 'chrome.actionRequested(String(actionKind))' in glyph
    assert 'model: ["lock", "restore", "rotate", "close"]' in glyph
    assert 'objectName: "hoverEditGlyph-" + actionKind' in glyph
    assert 'Timer {' not in glyph
    assert 'FrameAnimation' not in glyph
    assert 'parentGlyphControlsHidden' not in glyph
    assert 'parentGlyphControlWedge' in source('rendering/quick/qml/CustomLayoutOverlay.qml')


def test_builds_include_shared_glyph_and_ordinary_capabilities_come_from_descriptor():
    assert 'WidgetHoverEditGlyphs.qml' in source('tools/build_layout.ps1')
    assert 'WidgetHoverEditGlyphs.qml' in source('tools/build_runner.py')
    # The scene controller owns descriptor lookup; the presentation-only host
    # projects the injected capability tuple and never resolves descriptors.
    scene = source('rendering/quick/scene_controller.py')
    assert 'descriptor.supports_layout_edit_mode' in scene
    assert 'descriptor.requires_size_reset_affordance' in scene
    host = source('rendering/quick/widgets/host.py')
    assert 'get_widget_runtime_descriptor' not in host
    assert 'self._glyph_capabilities(' in host
