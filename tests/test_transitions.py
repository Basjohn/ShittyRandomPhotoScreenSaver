"""Tests for transition system."""
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from transitions.base_transition import BaseTransition, TransitionState
from transitions.crossfade_transition import CrossfadeTransition


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def test_widget(qapp):
    """Create test widget."""
    widget = QWidget()
    widget.resize(400, 300)
    yield widget
    widget.deleteLater()


@pytest.fixture
def test_pixmap():
    """Create test pixmap."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.red)
    return pixmap


@pytest.fixture
def test_pixmap2():
    """Create second test pixmap."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.blue)
    return pixmap


def test_transition_state_enum():
    """Test TransitionState enum."""
    assert TransitionState.IDLE.value == "idle"
    assert TransitionState.RUNNING.value == "running"
    assert TransitionState.PAUSED.value == "paused"
    assert TransitionState.FINISHED.value == "finished"
    assert TransitionState.CANCELLED.value == "cancelled"


def test_crossfade_creation():
    """Test crossfade transition creation."""
    transition = CrossfadeTransition(duration_ms=500)
    
    assert transition is not None
    assert transition.get_duration() == 500
    assert transition.get_state() == TransitionState.IDLE
    assert transition.is_running() is False


def test_crossfade_duration():
    """Test setting duration."""
    transition = CrossfadeTransition(duration_ms=1000)
    
    assert transition.get_duration() == 1000
    
    transition.set_duration(2000)
    assert transition.get_duration() == 2000
    
    # Invalid duration should fall back to 1000ms
    transition.set_duration(-100)
    assert transition.get_duration() == 1000


def test_crossfade_start_with_no_old_image(qapp, test_widget, test_pixmap, qtbot):
    """Test crossfade with no old image (first image)."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # Connect signal spy
    with qtbot.waitSignal(transition.finished, timeout=1000):
        result = transition.start(None, test_pixmap, test_widget)
        assert result is True


def test_crossfade_start_with_images(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test crossfade between two images."""
    transition = CrossfadeTransition(duration_ms=200)
    
    result = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result is True
    assert transition.is_running() is True


def test_crossfade_signals(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test transition signals are emitted."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # Track signals
    started_called = []
    finished_called = []
    progress_values = []
    
    transition.started.connect(lambda: started_called.append(True))
    transition.finished.connect(lambda: finished_called.append(True))
    transition.progress.connect(lambda p: progress_values.append(p))
    
    # Start transition
    result = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result is True
    
    # Wait for finish (increased timeout for timer-based animation)
    with qtbot.waitSignal(transition.finished, timeout=3000):
        pass
    
    # Verify signals
    assert len(started_called) >= 1
    assert len(finished_called) >= 1
    assert len(progress_values) > 0
    assert progress_values[0] >= 0.0
    assert progress_values[-1] >= 0.99  # Allow for float rounding


def test_crossfade_progress_range(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test progress values are in valid range."""
    transition = CrossfadeTransition(duration_ms=100)
    
    progress_values = []
    transition.progress.connect(lambda p: progress_values.append(p))
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    
    with qtbot.waitSignal(transition.finished, timeout=3000):
        pass
    
    # All progress values should be between 0.0 and 1.0
    for progress in progress_values:
        assert 0.0 <= progress <= 1.01  # Allow small rounding


def test_crossfade_stop(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test stopping transition."""
    transition = CrossfadeTransition(duration_ms=1000)
    
    # Start transition
    result = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result is True
    assert transition.is_running() is True
    
    # Let it run a bit
    qtbot.wait(50)
    
    # Stop transition
    transition.stop()
    
    # Verify stopped
    assert transition.is_running() is False
    assert transition.get_state() == TransitionState.CANCELLED


def test_crossfade_cleanup(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test transition cleanup."""
    transition = CrossfadeTransition(duration_ms=100)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    transition.stop()
    transition.cleanup()
    
    # State should be idle or cancelled
    assert transition.get_state() in [TransitionState.IDLE, TransitionState.CANCELLED]


def test_crossfade_invalid_pixmap(qapp, test_widget):
    """Test transition with invalid pixmap."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # Create null pixmap
    null_pixmap = QPixmap()
    
    result = transition.start(None, null_pixmap, test_widget)
    assert result is False


def test_crossfade_already_running(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test starting transition when already running."""
    transition = CrossfadeTransition(duration_ms=1000)
    
    # Start first transition
    result1 = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result1 is True
    
    # Let it start
    qtbot.wait(10)
    
    # Try to start second transition while first is running
    result2 = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result2 is False  # Should fail
    
    # Clean up
    transition.stop()
    transition.cleanup()


def test_crossfade_easing_curves(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test different easing curves."""
    easing_curves = ['Linear', 'InOutQuad', 'InOutCubic', 'InOutSine']
    
    for easing in easing_curves:
        transition = CrossfadeTransition(duration_ms=100, easing=easing)
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True
        
        with qtbot.waitSignal(transition.finished, timeout=3000):
            pass
        
        transition.cleanup()
        qtbot.wait(10)  # Small delay between tests


def test_crossfade_set_easing(qapp):
    """Test setting easing curve."""
    transition = CrossfadeTransition(duration_ms=100)
    
    transition.set_easing('OutQuad')
    assert transition._easing == 'OutQuad'
    
    transition.set_easing('InCubic')
    assert transition._easing == 'InCubic'


def test_crossfade_repr():
    """Test transition string representation."""
    transition = CrossfadeTransition(duration_ms=500)
    
    repr_str = repr(transition)
    assert 'CrossfadeTransition' in repr_str
    assert '500ms' in repr_str
    assert 'idle' in repr_str


def test_crossfade_state_transitions(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test transition state changes."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # Initial state
    assert transition.get_state() == TransitionState.IDLE
    
    # Start transition
    transition.start(test_pixmap, test_pixmap2, test_widget)
    qtbot.wait(10)
    assert transition.get_state() == TransitionState.RUNNING
    
    # Wait for completion
    with qtbot.waitSignal(transition.finished, timeout=3000):
        pass
    
    # Final state
    assert transition.get_state() == TransitionState.FINISHED


def test_crossfade_multiple_transitions(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test running multiple transitions sequentially."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # First transition
    with qtbot.waitSignal(transition.finished, timeout=1000):
        transition.start(None, test_pixmap, test_widget)
    
    # Second transition
    transition2 = CrossfadeTransition(duration_ms=50)
    with qtbot.waitSignal(transition2.finished, timeout=1000):
        transition2.start(test_pixmap, test_pixmap2, test_widget)
