"""Engine Event Handlers - Extracted from screensaver_engine.py.

Contains hotkey/event handlers that coordinate between subsystems:
cycle transition, settings dialog, source reconfiguration.
All functions accept the engine instance as the first parameter.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
import time

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger
from core.animation import AnimationManager
from core.performance.resource_metrics import log_lifecycle_resource_snapshot
from core.settings import SettingsManager
from core.threading.manager import ThreadManager
from rendering.transition_registry import get_transition_descriptor, is_transition_available_for_hw
from rendering.display_widget import DisplayWidget
from ui.settings_dialog import SettingsDialog

if TYPE_CHECKING:
    from engine.screensaver_engine import ScreensaverEngine

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Cycle transition (C key)
# ------------------------------------------------------------------

def on_cycle_transition(engine: ScreensaverEngine) -> None:
    """Handle cycle transition request (C key)."""
    logger.info("Cycle transition requested")

    if not engine._transition_types:
        logger.warning("No transitions configured; ignoring cycle request")
        return

    raw_hw = engine.settings_manager.get('display.hw_accel', False)
    hw = SettingsManager.to_bool(raw_hw, False)
    transitions_config = engine.settings_manager.get('transitions', {})
    if not isinstance(transitions_config, dict):
        transitions_config = {}
    pool_cfg = transitions_config.get('pool', {}) if isinstance(transitions_config.get('pool', {}), dict) else {}

    def _in_pool(name: str) -> bool:
        try:
            descriptor = get_transition_descriptor(name)
            pool_name = descriptor.random_pool_name if descriptor is not None and descriptor.random_pool_name else name
            raw_flag = pool_cfg.get(pool_name, True)
            return bool(SettingsManager.to_bool(raw_flag, True))
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            return True

    # Cycle to next transition honoring HW capabilities and per-type pool
    # membership. Types excluded from the pool will not be selected when
    # cycling, but remain available for explicit selection via settings.
    for _ in range(len(engine._transition_types)):
        engine._current_transition_index = (engine._current_transition_index + 1) % len(engine._transition_types)
        candidate = engine._transition_types[engine._current_transition_index]
        if not is_transition_available_for_hw(candidate, hw) or not _in_pool(candidate):
            continue
        new_transition = candidate
        break
    else:
        # Fallback to Crossfade if somehow no valid transition found
        new_transition = "Crossfade"
        engine._current_transition_index = engine._transition_types.index(new_transition) if new_transition in engine._transition_types else 0

    # Update settings with permissible transition
    if not is_transition_available_for_hw(new_transition, hw):
        new_transition = "Crossfade"
        if new_transition in engine._transition_types:
            engine._current_transition_index = engine._transition_types.index(new_transition)
    transitions_config = engine.settings_manager.get('transitions', {})
    if not isinstance(transitions_config, dict):
        transitions_config = {}
    transitions_config['type'] = new_transition
    transitions_config['random_always'] = False
    # Clear cached random selections from the dict itself so the
    # subsequent set() doesn't re-introduce stale values.
    transitions_config.pop('random_choice', None)
    transitions_config.pop('last_random_choice', None)
    engine.settings_manager.set('transitions', transitions_config)
    engine.settings_manager.save()

    logger.info(f"Transition cycled to: {new_transition}")

    # FIX: Don't force same image on all displays - preserve multi-monitor independence
    # Each display should keep its current image and just use the new transition type
    # No need to reload - the transition type is stored in settings and will be used
    # on the next natural image change
    logger.debug("Transition type updated in settings - will apply on next image change")


# ------------------------------------------------------------------
# Settings dialog (S key)
# ------------------------------------------------------------------

def on_settings_requested(engine: ScreensaverEngine) -> None:
    """Handle settings request (S key)."""
    if bool(getattr(engine, "_settings_dialog_active", False)) or getattr(
        engine, "_pending_runtime_destruction_barrier", None
    ) is not None:
        logger.info(
            "[LIFECYCLE] Duplicate Settings request ignored while recreation is active"
        )
        return
    logger.info("Settings requested - pausing screensaver and opening config")
    request_start = time.perf_counter()
    engine._settings_dialog_active = True
    engine._sources_changed_during_settings = False

    try:
        from rendering.custom_layout_manager import CustomLayoutManager

        if CustomLayoutManager.is_any_session_active():
            logger.info("Settings requested during active CUSTOM edit session; cancelling session before teardown")
            active_manager = CustomLayoutManager.active_manager()
            if active_manager is not None:
                active_manager.cancel_session()
    except Exception:
        logger.debug("Failed to cancel CUSTOM edit session before settings", exc_info=True)

    # Wake media widget from idle mode when returning from settings
    # This ensures Spotify detection resumes if user opened Spotify while in settings
    try:
        if engine.display_manager:
            for display in engine.display_manager.displays:
                media_widget = getattr(display, 'media_widget', None)
                if media_widget and hasattr(media_widget, 'wake_from_idle'):
                    media_widget.wake_from_idle()
    except Exception as e:
        logger.debug("[ENGINE] Failed to wake media widget from idle: %s", e)

    coordinator = None
    # Set settings dialog active flag FIRST - this prevents halo from showing
    try:
        from rendering.multi_monitor_coordinator import get_coordinator
        coordinator = get_coordinator()
        coordinator.set_settings_dialog_active(True)
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)

    # Hide and destroy all cursor halo windows
    if engine.display_manager:
        for display in getattr(engine.display_manager, 'displays', []):
            try:
                halo = getattr(display, '_ctrl_cursor_hint', None)
                if halo is not None:
                    halo.hide()
                    halo.close()
                    halo.deleteLater()
                    display._ctrl_cursor_hint = None
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)

    # Stop the engine but DON'T exit the app
    log_lifecycle_resource_snapshot(
        engine,
        event="settings",
        stage="before_stop",
    )
    stop_start = time.perf_counter()
    try:
        # stop(exit_app=False) owns the complete display/GL teardown. A second
        # teardown call here would create a shadow lifecycle path.
        engine.stop(exit_app=False, reason="settings")
    except Exception:
        engine._settings_dialog_active = False
        try:
            if coordinator is not None:
                coordinator.set_settings_dialog_active(False)
        except Exception:
            logger.debug("Coordinator reset after failed Settings teardown failed", exc_info=True)
        logger.critical(
            "[LIFECYCLE] Settings admission aborted because runtime teardown failed",
            exc_info=True,
        )
        QApplication.exit(1)
        return
    log_lifecycle_resource_snapshot(
        engine,
        event="settings",
        stage="after_stop",
    )
    log_lifecycle_resource_snapshot(
        engine,
        event="settings",
        stage="after_display_cleanup",
    )
    stop_ms = (time.perf_counter() - stop_start) * 1000
    overall_ms = (time.perf_counter() - request_start) * 1000
    logger.info("Settings stop() completed in %.1f ms (%.1f ms since request)", stop_ms, overall_ms)

    from engine.runtime_destruction import continue_after_runtime_destruction

    continue_after_runtime_destruction(
        engine,
        partial(_open_settings_after_runtime_destroyed, engine, request_start),
    )


def _open_settings_after_runtime_destroyed(
    engine: ScreensaverEngine,
    request_start: float,
) -> None:
    """Open Settings only after every retired display root is destroyed."""

    from engine.runtime_destruction import qt_replacement_may_run

    app = QApplication.instance()
    if app is None or not qt_replacement_may_run(engine):
        engine._settings_dialog_active = False
        return

    try:
        dialog_generation = (
            f"settings-dialog:{getattr(engine, '_runtime_generation', 'unknown')}:"
            f"{time.monotonic_ns()}"
        )
        try:
            animations = AnimationManager(
                resource_manager=engine.resource_manager,
                owner="settings:dialog",
                runtime_generation=dialog_generation,
            )
        except TypeError:
            # Lightweight test doubles and older embedder shims do not expose
            # lifecycle metadata; the QObject destruction barrier still owns
            # their ordering when applicable.
            animations = AnimationManager(
                resource_manager=engine.resource_manager,
                owner="settings:dialog",
            )

        dialog_init_start = time.perf_counter()
        dialog = SettingsDialog(
            engine.settings_manager,
            animations,
            runtime_generation=dialog_generation,
        )
        engine._active_settings_dialog = dialog
        try:
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        except Exception:
            logger.debug("Settings dialog delete-on-close attribute unavailable", exc_info=True)
        init_ms = (time.perf_counter() - dialog_init_start) * 1000
        since_request_ms = (time.perf_counter() - request_start) * 1000
        logger.info(
            "Settings dialog instantiated in %.1f ms (%.1f ms since request)",
            init_ms,
            since_request_ms,
        )
        exec_start = time.perf_counter()
        logger.info(
            "Entering settings dialog exec (%.1f ms since request)",
            (exec_start - request_start) * 1000,
        )
        _ = dialog.exec()
        exec_duration = (time.perf_counter() - exec_start) * 1000
        sources_changed = bool(
            getattr(engine, "_sources_changed_during_settings", False)
        )

        replacement_allowed = qt_replacement_may_run(engine)
        continuation = (
            partial(
                _restart_after_settings_dialog_destroyed,
                engine,
                request_start,
                exec_duration,
                sources_changed,
            )
            if replacement_allowed
            else None
        )

        from engine.runtime_destruction import RuntimeDestructionBarrier

        dialog_barrier = None
        if replacement_allowed and (
            isinstance(dialog, QObject) or isinstance(animations, QObject)
        ):
            dialog_barrier = RuntimeDestructionBarrier(
                engine,
                reason="settings_dialog_close",
                retiring_generation=dialog_generation,
            )
            if isinstance(dialog, QObject):
                dialog_barrier.watch_qobject(dialog, label="SettingsDialog")
                try:
                    for child in dialog.findChildren(QObject):
                        dialog_barrier.watch_qobject(child)
                except RuntimeError:
                    logger.debug(
                        "Settings dialog children already destroyed",
                        exc_info=True,
                    )
            if isinstance(animations, QObject):
                dialog_barrier.watch_qobject(
                    animations,
                    label="SettingsAnimationManager",
                )
                timer = getattr(animations, "_timer", None)
                if isinstance(timer, QObject):
                    dialog_barrier.watch_qobject(
                        timer,
                        label="SettingsAnimationTimer",
                    )

        try:
            animations.cleanup()
        except Exception:
            logger.debug(
                "Settings dialog AnimationManager cleanup failed",
                exc_info=True,
            )
        try:
            animations.deleteLater()
        except Exception:
            logger.debug(
                "Settings AnimationManager deleteLater failed",
                exc_info=True,
            )
        try:
            dialog.close()
        except Exception:
            logger.debug("Settings dialog close failed", exc_info=True)
        try:
            dialog.deleteLater()
        except Exception:
            logger.debug("Settings dialog deleteLater failed", exc_info=True)

        try:
            ThreadManager.cancel_scheduled_single_shots(dialog_generation)
        except RuntimeError:
            logger.critical(
                "[LIFECYCLE] Settings callbacks could not be cancelled on the UI thread",
                exc_info=True,
            )
            QApplication.exit(1)
            return

        engine._active_settings_dialog = None
        if continuation is None:
            engine._settings_dialog_active = False
            return

        if dialog_barrier is None:
            continuation()
        else:
            engine._pending_runtime_destruction_barrier = dialog_barrier
            dialog_barrier.seal()
            dialog_barrier.then(continuation)
    except Exception as e:
        engine._active_settings_dialog = None
        engine._settings_dialog_active = False
        logger.exception("Failed to open settings dialog: %s", e)
        QApplication.quit()


def _restart_after_settings_dialog_destroyed(
    engine: ScreensaverEngine,
    request_start: float,
    exec_duration: float,
    sources_changed_during_settings: bool,
) -> None:
    """Build the replacement runtime after the Settings root barrier."""

    from engine.runtime_destruction import qt_replacement_may_run

    if not qt_replacement_may_run(engine):
        engine._settings_dialog_active = False
        return

    logger.info(
        "Settings dialog destroyed, performing full-style restart of screensaver"
    )
    engine._settings_dialog_active = False
    try:
        from rendering.multi_monitor_coordinator import get_coordinator

        coordinator = get_coordinator()
        coordinator.set_settings_dialog_active(False)
        coordinator.cleanup()
    except Exception:
        logger.debug("Coordinator cleanup after settings failed", exc_info=True)

    DisplayWidget.suppress_pointer_input_globally(
        700,
        reason="settings_display_recreation",
    )
    if not _construct_and_start_replacement_runtime(engine, event="settings"):
        return

    total_duration = (time.perf_counter() - request_start) * 1000
    logger.info(
        "Settings lifecycle complete in %.1f ms "
        "(dialog exec %.1f ms, sources_changed=%s)",
        total_duration,
        exec_duration,
        sources_changed_during_settings,
    )


def _construct_and_start_replacement_runtime(
    engine: ScreensaverEngine,
    *,
    event: str,
) -> bool:
    """Construct one replacement after destruction; reveal remains owner-gated."""

    from engine.runtime_destruction import qt_replacement_may_run

    if not qt_replacement_may_run(engine):
        logger.info(
            "[LIFECYCLE] Replacement runtime construction discarded during terminal shutdown"
        )
        return False
    engine._runtime_lifecycle_event = event

    log_lifecycle_resource_snapshot(
        engine,
        event=event,
        stage="before_replacement_construction",
    )
    if not engine._initialize_display():
        logger.error("Failed to initialize replacement display runtime; quitting")
        QApplication.quit()
        return False
    log_lifecycle_resource_snapshot(
        engine,
        event=event,
        stage="after_replacement_before_first_frame",
    )
    engine._setup_rotation_timer()
    if not engine.start():
        logger.error("Failed to start replacement display runtime; quitting")
        QApplication.quit()
        return False
    log_lifecycle_resource_snapshot(
        engine,
        event=event,
        stage="after_restart",
    )
    return True


def on_custom_layout_reload_requested(engine: ScreensaverEngine) -> None:
    """Handle committed CUSTOM layout changes with a full clean runtime reload."""
    if bool(getattr(engine, "_settings_dialog_active", False)):
        logger.info(
            "[LIFECYCLE] CUSTOM reload ignored while Settings owns runtime recreation"
        )
        return
    if getattr(engine, "_pending_runtime_destruction_barrier", None) is not None:
        logger.info(
            "[LIFECYCLE] Duplicate CUSTOM reload ignored while recreation is active"
        )
        return
    if (
        getattr(engine, "display_manager", None) is None
        or not bool(getattr(engine, "_display_initialized", False))
    ):
        logger.info(
            "[LIFECYCLE] Stale CUSTOM reload ignored without a current display runtime"
        )
        return
    logger.info("CUSTOM layout reload requested")

    try:
        log_lifecycle_resource_snapshot(
            engine,
            event="custom_edit",
            stage="before_stop",
        )
        # stop(exit_app=False) is the single full teardown authority.
        engine.stop(exit_app=False, reason="custom_edit")
        log_lifecycle_resource_snapshot(
            engine,
            event="custom_edit",
            stage="after_stop",
        )
        log_lifecycle_resource_snapshot(
            engine,
            event="custom_edit",
            stage="after_display_cleanup",
        )

        from engine.runtime_destruction import continue_after_runtime_destruction

        continue_after_runtime_destruction(
            engine,
            partial(_restart_after_custom_runtime_destroyed, engine),
        )
    except Exception as e:
        logger.critical(
            "[LIFECYCLE] CUSTOM Edit reload aborted after teardown/rebuild failure: %s",
            e,
            exc_info=True,
        )
        QApplication.exit(1)


def _restart_after_custom_runtime_destroyed(engine: ScreensaverEngine) -> None:
    from engine.runtime_destruction import qt_replacement_may_run

    if not qt_replacement_may_run(engine):
        return
    try:
        from rendering.multi_monitor_coordinator import get_coordinator

        coordinator = get_coordinator()
        coordinator.cleanup()
    except Exception:
        logger.debug(
            "Coordinator cleanup after custom layout reload failed",
            exc_info=True,
        )

    DisplayWidget.suppress_pointer_input_globally(
        700,
        reason="custom_layout_runtime_reload",
    )
    try:
        if engine.settings_manager is not None:
            engine.settings_manager.load()
    except Exception:
        logger.debug(
            "Settings reload after custom layout commit failed",
            exc_info=True,
        )

    if _construct_and_start_replacement_runtime(engine, event="custom_edit"):
        logger.info("CUSTOM layout runtime reload complete")


# ------------------------------------------------------------------
# Source reconfiguration
# ------------------------------------------------------------------

def on_sources_changed(engine: ScreensaverEngine) -> None:
    """Handle source configuration changes.

    State transition: RUNNING -> REINITIALIZING -> RUNNING

    Reinitializes sources and rebuilds the image queue when the user
    adds/removes folders or RSS feeds in settings. This ensures new
    sources are available immediately without restarting the screensaver.

    CRITICAL: Uses REINITIALIZING state (not STOPPING) so that:
    - _shutting_down property returns False
    - Async RSS loading continues (does NOT abort)
    This was the root cause of the RSS reload bug.
    """
    from engine.screensaver_engine import EngineState

    if getattr(engine, "_settings_dialog_active", False) or engine._is_state(EngineState.STOPPED):
        engine._sources_changed_during_settings = True
        logger.info(
            "Sources changed while settings/runtime restart is active; deferring source rebuild until settings close"
        )
        return

    logger.info("Sources changed, reinitializing...")

    # Save current state to restore after reinitialization
    was_running = engine._running

    # Transition to REINITIALIZING state
    # This is NOT a shutdown - _shutting_down will return False
    # allowing async RSS loading to proceed
    if was_running:
        engine._transition_state(EngineState.REINITIALIZING)

    # Invalidate prefetch ownership before clearing the cache. A callback that
    # completes on either side of this boundary must be rejected or cleared,
    # never repopulate the new source generation after cache.clear().
    if engine._prefetcher:
        try:
            engine._prefetcher.clear_inflight()
        except Exception as e:
            logger.debug(f"Failed to clear prefetcher inflight: {e}")

    # Clear image cache - old cached images may no longer be valid
    if engine._image_cache:
        try:
            engine._image_cache.clear()
            logger.info("Image cache cleared due to source change")
        except Exception as e:
            logger.debug(f"Failed to clear image cache: {e}")

    # Clear existing sources
    engine.folder_sources.clear()
    engine.rss_coordinator = None

    # Reinitialize sources from updated settings
    if engine._initialize_sources():
        # Rebuild the queue with new sources
        if engine._build_image_queue():
            logger.info("Image queue rebuilt with updated sources")

            # Reset prefetcher for new queue
            if hasattr(engine, '_prefetcher') and engine._prefetcher:
                try:
                    engine._prefetcher.clear_inflight()
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)

            # Re-create prefetcher only if cache is available
            if engine._image_cache and engine.thread_manager:
                try:
                    from utils.image_prefetcher import ImagePrefetcher
                    engine._prefetcher = ImagePrefetcher(
                        thread_manager=engine.thread_manager,
                        cache=engine._image_cache,
                        max_concurrent=2,
                    )
                    logger.info("Prefetcher restarted with updated queue")
                except Exception as e:
                    logger.warning(f"Failed to restart prefetcher: {e}")
            elif not engine._image_cache:
                logger.debug("Skipping prefetcher restart — image cache not initialized yet")
        else:
            logger.warning("Failed to rebuild image queue after source change")
    else:
        logger.warning("No valid sources after source change")

    # Restore to RUNNING state if we were running before
    if was_running:
        engine._transition_state(EngineState.RUNNING)
        logger.info("Sources reinitialization complete, engine back to RUNNING")
