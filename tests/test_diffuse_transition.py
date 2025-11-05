"""Tests for diffuse transition."""
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from transitions.diffuse_transition import DiffuseTransition


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


def test_diffuse_start_with_images(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse between two images."""
    transition = DiffuseTransition(duration_ms=200, block_size=50)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True


def test_diffuse_signals(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse signals."""
    transition = DiffuseTransition(duration_ms=200, block_size=50)
    
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


def test_diffuse_progress_range(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test progress values are in valid range."""
    transition = DiffuseTransition(duration_ms=200, block_size=50)
    
    progress_values = []
    transition.progress.connect(lambda p: progress_values.append(p))
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        transition.start(test_pixmap, test_pixmap2, test_widget)
    
    for progress in progress_values:
        assert 0.0 <= progress <= 1.0
    
    # Should end at 1.0
    assert progress_values[-1] == 1.0


def test_diffuse_stop(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test stopping diffuse."""
    transition = DiffuseTransition(duration_ms=2000, block_size=50)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    assert transition.is_running() is True
    
    transition.stop()
    assert transition.get_state().value in ['cancelled', 'finished']


def test_diffuse_cleanup(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test diffuse cleanup."""
    transition = DiffuseTransition(duration_ms=200, block_size=50)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    transition.stop()
    transition.cleanup()
    
    assert transition._display_label is None
    assert transition._timer is None
    assert len(transition._blocks) == 0


def test_diffuse_invalid_pixmap(qapp, test_widget):
    """Test diffuse with invalid pixmap."""
    transition = DiffuseTransition(duration_ms=100, block_size=50)
    
    null_pixmap = QPixmap()
    result = transition.start(None, null_pixmap, test_widget)
    assert result is False


def test_diffuse_already_running(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test starting diffuse when already running."""
    transition = DiffuseTransition(duration_ms=2000, block_size=50)
    
    result1 = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result1 is True
    assert transition.is_running() is True
    
    result2 = transition.start(test_pixmap2, test_pixmap, test_widget)
    assert result2 is False
    
    transition.cleanup()


def test_diffuse_block_grid():
    """Test block grid creation."""
    transition = DiffuseTransition(duration_ms=100, block_size=50)
    
    # Test 400x300 with 50px blocks
    blocks = transition._create_block_grid(400, 300)
    
    # Should have 8 cols x 6 rows = 48 blocks
    assert len(blocks) == 48
    
    # First block should start at 0,0
    assert blocks[0].x() == 0
    assert blocks[0].y() == 0
    assert blocks[0].width() == 50
    assert blocks[0].height() == 50
    
    # Last block should be at edge
    last_block = blocks[-1]
    assert last_block.x() == 350
    assert last_block.y() == 250


def test_diffuse_different_block_sizes(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse with different block sizes."""
    block_sizes = [25, 50, 100]
    
    for size in block_sizes:
        transition = DiffuseTransition(duration_ms=200, block_size=size)
        
        with qtbot.waitSignal(transition.finished, timeout=2000):
            result = transition.start(test_pixmap, test_pixmap2, test_widget)
            assert result is True
        
        transition.cleanup()


def test_diffuse_set_block_size():
    """Test setting block size."""
    transition = DiffuseTransition(duration_ms=100, block_size=50)
    
    assert transition._block_size == 50
    
    transition.set_block_size(100)
    assert transition._block_size == 100
    
    # Invalid size should fall back
    transition.set_block_size(-10)
    assert transition._block_size == 50


def test_diffuse_small_widget(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test diffuse with small widget."""
    test_widget.resize(100, 100)
    
    transition = DiffuseTransition(duration_ms=200, block_size=50)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True


def test_diffuse_randomization(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test that blocks are revealed in random order."""
    transition = DiffuseTransition(duration_ms=2000, block_size=50)
    
    # Start transition
    transition.start(test_pixmap, test_pixmap2, test_widget)
    
    # Blocks should be shuffled (not in original order)
    # Note: This test might rarely fail due to random chance
    if len(transition._blocks) > 5:
        # Check if first 5 blocks are in sequential order
        first_five_sequential = True
        for i in range(4):
            if transition._blocks[i].x() >= transition._blocks[i+1].x():
                first_five_sequential = False
                break
        
        # Should be shuffled (not sequential)
        assert first_five_sequential is False or len(transition._blocks) < 10
    
    transition.cleanup()
