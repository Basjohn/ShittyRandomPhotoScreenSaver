"""
Monitor detection and management utilities for screensaver.

Simplified version adapted from SPQDocker reusable modules.
Provides basic multi-monitor detection for screensaver display.
"""
from typing import List
from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QGuiApplication, QScreen
from core.logging.logger import get_logger

logger = get_logger(__name__)


def get_all_screens() -> List[QScreen]:
    """
    Get all connected screens.
    
    Returns:
        List of QScreen objects
    """
    screens = QGuiApplication.screens()
    logger.debug(f"Found {len(screens)} screen(s)")
    for i, screen in enumerate(screens):
        logger.debug(f"  Screen {i}: {screen.name()} - {screen.geometry()}")
    return screens


def get_primary_screen() -> QScreen:
    """
    Get the primary screen.
    
    Returns:
        Primary QScreen object
    """
    primary = QGuiApplication.primaryScreen()
    logger.debug(f"Primary screen: {primary.name()}")
    return primary


def get_screen_count() -> int:
    """
    Get the number of connected screens.
    
    Returns:
        Number of screens
    """
    count = len(QGuiApplication.screens())
    logger.debug(f"Screen count: {count}")
    return count


def is_multi_monitor() -> bool:
    """
    Check if system has multiple monitors.
    
    Returns:
        True if multiple monitors detected
    """
    multi = get_screen_count() > 1
    logger.debug(f"Multi-monitor setup: {multi}")
    return multi


def get_screen_geometry(screen: QScreen) -> QRect:
    """
    Get the geometry of a screen.
    
    Args:
        screen: QScreen object
    
    Returns:
        QRect representing screen geometry
    """
    geometry = screen.geometry()
    logger.debug(f"Screen {screen.name()} geometry: {geometry}")
    return geometry


def get_screen_available_geometry(screen: QScreen) -> QRect:
    """
    Get the available geometry of a screen (excluding taskbar).
    
    Args:
        screen: QScreen object
    
    Returns:
        QRect representing available geometry
    """
    geometry = screen.availableGeometry()
    logger.debug(f"Screen {screen.name()} available geometry: {geometry}")
    return geometry


def get_physical_resolution(screen: QScreen) -> tuple[int, int]:
    """
    Get the physical pixel resolution of a screen (accounting for DPI scaling).
    
    Args:
        screen: QScreen object
    
    Returns:
        Tuple of (width, height) in physical pixels
    """
    geometry = screen.geometry()
    dpr = screen.devicePixelRatio()
    width = int(geometry.width() * dpr)
    height = int(geometry.height() * dpr)
    logger.debug(f"Screen {screen.name()} physical resolution: {width}x{height} (DPR: {dpr})")
    return (width, height)


def get_screen_by_index(index: int) -> QScreen | None:
    """
    Get a screen by index.
    
    Args:
        index: Screen index (0-based)
    
    Returns:
        QScreen object or None if index out of range
    """
    screens = get_all_screens()
    if 0 <= index < len(screens):
        return screens[index]
    logger.warning(f"Screen index {index} out of range (0-{len(screens)-1})")
    return None


def get_screen_by_name(name: str) -> QScreen | None:
    """
    Get a screen by name.
    
    Args:
        name: Screen name
    
    Returns:
        QScreen object or None if not found
    """
    screens = get_all_screens()
    for screen in screens:
        if screen.name() == name:
            return screen
    logger.warning(f"Screen with name '{name}' not found")
    return None


def get_virtual_desktop_rect() -> QRect:
    """
    Get the bounding rectangle of all screens (virtual desktop).
    
    Returns:
        QRect spanning all screens
    """
    screens = get_all_screens()
    if not screens:
        return QRect()
    
    # Get all geometries
    geometries = [screen.geometry() for screen in screens]
    
    # Calculate bounds
    left = min(g.left() for g in geometries)
    top = min(g.top() for g in geometries)
    right = max(g.right() for g in geometries)
    bottom = max(g.bottom() for g in geometries)
    
    virtual_rect = QRect(left, top, right - left + 1, bottom - top + 1)
    logger.debug(f"Virtual desktop rect: {virtual_rect}")
    return virtual_rect


def get_screen_at_point(point: QPoint) -> QScreen | None:
    """
    Get the screen that contains a specific point.
    
    Args:
        point: QPoint to check
    
    Returns:
        QScreen containing the point or None
    """
    screens = get_all_screens()
    for screen in screens:
        if screen.geometry().contains(point):
            return screen
    return None


def center_point_on_screen(screen: QScreen) -> QPoint:
    """
    Get the center point of a screen.
    
    Args:
        screen: QScreen object
    
    Returns:
        QPoint at screen center
    """
    return screen.geometry().center()


def get_screen_info_dict(screen: QScreen) -> dict:
    """
    Get comprehensive information about a screen as a dictionary.
    
    Args:
        screen: QScreen object
    
    Returns:
        Dictionary with screen information including both logical and physical sizes
    """
    geometry = screen.geometry()
    available = screen.availableGeometry()
    dpr = screen.devicePixelRatio()
    
    # Calculate physical pixel dimensions
    physical_width = int(geometry.width() * dpr)
    physical_height = int(geometry.height() * dpr)
    physical_available_width = int(available.width() * dpr)
    physical_available_height = int(available.height() * dpr)
    
    return {
        'name': screen.name(),
        'manufacturer': screen.manufacturer(),
        'model': screen.model(),
        'serial_number': screen.serialNumber(),
        'geometry': {
            'x': geometry.x(),
            'y': geometry.y(),
            'width': geometry.width(),
            'height': geometry.height()
        },
        'available_geometry': {
            'x': available.x(),
            'y': available.y(),
            'width': available.width(),
            'height': available.height()
        },
        'physical_geometry': {
            'width': physical_width,
            'height': physical_height
        },
        'physical_available_geometry': {
            'width': physical_available_width,
            'height': physical_available_height
        },
        'device_pixel_ratio': dpr,
        'dpi_scale_percent': int(dpr * 100),
        'logical_dpi_x': screen.logicalDotsPerInchX(),
        'logical_dpi_y': screen.logicalDotsPerInchY(),
        'physical_dpi_x': screen.physicalDotsPerInchX(),
        'physical_dpi_y': screen.physicalDotsPerInchY(),
        'physical_size_mm': {
            'width': screen.physicalSize().width(),
            'height': screen.physicalSize().height()
        },
        'refresh_rate': screen.refreshRate(),
        'orientation': str(screen.orientation()),
        'is_primary': screen == get_primary_screen()
    }


def log_screen_configuration():
    """Log the current screen configuration for debugging."""
    screens = get_all_screens()
    logger.info("=== Screen Configuration ===")
    logger.info(f"Total screens: {len(screens)}")
    logger.info(f"Multi-monitor: {is_multi_monitor()}")
    logger.info(f"Virtual desktop: {get_virtual_desktop_rect()}")
    
    for i, screen in enumerate(screens):
        info = get_screen_info_dict(screen)
        logger.info("")
        logger.info(f"Screen {i}: {info['name']}")
        logger.info(f"  Primary: {info['is_primary']}")
        logger.info(f"  Physical Resolution: {info['physical_geometry']['width']}x{info['physical_geometry']['height']} "
                   f"({info['dpi_scale_percent']}% DPI scaling)")
        logger.info(f"  Logical Resolution: {info['geometry']['width']}x{info['geometry']['height']} "
                   f"at ({info['geometry']['x']}, {info['geometry']['y']})")
        logger.info(f"  Device Pixel Ratio: {info['device_pixel_ratio']}")
        logger.info(f"  DPI: Logical={info['logical_dpi_x']:.1f}x{info['logical_dpi_y']:.1f}, "
                   f"Physical={info['physical_dpi_x']:.1f}x{info['physical_dpi_y']:.1f}")
        logger.info(f"  Refresh rate: {info['refresh_rate']} Hz")
    
    logger.info("=== End Screen Configuration ===")
