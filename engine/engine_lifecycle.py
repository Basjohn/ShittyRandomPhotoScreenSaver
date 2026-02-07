"""Engine Lifecycle - Extracted from screensaver_engine.py.

Contains stop, cleanup, and QTimer safety helpers for the engine
shutdown sequence. All functions accept the engine instance as the
first parameter to preserve the original interface.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QTimer, QMetaObject, Qt, QThread
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger, is_perf_metrics_enabled

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
# Engine stop
# ------------------------------------------------------------------

def stop(engine: ScreensaverEngine, exit_app: bool = True) -> None:
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

    # Check if running (using property)
    if not engine._running:
        logger.debug("Engine not running")
        return

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

        # Clear and hide/cleanup displays
        if engine.display_manager:
            try:
                try:
                    display_count = engine.display_manager.get_display_count()
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    display_count = len(getattr(engine.display_manager, "displays", []))
                logger.info(
                    "Stopping displays via DisplayManager (count=%s, exit_app=%s)",
                    display_count,
                    exit_app,
                )
            except Exception:
                logger.info(
                    "Stopping displays via DisplayManager (count=?, exit_app=%s)",
                    exit_app,
                )

            # Instrumentation: aggregate display states before shutdown
            if is_perf_metrics_enabled():
                try:
                    display_states = []
                    for disp in getattr(engine.display_manager, "displays", []):
                        try:
                            state = disp.describe_runtime_state()
                            display_states.append(state)
                        except Exception as exc:
                            logger.debug("[ENGINE] Failed to get display state: %s", exc)
                    logger.info("[PERF][ENGINE] pre_clear_display_states count=%s states=%s", display_count, display_states)
                except Exception as exc:
                    logger.debug("[ENGINE] Failed to aggregate display states: %s", exc)

            try:
                engine.display_manager.clear_all()
            except Exception as e:
                logger.debug("DisplayManager.clear_all() failed during stop: %s", e, exc_info=True)

            if exit_app:
                # Exiting app - full cleanup
                try:
                    engine.display_manager.cleanup()
                    logger.debug("Displays cleared and cleaned up")
                except Exception as e:
                    logger.warning("DisplayManager.cleanup() failed during stop: %s", e, exc_info=True)
                else:
                    try:
                        engine.display_manager.flush_deferred_reddit_urls(ensure_widgets_dismissed=True)
                    except Exception as e:
                        logger.warning("Deferred Reddit flush failed: %s", e, exc_info=True)
            else:
                # Just pausing (e.g., for settings) - hide windows
                try:
                    engine.display_manager.hide_all()
                    logger.debug("Displays cleared and hidden")
                except Exception as e:
                    logger.warning("DisplayManager.hide_all() failed during stop: %s", e, exc_info=True)

        # Stop any pending image loads
        engine._loading_in_progress = False

        # Force-stop shared beat engine audio worker to release audio threads
        if exit_app:
            try:
                from widgets.spotify_visualizer.beat_engine import _global_beat_engine
                if _global_beat_engine is not None:
                    _global_beat_engine.force_stop()
                    logger.info("Shared beat engine audio worker force-stopped")
            except Exception as e:
                logger.debug("Beat engine force-stop failed: %s", e)

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
                engine.thread_manager.shutdown(wait=True)
                logger.info("ThreadManager shutdown complete")
            except Exception as e:
                logger.warning("ThreadManager shutdown failed: %s", e, exc_info=True)

        engine.stopped.emit()
        logger.info("Screensaver engine stopped")

        # Emit a concise image cache summary for profiling.
        # Tagged with "[PERF] ImageCache" so production builds can grep and
        # gate/strip this debug telemetry if desired.
        if is_perf_metrics_enabled():
            try:
                if engine._image_cache is not None:
                    stats = engine._image_cache.get_stats()
                    logger.info(
                        "[PERF] ImageCache: items=%d/%d, mem=%.1f/%.0fMB, hits=%d, "
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
        logger.exception(f"Engine stop failed: {e}")
        # Force quit on error only if exit_app was requested
        if exit_app:
            try:
                QApplication.quit()
            except Exception as quit_error:
                logger.error(f"Failed to quit application: {quit_error}")


# ------------------------------------------------------------------
# Engine cleanup
# ------------------------------------------------------------------

def cleanup(engine: ScreensaverEngine) -> None:
    """Clean up all resources."""
    logger.info("Cleaning up screensaver engine...")

    try:
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

        # Cleanup display manager
        if engine.display_manager:
            try:
                engine.display_manager.cleanup()
                logger.debug("Display manager cleaned up")
            except Exception as e:
                logger.warning("DisplayManager.cleanup() failed during engine cleanup: %s", e, exc_info=True)
            else:
                try:
                    engine.display_manager.flush_deferred_reddit_urls(ensure_widgets_dismissed=True)
                except Exception as e:
                    logger.warning("Deferred Reddit flush failed during engine cleanup: %s", e, exc_info=True)

        # Cleanup thread manager
        if engine.thread_manager:
            try:
                engine.thread_manager.shutdown()
                logger.debug("Thread manager shut down")
            except Exception as e:
                logger.warning("ThreadManager.shutdown() failed during engine cleanup: %s", e, exc_info=True)

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

        # Cleanup global shader program singletons
        try:
            from rendering.gl_compositor import cleanup_global_shader_programs
            cleanup_global_shader_programs()
            logger.debug("Global shader programs cleaned up")
        except Exception as e:
            logger.debug("Shader cleanup skipped: %s", e)

        logger.info("Engine cleanup complete")

    except Exception as e:
        logger.exception(f"Cleanup failed: {e}")
