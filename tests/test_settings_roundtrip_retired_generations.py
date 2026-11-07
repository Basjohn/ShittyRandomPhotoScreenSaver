"""Settings round trips must not accumulate retired generations (7 Nov 2026: ~20 MB a round trip, no plateau).

Each Settings round trip retires a display generation and a Settings dialog generation. Their watched owners pass the
strict destruction barrier by reference counting (R-53/R-154), but what they leave in reference cycles (the Python
wrappers of their destroyed QObjects, with their dicts, closures and the Python-owned native objects they keep) is
reclaimed only by a deep collection, which the RUN GC thresholds practically never run; each later reveal re-froze it.
The replacement's construction now collects once, after the barriers have judged (``collect_retired_generations``).

This drives the engine's real Settings path (``on_settings_requested``: the real stop, the strict display barrier, the
real ``SettingsDialog`` with its own barrier, the replacement through ``_construct_and_start_replacement_runtime`` up
to the reveal's freeze) with the real ``RuntimeGCPolicy``, and a ``DisplayManager`` stand-in whose Python graph is
cyclic as the real one's is. Automatic collection is off for the test: under the RUN thresholds no deep collection
comes during a session, and only an explicit one may reclaim anything. Structural only, never an RSS threshold.
"""
from __future__ import annotations

import gc
import uuid
import weakref

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal

ROUND_TRIPS = 3


def _cyclic_display_manager_class():
    class _CyclicDisplayManager(QObject):
        exit_requested = Signal()
        monitors_changed = Signal(int)
        displays_ready = Signal(int)
        authoritative_first_frames_ready = Signal(int)
        startup_reveal_completed = Signal(int)
        transition_completed = Signal(int)
        transition_batch_idle = Signal()
        previous_requested = Signal()
        next_requested = Signal()
        save_image_requested = Signal(int)
        ban_image_requested = Signal(int)
        clear_image_bans_requested = Signal()
        cycle_transition_requested = Signal()
        settings_requested = Signal()
        settings_target_requested = Signal(str)
        custom_layout_reload_requested = Signal(str, int, object)
        jedi_mode_requested = Signal(str, str)

        def __init__(self, *, runtime_generation, **_kwargs):
            super().__init__()
            self._runtime_generation = runtime_generation
            # The real manager's routes and helpers point back at it: its wrapper outlives its C++ object in a cycle.
            self._route = lambda: self
            self.payload = bytearray(1 << 20)

        def set_random_transition_selection(self, _selection) -> None:
            return None

        def initialize_displays(self) -> int:
            return 1

        def get_display_count(self) -> int:
            return 1

        def collect_runtime_retirement_roots(self):
            return [self], []

        def cleanup(self) -> None:
            return None

        def retire_runtime(self) -> None:
            self.deleteLater()

    return _CyclicDisplayManager


@pytest.mark.qt
def test_settings_round_trips_leave_no_retired_generation_reachable(monkeypatch, qt_app, qtbot, tmp_path):
    from core.performance.gc_policy import RuntimeGCPolicy
    from core.settings import SettingsManager
    from engine import engine_handlers
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    from ui.settings_dialog import SettingsDialog
    from ui.styled_popup import StyledPopup

    engine = ScreensaverEngine()
    engine.settings_manager = SettingsManager(
        organization="Test", application=f"RetiredGenerations_{uuid.uuid4().hex}", storage_base_dir=tmp_path,
    )
    policy = RuntimeGCPolicy()
    reveals: list[int] = []

    def _start(*, show_first_image=True):
        engine._transition_state(EngineState.RUNNING)
        engine._freeze_revealed_generation()      # the coordinated reveal's freeze edge
        reveals.append(engine._runtime_generation)
        return True

    dialogs: list[weakref.ReferenceType] = []

    def _dialog_exec(dialog) -> int:              # never shown: closed by the handler as soon as exec returns
        dialogs.append(weakref.ref(dialog))
        return 0

    monkeypatch.setattr("engine.screensaver_engine.DisplayManager", _cyclic_display_manager_class())
    monkeypatch.setattr(engine, "_initialize_image_sources", lambda: True)
    monkeypatch.setattr(engine, "_start_rss_background_refresh_if_needed", lambda: None)
    monkeypatch.setattr(engine, "_setup_rotation_timer", lambda: None)
    monkeypatch.setattr(engine, "_arm_replacement_watchdog", lambda label=None: None)
    monkeypatch.setattr(engine, "start", _start)
    monkeypatch.setattr(engine_handlers, "log_lifecycle_resource_snapshot", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_handlers, "suppress_runtime_pointer_input", lambda *_a, **_k: None)
    monkeypatch.setattr(SettingsDialog, "exec", _dialog_exec)
    monkeypatch.setattr(StyledPopup, "exec", lambda _popup: pytest.fail("a popup was raised"))

    was_enabled = gc.isenabled()
    gc.disable()
    policy.start()
    engine._gc_policy = policy
    try:
        assert engine._initialize_display()
        _start()
        managers = [weakref.ref(engine.display_manager)]
        for round_trip in range(ROUND_TRIPS):
            revealed = len(reveals)
            engine_handlers.on_settings_requested(engine)

            def _revealed() -> None:
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                assert len(reveals) == revealed + 1, "the replacement never revealed"
                assert not engine._settings_dialog_active

            qtbot.waitUntil(_revealed, timeout=30000)
            assert policy.frozen, f"round trip {round_trip}: the replacement's reveal did not re-freeze"
            managers.append(weakref.ref(engine.display_manager))

        assert len(dialogs) == ROUND_TRIPS
        retired_managers = [ref for ref in managers[:-1] if ref() is not None]
        retired_dialogs = [ref for ref in dialogs if ref() is not None]
        assert not retired_managers and not retired_dialogs, (
            f"after {ROUND_TRIPS} Settings round trips, {len(retired_managers)} retired display generation(s) and "
            f"{len(retired_dialogs)} retired Settings dialog(s) are still reachable: their cycles were never "
            f"collected and each reveal re-froze them"
        )
        assert managers[-1]() is engine.display_manager       # the live generation is untouched
    finally:
        engine._gc_policy = None
        policy.stop()
        gc.unfreeze()
        if was_enabled:
            gc.enable()
