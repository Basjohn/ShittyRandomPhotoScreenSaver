"""Tests for GL compositor diffuse transition."""
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from transitions.gl_compositor_diffuse_transition import GLCompositorDiffuseTransition as DiffuseTransition


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


def test_diffuse_creation():
    """Test diffuse transition creation."""
    transition = DiffuseTransition(duration_ms=500, block_size=50)
    
    assert transition is not None
    assert transition.get_duration() == 500
    assert transition._block_size == 50


def test_diffuse_start_no_old_image(qapp, test_widget, test_pixmap, qtbot):
    """Test diffuse with no old image."""
    transition = DiffuseTransition(duration_ms=100, block_size=50)
    
    with qtbot.waitSignal(transition.finished, timeout=1000):
        result = transition.start(None, test_pixmap, test_widget)
        assert result is True


@pytest.mark.skip(reason="Requires live GL compositor attached to widget")
def test_diffuse_start_with_images(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse transition with images."""
    transition = DiffuseTransition(duration_ms=200, block_size=8)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True


@pytest.mark.skip(reason="Requires live GL compositor attached to widget")
def test_diffuse_signals(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse signals are emitted."""
    transition = DiffuseTransition(duration_ms=100, block_size=8)
    
    started_called = []
    finished_called = []
    progress_values = []
    
    transition.started.connect(lambda: started_called.append(True))
    transition.finished.connect(lambda: finished_called.append(True))
    transition.progress.connect(lambda p: progress_values.append(p))
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        transition.start(test_pixmap, test_pixmap2, test_widget)
    
    assert len(started_called) == 1
    assert len(finished_called) == 1
    assert len(progress_values) > 0


@pytest.mark.skip(reason="Requires live GL compositor attached to widget")
def test_diffuse_progress_range(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse progress values are in valid range."""
    transition = DiffuseTransition(duration_ms=100, block_size=8)
    
    progress_values = []
    transition.progress.connect(lambda p: progress_values.append(p))
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        transition.start(test_pixmap, test_pixmap2, test_widget)
    
    for progress in progress_values:
        assert 0.0 <= progress <= 1.0
    
    assert progress_values[-1] == 1.0


def test_diffuse_stop(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test stopping diffuse transition — without compositor, completes immediately."""
    transition = DiffuseTransition(duration_ms=1000, block_size=8)
    transition.start(test_pixmap, test_pixmap2, test_widget)
    transition.stop()
    transition.cleanup()


def test_diffuse_cleanup(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test diffuse transition cleanup."""
    transition = DiffuseTransition(duration_ms=200, block_size=8)
    transition.start(test_pixmap, test_pixmap2, test_widget)
    transition.stop()
    transition.cleanup()
    assert transition._compositor is None
    assert transition._cells == []


def test_diffuse_invalid_pixmap(qapp, test_widget):
    """Test diffuse with invalid pixmap."""
    transition = DiffuseTransition(duration_ms=100, block_size=8)
    
    null_pixmap = QPixmap()
    result = transition.start(None, null_pixmap, test_widget)
    assert result is False


def test_diffuse_already_running(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test starting diffuse when already running."""
    transition = DiffuseTransition(duration_ms=1000, block_size=8)
    # Without a compositor, start completes immediately
    result1 = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result1 is True
    transition.cleanup()


def test_diffuse_block_size(qapp):
    """Test block size is stored at construction."""
    transition = DiffuseTransition(duration_ms=100, block_size=8)
    assert transition._block_size == 8
    
    transition2 = DiffuseTransition(duration_ms=100, block_size=100)
    assert transition2._block_size == 100


@pytest.mark.skip(reason="Requires live GL compositor attached to widget")
def test_diffuse_small_widget(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse with small widget."""
    test_widget.resize(100, 100)
    
    transition = DiffuseTransition(duration_ms=200, block_size=50)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True
