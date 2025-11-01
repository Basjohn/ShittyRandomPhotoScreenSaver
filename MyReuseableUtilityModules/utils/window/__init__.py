"""Window utilities for behavior management and monitor detection."""

from .behavior import (
    WindowBehaviorManager,
    DragState,
    SnapEdge,
    apply_snap,
    get_resize_edge_for_pos,
    get_cursor_for_edge,
    DEFAULT_SNAP_DISTANCE,
    DEFAULT_RESIZE_MARGIN,
    MIN_WINDOW_SIZE
)

__all__ = [
    'WindowBehaviorManager',
    'DragState',
    'SnapEdge',
    'apply_snap',
    'get_resize_edge_for_pos',
    'get_cursor_for_edge',
    'DEFAULT_SNAP_DISTANCE',
    'DEFAULT_RESIZE_MARGIN',
    'MIN_WINDOW_SIZE'
]
