"""The RUN loop's post-exit backstop: every exit retires the terminal resources exactly once.

A bare ``QCoreApplication.exit(1)`` (here the real replacement barrier's timeout) ends ``app.exec()`` without the
terminal stop's finalization; ``main.run_screensaver`` then retires the application services, the ProcessSupervisor
and the ThreadManager itself. After a normal terminal stop it retires nothing a second time.

``run_screensaver`` runs for real on a real ``ScreensaverEngine`` whose startup is stubbed; the loop is the test
process's real Qt loop.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject

import main
from core.application_services import ApplicationServices
from engine.screensaver_engine import EngineState, ScreensaverEngine

STUB = "stub.player"


class _Service:
    def __init__(self, events: list) -> None:
        self.events = events

    def retire(self) -> None:
        self.events.append("service_retire")


class _Supervisor:
    def __init__(self, events: list) -> None:
        self.events = events

    def shutdown(self) -> None:
        self.events.append("supervisor_shutdown")


class _ThreadManager:
    def __init__(self, events: list) -> None:
        self.events = events

    def shutdown(self, *_args, **_kwargs) -> bool:
        self.events.append("thread_manager_shutdown")
        return True


class _Settings:
    def get_bool(self, _key, *_args, **_kwargs) -> bool:
        return False


def _run(monkeypatch, qt_app, loop):
    """``main.run_screensaver`` with a real engine; ``loop(engine)`` stands in for ``app.exec()``."""
    events: list = []
    engines: list = []

    def _engine() -> ScreensaverEngine:
        engine = ScreensaverEngine()
        engine._process_supervisor = _Supervisor(events)
        engine.thread_manager = _ThreadManager(events)
        engine.application_services = ApplicationServices()
        engine.application_services.register(STUB, lambda: _Service(events))
        engine.application_services.admit_generation(0)
        assert engine.application_services.lease(STUB, generation=0).service is not None
        engine.initialize = lambda: True

        def _start(**_kwargs) -> bool:
            engine._transition_state(EngineState.RUNNING)
            return True

        engine.start = _start
        engines.append(engine)
        return engine

    class _App:
        def setQuitOnLastWindowClosed(self, _value) -> None:
            return None

        def exec(self) -> int:
            return loop(engines[0])

    monkeypatch.setattr(main, "SettingsManager", _Settings)
    monkeypatch.setattr(main, "ScreensaverEngine", _engine)
    monkeypatch.setattr("core.sources.readiness.has_image_sources", lambda _settings: True)
    monkeypatch.setattr(main, "_schedule_runtime_reddit_helper_session", lambda _engine: None)
    monkeypatch.setattr(main, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr("core.network.bounded_dns.close_network_admission", lambda: events.append("network_fence"))
    monkeypatch.setattr("engine.runtime_destruction.request_application_quit", lambda reason: events.append("quit"))
    code = main.run_screensaver(_App(), usage_enabled=False)
    return code, events, engines[0]


@pytest.mark.qt
def test_a_bare_exit_from_a_replacement_barrier_timeout_retires_everything_once(monkeypatch, qt_app):
    from engine.runtime_destruction import RuntimeDestructionBarrier

    survivors: list = []
    exit_codes: list = []

    def _exit(code: int = 0) -> None:
        # The barrier's bare QCoreApplication.exit(code), stubbed (tests/conftest.py's exit tripwire): it ends
        # this real loop the same way, through quit(), and the loop reports the code the barrier asked for.
        exit_codes.append(int(code))
        qt_app.quit()

    monkeypatch.setattr("engine.runtime_destruction.QCoreApplication.exit", staticmethod(_exit))

    def _barrier_timeout_loop(engine) -> int:
        # A replacement barrier whose watched root never dies: its timeout calls QCoreApplication.exit(1).
        root = QObject()
        survivors.append(root)
        barrier = RuntimeDestructionBarrier(engine, reason="settings", retiring_generation=0, timeout_ms=50)
        barrier.watch_qobject(root, label="LeakedRoot")
        engine._pending_runtime_destruction_barrier = barrier
        barrier.seal()
        qt_app.exec()
        return exit_codes[0]

    code, events, engine = _run(monkeypatch, qt_app, _barrier_timeout_loop)

    assert code == 1
    assert events.count("service_retire") == 1
    assert events.count("supervisor_shutdown") == 1
    assert events.count("thread_manager_shutdown") == 1
    assert events.index("supervisor_shutdown") < events.index("network_fence") < events.index("service_retire")
    assert events.index("service_retire") < events.index("thread_manager_shutdown")
    assert engine.application_services.is_retired
    assert engine._pending_runtime_destruction_barrier is None


@pytest.mark.qt
def test_a_normal_terminal_stop_is_not_retired_again_after_the_loop(monkeypatch, qt_app):
    def _terminal_stop_loop(engine) -> int:
        engine.stop(exit_app=True)        # no display: the terminal finalization runs synchronously
        return 0

    code, events, engine = _run(monkeypatch, qt_app, _terminal_stop_loop)

    assert code == 0
    assert events.count("service_retire") == 1
    assert events.count("supervisor_shutdown") == 1
    assert events.count("thread_manager_shutdown") == 1
    assert events.count("network_fence") == 1
    assert engine.application_services.is_retired
