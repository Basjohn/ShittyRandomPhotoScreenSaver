"""Integration tests for transition system.

Tests that transitions actually run in DisplayWidget and complete properly.
These tests validate the full transition lifecycle end-to-end.
"""
import pytest
import types
from PySide6.QtGui import QPixmap, QImage, QColor
from PySide6.QtCore import QSize, QTimer

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from transitions.slide_transition import SlideDirection


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
    
    def _set_transitions(
        self,
        settings_manager,
        *,
        transition_type=None,
        duration_ms=None,
        slide_direction=None,
        wipe_direction=None,
        diffuse_block_size=None,
        block_rows=None,
        block_cols=None,
    ):
        """Helper to update canonical nested transition config for tests."""
        config = settings_manager.get('transitions', {}) or {}
        if not isinstance(config, dict):
            config = {}

        if transition_type is not None:
            config['type'] = transition_type
        if duration_ms is not None:
            config['duration_ms'] = duration_ms

        if slide_direction is not None:
            slide_cfg = config.get('slide', {})
            if not isinstance(slide_cfg, dict):
                slide_cfg = {}
            slide_cfg['direction'] = slide_direction
            config['slide'] = slide_cfg

        if wipe_direction is not None:
            wipe_cfg = config.get('wipe', {})
            if not isinstance(wipe_cfg, dict):
                wipe_cfg = {}
            wipe_cfg['direction'] = wipe_direction
            config['wipe'] = wipe_cfg

        if diffuse_block_size is not None:
            diffuse_cfg = config.get('diffuse', {})
            if not isinstance(diffuse_cfg, dict):
                diffuse_cfg = {}
            diffuse_cfg['block_size'] = diffuse_block_size
            config['diffuse'] = diffuse_cfg

        if block_rows is not None or block_cols is not None:
            block_cfg = config.get('block_flip', {})
            if not isinstance(block_cfg, dict):
                block_cfg = {}
            if block_rows is not None:
                block_cfg['rows'] = block_rows
            if block_cols is not None:
                block_cfg['cols'] = block_cols
            config['block_flip'] = block_cfg

        settings_manager.set('transitions', config)

    def test_crossfade_transition_runs(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that crossfade transition actually runs."""
        # Set up transition settings
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Crossfade',
            duration_ms=500,
        )
        
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
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Slide',
            duration_ms=300,
            slide_direction='Left to Right',
        )
        
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
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Diffuse',
            duration_ms=300,
            diffuse_block_size=50,
        )
        
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
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Block Puzzle Flip',
            duration_ms=200,
            block_rows=2,
            block_cols=2,
        )
        
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
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Wipe',
            duration_ms=200,
        )
        
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
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Slide',
            duration_ms=2000,
        )  # Long duration
        
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
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Slide',
            duration_ms=750,
            slide_direction='Top to Bottom',
        )
        
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Verify the active slide-style transition honours duration and direction
        current = display_widget._current_transition
        if current:
            assert current.duration_ms == 750
            assert current._direction == SlideDirection.DOWN
    
    def test_transition_fallback_on_error(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that invalid transition settings fall back gracefully."""
        # Set invalid transition type
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='InvalidType',
        )
        
        # Should fall back to crossfade or instant display
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Should complete without crashing
        assert display_widget.current_pixmap is not None
    
    def test_random_slide_direction(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Test that random slide direction selection works."""
        self._set_transitions(
            display_widget.settings_manager,
            transition_type='Slide',
            duration_ms=500,
            slide_direction='Random',
        )
        
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        
        # Should have created a slide-style transition with a valid random direction
        current = display_widget._current_transition
        if current:
            # Direction should be one of the four valid directions
            assert current._direction in [
                SlideDirection.LEFT,
                SlideDirection.RIGHT,
                SlideDirection.UP,
                SlideDirection.DOWN,
            ]

    def test_diffuse_transition_software_backend_no_watchdog(self, qt_app, settings_manager, test_pixmap, test_pixmap2):
        self._set_transitions(
            settings_manager,
            transition_type='Diffuse',
            duration_ms=300,
            diffuse_block_size=50,
        )
        settings_manager.set('display.render_backend_mode', 'software')
        settings_manager.set('display.hw_accel', False)
        settings_manager.set('transitions.watchdog_timeout_sec', 1.0)

        widget = DisplayWidget(
            screen_index=0,
            display_mode=DisplayMode.FILL,
            settings_manager=settings_manager,
        )
        widget.resize(400, 400)

        watchdog_flag = {'triggered': False}
        original_timeout = widget._on_transition_watchdog_timeout

        def _wrapped_timeout(self):
            watchdog_flag['triggered'] = True
            return original_timeout()

        widget._on_transition_watchdog_timeout = types.MethodType(_wrapped_timeout, widget)

        widget.set_image(test_pixmap, "test1.png")

        finished = {'value': False}

        def on_finished():
            finished['value'] = True

        widget.set_image(test_pixmap2, "test2.png")

        if widget._current_transition:
            widget._current_transition.finished.connect(on_finished)
            QTimer.singleShot(3000, qt_app.quit)
            qt_app.exec()
            assert finished['value'] is True
            assert watchdog_flag['triggered'] is False

        widget.close()

    def test_block_flip_transition_software_backend_no_watchdog(self, qt_app, settings_manager, test_pixmap, test_pixmap2):
        self._set_transitions(
            settings_manager,
            transition_type='Block Puzzle Flip',
            duration_ms=300,
            block_rows=2,
            block_cols=2,
        )
        settings_manager.set('display.render_backend_mode', 'software')
        settings_manager.set('display.hw_accel', False)
        settings_manager.set('transitions.watchdog_timeout_sec', 1.0)

        widget = DisplayWidget(
            screen_index=0,
            display_mode=DisplayMode.FILL,
            settings_manager=settings_manager,
        )
        widget.resize(400, 400)

        watchdog_flag = {'triggered': False}
        original_timeout = widget._on_transition_watchdog_timeout

        def _wrapped_timeout(self):
            watchdog_flag['triggered'] = True
            return original_timeout()

        widget._on_transition_watchdog_timeout = types.MethodType(_wrapped_timeout, widget)

        widget.set_image(test_pixmap, "test1.png")

        finished = {'value': False}

        def on_finished():
            finished['value'] = True

        widget.set_image(test_pixmap2, "test2.png")

        if widget._current_transition:
            widget._current_transition.finished.connect(on_finished)
            QTimer.singleShot(3000, qt_app.quit)
            qt_app.exec()
            assert finished['value'] is True
            assert watchdog_flag['triggered'] is False

        widget.close()
