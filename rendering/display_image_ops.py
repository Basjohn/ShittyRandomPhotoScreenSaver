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

from rendering.display_widget import _describe_pixmap

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def _texture_cache_perf_probe(
    compositor,
    old_pixmap: Optional[QPixmap],
    new_pixmap: Optional[QPixmap],
) -> dict[str, int | bool]:
    """Read exact texture-cache identity without changing GL/cache state."""
    probe = getattr(compositor, "get_texture_cache_perf_probe", None)
    if callable(probe):
        try:
            return dict(probe(old_pixmap, new_pixmap))
        except Exception:
            logger.debug("[PERF] Texture cache probe failed", exc_info=True)
    return {
        "manager_present": False,
        "cache_size": 0,
        "sole_cache_key": 0,
        "old_key": 0,
        "new_key": 0,
        "old_texture": 0,
        "new_texture": 0,
        "old_cached": False,
        "new_cached": False,
        "texture_cache_hits": 0,
        "texture_allocations": 0,
        "texture_uploads": 0,
    }


def _transition_pair_required(widget) -> bool:
    """Return whether this install can consume both old and new textures."""
    return bool(
        widget.settings_manager
        and widget._has_rendered_first_frame
        and widget._transitions_enabled
    )


def _compositor_texture_runtime_is_warm(compositor) -> bool:
    """Return whether the compositor can service an existing texture install."""
    if not isinstance(compositor, GLCompositorWidget):
        return False
    try:
        context = compositor.context()
        if context is None or not context.isValid():
            return False
    except Exception:
        return False
    pipeline = getattr(compositor, "_gl_pipeline", None)
    if pipeline is None or not bool(getattr(pipeline, "initialized", False)):
        return False
    return getattr(compositor, "_texture_manager", None) is not None


def _next_image_install_perf_id(widget) -> str:
    """Return one display-local correlation identity for a perf-gated install."""
    sequence = int(getattr(widget, "_perf_image_install_sequence", 0) or 0) + 1
    widget._perf_image_install_sequence = sequence
    screen = getattr(widget, "screen_index", "x")
    generation = getattr(widget, "_runtime_generation", 0)
    generation_text = "_".join(str(generation if generation is not None else 0).split())
    return f"d{screen}-g{generation_text}-i{sequence}"


def _format_image_ui_extra_fields(values: Optional[dict[str, object]]) -> str:
    """Format controlled perf fields without paying work outside perf logging."""
    if not values:
        return ""
    fields: list[str] = []
    for key, value in values.items():
        if value is None:
            rendered = "na"
        elif isinstance(value, bool):
            rendered = str(value).lower()
        elif isinstance(value, float):
            rendered = f"{value:.3f}"
        else:
            rendered = "_".join(str(value).split())
        fields.append(f"{key}={rendered}")
    return " " + " ".join(fields)


def _log_image_ui_stage(
    widget,
    *,
    stage: str,
    started_ts: float,
    install_id: str = "",
    transition: str = "none",
    outcome: str = "completed",
    cold_compositor: bool = False,
    before_probe: Optional[dict[str, int | bool]] = None,
    after_probe: Optional[dict[str, int | bool]] = None,
    extra_fields: Optional[dict[str, object]] = None,
) -> None:
    """Emit one bounded, perf-only substage record for image installation."""
    if not started_ts:
        return
    before = before_probe or {}
    after = after_probe or before

    def _ival(values: dict[str, int | bool], key: str) -> int:
        try:
            return int(values.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    cache_hits_delta = max(
        0,
        _ival(after, "texture_cache_hits") - _ival(before, "texture_cache_hits"),
    )
    allocations_delta = max(
        0,
        _ival(after, "texture_allocations") - _ival(before, "texture_allocations"),
    )
    uploads_delta = max(
        0,
        _ival(after, "texture_uploads") - _ival(before, "texture_uploads"),
    )
    pixmap = getattr(widget, "current_pixmap", None)
    width = 0
    height = 0
    try:
        if pixmap is not None and not pixmap.isNull():
            width = int(pixmap.width())
            height = int(pixmap.height())
    except Exception:
        width = 0
        height = 0
    logger.info(
        "[PERF] [IMAGE_UI_SEGMENT] reason=display_setter_detail display=%s "
        "stage=%s install_id=%s duration_ms=%.2f transition=%s outcome=%s size=%dx%d "
        "cold_compositor=%s manager_before=%s manager_after=%s "
        "cache_size_before=%d cache_size_after=%d retained_key_before=%d "
        "old_key=%d new_key=%d old_cached_before=%s new_cached_before=%s "
        "old_texture_before=%d new_texture_before=%d cache_hits_delta=%d "
        "texture_allocations_delta=%d texture_uploads_delta=%d%s",
        getattr(widget, "screen_index", "?"),
        stage,
        install_id or "none",
        max(0.0, (time.perf_counter() - started_ts) * 1000.0),
        transition or "none",
        outcome,
        width,
        height,
        str(bool(cold_compositor)).lower(),
        str(bool(before.get("manager_present", False))).lower(),
        str(bool(after.get("manager_present", False))).lower(),
        _ival(before, "cache_size"),
        _ival(after, "cache_size"),
        _ival(before, "sole_cache_key"),
        _ival(before, "old_key"),
        _ival(before, "new_key"),
        str(bool(before.get("old_cached", False))).lower(),
        str(bool(before.get("new_cached", False))).lower(),
        _ival(before, "old_texture"),
        _ival(before, "new_texture"),
        cache_hits_delta,
        allocations_delta,
        uploads_delta,
        _format_image_ui_extra_fields(extra_fields),
    )


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

    _complete_when_current._srpss_runtime_generation = getattr(
        widget,
        "_runtime_generation",
        None,
    )

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
        widget.refresh_image_resource_accounting()
        widget.update()
        return

    perf_enabled = is_perf_metrics_enabled()
    install_started = time.perf_counter() if perf_enabled else 0.0
    install_id = _next_image_install_perf_id(widget) if perf_enabled else ""

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
    retire_started = time.perf_counter() if perf_enabled else 0.0
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
    _log_image_ui_stage(
        widget,
        stage="retire_previous_transition",
        started_ts=retire_started,
        install_id=install_id,
    )
    
    # Cache previous pixmap reference before we mutate current_pixmap
    previous_pixmap_ref = widget.current_pixmap
    use_transition = _transition_pair_required(widget)

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
        cold_compositor = bool(
            perf_enabled
            and not _compositor_texture_runtime_is_warm(
                getattr(widget, "_gl_compositor", None)
            )
        )
        ensure_started = time.perf_counter() if perf_enabled else 0.0
        try:
            widget._ensure_gl_compositor()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        comp = getattr(widget, "_gl_compositor", None)
        _log_image_ui_stage(
            widget,
            stage="ensure_compositor",
            started_ts=ensure_started,
            install_id=install_id,
            cold_compositor=cold_compositor,
            after_probe=(
                _texture_cache_perf_probe(comp, previous_pixmap_ref, new_pixmap)
                if perf_enabled and isinstance(comp, GLCompositorWidget)
                else None
            ),
        )
        if isinstance(comp, GLCompositorWidget):
            compositor_setup_ok = True
            setup_started = time.perf_counter() if perf_enabled else 0.0
            setup_phase_started = setup_started if perf_enabled else 0.0
            setup_fields: Optional[dict[str, object]] = {} if perf_enabled else None
            try:
                comp.setGeometry(0, 0, widget.width(), widget.height())
                if perf_enabled:
                    setup_phase_now = time.perf_counter()
                    setup_fields["geometry_ms"] = (
                        setup_phase_now - setup_phase_started
                    ) * 1000.0
                    setup_phase_started = setup_phase_now
                comp.set_base_pixmap(widget.current_pixmap)
                if perf_enabled:
                    setup_phase_now = time.perf_counter()
                    setup_fields["set_base_ms"] = (
                        setup_phase_now - setup_phase_started
                    ) * 1000.0
                    setup_phase_started = setup_phase_now
                    mark_install = getattr(
                        comp,
                        "mark_image_install_next_paint_perf_trace",
                        None,
                    )
                    if callable(mark_install):
                        mark_install(install_id, install_started)
                comp.show()
                if perf_enabled:
                    setup_phase_now = time.perf_counter()
                    setup_fields["show_ms"] = (
                        setup_phase_now - setup_phase_started
                    ) * 1000.0
                    setup_phase_started = setup_phase_now
                comp.raise_()
                if perf_enabled:
                    setup_fields["raise_ms"] = (
                        time.perf_counter() - setup_phase_started
                    ) * 1000.0
            except Exception:
                compositor_setup_ok = False
                if perf_enabled:
                    clear_install = getattr(
                        comp,
                        "clear_image_install_next_paint_perf_trace",
                        None,
                    )
                    if callable(clear_install):
                        clear_install(install_id)
                logger.debug("[GL COMPOSITOR] Failed to pre-warm compositor with base frame", exc_info=True)
            _log_image_ui_stage(
                widget,
                stage="compositor_setup",
                started_ts=setup_started,
                install_id=install_id,
                outcome="completed" if compositor_setup_ok else "error",
                cold_compositor=cold_compositor,
                extra_fields=setup_fields,
            )
            if compositor_setup_ok:
                # Prewarm shader textures for the upcoming transition so
                # GLSL paths (Slide, Wipe, Diffuse, etc.) do not pay the
                # full texture upload cost on their first animated frame.
                warm_before = (
                    _texture_cache_perf_probe(comp, previous_pixmap_ref, new_pixmap)
                    if perf_enabled
                    else None
                )
                warm_started = time.perf_counter() if perf_enabled else 0.0
                warm_outcome = "completed"
                warm_old_pixmap = previous_pixmap_ref if use_transition else None
                try:
                    if perf_enabled:
                        comp.warm_shader_textures(
                            warm_old_pixmap,
                            new_pixmap,
                            perf_install_id=install_id,
                        )
                    else:
                        comp.warm_shader_textures(warm_old_pixmap, new_pixmap)
                except Exception:
                    warm_outcome = "error"
                    logger.debug(
                        "[GL COMPOSITOR] warm_shader_textures failed during pre-warm",
                        exc_info=True,
                    )
                warm_after = (
                    _texture_cache_perf_probe(comp, previous_pixmap_ref, new_pixmap)
                    if perf_enabled
                    else None
                )
                _log_image_ui_stage(
                    widget,
                    stage="generic_pair_warm",
                    started_ts=warm_started,
                    install_id=install_id,
                    outcome=warm_outcome,
                    cold_compositor=cold_compositor,
                    before_probe=warm_before,
                    after_probe=warm_after,
                )
                # Restore runtime widget stacking after compositor prewarm
                # without maintaining a stale handwritten widget inventory.
                prewarm_raise_started = time.perf_counter() if perf_enabled else 0.0
                _raise_runtime_widgets_above_compositor(widget, stage="compositor_prewarm")
                _log_image_ui_stage(
                    widget,
                    stage="prewarm_overlay_raise",
                    started_ts=prewarm_raise_started,
                    install_id=install_id,
                    cold_compositor=cold_compositor,
                )

        if widget.settings_manager and not widget._has_rendered_first_frame:
            logger.debug("[INIT] First frame - presenting without transition to avoid black flicker")

        if use_transition:
            construct_started = time.perf_counter() if perf_enabled else 0.0
            transition = widget._create_transition()
            transition_name = transition.__class__.__name__ if transition else "none"
            _log_image_ui_stage(
                widget,
                stage="transition_construct",
                started_ts=construct_started,
                install_id=install_id,
                transition=transition_name,
                outcome="completed" if transition else "none",
                cold_compositor=cold_compositor,
            )
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

                transition_warm_before = (
                    _texture_cache_perf_probe(comp, widget.previous_pixmap, new_pixmap)
                    if perf_enabled and isinstance(comp, GLCompositorWidget)
                    else None
                )
                transition_warm_started = time.perf_counter() if perf_enabled else 0.0
                widget._warm_transition_if_needed(
                    comp,
                    transition.__class__.__name__,
                    widget.previous_pixmap,
                    new_pixmap,
                )
                transition_warm_after = (
                    _texture_cache_perf_probe(comp, widget.previous_pixmap, new_pixmap)
                    if perf_enabled and isinstance(comp, GLCompositorWidget)
                    else None
                )
                _log_image_ui_stage(
                    widget,
                    stage="transition_specific_warm",
                    started_ts=transition_warm_started,
                    install_id=install_id,
                    transition=transition.__class__.__name__,
                    cold_compositor=cold_compositor,
                    before_probe=transition_warm_before,
                    after_probe=transition_warm_after,
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
                transition_start_started = time.perf_counter() if perf_enabled else 0.0
                if widget._transition_controller is not None:
                    success = widget._transition_controller.start_transition(
                        transition, widget.previous_pixmap, new_pixmap,
                        overlay_key=overlay_key, on_finished=_finish_handler
                    )
                else:
                    # Fallback: direct start
                    transition.finished.connect(_finish_handler)
                    success = transition.start(widget.previous_pixmap, new_pixmap, widget)
                _log_image_ui_stage(
                    widget,
                    stage="transition_controller_start",
                    started_ts=transition_start_started,
                    install_id=install_id,
                    transition=transition.__class__.__name__,
                    outcome="completed" if success else "refused",
                    cold_compositor=cold_compositor,
                )
                
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
                    post_start_started = time.perf_counter() if perf_enabled else 0.0
                    _raise_runtime_widgets_above_compositor(widget, stage="transition_start")
                    widget.refresh_image_resource_accounting()
                    _log_image_ui_stage(
                        widget,
                        stage="post_start_overlay_accounting",
                        started_ts=post_start_started,
                        install_id=install_id,
                        transition=transition.__class__.__name__,
                        cold_compositor=cold_compositor,
                    )
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
            immediate_started = time.perf_counter() if perf_enabled else 0.0
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

        widget.refresh_image_resource_accounting()
        _log_image_ui_stage(
            widget,
            stage="immediate_display_accounting",
            started_ts=immediate_started,
            install_id=install_id,
            transition="none",
            cold_compositor=cold_compositor,
        )

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
    widget.refresh_image_resource_accounting()

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
            _attach_overlay_presentation_owner(widget, overlay)
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


def _attach_overlay_presentation_owner(widget, overlay) -> bool:
    """Register the overlay with the display's own compositor frame opportunity.

    The `DisplayWidget` owns both the compositor and this auxiliary surface, so it is
    the correct registrar. If no render strategy is available the overlay stays unowned
    and keeps requesting a repaint per publication, which is the previous behaviour.
    """
    try:
        compositor = getattr(widget, "_gl_compositor", None)
        strategy = getattr(compositor, "_render_strategy_manager", None)
        if strategy is None or not hasattr(strategy, "set_auxiliary_presenter"):
            return False
        strategy.set_auxiliary_presenter(overlay)
        overlay.set_presentation_owned(True)
        logger.info(
            "[SPOTIFY_VIS] Overlay presentation owned by display frame opportunity screen=%s",
            getattr(widget, "_screen_index", "<unknown>"),
        )
        return True
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] Failed to attach overlay presentation owner", exc_info=True
        )
        return False


def _detach_overlay_presentation_owner(widget, overlay) -> None:
    """Release presentation ownership before the overlay or compositor is retired."""
    try:
        compositor = getattr(widget, "_gl_compositor", None)
        strategy = getattr(compositor, "_render_strategy_manager", None)
        if strategy is not None and hasattr(strategy, "clear_auxiliary_presenter"):
            strategy.clear_auxiliary_presenter()
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] Failed to detach overlay presentation owner", exc_info=True
        )
    try:
        if overlay is not None and hasattr(overlay, "set_presentation_owned"):
            overlay.set_presentation_owned(False)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear overlay ownership flag", exc_info=True)


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
