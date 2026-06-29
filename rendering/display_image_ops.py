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

from PySide6.QtCore import QTimer, QRect
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

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


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
    """Defer startup readiness until the first frame crosses a paint boundary.

    On startup we previously emitted `image_displayed` immediately after
    `update()`, which only queues a repaint. Under a busier host environment
    that let overlay fade coordination outrun the actual first frame.
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

    def _flush_presentation() -> None:
        if int(getattr(widget, "_pending_startup_frame_token", 0)) != token:
            return

        comp = getattr(widget, "_gl_compositor", None)
        try:
            if isinstance(comp, GLCompositorWidget) and comp.isVisible():
                comp.update()
                comp.repaint()
                if is_verbose_logging():
                    logger.debug(
                        "[STARTUP] Flushed first-frame via GL compositor on screen=%s token=%s",
                        getattr(widget, "screen_index", "?"),
                        token,
                    )
            else:
                widget.update()
                widget.repaint()
                if is_verbose_logging():
                    logger.debug(
                        "[STARTUP] Flushed first-frame via base widget paint on screen=%s token=%s",
                        getattr(widget, "screen_index", "?"),
                        token,
                    )
        except Exception:
            logger.debug("[STARTUP] First-frame presentation flush failed", exc_info=True)

        QTimer.singleShot(0, lambda: _complete_startup_first_frame_ready(widget, image_path, token))

    QTimer.singleShot(0, _flush_presentation)


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
        if hasattr(widget, "set_transition_work_pending"):
            widget.set_transition_work_pending(False)
        widget._transition_skip_count += 1
        logger.debug(
            "Transition in progress - skipping image request (skip_count=%s)",
            widget._transition_skip_count,
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
                        "[TRANSITION][ERROR] Transition refused/failed to start; displaying final image immediately "
                        "screen=%s transition=%s overlay=%s",
                        getattr(widget, "screen_index", "?"),
                        transition.__class__.__name__,
                        overlay_key or "<none>",
                    )
                    transition.cleanup()
                    widget._current_transition = None
                    widget._current_transition_name = None
                    widget._current_transition_first_run = False
                    widget._pending_transition_finish_args = None
                    _raise_runtime_widgets_above_compositor(widget, stage="transition_refused")
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
        **extra_kwargs,
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
        return False

    try:
        if hasattr(overlay, "prewarm_context"):
            overlay.prewarm_context(geom)
        else:
            overlay.setGeometry(geom)
            overlay.show()
            overlay.update()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to prewarm SpotifyBarsGLOverlay", exc_info=True)
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
        logger.debug("[SPOTIFY_VIS] Failed to sync SpotifyBarsGLOverlay geometry", exc_info=True)
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


def _ensure_spotify_bars_overlay(widget) -> SpotifyBarsGLOverlay | None:
    """Return the shared Spotify GL overlay, creating it if needed."""

    # Lazily create a small GL overlay dedicated to Spotify bars. This
    # sits above the card widget in Z-order while the card itself remains
    # a normal QWidget with ShadowFadeProfile-driven opacity.
    overlay = getattr(widget, "_spotify_bars_overlay", None)
    if overlay is None or not isinstance(overlay, SpotifyBarsGLOverlay):
        try:
            initial_mode = None
            try:
                vis = getattr(widget, "spotify_visualizer_widget", None)
                if vis is not None:
                    initial_mode = str(getattr(vis, "_vis_mode_str", "") or "").strip().lower() or None
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to read visualizer mode for overlay init", exc_info=True)
            overlay = SpotifyBarsGLOverlay(widget, initial_mode=initial_mode)
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
            # NOTE: Do NOT register the GL overlay with PixelShiftManager.
            # The overlay already tracks the visualizer card's geometry via
            # set_state(rect=vis.geometry()) every tick.  Registering it
            # causes double-shifting: PSM moves the overlay, then set_state()
            # snaps it to the card's already-shifted position, then PSM
            # shifts it again → the overlay drifts past the card and briefly
            # flashes over neighbouring widgets (e.g. weather).
        except Exception:
            logger.debug("[DISPLAY_WIDGET] Failed to initialize SpotifyBarsGLOverlay", exc_info=True)
            widget._spotify_bars_overlay = None
            return None

    if overlay is None:
        logger.warning("[SPOTIFY_VIS] Missing SpotifyBarsGLOverlay after initialization; visualizer bars will be blank")
        return None

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

    return overlay


def _push_spotify_bars_overlay_state(
    widget,
    *,
    overlay: SpotifyBarsGLOverlay,
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
    **extra_kwargs,
) -> bool:
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
            "visible": visible,
            "ghosting_enabled": ghosting_enabled,
            "ghost_alpha": ghost_alpha,
            "ghost_decay": ghost_decay,
            "vis_mode": vis_mode,
        }
        overlay_kwargs.update(extra_kwargs)

        try:
            vis = getattr(widget, "spotify_visualizer_widget", None)
            if vis is not None and hasattr(overlay, "set_painted_frame_shadow_enabled"):
                overlay.set_painted_frame_shadow_enabled(bool(vis.uses_painted_frame_shadow()))
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to sync GL stencil shadow state", exc_info=True)

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

