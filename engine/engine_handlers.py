"""Engine Event Handlers - Extracted from screensaver_engine.py.

Contains hotkey/event handlers that coordinate between subsystems:
cycle transition, settings dialog, source reconfiguration.
All functions accept the engine instance as the first parameter.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING
import time

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid as _is_valid_qobject

from core.logging.logger import get_logger
from core.build_profile import is_diagnostic_build
from core.animation import AnimationManager
from core.performance.resource_metrics import log_lifecycle_resource_snapshot
from core.settings import SettingsManager
from core.threading.manager import ThreadManager
from rendering.transition_registry import get_transition_descriptor, is_transition_available_for_hw
from core.settings.capability_activation import (
    DEFAULT_RECOVERY_TRANSITION,
    ensure_recovery_transition_activated,
    get_default_activated_transition,
    is_transition_activated,
    normalize_transition_capability_state,
)
from rendering.runtime_input import suppress_runtime_pointer_input
from ui.settings_dialog import SettingsDialog

if TYPE_CHECKING:
    from engine.screensaver_engine import ScreensaverEngine

logger = get_logger(__name__)


def _record_diagnostic_stage(stage: str, **fields: object) -> None:
    """Write a frozen-crash breadcrumb only in the dedicated diagnostic build."""

    if not is_diagnostic_build():
        return
    from core.logging.crash_capture import record_diagnostic_stage

    record_diagnostic_stage(stage, **fields)


@dataclass(frozen=True, slots=True)
class CustomLayoutReloadIntent:
    """Primitive-only handoff from an Edit frame to the engine GUI turn."""

    request_kind: str
    runtime_generation: int
    display_manager_identity: int


@dataclass(frozen=True, slots=True)
class SettingsRequestIntent:
    """Primitive-only handoff from a display input frame to the engine turn."""

    runtime_generation: int
    display_manager_identity: int


def _qobject_wrapper_is_valid(value: object) -> bool:
    """Return whether a Python QObject wrapper still owns a live C++ object."""

    if not isinstance(value, QObject):
        return False
    try:
        return bool(_is_valid_qobject(value))
    except (RuntimeError, TypeError):
        return False


# ------------------------------------------------------------------
# Cycle transition (C key)
# ------------------------------------------------------------------

def _resolve_cycle_fallback(engine: ScreensaverEngine, transitions_config: dict, hw: bool) -> str:
    """Return a deterministic activated, hw-available transition for C-key cycling.

    Never returns a deactivated Crossfade: prefer the canonical activated
    default, then any activated hw-available transition, and only as a last
    resort perform the explicit canonical recovery repair (persisting it) and
    return the now-activated recovery transition.
    """
    candidate = get_default_activated_transition(transitions_config)
    if is_transition_available_for_hw(candidate, hw) and is_transition_activated(transitions_config, candidate):
        return candidate
    for name in engine._transition_types:
        if is_transition_available_for_hw(name, hw) and is_transition_activated(transitions_config, name):
            return name
    if ensure_recovery_transition_activated(transitions_config):
        engine.settings_manager.set('transitions', transitions_config)
        engine.settings_manager.save()
    return DEFAULT_RECOVERY_TRANSITION


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
    # Canonical activation normalization before manual cycling (the one authority).
    if normalize_transition_capability_state(transitions_config):
        engine.settings_manager.set('transitions', transitions_config)
        engine.settings_manager.save()
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
        # A deactivated transition is excluded from explicit runtime cycling.
        if not is_transition_activated(transitions_config, candidate):
            continue
        new_transition = candidate
        break
    else:
        # No activated, pooled, hw-available candidate found while cycling. Fall
        # back to a deterministic activated transition, never a deactivated
        # Crossfade (see _resolve_cycle_fallback).
        new_transition = _resolve_cycle_fallback(engine, transitions_config, hw)
        if new_transition in engine._transition_types:
            engine._current_transition_index = engine._transition_types.index(new_transition)

    # Update settings with a permissible, activated transition.
    if not is_transition_available_for_hw(new_transition, hw) or not is_transition_activated(transitions_config, new_transition):
        new_transition = _resolve_cycle_fallback(engine, transitions_config, hw)
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

def request_settings_requested(engine: ScreensaverEngine) -> None:
    """Queue Settings admission after the emitting display input frame returns.

    Destroying the display graph synchronously inside a destination window's
    key event / Qt signal stack is undefined native ownership. Script builds can
    appear to tolerate it while frozen PySide builds terminate in Qt. Carry
    only primitive runtime identity into a zero-delay engine-owned callback,
    then validate that identity before invoking the existing teardown owner.
    """
    if (
        bool(getattr(engine, "_settings_dialog_active", False))
        or getattr(engine, "_pending_runtime_destruction_barrier", None) is not None
    ):
        logger.info(
            "[LIFECYCLE] Duplicate Settings request ignored while recreation is active"
        )
        return

    manager = getattr(engine, "display_manager", None)
    if manager is None or not bool(getattr(engine, "_display_initialized", False)):
        logger.info(
            "[LIFECYCLE] Stale Settings request ignored without a current display runtime"
        )
        return

    intent = SettingsRequestIntent(
        runtime_generation=int(
            getattr(
                manager,
                "_runtime_generation",
                getattr(engine, "_runtime_generation", -1),
            )
        ),
        display_manager_identity=id(manager),
    )
    pending = getattr(engine, "_pending_settings_request_intent", None)
    if pending is not None:
        logger.info(
            "[LIFECYCLE] Duplicate Settings admission ignored pending=%s requested=%s",
            pending,
            intent,
        )
        return

    engine._pending_settings_request_intent = intent
    _record_diagnostic_stage(
        "settings_request_queued",
        generation=intent.runtime_generation,
        manager=intent.display_manager_identity,
    )
    logger.info(
        "Settings request queued generation=%s manager=%s",
        intent.runtime_generation,
        intent.display_manager_identity,
    )
    ThreadManager.single_shot(
        0,
        partial(_admit_settings_requested, engine, intent),
    )


def _admit_settings_requested(
    engine: ScreensaverEngine,
    intent: SettingsRequestIntent,
) -> None:
    """Validate and admit Settings after the originating input frame returns."""
    if getattr(engine, "_pending_settings_request_intent", None) != intent:
        logger.info("[LIFECYCLE] Superseded Settings admission rejected")
        return
    engine._pending_settings_request_intent = None

    manager = getattr(engine, "display_manager", None)
    if (
        bool(getattr(engine, "_terminal_shutdown_requested", False))
        or bool(getattr(engine, "_settings_dialog_active", False))
        or getattr(engine, "_pending_runtime_destruction_barrier", None) is not None
        or manager is None
        or not bool(getattr(engine, "_display_initialized", False))
        or int(getattr(manager, "_runtime_generation", -1))
        != intent.runtime_generation
        or id(manager) != intent.display_manager_identity
    ):
        logger.info(
            "[LIFECYCLE] Settings admission rejected after runtime ownership changed "
            "generation=%s manager=%s",
            intent.runtime_generation,
            intent.display_manager_identity,
        )
        return

    logger.info(
        "Settings request admitted generation=%s manager=%s",
        intent.runtime_generation,
        intent.display_manager_identity,
    )
    _record_diagnostic_stage(
        "settings_request_admitted",
        generation=intent.runtime_generation,
        manager=intent.display_manager_identity,
    )
    on_settings_requested(engine)

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
        manager = engine.display_manager
        if manager is not None and manager.cancel_custom_layout_session():
            logger.info(
                "Settings requested during active CUSTOM edit session; "
                "cancelled session before teardown"
            )
    except Exception:
        logger.debug("Failed to cancel CUSTOM edit session before settings", exc_info=True)

    # Wake the presentation-neutral Media runtime from idle before teardown.
    # This ensures Spotify detection resumes if user opened Spotify while in settings
    try:
        if engine.display_manager:
            engine.display_manager.wake_media_runtime()
    except Exception as e:
        logger.debug("[ENGINE] Failed to wake Media runtime from idle: %s", e)

    coordinator = None
    # Set settings dialog active flag FIRST - this prevents halo from showing
    try:
        from rendering.multi_monitor_coordinator import get_coordinator
        coordinator = get_coordinator()
        coordinator.set_settings_dialog_active(True)
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)

    # Runtime teardown below owns all generation-scoped auxiliary presentation,
    # including the retained Quick halo and temporary legacy halo scaffolding.

    # Stop the engine but DON'T exit the app
    _record_diagnostic_stage(
        "settings_before_runtime_stop",
        generation=getattr(engine, "_runtime_generation", "unknown"),
    )
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
    _record_diagnostic_stage(
        "settings_after_runtime_stop",
        generation=getattr(engine, "_runtime_generation", "unknown"),
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

    _record_diagnostic_stage(
        "settings_retired_runtime_destroyed",
        generation=getattr(engine, "_runtime_generation", "unknown"),
    )

    dialog_barrier = None
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
        _record_diagnostic_stage(
            "settings_dialog_constructor_begin",
            generation=dialog_generation,
        )
        dialog = SettingsDialog(
            engine.settings_manager,
            animations,
            runtime_generation=dialog_generation,
        )
        engine._active_settings_dialog = dialog
        _record_diagnostic_stage(
            "settings_dialog_constructor_complete",
            generation=dialog_generation,
        )
        try:
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        except Exception:
            logger.debug("Settings dialog delete-on-close attribute unavailable", exc_info=True)

        from engine.runtime_destruction import RuntimeDestructionBarrier

        if isinstance(dialog, QObject) or isinstance(animations, QObject):
            dialog_barrier = RuntimeDestructionBarrier(
                engine,
                reason="settings_dialog_close",
                retiring_generation=dialog_generation,
            )
            if isinstance(dialog, QObject):
                if not _qobject_wrapper_is_valid(dialog):
                    raise RuntimeError(
                        "SettingsDialog wrapper became invalid before modal execution"
                    )
                dialog_barrier.watch_qobject(dialog, label="SettingsDialog")
                for child in dialog.findChildren(QObject):
                    dialog_barrier.watch_qobject(child)
            if isinstance(animations, QObject):
                if not _qobject_wrapper_is_valid(animations):
                    raise RuntimeError(
                        "Settings AnimationManager wrapper became invalid before modal execution"
                    )
                dialog_barrier.watch_qobject(
                    animations,
                    label="SettingsAnimationManager",
                )
                timer = getattr(animations, "_timer", None)
                if isinstance(timer, QObject) and _qobject_wrapper_is_valid(timer):
                    dialog_barrier.watch_qobject(
                        timer,
                        label="SettingsAnimationTimer",
                    )

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
        _record_diagnostic_stage(
            "settings_dialog_exec_begin",
            generation=dialog_generation,
        )
        _ = dialog.exec()
        _record_diagnostic_stage(
            "settings_dialog_exec_returned",
            generation=dialog_generation,
        )
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

        animations_touchable = (
            not isinstance(animations, QObject)
            or _qobject_wrapper_is_valid(animations)
        )
        if animations_touchable:
            try:
                animations.cleanup()
            except Exception:
                logger.debug(
                    "Settings dialog AnimationManager cleanup failed",
                    exc_info=True,
                )
            if (
                not isinstance(animations, QObject)
                or _qobject_wrapper_is_valid(animations)
            ):
                delete_animations = getattr(animations, "deleteLater", None)
                if callable(delete_animations):
                    try:
                        delete_animations()
                    except Exception:
                        logger.debug(
                            "Settings AnimationManager deleteLater failed",
                            exc_info=True,
                        )

        if isinstance(dialog, QObject):
            if _qobject_wrapper_is_valid(dialog):
                dialog.close()
                if _qobject_wrapper_is_valid(dialog):
                    dialog.deleteLater()
        else:
            close_dialog = getattr(dialog, "close", None)
            if callable(close_dialog):
                close_dialog()
            delete_dialog = getattr(dialog, "deleteLater", None)
            if callable(delete_dialog):
                delete_dialog()

        try:
            ThreadManager.cancel_scheduled_single_shots(dialog_generation)
        except RuntimeError:
            logger.critical(
                "[LIFECYCLE] Settings callbacks could not be cancelled on the UI thread",
                exc_info=True,
            )
            if dialog_barrier is not None:
                dialog_barrier.cancel_for_terminal_shutdown()
            engine._active_settings_dialog = None
            engine._settings_dialog_active = False
            QApplication.exit(1)
            return

        engine._active_settings_dialog = None
        if continuation is None:
            if dialog_barrier is not None:
                dialog_barrier.cancel_for_terminal_shutdown()
            engine._settings_dialog_active = False
            return

        if dialog_barrier is None:
            continuation()
        else:
            engine._pending_runtime_destruction_barrier = dialog_barrier
            _record_diagnostic_stage(
                "settings_dialog_barrier_seal",
                generation=dialog_generation,
            )
            dialog_barrier.seal()
            dialog_barrier.then(continuation)
    except Exception as e:
        if dialog_barrier is not None:
            dialog_barrier.cancel_for_terminal_shutdown()
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
    _record_diagnostic_stage(
        "settings_replacement_begin",
        generation=getattr(engine, "_runtime_generation", "unknown"),
    )
    engine._settings_dialog_active = False
    try:
        from rendering.multi_monitor_coordinator import get_coordinator

        coordinator = get_coordinator()
        coordinator.set_settings_dialog_active(False)
        coordinator.cleanup()
    except Exception:
        logger.debug("Coordinator cleanup after settings failed", exc_info=True)

    suppress_runtime_pointer_input(
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
    _record_diagnostic_stage(
        "settings_replacement_complete",
        generation=getattr(engine, "_runtime_generation", "unknown"),
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


def on_custom_layout_reload_requested(
    engine: ScreensaverEngine,
    request_kind: str = "custom_layout_commit",
    runtime_generation: int | None = None,
    display_manager_identity: int | None = None,
) -> None:
    """Queue a committed CUSTOM reload for a later engine-owned GUI turn."""
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
    manager = getattr(engine, "display_manager", None)
    if manager is None or not bool(getattr(engine, "_display_initialized", False)):
        logger.info(
            "[LIFECYCLE] Stale CUSTOM reload ignored without a current display runtime"
        )
        return

    current_generation = int(
        getattr(manager, "_runtime_generation", getattr(engine, "_runtime_generation", -1))
    )
    current_manager_identity = id(manager)
    source_generation = (
        current_generation if runtime_generation is None else int(runtime_generation)
    )
    source_manager_identity = (
        current_manager_identity
        if display_manager_identity is None
        else int(display_manager_identity)
    )
    if (
        source_generation != current_generation
        or source_manager_identity != current_manager_identity
    ):
        logger.info(
            "[LIFECYCLE] Stale CUSTOM reload rejected source_generation=%s "
            "current_generation=%s source_manager=%s current_manager=%s",
            source_generation,
            current_generation,
            source_manager_identity,
            current_manager_identity,
        )
        return

    intent = CustomLayoutReloadIntent(
        request_kind=str(request_kind or "custom_layout_commit"),
        runtime_generation=source_generation,
        display_manager_identity=source_manager_identity,
    )
    pending = getattr(engine, "_pending_custom_layout_reload_intent", None)
    if pending is not None:
        logger.info(
            "[LIFECYCLE] Duplicate CUSTOM reload admission ignored pending=%s requested=%s",
            pending,
            intent,
        )
        return

    engine._pending_custom_layout_reload_intent = intent
    logger.info(
        "CUSTOM layout reload queued kind=%s generation=%s manager=%s",
        intent.request_kind,
        intent.runtime_generation,
        intent.display_manager_identity,
    )
    ThreadManager.single_shot(
        0,
        partial(_admit_custom_layout_reload, engine, intent),
    )


def _admit_custom_layout_reload(
    engine: ScreensaverEngine,
    intent: CustomLayoutReloadIntent,
) -> None:
    """Validate and admit one immutable CUSTOM intent after Edit returns."""

    if getattr(engine, "_pending_custom_layout_reload_intent", None) != intent:
        logger.info("[LIFECYCLE] Superseded CUSTOM reload admission rejected")
        return
    engine._pending_custom_layout_reload_intent = None

    manager = getattr(engine, "display_manager", None)
    if (
        bool(getattr(engine, "_terminal_shutdown_requested", False))
        or bool(getattr(engine, "_settings_dialog_active", False))
        or getattr(engine, "_pending_runtime_destruction_barrier", None) is not None
        or manager is None
        or not bool(getattr(engine, "_display_initialized", False))
        or int(getattr(manager, "_runtime_generation", -1)) != intent.runtime_generation
        or id(manager) != intent.display_manager_identity
    ):
        logger.info(
            "[LIFECYCLE] CUSTOM reload admission rejected after runtime ownership changed "
            "kind=%s generation=%s manager=%s",
            intent.request_kind,
            intent.runtime_generation,
            intent.display_manager_identity,
        )
        return

    logger.info(
        "CUSTOM layout reload admitted kind=%s generation=%s manager=%s",
        intent.request_kind,
        intent.runtime_generation,
        intent.display_manager_identity,
    )

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

    suppress_runtime_pointer_input(
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
