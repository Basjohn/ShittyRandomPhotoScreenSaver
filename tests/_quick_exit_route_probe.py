"""Child process for ``tests/test_quick_exit_routes.py`` (not collected: no ``test_`` prefix).

One real ``QuickDisplayRuntime`` on Vulkan, rendering on the native core's device and kept off screen (a 64x64
transparent tool window at opacity 0, as ``tests/test_quick_backend_owner.py`` keeps its windows). At its first
presented frame the route's real product code runs; the process ends with a normal interpreter exit, so a Quick
window still alive when the loop ends shows as the process's crash.

usage: python tests/_quick_exit_route_probe.py <state_dir> <route> <fixed|bare>

``bare`` is the negative control: the code before the fix. The window release is skipped (the exit runs at once, as
the bare ``QCoreApplication.exit(1)`` did) and the second exiting stop does not see the terminal drain (so it cancels
it, as it did).
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEARDOWN_FAILURES = ("settings_teardown_failed", "custom_teardown_failed", "monitor_teardown_failed")


def main() -> int:
    from types import SimpleNamespace

    import shiboken6
    from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
    from PySide6.QtWidgets import QApplication

    from rendering.quick import bootstrap

    state_dir, route, variant = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    bootstrap.configure_quick_graphics(reason="exit-route-probe", backend="vulkan", start_state_dir=state_dir)
    app = QApplication(sys.argv[:1])
    bootstrap.start_quick_backend()
    from engine import engine_handlers, engine_lifecycle
    import engine.runtime_destruction as destruction
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy

    if variant == "bare":
        destruction.release_quick_windows_then = lambda _reason, continuation: (continuation(), 0)[1]
        destruction.RuntimeDestructionBarrier.is_terminal = property(lambda _self: False)
    destruction.RuntimeDestructionBarrier.__init__.__kwdefaults__["timeout_ms"] = 300   # the barrier timeouts
    runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=1, screen=app.primaryScreen(),
                                  scene_factory=QuickSceneFactory(),
                                  window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    window = runtime.window
    window.setOpacity(0.0)
    window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
    window.setFlag(Qt.WindowType.Tool, True)
    bound = window.screen().geometry()
    window.setGeometry(bound.x() + 16, bound.y() + 16, 64, 64)

    class Manager(QObject):
        """The display manager's teardown contract around the one real runtime."""
        _runtime_generation = 1

        def collect_runtime_retirement_roots(self):
            return [runtime, window], []

        def get_display_count(self):
            return 1

        def cleanup(self):
            if route in TEARDOWN_FAILURES:
                raise RuntimeError("probe: the teardown failed before the runtime closed")
            if route.endswith("timeout"):
                return               # the window's retirement never completes: the barrier times out on it
            runtime.close_runtime()

        def cancel_custom_layout_session(self):
            return False

    class Engine(QObject):
        """The lifecycle's collaborators; stop, the teardown, the barriers and the handlers are the real ones."""
        stopped = Signal()

        def __init__(self):
            super().__init__()
            self._state = EngineState.RUNNING
            self._running = True
            self.display_manager = Manager()
            self.thread_manager = self.resource_manager = self._process_supervisor = None
            self.application_services = None
            self._pending_runtime_destruction_barrier = None
            self._terminal_shutdown_requested = False
            self._settings_dialog_active = False
            self._display_initialized = True
            self._rotation_timer = None
            self._runtime_generation = 1
            self._instance_lock = threading.Lock()
            self._current_image = None
            self._pending_custom_layout_reload_intent = None

        def _get_state(self):
            return self._state

        def _transition_state(self, target, expected_from=()):
            self._state = target
            return True

        def _advance_runtime_generation(self, _reason):
            self._runtime_generation += 1

        def stop(self, exit_app=True, *, reason=None):
            engine_lifecycle.stop(self, exit_app=exit_app, reason=reason)

    import core.windows.reddit_helper_runtime as reddit_helper_runtime
    reddit_helper_runtime.clear_session_ticket = lambda **_kwargs: False
    engine = Engine()
    report = {"route": route, "variant": variant}

    def trigger():
        if route == "replacement_barrier_timeout":
            engine.stop(exit_app=False, reason="settings")
        elif route == "terminal_barrier_timeout":
            engine.stop(exit_app=True, reason="cli_exit_after")
        elif route == "settings_teardown_failed":
            engine_handlers.on_settings_requested(engine)
        elif route == "custom_teardown_failed":
            intent = engine_handlers.CustomLayoutReloadIntent(
                request_kind="custom_layout_commit", runtime_generation=1,
                display_manager_identity=id(engine.display_manager))
            engine._pending_custom_layout_reload_intent = intent
            engine_handlers._admit_custom_layout_reload(engine, intent)
        elif route == "monitor_teardown_failed":
            ScreensaverEngine._on_monitors_changed(engine, 2)
        elif route == "replacement_continuation_failed":
            # A replacement whose construction raised after its window existed (this window stands for it).
            barrier = destruction.RuntimeDestructionBarrier(engine, reason="settings", retiring_generation=0)
            barrier.seal()
            barrier.then(lambda: (_ for _ in ()).throw(RuntimeError("probe: the replacement failed")))
        elif route == "second_exiting_stop":
            engine.stop(exit_app=True, reason="cli_exit_after")
            engine.stop(exit_app=True)                  # e.g. the tray's Exit while the first stop drains
        else:
            raise SystemExit(f"unknown route {route}")

    class Presented(QObject):
        @Slot()
        def frame(self):
            window.frameSwapped.disconnect(presented.frame)
            report["api"] = window.rendererInterface().graphicsApi().name
            trigger()

    presented = Presented()
    window.frameSwapped.connect(presented.frame, Qt.ConnectionType.QueuedConnection)
    window.show()
    window.requestUpdate()
    QTimer.singleShot(15000, lambda: (report.__setitem__("timeout", True), app.exit(2)))
    report["exec_code"] = app.exec()
    report["window_alive_at_loop_end"] = shiboken6.isValid(window)
    report["hosts_left"] = len(bootstrap._owner.window_hosts)
    print("PROBE " + json.dumps(report), flush=True)
    return 0                 # a normal interpreter exit, never os._exit: the process's own end is what is tested


if __name__ == "__main__":
    sys.exit(main())
