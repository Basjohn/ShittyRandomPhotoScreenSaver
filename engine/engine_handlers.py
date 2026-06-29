"""Engine Event Handlers - Extracted from screensaver_engine.py.

Contains hotkey/event handlers that coordinate between subsystems:
cycle transition, settings dialog, source reconfiguration.
All functions accept the engine instance as the first parameter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import time

from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger
from core.animation import AnimationManager
from core.settings import SettingsManager
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
    logger.info("Settings requested - pausing screensaver and opening config")
    request_start = time.perf_counter()

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
    stop_start = time.perf_counter()
    engine.stop(exit_app=False)
    stop_ms = (time.perf_counter() - stop_start) * 1000
    overall_ms = (time.perf_counter() - request_start) * 1000
    logger.info("Settings stop() completed in %.1f ms (%.1f ms since request)", stop_ms, overall_ms)

    app = QApplication.instance()

    try:
        if app:
            animations = AnimationManager(
                resource_manager=engine.resource_manager,
                owner="settings:dialog",
            )
            dialog_init_start = time.perf_counter()
            dialog = SettingsDialog(engine.settings_manager, animations)
            init_ms = (time.perf_counter() - dialog_init_start) * 1000
            since_request_ms = (time.perf_counter() - request_start) * 1000
            logger.info(
                "Settings dialog instantiated in %.1f ms (%.1f ms since request)",
                init_ms,
                since_request_ms,
            )
            exec_start = time.perf_counter()
            logger.info("Entering settings dialog exec (%.1f ms since request)", (exec_start - request_start) * 1000)
            try:
                _ = dialog.exec()
            finally:
                try:
                    animations.cleanup()
                except Exception:
                    logger.debug("Settings dialog AnimationManager cleanup failed", exc_info=True)
                try:
                    dialog.deleteLater()
                except Exception:
                    logger.debug("Settings dialog deleteLater failed", exc_info=True)
            exec_duration = (time.perf_counter() - exec_start) * 1000

            # After dialog closes, fully reset displays and restart
            logger.info("Settings dialog closed, performing full-style restart of screensaver")

            # Tear down any existing display manager stack so we get a fresh
            # set of DisplayWidget instances (clears stale GL/compositor state
            # and avoids banding on secondary displays).
            if engine.display_manager:
                try:
                    engine.display_manager.cleanup()
                except Exception:
                    logger.debug("DisplayManager cleanup after settings failed", exc_info=True)
                engine.display_manager = None
                engine._display_initialized = False

            # Reset coordinator state (halo owner, ctrl state) to avoid stale refs
            try:
                from rendering.multi_monitor_coordinator import get_coordinator
                coordinator = get_coordinator()
                coordinator.set_settings_dialog_active(False)  # Re-enable halo
                coordinator.cleanup()
            except Exception:
                logger.debug("Coordinator cleanup after settings failed", exc_info=True)

            DisplayWidget.suppress_pointer_input_globally(
                700,
                reason="settings_display_recreation",
            )

            # Reinitialize displays using current settings
            if not engine._initialize_display():
                logger.error("Failed to reinitialize displays after settings; quitting")
                QApplication.quit()
                return

            # Recreate rotation timer with any updated timing settings
            engine._setup_rotation_timer()

            # Note: stop(exit_app=False) already transitioned state to STOPPED,
            # so start() will not early-out. No need to manually set _running.

            if not engine.start():
                logger.error("Failed to restart screensaver after settings; quitting")
                QApplication.quit()
                return

            total_duration = (time.perf_counter() - request_start) * 1000
            logger.info("Settings lifecycle complete in %.1f ms (dialog exec %.1f ms)", total_duration, exec_duration)
    except Exception as e:
        logger.exception(f"Failed to open settings dialog: {e}")
        QApplication.quit()


def on_custom_layout_reload_requested(engine: ScreensaverEngine) -> None:
    """Handle committed CUSTOM layout changes with a full clean runtime reload."""
    logger.info("CUSTOM layout reload requested")

    try:
        engine.stop(exit_app=False)

        if engine.display_manager:
            try:
                engine.display_manager.cleanup()
            except Exception:
                logger.debug("DisplayManager cleanup after custom layout reload failed", exc_info=True)
            engine.display_manager = None
            engine._display_initialized = False

        try:
            from rendering.multi_monitor_coordinator import get_coordinator
            coordinator = get_coordinator()
            coordinator.cleanup()
        except Exception:
            logger.debug("Coordinator cleanup after custom layout reload failed", exc_info=True)

        DisplayWidget.suppress_pointer_input_globally(
            700,
            reason="custom_layout_runtime_reload",
        )

        try:
            if engine.settings_manager is not None:
                engine.settings_manager.load()
        except Exception:
            logger.debug("Settings reload after custom layout commit failed", exc_info=True)

        if not engine._initialize_display():
            logger.error("Failed to reinitialize displays after custom layout reload; quitting")
            QApplication.quit()
            return

        engine._setup_rotation_timer()

        if not engine.start():
            logger.error("Failed to restart screensaver after custom layout reload; quitting")
            QApplication.quit()
            return

        logger.info("CUSTOM layout runtime reload complete")
    except Exception as e:
        logger.exception("Failed to reload screensaver after CUSTOM layout commit: %s", e)
        QApplication.quit()


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

    logger.info("Sources changed, reinitializing...")

    # Save current state to restore after reinitialization
    was_running = engine._running

    # Transition to REINITIALIZING state
    # This is NOT a shutdown - _shutting_down will return False
    # allowing async RSS loading to proceed
    if was_running:
        engine._transition_state(EngineState.REINITIALIZING)

    # Clear image cache - old cached images may no longer be valid
    if engine._image_cache:
        try:
            engine._image_cache.clear()
            logger.info("Image cache cleared due to source change")
        except Exception as e:
            logger.debug(f"Failed to clear image cache: {e}")

    # Clear prefetcher inflight set to avoid stale paths
    if engine._prefetcher:
        try:
            engine._prefetcher.clear_inflight()
        except Exception as e:
            logger.debug(f"Failed to clear prefetcher inflight: {e}")

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
