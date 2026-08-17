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
        manager.prepare_for_runtime_pause()

    custom_layout_manager = getattr(widget, "_custom_layout_manager", None)
    if custom_layout_manager is not None:
        custom_layout_manager.cleanup()
        widget._custom_layout_manager = None

    # The visualizer owns a separate display-local GL overlay until Phase 8.
    # Require its strict deletion before any manager clears widget references.
    widget._cleanup_widget(
        "spotify_visualizer_widget",
        "SPOTIFY_VIS",
        "cleanup",
        strict=True,
    )

    if manager is not None:
        manager.cleanup()
        widget._widget_manager = None

    # Some overlays predate WidgetManager ownership. Their lifecycle methods
    # are idempotent, so clean them explicitly after the managed set.
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
            widget._transition_controller.cleanup()
            widget._transition_controller = None
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

    input_handler = getattr(widget, "_input_handler", None)
    if input_handler is not None:
        input_handler.cleanup()
        widget._input_handler = None

    image_presenter = getattr(widget, "_image_presenter", None)
    if image_presenter is not None:
        image_presenter.cleanup()
        widget._image_presenter = None

    transition_factory = getattr(widget, "_transition_factory", None)
    if transition_factory is not None:
        transition_factory.cleanup()
        widget._transition_factory = None

    try:
        if widget._ctrl_cursor_hint is not None:
            widget._ctrl_cursor_hint.hide()
            widget._ctrl_cursor_hint.close()
            widget._ctrl_cursor_hint.deleteLater()
            widget._ctrl_cursor_hint = None
    except Exception as exc:
        logger.debug("[DISPLAY_WIDGET] Cursor halo cleanup failed: %s", exc)
        widget._ctrl_cursor_hint = None

    # Release the display-owned auxiliary presentation registration before the
    # render strategy stops, so a retiring overlay can never be serviced by a
    # frame opportunity belonging to a runtime that is going away.
    try:
        from rendering.display_image_ops import _detach_overlay_presentation_owner

        _detach_overlay_presentation_owner(
            widget, getattr(widget, "_spotify_bars_overlay", None)
        )
    except Exception as exc:
        logger.debug("[DISPLAY_WIDGET] Overlay presentation detach failed: %s", exc)

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
