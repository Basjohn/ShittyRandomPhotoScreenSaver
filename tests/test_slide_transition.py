"""Tests for slide transition."""
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from transitions.slide_transition import SlideTransition, SlideDirection


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


def test_slide_direction_enum():
    """Test SlideDirection enum."""
    assert SlideDirection.LEFT.value == "left"
    assert SlideDirection.RIGHT.value == "right"
    assert SlideDirection.UP.value == "up"
    assert SlideDirection.DOWN.value == "down"


def test_slide_creation():
    """Test slide transition creation."""
    transition = SlideTransition(duration_ms=500, direction=SlideDirection.LEFT)
    
    assert transition is not None
    assert transition.get_duration() == 500
    assert transition._direction == SlideDirection.LEFT


def test_slide_all_directions(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test slide in all directions."""
    directions = [SlideDirection.LEFT, SlideDirection.RIGHT, SlideDirection.UP, SlideDirection.DOWN]
    
    for direction in directions:
        transition = SlideTransition(duration_ms=100, direction=direction)
        
        with qtbot.waitSignal(transition.finished, timeout=1000):
            result = transition.start(test_pixmap, test_pixmap2, test_widget)
            assert result is True
        
        transition.cleanup()


def test_slide_start_no_old_image(qapp, test_widget, test_pixmap, qtbot):
    """Test slide with no old image."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    with qtbot.waitSignal(transition.finished, timeout=1000):
        result = transition.start(None, test_pixmap, test_widget)
        assert result is True


def test_slide_signals(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test slide signals."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    started_called = []
    finished_called = []
    progress_values = []
    
    transition.started.connect(lambda: started_called.append(True))
    transition.finished.connect(lambda: finished_called.append(True))
    transition.progress.connect(lambda p: progress_values.append(p))
    
    with qtbot.waitSignal(transition.finished, timeout=1000):
        transition.start(test_pixmap, test_pixmap2, test_widget)
    
    assert len(started_called) == 1
    assert len(finished_called) == 1
    assert len(progress_values) > 0


def test_slide_progress_range(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test progress values are in valid range."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    progress_values = []
    transition.progress.connect(lambda p: progress_values.append(p))
    
    with qtbot.waitSignal(transition.finished, timeout=1000):
        transition.start(test_pixmap, test_pixmap2, test_widget)
    
    for progress in progress_values:
        assert 0.0 <= progress <= 1.0


def test_slide_stop(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test stopping slide."""
    transition = SlideTransition(duration_ms=1000, direction=SlideDirection.LEFT)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    assert transition.is_running() is True
    
    transition.stop()
    assert transition.get_state().value in ['cancelled', 'finished']


def test_slide_cleanup(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test slide cleanup."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    transition.stop()
    transition.cleanup()
    
    assert transition._old_label is None
    assert transition._new_label is None
    assert transition._old_animation is None
    assert transition._new_animation is None


def test_slide_invalid_pixmap(qapp, test_widget):
    """Test slide with invalid pixmap."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    null_pixmap = QPixmap()
    result = transition.start(None, null_pixmap, test_widget)
    assert result is False


def test_slide_already_running(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test starting slide when already running."""
    transition = SlideTransition(duration_ms=1000, direction=SlideDirection.LEFT)
    
    result1 = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result1 is True
    assert transition.is_running() is True
    
    result2 = transition.start(test_pixmap2, test_pixmap, test_widget)
    assert result2 is False
    
    transition.cleanup()


def test_slide_set_direction(qapp):
    """Test setting slide direction."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    assert transition._direction == SlideDirection.LEFT
    
    transition.set_direction(SlideDirection.RIGHT)
    assert transition._direction == SlideDirection.RIGHT


def test_slide_easing_curves(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test different easing curves."""
    easing_curves = ['Linear', 'InOutQuad', 'InOutCubic']
    
    for easing in easing_curves:
        transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT, easing=easing)
        
        with qtbot.waitSignal(transition.finished, timeout=1000):
            result = transition.start(test_pixmap, test_pixmap2, test_widget)
            assert result is True
        
        transition.cleanup()


def test_slide_position_calculation():
    """Test position calculation for different directions."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    width, height = 400, 300
    
    # Test LEFT
    transition.set_direction(SlideDirection.LEFT)
    old_start, old_end, new_start, new_end = transition._calculate_positions(width, height)
    assert old_start.x() == 0 and old_end.x() == -width
    assert new_start.x() == width and new_end.x() == 0
    
    # Test RIGHT
    transition.set_direction(SlideDirection.RIGHT)
    old_start, old_end, new_start, new_end = transition._calculate_positions(width, height)
    assert old_start.x() == 0 and old_end.x() == width
    assert new_start.x() == -width and new_end.x() == 0
    
    # Test UP
    transition.set_direction(SlideDirection.UP)
    old_start, old_end, new_start, new_end = transition._calculate_positions(width, height)
    assert old_start.y() == 0 and old_end.y() == -height
    assert new_start.y() == height and new_end.y() == 0
    
    # Test DOWN
    transition.set_direction(SlideDirection.DOWN)
    old_start, old_end, new_start, new_end = transition._calculate_positions(width, height)
    assert old_start.y() == 0 and old_end.y() == height
    assert new_start.y() == -height and new_end.y() == 0
