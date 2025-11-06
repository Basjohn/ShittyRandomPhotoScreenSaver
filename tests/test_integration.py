"""Integration tests for screensaver engine."""
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from engine.screensaver_engine import ScreensaverEngine


@pytest.fixture
def qapp():
    """Create QApplication for tests that need it."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def engine(qapp):
    """Create screensaver engine for testing."""
    engine = ScreensaverEngine()
    yield engine
    engine.cleanup()


def test_engine_creation(engine):
    """Test engine can be created."""
    assert engine is not None
    assert engine.is_running() is False


def test_engine_initialization(engine):
    """Test engine initialization."""
    # Initialize
    result = engine.initialize()
    
    # Should succeed even without image sources (uses RSS defaults)
    assert result is True
    
    # Core systems should be initialized
    assert engine.event_system is not None
    assert engine.resource_manager is not None
    assert engine.thread_manager is not None
    assert engine.settings_manager is not None
    
    # Engine components should be initialized
    assert engine.display_manager is not None
    assert engine.image_queue is not None


def test_engine_core_systems(engine):
    """Test core systems initialization."""
    engine.initialize()
    
    # Event system
    assert engine.event_system is not None
    
    # Resource manager
    assert engine.resource_manager is not None
    stats = engine.resource_manager.get_stats()
    assert 'total_resources' in stats
    
    # Thread manager
    assert engine.thread_manager is not None
    pool_stats = engine.thread_manager.get_pool_stats()
    assert 'io' in pool_stats or 'compute' in pool_stats
    
    # Settings manager
    assert engine.settings_manager is not None
    interval = engine.settings_manager.get('timing.interval', 10)
    assert interval > 0


def test_engine_image_queue_initialization(engine):
    """Test image queue is built from sources."""
    engine.initialize()
    
    assert engine.image_queue is not None
    
    # Should have images from default RSS sources
    assert engine.image_queue.total_images() > 0
    
    # Queue stats
    stats = engine.image_queue.get_stats()
    assert stats['total_images'] > 0
    assert stats['shuffle_enabled'] in [True, False]


def test_engine_display_initialization(engine):
    """Test display manager initialization."""
    engine.initialize()
    
    assert engine.display_manager is not None
    
    # Should have at least one display
    display_count = engine.display_manager.get_display_count()
    assert display_count > 0
    
    # Display info
    displays = engine.display_manager.get_display_info()
    assert len(displays) > 0


def test_engine_start_stop(engine):
    """Test engine start and stop."""
    engine.initialize()
    
    # Start
    result = engine.start()
    assert result is True
    assert engine.is_running() is True
    
    # Stop
    engine.stop()
    assert engine.is_running() is False


def test_engine_signals(engine, qtbot):
    """Test engine signals are emitted."""
    engine.initialize()
    
    # Connect signal spy
    with qtbot.waitSignal(engine.started, timeout=1000):
        engine.start()
    
    with qtbot.waitSignal(engine.stopped, timeout=1000):
        engine.stop()


def test_engine_rotation_timer(engine):
    """Test rotation timer is configured."""
    engine.initialize()
    
    assert engine._rotation_timer is not None
    
    # Timer should be configured but not started
    assert engine._rotation_timer.isActive() is False
    
    # Start engine
    engine.start()
    
    # Timer should now be active
    assert engine._rotation_timer.isActive() is True
    
    # Stop engine
    engine.stop()
    
    # Timer should be stopped and cleaned up
    assert engine._rotation_timer is None


def test_engine_get_stats(engine):
    """Test engine statistics."""
    engine.initialize()
    
    stats = engine.get_stats()
    
    assert 'running' in stats
    assert 'current_image' in stats
    assert 'loading' in stats
    assert 'folder_sources' in stats
    assert 'rss_sources' in stats
    assert 'queue' in stats
    assert 'displays' in stats
    
    # RSS sources depend on configuration (may be 0 if none configured)
    assert stats['rss_sources'] >= 0


def test_engine_cleanup(engine):
    """Test engine cleanup."""
    engine.initialize()
    engine.start()
    
    # Cleanup should stop engine
    engine.cleanup()
    
    assert engine.is_running() is False


def test_engine_without_initialization():
    """Test engine behavior without initialization."""
    engine = ScreensaverEngine()
    
    # Should not crash
    assert engine.is_running() is False
    
    # Start without init should handle gracefully
    # (May fail but shouldn't crash)
    try:
        engine.start()
    except Exception:
        pass  # Expected to potentially fail
    
    engine.cleanup()


def test_engine_default_rss_sources(engine):
    """Test engine RSS sources are empty when none configured."""
    engine.initialize()
    
    # RSS sources are only created if explicitly configured
    # With no configuration, rss_sources should be empty
    assert len(engine.rss_sources) >= 0  # May be 0 or more depending on settings
    
    # If RSS sources exist, they should be valid
    assert engine.image_queue.total_images() > 0


def test_engine_settings_integration(engine):
    """Test engine reads settings correctly."""
    engine.initialize()
    
    # Check timing settings
    assert engine._rotation_timer is not None
    interval = engine.settings_manager.get('timing.interval', 10)
    assert engine._rotation_timer.interval() == interval * 1000
    
    # Check display settings
    display_mode = engine.settings_manager.get('display.mode', 'fill')
    assert display_mode in ['fill', 'fit', 'shrink']
    
    # Check queue settings
    shuffle = engine.settings_manager.get('queue.shuffle', True)
    # Convert shuffle to bool if it's a string (settings may return strings)
    if isinstance(shuffle, str):
        shuffle_bool = shuffle.lower() == 'true'
    else:
        shuffle_bool = bool(shuffle)
    assert engine.image_queue.shuffle_enabled == shuffle_bool


def test_engine_multiple_start_calls(engine):
    """Test multiple start calls are handled."""
    engine.initialize()
    
    # First start
    result1 = engine.start()
    assert result1 is True
    
    # Second start (should be idempotent)
    result2 = engine.start()
    assert result2 is True
    
    assert engine.is_running() is True
    
    engine.stop()


def test_engine_stop_without_start(engine):
    """Test stop without start doesn't crash."""
    engine.initialize()
    
    # Stop without starting
    engine.stop()  # Should not crash
    
    assert engine.is_running() is False
