"""
Shared pytest fixtures for screensaver tests.

Chunked test execution:
  Use ``python tests/run_chunked.py`` to run isolated subprocess chunks with
  a per-chunk timeout. Direct ``pytest tests/`` remains a single process.

  Manual chunk selection::

      pytest tests/ --chunk 1 --total-chunks 4   # run only chunk 1 of 4

  Or use the helper script::

      python tests/run_chunked.py          # four bounded chunks
      python tests/run_chunked.py --chunks 6
"""
import os
import pytest
import sys
import time
import uuid
from pathlib import Path

# Production-shaped Qt tests must establish the sole Quick graphics contract
# before the first QApplication exists.  In particular, native render owners
# require an actual current OpenGL 4.6 Core scene-graph context; accepting
# Qt's Windows D3D11 default in the shared test fixture would exercise a
# renderer contract production never permits.
from rendering.quick.bootstrap import configure_quick_graphics

configure_quick_graphics(reason="pytest-conftest")

from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
TEST_APPDATA = ROOT / "tests_tmp_appdata"
TEST_LOCALAPPDATA = ROOT / "tests_tmp_localappdata"
TEST_APPDATA.mkdir(parents=True, exist_ok=True)
TEST_LOCALAPPDATA.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(TEST_APPDATA)
os.environ["LOCALAPPDATA"] = str(TEST_LOCALAPPDATA)
# Linux resolves the same roots from XDG base directories (core/platform_paths.py);
# isolate them identically so no test run touches the real ~/.config or ~/.local.
if not sys.platform.startswith("win"):
    TEST_SHARED_DATA = ROOT / "tests_tmp_shareddata"
    TEST_SHARED_DATA.mkdir(parents=True, exist_ok=True)
    os.environ["XDG_CONFIG_HOME"] = str(TEST_APPDATA)
    os.environ["XDG_STATE_HOME"] = str(TEST_LOCALAPPDATA)
    os.environ["XDG_DATA_HOME"] = str(TEST_SHARED_DATA)


# ---------------------------------------------------------------------------
# Stale-test reconciliation — CLOSED (2026-09-05 test-truth audit)
# ---------------------------------------------------------------------------
# The former deferred skip list is fully reconciled. Of the 16 previously
# ignored modules: 13 whole-file pre-cutover fossils were deleted (they imported
# removed subsystems — rendering.widget_manager / display_widget /
# gl_compositor_pkg, widgets.spotify_bars_gl_overlay, etc.) and 3 were repaired
# and restored to normal collection (test_widget_import_dormancy: dropped the two
# deleted legacy-host probes; test_logging_routing: dropped the deleted
# gl_programs.program_cache test; test_f0_5_shadow_controls: negative-control
# guards now skip source files the cutover deleted). No module needs skipping.
# See the 2026-09-05 reconciliation section in Docs/TestSuite.md.
collect_ignore: list[str] = []

# Linux-only tests (tests/test_linux_*.py) are neither collected from a directory
# nor run when named explicitly off Linux (Docs/Guardrails/Linux_Compatibility.md §7).
from tools.impacted_tests import LINUX_ONLY_TEST_GLOB, runs_on_this_platform  # noqa: E402

collect_ignore_glob: list[str] = [] if sys.platform.startswith("linux") else [LINUX_ONLY_TEST_GLOB]


# ---------------------------------------------------------------------------
# Chunked-suite support
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption("--chunk", type=int, default=None,
                     help="1-indexed chunk number to run (requires --total-chunks)")
    parser.addoption("--total-chunks", type=int, default=None,
                     help="Total number of chunks the suite is split into")
    parser.addoption("--display-disruptive", action="store_true", default=False,
                     help="Also run tests that put real display windows on the operator's monitors "
                          "(QuickDisplayWindow.show_on_screen). Only when directly relevant.")


# ---------------------------------------------------------------------------
# Guards on production classes, installed the moment their module is imported (at collection, or lazily inside a
# test or inside production code), so no test can reach the guarded call unguarded.
# ---------------------------------------------------------------------------
import importlib.abc

_POST_IMPORT_GUARDS: dict = {}


class _GuardLoader(importlib.abc.Loader):
    """Delegates to the real loader, then installs the module's guard."""

    def __init__(self, loader, install):
        self._srpss_loader = loader
        self._srpss_install = install

    def create_module(self, spec):
        return self._srpss_loader.create_module(spec)

    def exec_module(self, module):
        self._srpss_loader.exec_module(module)
        self._srpss_install(module)

    def __getattr__(self, name):           # get_source, get_resource_reader, ...
        return getattr(self._srpss_loader, name)


class _GuardFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        install = _POST_IMPORT_GUARDS.get(name)
        if install is None:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None:
                if spec.loader is not None:
                    spec.loader = _GuardLoader(spec.loader, install)
                return spec
        return None


def _guard_on_import(name: str, install) -> None:
    _POST_IMPORT_GUARDS[name] = install
    if not any(isinstance(finder, _GuardFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _GuardFinder())
    module = sys.modules.get(name)
    if module is not None:
        install(module)


# Real display windows on the operator's monitors (operator, 7 Nov: "a test that causes a blue screen and a black
# screen ... it disrupts my entire display ecosystem"). A test reaching QuickDisplayWindow.show_on_screen - directly or
# through production code - is skipped unless the run asks for --display-disruptive. The window never shows.
# The refusal is an ordinary error inside production (``DisplayWindowBlocked``), so production's own show-failure path
# retires what it already started (the Visualizer's non-daemon logical runtime among it); the test is then reported
# as skipped (``pytest_runtest_makereport``). A ``pytest.skip`` raised in here escaped every ``except Exception`` and
# abandoned a running runtime: ``test_s_hotkey_workflow.py`` then never exited (7 Nov).
_DISPLAY_GUARD = {"allowed": False, "nodeid": "", "blocked": None}


class DisplayWindowBlocked(RuntimeError):
    """A test reached ``QuickDisplayWindow.show_on_screen`` without --display-disruptive."""


# The refusal's log record must not keep the refused runtime alive. Production's show-failure path logs the error
# with ``exc_info`` and the exception as an argument; production's queued handler snapshots every record without its
# traceback (``core/logging/logger.py:_snapshot_log_record``), but pytest's log capture keeps the record itself for the
# whole test. Its traceback's frames chain back (``f_back``) to ``DisplayManager.initialize_displays``, whose locals
# hold every display unit it built, so a runtime-destruction barrier waiting for those units timed out and reached
# the real ``QCoreApplication.exit(1)`` (``test_s_hotkey_workflow.py``, 7 Nov). Records about the guard's own refusal
# are detached the way production detaches them: the traceback is rendered to text, the exception to its message.
# Every other record keeps its ``exc_info`` for tests that inspect it.
def _install_display_guard_record_detach() -> None:
    import logging
    import traceback

    previous = logging.getLogRecordFactory()
    if getattr(previous, "_srpss_display_guard_detach", False):
        return

    def detach_display_guard_refusals(*args, **kwargs):
        record = previous(*args, **kwargs)
        exc_info = record.exc_info
        if exc_info and isinstance(exc_info[1], DisplayWindowBlocked):
            record.exc_text = "".join(traceback.format_exception(*exc_info)).rstrip()
            record.exc_info = None
        if isinstance(record.args, tuple) and any(isinstance(arg, DisplayWindowBlocked) for arg in record.args):
            record.args = tuple(str(arg) if isinstance(arg, DisplayWindowBlocked) else arg for arg in record.args)
        return record

    detach_display_guard_refusals._srpss_display_guard_detach = True
    logging.setLogRecordFactory(detach_display_guard_refusals)


_install_display_guard_record_detach()


def _install_display_window_guard(module) -> None:
    window = module.QuickDisplayWindow
    if getattr(window.show_on_screen, "_srpss_guard", False):
        return
    original = window.show_on_screen

    def guarded_show_on_screen(self, *args, **kwargs):
        if not _DISPLAY_GUARD["allowed"]:
            message = (f"{_DISPLAY_GUARD['nodeid']} would show a real display window on the operator's monitors; "
                       "run it only when directly relevant, with --display-disruptive")
            _DISPLAY_GUARD["blocked"] = message
            raise DisplayWindowBlocked(message)
        return original(self, *args, **kwargs)

    guarded_show_on_screen._srpss_guard = True
    window.show_on_screen = guarded_show_on_screen


# Modal popups (7 Nov): an unpatched StyledPopup.exec() shows a real modal dialog on the operator's screen and blocks
# the test forever (a Studio that failed to open under the GL-less offscreen platform hung for minutes in its error
# popup). A test that expects a popup patches StyledPopup.exec itself; any other popup is answered as dismissed, never
# shown, and fails the test at teardown with its title and message.
_POPUP_GUARD = {"shown": []}


def _install_popup_guard(module) -> None:
    popup = module.StyledPopup
    if getattr(popup.exec, "_srpss_guard", False):
        return

    def guarded_exec(self, *args, **kwargs):
        _POPUP_GUARD["shown"].append(f"{getattr(self, '_title', '')}: {getattr(self, '_message', '')}")
        return 0

    guarded_exec._srpss_guard = True
    popup.exec = guarded_exec


_guard_on_import("rendering.quick.window", _install_display_window_guard)
_guard_on_import("ui.styled_popup", _install_popup_guard)


@pytest.fixture(autouse=True)
def _no_real_display_window_unless_asked(request):
    _DISPLAY_GUARD["allowed"] = bool(request.config.getoption("--display-disruptive"))
    _DISPLAY_GUARD["nodeid"] = request.node.nodeid
    _DISPLAY_GUARD["blocked"] = None
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A test whose setup or body reached the display-window guard is reported as skipped, whatever it raised."""
    outcome = yield
    blocked = _DISPLAY_GUARD.get("blocked")
    if blocked and call.when in ("setup", "call"):
        report = outcome.get_result()
        report.outcome = "skipped"
        report.longrepr = (str(item.path), int(item.location[1] or 0), f"Skipped: {blocked}")


@pytest.fixture(autouse=True)
def _no_unpatched_modal_popup():
    _POPUP_GUARD["shown"].clear()
    yield
    shown, _POPUP_GUARD["shown"] = list(_POPUP_GUARD["shown"]), []
    if shown:
        pytest.fail("the test reached a real modal StyledPopup without patching StyledPopup.exec (it would show "
                    "on the operator's screen and block): " + " | ".join(shown), pytrace=False)


def pytest_collection_modifyitems(config, items):
    """Skip Linux-only tests off Linux; select a deterministic requested chunk."""

    linux_only = pytest.mark.skip(reason="Linux-only test (tests/test_linux_*.py)")
    for item in items:
        if not runs_on_this_platform(item.path):
            item.add_marker(linux_only)

    chunk = config.getoption("--chunk")
    total = config.getoption("--total-chunks")
    if chunk is None or total is None:
        return
    chunk = max(1, min(chunk, total))
    # Stable sort by nodeid so chunks are deterministic
    items.sort(key=lambda item: item.nodeid)
    per_chunk = len(items) // total
    remainder = len(items) % total
    start = 0
    for i in range(1, chunk):
        start += per_chunk + (1 if i <= remainder else 0)
    size = per_chunk + (1 if chunk <= remainder else 0)
    selected = items[start:start + size]
    deselected = [it for it in items if it not in selected]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = selected


def pytest_sessionstart(session):
    """Keep storage-path resolution deterministic for the whole suite."""
    try:
        from core.settings.storage_paths import reset_module_cache
        reset_module_cache()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Qt exit tripwire: one real QCoreApplication.exit() poisons the whole process
# ---------------------------------------------------------------------------
# pytest never runs QCoreApplication.exec(). Outside it, exit() leaves Qt's
# per-thread quit flag set, so every later nested QEventLoop.exec() (qtbot.wait
# / waitUntil / local loops) returns at once and unrelated event-loop tests fail
# in cascade (measured: the loop's own timer never runs; only a real exec()
# clears it; quit() outside exec() is harmless). Production reaches exit(1) by
# fail-closed paths such as a replacement destruction-barrier timeout (R-53),
# which is correct there but leaves this process's Qt state untrustworthy.
# Tests that exercise those paths stub exit with monkeypatch and never reach
# the real one. Anything that does reach it stops the session right after that
# test, naming it, instead of letting later tests fail for the wrong reason.
_QT_EXIT_CODES: list[int] = []


def _install_qt_exit_tripwire() -> None:
    from PySide6.QtCore import QCoreApplication

    real_exit = QCoreApplication.exit
    if getattr(real_exit, "_srpss_exit_tripwire", False):
        return

    def exit_tripwire(returnCode: int = 0) -> None:  # noqa: N803 - Qt's name
        _QT_EXIT_CODES.append(int(returnCode))
        real_exit(returnCode)

    exit_tripwire._srpss_exit_tripwire = True
    QCoreApplication.exit = staticmethod(exit_tripwire)


_install_qt_exit_tripwire()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    yield
    if _QT_EXIT_CODES:
        code = _QT_EXIT_CODES[0]
        _QT_EXIT_CODES.clear()
        pytest.exit(
            f"{item.nodeid} reached the real QCoreApplication.exit({code}) (e.g. a "
            "runtime destruction-barrier timeout). Every later Qt event loop in this "
            "process would return immediately, so later results would be invalid. "
            "Fix or isolate that test, then run the remaining tests in a fresh process.",
            returncode=3,
        )


@pytest.fixture(autouse=True)
def _no_plain_qcoreapplication(request):
    """Fail the test that leaves a non-GUI QCoreApplication as the process's application.

    Qt allows one application per process and it cannot be replaced. Once a plain
    QCoreApplication exists, every later QGuiApplication/QApplication request returns
    it, and creating an OpenGL context (offscreen captures, Quick windows) crashes the
    interpreter with an access violation in whichever later test tries first, far from
    the cause (it happened with ``test_release_media``). Tests and the tools they drive
    use QGuiApplication (or the ``qt_app`` fixture) instead.
    """
    yield
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    app = QCoreApplication.instance()
    if app is not None and not isinstance(app, QGuiApplication):
        pytest.exit(
            f"{request.node.nodeid} left a plain QCoreApplication as this process's Qt "
            "application. Later OpenGL context creation in this process would crash. Create a "
            "QGuiApplication (or use the qt_app fixture) before the code under test needs one.",
            returncode=3,
        )


@pytest.fixture(autouse=True)
def _forget_idle_generation_cancellations():
    """Tests reuse generation numbers; a cancellation must not outlive its test.

    Only generations with no queued or scheduled work are forgotten (see
    ``forget_idle_generation_cancellations_for_tests``); production fencing is
    untouched.
    """
    yield
    manager = sys.modules.get("core.threading.manager")
    if manager is not None:
        manager.forget_idle_generation_cancellations_for_tests()


@pytest.fixture(autouse=True, scope="module")
def _no_studio_worker_outlives_its_module():
    """A module that started a Studio clip worker (``ClipLoadJob``) leaves none running: every job is cancelled or
    finished, and its whole process tree with it. Free for every other module (one counter read)."""
    def started() -> int:
        module = sys.modules.get("ui.studio.waveform_recorded_inputs")
        return module.STARTED[0] if module is not None and hasattr(module, "STARTED") else 0
    before = started()
    yield
    if started() == before:
        return
    from PySide6.QtCore import QCoreApplication
    from tests.studio_worker_probe import kill_all, surviving_workers
    from ui.studio.waveform_recorded_inputs import worker_tag
    tag = worker_tag()
    deadline = time.monotonic() + 20.0          # finished-signal handling needs the event loop
    left = surviving_workers(tag)
    while left and time.monotonic() < deadline:
        if QCoreApplication.instance() is not None:
            QCoreApplication.processEvents()
        time.sleep(0.2)
        left = surviving_workers(tag)
    if left:
        lines = [" ".join(p.cmdline()[-4:]) for p in left if p.is_running()]
        kill_all(left)
        pytest.fail(f"Studio clip workers outlived their test module: {lines}", pytrace=False)


@pytest.fixture(scope='session')
def qt_app():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # Don't quit - causes issues with pytest


# ---------------------------------------------------------------------------
# Benign cross-test Qt scene-graph teardown slot-miss filter
# ---------------------------------------------------------------------------
# Retained Quick display objects (BackgroundRenderItem / QuickSceneController)
# bind a DirectConnection ``sceneGraphInvalidated -> invalidate`` slot. When a
# retired window is torn down (lazily, whenever Python releases it), that scene
# graph invalidation can strike a sibling render item whose C++ object is already
# gone, raising ``AttributeError: Slot '<Type>::' not found``. Production guards
# this teardown ordering (rendering/quick/render/background_item.py disconnects in
# a try/except and never aborts teardown), and the operator confirms live editing
# is clean -- but across a *whole-file* Qt run pytest-qt's global excepthook
# records the stray slot-miss and escalates it to whichever unrelated test happens
# to be pumping the event loop (the victim shifts if you deselect one).
#
# Patch pytest-qt's capture hook exactly once so ONLY this specific benign pattern
# is dropped; every other exception is forwarded to the original hook unchanged,
# preserving genuine Qt-slot exception capture. This is test-harness hygiene only;
# no production behavior changes.
try:  # pragma: no cover - depends on pytest-qt being installed
    import pytestqt.exceptions as _pytestqt_exceptions

    _ORIG_EXCEPT_HOOK = _pytestqt_exceptions._except_hook

    def _is_benign_qt_teardown_slot_miss(exc_type, value) -> bool:
        if exc_type is not AttributeError:
            return False
        text = str(value)
        return text.startswith("Slot '") and "::' not found" in text

    def _filtered_except_hook(type_, value, tback, exceptions=None):
        if _is_benign_qt_teardown_slot_miss(type_, value):
            return
        _ORIG_EXCEPT_HOOK(type_, value, tback, exceptions=exceptions)

    _pytestqt_exceptions._except_hook = _filtered_except_hook
except Exception:  # pragma: no cover
    pass


@pytest.fixture
def windows_platform(monkeypatch):
    """Select the Windows branch of every ``core.platform_paths.IS_WINDOWS`` decision on any OS.

    For tests that pin a Windows contract: the ``%APPDATA%``/``%PROGRAMDATA%``/
    ``%LOCALAPPDATA%`` roots (Linux ignores those variables by design) or the
    Windows-only secure-desktop URL handoff.
    """
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", True)


@pytest.fixture
def visualizer_in_process():
    """State the Visualizer's in-process path (``--viz-in-process``) for a test whose owner must tick in this process
    (a patched beat engine or tick, the logical runtime's own thread). The engine worker is the product's default on
    Windows; a test that builds the owner through the host binding without stating a path follows the platform."""
    import dataclasses

    from core.diagnostics import experiment_flags

    saved = experiment_flags.active_experiment_flags()
    experiment_flags.override_active_flags_for_testing(dataclasses.replace(saved, visualizer_engine_worker=False))
    try:
        yield
    finally:
        experiment_flags.override_active_flags_for_testing(saved)


@pytest.fixture
def settings_manager(tmp_path):
    """Create SettingsManager instance for testing."""
    from core.settings import SettingsManager
    storage_base = tmp_path / "settings"
    manager = SettingsManager(
        organization="Test",
        application=f"ScreensaverTest_{uuid.uuid4().hex}",
        storage_base_dir=storage_base,
    )
    yield manager


@pytest.fixture
def thread_manager():
    """Create ThreadManager instance for testing."""
    from core.threading.manager import ThreadManager
    manager = ThreadManager()
    yield manager
    manager.shutdown(wait=True)


@pytest.fixture
def app_shared_thread_manager():
    """A ThreadManager registered as app-shared (e.g. for sidecar readers), restored afterwards."""
    from core.threading.manager import ThreadManager
    previous = ThreadManager.get_app_shared()
    manager = ThreadManager()
    ThreadManager.set_app_shared(manager)
    yield manager
    ThreadManager.set_app_shared(previous)
    manager.shutdown(wait=True)


@pytest.fixture
def resource_manager():
    """Create ResourceManager instance for testing."""
    from core.resources import ResourceManager
    manager = ResourceManager()
    yield manager
    manager.shutdown()


@pytest.fixture
def event_system():
    """Create EventSystem instance for testing."""
    from core.events import EventSystem
    system = EventSystem()
    yield system
    system.clear()


@pytest.fixture
def temp_image(tmp_path):
    """Create a temporary test image."""
    from PySide6.QtGui import QImage, QColor
    from PySide6.QtCore import QSize
    
    # Create a simple 100x100 test image
    image = QImage(QSize(100, 100), QImage.Format.Format_RGB32)
    image.fill(QColor(255, 0, 0))  # Red
    
    image_path = tmp_path / "test_image.png"
    image.save(str(image_path))
    
    return image_path


def pytest_sessionfinish(session, exitstatus):
    """Every run, focused ones included, fails on a QML import the frozen build would refuse. The release build
    rejects it anyway; this catches it on the commit that adds it (QtQml.Models slipped through a focused run)."""
    from tools.qml_import_contract import violations
    found = violations()
    if found:
        session.config._srpss_qml_import_violations = found
        session.exitstatus = 1


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    found = getattr(config, "_srpss_qml_import_violations", None)
    if found:
        terminalreporter.section("QML import contract", sep="=", red=True, bold=True)
        terminalreporter.write_line("Qt QML imports outside tools/build_layout.ps1's frozen packaging allowlist; "
                                    "the release build refuses them. Remove the import or review the packaging:")
        for line in found:
            terminalreporter.write_line(f"  {line}")

