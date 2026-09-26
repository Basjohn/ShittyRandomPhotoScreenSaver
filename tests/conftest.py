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
import uuid
from pathlib import Path
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
TEST_APPDATA = ROOT / "tests_tmp_appdata"
TEST_LOCALAPPDATA = ROOT / "tests_tmp_localappdata"
TEST_APPDATA.mkdir(parents=True, exist_ok=True)
TEST_LOCALAPPDATA.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(TEST_APPDATA)
os.environ["LOCALAPPDATA"] = str(TEST_LOCALAPPDATA)


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


# ---------------------------------------------------------------------------
# Chunked-suite support
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption("--chunk", type=int, default=None,
                     help="1-indexed chunk number to run (requires --total-chunks)")
    parser.addoption("--total-chunks", type=int, default=None,
                     help="Total number of chunks the suite is split into")
def pytest_collection_modifyitems(config, items):
    """Select a deterministic requested chunk."""

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
