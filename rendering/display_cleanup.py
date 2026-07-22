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
    if bool(getattr(widget, "_destroy_cleanup_done", False)):
        return
    widget._destroy_cleanup_done = True

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

    # Reconcile transition/controller state before visualizer or compositor GL
    # resources are touched. Cancellation is signal-suppressed by the
    # controller, so teardown cannot re-enter normal image completion.
    try:
        from rendering.display_image_ops import _clear_deferred_processed_image

        _clear_deferred_processed_image(widget, clear_pending=True)
        if widget._transition_controller is not None:
            widget._transition_controller.begin_quiesce(
                reason="display_destroy",
                snap_to_new=True,
            )
        elif widget._current_transition:
            transition = widget._current_transition
            widget._current_transition = None
            try:
                transition.stop()
            finally:
                transition.cleanup()
    except Exception:
        logger.error("[TRANSITION] Pre-GL teardown reconciliation failed", exc_info=True)

    # Release the visualizer renderer target before tearing down the owning
    # compositor/context. This covers both the normal compositor layer and the
    # environment-forced legacy child-surface adapter.
    widget._cleanup_widget("spotify_visualizer_widget", "SPOTIFY_VIS", "cleanup")

    # Ensure compositor is torn down cleanly
    try:
        if widget._gl_compositor is not None:
            cleanup = getattr(widget._gl_compositor, "cleanup", None)
            if callable(cleanup):
                cleanup()
            widget._gl_compositor.hide()
            widget._gl_compositor.setParent(None)
            widget._gl_compositor = None
    except Exception:
        widget._destroy_cleanup_done = False
        logger.critical("[GL COMPOSITOR] Teardown failed before ownership release", exc_info=True)
        raise

    widget._destroy_render_surface()

    # Cleanup all overlay widgets using helper
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

    # Hide overlays and cancel watchdog timer
    try:
        hide_all_overlays(widget)
    except Exception as e:
        logger.debug("[OVERLAYS] Hide failed: %s", e, exc_info=True)
    widget._cancel_transition_watchdog()
