"""The one Qt Quick backend owner and the Vulkan rehearsal path (D10, D6; Current_Plan.md item 8b N2.7).

In process: the owner's choice and its remembered starts (no Qt application is created or changed). In subprocesses
(the graphics API is process-wide): the real product window on Vulkan, hosted on the native core's device, the
start-up fallback to OpenGL before any window exists, and the forced failures whose next start runs on OpenGL. No
window is ever shown (N5.2h): a probe's first presented frame is its window's frameSwapped edge, emitted by the probe;
the frames themselves are the hidden-host harnesses' and the lead's display runs'. The subprocess tests
need the built module (``release/native_module``, a GitHub build) and skip without it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rendering.native import loader
from rendering.quick import bootstrap

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
needs_module = pytest.mark.skipif(
    not BUILT, reason="the native core is not built in this checkout: no release/native_module/"
                      f"{loader.MODULE_NAME}.pyd (only GitHub builds it)")


@pytest.fixture(autouse=True)
def _fresh_owner():
    # The owner's state is process-wide; these tests change only its record keeping, never the Qt graphics API.
    saved = bootstrap._owner
    bootstrap.reset_quick_backend_for_testing()
    yield
    bootstrap._owner = saved


def _records(state_dir: Path) -> list[dict]:
    folder = state_dir / bootstrap.START_RECORD_FOLDER
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def _write(state_dir: Path, name: str, record: dict) -> Path:
    folder = state_dir / bootstrap.START_RECORD_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{bootstrap.START_RECORD_PREFIX}{name}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


# ------------------------------------------------------------------------------------------------- the choice, in process


def test_without_a_request_the_owner_runs_opengl_and_keeps_no_record(tmp_path):
    chosen = bootstrap._choose_quick_backend(None, tmp_path)
    assert chosen == bootstrap.QuickBackend() == bootstrap.active_quick_backend()
    assert (chosen.api, chosen.requested, chosen.reason, chosen.qt_graphics_api) == ("opengl", "opengl", "", "OpenGL")
    assert bootstrap.quick_backend_api() == "opengl"
    assert not (tmp_path / bootstrap.START_RECORD_FOLDER).exists()      # the product path touches no state


def test_the_switch_is_the_request_when_none_is_named(tmp_path):
    from core.diagnostics import experiment_flags as ef

    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", f"{ef.GRAPHICS_BACKEND_FLAG}=vulkan"]))
    try:
        assert bootstrap._choose_quick_backend(None, tmp_path).api == "vulkan"
    finally:
        ef.override_active_flags_for_testing(None)


def test_a_vulkan_request_records_one_pending_start_for_this_process(tmp_path):
    chosen = bootstrap._choose_quick_backend("vulkan", tmp_path)
    assert (chosen.api, chosen.requested, chosen.fell_back, chosen.qt_graphics_api) == ("vulkan", "vulkan", False,
                                                                                        "Vulkan")
    [record] = _records(tmp_path)
    assert record["state"] == "pending" and record["pid"] == os.getpid() and record["backend"] == "vulkan"
    with pytest.raises(ValueError):
        bootstrap._choose_quick_backend("metal", tmp_path)


def test_a_failed_start_sends_the_next_start_to_opengl_once_and_says_why(tmp_path):
    _write(tmp_path, "1", {"backend": "vulkan", "state": "failed", "pid": 1, "started": "2026-11-13T01:00:00+00:00",
                           "reason": "vkCreateDevice: VK_ERROR_INITIALIZATION_FAILED"})
    chosen = bootstrap._choose_quick_backend("vulkan", tmp_path)
    assert (chosen.api, chosen.requested, chosen.fell_back) == ("opengl", "vulkan", True)
    assert "VK_ERROR_INITIALIZATION_FAILED" in chosen.reason and "2026-11-13T01:00:00" in chosen.reason
    assert _records(tmp_path) == []                                    # read once: the start after tries Vulkan
    assert bootstrap._choose_quick_backend("vulkan", tmp_path).api == "vulkan"


def test_a_pending_start_whose_process_is_gone_did_not_complete(tmp_path):
    # This pid is alive but was created at another time: the recorded process is gone (a reused pid).
    _write(tmp_path, "2", {"backend": "vulkan", "state": "pending", "pid": os.getpid(), "process_created": 1.0,
                           "started": "2026-11-13T02:00:00+00:00", "reason": ""})
    chosen = bootstrap._choose_quick_backend("vulkan", tmp_path)
    assert chosen.api == "opengl" and "ended before its first frame" in chosen.reason


def test_a_pending_start_of_a_running_process_is_another_start_and_left_alone(tmp_path):
    live = _write(tmp_path, "3", {"backend": "vulkan", "state": "pending", "pid": os.getpid(),
                                  "process_created": bootstrap._process_created(os.getpid()),
                                  "started": "2026-11-13T03:00:00+00:00", "reason": ""})
    assert bootstrap._choose_quick_backend("vulkan", tmp_path).api == "vulkan"
    assert live.is_file()


def test_an_unreadable_record_counts_as_a_start_that_did_not_complete(tmp_path):
    folder = tmp_path / bootstrap.START_RECORD_FOLDER
    folder.mkdir(parents=True)
    (folder / f"{bootstrap.START_RECORD_PREFIX}9.json").write_text("{torn", encoding="utf-8")
    assert bootstrap._choose_quick_backend("vulkan", tmp_path).api == "opengl"


def test_a_clean_quit_or_the_first_frame_completes_the_start(tmp_path):
    bootstrap._choose_quick_backend("vulkan", tmp_path)
    assert len(_records(tmp_path)) == 1
    bootstrap._on_about_to_quit()
    assert _records(tmp_path) == []
    bootstrap.reset_quick_backend_for_testing()
    bootstrap._choose_quick_backend("vulkan", tmp_path)
    bootstrap._complete_start("first frame presented")
    assert _records(tmp_path) == []


def test_a_recorded_failure_survives_the_clean_quit_that_follows_it(tmp_path):
    bootstrap._choose_quick_backend("vulkan", tmp_path)
    bootstrap._record_failed_start("forced")
    bootstrap._on_about_to_quit()
    [record] = _records(tmp_path)
    assert record["state"] == "failed" and record["reason"] == "forced"


def test_hosting_a_window_on_opengl_hosts_it_on_the_core_or_degrades(qt_app, caplog):
    # N5.2h: OpenGL windows are hosted on the native core too (its frame driver records the background layer); with no
    # core, or a host the core refuses, the process shows the degraded display (one error), never a quit.
    from PySide6.QtQuick import QQuickWindow

    attached: list = []

    class Host:
        handle, closed = 11, False

        def close(self):
            return {}

    class Core:
        def attach_host(self, window):
            attached.append(window)
            return Host()

    class Refusing:
        def attach_host(self, window):
            raise RuntimeError("refused")

    window = QQuickWindow()                                    # never shown: no frame, no device
    try:
        assert bootstrap._owner.backend.api == "opengl"
        assert bootstrap.host_quick_window(window) is None and bootstrap.degraded_reason() == ""   # no core yet
        bootstrap._owner.core = Core()
        host = bootstrap.host_quick_window(window)
        assert isinstance(host, Host) and attached == [window] and bootstrap._owner.window_hosts == {11: host}
        bootstrap._owner.core = Refusing()
        with caplog.at_level("ERROR"):
            assert bootstrap.host_quick_window(window) is None
            assert bootstrap.host_quick_window(window) is None
        assert "could not be hosted" in bootstrap.degraded_reason()
        assert bootstrap._owner.core is None
        assert len([r for r in caplog.records if "Degraded display" in r.getMessage()]) == 1    # logged once
    finally:
        window.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize("admitted", [False, True])
def test_gpu_pass_timing_is_switched_on_and_drained_only_when_admitted(admitted, monkeypatch, qt_app):
    # N2.6's admission: --gpu-pass-timing with a frame trace. The window is never shown (no frame, no device).
    from PySide6.QtQuick import QQuickWindow
    from core.diagnostics import experiment_flags as ef
    import core.performance.frame_trace as frame_trace
    import rendering.native.gpu_timing as gpu_timing

    calls: list = []

    class Host:
        handle, closed = 7, False

        def set_gpu_timer(self, enabled=True, **_controls):
            calls.append(("timer", enabled))

        def gpu_samples(self):
            return ("sample",)

        def close(self):
            return {}

    sink = object()
    monkeypatch.setattr(frame_trace, "current_frame_trace", lambda: sink)
    monkeypatch.setattr(gpu_timing, "write_to_frame_trace",
                        lambda to, samples, *, screen_index: calls.append(("drain", to is sink, tuple(samples))))
    argv = ["main.py", ef.GPU_PASS_TIMING_FLAG] if admitted else ["main.py"]
    ef.activate_experiment_flags(ef.parse_experiment_flags(argv))
    bootstrap._owner.backend = bootstrap.QuickBackend("vulkan", "vulkan")
    bootstrap._owner.core = type("Core", (), {"attach_host": lambda self, window: Host()})()
    window = QQuickWindow()
    try:
        bootstrap.host_quick_window(window)
        window.frameSwapped.emit()
        qt_app.processEvents()
        assert calls == ([("timer", True), ("drain", True, ("sample",))] if admitted else [])
    finally:
        ef.override_active_flags_for_testing(None)
        window.deleteLater()
        qt_app.processEvents()


# ------------------------------------------------------------------------------------------ the real process, subprocesses

_PRELUDE = r'''
import json
import os
import sys
from pathlib import Path

from rendering.quick import bootstrap

state_dir = Path(sys.argv[1])
step = sys.argv[2]


def records():
    folder = state_dir / bootstrap.START_RECORD_FOLDER
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []


def emit(report, code=0):
    print("PROBE " + json.dumps(report), flush=True)
    os._exit(code)
'''

_WINDOW = r'''
from PySide6.QtCore import QObject, Qt, QTimer, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow
from rendering.quick import window as quick_window
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow

app = QGuiApplication(sys.argv)
report = {"configured_api": configured.graphics_api, "records_before_start": records()}
backend = bootstrap.start_quick_backend(**start_kwargs)
report["backend"] = [backend.api, backend.requested, backend.reason]
report["module_loaded"] = "_srpss_native_core" in sys.modules
report["records_after_start"] = records()
gl_validations = []
quick_window.validate_or_quit_current_opengl_context = lambda **kw: gl_validations.append(kw["reason"])
quits = []
import engine.runtime_destruction as destruction
_quit = destruction.request_application_quit
destruction.request_application_quit = lambda reason: (quits.append(reason), _quit(reason))[1]
try:
    window = QuickDisplayWindow(screen_index=0, runtime_generation=1, screen=app.primaryScreen(),
                                policy=QuickWindowPolicy())
except RuntimeError as exc:
    report["window_error"] = str(exc)
    report["quits"] = quits
    app.exec()                       # the queued quit runs (and the clean quit's edge with it)
    report["records_after_quit"] = records()
    emit(report)


class Presented(QObject):
    @Slot()
    def frame(self):
        # Queued after the owner's own completion slot (connected first, at the window's construction).
        hosts = list(bootstrap._owner.window_hosts.values())
        report["api"] = QQuickWindow.graphicsApi().name
        report["records_after_first_frame"] = records()
        report["host"] = hosts[0].state() if hosts else None
        report["gl_validations"] = list(gl_validations)      # at the first frame, before the teardown
        report["quits"] = quits
        report["binding_lost"] = window.binding_loss is not None
        window.frameSwapped.disconnect(presented.frame)
        # The decided teardown order (facts A7): the window goes first (on Vulkan its device with it), then the
        # process ends (os._exit with the Vulkan window still alive ended this probe with 0xC0000005).
        window.destroyed.connect(app.quit)
        window.deleteLater()


presented = Presented()
window.frameSwapped.connect(presented.frame, Qt.ConnectionType.QueuedConnection)
# Never shown (no probe window reaches a screen): the window's first presented frame is its frameSwapped edge, emitted
# here once the loop runs; the frames themselves are the hidden-host harnesses' and the lead's display runs'.
report["visible"] = window.isVisible()
QTimer.singleShot(0, window.frameSwapped.emit)
QTimer.singleShot(15000, lambda: emit(dict(report, timeout=True), 2))
app.exec()
hosts = list(bootstrap._owner.window_hosts.values())
report["hosts_left"] = len(hosts)
report["gl_validations_at_exit"] = gl_validations    # a scene graph initialised again before the exit would show here
emit(report)
'''


def _probe_env() -> dict:
    """The probe's environment: Qt's own Windows platform whatever the caller's is (Qt's offscreen platform has no
    Vulkan, and the probes never show a window, so they need none)."""
    env = os.environ.copy()
    env.pop("QT_QPA_PLATFORM", None)
    return env


def _probe(script: str, state_dir: Path, step: str = "", timeout: float = 60.0) -> dict:
    completed = subprocess.run([sys.executable, "-c", script, str(state_dir), step], cwd=ROOT, env=_probe_env(),
                               text=True, capture_output=True, check=False, timeout=timeout)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("PROBE ")]
    assert completed.returncode == 0 and lines, completed.stdout + completed.stderr
    return json.loads(lines[-1][len("PROBE "):])


def _window_script(configure: str, start_kwargs: str = "{}") -> str:
    return _PRELUDE + configure + f"\nstart_kwargs = {start_kwargs}\n" + _WINDOW


_CONFIGURE_VULKAN = ('configured = bootstrap.configure_quick_graphics(reason="n27-probe", backend="vulkan", '
                     'start_state_dir=state_dir)\n')


@needs_module
def test_the_rehearsal_window_renders_on_the_native_core_device_and_completes_its_start(tmp_path):
    report = _probe(_window_script(_CONFIGURE_VULKAN), tmp_path)
    assert report["configured_api"] == "Vulkan" and report["backend"] == ["vulkan", "vulkan", ""]
    assert [record["state"] for record in report["records_after_start"]] == ["pending"]
    assert report["api"] == "Vulkan"
    host = report["host"]
    assert host["graphics_api"] == "vulkan" and host["attached"] and host["device_alive"]
    assert int(host["device"]["vk_device"]) != 0                    # the module's VkDevice, given before the show
    assert report["visible"] is False                                # never shown
    assert report["records_after_first_frame"] == []                 # the first presented frame completed the start
    assert report["gl_validations"] == [] and report["quits"] == []  # no OpenGL check on a Vulkan window
    assert report["hosts_left"] == 0                                  # the destroyed window closed its host
    assert report["binding_lost"] is False and report["gl_validations_at_exit"] == []


#: N5.2h: the default path (OpenGL) in its own process with no window ever shown: the start loads the native core, the
#: product window is hosted on it at its construction, and its destruction closes the host; no start record is kept.
_DEFAULT_PATH = r'''
configured = bootstrap.configure_quick_graphics(reason="n52h-default", start_state_dir=state_dir)
from PySide6.QtGui import QGuiApplication
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow

app = QGuiApplication(sys.argv[:1])
start = {}
if step == "no_module":
    start = {"load_core": lambda: __import__("rendering.native", fromlist=["load"]).load(state_dir / "no_module")}
backend = bootstrap.start_quick_backend(**start)
report = {"configured_api": configured.graphics_api, "backend": [backend.api, backend.requested, backend.reason],
          "module_loaded": "_srpss_native_core" in sys.modules, "core": bootstrap.native_core() is not None,
          "degraded": bootstrap.degraded_reason()}
window = QuickDisplayWindow(screen_index=0, runtime_generation=1, screen=app.primaryScreen(), policy=QuickWindowPolicy())
hosts = list(bootstrap._owner.window_hosts.values())
report["hosts"] = len(hosts)
report["host"] = hosts[0].state() if hosts else None
report["visible"] = window.isVisible()
window.destroyed.connect(app.quit)
window.deleteLater()
app.exec()
report["hosts_left"] = len(bootstrap._owner.window_hosts)
report["records"] = records()
emit(report)
'''


@needs_module
def test_the_default_path_loads_the_native_core_and_hosts_its_windows_without_a_record(tmp_path):
    report = _probe(_PRELUDE + _DEFAULT_PATH, tmp_path)
    assert report["configured_api"] == "OpenGL" and report["backend"] == ["opengl", "opengl", ""]
    assert report["module_loaded"] is True and report["core"] is True and report["degraded"] == ""
    assert report["hosts"] == 1 and report["host"]["kind"] == "window" and report["host"]["attached"]
    assert report["visible"] is False and report["hosts_left"] == 0      # never shown; destroyed closes the host
    assert report["records"] == [] and not (tmp_path / bootstrap.START_RECORD_FOLDER).exists()


def test_the_default_path_without_a_module_runs_the_degraded_display(tmp_path):
    (tmp_path / "no_module").mkdir()
    report = _probe(_PRELUDE + _DEFAULT_PATH, tmp_path, step="no_module")
    assert report["configured_api"] == "OpenGL" and report["backend"][0] == "opengl"
    assert report["core"] is False and "did not load" in report["degraded"]
    assert report["hosts"] == 0 and report["visible"] is False and report["records"] == []


@needs_module
def test_a_module_that_cannot_load_falls_back_to_opengl_before_any_window(tmp_path):
    empty = tmp_path / "no_module"
    empty.mkdir()
    start = '{"load_core": lambda: __import__("rendering.native", fromlist=["load"]).load(Path(sys.argv[1]) / "no_module")}'
    report = _probe(_window_script(_CONFIGURE_VULKAN, start), tmp_path)
    api, requested, reason = report["backend"]
    assert (api, requested) == ("opengl", "vulkan") and "not built" in reason
    assert report["api"] == "OpenGL"                                  # the same process, set before any window
    # No core loaded: no host (the degraded display). Never shown, the window's scene graph is never initialised, so
    # its OpenGL context check (at that edge) does not run here.
    assert report["host"] is None and report["visible"] is False
    assert report["binding_lost"] is False and report["gl_validations_at_exit"] == []
    [record] = report["records_after_first_frame"]
    assert record["state"] == "failed" and "not built" in record["reason"]
    # ... and the next start runs on OpenGL and says so (then the one after tries Vulkan again).
    nxt = _probe(_PRELUDE + _CONFIGURE_VULKAN + 'emit({"api": configured.graphics_api, '
                 '"reason": bootstrap.active_quick_backend().reason, "records": records()})\n', tmp_path)
    assert nxt["api"] == "OpenGL" and "not built" in nxt["reason"] and nxt["records"] == []


_FORCED_DEVICE_FAILURE = r'''{"load_core": lambda: NoInstance(__import__("rendering.native", fromlist=["load"]).load(
    bootstrap._native_module_dir()))}


class NoInstance:
    """The real core, with the process instance never created: the module's device creation then fails for real."""

    def __init__(self, core):
        self._core = core

    def vulkan_instance(self, **_kwargs):
        return {"ok": True}

    def __getattr__(self, name):
        return getattr(self._core, name)
'''


@needs_module
def test_a_forced_device_failure_quits_before_any_frame_and_the_next_start_runs_opengl(tmp_path):
    # start_kwargs is assigned before NoInstance is defined; its lambda runs only inside start_quick_backend.
    script = _PRELUDE + _CONFIGURE_VULKAN + "\nstart_kwargs = " + _FORCED_DEVICE_FAILURE + _WINDOW
    report = _probe(script, tmp_path)
    assert report["backend"] == ["vulkan", "vulkan", ""]              # the start itself succeeded ...
    assert "native core's device" in report["window_error"]           # ... the device did not
    assert "no Vulkan process instance" in report["window_error"]     # the module's own refusal, not a Python one
    assert report["quits"] == ["quick_backend_window_host_failed"]
    [record] = report["records_after_quit"]                           # the clean quit did not erase the failure
    assert record["state"] == "failed" and "no Vulkan process instance" in record["reason"]

    nxt = _probe(_window_script(_CONFIGURE_VULKAN), tmp_path)
    assert nxt["configured_api"] == "OpenGL" and nxt["api"] == "OpenGL"
    assert "no Vulkan process instance" in nxt["backend"][2]
    # N5.2h: the OpenGL start loads the core too (the native background on both APIs).
    assert nxt["module_loaded"] is True and nxt["records_after_first_frame"] == []

    again = _probe(_window_script(_CONFIGURE_VULKAN), tmp_path)        # the one after tries Vulkan again
    assert again["api"] == "Vulkan" and again["records_after_first_frame"] == []


@needs_module
def test_a_start_that_dies_before_its_first_frame_sends_the_next_start_to_opengl(tmp_path):
    # As a driver crashing at device creation leaves it: the process ends with its start pending.
    died = subprocess.run([sys.executable, "-c", _PRELUDE + _CONFIGURE_VULKAN + "os._exit(3)\n", str(tmp_path), ""],
                          cwd=ROOT, env=_probe_env(), text=True, capture_output=True, check=False, timeout=60)
    assert died.returncode == 3, died.stderr
    assert [record["state"] for record in _records(tmp_path)] == ["pending"]
    nxt = _probe(_window_script(_CONFIGURE_VULKAN), tmp_path)
    assert nxt["configured_api"] == "OpenGL" and "ended before its first frame" in nxt["backend"][2]
    assert nxt["api"] == "OpenGL"


_EXIT = r'''
import threading
import shiboken6
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication

configured = bootstrap.configure_quick_graphics(reason="n27-exit", backend="vulkan", start_state_dir=state_dir)
app = QApplication(sys.argv[:1])
bootstrap.start_quick_backend()
from engine import engine_lifecycle
from engine.screensaver_engine import EngineState
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy

factory = QuickSceneFactory()
runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=1, screen=app.primaryScreen(), scene_factory=factory,
                              window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
window = runtime.window


class Manager(QObject):
    """The display manager's teardown contract around the one real runtime: cleanup begins its retirement."""
    _runtime_generation = 1

    def collect_runtime_retirement_roots(self):
        return [runtime, window], []

    def get_display_count(self):
        return 1

    def cleanup(self):
        runtime.close_runtime()


class Engine(QObject):
    """engine_lifecycle.stop's collaborators (the stop, the teardown and the finalization are the real ones)."""
    stopped = Signal()

    def __init__(self):
        super().__init__()
        self._state = EngineState.RUNNING
        self._running = True
        self.display_manager = Manager()
        self.thread_manager = self.resource_manager = self._process_supervisor = None
        self._pending_runtime_destruction_barrier = None
        self._terminal_shutdown_requested = False
        self._rotation_timer = None
        self._runtime_generation = 1
        self._instance_lock = threading.Lock()

    def _get_state(self):
        return self._state

    def _transition_state(self, target, expected_from=()):
        self._state = target
        return True

    def _advance_runtime_generation(self, _reason):
        self._runtime_generation += 1


import core.windows.reddit_helper_runtime as reddit_helper_runtime
reddit_helper_runtime.clear_session_ticket = lambda **_kwargs: False
engine = Engine()
report = {}


class Presented(QObject):
    @Slot()
    def frame(self):
        window.frameSwapped.disconnect(presented.frame)
        report["api"] = QQuickWindow.graphicsApi().name
        engine_lifecycle.stop(engine, exit_app=True, reason="cli_exit_after")           # what --exit-after runs


presented = Presented()
window.frameSwapped.connect(presented.frame, Qt.ConnectionType.QueuedConnection)
report["visible"] = window.isVisible()       # never shown: the frame edge is emitted once the loop runs
QTimer.singleShot(0, window.frameSwapped.emit)
QTimer.singleShot(15000, lambda: emit(dict(report, timeout=True), 2))
app.exec()
report["window_alive_at_loop_end"] = shiboken6.isValid(window)
report["hosts_left"] = len(bootstrap._owner.window_hosts)
print("PROBE " + json.dumps(report), flush=True)
sys.exit(0)          # a normal interpreter exit, never os._exit: the process's own end is what is tested
'''


@needs_module
def test_an_exiting_stop_releases_the_vulkan_window_and_the_process_exits_cleanly(tmp_path):
    # Lead's run, 14 Nov: --exit-after on Vulkan ended with 0xC0000005, its window still alive when the loop ended.
    # The probe's window is never shown (N5.2h: no probe window on a screen); the old stop's crash needed a window
    # rendering on the device, so its negative control (the stop before the fix) is no longer run here.
    completed = subprocess.run([sys.executable, "-c", _PRELUDE + _EXIT, str(tmp_path), "stop"], cwd=ROOT,
                               env=_probe_env(), text=True, capture_output=True, check=False, timeout=60)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, completed.stdout + completed.stderr
    report = json.loads(lines[-1][len("PROBE "):])
    assert report["api"] == "Vulkan" and "timeout" not in report and report["visible"] is False
    assert report["window_alive_at_loop_end"] is False and report["hosts_left"] == 0
    assert completed.returncode == 0, completed.stderr


@needs_module
def test_the_hidden_host_is_created_once_per_process_and_kept(tmp_path):
    # Facts J1: on OpenGL Qt's threaded render control keeps 2 handles and 1 USER object per create and destroy.
    script = _PRELUDE + r'''
configured = bootstrap.configure_quick_graphics(reason="n27-hidden", start_state_dir=state_dir)
from PySide6.QtGui import QGuiApplication
app = QGuiApplication(sys.argv)
bootstrap.start_quick_backend()
first = bootstrap.native_hidden_host(64, 48)
again = [bootstrap.native_hidden_host(64, 48) for _ in range(5)]
core = bootstrap._owner.core
report = {"same": all(host is first for host in again), "created": bootstrap._owner.hidden_hosts_created,
          "live_hosts": core.live_hosts(), "api": first.state()["graphics_api"]}
try:
    bootstrap.native_hidden_host(32, 32)
    report["other_size"] = "accepted"
except ValueError as exc:
    report["other_size"] = str(exc)
report["live_hosts_after"] = core.live_hosts()
try:
    bootstrap.native_hidden_host(64, 48, timestamps=True)       # a timed host is another host: refused while kept
    report["timed_while_kept"] = "accepted"
except ValueError as exc:
    report["timed_while_kept"] = str(exc)
bootstrap.close_native_hidden_host()                            # a tool's --cost: the kept host closed first
timed = bootstrap.native_hidden_host(64, 48, timestamps=True)
report["timed"] = {"created": bootstrap._owner.hidden_hosts_created, "live_hosts": core.live_hosts(),
                   "first_closed": first.closed, "kept": bootstrap.native_hidden_host(64, 48, timestamps=True) is timed}
from PySide6.QtCore import QTimer
QTimer.singleShot(0, app.quit)
app.exec()                           # the application's quit edge closes the kept host (its render thread with it)
report["closed_at_quit"] = first.closed and timed.closed
report["live_hosts_at_exit"] = core.live_hosts()
emit(report)
'''
    report = _probe(script, tmp_path)
    assert report["same"] is True and report["created"] == 1
    assert report["live_hosts"] == report["live_hosts_after"] == 1
    assert report["api"] == "opengl" and "created once and kept" in report["other_size"]
    assert "created once and kept" in report["timed_while_kept"]
    assert report["timed"] == {"created": 2, "live_hosts": 1, "first_closed": True, "kept": True}
    assert report["closed_at_quit"] is True and report["live_hosts_at_exit"] == 0


# Where a hidden host of the native core may be created (facts J1: every other user goes through the owner).
_HIDDEN_HOST_OWNER = "rendering/quick/bootstrap.py"            # native_hidden_host: created once per process, kept
_HIDDEN_HOST_PRIMITIVE = "rendering/native/loader.py"          # NativeCore.hidden_host itself
# The core's own proof harnesses, each one bounded child process per backend, whose rounds measure a host's own
# creation, timestamps setting or teardown (host_check's lifecycle rounds are how J1 was found), or a content's draw on
# its own validated device and host (N2.5's Spectrum, N2.9's generic mode: the Vulkan child creates the instance with
# validation before its host, which the owner's host never has).
_HIDDEN_HOST_HARNESSES = frozenset({
    "native/core/python/host_check.py",
    "native/core/python/timer_check.py",
    "native/core/python/composite_check.py",
    "native/core/python/spectrum_check.py",
    "native/core/python/generic_mode_check.py",
    "native/core/python/fullscreen_pass_check.py",
    "native/core/python/job_service_check.py",
    "native/core/python/background_layer_check.py",
    "native/core/python/backdrop_pyramid_check.py",
    "native/core/python/transition_route_check.py",     # its hosts through background_layer_check._host
    "native/core/python/devcurve_check.py",
    "native/core/python/bubble_check.py",               # its cost round's 4K host
    "native/core/python/bubble_cost_matrix.py",         # its 4K-class cost hosts (one per card shape and ratio)
    "native/core/python/oscilloscope_check.py",         # its cost round's 1440p and 4K hosts
    "native/core/python/device_loss_check.py",          # N3.6: its forced losses rebuild a host's own QRhi and device
    "native/core/python/scene_target_check.py",
    "native/core/python/mesh_buffer_check.py",
    "tools/visualizer_replay/native_stream_player.py",  # rule (b) harness: replays a take's delivery stream on each backend
    "native/core/python/post_stage_check.py",
    # N5.6's core children, the same shape as mesh_buffer_check and bubble_check above (audit 28 Nov item 2, kept here
    # by decision): each Vulkan child creates its instance with validation before any host, and each round makes and
    # closes hosts at sizes it measures (EB's card-sized and margin hosts; Waveform's cost host at each dpr's scene
    # size), which the owner's one kept, never-rebuilt, unvalidated host cannot be.
    "native/core/python/eb_core_check.py",
    "native/core/python/waveform_check.py",
})
_SKIPPED_DIRS = frozenset({"tests", "release", "build", "dist", "node_modules", "__pycache__"})


def _hidden_host_creations(source: str) -> int:
    """Calls in ``source`` that create a hidden host: ``<anything>.hidden_host(...)`` or ``host_attach("hidden", ...)``."""
    import ast

    count = 0
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if name == "hidden_host":
            count += 1
        elif name == "host_attach" and node.args and isinstance(node.args[0], ast.Constant) \
                and node.args[0].value == "hidden":
            count += 1
    return count


def _hidden_host_creators(root: Path) -> dict[str, int]:
    found: dict[str, int] = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if not name.startswith(".") and name not in _SKIPPED_DIRS]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = Path(folder) / name
            try:
                count = _hidden_host_creations(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            if count:
                found[path.relative_to(root).as_posix()] = count
    return found


def test_every_hidden_host_user_goes_through_the_owner():
    """Facts J1: outside the core's proof harnesses, the owner's ``native_hidden_host`` is the one place a hidden host
    is created (once per process, counted by ``hidden_hosts_created``); a user creating its own would create one per
    use. The test above counts the owner's creations."""
    creators = _hidden_host_creators(ROOT)
    assert creators.get(_HIDDEN_HOST_OWNER) == 1
    unexpected = set(creators) - {_HIDDEN_HOST_OWNER, _HIDDEN_HOST_PRIMITIVE} - _HIDDEN_HOST_HARNESSES
    assert not unexpected, f"hidden hosts created outside the owner (use bootstrap.native_hidden_host): {unexpected}"


def test_the_creation_scan_finds_a_direct_hidden_host_negative_control(tmp_path):
    (tmp_path / "rendering" / "quick").mkdir(parents=True)
    (tmp_path / "rendering" / "quick" / "bootstrap.py").write_text("host = core.hidden_host(1, 1)\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "capture.py").write_text(
        "def grab(core):\n    a = core.hidden_host(64, 48)\n    b = module.host_attach('hidden', 0, 1, 1)\n",
        encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("core.hidden_host(1, 1)\n", encoding="utf-8")
    assert _hidden_host_creators(tmp_path) == {"rendering/quick/bootstrap.py": 1, "tools/capture.py": 2}
