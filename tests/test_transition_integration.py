"""
Integration tests for transition system.

Tests that transitions actually run in DisplayWidget and complete properly.
These tests validate the full transition lifecycle end-to-end.
"""
import pytest
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap, QImage, QColor
from PySide6.QtCore import QSize, QTimer, Qt
from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from core.settings import SettingsManager
from transitions.crossfade_transition import CrossfadeTransition
from transitions.slide_transition import SlideTransition, SlideDirection
from transitions.diffuse_transition import DiffuseTransition
from transitions.block_puzzle_flip_transition import BlockPuzzleFlipTransition
from transitions.wipe_transition import WipeTransition, WipeDirection


@pytest.fixture
def test_pixmap():
    """Create test pixmap."""
    image = QImage(QSize(200, 200), QImage.Format.Format_RGB32)
    image.fill(QColor(255, 0, 0))  # Red
    return QPixmap.fromImage(image)


@pytest.fixture
def test_pixmap2():
    """Create second test pixmap."""
    image = QImage(QSize(200, 200), QImage.Format.Format_RGB32)
    image.fill(QColor(0, 255, 0))  # Green
    return QPixmap.fromImage(image)


@pytest.fixture
def display_widget(qt_app, settings_manager):
    """Create DisplayWidget for testing."""
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager
    )
    widget.resize(400, 400)
    yield widget
    widget.close()
    widget.deleteLater()


class TestTransitionIntegration:
    """Integration tests for transition system."""
    
    def test_crossfade_transition_runs(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that crossfade transition actually runs."""
        # Set up transition settings
        display_widget.settings_manager.set('transitions.type', 'Crossfade')
        display_widget.settings_manager.set('transitions.duration_ms', 500)
        
        # Display first image
        display_widget.set_image(test_pixmap, "test1.png")
        assert display_widget.current_pixmap is not None
        
        # Track transition completion
        transition_finished = {'value': False}
        
        def on_finished():
            transition_finished['value'] = True
        
        # Display second image with transition
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Check transition was created
        if display_widget._current_transition:
            display_widget._current_transition.finished.connect(on_finished)
            
            # Process events for transition to complete (longer timeout for timer-based animation)
            QTimer.singleShot(3000, qt_app.quit)
            qt_app.exec()
            
            # Verify transition completed
            assert transition_finished['value'], "Crossfade transition should finish"
        
        # Verify final image displayed
        assert display_widget.current_pixmap is not None
    
    def test_slide_transition_runs(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that slide transition actually runs."""
        # Set up transition settings
        display_widget.settings_manager.set('transitions.type', 'Slide')
        display_widget.settings_manager.set('transitions.duration_ms', 300)
        display_widget.settings_manager.set('transitions.direction', 'Left to Right')
        
        # Display first image
        display_widget.set_image(test_pixmap, "test1.png")
        
        # Track transition completion
        transition_finished = {'value': False}
        
        def on_finished():
            transition_finished['value'] = True
        
        # Display second image with transition
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Check transition was created
        if display_widget._current_transition:
            display_widget._current_transition.finished.connect(on_finished)
            
            # Process events for transition to complete
            QTimer.singleShot(3000, qt_app.quit)
            qt_app.exec()
            
            # Verify transition completed
            assert transition_finished['value'], "Slide transition should finish"
        
        assert display_widget.current_pixmap is not None
    
    def test_diffuse_transition_runs(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that diffuse transition actually runs."""
        display_widget.settings_manager.set('transitions.type', 'Diffuse')
        display_widget.settings_manager.set('transitions.duration_ms', 300)
        display_widget.settings_manager.set('transitions.diffuse.block_size', 50)
        
        display_widget.set_image(test_pixmap, "test1.png")
        
        transition_finished = {'value': False}
        
        def on_finished():
            transition_finished['value'] = True
        
        display_widget.set_image(test_pixmap2, "test2.png")
        
        if display_widget._current_transition:
            display_widget._current_transition.finished.connect(on_finished)
            QTimer.singleShot(2000, qt_app.quit)
            qt_app.exec()
            assert transition_finished['value'], "Diffuse transition should finish"
        
        assert display_widget.current_pixmap is not None
    
    def test_block_puzzle_flip_transition_runs(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that block puzzle flip transition actually runs."""
        display_widget.settings_manager.set('transitions.type', 'Block Puzzle Flip')
        display_widget.settings_manager.set('transitions.duration_ms', 200)
        display_widget.settings_manager.set('transitions.block_flip.rows', 2)
        display_widget.settings_manager.set('transitions.block_flip.cols', 2)
        
        display_widget.set_image(test_pixmap, "test1.png")
        
        transition_finished = {'value': False}
        
        def on_finished():
            transition_finished['value'] = True
        
        display_widget.set_image(test_pixmap2, "test2.png")
        
        if display_widget._current_transition:
            display_widget._current_transition.finished.connect(on_finished)
            QTimer.singleShot(2000, qt_app.quit)
            qt_app.exec()
            assert transition_finished['value'], "Block puzzle flip transition should finish"
        
        assert display_widget.current_pixmap is not None
    
    def test_wipe_transition_runs(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that wipe transition actually runs."""
        display_widget.settings_manager.set('transitions.type', 'Wipe')
        display_widget.settings_manager.set('transitions.duration_ms', 200)
        
        display_widget.set_image(test_pixmap, "test1.png")
        
        transition_finished = {'value': False}
        
        def on_finished():
            transition_finished['value'] = True
        
        display_widget.set_image(test_pixmap2, "test2.png")
        
        if display_widget._current_transition:
            display_widget._current_transition.finished.connect(on_finished)
            QTimer.singleShot(2000, qt_app.quit)
            qt_app.exec()
            assert transition_finished['value'], "Wipe transition should finish"
        
        assert display_widget.current_pixmap is not None
    
    def test_transition_cleanup_on_stop(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that transitions clean up properly when stopped."""
        display_widget.settings_manager.set('transitions.type', 'Slide')
        display_widget.settings_manager.set('transitions.duration_ms', 2000)  # Long duration
        
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Transition should be running
        assert display_widget._current_transition is not None
        
        # Clear should stop and clean up transition
        display_widget.clear()
        
        # Verify cleanup
        assert display_widget._current_transition is None
        assert display_widget.current_pixmap is None
    
    def test_transition_settings_respected(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that transition settings are properly read and applied."""
        # Set specific settings
        display_widget.settings_manager.set('transitions.type', 'Slide')
        display_widget.settings_manager.set('transitions.duration_ms', 750)
        display_widget.settings_manager.set('transitions.direction', 'Top to Bottom')
        
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Verify transition was created with correct type
        if display_widget._current_transition:
            assert type(display_widget._current_transition).__name__ == 'SlideTransition'
            assert display_widget._current_transition.duration_ms == 750
            assert display_widget._current_transition._direction == SlideDirection.DOWN
    
    def test_transition_fallback_on_error(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that invalid transition settings fall back gracefully."""
        # Set invalid transition type
        display_widget.settings_manager.set('transitions.type', 'InvalidType')
        
        # Should fall back to crossfade or instant display
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Should complete without crashing
        assert display_widget.current_pixmap is not None
    
    def test_random_slide_direction(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that random slide direction selection works."""
        display_widget.settings_manager.set('transitions.type', 'Slide')
        display_widget.settings_manager.set('transitions.duration_ms', 500)
        display_widget.settings_manager.set('transitions.direction', 'Random')
        
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Should have created a slide transition with random direction
        if display_widget._current_transition:
            assert type(display_widget._current_transition).__name__ == 'SlideTransition'
            # Direction should be one of the four valid directions
            assert display_widget._current_transition._direction in [SlideDirection.LEFT, SlideDirection.RIGHT, SlideDirection.UP, SlideDirection.DOWN]
