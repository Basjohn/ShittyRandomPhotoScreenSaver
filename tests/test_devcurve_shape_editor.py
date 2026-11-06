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


def _right_click(editor, point) -> None:
    event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, point, point, Qt.MouseButton.RightButton,
                        Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    editor.mousePressEvent(event)


def _advance(nodes):
    """One DevCurve step with ``nodes`` on every layer (the production frame runtime's own validation)."""
    from core.settings.default_contract import require_canonical_default
    from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
    from widgets.spotify_visualizer.render_state import VisualizerEnergyState, VisualizerTransientState
    from widgets.spotify_visualizer.tick_pipeline import _devcurve_parameter_snapshot
    defaults = require_canonical_default("widgets.spotify_visualizer")

    class Host:
        def __getattr__(self, name):
            return defaults[name[1:]]
    return DevCurveFrameRuntime().advance(
        now_ts=1.0, runtime_generation=0, engine_generation=0, activation_id=0, source_generation=0,
        source_activation_id=0, source_timestamp=1.0, playing=True, energy=VisualizerEnergyState(),
        transient=VisualizerTransientState(), musical_level=(8.0, 1.0), musical_intensity=0.5,
        layer_shape_nodes={src: nodes for src in _LAYERS}, parameters=_devcurve_parameter_snapshot(Host()))


@pytest.mark.qt
def test_right_click_keeps_the_two_nodes_the_devcurve_solver_needs(qt_app):
    """Removing nodes stops at two, which the production runtime accepts; one node (what the editor used to allow)
    is refused by the runtime, so a saved one-node layer stopped DevCurve's step (negative control)."""
    editor = _make_editor()
    editor.resize(640, 320)
    qt_app.processEvents()
    editor.set_nodes([[0.0, 0.3], [0.5, 0.7], [1.0, 0.4]])
    for _ in range(4):
        nx, ny = editor.get_nodes()[0]
        _right_click(editor, editor._node_to_pixel(nx, ny))
    nodes = editor.get_nodes()
    assert len(nodes) == 2
    assert _advance(nodes) is not None
    with pytest.raises(ValueError):
        _advance(nodes[:1])
