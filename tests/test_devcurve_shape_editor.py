from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from ui.tabs.media.devcurve_shape_editor import DevCurveShapeEditor

_LAYERS = ("bass", "vocals", "mids", "transients")
_DEFAULT_LAYER_NODES = {src: [[0.0, 0.5], [1.0, 0.5]] for src in _LAYERS}
_DEFAULT_LAYER_STRENGTHS = {src: 0.25 for src in _LAYERS}


def _make_editor(*, mirrored: bool = False) -> DevCurveShapeEditor:
    """Build the editor with the per-layer defaults its ctor now requires."""
    return DevCurveShapeEditor(
        parent=None,
        mirrored=mirrored,
        default_layer_nodes=_DEFAULT_LAYER_NODES,
        default_layer_strengths=_DEFAULT_LAYER_STRENGTHS,
    )


@pytest.mark.qt
def test_devcurve_soft_snap_pulls_near_grid_without_hard_lock(qt_app):
    editor = _make_editor()
    editor.resize(640, 320)
    qt_app.processEvents()
    rect = editor._edit_rect()
    x_guide = rect.left() + rect.width() * 0.25
    y_guide = rect.bottom() - rect.height() * 0.5
    px = x_guide + 4.0
    py = y_guide + 4.0

    snapped_x, snapped_y = editor._apply_soft_snap(px, py)

    assert abs(snapped_x - x_guide) < abs(px - x_guide)
    assert abs(snapped_y - y_guide) < abs(py - y_guide)
    assert snapped_x != pytest.approx(x_guide)
    assert snapped_y != pytest.approx(y_guide)


@pytest.mark.qt
def test_devcurve_soft_snap_does_not_pull_outside_threshold(qt_app):
    editor = _make_editor()
    editor.resize(640, 320)
    qt_app.processEvents()
    rect = editor._edit_rect()
    x_guide = rect.left() + rect.width() * 0.25
    y_guide = rect.bottom() - rect.height() * 0.5
    px = x_guide + 31.0
    py = y_guide + 31.0

    snapped_x, snapped_y = editor._apply_soft_snap(px, py)

    assert snapped_x == pytest.approx(px)
    assert snapped_y == pytest.approx(py)


@pytest.mark.qt
def test_devcurve_lane_drag_path_does_not_use_soft_snap(qt_app):
    editor = _make_editor()
    editor.resize(640, 320)
    qt_app.processEvents()
    editor._lane_drag_index = 0

    def _fail(*_args):
        raise AssertionError("lane drag must not call node snap assist")

    editor._apply_soft_snap = _fail  # type: ignore[method-assign]
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(200.0, 200.0),
        QPointF(200.0, 200.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    editor.mouseMoveEvent(event)
