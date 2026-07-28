"""DisplayWidget runtime teardown.

The normal path is explicit and synchronous: DisplayManager invokes
``cleanup_runtime`` while the compositor and its GL context still exist.  The
QObject ``destroyed`` signal is only a residual safety net.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.logger import get_logger
from transitions.overlay_manager import hide_all_overlays

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget

logger = get_logger(__name__)


def cleanup_runtime(widget: "DisplayWidget", *, reason: str) -> None:
    """Stop producers, destroy GL resources, then destroy render surfaces."""
    if bool(getattr(widget, "_runtime_cleanup_complete", False)):
        return

    widget.shutdown_render_pipeline(reason)

    manager = getattr(widget, "_widget_manager", None)
    if manager is not None:
        manager.cleanup()

    # Some overlays predate WidgetManager ownership. Their lifecycle methods
    # are idempotent, so clean them explicitly after the managed set.
    widget._cleanup_widget("spotify_visualizer_widget", "SPOTIFY_VIS", "cleanup")
    widget._cleanup_widget("media_widget", "MEDIA", "cleanup")
    widget._cleanup_widget("weather_widget", "WEATHER", "cleanup")
    widget._cleanup_widget("reddit_widget", "REDDIT", "cleanup")
    widget._cleanup_widget("reddit2_widget", "REDDIT2", "cleanup")
    widget._cleanup_widget("_pixel_shift_manager", "PIXEL_SHIFT", "cleanup")

    if widget.settings_manager and widget._settings_listener_connected:
        try:
            widget.settings_manager.settings_changed.disconnect(
                widget._on_settings_value_changed
            )
        except Exception as exc:
            logger.debug("[DISPLAY_WIDGET] Settings disconnect failed: %s", exc)
        finally:
            widget._settings_listener_connected = False

    if widget._screen is not None:
        try:
            widget._coordinator.unregister_instance(widget, widget._screen)
        except Exception as exc:
            logger.debug("[DISPLAY_WIDGET] Coordinator unregister failed: %s", exc)

    try:
        widget._coordinator.release_focus(widget)
        widget._coordinator.uninstall_event_filter(widget)
    except Exception as exc:
        logger.debug("[DISPLAY_WIDGET] Coordinator release failed: %s", exc)

    try:
        if widget._transition_controller is not None:
            widget._transition_controller.stop_current(reason=reason)
        elif widget._current_transition:
            widget._current_transition.stop()
            widget._current_transition.cleanup()
            widget._current_transition = None
    except Exception as exc:
        logger.debug("[TRANSITION] Cleanup failed: %s", exc, exc_info=True)

    try:
        hide_all_overlays(widget)
    except Exception as exc:
        logger.debug("[OVERLAYS] Hide failed: %s", exc, exc_info=True)
    widget._cancel_transition_watchdog()

    try:
        if widget._ctrl_cursor_hint is not None:
            widget._ctrl_cursor_hint.hide()
            widget._ctrl_cursor_hint.close()
            widget._ctrl_cursor_hint.deleteLater()
            widget._ctrl_cursor_hint = None
    except Exception as exc:
        logger.debug("[DISPLAY_WIDGET] Cursor halo cleanup failed: %s", exc)
        widget._ctrl_cursor_hint = None

    # GL resources must be deleted while their QOpenGLWidget/context is still
    # alive. cleanup() deliberately raises if live resources cannot acquire the
    # context; do not destroy the surface and make the leak unrecoverable.
    compositor = getattr(widget, "_gl_compositor", None)
    if compositor is not None:
        compositor.cleanup()
        from rendering.gl_compositor_pkg.gl_lifecycle import gl_pipeline_has_live_resources
        if gl_pipeline_has_live_resources(compositor):
            raise RuntimeError("Compositor cleanup returned with live GL resources")
        compositor.hide()
        compositor.setParent(None)
        compositor.deleteLater()
        widget._gl_compositor = None

    widget._destroy_render_surface()
    widget._runtime_cleanup_complete = True
    logger.info(
        "[LIFECYCLE] Display runtime cleanup complete screen=%s reason=%s",
        getattr(widget, "screen_index", "unknown"),
        reason,
    )


def on_destroyed(widget: "DisplayWidget", *_args) -> None:
    """Residual safety net; normal teardown must finish before destruction."""
    try:
        cleanup_runtime(widget, reason="qobject_destroyed_fallback")
    except Exception:
        logger.critical(
            "[LIFECYCLE] Display reached QObject destruction before clean runtime teardown",
            exc_info=True,
        )