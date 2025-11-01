"""
Window Behavior Management Module

This module provides a unified, centralized interface for all window behavior
including dragging, resizing, snapping, cursor management, and window management
operations. It serves as the single source of truth for window behavior throughout
the application.
"""

import json
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Callable, Dict, Any, Type, TypeVar

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QObject, Signal, QSettings, QAbstractNativeEventFilter, QCoreApplication
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QGuiApplication

from core.logging import get_logger
from utils.window.monitors import get_physical_work_area_at, get_physical_monitor_rect_at
from core.threading import ThreadManager

T = TypeVar('T', bound='WindowState')

# Windows-specific imports for native window handling
if sys.platform == 'win32':
    from ctypes import POINTER, cast, Structure
    from ctypes.wintypes import HWND, LPARAM, WPARAM, UINT, DWORD, POINT, RECT

    class MSG(Structure):
        _fields_ = [
            ("hwnd", HWND),
            ("message", UINT),
            ("wParam", WPARAM),
            ("lParam", LPARAM),
            ("time", DWORD),
            ("pt", POINT),
        ]

    WM_MOVING = 0x0216

    class _WinBoundsFilter(QAbstractNativeEventFilter):
        def __init__(self, logger, target_hwnd_provider, allow_overlap_provider=None, is_custom_drag_provider=None):
            super().__init__()
            self._logger = logger
            self._get_target_hwnd = target_hwnd_provider
            # Callable returning bool; when True, clamp to full monitor geometry
            # in physical pixels, otherwise clamp to work area (taskbar-aware).
            self._allow_overlap_provider = allow_overlap_provider
            # Callable returning bool; when True, indicates our own custom drag is active
            # and native clamping should be skipped to avoid conflicts.
            self._is_custom_drag_provider = is_custom_drag_provider

        def nativeEventFilter(self, eventType, message):
            # Only process standard Windows messages
            if eventType != b"windows_generic_MSG":
                return False, 0
            try:
                msg = cast(message, POINTER(MSG)).contents
                if msg.message == WM_MOVING:
                    target = self._get_target_hwnd()
                    if not target or msg.hwnd != target:
                        return False, 0
                    # If our custom drag logic is active, skip native clamping entirely
                    try:
                        if callable(self._is_custom_drag_provider) and bool(self._is_custom_drag_provider()):
                            return False, 0
                    except Exception:
                        pass
                    # lParam points to a RECT in screen coordinates
                    rect_ptr = cast(msg.lParam, POINTER(RECT))
                    rect = rect_ptr.contents
                    # Determine physical work area directly via Win32 using RECT center (physical coords)
                    cx = (rect.left + rect.right) // 2
                    cy = (rect.top + rect.bottom) // 2
                    # Choose clamp rect based on drag intent
                    allow_overlap = False
                    try:
                        if callable(self._allow_overlap_provider):
                            allow_overlap = bool(self._allow_overlap_provider())
                    except Exception:
                        allow_overlap = False

                    if allow_overlap:
                        work = get_physical_monitor_rect_at(QPoint(int(cx), int(cy)))
                    else:
                        work = get_physical_work_area_at(QPoint(int(cx), int(cy)))
                    wl, wt, ww, wh = work.left(), work.top(), work.width(), work.height()
                    width = rect.right - rect.left
                    height = rect.bottom - rect.top
                    # Clamp top-left within work area (physical coords)
                    new_left = max(wl, min(rect.left, wl + ww - width))
                    new_top = max(wt, min(rect.top, wt + wh - height))

                    # Write back to RECT
                    rect.left = new_left
                    rect.top = new_top
                    rect.right = new_left + width
                    rect.bottom = new_top + height
                    # Do not consume the event; just modify the rect
                    return False, 0
            except Exception:
                # Never break the event loop on errors
                return False, 0
            return False, 0

# Configuration constants
# Slightly stronger default snapping per user feedback
DEFAULT_SNAP_DISTANCE = 40
DEFAULT_RESIZE_MARGIN = 12  # Reduced margin to make resize handles only show near edges/corners
MIN_WINDOW_SIZE = QSize(100, 50)



@dataclass
class SnapEdge:
    """Represents a snap edge with position and orientation."""
    position: QPoint
    orientation: str  # 'left', 'right', 'top', 'bottom'
    monitor_index: int


@dataclass
class DragState:
    """Represents the drag state for a widget."""
    is_dragging: bool = False
    is_resizing: bool = False
    drag_start_position: Optional[QPoint] = None
    drag_global_start: Optional[QPoint] = None
    resize_edge: Optional[str] = None
    cursor_overridden: bool = False
    # When True, native bounds filter will allow overlapping the taskbar by
    # clamping to full monitor rect (physical), preventing bounce.
    allow_taskbar_overlap: bool = False


def apply_snap(
    pos: QPoint, 
    size: QSize, 
    snap_distance: int = DEFAULT_SNAP_DISTANCE,
    screen_rects: Optional[List[QRect]] = None
) -> QPoint:
    """
    Apply intelligent snapping with improved multi-monitor support.
    
    Args:
        pos: Current window position
        size: Window size
        snap_distance: Maximum distance for snapping (in pixels)
        screen_rects: List of screen rectangles to snap to. If None, uses all screens.
                     Each rectangle should be in global coordinates.
        
    Returns:
        QPoint: New position after snapping
    """
    # Get all screens if none provided
    if screen_rects is None:
        screens = QApplication.screens()
        screen_rects = [screen.availableGeometry() for screen in screens]
    
    if not screen_rects:
        return pos  # No screens available, return original position
    
    # Create window rectangle
    window_rect = QRect(pos, size)
    snap_points = []
    
    for i, rect in enumerate(screen_rects):
        # Convert to QRect if it's a QRectF
        if hasattr(rect, 'toRect'):
            rect = rect.toRect()
        
        # Only consider screens that are near the window
        if not (window_rect.intersects(rect) or 
               window_rect.adjusted(-snap_distance, -snap_distance, snap_distance, snap_distance).intersects(rect)):
            continue
            
        # Add edges of the screen
        snap_points.extend([
            # Left edge (top to bottom)
            SnapEdge(QPoint(rect.left(), rect.top()), 'left', i),
            SnapEdge(QPoint(rect.left(), rect.center().y()), 'left', i),
            SnapEdge(QPoint(rect.left(), rect.bottom()), 'left', i),
            # Right edge (top to bottom)
            SnapEdge(QPoint(rect.right(), rect.top()), 'right', i),
            SnapEdge(QPoint(rect.right(), rect.center().y()), 'right', i),
            SnapEdge(QPoint(rect.right(), rect.bottom()), 'right', i),
            # Top edge (left to right)
            SnapEdge(QPoint(rect.left(), rect.top()), 'top', i),
            SnapEdge(QPoint(rect.center().x(), rect.top()), 'top', i),
            SnapEdge(QPoint(rect.right(), rect.top()), 'top', i),
            # Bottom edge (left to right)
            SnapEdge(QPoint(rect.left(), rect.bottom()), 'bottom', i),
            SnapEdge(QPoint(rect.center().x(), rect.bottom()), 'bottom', i),
            SnapEdge(QPoint(rect.right(), rect.bottom()), 'bottom', i),
            # Center (both axes)
            SnapEdge(rect.center(), 'center', i)
        ])
    
    # Calculate window edges and center
    window_rect = QRect(pos, size)
    window_edges = {
        'left': window_rect.left(),
        'right': window_rect.right(),
        'top': window_rect.top(),
        'bottom': window_rect.bottom(),
        'center_x': window_rect.center().x(),
        'center_y': window_rect.center().y()
    }
    
    # Find closest snap point within distance
    min_dist = float('inf')
    best_snap = None
    snap_axis = None
    
    for snap in snap_points:
        # Get the screen this snap point belongs to
        
        # Calculate distance based on orientation
        if snap.orientation in ['left', 'right']:
            # For left/right edges, snap the window's edge to the snap point
            if snap.orientation == 'left':
                dist = abs(window_edges['left'] - snap.position.x())
                # Only snap if moving towards the edge
                if pos.x() < snap.position.x() and dist > 5:  # 5px threshold to prevent jitter
                    continue
            else:  # right
                dist = abs(window_edges['right'] - snap.position.x())
                # Only snap if moving towards the edge
                if pos.x() + size.width() > snap.position.x() and dist > 5:
                    continue
            
            if dist < min_dist and dist <= snap_distance:
                min_dist = dist
                best_snap = snap
                snap_axis = 'x'
                
        elif snap.orientation in ['top', 'bottom']:
            # For top/bottom edges, snap the window's edge to the snap point
            if snap.orientation == 'top':
                dist = abs(window_edges['top'] - snap.position.y())
                # Improved top edge snapping - don't use directional constraint
                # This allows snapping regardless of approach direction
            else:  # bottom
                dist = abs(window_edges['bottom'] - snap.position.y())
                # Improved bottom edge snapping - don't use directional constraint
                # This allows snapping regardless of approach direction
            
            if dist < min_dist and dist <= snap_distance:
                min_dist = dist
                best_snap = snap
                snap_axis = 'y'
                
        elif snap.orientation == 'center':
            # For center, snap the window's center to the snap point
            dist_x = abs(window_edges['center_x'] - snap.position.x())
            dist_y = abs(window_edges['center_y'] - snap.position.y())
            
            # Only snap if both distances are within range
            if dist_x <= snap_distance and dist_y <= snap_distance:
                total_dist = dist_x + dist_y
                if total_dist < min_dist:
                    min_dist = total_dist
                    best_snap = snap
                    snap_axis = 'both'
    
    # Apply snap if found
    if best_snap is not None:
        new_pos = QPoint(pos)
        
        if snap_axis == 'x' or snap_axis == 'both':
            if best_snap.orientation == 'left':
                new_pos.setX(best_snap.position.x())
            elif best_snap.orientation == 'right':
                new_pos.setX(best_snap.position.x() - size.width())
            elif best_snap.orientation == 'center':
                new_pos.setX(best_snap.position.x() - size.width() // 2)
        
        if snap_axis == 'y' or snap_axis == 'both':
            if best_snap.orientation == 'top':
                new_pos.setY(best_snap.position.y())
            elif best_snap.orientation == 'bottom':
                new_pos.setY(best_snap.position.y() - size.height())
            elif best_snap.orientation == 'center':
                new_pos.setY(best_snap.position.y() - size.height() // 2)
        
        return new_pos
    
    # No snap found, return original position
    return pos


def get_resize_edge_for_pos(
    pos: QPoint, 
    widget, 
    margin: int = DEFAULT_RESIZE_MARGIN, 
    restrict_to_bottom_right: bool = False
) -> Optional[str]:
    """
    Determine resize edge with improved corner detection.
    Optionally restrict to only the bottom right corner (for SettingsPanel, etc).
    
    Args:
        pos: Mouse position relative to the widget
        widget: Widget to check resize edge for
        margin: Margin from edge for resize detection (in pixels)
        restrict_to_bottom_right: Whether to restrict to bottom right corner only
        
    Returns:
        Optional[str]: The edge being hovered ('bottom_right') or None
    """
    # Use standardized resize margin; legacy border overlay dependency removed
    
    width = widget.width()
    height = widget.height()
    
    # Restrict to bottom-right corner only if requested
    if restrict_to_bottom_right:
        if pos.x() > width - margin and pos.y() > height - margin:
            return 'bottom_right'
        return None
    
    # Default: all corners/edges
    if pos.x() < margin and pos.y() < margin:
        return 'top_left'
    elif pos.x() > width - margin and pos.y() < margin:
        return 'top_right'
    elif pos.x() < margin and pos.y() > height - margin:
        return 'bottom_left'
    elif pos.x() > width - margin and pos.y() > height - margin:
        return 'bottom_right'
    if pos.x() < margin:
        return 'left'
    elif pos.x() > width - margin:
        return 'right'
    elif pos.y() < margin:
        return 'top'
    elif pos.y() > height - margin:
        return 'bottom'
    return None


def get_cursor_for_edge(edge: Optional[str]) -> Optional[Qt.CursorShape]:
    """
    Get the appropriate cursor shape for a window edge or corner.
    
    This function maps edge/corner identifiers to their corresponding cursor shapes
    to provide visual feedback during window resizing operations.
    
    Args:
        edge: Edge/corner identifier from get_resize_edge_for_pos, which can be one of:
              - 'left': Left edge
              - 'right': Right edge
              - 'top': Top edge
              - 'bottom': Bottom edge
              - 'top_left': Top-left corner
              - 'top_right': Top-right corner
              - 'bottom_left': Bottom-left corner
              - 'bottom_right': Bottom-right corner
              
    Returns:
        Qt.CursorShape: The appropriate cursor shape for the specified edge/corner,
                      or None if the edge is invalid/None
    """
    if not edge:
        return None
    
    # Map edge/corner identifiers to their corresponding cursor shapes
    cursor_map = {
        # Horizontal edges
        'left': Qt.SizeHorCursor,
        'right': Qt.SizeHorCursor,
        # Vertical edges
        'top': Qt.SizeVerCursor,
        'bottom': Qt.SizeVerCursor,
        # Diagonal corners
        'top_left': Qt.SizeFDiagCursor,
        'bottom_right': Qt.SizeFDiagCursor,
        # Reverse diagonal corners
        'top_right': Qt.SizeBDiagCursor,
        'bottom_left': Qt.SizeBDiagCursor
    }
    
    return cursor_map.get(edge)


def _apply_resize_delta(geometry: QRect, edge: str, delta: QPoint, min_size: QSize) -> QRect:
    """
    Apply resize delta to geometry with minimum size enforcement.
    
    Args:
        geometry: Current window geometry
        edge: Edge being resized
        delta: Mouse movement delta
        min_size: Minimum window size
        
    Returns:
        QRect: New geometry after resize
    """
    new_geo = QRect(geometry)
    
    # Apply delta based on edge
    if edge in ['left', 'top_left', 'bottom_left']:
        # Left edge - move left edge, constrain width
        new_left = geometry.left() + delta.x()
        new_width = geometry.right() - new_left
        if new_width >= min_size.width():
            new_geo.setLeft(new_left)
    
    if edge in ['right', 'top_right', 'bottom_right']:
        # Right edge - adjust width
        new_width = geometry.width() + delta.x()
        if new_width >= min_size.width():
            new_geo.setWidth(new_width)
    
    if edge in ['top', 'top_left', 'top_right']:
        # Top edge - move top edge, constrain height
        new_top = geometry.top() + delta.y()
        new_height = geometry.bottom() - new_top
        if new_height >= min_size.height():
            new_geo.setTop(new_top)
    
    if edge in ['bottom', 'bottom_left', 'bottom_right']:
        # Bottom edge - adjust height
        new_height = geometry.height() + delta.y()
        if new_height >= min_size.height():
            new_geo.setHeight(new_height)
    
    return new_geo


def _update_cursor_for_position(widget: QWidget, pos: QPoint, resize_margin: int = DEFAULT_RESIZE_MARGIN) -> None:
    """
    Update cursor based on position over the widget.
    
    Args:
        widget: Widget to update cursor for
        pos: Current mouse position
        resize_margin: Margin from edge for resize detection
    """
    edge = get_resize_edge_for_pos(pos, widget, resize_margin)
    cursor = get_cursor_for_edge(edge)
    
    if cursor is not None:
        widget.setCursor(cursor)
    else:
        widget.unsetCursor()


def _handle_drag(widget: QWidget, global_pos: QPoint) -> None:
    """
    Handle window dragging.
    
    Args:
        widget: Widget being dragged
        global_pos: Current global mouse position
    """
    # Get drag state
    state = getattr(widget, '_window_behavior_state', None)
    if not state or not isinstance(state, DragState) or not state.is_dragging:
        return
    
    # Calculate delta and apply
    delta = global_pos - state.drag_global_start
    new_pos = widget.pos() + delta
    
    # Apply snapping
    screens = QApplication.screens()
    screen_rects = [screen.availableGeometry() for screen in screens]
    snapped_pos = apply_snap(new_pos, widget.size(), DEFAULT_SNAP_DISTANCE, screen_rects)

    # Enforce live monitor bounds during manual drag (logical coordinates)
    try:
        # Determine the target screen based on the window's center at the snapped position
        future_rect = QRect(snapped_pos, widget.size())
        center = future_rect.center()
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is not None:
            work = screen.availableGeometry()
            bx = min(max(future_rect.x(), work.left()), work.right() - future_rect.width())
            by = min(max(future_rect.y(), work.top()), work.bottom() - future_rect.height())
            bounded_pos = QPoint(bx, by)
        else:
            bounded_pos = snapped_pos
    except Exception:
        bounded_pos = snapped_pos

    # Move window
    widget.move(bounded_pos)
    
    # Update global start position for next move
    state.drag_global_start = global_pos


def _handle_resize(widget: QWidget, global_pos: QPoint) -> None:
    """
    Handle window resizing.
    
    Args:
        widget: Widget being resized
        global_pos: Current global mouse position
    """
    # Get resize state
    state = getattr(widget, '_window_behavior_state', None)
    if not state or not isinstance(state, DragState) or not state.is_resizing:
        return
    
    # Calculate delta
    delta = global_pos - state.drag_global_start
    
    # Get current geometry
    geo = widget.geometry()
    
    # Apply resize based on edge
    min_size = QSize(getattr(widget, 'min_width', MIN_WINDOW_SIZE.width()),
                    getattr(widget, 'min_height', MIN_WINDOW_SIZE.height()))
    
    new_geo = _apply_resize_delta(geo, state.resize_edge, delta, min_size)
    
    # Apply new geometry
    widget.setGeometry(new_geo)
    
    # Update global start position for next resize
    state.drag_global_start = global_pos


class WindowBehaviorManager:
    """Unified interface for window behavior management including drag, resize, and snap operations."""
    
    def __init__(self, widget: QWidget, min_width: int = MIN_WINDOW_SIZE.width(), min_height: int = MIN_WINDOW_SIZE.height()):
        """Initialize the window behavior manager.
        
        Args:
            widget: The widget to manage behavior for
            min_width: Minimum window width
            min_height: Minimum window height
        """
        self._widget = widget
        self._min_size = QSize(min_width, min_height)
        self._drag_state = DragState()
        self._logger = get_logger(__name__)
        # Per-instance snap distance (configurable); default to module constant
        self._snap_distance: int = int(DEFAULT_SNAP_DISTANCE)
        # Wheel batching state
        self._wheel_accum: float = 0.0
        self._pending_wheel_geo: Optional[QRect] = None
        
        # Install native Windows live-bounds filter for native dragging
        if sys.platform == 'win32':
            try:
                app = QCoreApplication.instance()
                if app is not None:
                    def _get_target_hwnd():
                        try:
                            return HWND(int(self._widget.winId()))
                        except Exception:
                            return None
                    self._win_bounds_filter = _WinBoundsFilter(
                        self._logger,
                        _get_target_hwnd,
                        allow_overlap_provider=lambda: bool(getattr(self._drag_state, 'allow_taskbar_overlap', False)),
                        is_custom_drag_provider=lambda: bool(getattr(self._drag_state, 'is_dragging', False)),
                    )
                    app.installNativeEventFilter(self._win_bounds_filter)
                    self._logger.debug("Installed Windows native bounds filter for live monitor clamping during drag")
            except Exception as e:
                self._logger.error(f"Failed to install native bounds filter: {e}")
    
    @property
    def state(self) -> DragState:
        """Get the current drag state."""
        return self._drag_state
    
    def handle_mouse_press(self, event, is_draggable_region: Callable[[QPoint], bool] = None, restrict_to_bottom_right: bool = False):
        """Handle mouse press events for dragging and resizing.
        
        Args:
            event: The mouse event
            is_draggable_region: Optional function to determine if position is draggable
            restrict_to_bottom_right: Whether to restrict resizing to bottom right corner only
        """
        # Skip processing right-click events to allow context menu handling
        if event.button() == Qt.RightButton:
            self._logger.debug("Bypassing right-click event for context menu system")
            return
            
        if event.button() != Qt.LeftButton:
            return
        
        # Reset drag state
        self._drag_state = DragState()
        
        # Get mouse position
        pos = event.position().toPoint() if hasattr(event.position(), 'toPoint') else event.pos()
        global_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()

        # Check if we're on a resize edge - with higher priority than dragging
        resize_edge = get_resize_edge_for_pos(pos, self._widget, restrict_to_bottom_right=restrict_to_bottom_right)
        
        if resize_edge:
            # Start resize operation
            self._drag_state.is_resizing = True
            self._drag_state.resize_edge = resize_edge
            self._drag_state.drag_start_position = pos
            self._drag_state.drag_global_start = global_pos
            self._logger.debug(f"Resize start: edge={resize_edge}, local={pos}, global={global_pos}")
            
            # Set appropriate cursor through cursor manager
            cursor = get_cursor_for_edge(resize_edge)
            if cursor:
                try:
                    from utils.cursor_manager import set_managed_cursor, CursorPriority
                    success = set_managed_cursor(
                        "window_behavior_resize",
                        self._widget,
                        cursor,
                        CursorPriority.WINDOW_BEHAVIOR,
                        f"resize_{resize_edge}"
                    )
                    self._drag_state.cursor_overridden = success
                except Exception as e:
                    self._logger.error(f"Failed to set resize cursor: {e}")
                    # Fallback to direct cursor setting
                    self._widget.setCursor(cursor)
                    self._drag_state.cursor_overridden = True
            # Request mouse capture through coordinator
            try:
                from utils.mouse_capture_coordinator import request_mouse_capture, MouseCapturePriority
                success = request_mouse_capture(
                    "window_behavior_resize", 
                    self._widget, 
                    MouseCapturePriority.WINDOW_BEHAVIOR,
                    f"resize_{resize_edge}"
                )
                if not success:
                    self._logger.debug("Mouse capture denied for resize operation")
            except Exception as e:
                self._logger.error(f"Failed to request mouse capture for resize: {e}")
        else:
            # Docking mode: for SECONDARY overlays, do not start a local drag; delegate group-drag to manager.
            # This applies only when not on a resize edge.
            try:
                overlay = getattr(self._widget, '_parent_overlay', None)
                if overlay is None:
                    overlay = getattr(self._widget, '_backend_overlay', None)
            except Exception:
                overlay = None
            if (not resize_edge) and (overlay and overlay.__class__.__name__ == 'DockingOverlay' and not getattr(overlay, '_is_main', False)):
                try:
                    mgr = getattr(overlay, '_manager', None)
                    if mgr is not None:
                        setattr(mgr, '_secondary_drag_active', True)
                        setattr(mgr, '_secondary_drag_global_last', global_pos)
                    # Set drag cursor via cursor manager for UX consistency
                    try:
                        from utils.cursor_manager import set_managed_cursor, CursorPriority
                        set_managed_cursor(
                            "window_behavior_drag",
                            self._widget,
                            Qt.SizeAllCursor,
                            CursorPriority.WINDOW_BEHAVIOR,
                            "dock_group_drag_secondary"
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                self._logger.debug("Docking secondary press: delegating drag to manager (no local drag)")
                return

            allowed = (is_draggable_region is None or is_draggable_region(pos))
            self._logger.debug(f"Press: local={pos}, global={global_pos}, draggable={allowed}")
        
        if (not resize_edge) and (is_draggable_region is None or is_draggable_region(pos)):
            # Start drag operation
            self._drag_state.is_dragging = True
            self._drag_state.drag_start_position = pos
            self._drag_state.drag_global_start = global_pos
            # Enable full-monitor clamping in native filter for the duration of our drag
            self._drag_state.allow_taskbar_overlap = True
            self._logger.debug(f"Drag start: local={pos}, global={global_pos}")
            
            # Set appropriate cursor for dragging through cursor manager
            try:
                from utils.cursor_manager import set_managed_cursor, CursorPriority
                success = set_managed_cursor(
                    "window_behavior_drag",
                    self._widget,
                    Qt.SizeAllCursor,
                    CursorPriority.WINDOW_BEHAVIOR,
                    "drag_operation"
                )
                self._drag_state.cursor_overridden = success
            except Exception as e:
                self._logger.error(f"Failed to set drag cursor: {e}")
                # Fallback to direct cursor setting
                self._widget.setCursor(Qt.SizeAllCursor)
                self._drag_state.cursor_overridden = True
            # Request mouse capture through coordinator
            try:
                from utils.mouse_capture_coordinator import request_mouse_capture, MouseCapturePriority
                success = request_mouse_capture(
                    "window_behavior_drag", 
                    self._widget, 
                    MouseCapturePriority.WINDOW_BEHAVIOR,
                    "drag_operation"
                )
                if not success:
                    self._logger.debug("Mouse capture denied for drag operation")
            except Exception as e:
                self._logger.error(f"Failed to request mouse capture for drag: {e}")
    
    def handle_mouse_move(self, event, restrict_to_bottom_right: bool = False):
        """Handle mouse move events for dragging and resizing.
        
        Args:
            event: The mouse event
            restrict_to_bottom_right: Whether to restrict resizing to bottom right corner only
        """
        pos = event.position().toPoint() if hasattr(event.position(), 'toPoint') else event.pos()
        global_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
        
        if self._drag_state.is_dragging:
            # Handle dragging
            self._handle_drag(global_pos)
        elif self._drag_state.is_resizing:
            # Handle resizing
            self._handle_resize(global_pos)
        else:
            # Update cursor based on position
            self._update_cursor_for_position(pos, restrict_to_bottom_right)
    
    def set_snap_distance(self, pixels: int) -> None:
        """Set the snap distance for this window behavior instance."""
        try:
            p = int(pixels)
            if p > 0:
                self._snap_distance = p
                self._logger.debug(f"WindowBehaviorManager snap distance set to {p}")
        except Exception as e:
            self._logger.debug(f"Failed to set snap distance: {e}")
    
    def handle_double_click(self, event) -> bool:
        """Handle double-click events for window behavior.
        
        Args:
            event: The mouse event
            
        Returns:
            bool: True if the event was handled, False otherwise
        """
        # Skip processing right-click double-clicks
        if event.button() == Qt.RightButton:
            self._logger.debug("Bypassing right-click double-click for context menu system")
            return False
            
        # For left-button double-clicks, do NOT handle them here
        # Let the overlay host handle quickswitch functionality
        if event.button() == Qt.LeftButton:
            self._logger.debug("Bypassing left-click double-click for quickswitch system")
            return False
            
        # Only handle other buttons if needed
        return False
    
    def handle_mouse_release(self, event):
        """Handle mouse release events.
        
        Args:
            event: The mouse event
        """
        if event.button() == Qt.LeftButton:
            # Capture current operation state before reset
            was_dragging = self._drag_state.is_dragging
            was_resizing = self._drag_state.is_resizing
            
            # Reset cursor if it was overridden through cursor manager
            if self._drag_state.cursor_overridden:
                try:
                    from utils.cursor_manager import unset_managed_cursor
                    if was_dragging:
                        unset_managed_cursor("window_behavior_drag", self._widget)
                    elif was_resizing:
                        unset_managed_cursor("window_behavior_resize", self._widget)
                except Exception as e:
                    self._logger.error(f"Failed to unset managed cursor: {e}")
                    # Fallback to direct cursor reset
                    self._widget.setCursor(Qt.ArrowCursor)

            # If we were dragging, apply snapping to the final position
            if was_dragging and not self._widget.isMaximized():
                try:
                    snapped = apply_snap(self._widget.pos(), self._widget.size(), DEFAULT_SNAP_DISTANCE)
                    if snapped != self._widget.pos():
                        self._logger.debug(f"Snap on release: from={self._widget.pos()} to={snapped}")
                        self._widget.move(snapped)
                        self._widget.update()
                except Exception:
                    # Best-effort snap; do not fail release handling
                    pass

                # After snapping, enforce monitor bounds (multi-monitor aware)
                try:
                    # Determine the screen by the window's center
                    center = self._widget.frameGeometry().center()
                    screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
                    if screen is not None:
                        full = screen.geometry()
                        geo = self._widget.frameGeometry()
                        # Clamp within FULL monitor geometry to allow overlapping the taskbar
                        new_x = min(max(geo.x(), full.left()), full.right() - geo.width())
                        new_y = min(max(geo.y(), full.top()), full.bottom() - geo.height())
                        bounded = QPoint(new_x, new_y)
                        if bounded != geo.topLeft():
                            self._logger.debug(
                                f"Bounds on release (full): from={geo.topLeft()} to={bounded} within={full}")
                            self._widget.move(bounded)
                            self._widget.update()
                except Exception:
                    # Best-effort bounds; do not fail release handling
                    pass

            # Reset drag state
            self._drag_state = DragState()
            self._logger.debug(f"Mouse release: was_dragging={was_dragging}, was_resizing={was_resizing}")
            # Release mouse capture through coordinator
            try:
                from utils.mouse_capture_coordinator import release_mouse_capture
                if was_dragging:
                    release_mouse_capture("window_behavior_drag")
                elif was_resizing:
                    release_mouse_capture("window_behavior_resize")
            except Exception as e:
                self._logger.error(f"Failed to release mouse capture: {e}")

            # If this was a delegated secondary drag, clear manager flag and cursor
            try:
                overlay = getattr(self._widget, '_parent_overlay', None)
                if overlay is None:
                    overlay = getattr(self._widget, '_backend_overlay', None)
                if overlay and overlay.__class__.__name__ == 'DockingOverlay' and not getattr(overlay, '_is_main', False):
                    mgr = getattr(overlay, '_manager', None)
                    if mgr is not None and hasattr(mgr, '_secondary_drag_active'):
                        try:
                            setattr(mgr, '_secondary_drag_active', False)
                        except Exception:
                            pass
                    try:
                        from utils.cursor_manager import unset_managed_cursor
                        unset_managed_cursor("window_behavior_drag", self._widget)
                    except Exception:
                        pass
            except Exception:
                pass

            # Opportunistic persistence for standalone overlays after drag/resize release
            try:
                overlay = getattr(self._widget, '_parent_overlay', None)
                if overlay is None:
                    overlay = getattr(self._widget, '_backend_overlay', None)
                if overlay is not None and hasattr(overlay, '_persist_current_geometry'):
                    overlay._persist_current_geometry()
            except Exception:
                pass

    # --- Qt-style event adapter methods (for widgets forwarding events) ---
    def mousePressEvent(self, event) -> None:
        """Qt adapter: forwards to handle_mouse_press."""
        # Keep default behavior: draggable anywhere except right click
        self.handle_mouse_press(event)

    def mouseMoveEvent(self, event) -> None:
        """Qt adapter: forwards to handle_mouse_move."""
        self.handle_mouse_move(event)

    def mouseReleaseEvent(self, event) -> None:
        """Qt adapter: forwards to handle_mouse_release."""
        self.handle_mouse_release(event)

    def leaveEvent(self, event) -> None:
        """Qt adapter: forwards to handle_leave."""
        self.handle_leave()

    def wheelEvent(self, event) -> None:
        """Qt adapter: forwards to handle_wheel for resize gestures."""
        # Default: no content aspect/insets; callers can use handle_wheel directly for more control
        try:
            self.handle_wheel(event)
        except AttributeError:
            # handle_wheel may be absent in older builds; ignore gracefully
            pass
    
    def handle_wheel(self, event, content_aspect: Optional[tuple[int, int]] = None, content_insets: Optional[tuple[int, int]] = None) -> None:
        """Handle wheel-based resize with batching, inner-AR preservation, and bounds clamping.
        
        Args:
            event: QWheelEvent (must provide angleDelta())
            content_aspect: Optional (w, h) to maintain inner content aspect ratio
            content_insets: Optional (ix, iy) DPI-aware per-side insets used to derive inner content rect
        """
        try:
            # Docking mode guard: if this host belongs to a secondary docking overlay,
            # do not perform host wheel-resize here. Let DockingOverlay intercept and scale the main.
            try:
                ov = getattr(self._widget, '_parent_overlay', None)
                if ov is None:
                    ov = getattr(self._widget, '_backend_overlay', None)
                # Detect DockingOverlay without importing to avoid cycles
                if ov is not None and ov.__class__.__name__ == 'DockingOverlay':
                    is_main = bool(getattr(ov, '_is_main', False))
                    if not is_main:
                        return
            except Exception:
                pass

            # Extract wheel delta (Qt: 120 units per step)
            angle = event.angleDelta() if hasattr(event, 'angleDelta') else None
            if angle is None:
                return
            raw = angle.y() if hasattr(angle, 'y') and angle.y() != 0 else (angle.x() if hasattr(angle, 'x') else 0)
            if raw == 0:
                return

            # Accumulate fractional steps for smoothness
            self._wheel_accum += float(raw) / 120.0

            # Convert steps to pixels (tuned constants per Index.md notes)
            base_step_px = 28.0
            scale = 2.0 if self._wheel_accum >= 0 else 2.1
            px_delta = self._wheel_accum * base_step_px * scale
            
            self._logger.debug(f"WHEEL_RESIZE: accum={self._wheel_accum:.3f}, px_delta={px_delta:.1f}, direction={'grow' if px_delta > 0 else 'shrink'}")

            # Aspect handling
            aspect_ratio: Optional[float] = None
            if content_aspect is not None:
                try:
                    aw, ah = content_aspect
                    if aw > 0 and ah > 0:
                        aspect_ratio = float(aw) / float(ah)
                except Exception:
                    aspect_ratio = None

            # Current geometry (use widget logical geometry for setGeometry)
            cur_geo = QRect(self._widget.geometry())

            # Build union of all monitor available geometries for clamping
            screens = QGuiApplication.screens() or []
            if screens:
                rects = [s.availableGeometry() for s in screens]
                left = min(r.left() for r in rects)
                top = min(r.top() for r in rects)
                right = max(r.right() for r in rects)
                bottom = max(r.bottom() for r in rects)
                union_rect = QRect(QPoint(left, top), QPoint(right, bottom))
            else:
                union_rect = QRect(0, 0, 9999, 9999)

            # Determine pinned edges relative to current screen work area AND full screen
            center = self._widget.frameGeometry().center()
            screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
            work = screen.availableGeometry() if screen else union_rect
            full_screen = screen.geometry() if screen else union_rect
            PIN_THRESH = 30
            pinned_left = abs(cur_geo.left() - work.left()) <= PIN_THRESH
            pinned_right = abs(cur_geo.right() - work.right()) <= PIN_THRESH
            pinned_top = abs(cur_geo.top() - work.top()) <= PIN_THRESH
            # Bottom can be pinned to either taskbar (work area) OR real screen bottom
            pinned_bottom = (abs(cur_geo.bottom() - work.bottom()) <= PIN_THRESH or 
                            abs(cur_geo.bottom() - full_screen.bottom()) <= PIN_THRESH)

            # Determine number of expanding sides per axis (1 if pinned on any side, else 2)
            width0, height0 = cur_geo.width(), cur_geo.height()
            dx = int(round(px_delta))
            sides_h = 1 if (pinned_left or pinned_right) else 2
            sides_v = 1 if (pinned_top or pinned_bottom) else 2

            # Proposed target size with strict AR preservation on INNER content when provided
            if aspect_ratio:
                ix = iy = 0
                if isinstance(content_insets, tuple) and len(content_insets) == 2:
                    ix, iy = content_insets
                    ix = max(0, int(ix))
                    iy = max(0, int(iy))

                # Current inner size after subtracting insets
                inner_w0 = max(1, width0 - 2 * ix)

                # Apply horizontal delta to inner width based on pinned sides
                proposed_inner_w = inner_w0 + sides_h * dx
                proposed_inner_w = max(1, proposed_inner_w)

                # Derive inner height from AR, then reconstruct outer size by adding insets back
                target_inner_w = proposed_inner_w
                target_inner_h = int(round(target_inner_w / aspect_ratio))

                target_w = target_inner_w + 2 * ix
                target_h = target_inner_h + 2 * iy
            else:
                # No AR: symmetric growth per expanding sides
                target_w = width0 + sides_h * dx
                target_h = height0 + sides_v * dx

            # Minimum size constraints (use manager's configured minimums)
            min_w = self._min_size.width()
            min_h = self._min_size.height()
            if aspect_ratio:
                # Enforce mins on OUTER while keeping INNER AR; adjust via inner dims and add insets back
                ix = iy = 0
                if isinstance(content_insets, tuple) and len(content_insets) == 2:
                    ix, iy = content_insets
                    ix = max(0, int(ix))
                    iy = max(0, int(iy))

                inner_w = max(1, target_w - 2 * ix)
                inner_h = max(1, target_h - 2 * iy)

                if target_w < min_w:
                    inner_w = max(1, min_w - 2 * ix)
                    inner_h = int(round(inner_w / aspect_ratio))
                if target_h < min_h:
                    inner_h = max(1, min_h - 2 * iy)
                    inner_w = int(round(inner_h * aspect_ratio))

                target_w = inner_w + 2 * ix
                target_h = inner_h + 2 * iy
            else:
                if target_w < min_w:
                    target_w = min_w
                if target_h < min_h:
                    target_h = min_h

            # Position adjustments based on pinned edges
            dw = target_w - width0
            dh = target_h - height0
            if pinned_right and not pinned_left:
                new_left = cur_geo.left() - dw
            elif pinned_left and not pinned_right:
                new_left = cur_geo.left()
            else:
                new_left = cur_geo.left() - dw // 2

            if pinned_bottom and not pinned_top:
                new_top = cur_geo.top() - dh
            elif pinned_top and not pinned_bottom:
                new_top = cur_geo.top()
            else:
                new_top = cur_geo.top() - dh // 2

            new_rect = QRect(new_left, new_top, int(target_w), int(target_h))

            # Clamp within the current monitor FULL geometry; adjust size if necessary to prevent escape
            try:
                screen_for_new = QGuiApplication.screenAt(new_rect.center()) or QGuiApplication.primaryScreen()
                full_bounds = screen_for_new.geometry() if screen_for_new else union_rect

                # If new size exceeds monitor, reduce while preserving AR/insets when provided
                if new_rect.width() > full_bounds.width() or new_rect.height() > full_bounds.height():
                    if aspect_ratio:
                        ix2 = iy2 = 0
                        if isinstance(content_insets, tuple) and len(content_insets) == 2:
                            ix2, iy2 = content_insets
                            ix2 = max(0, int(ix2))
                            iy2 = max(0, int(iy2))
                        max_outer_w = max(1, full_bounds.width())
                        max_outer_h = max(1, full_bounds.height())
                        # Compute inner limits and fit by the most constraining dimension
                        max_inner_w = max(1, max_outer_w - 2 * ix2)
                        max_inner_h = max(1, max_outer_h - 2 * iy2)
                        # Candidate by width limit
                        cand_inner_h_from_w = int(round(max_inner_w / aspect_ratio))
                        # Candidate by height limit
                        cand_inner_w_from_h = int(round(max_inner_h * aspect_ratio))
                        # Choose the pair that fits within both limits
                        if cand_inner_h_from_w <= max_inner_h:
                            inner_w_fit = max_inner_w
                            inner_h_fit = max(1, cand_inner_h_from_w)
                        else:
                            inner_h_fit = max_inner_h
                            inner_w_fit = max(1, cand_inner_w_from_h)
                        # Reconstruct outer target size
                        target_w2 = inner_w_fit + 2 * ix2
                        target_h2 = inner_h_fit + 2 * iy2
                    else:
                        target_w2 = min(new_rect.width(), full_bounds.width())
                        target_h2 = min(new_rect.height(), full_bounds.height())

                    # Recompute origin based on pinned edges
                    dw2 = int(target_w2) - width0
                    dh2 = int(target_h2) - height0
                    if pinned_right and not pinned_left:
                        new_left2 = cur_geo.left() - dw2
                    elif pinned_left and not pinned_right:
                        new_left2 = cur_geo.left()
                    else:
                        new_left2 = cur_geo.left() - dw2 // 2

                    if pinned_bottom and not pinned_top:
                        new_top2 = cur_geo.top() - dh2
                    elif pinned_top and not pinned_bottom:
                        new_top2 = cur_geo.top()
                    else:
                        new_top2 = cur_geo.top() - dh2 // 2

                    new_rect = QRect(new_left2, new_top2, int(target_w2), int(target_h2))

                # Finally, clamp position within full monitor bounds
                max_xm = full_bounds.right() - new_rect.width()
                max_ym = full_bounds.bottom() - new_rect.height()
                clamped = QRect(
                    max(full_bounds.left(), min(new_rect.left(), max_xm)),
                    max(full_bounds.top(), min(new_rect.top(), max_ym)),
                    new_rect.width(),
                    new_rect.height(),
                )
            except Exception:
                # Fallback to union clamp
                max_x = union_rect.right() - new_rect.width()
                max_y = union_rect.bottom() - new_rect.height()
                clamped = QRect(
                    max(union_rect.left(), min(new_rect.left(), max_x)),
                    max(union_rect.top(), min(new_rect.top(), max_y)),
                    new_rect.width(),
                    new_rect.height(),
                )

            # Boundary smoothing: when we hit union bounds, apply smaller incremental step
            # BUT: Skip smoothing if pinned edges are stable (window growing away from boundary, not into it)
            try:
                pinned_edges_stable = False
                try:
                    # Check if pinned edge positions are unchanged (growing away from boundary)
                    if pinned_left and clamped.left() == new_rect.left() == cur_geo.left():
                        pinned_edges_stable = True
                    if pinned_right and clamped.right() == new_rect.right() == cur_geo.right():
                        pinned_edges_stable = True
                    if pinned_top and clamped.top() == new_rect.top() == cur_geo.top():
                        pinned_edges_stable = True
                    if pinned_bottom and clamped.bottom() == new_rect.bottom() == cur_geo.bottom():
                        pinned_edges_stable = True
                except Exception:
                    pass
                
                if clamped != new_rect and abs(dx) > 1 and not pinned_edges_stable:
                    step = max(1, min(abs(dx), 2))
                    step_sign = 1 if dx > 0 else -1
                    if aspect_ratio:
                        # Adjust inner size by a tiny step while preserving AR and insets
                        ix2 = iy2 = 0
                        if isinstance(content_insets, tuple) and len(content_insets) == 2:
                            ix2, iy2 = content_insets
                            ix2 = max(0, int(ix2))
                            iy2 = max(0, int(iy2))
                        inner_w1 = max(1, (width0 - 2 * ix2) + sides_h * step_sign * step)
                        inner_h1 = int(round(inner_w1 / aspect_ratio)) if aspect_ratio else (height0 + sides_v * step_sign * step)
                        target_w2 = inner_w1 + 2 * ix2
                        target_h2 = inner_h1 + 2 * iy2
                    else:
                        target_w2 = width0 + sides_h * step_sign * step
                        target_h2 = height0 + sides_v * step_sign * step

                    dw2 = target_w2 - width0
                    dh2 = target_h2 - height0
                    if pinned_right and not pinned_left:
                        new_left2 = cur_geo.left() - dw2
                    elif pinned_left and not pinned_right:
                        new_left2 = cur_geo.left()
                    else:
                        new_left2 = cur_geo.left() - dw2 // 2

                    if pinned_bottom and not pinned_top:
                        new_top2 = cur_geo.top() - dh2
                    elif pinned_top and not pinned_bottom:
                        new_top2 = cur_geo.top()
                    else:
                        new_top2 = cur_geo.top() - dh2 // 2

                    new_rect2 = QRect(new_left2, new_top2, int(target_w2), int(target_h2))
                    clamped = QRect(
                        max(union_rect.left(), min(new_rect2.left(), union_rect.right() - new_rect2.width())),
                        max(union_rect.top(), min(new_rect2.top(), union_rect.bottom() - new_rect2.height())),
                        new_rect2.width(),
                        new_rect2.height(),
                    )
            except Exception:
                pass

            # Store latest pending geometry for coalesced apply
            self._pending_wheel_geo = clamped
            
            old_size = f"{cur_geo.width()}x{cur_geo.height()}"
            new_size = f"{clamped.width()}x{clamped.height()}"
            self._logger.debug(f"WHEEL_RESIZE: {old_size} -> {new_size} (delta: {clamped.width()-cur_geo.width()}x{clamped.height()-cur_geo.height()})")

            # Coalesce timers: schedule once per burst via ThreadManager (UI-safe)
            if not hasattr(self, "_wheel_apply_scheduled") or not getattr(self, "_wheel_apply_scheduled"):
                setattr(self, "_wheel_apply_scheduled", True)
                try:
                    ThreadManager.single_shot(5, self._apply_pending_wheel_geo)
                except Exception as e:
                    self._logger.error(f"Wheel resize schedule failed: {e}")
                    # Fallback: apply immediately
                    self._apply_pending_wheel_geo()
        except Exception as e:
            self._logger.error(f"handle_wheel failed: {e}")

    def handle_leave(self):
        """Handle mouse leave events to reset cursor."""
        if not (self._drag_state.is_dragging or self._drag_state.is_resizing):
            self._widget.setCursor(Qt.ArrowCursor)
            self._drag_state.cursor_overridden = False

    def _apply_pending_wheel_geo(self) -> None:
        """Apply the latest pending wheel geometry on the UI thread."""
        try:
            pending = self._pending_wheel_geo
            if pending is None:
                return
            self._widget.setGeometry(pending)
            self._widget.update()
            # Opportunistic persistence for standalone DWM overlays after wheel-resize
            try:
                overlay = getattr(self._widget, '_parent_overlay', None)
                if overlay is None:
                    overlay = getattr(self._widget, '_backend_overlay', None)
                if overlay is not None and hasattr(overlay, '_persist_current_geometry'):
                    overlay._persist_current_geometry()
            except Exception:
                pass
        except Exception as e:
            self._logger.error(f"Failed to apply wheel geometry: {e}")
        finally:
            self._pending_wheel_geo = None
            self._wheel_accum = 0.0
            setattr(self, "_wheel_apply_scheduled", False)
    
    def apply_snap_to_position(self, screen_rects: Optional[List[QRect]] = None) -> QPoint:
        """Apply snapping to the current widget position.
        
        Args:
            screen_rects: Optional list of screen rectangles to snap to
            
        Returns:
            QPoint: New position after snapping
        """
        return apply_snap(self._widget.pos(), self._widget.size(), DEFAULT_SNAP_DISTANCE, screen_rects)
        
    def _handle_drag(self, global_pos: QPoint):
        """Handle window dragging with snapping and strict per-monitor clamping.
        
        Args:
            global_pos: Current global mouse position
        """
        if not self._drag_state.is_dragging or not self._drag_state.drag_start_position:
            return

        # Intended top-left = global mouse - local press offset (logical coords)
        offset = self._drag_state.drag_start_position
        target = global_pos - offset

        # Snap selection without bounce:
        # - If the intended bottom is below work-area bottom by a small margin, only snap to full geometry
        # - Otherwise, allow snapping to both work-area (taskbar) and full edges
        screens = QGuiApplication.screens() or []
        size = self._widget.size()
        future_target = QRect(target, size)
        center_target = future_target.center()
        screen = QGuiApplication.screenAt(center_target) or QGuiApplication.primaryScreen()
        snapped = target
        if screen is not None:
            work = screen.availableGeometry()
            full = screen.geometry()
            INTENT_MARGIN = 4  # px
            target_bottom = target.y() + size.height()

            if target_bottom > work.bottom() + INTENT_MARGIN:
                # User intent clearly below taskbar: no work-area snapping, prevent bounce
                snap_rects = [full]
                # Inform native filter to clamp to full monitor rect (allow taskbar overlap)
                try:
                    self._drag_state.allow_taskbar_overlap = True
                except Exception:
                    pass
            else:
                # Near or above taskbar: allow both taskbar snag and full-bottom snap
                snap_rects = [work, full]
                try:
                    self._drag_state.allow_taskbar_overlap = False
                except Exception:
                    pass

            snapped = apply_snap(target, size, DEFAULT_SNAP_DISTANCE, snap_rects)
        else:
            # Fallback: snap against all known screens' full bounds
            snap_rects = [s.geometry() for s in screens]
            snapped = apply_snap(target, size, DEFAULT_SNAP_DISTANCE, snap_rects)

        # Clamp within the FULL monitor geometry (not work area) so the window can overlay taskbar
        bounded = snapped
        try:
            future = QRect(bounded, self._widget.size())
            center = future.center()
            screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
            if screen is not None:
                full = screen.geometry()
                bx = min(max(future.x(), full.left()), full.right() - future.width())
                by = min(max(future.y(), full.top()), full.bottom() - future.height())
                bounded = QPoint(bx, by)
        except Exception:
            pass

        # Move window
        self._widget.move(bounded)
    
    def _handle_resize(self, global_pos: QPoint):
        """Handle window resizing with proper geometry calculations.
        
        Args:
            global_pos: Current global mouse position
        """
        if not self._drag_state.is_resizing or not self._drag_state.resize_edge:
            return
        
        # Calculate delta from start position
        delta = global_pos - self._drag_state.drag_global_start
        
        # Get current geometry
        current_geo = self._widget.geometry()
        
        # Apply resize based on edge with minimum size constraints
        new_geo = _apply_resize_delta(current_geo, self._drag_state.resize_edge, delta, self._min_size)
        
        # Apply the new geometry
        self._widget.setGeometry(new_geo)
        
        # Update start position for next resize calculation
        self._drag_state.drag_global_start = global_pos
        
        # Only log resize events at lower frequency to reduce spam
        if not hasattr(self, '_resize_log_counter'):
            self._resize_log_counter = 0
        self._resize_log_counter += 1
        if self._resize_log_counter % 10 == 0:  # Log every 10th resize event
            self._logger.debug(f"Resize: edge={self._drag_state.resize_edge}, delta={delta}, new_geo={new_geo}")

    def _update_cursor_for_position(self, pos: QPoint, restrict_to_bottom_right: bool = False):
        """Update cursor based on position over the widget with improved reliability.
        
        Args:
{{ ... }}
            pos: Current mouse position
            restrict_to_bottom_right: Whether to restrict to bottom right corner only
        """
        # Skip if we're already dragging or resizing
        if self._drag_state.is_dragging or self._drag_state.is_resizing:
            return
            
        # Get the resize edge for the current position
        edge = get_resize_edge_for_pos(pos, self._widget, restrict_to_bottom_right=restrict_to_bottom_right)
        
        # Set the appropriate cursor
        cursor = get_cursor_for_edge(edge)
        if cursor:
            self._widget.setCursor(cursor)
            self._drag_state.cursor_overridden = True
        elif self._drag_state.cursor_overridden:
            self._widget.setCursor(Qt.ArrowCursor)
            self._drag_state.cursor_overridden = False


class WindowManagementCore(QObject):
    """
    This class provides a unified interface for all window management operations,
    including overlay management, window state persistence, and thumbnail handling.
    """
    
    # Signals
    overlay_created = Signal(int, bool)  # hwnd, success
    overlay_updated = Signal(int, bool)  # hwnd, success
    overlay_removed = Signal(int)  # hwnd
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super(WindowManagementCore, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the window management core."""
        if not self._initialized:
            super().__init__()
            self._logger = get_logger(__name__)
            self._initialized = True
            
            # Window integration functionality is now directly integrated
            # into this class, no need for a separate WindowIntegration instance
            self._window_integration = None
            self._logger.info("Window integration functionality consolidated into WindowManagementCore")
    
    @property
    def window_integration(self):
        """Get the window integration instance."""
        return self._window_integration
    
    # Monitor Management
    
    @staticmethod
    def get_all_monitor_rects() -> List[QRect]:
        """Get rectangles for all monitors using core systems."""
        # Use cached value if available
        if hasattr(WindowManagementCore, '_cached_monitor_rects'):
            return WindowManagementCore._cached_monitor_rects
            
        # Import here to avoid circular imports
        from .monitors import get_all_monitor_rects as _get_all_monitor_rects
        
        # Cache the result
        WindowManagementCore._cached_monitor_rects = _get_all_monitor_rects()
        return WindowManagementCore._cached_monitor_rects
    
    @staticmethod
    def apply_window_snap(
        pos: QPoint,
        size: QSize,
        screen_rects: Optional[List[QRect]] = None,
    ) -> QPoint:
        """
        Apply window snapping logic using core systems.
        
        Args:
            pos: Current window position
            size: Window size
            screen_rects: Optional list of screen rectangles to snap to
            
        Returns:
            New window position after applying snap
        """
        # Get screen rects if not provided
        if screen_rects is None:
            screen_rects = WindowManagementCore.get_all_monitor_rects()
            
        # Use the apply_snap function from this module
        return apply_snap(pos, size, DEFAULT_SNAP_DISTANCE, screen_rects)
    
    # Overlay Management
    
    def create_overlay(self, window_id: str, hwnd: int, config: Dict[str, Any] = None) -> bool:
        """Create an overlay for a window."""
        if self._window_integration:
            return self._window_integration.create_overlay(window_id, hwnd, config)
        return False
    
    def update_overlay(self, hwnd: int, config: Dict[str, Any]) -> bool:
        """Update an existing overlay."""
        if self._window_integration:
            return self._window_integration.update_overlay(hwnd, config)
        return False
    
    def remove_overlay(self, hwnd: int) -> bool:
        """Remove an overlay."""
        if self._window_integration:
            return self._window_integration.remove_overlay(hwnd)
        return False


class WindowManager(QObject):
    """
    Centralized window management for overlays, MRU, and lock state.
    All logic is migrated from main.py for modularity and maintainability.
    """
    # Define signals for external components to connect to
    lock_state_changed = Signal(bool)  # Emitted when overlay lock state changes
    
    def __init__(self, max_mru_items=50):
        super().__init__()
        self.logger = get_logger(__name__)
        
        self.mru_hwnds = []
        self._hwnd_last_focus_ts = {}
        self.MAX_MRU_ITEMS = max_mru_items
        self._overlays_locked = False
        self.active_overlays = {}
        self.keep_alive_handlers = {}

    def is_overlay_locked(self):
        return self._overlays_locked

    def set_overlay_lock(self, locked):
        locked_state = bool(locked)
        if self._overlays_locked != locked_state:
            self._overlays_locked = locked_state
            self.logger.debug(f"Overlay lock {'enabled' if locked_state else 'disabled'}")
            
            # Update all overlays with the new lock state
            for overlay in self.active_overlays.values():
                if hasattr(overlay, 'update_lock_state'):
                    overlay.update_lock_state(locked_state)
            
            # Emit signal to notify other components of the state change
            self.lock_state_changed.emit(locked_state)


@dataclass
class WindowState:
    """Represents the state of a window that should be persisted."""
    window_id: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    is_maximized: bool = False
    is_minimized: bool = False
    opacity: float = 1.0
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the window state to a dictionary."""
        data = asdict(self)
        # Ensure extra_data is a dict
        if not isinstance(data.get('extra_data'), dict):
            data['extra_data'] = {}
        return data
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Create a WindowState from a dictionary."""
        # Ensure required fields exist
        if 'window_id' not in data:
            raise ValueError("Window state data must contain 'window_id'")
            
        # Ensure extra_data is a dict
        if 'extra_data' not in data or not isinstance(data['extra_data'], dict):
            data['extra_data'] = {}
            
        return cls(**data)


class WindowStateManager:
    """Manages persistence and retrieval of window states."""
    
    def __init__(self, app_name: str = "ShittyPiP", organization: str = "ShittyPiP"):
        """Initialize the window state manager.
        
        Args:
            app_name: Application name for settings organization
            organization: Organization name for settings organization
        """
        self._logger = get_logger(__name__)
        self._settings = QSettings(organization, app_name)
        self._window_states: Dict[str, WindowState] = {}
        self._load_states()
    
    def save_state(self, state: WindowState) -> bool:
        """Save a window state.
        
        Args:
            state: WindowState to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self._window_states[state.window_id] = state
            self._save_states()
            return True
        except Exception as e:
            self._logger.error(f"Failed to save window state {state.window_id}: {e}")
            return False
    
    def get_state(self, window_id: str) -> Optional[WindowState]:
        """Get a window state by ID.
        
        Args:
            window_id: ID of the window to get state for
            
        Returns:
            Optional[WindowState]: The window state if found, None otherwise
        """
        return self._window_states.get(window_id)
    
    def remove_state(self, window_id: str) -> bool:
        """Remove a window state.
        
        Args:
            window_id: ID of the window state to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        if window_id in self._window_states:
            del self._window_states[window_id]
            self._save_states()
            return True
        return False
    
    def _load_states(self) -> None:
        """Load window states from settings."""
        try:
            states_json = self._settings.value("window_states", "{}")
            states_dict = json.loads(states_json)
            
            for window_id, state_dict in states_dict.items():
                try:
                    self._window_states[window_id] = WindowState.from_dict(state_dict)
                except Exception as e:
                    self._logger.error(f"Failed to load window state {window_id}: {e}")
        except Exception as e:
            self._logger.error(f"Failed to load window states: {e}")
    
    def _save_states(self) -> None:
        """Save window states to settings."""
        try:
            states_dict = {}
            for window_id, state in self._window_states.items():
                states_dict[window_id] = state.to_dict()
                
            states_json = json.dumps(states_dict)
            self._settings.setValue("window_states", states_json)
            self._settings.sync()
        except Exception as e:
            self._logger.error(f"Failed to save window states: {e}")


