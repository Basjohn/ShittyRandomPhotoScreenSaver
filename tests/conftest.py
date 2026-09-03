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
# Deferred stale-test reconciliation (skip in the meantime; reconcile at J+ exit)
# ---------------------------------------------------------------------------
# These modules import pre-cutover code the retained-Quick architecture removed
# (the SpotifyVisualizerWidget monolith, spotify_bars_gl_overlay, WidgetManager,
# rendering.spotify_widget_creators, rendering.widget_setup_all, and various
# removed config_applier/tick_helpers/adapter symbols). The visualizer floor is
# already reconciled and green; these remaining modules are skipped here until
# the J+ exit reconciliation pass, which biases to the current Quick
# architecture and deletes when in doubt. See Current_Plan.md.
collect_ignore = [
    # Visualizer-unrelated infrastructure (WidgetManager / display / logging /
    # layout / shadow / GL-compositor) — reconcile or delete at J+ exit.
    "test_widget_manager.py",
    "test_widget_manager_refresh.py",
    "test_widget_setup.py",
    "test_widget_import_dormancy.py",
    "test_display_context_menu.py",
    "test_display_image_ops.py",
    "test_display_integration.py",
    "test_custom_layout_manager.py",
    "test_logging_routing.py",
    "test_f0_5_shadow_controls.py",
    "test_p3_set_state_attribution.py",
    "test_compositor_gpu_queries.py",
    "test_startup_shader_warmup.py",
    # Visualizer-related but still importing removed modules — reconcile at J+
    # exit (fix against the current renderers/config_applier where valuable).
    "test_ghost_isolation.py",
    "test_line4_6_pipeline_trace.py",
    "test_oscilloscope_display_contract.py",
]


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


@pytest.fixture(scope='session')
def qt_app():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # Don't quit - causes issues with pytest


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
