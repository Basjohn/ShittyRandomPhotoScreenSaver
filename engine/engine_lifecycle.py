"""Engine Lifecycle - Extracted from screensaver_engine.py.

Contains stop, cleanup, and QTimer safety helpers for the engine
shutdown sequence. All functions accept the engine instance as the
first parameter to preserve the original interface.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QTimer, QMetaObject, Qt, QThread
from PySide6.QtWidgets import QApplication

from core.logging.logger import (
    get_logger,
    is_cache_logging_enabled,
    is_perf_metrics_enabled,
)

if TYPE_CHECKING:
    from engine.screensaver_engine import ScreensaverEngine

logger = get_logger(__name__)


# ------------------------------------------------------------------
# QTimer safety helper
# ------------------------------------------------------------------

def stop_qtimer_safe(
    engine: ScreensaverEngine,
    timer: Optional[QTimer],
    *,
    description: str,
) -> None:
    """Stop/delete a QTimer on its owning thread."""
    if timer is None:
        return
    try:
        if QThread.currentThread() is timer.thread():
            if timer.isActive():
                timer.stop()
            try:
                timer.deleteLater()
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
        else:
            QMetaObject.invokeMethod(
                timer,
                "stop",
                Qt.ConnectionType.QueuedConnection,
            )
            QMetaObject.invokeMethod(
                timer,
                "deleteLater",
                Qt.ConnectionType.QueuedConnection,
            )
        logger.debug("%s stopped", description)
    except Exception as exc:
        logger.debug("%s stop failed: %s", description, exc, exc_info=True)


# ------------------------------------------------------------------
# Display runtime teardown
# ------------------------------------------------------------------

def teardown_display_runtime(
    engine: ScreensaverEngine,
    *,
    reason: str,
) -> object | None:
    """Clean one display runtime and queue its Qt roots for destruction.

    Producer shutdown and strict GL deletion complete synchronously.  The
    returned barrier represents only Qt/Python root destruction, which must be
    observed on a later event-loop turn before constructing a replacement.
    """
    manager = getattr(engine, "display_manager", None)
    if manager is None:
        engine._display_initialized = False
        return None

    retiring_generation = getattr(manager, "_runtime_generation", None)
    barrier = None
    try:
        from PySide6.QtCore import QObject
        from engine.runtime_destruction import create_runtime_destruction_barrier

        app = QCoreApplication.instance()
        qt_event_loop_available = (
            app is not None and not QCoreApplication.closingDown()
        )
        if (
            isinstance(manager, QObject)
            and qt_event_loop_available
            and reason not in {"application_exit", "engine_cleanup"}
        ):
            barrier = create_runtime_destruction_barrier(
                engine,
                manager,
                reason=reason,
                retiring_generation=retiring_generation,
            )
    except Exception:
        logger.critical(
            "[LIFECYCLE] Failed to arm retired-runtime destruction tracking",
            exc_info=True,
        )
        raise

    display_count = manager.get_display_count()
    logger.info(
        "[LIFECYCLE] Full display teardown started reason=%s count=%d",
        reason,
        display_count,
    )

    if is_perf_metrics_enabled():
        states = manager.describe_display_states()
        logger.info(
            "[PERF][ENGINE] pre_teardown_display_states reason=%s count=%d states=%s",
            reason,
            display_count,
            states,
        )

    disconnect_monitor_detection = getattr(
        manager, "disconnect_monitor_detection", None
    )
    if callable(disconnect_monitor_detection):
        disconnect_monitor_detection()

    quiesce = getattr(manager, "quiesce_all", None)
    if callable(quiesce):
        quiesce()
    clear = getattr(manager, "clear_all", None)
    if callable(clear):
        clear()

    thread_manager = getattr(engine, "thread_manager", None)
    cancel_generation_callbacks = getattr(
        thread_manager,
        "cancel_scheduled_single_shots",
        None,
    )
    if retiring_generation is not None and callable(cancel_generation_callbacks):
        cancelled_callbacks = cancel_generation_callbacks(retiring_generation)
        if cancelled_callbacks:
            logger.info(
                "[LIFECYCLE] Cancelled %d delayed callbacks for retiring generation=%s",
                cancelled_callbacks,
                retiring_generation,
            )
    reject_generation_ui = getattr(
        thread_manager,
        "cancel_queued_ui_callbacks",
        None,
    )
    if retiring_generation is not None and callable(reject_generation_ui):
        queued_callbacks = reject_generation_ui(retiring_generation)
        if queued_callbacks:
            logger.info(
                "[LIFECYCLE] Rejected %d queued UI callbacks for retiring generation=%s",
                queued_callbacks,
                retiring_generation,
            )

    try:
        from core.performance.resource_metrics import log_lifecycle_resource_snapshot

        log_lifecycle_resource_snapshot(
            engine,
            event=reason,
            stage="after_producers_stopped",
        )
    except Exception:
        logger.debug("Lifecycle producer-stop snapshot failed", exc_info=True)

    cleanup_manager = getattr(manager, "cleanup", None)
    if not callable(cleanup_manager):
        raise RuntimeError("DisplayManager has no cleanup() contract")
    cleanup_manager()

    try:
        from core.performance.resource_metrics import log_lifecycle_resource_snapshot

        log_lifecycle_resource_snapshot(
            engine,
            event=reason,
            stage="after_gl_display_cleanup",
        )
    except Exception:
        logger.debug("Lifecycle GL/display snapshot failed", exc_info=True)

    flush_urls = getattr(manager, "flush_deferred_reddit_urls", None)
    if callable(flush_urls):
        flush_urls(ensure_widgets_dismissed=True)

    retire_manager = getattr(manager, "retire_runtime", None)
    if callable(retire_manager):
        retire_manager()
    else:
        delete_later = getattr(manager, "deleteLater", None)
        if callable(delete_later):
            delete_later()

    if getattr(engine, "display_manager", None) is manager:
        engine.display_manager = None
    engine._display_initialized = False
    engine._display_initializing = False
    engine._pending_displays_ready_generation = None
    engine._loading_in_progress = False
    if barrier is not None:
        engine._pending_runtime_destruction_barrier = barrier
        barrier.seal()
    try:
        from core.performance.resource_metrics import log_lifecycle_resource_snapshot

        log_lifecycle_resource_snapshot(
            engine,
            event=reason,
            stage="after_roots_queued",
        )
    except Exception:
        logger.debug("Lifecycle root-queue snapshot failed", exc_info=True)
    logger.info(
        "[LIFECYCLE] Full display teardown complete reason=%s generation=%s",
        reason,
        getattr(engine, "_runtime_generation", "unknown"),
    )
    return barrier

# ------------------------------------------------------------------
# Engine stop
# ------------------------------------------------------------------

def stop(
    engine: ScreensaverEngine,
    exit_app: bool = True,
    *,
    reason: str | None = None,
) -> None:
    """
    Stop the screensaver engine.

    State transition:
        RUNNING -> STOPPING -> STOPPED (if exit_app=False)
        RUNNING -> SHUTTING_DOWN (if exit_app=True, terminal)

    Args:
        engine: ScreensaverEngine instance
        exit_app: If True, quit the application. If False, just stop the engine.
    """
    from engine.screensaver_engine import EngineState

    # Any queued CUSTOM admission belongs to the runtime that is about to be
    # invalidated.  The admitted CUSTOM path clears its own intent before it
    # calls stop(); all other stop owners reject that queued request here.
    engine._pending_custom_layout_reload_intent = None

    if exit_app:
        engine._terminal_shutdown_requested = True
        pending_barrier = getattr(
            engine, "_pending_runtime_destruction_barrier", None
        )
        cancel_barrier = getattr(
            pending_barrier, "cancel_for_terminal_shutdown", None
        )
        if callable(cancel_barrier):
            cancel_barrier()
        active_dialog = getattr(engine, "_active_settings_dialog", None)
        close_dialog = getattr(active_dialog, "close", None)
        if callable(close_dialog):
            try:
                close_dialog()
            except (RuntimeError, TypeError):
                logger.debug(
                    "[LIFECYCLE] Active Settings dialog already destroyed"
                )
        engine._active_settings_dialog = None

    current_state = engine._get_state()
    if (
        not exit_app
        and not bool(getattr(engine, "_running", False))
        and current_state not in {
        EngineState.RUNNING,
        EngineState.STARTING,
        EngineState.REINITIALIZING,
        }
    ):
        logger.debug("Engine stop ignored in state=%s", current_state.name)
        return

    lifecycle_reason = str(
        reason
        or ("application_exit" if exit_app else "runtime_reconfiguration")
    )

    # Determine target state based on exit_app
    target_state = EngineState.SHUTTING_DOWN if exit_app else EngineState.STOPPING

    # Transition to stopping/shutting_down state
    # This makes _shutting_down property return True, signaling async tasks to abort
    if not engine._transition_state(
        target_state,
        expected_from=[EngineState.RUNNING, EngineState.STARTING, EngineState.REINITIALIZING]
    ):
        logger.warning(f"Stop called in unexpected state: {engine._get_state().name}")
        # Force transition anyway for safety
        with engine._state_lock:
            engine._state = target_state

    advance_generation = getattr(engine, "_advance_runtime_generation", None)
    if callable(advance_generation):
        advance_generation(lifecycle_reason)
    else:
        engine._runtime_generation = int(getattr(engine, "_runtime_generation", 0)) + 1
    try:
        from core.performance.resource_metrics import log_lifecycle_resource_snapshot

        log_lifecycle_resource_snapshot(
            engine,
            event=lifecycle_reason,
            stage="after_generation_invalidation",
        )
    except Exception:
        logger.debug("Lifecycle generation snapshot failed", exc_info=True)
    engine._pending_displays_ready_generation = None
    engine._pending_monitor_replay_image = None
    engine._prefetch_resume_scheduled = False

    try:
        logger.info("Stopping screensaver engine...")
        # exit_app parameter intentionally unused in debug log
        logger.debug("Engine stop requested (exit_app=%s)", exit_app)

        # Signal RSS coordinator to abort any in-progress waits immediately
        if engine.rss_coordinator:
            try:
                engine.rss_coordinator.request_stop()
            except Exception as e:
                logger.debug(f"RSSCoordinator request_stop failed: {e}")

        # Stop background RSS refresh timer if present so no further
        # callbacks run after teardown begins.
        if engine._rss_refresh_timer is not None:
            stop_qtimer_safe(engine, engine._rss_refresh_timer, description="Background RSS refresh timer")
            engine._rss_refresh_timer = None

        # Stop rotation timer (do not delete here to avoid double-delete on repeated stops)
        if engine._rotation_timer:
            stop_qtimer_safe(engine, engine._rotation_timer, description="Engine rotation timer")
            engine._rotation_timer = None

        # A pause is a full runtime boundary: no display, widget, timer, or GL
        # object survives into Settings/CUSTOM reconfiguration.
        teardown_display_runtime(
            engine,
            reason=lifecycle_reason,
        )
        # Stop any pending image loads
        engine._loading_in_progress = False

        try:
            from core.windows import reddit_helper_runtime
            reddit_helper_runtime.clear_session_ticket(source="engine_stop")
        except Exception as e:
            logger.debug("Helper session ticket cleanup skipped: %s", e)

        # Force-stop shared beat engine audio worker to release audio threads
        if exit_app:
            try:
                from widgets.spotify_visualizer.beat_engine import BeatEngineRegistry, _global_beat_engine
                if _global_beat_engine is not None:
                    _global_beat_engine.force_stop()
                BeatEngineRegistry.get_instance().clear()
                logger.info("Shared beat engine audio worker force-stopped")
            except Exception as e:
                logger.debug("Beat engine force-stop failed: %s", e)

        # The opt-in sampler shares the app ThreadManager and must quiesce
        # before that pool. Keep it alive across settings pauses so a profiling
        # run remains continuous through the stop/restart cycle.
        if exit_app:
            usage_telemetry = getattr(engine, "_usage_telemetry", None)
            if usage_telemetry is not None:
                try:
                    usage_telemetry.stop()
                except Exception as e:
                    logger.debug("[USAGE] Failed to stop usage telemetry: %s", e)
                engine._usage_telemetry = None

        # Shutdown ProcessSupervisor and all workers
        if exit_app and engine._process_supervisor:
            logger.info("Shutting down ProcessSupervisor...")
            try:
                engine._process_supervisor.shutdown()
                logger.info("ProcessSupervisor shutdown complete")
            except Exception as e:
                logger.warning("ProcessSupervisor shutdown failed: %s", e, exc_info=True)

        # Shutdown ThreadManager to stop all IO/compute threads
        if exit_app and engine.thread_manager:
            logger.info("Shutting down ThreadManager...")
            try:
                # wait=True so non-daemon pool threads are joined.
                # Active tasks were already cancelled above so this should
                # complete quickly. Stuck threads would be killed by OS on
                # process exit anyway, but joining avoids lingering processes.
                shutdown_complete = engine.thread_manager.shutdown(
                    wait=True,
                    timeout=5.0,
                )
                if shutdown_complete is False:
                    raise RuntimeError(
                        "ThreadManager still has executing compute-lane work"
                    )
                logger.info("ThreadManager shutdown complete")
            except Exception as e:
                logger.warning("ThreadManager shutdown failed: %s", e, exc_info=True)

        # Emit a concise image cache summary for profiling.
        # Dual-tagged for the PERF and cache sidecars so cache investigations
        # retain their bounded stop summary without adding it to the main log.
        if is_perf_metrics_enabled() or is_cache_logging_enabled():
            try:
                if engine._image_cache is not None:
                    stats = engine._image_cache.get_stats()
                    logger.info(
                        "[PERF] [CACHE] ImageCache: items=%d/%d, mem=%.1f/%.0fMB, hits=%d, "
                        "misses=%d, hit_rate=%.1f%%%%, evictions=%d",
                        stats.get('item_count', 0),
                        stats.get('max_items', 0),
                        stats.get('memory_usage_mb', 0.0),
                        stats.get('max_memory_mb', 0.0),
                        stats.get('hits', 0),
                        stats.get('misses', 0),
                        stats.get('hit_rate_percent', 0.0),
                        stats.get('evictions', 0),
                    )
                    logger.info(
                        "[PERF] [CACHE] ImageCacheRepresentations: raw_items=%d raw_mb=%.1f "
                        "scaled_items=%d scaled_mb=%.1f raw_evictions=%d scaled_evictions=%d "
                        "raw_evicted_mb=%.1f scaled_evicted_mb=%.1f replacements=%d "
                        "idempotent_puts_avoided=%d",
                        int(stats.get("raw_items", 0)),
                        int(stats.get("raw_bytes", 0)) / (1024 * 1024),
                        int(stats.get("scaled_items", 0)),
                        int(stats.get("scaled_bytes", 0)) / (1024 * 1024),
                        int(stats.get("raw_evictions", 0)),
                        int(stats.get("scaled_evictions", 0)),
                        int(stats.get("raw_evicted_bytes", 0)) / (1024 * 1024),
                        int(stats.get("scaled_evicted_bytes", 0)) / (1024 * 1024),
                        int(stats.get("replacements", 0)),
                        int(stats.get("idempotent_puts_avoided", 0)),
                    )
                cache_flow = getattr(engine, "_cache_runtime_stats", None)
                if isinstance(cache_flow, dict):
                    logger.info(
                        "[PERF] [CACHE] ImageCacheFlow: raw_hits=%d raw_misses=%d scaled_hits=%d "
                        "scaled_misses=%d worker_requests=%d worker_fallbacks=%d "
                        "scaled_prefetch_requests=%d "
                        "scaled_prefetch_completed=%d scaled_derivations=%d "
                        "raw_released_after_scaled=%d raw_prefetch_paths=%d "
                        "raw_prefetch_skipped_display_ready=%d "
                        "scaled_reuses_without_put=%d "
                        "prefetch_resume_scheduled=%d prefetch_resume_runs=%d",
                        int(cache_flow.get("raw_hits", 0)),
                        int(cache_flow.get("raw_misses", 0)),
                        int(cache_flow.get("scaled_hits", 0)),
                        int(cache_flow.get("scaled_misses", 0)),
                        int(cache_flow.get("worker_requests", 0)),
                        int(cache_flow.get("worker_fallbacks", 0)),
                        int(cache_flow.get("scaled_prefetch_requests", 0)),
                        int(cache_flow.get("scaled_prefetch_completed", 0)),
                        int(cache_flow.get("scaled_derivations", 0)),
                        int(cache_flow.get("raw_released_after_scaled", 0)),
                        int(cache_flow.get("raw_prefetch_paths", 0)),
                        int(
                            cache_flow.get(
                                "raw_prefetch_skipped_display_ready",
                                0,
                            )
                        ),
                        int(cache_flow.get("scaled_reuses_without_put", 0)),
                        int(cache_flow.get("prefetch_resume_scheduled", 0)),
                        int(cache_flow.get("prefetch_resume_runs", 0)),
                    )
            except Exception as e:
                logger.debug("[PERF] ImageCache summary logging failed: %s", e, exc_info=True)

        # Clear class-level flag for widget perf logging
        with engine._instance_lock:
            engine.__class__._instance_running = False

        # Transition to final state
        if not exit_app:
            # If not exiting, transition to STOPPED (can restart)
            engine._transition_state(EngineState.STOPPED)
        # If exit_app=True, stay in SHUTTING_DOWN (terminal state)

        engine.stopped.emit()
        logger.info("Screensaver engine stopped")

        # Only exit the Qt event loop if requested
        if exit_app:
            QApplication.quit()

    except Exception as e:
        logger.exception("Engine stop failed: %s", e)
        if exit_app:
            try:
                QApplication.quit()
            except Exception as quit_error:
                logger.error("Failed to quit application: %s", quit_error)
        raise


# ------------------------------------------------------------------
# Engine cleanup
# ------------------------------------------------------------------

def cleanup(engine: ScreensaverEngine) -> None:
    """Clean up all resources."""
    logger.info("Cleaning up screensaver engine...")

    try:
        pending_barrier = getattr(
            engine, "_pending_runtime_destruction_barrier", None
        )
        cancel_barrier = getattr(
            pending_barrier, "cancel_for_terminal_shutdown", None
        )
        if callable(cancel_barrier):
            cancel_barrier()
        # Stop if running
        if engine._running:
            engine.stop()

        # Emit a concise summary tying together queue stats and transition skips
        # for prefetch vs transition-skip pacing diagnostics.
        # Tagged with "[PERF] Engine summary" so production builds can grep
        # and gate/strip this debug telemetry if desired.
        if is_perf_metrics_enabled():
            try:
                if engine.image_queue:
                    qstats = engine.image_queue.get_stats()
                else:
                    qstats = None
                dstats = None
                if engine.display_manager:
                    try:
                        dstats = engine.display_manager.get_display_info()
                    except Exception as e:
                        logger.debug("[PERF] Engine summary display info failed: %s", e, exc_info=True)
                        dstats = None
                logger.info(
                    "[PERF] Engine summary: queue=%s, displays=%s",
                    qstats,
                    dstats,
                )
            except Exception as e:
                logger.debug("[PERF] Engine summary logging failed: %s", e, exc_info=True)

        # Clean up a residual display stack even if the engine was already stopped.
        teardown_display_runtime(engine, reason="engine_cleanup")
        # Cleanup thread manager
        if engine.thread_manager:
            try:
                engine.thread_manager.shutdown()
                logger.debug("Thread manager shut down")
            except Exception as e:
                logger.warning("ThreadManager.shutdown() failed during engine cleanup: %s", e, exc_info=True)

        # Cleanup shared animation manager
        if engine.animation_manager:
            try:
                engine.animation_manager.cleanup()
                logger.debug("Animation manager cleaned up")
            except Exception as e:
                logger.warning("AnimationManager.cleanup() failed during engine cleanup: %s", e, exc_info=True)

        # Cleanup resource manager
        if engine.resource_manager:
            try:
                engine.resource_manager.cleanup_all()
                logger.debug("Resources cleaned up")
            except Exception as e:
                logger.warning("ResourceManager.cleanup_all() failed during engine cleanup: %s", e, exc_info=True)

        # Clear sources
        engine.folder_sources.clear()
        engine.rss_coordinator = None


        logger.info("Engine cleanup complete")

    except Exception as e:
        logger.exception(f"Cleanup failed: {e}")
