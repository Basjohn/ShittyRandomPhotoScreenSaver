"""DisplayWidget destruction and cleanup logic.

Extracted from display_widget.py to reduce monolith size.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.logger import get_logger
from transitions.overlay_manager import hide_all_overlays

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget

logger = get_logger(__name__)


def on_destroyed(widget: "DisplayWidget", *_args) -> None:
    """Ensure active transitions are stopped when the widget is destroyed."""
    # NOTE: Deferred Reddit URL opening is now handled by DisplayManager.cleanup()
    # to ensure it happens AFTER windows are hidden but BEFORE QApplication.quit()
    if widget.settings_manager and widget._settings_listener_connected:
        try:
            widget.settings_manager.settings_changed.disconnect(widget._on_settings_value_changed)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        finally:
            widget._settings_listener_connected = False

    # Phase 5: Unregister from MultiMonitorCoordinator
    if widget._screen is not None:
        try:
            widget._coordinator.unregister_instance(widget, widget._screen)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    # Phase 5: Release focus and event filter ownership via coordinator
    try:
        widget._coordinator.release_focus(widget)
        widget._coordinator.uninstall_event_filter(widget)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    widget._destroy_render_surface()

    # Ensure compositor is torn down cleanly
    try:
        if widget._gl_compositor is not None:
            cleanup = getattr(widget._gl_compositor, "cleanup", None)
            if callable(cleanup):
                try:
                    cleanup()
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Cleanup failed: %s", e, exc_info=True)
            widget._gl_compositor.hide()
            widget._gl_compositor.setParent(None)
            widget._gl_compositor = None
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Teardown failed: %s", e, exc_info=True)
        widget._gl_compositor = None

    # Cleanup all overlay widgets using helper
    widget._cleanup_widget("spotify_visualizer_widget", "SPOTIFY_VIS", "stop")
    widget._cleanup_widget("media_widget", "MEDIA", "cleanup")
    widget._cleanup_widget("weather_widget", "WEATHER", "cleanup")
    widget._cleanup_widget("reddit_widget", "REDDIT", "cleanup")
    widget._cleanup_widget("reddit2_widget", "REDDIT2", "cleanup")
    widget._cleanup_widget("_pixel_shift_manager", "PIXEL_SHIFT", "cleanup")

    # Cleanup cursor halo (top-level window, must be explicitly destroyed)
    try:
        if widget._ctrl_cursor_hint is not None:
            widget._ctrl_cursor_hint.hide()
            widget._ctrl_cursor_hint.deleteLater()
            widget._ctrl_cursor_hint = None
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        widget._ctrl_cursor_hint = None

    # Stop and clean up any active transition via TransitionController
    try:
        if widget._transition_controller is not None:
            widget._transition_controller.stop_current()
        elif widget._current_transition:
            try:
                widget._current_transition.stop()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                widget._current_transition.cleanup()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            widget._current_transition = None
    except Exception as e:
        logger.debug("[TRANSITION] Cleanup failed: %s", e, exc_info=True)

    # Hide overlays and cancel watchdog timer
    try:
        hide_all_overlays(widget)
    except Exception as e:
        logger.debug("[OVERLAYS] Hide failed: %s", e, exc_info=True)
    widget._cancel_transition_watchdog()
