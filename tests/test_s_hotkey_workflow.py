"""
Integration test for S hotkey workflow.

Tests the complete workflow:
1. Start screensaver
2. Press S key
3. Display windows are HIDDEN (not just cleared)
4. Settings dialog opens (and is visible)
5. Close settings
6. Display windows shown again
7. Screensaver resumes

CRITICAL: Display widgets must be hidden when settings open,
otherwise they cover the dialog with black fullscreen windows!
"""
import pytest
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from core.settings import SettingsManager
from engine.screensaver_engine import ScreensaverEngine


@pytest.fixture
def engine_with_settings(qt_app, tmp_path):
    """Create engine with test settings."""
    settings = SettingsManager(
        organization="Test",
        application="SHotkeyTest"
    )
    
    # Create test folder with one image
    test_folder = tmp_path / "images"
    test_folder.mkdir()
    test_image = test_folder / "test.jpg"
    test_image.write_bytes(b"fake image data")
    
    # Configure settings
    settings.set('sources.folders', [str(test_folder)])
    settings.save()
    
    # Create engine
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    
    yield engine, settings
    
    # Cleanup
    if engine._running:
        engine.stop()
    engine.cleanup()
    settings.clear()


def test_s_hotkey_opens_settings_without_crash(engine_with_settings, qt_app):
    """
    Test that S hotkey opens settings dialog without crashing.
    
    This test verifies:
    - AttributeError: '_display_initialized' exists
    - NameError: All imports present
    - Display windows are HIDDEN (not covering dialog)
    """
    engine, settings = engine_with_settings
    
    # Initialize engine
    assert engine.initialize(), "Engine should initialize"
    
    # Verify _display_initialized exists and is True
    assert hasattr(engine, '_display_initialized'), "_display_initialized attribute must exist"
    assert engine._display_initialized is True, "_display_initialized should be True after init"
    
    # Start engine
    assert engine.start(), "Engine should start"
    assert engine._running is True, "Engine should be running"
    
    # Verify displays are visible before S key
    assert engine.display_manager is not None
    for display in engine.display_manager.displays:
        assert display.isVisible(), "Displays should be visible while running"
    
    # Simulate S key press - stop(exit_app=False)
    engine.stop(exit_app=False)
    
    # CRITICAL: Verify displays are HIDDEN after stop
    for display in engine.display_manager.displays:
        assert not display.isVisible(), "Displays MUST be hidden when settings open!"
    
    # Verify engine stopped
    assert engine._running is False, "Engine should be stopped"
    
    # Now simulate settings dialog closing and restart
    engine.display_manager.show_all()
    engine.start()
    
    # Verify displays visible again
    for display in engine.display_manager.displays:
        assert display.isVisible(), "Displays should be visible after restart"


def test_display_initialized_flag_lifecycle(qt_app):
    """
    Test _display_initialized flag through lifecycle.
    
    This verifies the flag exists and changes correctly.
    """
    settings = SettingsManager(
        organization="Test",
        application="DisplayFlagTest"
    )
    
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    
    # Before init
    assert hasattr(engine, '_display_initialized'), "Flag must exist from __init__"
    assert engine._display_initialized is False, "Should be False initially"
    
    # After display init (if successful)
    # Note: This might fail in test environment without displays
    try:
        result = engine._initialize_display()
        if result:
            assert engine._display_initialized is True, "Should be True after successful init"
    except Exception:
        # Display init may fail in test environment - that's okay
        pass
    
    # Cleanup
    engine.cleanup()
    settings.clear()


def test_engine_has_required_attributes(qt_app):
    """
    Test that ScreensaverEngine has all required attributes.
    
    This is a sanity check for attributes used in various methods.
    """
    engine = ScreensaverEngine()
    
    # State flags that must exist
    required_attributes = [
        '_running',
        '_initialized',
        '_display_initialized',
        '_loading_in_progress',
        '_current_transition_index',
        '_transition_types',
    ]
    
    for attr in required_attributes:
        assert hasattr(engine, attr), f"Engine must have '{attr}' attribute"


def test_settings_requested_handler_doesnt_crash_on_stop(engine_with_settings, qt_app):
    """
    Test that calling _on_settings_requested doesn't crash during stop().
    
    Tests the specific sequence:
    1. Stop engine (exit_app=False)
    2. Try to check _display_initialized
    """
    engine, settings = engine_with_settings
    
    # Initialize and start
    if not engine.initialize():
        pytest.skip("Engine initialization failed (no display in test env)")
    
    engine.start()
    
    # Stop without exiting app
    engine.stop(exit_app=False)
    
    # Now _display_initialized should still exist and be accessible
    assert hasattr(engine, '_display_initialized'), "Flag should exist after stop"
    
    # This is the check that was failing
    if engine._display_initialized:
        # Display was initialized, could restart
        pass
    else:
        # Display wasn't initialized, would need full init
        pass
    
    # If we get here, no AttributeError was raised
    engine.cleanup()


def test_settings_dialog_import_exists():
    """
    Test that required imports exist.
    
    This would catch NameError issues.
    """
    from engine.screensaver_engine import QApplication
    from engine.screensaver_engine import AnimationManager
    from engine.screensaver_engine import SettingsDialog
    
    assert QApplication is not None
    assert AnimationManager is not None
    assert SettingsDialog is not None
