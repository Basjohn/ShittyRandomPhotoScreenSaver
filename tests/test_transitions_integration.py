"""
Integration tests for transitions with pan & scan.

Tests that transitions work correctly when pan & scan is enabled,
and that they trigger automatically during normal rotation.
"""
import pytest
import time
from pathlib import Path
import uuid
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
import sys

from transitions.crossfade_transition import CrossfadeTransition
from transitions.diffuse_transition import DiffuseTransition
from rendering.display_widget import DisplayWidget
from core.settings.settings_manager import SettingsManager
from engine.display_manager import DisplayMode


@pytest.fixture
def app():
    """Create QApplication for tests."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
        yield app
        app.quit()
    else:
        yield QApplication.instance()


@pytest.fixture
def test_images():
    """Get test image paths."""
    # Use actual images from user's wallpaper folder
    test_dir = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET")
    images = list(test_dir.glob("*.jpg"))[:3]  # Get first 3 JPG images
    if len(images) < 2:
        images = list(test_dir.glob("*.png"))[:3]  # Fallback to PNG
    return images


@pytest.fixture
def settings_manager(tmp_path):
    """Create settings manager for tests."""
    # Use a dedicated organization/application pair so this suite has an
    # isolated QSettings store, rather than attempting to pass a file path
    # into SettingsManager (its constructor expects org/app, not a path).
    manager = SettingsManager(
        organization="Test",
        application=f"TransitionsIntegrationTest_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path,
    )

    # Configure for testing
    manager.set('display.pan_and_scan', True)
    manager.set('display.pan_auto_speed', True)
    manager.set('timing.interval', 5)  # 5 second rotation

    # Canonical nested transitions config for tests
    transitions_cfg = manager.get('transitions', {}) or {}
    if not isinstance(transitions_cfg, dict):
        transitions_cfg = {}
    transitions_cfg['type'] = 'Crossfade'
    transitions_cfg['duration_ms'] = 500  # Fast transitions for testing
    manager.set('transitions', transitions_cfg)

    return manager


def _update_transitions(
    settings_manager: SettingsManager,
    *,
    transition_type: str | None = None,
    duration_ms: int | None = None,
    diffuse_block_size: int | None = None,
    diffuse_shape: str | None = None,
    block_rows: int | None = None,
    block_cols: int | None = None,
) -> None:
    """Helper to update canonical nested transition config for these tests."""
    cfg = settings_manager.get('transitions', {}) or {}
    if not isinstance(cfg, dict):
        cfg = {}

    if transition_type is not None:
        cfg['type'] = transition_type
    if duration_ms is not None:
        cfg['duration_ms'] = duration_ms

    if diffuse_block_size is not None or diffuse_shape is not None:
        diff_cfg = cfg.get('diffuse', {})
        if not isinstance(diff_cfg, dict):
            diff_cfg = {}
        if diffuse_block_size is not None:
            diff_cfg['block_size'] = diffuse_block_size
        if diffuse_shape is not None:
            diff_cfg['shape'] = diffuse_shape
        cfg['diffuse'] = diff_cfg

    if block_rows is not None or block_cols is not None:
        block_cfg = cfg.get('block_flip', {})
        if not isinstance(block_cfg, dict):
            block_cfg = {}
        if block_rows is not None:
            block_cfg['rows'] = block_rows
        if block_cols is not None:
            block_cfg['cols'] = block_cols
        cfg['block_flip'] = block_cfg

    settings_manager.set('transitions', cfg)


@pytest.mark.skip(reason="Pan & Scan feature removed in v1.2; DisplayWidget no longer exposes _pan_and_scan.")
def test_crossfade_with_pan_and_scan(app, test_images, settings_manager):
    """Test that crossfade transition works with pan & scan enabled."""
    if len(test_images) < 2:
        pytest.skip("Not enough test images")
    
    # Create display widget
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager
    )
    widget.setGeometry(100, 100, 800, 600)
    widget.show()
    
    # Load first image
    pixmap1 = QPixmap(str(test_images[0]))
    assert not pixmap1.isNull(), f"Failed to load {test_images[0]}"
    widget.set_image(pixmap1, str(test_images[0]))
    
    # Process events
    app.processEvents()
    time.sleep(0.1)
    
    # Load second image (should trigger transition)
    pixmap2 = QPixmap(str(test_images[1]))
    assert not pixmap2.isNull(), f"Failed to load {test_images[1]}"
    
    # Track if transition started
    transition_started = [False]
    def on_transition():
        transition_started[0] = True
    
    if widget._current_transition:
        widget._current_transition.started.connect(on_transition)
    
    widget.set_image(pixmap2, str(test_images[1]))
    app.processEvents()
    
    # Wait for transition to start
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
        if widget._current_transition:
            break
    
    assert widget._current_transition is not None, "Transition did not start"
    assert isinstance(widget._current_transition, CrossfadeTransition), \
        f"Wrong transition type: {type(widget._current_transition)}"
    
    # Wait for transition to complete (max 2 seconds)
    max_wait = 2.0
    start_time = time.time()
    while widget._current_transition and (time.time() - start_time) < max_wait:
        app.processEvents()
        time.sleep(0.05)
    
    assert widget._current_transition is None, "Transition did not complete"
    
    # Verify pan & scan is running after transition
    assert widget._pan_and_scan.is_enabled(), "Pan & scan not enabled after transition"
    
    widget.close()


@pytest.mark.skip(reason="Pan & Scan feature removed in v1.2; DisplayWidget no longer exposes _pan_and_scan.")
def test_diffuse_with_pan_and_scan(app, test_images, settings_manager):
    """Test that diffuse transition works with pan & scan enabled."""
    if len(test_images) < 2:
        pytest.skip("Not enough test images")
    
    # Configure for diffuse
    _update_transitions(settings_manager, transition_type='Diffuse')
    
    # Create display widget
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager
    )
    widget.setGeometry(100, 100, 800, 600)
    widget.show()
    
    # Load first image
    pixmap1 = QPixmap(str(test_images[0]))
    widget.set_image(pixmap1, str(test_images[0]))
    app.processEvents()
    time.sleep(0.1)
    
    # Load second image (should trigger transition)
    pixmap2 = QPixmap(str(test_images[1]))
    widget.set_image(pixmap2, str(test_images[1]))
    app.processEvents()
    
    # Wait for transition to start
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
        if widget._current_transition:
            break
    
    assert widget._current_transition is not None, "Diffuse transition did not start"
    assert isinstance(widget._current_transition, DiffuseTransition), \
        f"Wrong transition type: {type(widget._current_transition)}"
    
    # Verify labels exist and have pixmaps (not black)
    if hasattr(widget._current_transition, '_old_label') and widget._current_transition._old_label:
        old_pixmap = widget._current_transition._old_label.pixmap()
        assert old_pixmap and not old_pixmap.isNull(), "Old label has no pixmap (would show black)"
    
    if hasattr(widget._current_transition, '_new_label') and widget._current_transition._new_label:
        new_pixmap = widget._current_transition._new_label.pixmap()
        assert new_pixmap and not new_pixmap.isNull(), "New label has no pixmap (would show black)"
    
    # Wait for transition to complete
    max_wait = 2.0
    start_time = time.time()
    while widget._current_transition and (time.time() - start_time) < max_wait:
        app.processEvents()
        time.sleep(0.05)
    
    assert widget._current_transition is None, "Diffuse transition did not complete"
    
    # Verify pan & scan is running
    assert widget._pan_and_scan.is_enabled(), "Pan & scan not enabled after diffuse"
    
    widget.close()


@pytest.mark.skip(reason="Pan & Scan feature removed in v1.2; DisplayWidget no longer exposes _pan_and_scan.")
def test_pan_and_scan_no_zoom_after_transition(app, test_images, settings_manager):
    """Test that pan & scan doesn't cause zoom effect after transition completes."""
    if len(test_images) < 2:
        pytest.skip("Not enough test images")
    
    # Create display widget
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager
    )
    widget.setGeometry(100, 100, 800, 600)
    widget.show()
    
    # Load first image
    pixmap1 = QPixmap(str(test_images[0]))
    widget.set_image(pixmap1, str(test_images[0]))
    app.processEvents()
    time.sleep(0.1)
    
    # Get pan & scan image size after first load
    if widget._pan_and_scan._scaled_pixmap:
        first_size = widget._pan_and_scan._scaled_pixmap.size()
    
    # Load second image with transition
    pixmap2 = QPixmap(str(test_images[1]))
    widget.set_image(pixmap2, str(test_images[1]))
    app.processEvents()
    
    # Wait for transition to complete
    max_wait = 2.0
    start_time = time.time()
    while widget._current_transition and (time.time() - start_time) < max_wait:
        app.processEvents()
        time.sleep(0.05)
    
    # Get pan & scan image size after transition
    if widget._pan_and_scan._scaled_pixmap:
        second_size = widget._pan_and_scan._scaled_pixmap.size()
        
        # Sizes should be similar (within 20% - accounts for different aspect ratios)
        width_ratio = second_size.width() / first_size.width()
        height_ratio = second_size.height() / first_size.height()
        
        assert 0.8 <= width_ratio <= 1.2, \
            f"Width changed too much: {first_size.width()} -> {second_size.width()}"
        assert 0.8 <= height_ratio <= 1.2, \
            f"Height changed too much: {first_size.height()} -> {second_size.height()}"
    
    widget.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
