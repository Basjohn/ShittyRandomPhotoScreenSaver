"""Display Image Operations - Extracted from display_widget.py.

Contains image display pipeline (set_processed_image), transition finish
handling, and Spotify visualizer frame pushing.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import List, Optional, TYPE_CHECKING

import weakref

from PySide6.QtGui import QPixmap

try:
    from OpenGL import GL  # type: ignore[import]
except ImportError:
    GL = None

try:
    import shiboken6
    Shiboken = shiboken6.Shiboken
except ImportError:
    Shiboken = None

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from rendering.gl_compositor import GLCompositorWidget
from transitions.overlay_manager import GL_OVERLAY_KEYS
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

from rendering.display_widget import _describe_pixmap

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def set_processed_image(widget, processed_pixmap: QPixmap, original_pixmap: QPixmap, 
                       image_path: str = "") -> None:
    """Display an already-processed image with transition.
    
    ARCHITECTURAL NOTE: This method accepts pre-processed pixmaps to avoid
    blocking the UI thread with image scaling. The caller (typically the
    engine) should process images on a background thread and call this
    method on the UI thread with the results.
    
    Args:
        processed_pixmap: Screen-fitted pixmap ready for display
        original_pixmap: Original unprocessed pixmap (for reference)
        image_path: Path to image (for logging/events)
    """
    # If a transition is already running, skip this call (single-skip policy)
    if widget.has_running_transition():
        widget._transition_skip_count += 1
        logger.debug(
            "Transition in progress - skipping image request (skip_count=%s)",
            widget._transition_skip_count,
        )
        return

    if processed_pixmap.isNull():
        logger.warning("[FALLBACK] Received null processed pixmap")
        widget.error_message = "Failed to load image"
        widget.current_pixmap = None
        widget.update()
        return

    # Use the pre-processed pixmap directly - no UI thread blocking
    new_pixmap = processed_pixmap
    
    widget._animation_manager = None
    widget._overlay_timeouts: dict[str, float] = {}
    widget._pre_raise_log_emitted = False
    widget._base_fallback_paint_logged = False
    
    # Set DPR on the processed pixmap for proper display scaling
    processed_pixmap.setDevicePixelRatio(widget._device_pixel_ratio)
    try:
        new_pixmap.setDevicePixelRatio(widget._device_pixel_ratio)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    
    # Stop any running transition via TransitionController
    if widget._transition_controller is not None:
        widget._transition_controller.stop_current()
    elif widget._current_transition:
        transition_to_stop = widget._current_transition
        widget._current_transition = None
        try:
            transition_to_stop.stop()
            transition_to_stop.cleanup()
        except Exception as e:
            logger.warning(f"Error stopping transition: {e}")
    
    # Cache previous pixmap reference before we mutate current_pixmap
    previous_pixmap_ref = widget.current_pixmap

    # Seed base widget with the new frame before starting transitions.
    # This prevents fallback paints (black bands) while overlays warm up.
    widget.current_pixmap = processed_pixmap
    if widget.current_pixmap:
        try:
            widget.current_pixmap.setDevicePixelRatio(widget._device_pixel_ratio)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        widget._seed_pixmap = widget.current_pixmap
        widget._last_pixmap_seed_ts = time.monotonic()
        
        # Phase 4b: Notify ImagePresenter of pixmap change
        if widget._image_presenter is not None:
            try:
                widget._image_presenter.set_current(widget.current_pixmap, update_seed=True)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        if is_verbose_logging():
            logger.debug(
                "[DIAG] Seed pixmap set (phase=pre-transition, pixmap=%s)",
                _describe_pixmap(widget.current_pixmap),
            )
        if widget._updates_blocked_until_seed:
            try:
                widget.setUpdatesEnabled(True)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            widget._updates_blocked_until_seed = False

        # Pre-warm the shared GL compositor with the current frame so that
        # its GL surface is active before any animated transition starts.
        # This reduces first-use flicker, especially on secondary
        # displays, by avoiding late compositor initialization.
        try:
            widget._ensure_gl_compositor()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        comp = getattr(widget, "_gl_compositor", None)
        if isinstance(comp, GLCompositorWidget):
            try:
                comp.setGeometry(0, 0, widget.width(), widget.height())
                comp.set_base_pixmap(widget.current_pixmap)
                comp.show()
                comp.raise_()
                # Prewarm shader textures for the upcoming transition so
                # GLSL paths (Slide, Wipe, Diffuse, etc.) do not pay the
                # full texture upload cost on their first animated frame.
                try:
                    comp.warm_shader_textures(previous_pixmap_ref, new_pixmap)
                except Exception:
                    logger.debug(
                        "[GL COMPOSITOR] warm_shader_textures failed during pre-warm",
                        exc_info=True,
                    )
                # Raise all overlay widgets above the compositor ONCE here.
                # The rate-limited raise_overlay() handles ongoing raises.
                # Raise all widgets above the compositor
                for attr_name in (
                    "clock_widget", "clock2_widget", "clock3_widget",
                    "weather_widget", "media_widget", "spotify_visualizer_widget",
                    "_spotify_bars_overlay", "spotify_volume_widget", "reddit_widget",
                    "reddit2_widget", "_ctrl_cursor_hint",
                ):
                    w = getattr(widget, attr_name, None)
                    if w is not None:
                        try:
                            w.raise_()
                        except Exception as e:
                            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to pre-warm compositor with base frame", exc_info=True)

        use_transition = bool(widget.settings_manager) and widget._has_rendered_first_frame
        if widget.settings_manager and not widget._has_rendered_first_frame:
            logger.debug("[INIT] First frame - presenting without transition to avoid black flicker")

        if not widget._transitions_enabled:
            use_transition = False

        if use_transition:
            transition = widget._create_transition()
            if transition:
                # Set previous pixmap for transition
                widget.previous_pixmap = previous_pixmap_ref or processed_pixmap
                
                # For compositor-backed 3D Block Spins, seed with old image
                comp = getattr(widget, "_gl_compositor", None)
                if isinstance(comp, GLCompositorWidget):
                    try:
                        if (
                            transition.__class__.__name__ == "GLCompositorCrossfadeTransition"
                            and previous_pixmap_ref is not None
                            and not previous_pixmap_ref.isNull()
                        ):
                            comp.set_base_pixmap(previous_pixmap_ref)
                        elif (
                            transition.__class__.__name__ == "GLCompositorBlockSpinTransition"
                            and previous_pixmap_ref is not None
                            and not previous_pixmap_ref.isNull()
                        ):
                            comp.set_base_pixmap(previous_pixmap_ref)
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

                widget._warm_transition_if_needed(
                    comp,
                    transition.__class__.__name__,
                    widget.previous_pixmap,
                    new_pixmap,
                )

                # Store pending finish args
                widget._pending_transition_finish_args = (processed_pixmap, original_pixmap, image_path, False, None)
                
                # Create finish handler with weakref
                self_ref = weakref.ref(widget)
                def _finish_handler(np=processed_pixmap, op=original_pixmap, ip=image_path, ref=self_ref):
                    widget = ref()
                    if widget is None or not Shiboken.isValid(widget):
                        return
                    try:
                        widget._pending_transition_finish_args = (np, op, ip, False, None)
                        widget._on_transition_finished(np, op, ip, False, None)
                    finally:
                        widget._pending_transition_finish_args = None

                # Delegate transition start to TransitionController
                overlay_key = widget._resolve_overlay_key_for_transition(transition)
                if widget._transition_controller is not None:
                    success = widget._transition_controller.start_transition(
                        transition, widget.previous_pixmap, new_pixmap,
                        overlay_key=overlay_key, on_finished=_finish_handler
                    )
                else:
                    # Fallback: direct start
                    transition.finished.connect(_finish_handler)
                    success = transition.start(widget.previous_pixmap, new_pixmap, widget)
                
                if success:
                    widget._current_transition = transition
                    widget._current_transition_overlay_key = overlay_key
                    widget._current_transition_started_at = time.monotonic()
                    widget._current_transition_name = transition.__class__.__name__
                    widget._current_transition_first_run = (
                        widget._current_transition_name not in widget._warmed_transition_types
                    )
                    if is_perf_metrics_enabled():
                        logger.info(
                            "[PERF] [TRANSITION] Start name=%s first_run=%s overlay=%s",
                            widget._current_transition_name,
                            widget._current_transition_first_run,
                            overlay_key or "<none>",
                        )
                    if overlay_key:
                        widget._overlay_timeouts[overlay_key] = widget._current_transition_started_at
                    # Raise widgets SYNCHRONOUSLY
                    if widget._widget_manager is not None:
                        try:
                            widget._widget_manager.raise_all_widgets()
                        except Exception as e:
                            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    for attr in ("_spotify_bars_overlay", "_ctrl_cursor_hint"):
                        w = getattr(widget, attr, None)
                        if w is not None:
                            try:
                                w.raise_()
                            except Exception as e:
                                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    logger.debug(f"Transition started: {transition.__class__.__name__}")
                    return
                else:
                    logger.warning("Transition failed to start, displaying immediately")
                    transition.cleanup()
                    widget._current_transition = None
                    widget._current_transition_name = None
                    widget._current_transition_first_run = False
                    widget._pending_transition_finish_args = None
                    use_transition = False
            else:
                use_transition = False

        if not use_transition:
            widget._pending_transition_finish_args = None
            widget._cancel_transition_watchdog()
            # No transition - display immediately
            widget.previous_pixmap = None
            widget.update()
            if GL is None:
                try:
                    widget._mark_all_overlays_ready(GL_OVERLAY_KEYS, stage="software_display")
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

            try:
                widget._ensure_overlay_stack(stage="display")
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

            logger.debug(f"Image displayed: {image_path} ({processed_pixmap.width()}x{processed_pixmap.height()})")
            widget.current_image_path = image_path
            widget.image_displayed.emit(image_path)
            widget._has_rendered_first_frame = True

def _on_transition_finished(
    widget,
    new_pixmap: QPixmap,
    original_pixmap: QPixmap,
    image_path: str,
    pan_enabled: bool,
    pan_preview: Optional[QPixmap] = None,
) -> None:
    """Handle transition completion."""
    # Delegate cleanup to TransitionController
    if widget._transition_controller is not None:
        try:
            widget._transition_controller.on_transition_finished()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    
    # Clear local state
    widget._current_transition_overlay_key = None
    widget._current_transition_started_at = 0.0
    widget._current_transition = None
    if widget._current_transition_name:
        widget._warmed_transition_types.add(widget._current_transition_name)
        widget._last_transition_name = widget._current_transition_name
    widget._current_transition_name = None
    widget._current_transition_first_run = False
    widget._last_transition_finished_wall_ts = time.time()

    # Update pixmap state
    widget.current_pixmap = pan_preview or new_pixmap
    if widget.current_pixmap:
        try:
            widget.current_pixmap.setDevicePixelRatio(widget._device_pixel_ratio)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    widget._seed_pixmap = widget.current_pixmap
    widget._last_pixmap_seed_ts = time.monotonic()
    
    # Notify ImagePresenter
    if widget._image_presenter is not None:
        try:
            widget._image_presenter.complete_transition(new_pixmap, pan_preview)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    
    if widget._updates_blocked_until_seed:
        try:
            widget.setUpdatesEnabled(True)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        widget._updates_blocked_until_seed = False
    widget.previous_pixmap = None

    # Ensure overlays and repaint
    try:
        widget._ensure_overlay_stack(stage="transition_finish")
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    widget.update()

    try:
        logger.debug("Transition completed, image displayed: %s", image_path)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    widget.current_image_path = image_path
    widget.image_displayed.emit(image_path)
    widget._pending_transition_finish_args = None

def push_spotify_visualizer_frame(
    widget,
    *,
    bars,
    bar_count,
    segments,
    fill_color,
    border_color,
    fade,
    playing,
    ghosting_enabled=True,
    ghost_alpha=0.4,
    ghost_decay=-1.0,
    vis_mode="spectrum",
    **extra_kwargs,
):
    vis = getattr(widget, "spotify_visualizer_widget", None)
    if vis is None:
        return False

    try:
        if not vis.isVisible():
            return False
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return False

    try:
        geom = vis.geometry()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return False

    if geom.width() <= 0 or geom.height() <= 0:
        return False

    # Lazily create a small GL overlay dedicated to Spotify bars. This
    # sits above the card widget in Z-order while the card itself remains
    # a normal QWidget with ShadowFadeProfile-driven opacity.
    overlay = getattr(widget, "_spotify_bars_overlay", None)
    if overlay is None or not isinstance(overlay, SpotifyBarsGLOverlay):
        try:
            overlay = SpotifyBarsGLOverlay(widget)
            overlay.setObjectName("spotify_bars_gl_overlay")
            widget._spotify_bars_overlay = overlay
            if widget._resource_manager is not None:
                try:
                    widget._resource_manager.register_qt(
                        overlay,
                        description="Spotify bars GL overlay",
                    )
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Failed to register SpotifyBarsGLOverlay", exc_info=True)
            pixel_shift_manager = getattr(widget, "_pixel_shift_manager", None)
            if pixel_shift_manager is not None:
                try:
                    pixel_shift_manager.register_widget(overlay)
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Failed to register GL overlay with PixelShiftManager", exc_info=True)
        except Exception:
            logger.debug("[DISPLAY_WIDGET] Failed to initialize SpotifyBarsGLOverlay", exc_info=True)
            widget._widget._spotify_bars_overlay = None
            return False

    if overlay is None:
        logger.warning("[SPOTIFY_VIS] Missing SpotifyBarsGLOverlay after initialization; visualizer bars will be blank")
        return False

    if not hasattr(overlay, "clear_overlay_buffer"):
        module_name = type(overlay).__module__
        module = sys.modules.get(module_name)
        module_path = getattr(module, "__file__", "<unknown>")
        logger.critical(
            "[SPOTIFY_VIS] SpotifyBarsGLOverlay missing clear_overlay_buffer (module=%s path=%s). "
            "Ensure code reload or delete stale pyc files.",
            module_name,
            module_path,
        )
        raise RuntimeError("SpotifyBarsGLOverlay missing clear_overlay_buffer; stale build detected")

    try:
        overlay_kwargs = {
            "rect": geom,
            "bars": bars,
            "bar_count": bar_count,
            "segments": segments,
            "fill_color": fill_color,
            "border_color": border_color,
            "fade": fade,
            "playing": playing,
            "visible": True,
            "ghosting_enabled": ghosting_enabled,
            "ghost_alpha": ghost_alpha,
            "ghost_decay": ghost_decay,
            "vis_mode": vis_mode,
        }
        overlay_kwargs.update(extra_kwargs)

        try:
            overlay.set_state(**overlay_kwargs)
        except TypeError as exc:
            # Fallback: strip keys the current overlay implementation does not accept.
            unexpected = []
            msg = str(exc)
            if "got an unexpected keyword argument" in msg:
                # extract the offending arg name to remove it and retry.
                start = msg.find("'")
                end = msg.find("'", start + 1)
                if start != -1 and end != -1:
                    unexpected.append(msg[start + 1:end])
            if unexpected:
                for key in unexpected:
                    overlay_kwargs.pop(key, None)
                overlay.set_state(**overlay_kwargs)
            else:
                raise
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to push frame to SpotifyBarsGLOverlay", exc_info=True)
        return False

    return True

