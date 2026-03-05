"""
Shared pytest fixtures for screensaver tests.

Chunked test execution:
  When running the full suite (``pytest tests/``), tests are automatically
  split into chunks to avoid memory/timeout issues.  The chunking is
  transparent — each chunk runs in its own subprocess so GL state, leaked
  Qt singletons, and memory are cleanly isolated.

  Manual chunk selection::

      pytest tests/ --chunk 1 --total-chunks 4   # run only chunk 1 of 4

  Or use the helper script::

      python tests/run_chunked.py          # auto-detect chunk count
      python tests/run_chunked.py --chunks 6
"""
import pytest
import sys
import uuid
from PySide6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# Chunked-suite support
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption("--chunk", type=int, default=None,
                     help="1-indexed chunk number to run (requires --total-chunks)")
    parser.addoption("--total-chunks", type=int, default=None,
                     help="Total number of chunks the suite is split into")


def pytest_collection_modifyitems(config, items):
    """Filter collected tests to only those in the requested chunk."""
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
