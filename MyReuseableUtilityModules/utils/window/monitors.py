"""
Monitor detection and management utilities.

This module provides functionality for working with multiple monitors, including
retrieving monitor information, calculating positions, and handling DPI scaling.
"""

import ctypes
import ctypes.wintypes as wintypes
import time
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QGuiApplication, QScreen

from core.logging import get_logger

# Define HRESULT type if not available
if not hasattr(wintypes, 'HRESULT'):
    wintypes.HRESULT = ctypes.c_long

# Windows API constants
MONITOR_DEFAULTTONEAREST = 0x00000002
MONITOR_DEFAULTTOPRIMARY = 0x00000001
MONITOR_DEFAULTTONULL = 0x00000000

# DPI Awareness constants
MDT_EFFECTIVE_DPI = 0
MDT_ANGULAR_DPI = 1
MDT_RAW_DPI = 2

# System metrics constants
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# GetDeviceCaps constants
LOGPIXELSX = 88
LOGPIXELSY = 90

# Monitor flags
MONITORINFOF_PRIMARY = 0x1

# Cache configuration
CACHE_TTL_SECONDS = 5.0
DEFAULT_DPI = 96

logger = get_logger(__name__)

# Windows API structures
class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG)
    ]

class MonitorInfo(NamedTuple):
    """Structured monitor information."""
    name: str
    is_primary: bool
    screen: QScreen
    logical_geometry: QRect
    logical_available_geometry: QRect
    device_pixel_ratio: float
    logical_dpi: Tuple[float, float]
    physical_dpi: Tuple[float, float]
    physical_width: int
    physical_height: int
    physical_position: QPoint
    physical_rect: QRect
    physical_work_area: QRect
    scaled_width: int
    scaled_height: int
    scaled_rect: QRect
    dpi: Tuple[int, int]
    scale_factor: float
    scale_factor_x: float
    scale_factor_y: float
    monitor_handle: Optional[int]
    device_name: str

# Windows API setup
user32 = ctypes.WinDLL('user32')
shcore = ctypes.OleDLL('shcore')
gdi32 = ctypes.WinDLL('gdi32')

# Function prototypes
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR

user32.MonitorFromRect.argtypes = [wintypes.LPRECT, wintypes.DWORD]
user32.MonitorFromRect.restype = wintypes.HMONITOR

user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR

user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
user32.GetMonitorInfoW.restype = wintypes.BOOL

shcore.GetDpiForMonitor.argtypes = [wintypes.HMONITOR, ctypes.c_int, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)]
shcore.GetDpiForMonitor.restype = wintypes.HRESULT

class CacheManager:
    """Manages caching for screen and monitor information."""
    
    def __init__(self, ttl: float = CACHE_TTL_SECONDS):
        self.ttl = ttl
        self.screen_cache: Optional[Dict[str, Any]] = None
        self.screen_cache_time: float = 0
        self.monitor_cache: Dict[str, MonitorInfo] = {}
        self.monitor_cache_time: float = 0
        self.dpi_cache: Dict[str, float] = {}
        self.dpi_cache_time: float = 0
        self._cache_valid = False
    
    def is_cache_valid(self, cache_time: float) -> bool:
        """Check if cache is still valid based on TTL."""
        return (time.time() - cache_time) < self.ttl
    
    def invalidate_all(self):
        """Invalidate all caches."""
        self.screen_cache = None
        self.monitor_cache.clear()
        self.dpi_cache.clear()
        self.screen_cache_time = 0
        self.monitor_cache_time = 0
        self.dpi_cache_time = 0
        self._cache_valid = False
    
    def get_screen_cache(self) -> Optional[Dict[str, Any]]:
        """Get screen cache if valid."""
        if self.screen_cache is not None and self.is_cache_valid(self.screen_cache_time):
            return self.screen_cache
        return None
    
    def set_screen_cache(self, cache_data: Dict[str, Any]):
        """Set screen cache with current timestamp."""
        self.screen_cache = cache_data
        self.screen_cache_time = time.time()
        self._cache_valid = True

# Global cache manager
_cache_manager = CacheManager()

def _get_default_monitor_info(screen: Optional[QScreen] = None) -> MonitorInfo:
    """Create default monitor info for fallback scenarios."""
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    
    return MonitorInfo(
        name="Primary Monitor",
        is_primary=True,
        screen=screen,
        logical_geometry=screen.geometry(),
        logical_available_geometry=screen.availableGeometry(),
        device_pixel_ratio=screen.devicePixelRatio(),
        logical_dpi=(screen.logicalDotsPerInchX(), screen.logicalDotsPerInchY()),
        physical_dpi=(screen.physicalDotsPerInchX(), screen.physicalDotsPerInchY()),
        physical_width=screen.size().width(),
        physical_height=screen.size().height(),
        physical_position=screen.geometry().topLeft(),
        physical_rect=screen.geometry(),
        physical_work_area=screen.availableGeometry(),
        scaled_width=screen.size().width(),
        scaled_height=screen.size().height(),
        scaled_rect=screen.geometry(),
        dpi=(int(screen.logicalDotsPerInchX()), int(screen.logicalDotsPerInchY())),
        scale_factor=screen.devicePixelRatio(),
        scale_factor_x=screen.devicePixelRatio(),
        scale_factor_y=screen.devicePixelRatio(),
        monitor_handle=None,
        device_name=""
    )

def _get_monitor_dpi(monitor_handle: wintypes.HMONITOR, device_name: str) -> Tuple[int, int]:
    """Get DPI for monitor using Windows API with multiple fallbacks."""
    # Try GetDpiForMonitor first (Windows 8.1+)
    dpi_x = wintypes.UINT()
    dpi_y = wintypes.UINT()
    
    try:
        if hasattr(shcore, 'GetDpiForMonitor'):
            result = shcore.GetDpiForMonitor(
                monitor_handle,
                MDT_EFFECTIVE_DPI,
                ctypes.byref(dpi_x),
                ctypes.byref(dpi_y)
            )
            if result == 0:  # S_OK
                return (dpi_x.value, dpi_y.value)
    except Exception as e:
        logger.debug(f"GetDpiForMonitor failed: {e}")
    
    # Fall back to system DPI
    hdc = user32.GetDC(None)
    if hdc:
        try:
            dpi_x = gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
            dpi_y = gdi32.GetDeviceCaps(hdc, LOGPIXELSY)
            return (dpi_x, dpi_y)
        finally:
            user32.ReleaseDC(None, hdc)
    
    # Last resort: default DPI
    return (DEFAULT_DPI, DEFAULT_DPI)

def get_physical_monitor_info(screen: QScreen) -> MonitorInfo:
    """Get comprehensive monitor information using Windows API with caching."""
    # Check cache first
    cache_key = f"{screen.name()}_{screen.serialNumber()}"
    if cache_key in _cache_manager.monitor_cache:
        if _cache_manager.is_cache_valid(_cache_manager.monitor_cache_time):
            return _cache_manager.monitor_cache[cache_key]
    
    # Get monitor handle from screen position
    screen_geometry = screen.geometry()
    center = screen_geometry.center()
    point = wintypes.POINT(center.x(), center.y())
    monitor_handle = user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
    
    if not monitor_handle:
        logger.warning(f"Could not get monitor handle for screen {screen.name()}")
        return _get_default_monitor_info(screen)
    
    # Get monitor info
    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ('cbSize', wintypes.DWORD),
            ('rcMonitor', RECT),
            ('rcWork', RECT),
            ('dwFlags', wintypes.DWORD),
            ('szDevice', wintypes.WCHAR * 32)
        ]
    
    monitor_info = MONITORINFOEX()
    monitor_info.cbSize = ctypes.sizeof(MONITORINFOEX)
    
    if not user32.GetMonitorInfoW(monitor_handle, ctypes.byref(monitor_info)):
        logger.warning(f"Could not get monitor info for handle {monitor_handle}")
        return _get_default_monitor_info(screen)
    
    # Get DPI
    dpi_x, dpi_y = _get_monitor_dpi(monitor_handle, monitor_info.szDevice)
    
    # Calculate scale factors
    scale_factor_x = dpi_x / DEFAULT_DPI
    scale_factor_y = dpi_y / DEFAULT_DPI
    
    # Create monitor info
    monitor_rect = QRect(
        monitor_info.rcMonitor.left,
        monitor_info.rcMonitor.top,
        monitor_info.rcMonitor.right - monitor_info.rcMonitor.left,
        monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top
    )
    
    work_area = QRect(
        monitor_info.rcWork.left,
        monitor_info.rcWork.top,
        monitor_info.rcWork.right - monitor_info.rcWork.left,
        monitor_info.rcWork.bottom - monitor_info.rcWork.top
    )
    
    is_primary = bool(monitor_info.dwFlags & MONITORINFOF_PRIMARY)
    
    info = MonitorInfo(
        name=screen.name(),
        is_primary=is_primary,
        screen=screen,
        logical_geometry=screen_geometry,
        logical_available_geometry=screen.availableGeometry(),
        device_pixel_ratio=screen.devicePixelRatio(),
        logical_dpi=(screen.logicalDotsPerInchX(), screen.logicalDotsPerInchY()),
        physical_dpi=(dpi_x, dpi_y),
        physical_width=monitor_rect.width(),
        physical_height=monitor_rect.height(),
        physical_position=monitor_rect.topLeft(),
        physical_rect=monitor_rect,
        physical_work_area=work_area,
        scaled_width=int(monitor_rect.width() / scale_factor_x),
        scaled_height=int(monitor_rect.height() / scale_factor_y),
        scaled_rect=QRect(
            monitor_rect.x(),
            monitor_rect.y(),
            int(monitor_rect.width() / scale_factor_x),
            int(monitor_rect.height() / scale_factor_y)
        ),
        dpi=(dpi_x, dpi_y),
        scale_factor=max(scale_factor_x, scale_factor_y),
        scale_factor_x=scale_factor_x,
        scale_factor_y=scale_factor_y,
        monitor_handle=monitor_handle,
        device_name=monitor_info.szDevice
    )
    
    # Update cache
    _cache_manager.monitor_cache[cache_key] = info
    _cache_manager.monitor_cache_time = time.time()
    
    return info

def _refresh_screen_cache() -> Dict[str, Any]:
    """Refresh the comprehensive screen cache."""
    screens = QGuiApplication.screens()
    primary_screen = QGuiApplication.primaryScreen()
    
    # Get all monitor rects
    all_rects = []
    for screen in screens:
        info = get_physical_monitor_info(screen)
        all_rects.append(info.physical_rect)
    
    # Calculate virtual screen bounds
    if not all_rects:
        virtual_rect = QRect()
    else:
        left = min(r.left() for r in all_rects)
        top = min(r.top() for r in all_rects)
        right = max(r.right() for r in all_rects)
        bottom = max(r.bottom() for r in all_rects)
        virtual_rect = QRect(left, top, right - left, bottom - top)
    
    # Build screen info
    screen_info = {
        'screens': screens,
        'primary_screen': primary_screen,
        'all_rects': all_rects,
        'virtual_rect': virtual_rect,
        'timestamp': time.time()
    }
    
    _cache_manager.set_screen_cache(screen_info)
    return screen_info

def get_screen_info() -> Dict[str, Any]:
    """Get cached screen information, refreshing if necessary."""
    cached = _cache_manager.get_screen_cache()
    if cached is not None:
        return cached
    return _refresh_screen_cache()

def get_all_monitor_rects() -> List[QRect]:
    """Get rectangles for all monitors."""
    return get_screen_info()['all_rects']

def get_virtual_screen_rect() -> QRect:
    """Get the virtual screen rectangle spanning all monitors."""
    return get_screen_info()['virtual_rect']

def find_monitor_for_window(pos: QPoint, size: QSize) -> int:
    """Find which monitor contains the window center."""
    center = pos + QPoint(size.width() // 2, size.height() // 2)
    screens = QGuiApplication.screens()
    
    for i, screen in enumerate(screens):
        if screen.geometry().contains(center):
            return i
    
    # Fall back to primary screen if no monitor contains the center
    return 0

def get_screen_scale_factor(screen: QScreen) -> float:
    """Get screen scale factor with caching."""
    cache_key = f"{screen.name()}_{screen.serialNumber()}"
    
    if cache_key in _cache_manager.dpi_cache:
        if _cache_manager.is_cache_valid(_cache_manager.dpi_cache_time):
            return _cache_manager.dpi_cache[cache_key]
    
    # Get the monitor info which includes DPI information
    monitor_info = get_physical_monitor_info(screen)
    scale_factor = monitor_info.scale_factor
    
    # Update cache
    _cache_manager.dpi_cache[cache_key] = scale_factor
    _cache_manager.dpi_cache_time = time.time()
    
    return scale_factor

def ensure_within_available_desktop(pos: QPoint, size: QSize) -> QPoint:
    """Ensure window stays within available desktop area with improved logic."""
    screens = QGuiApplication.screens()
    if not screens:
        return pos
    
    # Get the target monitor
    target_monitor_idx = find_monitor_for_window(pos, size)
    target_screen = screens[target_monitor_idx]
    
    # Get available geometry (accounting for taskbar)
    available = target_screen.availableGeometry()
    
    # Adjust position to stay within available area
    new_pos = pos
    
    # Check right edge
    if new_pos.x() + size.width() > available.right():
        new_pos.setX(available.right() - size.width() + 1)
    
    # Check bottom edge
    if new_pos.y() + size.height() > available.bottom():
        new_pos.setY(available.bottom() - size.height() + 1)
    
    # Check left edge
    if new_pos.x() < available.left():
        new_pos.setX(available.left())
    
    # Check top edge
    if new_pos.y() < available.top():
        new_pos.setY(available.top())
    
    # If the window is larger than the available area, ensure it's visible
    if size.width() > available.width():
        new_pos.setX(available.left())
    if size.height() > available.height():
        new_pos.setY(available.top())
    
    return new_pos

def _constrain_to_virtual_screen(pos: QPoint, size: QSize) -> QPoint:
    """Constrain position to virtual screen bounds."""
    virtual_rect = get_virtual_screen_rect()
    new_pos = pos
    
    # Right edge
    if new_pos.x() + size.width() > virtual_rect.right():
        new_pos.setX(virtual_rect.right() - size.width() + 1)
    
    # Bottom edge
    if new_pos.y() + size.height() > virtual_rect.bottom():
        new_pos.setY(virtual_rect.bottom() - size.height() + 1)
    
    # Left edge
    if new_pos.x() < virtual_rect.left():
        new_pos.setX(virtual_rect.left())
    
    # Top edge
    if new_pos.y() < virtual_rect.top():
        new_pos.setY(virtual_rect.top())
    
    return new_pos

def invalidate_cache():
    """Invalidate all caches to force refresh."""
    _cache_manager.invalidate_all()

def get_monitor_at_position(pos: QPoint) -> int:
    """Get monitor information for a specific position."""
    screens = QGuiApplication.screens()
    for i, screen in enumerate(screens):
        if screen.geometry().contains(pos):
            return i
    return 0  # Default to primary monitor

def get_primary_monitor() -> int:
    """Get information about the primary monitor."""
    primary_screen = QGuiApplication.primaryScreen()
    screens = QGuiApplication.screens()
    return screens.index(primary_screen) if primary_screen in screens else 0

def calculate_window_center(geometry: QRect) -> QPoint:
    """Calculate the center point of a window geometry."""
    return geometry.center()

def is_window_on_monitor(window_geometry: QRect, monitor_rect: QRect, threshold: float = 0.5) -> bool:
    """Check if a window is significantly on a monitor (by area overlap)."""
    # Calculate intersection area
    x_overlap = max(0, min(window_geometry.right(), monitor_rect.right()) - max(window_geometry.left(), monitor_rect.left()))
    y_overlap = max(0, min(window_geometry.bottom(), monitor_rect.bottom()) - max(window_geometry.top(), monitor_rect.top()))
    overlap_area = x_overlap * y_overlap
    
    # Calculate window area
    window_area = window_geometry.width() * window_geometry.height()
    
    # Check if overlap is above threshold
    return (overlap_area / window_area) >= threshold if window_area > 0 else False

def get_best_monitor_for_window(window_geometry: QRect) -> int:
    """Find the best monitor for a window based on overlap area."""
    screens = QGuiApplication.screens()
    if not screens:
        return 0
    
    max_overlap = 0
    best_monitor = 0
    
    for i, screen in enumerate(screens):
        screen_rect = screen.geometry()
        # Calculate intersection area
        x_overlap = max(0, min(window_geometry.right(), screen_rect.right()) - max(window_geometry.left(), screen_rect.left()))
        y_overlap = max(0, min(window_geometry.bottom(), screen_rect.bottom()) - max(window_geometry.top(), screen_rect.top()))
        overlap_area = x_overlap * y_overlap
        
        if overlap_area > max_overlap:
            max_overlap = overlap_area
            best_monitor = i
    
    return best_monitor

def get_available_geometry_for_monitor(monitor_index: int) -> QRect:
    """Get the available geometry (work area) for a specific monitor."""
    screens = QGuiApplication.screens()
    if 0 <= monitor_index < len(screens):
        return screens[monitor_index].availableGeometry()
    return QGuiApplication.primaryScreen().availableGeometry()

def center_window_on_monitor(window_size: QSize, monitor_index: int = 0) -> QPoint:
    """Calculate position to center a window on a specific monitor."""
    screens = QGuiApplication.screens()
    if not screens or monitor_index >= len(screens):
        return QPoint(0, 0)
    
    screen = screens[monitor_index]
    geometry = screen.availableGeometry()
    
    x = geometry.left() + (geometry.width() - window_size.width()) // 2
    y = geometry.top() + (geometry.height() - window_size.height()) // 2
    
    return QPoint(x, y)

def get_physical_work_area_at(point: QPoint) -> QRect:
    """Return the monitor work area (physical pixels) for a given physical point.

    This uses Win32 MonitorFromPoint/GetMonitorInfoW and returns a QRect in the same
    coordinate space as WM_MOVING's RECT (physical device pixels in the virtual desktop).
    The caller is responsible for passing a point in physical pixels.
    """
    # Define MONITORINFOEX compatible with our RECT
    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ('cbSize', wintypes.DWORD),
            ('rcMonitor', RECT),
            ('rcWork', RECT),
            ('dwFlags', wintypes.DWORD),
            ('szDevice', wintypes.WCHAR * 32)
        ]

    pt = wintypes.POINT(int(point.x()), int(point.y()))
    hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    if not hmon:
        # Fallback to virtual screen bounds
        return get_virtual_screen_rect()

    mi = MONITORINFOEX()
    mi.cbSize = ctypes.sizeof(MONITORINFOEX)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        return get_virtual_screen_rect()

    return QRect(
        mi.rcWork.left,
        mi.rcWork.top,
        mi.rcWork.right - mi.rcWork.left,
        mi.rcWork.bottom - mi.rcWork.top,
    )

def get_physical_monitor_rect_at(point: QPoint) -> QRect:
    """Return the full monitor rectangle (physical pixels) for a given physical point.

    Uses Win32 MonitorFromPoint/GetMonitorInfoW and returns the rcMonitor as a QRect
    in the virtual desktop physical coordinate space (same as WM_MOVING's RECT).
    The caller must pass a QPoint already in physical pixels.
    """
    # Define MONITORINFOEX compatible with our RECT
    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ('cbSize', wintypes.DWORD),
            ('rcMonitor', RECT),
            ('rcWork', RECT),
            ('dwFlags', wintypes.DWORD),
            ('szDevice', wintypes.WCHAR * 32)
        ]

    pt = wintypes.POINT(int(point.x()), int(point.y()))
    hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    if not hmon:
        # Fallback to virtual screen bounds
        return get_virtual_screen_rect()

    mi = MONITORINFOEX()
    mi.cbSize = ctypes.sizeof(MONITORINFOEX)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        return get_virtual_screen_rect()

    return QRect(
        mi.rcMonitor.left,
        mi.rcMonitor.top,
        mi.rcMonitor.right - mi.rcMonitor.left,
        mi.rcMonitor.bottom - mi.rcMonitor.top,
    )

def get_monitor_count() -> int:
    """Get the number of monitors in the system."""
    return len(QGuiApplication.screens())

def is_multi_monitor_setup() -> bool:
    """Check if the system has multiple monitors."""
    return len(QGuiApplication.screens()) > 1

def get_snap_zones_for_monitor(monitor_index: int, window_size: QSize) -> Dict[str, QRect]:
    """Get snap zones (left half, right half, etc.) for a monitor."""
    screens = QGuiApplication.screens()
    if not screens or monitor_index >= len(screens):
        return {}
    
    screen = screens[monitor_index]
    geometry = screen.availableGeometry()
    
    # Calculate zones
    half_width = geometry.width() // 2
    half_height = geometry.height() // 2
    
    return {
        'top_left': QRect(geometry.left(), geometry.top(), half_width, half_height),
        'top_right': QRect(geometry.left() + half_width, geometry.top(), half_width, half_height),
        'bottom_left': QRect(geometry.left(), geometry.top() + half_height, half_width, half_height),
        'bottom_right': QRect(geometry.left() + half_width, geometry.top() + half_height, half_width, half_height),
        'left': QRect(geometry.left(), geometry.top(), half_width, geometry.height()),
        'right': QRect(geometry.left() + half_width, geometry.top(), half_width, geometry.height()),
        'top': QRect(geometry.left(), geometry.top(), geometry.width(), half_height),
        'bottom': QRect(geometry.left(), geometry.top() + half_height, geometry.width(), half_height),
        'center': geometry.adjusted(geometry.width() // 4, geometry.height() // 4, 
                                  -geometry.width() // 4, -geometry.height() // 4)
    }

# Re-export commonly used types and constants
__all__ = [
    'MonitorInfo',
    'get_physical_monitor_info',
    'get_all_monitor_rects',
    'get_virtual_screen_rect',
    'find_monitor_for_window',
    'get_screen_scale_factor',
    'ensure_within_available_desktop',
    'invalidate_cache',
    'get_monitor_at_position',
    'get_primary_monitor',
    'calculate_window_center',
    'is_window_on_monitor',
    'get_best_monitor_for_window',
    'get_available_geometry_for_monitor',
    'center_window_on_monitor',
    'get_physical_work_area_at',
    'get_physical_monitor_rect_at',
    'get_monitor_count',
    'is_multi_monitor_setup',
    'get_snap_zones_for_monitor',
    'CACHE_TTL_SECONDS',
    'DEFAULT_DPI'
]