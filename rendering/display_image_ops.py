"""Display Image Operations - Extracted from display_widget.py.

Contains image display pipeline (set_processed_image), transition finish
handling, and Spotify visualizer frame pushing.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional, TYPE_CHECKING

import weakref

from PySide6.QtCore import QRect
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
from widgets.spotify_visualizer.frame_transport import VisualizerFramePacket
from rendering.gl_compositor_pkg.spotify_visualizer_layer import (
    CompositorSpotifyVisualizerLayer,
    single_surface_visualizer_enabled,
)

from rendering.display_widget import _describe_pixmap

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")

_TRANSITION_ADMISSION_RETRY_DELAYS_MS = (125, 375, 1000, 2500)


def _raise_runtime_widgets_above_compositor(widget, *, stage: str) -> None:
    """Synchronously restore runtime widget stacking after compositor use.

    GL compositor-backed transitions raise the compositor before they know
    whether the shader path will actually start. If a transition refuses after
    that point, the final image can be displayed with the compositor still
    above all overlay widgets. Use the WidgetManager owner rather than adding
    another handwritten widget inventory here.
    """

    manager = getattr(widget, "_widget_manager", None)
    if manager is not None:
        try:
            manager.raise_all_widgets()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to raise runtime widgets after %s: %s", stage, e)

    for attr in ("_spotify_bars_overlay", "_ctrl_cursor_hint"):
        overlay = getattr(widget, attr, None)
        if overlay is None:
            continue
        try:
            overlay.raise_()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to raise %s after %s: %s", attr, stage, e)


def _complete_startup_first_frame_ready(widget, image_path: str, token: int) -> None:
    """Mark the startup first frame as truly ready after a presentation flush."""
    if int(getattr(widget, "_pending_startup_frame_token", 0)) != token:
        return

    setattr(widget, "_pending_startup_frame_image_path", None)
    setattr(widget, "_pending_startup_frame_token", 0)

    widget.current_image_path = image_path
    widget._has_rendered_first_frame = True
    widget._first_frame_committed_ts = time.monotonic()
    widget._first_frame_committed_image_path = image_path

    requested_ts = getattr(widget, "_startup_first_frame_requested_ts", None)
    elapsed_ms = None
    if isinstance(requested_ts, (int, float)):
        try:
            elapsed_ms = (time.monotonic() - float(requested_ts)) * 1000.0
        except Exception:
            elapsed_ms = None
    widget._startup_first_frame_requested_ts = None

    if is_perf_metrics_enabled() or is_verbose_logging():
        logger.info(
            "[STARTUP] First frame committed on screen=%s image=%s elapsed_ms=%s",
            getattr(widget, "screen_index", "?"),
            image_path,
            f"{elapsed_ms:.2f}" if elapsed_ms is not None else "N/A",
        )

    widget.image_displayed.emit(image_path)
    if hasattr(widget, "set_transition_work_pending"):
        widget.set_transition_work_pending(False)


def _schedule_startup_first_frame_ready(widget, image_path: str) -> None:
    """Defer startup readiness through the app ThreadManager handoff.

    This deliberately avoids QTimer lifecycle nudges and forced repaint().
    The caller already queues the normal widget update; this seam only delays
    readiness publication so deleted/stale widgets cannot win the startup race.
    """
    token = int(getattr(widget, "_pending_startup_frame_token", 0)) + 1
    setattr(widget, "_pending_startup_frame_token", token)
    setattr(widget, "_pending_startup_frame_image_path", image_path)
    setattr(widget, "_startup_first_frame_requested_ts", time.monotonic())

    if is_verbose_logging():
        logger.debug(
            "[STARTUP] Arming first-frame ready flush on screen=%s image=%s token=%s",
            getattr(widget, "screen_index", "?"),
            image_path,
            token,
        )

    def _complete_when_current() -> None:
        if int(getattr(widget, "_pending_startup_frame_token", 0)) != token:
            return
        _complete_startup_first_frame_ready(widget, image_path, token)

    thread_manager = getattr(widget, "_thread_manager", None)
    if thread_manager is not None and hasattr(thread_manager, "single_shot"):
        try:
            thread_manager.single_shot(0, _complete_when_current)
            return
        except Exception:
            logger.warning(
                "[STARTUP][FALLBACK] ThreadManager first-frame readiness handoff failed; completing inline",
                exc_info=True,
            )
    else:
        logger.warning(
            "[STARTUP][FALLBACK] ThreadManager unavailable for first-frame readiness; completing inline"
        )
    _complete_when_current()


def _is_live_widget(widget) -> bool:
    if Shiboken is None:
        return True
    try:
        return bool(Shiboken.isValid(widget))
    except Exception:
        return False


def _clear_deferred_processed_image(widget, *, clear_pending: bool = False) -> None:
    """Release one retained prepared frame and invalidate scheduled retries."""

    widget._deferred_processed_image_retry_token = (
        int(getattr(widget, "_deferred_processed_image_retry_token", 0)) + 1
    )
    widget._deferred_processed_image = None
    widget._deferred_processed_image_retry_attempts = 0
    widget._deferred_processed_image_retry_scheduled = False
    widget._deferred_processed_image_retry_in_progress = False
    if clear_pending and hasattr(widget, "set_transition_work_pending"):
        widget.set_transition_work_pending(False)


def _restore_visible_pixmap(widget, previous_pixmap: Optional[QPixmap]) -> None:
    """Restore the last committed frame after transition admission refuses."""

    widget.current_pixmap = previous_pixmap
    widget.previous_pixmap = None
    widget._seed_pixmap = previous_pixmap
    widget._last_pixmap_seed_ts = time.monotonic()

    presenter = getattr(widget, "_image_presenter", None)
    if presenter is not None and previous_pixmap is not None:
        try:
            presenter.set_current(previous_pixmap, update_seed=True)
        except Exception:
            logger.debug(
                "[DISPLAY_WIDGET] Failed to restore presenter after transition refusal",
                exc_info=True,
            )

    comp = getattr(widget, "_gl_compositor", None)
    if comp is not None and previous_pixmap is not None:
        try:
            comp.set_base_pixmap(previous_pixmap)
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] Failed to restore committed base frame",
                exc_info=True,
            )
    try:
        widget.update()
    except Exception:
        logger.debug(
            "[DISPLAY_WIDGET] Failed to repaint restored committed frame",
            exc_info=True,
        )


def _schedule_deferred_processed_image_retry(
    widget,
    *,
    reason: str,
    immediate: bool = False,
) -> bool:
    """Retry one retained frame without creating a paint-owned retry loop."""

    payload = getattr(widget, "_deferred_processed_image", None)
    if payload is None:
        return False
    if bool(getattr(widget, "_deferred_processed_image_retry_scheduled", False)):
        return False
    if widget.has_running_transition():
        return False

    attempts = int(getattr(widget, "_deferred_processed_image_retry_attempts", 0))
    if attempts >= len(_TRANSITION_ADMISSION_RETRY_DELAYS_MS):
        logger.error(
            "[TRANSITION][BLOCKED] Prepared frame remains deferred after admission retries "
            "screen=%s image=%s attempts=%s reason=%s",
            getattr(widget, "screen_index", "?"),
            payload[2],
            attempts,
            reason,
        )
        return False

    delay_ms = 0 if immediate else _TRANSITION_ADMISSION_RETRY_DELAYS_MS[attempts]
    token = int(getattr(widget, "_deferred_processed_image_retry_token", 0)) + 1
    widget._deferred_processed_image_retry_token = token
    widget._deferred_processed_image_retry_scheduled = True
    widget_ref = weakref.ref(widget)

    def _retry() -> None:
        target = widget_ref()
        if target is None or not _is_live_widget(target):
            return
        if token != int(getattr(target, "_deferred_processed_image_retry_token", 0)):
            return
        target._deferred_processed_image_retry_scheduled = False
        if target.has_running_transition():
            return

        retained = getattr(target, "_deferred_processed_image", None)
        if retained is None:
            return
        target._deferred_processed_image = None
        target._deferred_processed_image_retry_in_progress = True
        try:
            set_processed_image(target, retained[0], retained[1], retained[2])
        finally:
            target._deferred_processed_image_retry_in_progress = False

    scheduler = getattr(widget, "_thread_manager", None)
    try:
        if scheduler is not None and hasattr(scheduler, "single_shot"):
            scheduler.single_shot(delay_ms, _retry)
        else:
            from core.threading.manager import ThreadManager

            ThreadManager.single_shot(delay_ms, _retry)
        logger.warning(
            "[TRANSITION][DEFER] Prepared frame retry armed screen=%s image=%s "
            "delay_ms=%s attempt=%s reason=%s",
            getattr(widget, "screen_index", "?"),
            payload[2],
            delay_ms,
            attempts + 1,
            reason,
        )
        return True
    except Exception:
        widget._deferred_processed_image_retry_scheduled = False
        logger.error(
            "[TRANSITION][BLOCKED] Failed to schedule retained prepared frame screen=%s",
            getattr(widget, "screen_index", "?"),
            exc_info=True,
        )
        return False


def _stage_deferred_processed_image(
    widget,
    processed_pixmap: QPixmap,
    original_pixmap: QPixmap,
    image_path: str,
    *,
    reason: str,
    schedule_retry: bool,
) -> None:
    """Retain the first accepted prepared frame while the old image stays visible."""

    existing = getattr(widget, "_deferred_processed_image", None)
    if existing is None:
        widget._deferred_processed_image = (
            processed_pixmap,
            original_pixmap,
            image_path,
        )
        widget._transition_defer_count = (
            int(getattr(widget, "_transition_defer_count", 0)) + 1
        )
    elif existing[2] != image_path:
        logger.error(
            "[TRANSITION][ERROR] Additional prepared frame arrived while one was already retained; "
            "preserving first accepted frame screen=%s retained=%s rejected=%s",
            getattr(widget, "screen_index", "?"),
            existing[2],
            image_path,
        )

    if bool(getattr(widget, "_deferred_processed_image_retry_in_progress", False)):
        widget._deferred_processed_image_retry_attempts = (
            int(getattr(widget, "_deferred_processed_image_retry_attempts", 0)) + 1
        )

    if hasattr(widget, "set_transition_work_pending"):
        widget.set_transition_work_pending(True)
    logger.warning(
        "[TRANSITION][DEFER] Prepared frame retained behind committed image "
        "screen=%s image=%s reason=%s",
        getattr(widget, "screen_index", "?"),
        image_path,
        reason,
    )
    if schedule_retry:
        _schedule_deferred_processed_image_retry(widget, reason=reason)


def _ensure_transition_admitted(widget, transition) -> bool:
    """Prove compositor program readiness before visible state can change."""

    transition_name = transition.__class__.__name__
    if not transition_name.startswith("GLCompositor"):
        return True
    comp = getattr(widget, "_gl_compositor", None)
    if not isinstance(comp, GLCompositorWidget):
        return False
    try:
        return bool(
            comp._ensure_gl_pipeline_ready()
            and comp._ensure_transition_program_ready(transition_name)
        )
    except Exception:
        logger.debug(
            "[TRANSITION] Compositor admission preflight failed for %s",
            transition_name,
            exc_info=True,
        )
        return False


def _on_deferred_transition_start_failed(
    widget,
    transition_label: str,
    reason: str,
) -> None:
    """Roll a delayed compositor refusal back without exposing its destination."""

    if not _is_live_widget(widget) or bool(
        getattr(widget, "_render_shutdown_requested", False)
    ):
        return

    payload = getattr(widget, "_pending_transition_finish_args", None)
    previous_pixmap = getattr(widget, "previous_pixmap", None)
    logger.error(
        "[TRANSITION][DEFER] Compositor work failed after acceptance; preserving old frame "
        "screen=%s transition=%s reason=%s image=%s",
        getattr(widget, "screen_index", "?"),
        transition_label,
        reason,
        payload[2] if payload else "<none>",
    )

    controller = getattr(widget, "_transition_controller", None)
    if controller is not None:
        controller.abort_current_preserving_old(reason)
    else:
        compositor = getattr(widget, "_gl_compositor", None)
        if compositor is not None:
            try:
                compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug(
                    "[TRANSITION] Failed to cancel compositor after deferred refusal",
                    exc_info=True,
                )

    widget._current_transition = None
    widget._current_transition_overlay_key = None
    widget._current_transition_started_at = 0.0
    widget._current_transition_expected_duration_ms = 0
    widget._current_transition_name = None
    widget._current_transition_first_run = False
    widget._pending_transition_finish_args = None
    widget._cancel_transition_watchdog()
    _restore_visible_pixmap(widget, previous_pixmap)
    _raise_runtime_widgets_above_compositor(
        widget,
        stage="deferred_transition_refused",
    )

    if payload is None:
        if hasattr(widget, "set_transition_work_pending"):
            widget.set_transition_work_pending(False)
        logger.error(
            "[TRANSITION][BLOCKED] Deferred transition failure had no retained payload "
            "screen=%s transition=%s",
            getattr(widget, "screen_index", "?"),
            transition_label,
        )
        return

    _stage_deferred_processed_image(
        widget,
        payload[0],
        payload[1],
        payload[2],
        reason=reason,
        schedule_retry=True,
    )


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
    if (
        getattr(widget, "_deferred_processed_image", None) is not None
        and not bool(getattr(widget, "_deferred_processed_image_retry_in_progress", False))
    ):
        _stage_deferred_processed_image(
            widget,
            processed_pixmap,
            original_pixmap,
            image_path,
            reason="retained_frame_already_pending",
            schedule_retry=False,
        )
        return

    # A prepared frame is retained until the active transition finishes.
    if widget.has_running_transition():
        _stage_deferred_processed_image(
            widget,
            processed_pixmap,
            original_pixmap,
            image_path,
            reason="transition_in_progress",
            schedule_retry=False,
        )
        return

    if processed_pixmap.isNull():
        if hasattr(widget, "set_transition_work_pending"):
            widget.set_transition_work_pending(False)
        logger.warning("[CACHE][FALLBACK] Received null processed pixmap")
        widget.error_message = "Failed to load image"
        widget.current_pixmap = None
        widget.update()
        return

    # Use the pre-processed pixmap directly - no UI thread blocking
    new_pixmap = processed_pixmap
    
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
                # Restore runtime widget stacking after compositor prewarm
                # without maintaining a stale handwritten widget inventory.
                _raise_runtime_widgets_above_compositor(widget, stage="compositor_prewarm")
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
                if not _ensure_transition_admitted(widget, transition):
                    try:
                        transition.cleanup()
                    except Exception:
                        logger.debug(
                            "[TRANSITION] Failed to cleanup unadmitted transition",
                            exc_info=True,
                        )
                    _restore_visible_pixmap(widget, previous_pixmap_ref)
                    _raise_runtime_widgets_above_compositor(
                        widget,
                        stage="transition_admission_refused",
                    )
                    _stage_deferred_processed_image(
                        widget,
                        processed_pixmap,
                        original_pixmap,
                        image_path,
                        reason="program_admission_refused",
                        schedule_retry=True,
                    )
                    return

                # Set previous pixmap for transition
                widget.previous_pixmap = previous_pixmap_ref or processed_pixmap
                
                # For compositor-backed transitions, keep the old frame visible
                # until the delayed/shared desync start actually begins.
                comp = getattr(widget, "_gl_compositor", None)
                if isinstance(comp, GLCompositorWidget):
                    try:
                        if (
                            transition.__class__.__name__.startswith("GLCompositor")
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
                    if widget is None or not _is_live_widget(widget):
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
                    deferred_start = False
                    try:
                        deferred_start = bool(transition.uses_deferred_start_telemetry())
                    except Exception:
                        deferred_start = False
                    widget._current_transition_started_at = 0.0 if deferred_start else time.monotonic()
                    widget._current_transition_expected_duration_ms = transition.get_expected_duration_ms()
                    widget._current_transition_name = transition.__class__.__name__
                    widget._current_transition_first_run = (
                        widget._current_transition_name not in widget._warmed_transition_types
                        and widget._current_transition_name not in widget._prewarmed_transition_types
                    )
                    _clear_deferred_processed_image(widget)
                    if hasattr(widget, "set_transition_work_pending"):
                        widget.set_transition_work_pending(False)
                    if is_perf_metrics_enabled():
                        logger.info(
                            "[PERF] [TRANSITION] Start name=%s first_run=%s overlay=%s",
                            widget._current_transition_name,
                            widget._current_transition_first_run,
                            overlay_key or "<none>",
                        )
                    if overlay_key:
                        widget._overlay_timeouts[overlay_key] = widget._current_transition_started_at
                    # Raise widgets SYNCHRONOUSLY after compositor start.
                    _raise_runtime_widgets_above_compositor(widget, stage="transition_start")
                    logger.debug(f"Transition started: {transition.__class__.__name__}")
                    return
                else:
                    logger.error(
                        "[TRANSITION][DEFER] Transition refused/failed to start; retaining committed image "
                        "screen=%s transition=%s overlay=%s",
                        getattr(widget, "screen_index", "?"),
                        transition.__class__.__name__,
                        overlay_key or "<none>",
                    )
                    if widget._transition_controller is None:
                        transition.cleanup()
                    widget._current_transition = None
                    widget._current_transition_name = None
                    widget._current_transition_first_run = False
                    widget._pending_transition_finish_args = None
                    widget._cancel_transition_watchdog()
                    _restore_visible_pixmap(widget, previous_pixmap_ref)
                    _raise_runtime_widgets_above_compositor(widget, stage="transition_refused")
                    _stage_deferred_processed_image(
                        widget,
                        processed_pixmap,
                        original_pixmap,
                        image_path,
                        reason="transition_start_refused",
                        schedule_retry=True,
                    )
                    return
            else:
                _restore_visible_pixmap(widget, previous_pixmap_ref)
                _stage_deferred_processed_image(
                    widget,
                    processed_pixmap,
                    original_pixmap,
                    image_path,
                    reason="transition_factory_unavailable",
                    schedule_retry=True,
                )
                return

        if not use_transition:
            _clear_deferred_processed_image(widget)
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
            if widget._has_rendered_first_frame:
                widget.current_image_path = image_path
                widget.image_displayed.emit(image_path)
                if hasattr(widget, "set_transition_work_pending"):
                    widget.set_transition_work_pending(False)
            else:
                _schedule_startup_first_frame_ready(widget, image_path)

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
    widget._current_transition_expected_duration_ms = 0
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
    try:
        widget.transition_completed.emit()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Transition completed signal failed: %s", e)
    widget.image_displayed.emit(image_path)
    widget._pending_transition_finish_args = None
    if getattr(widget, "_deferred_processed_image", None) is not None:
        _schedule_deferred_processed_image_retry(
            widget,
            reason="prior_transition_completed",
            immediate=True,
        )

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

    allow_hidden_startup_priming = False
    try:
        if not vis.isVisible():
            allow_hidden_startup_priming = bool(
                getattr(vis, "_startup_reveal_pending", False)
                or getattr(vis, "_waiting_for_fresh_frame", False)
                or getattr(vis, "_waiting_for_fresh_engine_frame", False)
            )
            if not allow_hidden_startup_priming:
                return False
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return False

    geom = _resolve_spotify_visualizer_overlay_rect(vis)
    if geom is None:
        return False

    if geom.width() <= 0 or geom.height() <= 0:
        return False

    overlay = _ensure_spotify_bars_overlay(widget)
    if overlay is None:
        return False

    # Border width is needed so the GL stencil mask can inset by border_width/2
    # and avoid bleeding over the pen stroke drawn centred on the card path.
    try:
        border_width = int(vis._border_width)
    except Exception:
        border_width = 0
    extra_kwargs.pop("border_width_px", None)

    return _push_spotify_bars_overlay_state(
        widget,
        overlay=overlay,
        geom=geom,
        bars=bars,
        bar_count=bar_count,
        segments=segments,
        fill_color=fill_color,
        border_color=border_color,
        fade=fade,
        playing=playing,
        ghosting_enabled=ghosting_enabled,
        ghost_alpha=ghost_alpha,
        ghost_decay=ghost_decay,
        vis_mode=vis_mode,
        visible=True,
        border_width_px=border_width,
        extra_kwargs=extra_kwargs,
    )


def push_spotify_visualizer_frame_packet(
    widget,
    packet: VisualizerFramePacket,
) -> bool:
    """Push a reusable frame packet through the real DisplayWidget fast path."""
    vis = getattr(widget, "spotify_visualizer_widget", None)
    if vis is None:
        return False

    allow_hidden_startup_priming = False
    try:
        if not vis.isVisible():
            allow_hidden_startup_priming = bool(
                getattr(vis, "_startup_reveal_pending", False)
                or getattr(vis, "_waiting_for_fresh_frame", False)
                or getattr(vis, "_waiting_for_fresh_engine_frame", False)
            )
            if not allow_hidden_startup_priming:
                return False
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return False

    geom = _resolve_spotify_visualizer_overlay_rect(vis)
    if geom is None or geom.width() <= 0 or geom.height() <= 0:
        return False

    overlay = _ensure_spotify_bars_overlay(widget)
    if overlay is None:
        return False

    try:
        border_width = int(vis._border_width)
    except Exception:
        border_width = 0

    return _push_spotify_bars_overlay_state(
        widget,
        overlay=overlay,
        geom=geom,
        bars=packet.bars,
        bar_count=packet.bar_count,
        segments=packet.segments,
        fill_color=packet.fill_color,
        border_color=packet.border_color,
        fade=packet.fade,
        playing=packet.playing,
        ghosting_enabled=packet.ghosting_enabled,
        ghost_alpha=packet.ghost_alpha,
        ghost_decay=packet.ghost_decay,
        vis_mode=packet.vis_mode,
        visible=True,
        border_width_px=border_width,
        extra_kwargs=packet.extra_kwargs,
    )


def prewarm_spotify_visualizer_overlay(widget) -> bool:
    """Create and initialize the Spotify GL overlay before the first visible frame."""

    vis = getattr(widget, "spotify_visualizer_widget", None)
    if vis is None:
        return False

    geom = _resolve_spotify_visualizer_overlay_rect(vis)
    if geom is None:
        return False

    if geom.width() <= 0 or geom.height() <= 0:
        return False

    overlay = _ensure_spotify_bars_overlay(widget)
    if overlay is None:
        return False

    startup_mode = ""
    try:
        # Keep deferred shader warmup aligned with the real startup mode rather than
        # the overlay's historical internal default.
        startup_mode = str(getattr(vis, "_vis_mode_str", "") or "").strip().lower()
        if startup_mode:
            setattr(overlay, "_vis_mode", startup_mode)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to seed overlay startup mode before prewarm", exc_info=True)

    try:
        from widgets.spotify_visualizer.shaders import preload_fragment_shaders

        # Prime the shared shader-source cache before the GL widget asks for
        # program creation so startup hot-path work does not include file IO.
        preload_fragment_shaders()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to preload visualizer shader sources", exc_info=True)
        _set_visualizer_surface_terminal_reason(
            widget,
            "shader_source_preload_failed",
        )
        return False

    try:
        if hasattr(overlay, "prewarm_context"):
            overlay.prewarm_context(geom)
        else:
            overlay.setGeometry(geom)
            overlay.show()
            overlay.update()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to prewarm visualizer renderer", exc_info=True)
        return False

    if isinstance(overlay, CompositorSpotifyVisualizerLayer):
        ready = False
        try:
            ready = bool(overlay.is_render_ready())
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to inspect compositor visualizer readiness",
                exc_info=True,
            )
        if not ready:
            fallback_reason = None
            try:
                fallback_reason = overlay.hard_legacy_fallback_reason()
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to classify compositor prewarm readiness",
                    exc_info=True,
                )
            if fallback_reason:
                overlay = _fallback_compositor_visualizer_to_legacy(
                    widget,
                    overlay,
                    vis=vis,
                    initial_mode=startup_mode or None,
                    reason=fallback_reason,
                )
                if overlay is None:
                    return False
                try:
                    overlay.prewarm_context(geom)
                except Exception:
                    logger.error(
                        "[SPOTIFY_VIS][FALLBACK] Legacy visualizer prewarm also failed",
                        exc_info=True,
                    )
                    _set_visualizer_surface_terminal_reason(
                        widget,
                        "legacy_prewarm_failed",
                    )
                    return False
            else:
                logger.debug(
                    "[SPOTIFY_VIS] Compositor visualizer prewarm deferred without "
                    "legacy fallback screen=%s state=%s",
                    getattr(widget, "screen_index", getattr(widget, "_screen_index", "?")),
                    overlay.describe_state(),
                )
                return False

    if str(getattr(overlay, "render_surface_kind", "")) == "legacy_child":
        readiness = getattr(overlay, "is_gl_ready", None)
        try:
            ready = bool(readiness()) if callable(readiness) else False
        except Exception:
            ready = False
        if not ready:
            logger.error(
                "[SPOTIFY_VIS][FALLBACK] Legacy renderer failed to reach READY; "
                "the visualizer will remain hidden"
            )
            _set_visualizer_surface_terminal_reason(
                widget,
                "legacy_renderer_not_ready",
            )
            return False

    return True


def sync_spotify_visualizer_overlay_geometry(widget) -> bool:
    """Realign an existing Spotify GL overlay to the authoritative card rect.

    This is intentionally geometry-only. It does not push fresh bars, mutate
    fade state, or force visibility changes. The goal is to keep startup,
    CUSTOM replay, and runtime rebuilds from leaving the overlay stranded on
    an earlier stale rect when the card has already moved to its committed
    geometry.
    """

    vis = getattr(widget, "spotify_visualizer_widget", None)
    if vis is None:
        return False

    overlay = getattr(widget, "_spotify_bars_overlay", None)
    if overlay is None:
        return False

    geom = _resolve_spotify_visualizer_overlay_rect(vis)
    if geom is None or geom.width() <= 0 or geom.height() <= 0:
        return False

    try:
        cur_geom = overlay.geometry()
    except Exception:
        cur_geom = None

    try:
        if cur_geom is None or QRect(cur_geom) != geom:
            overlay.setGeometry(geom)
            try:
                overlay.update()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to update overlay after geometry sync", exc_info=True)
        return True
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to sync visualizer renderer geometry", exc_info=True)
        return False


def _resolve_spotify_visualizer_overlay_rect(vis) -> QRect | None:
    """Prefer the committed CUSTOM rect when it is available and valid.

    The visualizer can briefly carry a stale live geometry during startup,
    rebuild, or runtime card-pressure churn even though a committed CUSTOM rect
    is already authoritative. The GL overlay must follow the committed rect in
    those windows so runtime content cannot regress back to a square/stale card
    while geometry replay logs stay green.
    """

    try:
        resolve_gpu_target_rect = getattr(vis, "_resolve_gpu_target_rect", None)
        if callable(resolve_gpu_target_rect):
            rect = resolve_gpu_target_rect()
            if isinstance(rect, QRect) and rect.width() > 0 and rect.height() > 0:
                return QRect(rect)
    except Exception:
        logger.debug("[DISPLAY_WIDGET] Failed to read visualizer authoritative GPU rect", exc_info=True)

    try:
        active_custom_rect = getattr(vis, "_active_custom_layout_rect", None)
        if callable(active_custom_rect):
            rect = active_custom_rect()
            if isinstance(rect, QRect) and rect.width() > 0 and rect.height() > 0:
                return QRect(rect)
    except Exception:
        logger.debug("[DISPLAY_WIDGET] Failed to read visualizer active custom rect", exc_info=True)

    try:
        geom = vis.geometry()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return None

    try:
        return QRect(geom)
    except Exception:
        logger.debug("[DISPLAY_WIDGET] Failed to normalize visualizer geometry", exc_info=True)
        return None


def _set_visualizer_compositor_ownership(vis, enabled: bool) -> None:
    if vis is None:
        return
    setter = getattr(vis, "set_compositor_visualizer_active", None)
    if callable(setter):
        setter(enabled)
        return
    setattr(vis, "_compositor_visualizer_active", bool(enabled))


def _set_visualizer_surface_terminal_reason(widget, reason: str | None) -> None:
    """Publish display-generation renderer setup failure without fallback."""

    normalized = str(reason or "").strip()
    setattr(widget, "_spotify_visualizer_surface_terminal_reason", normalized)
    if not normalized:
        vis = getattr(widget, "spotify_visualizer_widget", None)
        if vis is not None:
            setattr(vis, "_startup_renderer_terminal_logged", False)


def _create_legacy_spotify_bars_overlay(
    widget,
    *,
    vis,
    initial_mode: str | None,
    reason: str,
) -> SpotifyBarsGLOverlay | None:
    try:
        overlay = SpotifyBarsGLOverlay(widget, initial_mode=initial_mode)
        overlay.setObjectName("spotify_bars_gl_overlay")
        widget._spotify_bars_overlay = overlay
        _set_visualizer_surface_terminal_reason(widget, None)
        _set_visualizer_compositor_ownership(vis, False)
        if widget._resource_manager is not None:
            try:
                widget._resource_manager.register_qt(
                    overlay,
                    description="Spotify bars GL overlay",
                )
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to register legacy visualizer surface",
                    exc_info=True,
                )
        logger.warning(
            "[SPOTIFY_VIS][SURFACE] Renderer target=legacy_child reason=%s screen=%s",
            str(reason or "unknown"),
            getattr(widget, "screen_index", getattr(widget, "_screen_index", "?")),
        )
        return overlay
    except Exception:
        logger.debug(
            "[DISPLAY_WIDGET] Failed to initialize legacy visualizer surface",
            exc_info=True,
        )
        widget._spotify_bars_overlay = None
        _set_visualizer_surface_terminal_reason(
            widget,
            "legacy_surface_creation_failed",
        )
        return None


def _fallback_compositor_visualizer_to_legacy(
    widget,
    overlay: CompositorSpotifyVisualizerLayer,
    *,
    vis,
    initial_mode: str | None,
    reason: str,
) -> SpotifyBarsGLOverlay | None:
    """Switch before first reveal when compositor prewarm cannot reach READY."""

    logger.error(
        "[SPOTIFY_VIS][FALLBACK] Using legacy child surface before reveal "
        "reason=%s screen=%s",
        reason,
        getattr(widget, "screen_index", getattr(widget, "_screen_index", "?")),
    )
    try:
        overlay.hide()
        overlay.cleanup_gl()
        overlay.deleteLater()
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] Failed to retire compositor visualizer layer",
            exc_info=True,
        )
    compositor = getattr(widget, "_gl_compositor", None)
    if compositor is not None and getattr(
        compositor,
        "_spotify_visualizer_layer",
        None,
    ) is overlay:
        compositor._spotify_visualizer_layer = None
    widget._spotify_bars_overlay = None
    _set_visualizer_compositor_ownership(vis, False)
    return _create_legacy_spotify_bars_overlay(
        widget,
        vis=vis,
        initial_mode=initial_mode,
        reason=f"hard_fallback_{reason}",
    )


def _ensure_spotify_bars_overlay(
    widget,
) -> SpotifyBarsGLOverlay | CompositorSpotifyVisualizerLayer | None:
    """Return the active visualizer renderer target, creating it if needed."""

    overlay = getattr(widget, "_spotify_bars_overlay", None)
    if isinstance(overlay, CompositorSpotifyVisualizerLayer):
        vis = getattr(widget, "spotify_visualizer_widget", None)
        _set_visualizer_surface_terminal_reason(widget, None)
        _set_visualizer_compositor_ownership(vis, True)
        return overlay
    if isinstance(overlay, SpotifyBarsGLOverlay):
        vis = getattr(widget, "spotify_visualizer_widget", None)
        _set_visualizer_surface_terminal_reason(widget, None)
        _set_visualizer_compositor_ownership(vis, False)
        return overlay

    initial_mode = None
    vis = getattr(widget, "spotify_visualizer_widget", None)
    try:
        if vis is not None:
            initial_mode = (
                str(getattr(vis, "_vis_mode_str", "") or "").strip().lower()
                or None
            )
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] Failed to read visualizer mode for renderer init",
            exc_info=True,
        )

    single_surface_requested = single_surface_visualizer_enabled()
    if single_surface_requested:
        compositor = getattr(widget, "_gl_compositor", None)
        if isinstance(compositor, GLCompositorWidget):
            try:
                overlay = compositor.get_or_create_spotify_visualizer_layer(
                    initial_mode=initial_mode,
                )
                widget._spotify_bars_overlay = overlay
                _set_visualizer_surface_terminal_reason(widget, None)
                _set_visualizer_compositor_ownership(vis, True)
                logger.info(
                    "[SPOTIFY_VIS][SURFACE] Renderer target=compositor "
                    "reason=default screen=%s",
                    getattr(widget, "screen_index", getattr(widget, "_screen_index", "?")),
                )
                return overlay
            except Exception:
                logger.error(
                    "[SPOTIFY_VIS][COMPOSITOR] Failed to create display-owned visualizer layer; "
                    "legacy will not mask an unexpected compositor-path defect",
                    exc_info=True,
                )
                _set_visualizer_surface_terminal_reason(
                    widget,
                    "compositor_layer_creation_failed",
                )
                return None

    # Legacy is restricted to explicit rollback or a deliberately selected
    # non-compositor backend. An unexpectedly missing GL compositor is a real
    # failure, not permission to restore the competing child surface.
    if overlay is None:
        if not single_surface_requested:
            legacy_reason = "explicit_rollback"
        else:
            backend_selection = getattr(widget, "_backend_selection", None)
            resolved_mode = str(
                getattr(backend_selection, "resolved_mode", "") or ""
            ).strip().lower()
            if resolved_mode and resolved_mode != "opengl":
                legacy_reason = "software_backend"
            else:
                logger.error(
                    "[SPOTIFY_VIS][COMPOSITOR] Display-owned visualizer unavailable "
                    "without an authorized legacy condition screen=%s backend=%s pyopengl=%s",
                    getattr(widget, "screen_index", getattr(widget, "_screen_index", "?")),
                    resolved_mode or "unknown",
                    GL is not None,
                )
                _set_visualizer_surface_terminal_reason(
                    widget,
                    "compositor_unavailable",
                )
                return None
        overlay = _create_legacy_spotify_bars_overlay(
            widget,
            vis=vis,
            initial_mode=initial_mode,
            reason=legacy_reason,
        )

    # NOTE: Do NOT register either renderer target with PixelShiftManager.
    # Both follow the visualizer card's already-shifted authoritative geometry.

    if overlay is None:
        logger.warning(
            "[SPOTIFY_VIS] Missing visualizer renderer target after initialization; "
            "visualizer content will be blank"
        )
        return None

    if not hasattr(overlay, "clear_overlay_buffer"):
        module_name = type(overlay).__module__
        module = sys.modules.get(module_name)
        module_path = getattr(module, "__file__", "<unknown>")
        logger.critical(
            "[SPOTIFY_VIS] Visualizer renderer target missing clear_overlay_buffer "
            "(module=%s path=%s). "
            "Ensure code reload or delete stale pyc files.",
            module_name,
            module_path,
        )
        _set_visualizer_surface_terminal_reason(
            widget,
            "renderer_interface_invalid",
        )
        raise RuntimeError(
            "Visualizer renderer target missing clear_overlay_buffer; stale build detected"
        )

    return overlay


def _push_spotify_bars_overlay_state(
    widget,
    *,
    overlay: SpotifyBarsGLOverlay | CompositorSpotifyVisualizerLayer,
    geom: QRect,
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
    visible=True,
    border_width_px=0,
    extra_kwargs=None,
) -> bool:
    extras = extra_kwargs if isinstance(extra_kwargs, dict) else {}
    if "border_width_px" in extras:
        extras = dict(extras)
        extras.pop("border_width_px", None)

    try:
        try:
            vis = getattr(widget, "spotify_visualizer_widget", None)
            if vis is not None and hasattr(overlay, "set_painted_frame_shadow_enabled"):
                overlay.set_painted_frame_shadow_enabled(bool(vis.uses_painted_frame_shadow()))
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to sync GL stencil shadow state", exc_info=True)

        try:
            overlay.set_state(
                rect=geom,
                bars=bars,
                bar_count=bar_count,
                segments=segments,
                fill_color=fill_color,
                border_color=border_color,
                fade=fade,
                playing=playing,
                visible=visible,
                ghosting_enabled=ghosting_enabled,
                ghost_alpha=ghost_alpha,
                ghost_decay=ghost_decay,
                vis_mode=vis_mode,
                border_width_px=border_width_px,
                **extras,
            )
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
                fallback_extras = dict(extras)
                for key in unexpected:
                    fallback_extras.pop(key, None)
                overlay.set_state(
                    rect=geom,
                    bars=bars,
                    bar_count=bar_count,
                    segments=segments,
                    fill_color=fill_color,
                    border_color=border_color,
                    fade=fade,
                    playing=playing,
                    visible=visible,
                    ghosting_enabled=ghosting_enabled,
                    ghost_alpha=ghost_alpha,
                    ghost_decay=ghost_decay,
                    vis_mode=vis_mode,
                    border_width_px=border_width_px,
                    **fallback_extras,
                )
            else:
                raise
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to push frame to visualizer renderer", exc_info=True)
        return False

    return True

