"""The one Qt Quick backend owner and the Vulkan rehearsal path (D10, D6; Current_Plan.md item 8b N2.7).

In process: the owner's choice and its remembered starts (no Qt application is created or changed). In subprocesses
(the graphics API is process-wide): the real product window on Vulkan, rendering on the native core's device, the
start-up fallback to OpenGL before any window exists, and the forced failures whose next start runs on OpenGL. Every
window is kept off screen (the inline ``keep_off_screen`` of ``tests/_invisible_windows.py``). The subprocess tests
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


def test_hosting_a_window_on_opengl_does_nothing():
    assert bootstrap.host_quick_window(object()) is None


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
from PySide6.QtQuick import QQuickItem
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
item = QQuickItem()
item.setParentItem(window.contentItem())
item.setWidth(1.0)
item.setHeight(1.0)
window.setOpacity(0.0)
window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
window.setFlag(Qt.WindowType.Tool, True)


class Presented(QObject):
    @Slot()
    def frame(self):
        # Queued after the owner's own completion slot (connected first, at the window's construction).
        hosts = list(bootstrap._owner.window_hosts.values())
        report["api"] = window.rendererInterface().graphicsApi().name
        report["records_after_first_frame"] = records()
        report["host"] = hosts[0].state() if hosts else None
        report["gl_validations"] = gl_validations
        report["quits"] = quits
        window.frameSwapped.disconnect(presented.frame)
        # The decided teardown order (facts A7): the window goes first (on Vulkan its device with it), then the
        # process ends (os._exit with the Vulkan window still alive ended this probe with 0xC0000005).
        window.destroyed.connect(app.quit)
        window.deleteLater()


presented = Presented()
window.frameSwapped.connect(presented.frame, Qt.ConnectionType.QueuedConnection)
window.show()
window.requestUpdate()
QTimer.singleShot(15000, lambda: emit(dict(report, timeout=True), 2))
app.exec()
hosts = list(bootstrap._owner.window_hosts.values())
report["hosts_left"] = len(hosts)
emit(report)
'''


def _probe(script: str, state_dir: Path, step: str = "", timeout: float = 60.0) -> dict:
    completed = subprocess.run([sys.executable, "-c", script, str(state_dir), step], cwd=ROOT, env=os.environ.copy(),
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
    assert host["driver"]["edges"] >= 1                              # the core's frame driver saw the frame edge
    assert report["records_after_first_frame"] == []                 # the first presented frame completed the start
    assert report["gl_validations"] == [] and report["quits"] == []  # no OpenGL check on a Vulkan window
    assert report["hosts_left"] == 0                                  # the destroyed window closed its host


def test_the_default_path_loads_no_native_core_and_keeps_no_record(tmp_path):
    configure = 'configured = bootstrap.configure_quick_graphics(reason="n27-default", start_state_dir=state_dir)\n'
    report = _probe(_window_script(configure), tmp_path)
    assert report["configured_api"] == "OpenGL" and report["backend"] == ["opengl", "opengl", ""]
    assert report["module_loaded"] is False and report["api"] == "OpenGL"
    assert report["host"] is None and report["records_after_first_frame"] == []
    assert not (tmp_path / bootstrap.START_RECORD_FOLDER).exists()
    assert report["gl_validations"] == ["quick-display-scene-graph-screen-0-generation-1"]


@needs_module
def test_a_module_that_cannot_load_falls_back_to_opengl_before_any_window(tmp_path):
    empty = tmp_path / "no_module"
    empty.mkdir()
    start = '{"load_core": lambda: __import__("rendering.native", fromlist=["load"]).load(Path(sys.argv[1]) / "no_module")}'
    report = _probe(_window_script(_CONFIGURE_VULKAN, start), tmp_path)
    api, requested, reason = report["backend"]
    assert (api, requested) == ("opengl", "vulkan") and "not built" in reason
    assert report["api"] == "OpenGL"                                  # the same process, set before any window
    assert len(report["gl_validations"]) == 1 and report["host"] is None
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
    assert nxt["module_loaded"] is False and nxt["records_after_first_frame"] == []

    again = _probe(_window_script(_CONFIGURE_VULKAN), tmp_path)        # the one after tries Vulkan again
    assert again["api"] == "Vulkan" and again["records_after_first_frame"] == []


@needs_module
def test_a_start_that_dies_before_its_first_frame_sends_the_next_start_to_opengl(tmp_path):
    # As a driver crashing at device creation leaves it: the process ends with its start pending.
    died = subprocess.run([sys.executable, "-c", _PRELUDE + _CONFIGURE_VULKAN + "os._exit(3)\n", str(tmp_path), ""],
                          cwd=ROOT, env=os.environ.copy(), text=True, capture_output=True, check=False, timeout=60)
    assert died.returncode == 3, died.stderr
    assert [record["state"] for record in _records(tmp_path)] == ["pending"]
    nxt = _probe(_window_script(_CONFIGURE_VULKAN), tmp_path)
    assert nxt["configured_api"] == "OpenGL" and "ended before its first frame" in nxt["backend"][2]
    assert nxt["api"] == "OpenGL"


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
from PySide6.QtCore import QTimer
QTimer.singleShot(0, app.quit)
app.exec()                           # the application's quit edge closes the kept host (its render thread with it)
report["closed_at_quit"] = first.closed
report["live_hosts_at_exit"] = core.live_hosts()
emit(report)
'''
    report = _probe(script, tmp_path)
    assert report["same"] is True and report["created"] == 1
    assert report["live_hosts"] == report["live_hosts_after"] == 1
    assert report["api"] == "opengl" and "created once and kept" in report["other_size"]
    assert report["closed_at_quit"] is True and report["live_hosts_at_exit"] == 0
