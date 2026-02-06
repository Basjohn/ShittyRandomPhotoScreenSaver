"""Display GL Initialization & Lifecycle - Extracted from display_widget.py.

Contains renderer backend init, GL compositor setup, render surface management,
and widget cleanup/destruction handlers.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING


from core.logging.logger import get_logger
from core.events.event_system import EventSystem
from core.settings.settings_manager import SettingsManager
from rendering.backends import create_backend_from_settings
from rendering.backends.base import SurfaceDescriptor
from rendering.gl_compositor import GLCompositorWidget
from transitions.overlay_manager import hide_backend_fallback_overlay

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def init_renderer_backend(widget) -> None:
    """Select and initialize the configured renderer backend."""

    if widget.settings_manager is None:
        logger.info("[RENDER] No settings manager attached; backend initialization skipped")
        return

    event_system: Optional[EventSystem] = None
    try:
        if hasattr(widget.settings_manager, "get_event_system"):
            candidate = widget.settings_manager.get_event_system()
            if isinstance(candidate, EventSystem):
                event_system = candidate
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        event_system = None

    try:
        selection = create_backend_from_settings(
            widget.settings_manager,
            event_system=event_system,
        )
        backend = selection.backend
        widget._backend_selection = selection
        widget._renderer_backend = backend
        caps = backend.get_capabilities()
        logger.info(
            "[RENDER] Backend active (screen=%s, api=%s %s, triple=%s, vsync_toggle=%s)",
            widget.screen_index,
            caps.api_name,
            caps.api_version,
            caps.supports_triple_buffer,
            caps.supports_vsync_toggle,
        )
        if selection.fallback_performed:
            logger.warning(
                "[RENDER] Backend fallback engaged (requested=%s, resolved=%s, reason=%s)",
                selection.requested_mode,
                selection.resolved_mode,
                selection.fallback_reason,
            )
        widget._backend_fallback_message = (
            "Renderer backend: "
            f"{selection.resolved_mode.upper()} (requested {selection.requested_mode.upper()})"
        )
        widget._update_backend_fallback_overlay()
    except Exception:
        logger.exception("[RENDER] Failed to initialize renderer backend", exc_info=True)
        widget._renderer_backend = None
        widget._backend_selection = None
        widget._backend_fallback_message = None
        hide_backend_fallback_overlay(widget)

def build_surface_descriptor(widget) -> SurfaceDescriptor:
    # Timer-only policy: never request driver vsync; rely on timer FPS cap.
    vsync_enabled = False
    prefer_triple = True
    if widget.settings_manager:
        prefer_triple = widget.settings_manager.get('display.prefer_triple_buffer', True)
        if isinstance(prefer_triple, str):
            prefer_triple = prefer_triple.lower() in ('true', '1', 'yes')

    width = max(1, widget.width())
    height = max(1, widget.height())

    return SurfaceDescriptor(
        screen_index=widget.screen_index,
        width=width,
        height=height,
        dpi=widget._device_pixel_ratio,
        vsync_enabled=vsync_enabled,
        prefer_triple_buffer=prefer_triple,
    )

def ensure_render_surface(widget) -> None:
    if widget._renderer_backend is None:
        return
    if widget._render_surface is not None:
        return
    descriptor = build_surface_descriptor(widget, )
    try:
        surface = widget._renderer_backend.create_surface(descriptor)
    except NotImplementedError:
        logger.debug("[RENDER] Backend create_surface not implemented; using widget fallback")
        return
    except Exception as exc:
        logger.exception("[RENDER] Failed to create render surface: %s", exc)
        return

    widget._render_surface = surface
    logger.info(
        "[RENDER] Render surface established (screen=%s, %sx%s, vsync=%s, triple_preference=%s)",
        descriptor.screen_index,
        descriptor.width,
        descriptor.height,
        descriptor.vsync_enabled,
        descriptor.prefer_triple_buffer,
    )

def ensure_gl_compositor(widget) -> None:
    """Create or resize the shared GL compositor widget when appropriate.

    The compositor is only used when hardware acceleration is enabled,
    an OpenGL backend is active, and PyOpenGL/GL are available. This keeps
    software-only environments on the existing CPU path.
    """

    # Guard on hw_accel setting
    hw_accel = True
    if widget.settings_manager is not None:
        try:
            raw = widget.settings_manager.get("display.hw_accel", True)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            raw = True
        hw_accel = SettingsManager.to_bool(raw, True)
    if not hw_accel:
        return

    # Require an OpenGL backend selection
    if widget._backend_selection and widget._backend_selection.resolved_mode != "opengl":
        return

    if widget._gl_compositor is None:
        try:
            comp = GLCompositorWidget(widget)
            comp.setObjectName("_srpss_gl_compositor")
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.hide()
            
            # Timer-based rendering is always used (VSync disabled)
            # Per-screen refresh rate is detected automatically
            
            if widget._resource_manager is not None:
                try:
                    widget._resource_manager.register_qt(
                        comp,
                        description="Shared GL compositor for DisplayWidget",
                    )
                except Exception:
                    logger.debug("[GL COMPOSITOR] Failed to register compositor with ResourceManager", exc_info=True)
            widget._gl_compositor = comp
            logger.info("[GL COMPOSITOR] Created shared compositor for screen %s (timer_render=True)", 
                       widget.screen_index)
        except Exception as exc:
            logger.warning("[GL COMPOSITOR] Failed to create compositor: %s", exc)
            widget._gl_compositor = None
            return
    else:
        try:
            widget._gl_compositor.setGeometry(0, 0, widget.width(), widget.height())
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to update compositor geometry", exc_info=True)

def cleanup_widget(widget, attr_name: str, tag: str, stop_method: str = "cleanup") -> None:
    """Helper to safely cleanup a widget attribute.
    
    Args:
        attr_name: Name of the widget attribute (e.g., "media_widget")
        tag: Log tag for debug messages (e.g., "MEDIA")
        stop_method: Method to call for cleanup ("cleanup", "stop", or None)
    """
    try:
        widget = getattr(widget, attr_name, None)
        if widget is None:
            return
        if stop_method:
            method = getattr(widget, stop_method, None)
            if callable(method):
                try:
                    method()
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        try:
            widget.hide()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        setattr(widget, attr_name, None)
    except Exception as e:
        logger.debug("[%s] Failed to cleanup in _on_destroyed: %s", tag, e, exc_info=True)

def on_destroyed(widget) -> None:
    """Cleanup when widget is destroyed."""
    # Widget cleanup handled by other methods
    pass

