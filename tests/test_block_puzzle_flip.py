"""Tests for block puzzle flip transition."""
import pytest
import time
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QRect
from transitions.block_puzzle_flip_transition import BlockPuzzleFlipTransition, FlipBlock


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Process events to allow cleanup
    app.processEvents()


@pytest.fixture
def test_widget(qapp):
    """Create test widget."""
    widget = QWidget()
    widget.resize(400, 300)
    yield widget
    widget.deleteLater()
    qapp.processEvents()


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


def test_flip_block_creation(qapp):
    """Test FlipBlock creation."""
    old_pixmap = QPixmap(100, 100)
    new_pixmap = QPixmap(100, 100)
    old_pixmap.fill(Qt.GlobalColor.red)
    new_pixmap.fill(Qt.GlobalColor.blue)
    
    rect = QRect(0, 0, 50, 50)
    block = FlipBlock(rect, old_pixmap, new_pixmap)
    
    assert block.rect == rect
    assert block.flip_progress == 0.0
    assert block.is_flipping is False
    assert block.is_complete is False


def test_flip_block_progress(qapp):
    """Test FlipBlock flip progress."""
    old_pixmap = QPixmap(100, 100)
    new_pixmap = QPixmap(100, 100)
    old_pixmap.fill(Qt.GlobalColor.red)
    new_pixmap.fill(Qt.GlobalColor.blue)
    
    rect = QRect(0, 0, 50, 50)
    block = FlipBlock(rect, old_pixmap, new_pixmap)
    
    # Test progress stages
    block.flip_progress = 0.0
    pixmap = block.get_current_pixmap()
    assert not pixmap.isNull()
    
    block.flip_progress = 0.25
    pixmap = block.get_current_pixmap()
    assert not pixmap.isNull()
    
    block.flip_progress = 0.5
    pixmap = block.get_current_pixmap()
    assert not pixmap.isNull()
    
    block.flip_progress = 0.75
    pixmap = block.get_current_pixmap()
    assert not pixmap.isNull()
    
    block.flip_progress = 1.0
    pixmap = block.get_current_pixmap()
    assert not pixmap.isNull()


def test_block_puzzle_creation():
    """Test block puzzle flip creation."""
    transition = BlockPuzzleFlipTransition(
        duration_ms=3000,
        grid_rows=4,
        grid_cols=6,
        flip_duration_ms=500
    )
    
    assert transition is not None
    assert transition.get_duration() == 3000
    assert transition._grid_rows == 4
    assert transition._grid_cols == 6
    assert transition._flip_duration_ms == 500


def test_block_puzzle_start_no_old_image(qapp, test_widget, test_pixmap, qtbot):
    """Test block puzzle with no old image."""
    transition = BlockPuzzleFlipTransition(duration_ms=500)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        result = transition.start(None, test_pixmap, test_widget)
        assert result is True


def test_block_puzzle_start_with_images(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test block puzzle between two images."""
    transition = BlockPuzzleFlipTransition(duration_ms=500, grid_rows=2, grid_cols=2, flip_duration_ms=100)
    
    with qtbot.waitSignal(transition.finished, timeout=3000):
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True
    
    # Allow cleanup
    transition.cleanup()
    qapp.processEvents()


def test_block_puzzle_signals(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test block puzzle signals."""
    transition = BlockPuzzleFlipTransition(duration_ms=500, grid_rows=2, grid_cols=2, flip_duration_ms=100)
    
    started_called = []
    finished_called = []
    progress_values = []
    
    transition.started.connect(lambda: started_called.append(True))
    transition.finished.connect(lambda: finished_called.append(True))
    transition.progress.connect(lambda p: progress_values.append(p))
    
    with qtbot.waitSignal(transition.finished, timeout=3000):
        transition.start(test_pixmap, test_pixmap2, test_widget)
    
    assert len(started_called) == 1
    assert len(finished_called) == 1
    assert len(progress_values) > 0
    
    transition.cleanup()
    qapp.processEvents()


def test_block_puzzle_progress_range(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test progress values are in valid range."""
    transition = BlockPuzzleFlipTransition(duration_ms=1000, grid_rows=2, grid_cols=2)
    
    progress_values = []
    transition.progress.connect(lambda p: progress_values.append(p))
    
    with qtbot.waitSignal(transition.finished, timeout=5000):
        transition.start(test_pixmap, test_pixmap2, test_widget)
    
    for progress in progress_values:
        assert 0.0 <= progress <= 1.0
    
    # Should end at 1.0
    assert progress_values[-1] == 1.0


def test_block_puzzle_stop(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test stopping block puzzle."""
    transition = BlockPuzzleFlipTransition(duration_ms=5000, grid_rows=4, grid_cols=6)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    assert transition.is_running() is True
    
    transition.stop()
    assert transition.get_state().value in ['cancelled', 'finished']


def test_block_puzzle_cleanup(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test block puzzle cleanup."""
    transition = BlockPuzzleFlipTransition(duration_ms=1000, grid_rows=2, grid_cols=2)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    transition.stop()
    transition.cleanup()
    
    assert transition._timer is None
    assert transition._flip_timer is None
    assert transition._display_label is None
    assert len(transition._blocks) == 0


def test_block_puzzle_invalid_pixmap(qapp, test_widget):
    """Test block puzzle with invalid pixmap."""
    transition = BlockPuzzleFlipTransition(duration_ms=1000)
    
    null_pixmap = QPixmap()
    result = transition.start(None, null_pixmap, test_widget)
    assert result is False


def test_block_puzzle_already_running(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test starting block puzzle when already running."""
    transition = BlockPuzzleFlipTransition(duration_ms=5000, grid_rows=2, grid_cols=2)
    
    result1 = transition.start(test_pixmap, test_pixmap2, test_widget)
    assert result1 is True
    assert transition.is_running() is True
    
    result2 = transition.start(test_pixmap2, test_pixmap, test_widget)
    assert result2 is False
    
    transition.cleanup()


def test_block_puzzle_grid_creation(qapp, test_pixmap, test_pixmap2):
    """Test block grid creation."""
    transition = BlockPuzzleFlipTransition(duration_ms=1000, grid_rows=3, grid_cols=4)
    
    transition._old_pixmap = test_pixmap
    transition._new_pixmap = test_pixmap2
    transition._create_block_grid(600, 400)
    
    # Should have 3 rows x 4 cols = 12 blocks
    assert len(transition._blocks) == 12
    
    # First block should start at 0,0
    first_block = transition._blocks[0]
    assert first_block.rect.x() == 0
    assert first_block.rect.y() == 0


def test_block_puzzle_different_grid_sizes(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test different grid sizes."""
    grid_sizes = [(2, 2), (3, 4), (4, 6)]
    
    for rows, cols in grid_sizes:
        transition = BlockPuzzleFlipTransition(
            duration_ms=1000,
            grid_rows=rows,
            grid_cols=cols
        )
        
        with qtbot.waitSignal(transition.finished, timeout=5000):
            result = transition.start(test_pixmap, test_pixmap2, test_widget)
            assert result is True
        
        transition.cleanup()


def test_block_puzzle_set_grid_size():
    """Test setting grid size."""
    transition = BlockPuzzleFlipTransition(duration_ms=1000, grid_rows=4, grid_cols=6)
    
    assert transition._grid_rows == 4
    assert transition._grid_cols == 6
    
    transition.set_grid_size(8, 10)
    assert transition._grid_rows == 8
    assert transition._grid_cols == 10
    
    # Invalid size should fall back
    transition.set_grid_size(-1, 5)
    assert transition._grid_rows == 4
    assert transition._grid_cols == 6


def test_block_puzzle_set_flip_duration():
    """Test setting flip duration."""
    transition = BlockPuzzleFlipTransition(duration_ms=1000, flip_duration_ms=500)
    
    assert transition._flip_duration_ms == 500
    
    transition.set_flip_duration(1000)
    assert transition._flip_duration_ms == 1000
    
    # Invalid duration should fall back
    transition.set_flip_duration(-100)
    assert transition._flip_duration_ms == 500


def test_block_puzzle_randomization(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test that blocks flip in random order."""
    transition = BlockPuzzleFlipTransition(duration_ms=3000, grid_rows=3, grid_cols=4)
    
    # Start transition
    transition.start(test_pixmap, test_pixmap2, test_widget)
    
    # Flip order should be shuffled (not sequential)
    total_blocks = 12
    assert len(transition._flip_order) == total_blocks
    
    # Check if order is non-sequential
    is_sequential = all(
        transition._flip_order[i] == i 
        for i in range(total_blocks)
    )
    
    # Very unlikely to be sequential after shuffle
    # (This test might rarely fail due to random chance, but probability is 1/12!)
    assert is_sequential is False
    
    transition.cleanup()


def test_flip_block_scale_horizontal(qapp):
    """Test horizontal scaling in FlipBlock."""
    old_pixmap = QPixmap(100, 100)
    new_pixmap = QPixmap(100, 100)
    old_pixmap.fill(Qt.GlobalColor.red)
    new_pixmap.fill(Qt.GlobalColor.blue)
    
    rect = QRect(0, 0, 100, 100)
    block = FlipBlock(rect, old_pixmap, new_pixmap)
    
    # Test different scale factors
    scaled = block._scale_horizontal(old_pixmap, 0.5)
    assert not scaled.isNull()
    assert scaled.width() == 100
    assert scaled.height() == 100
    
    scaled = block._scale_horizontal(old_pixmap, 0.0)
    assert not scaled.isNull()
    
    scaled = block._scale_horizontal(old_pixmap, 1.0)
    assert not scaled.isNull()


def test_block_puzzle_small_widget(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test block puzzle with small widget."""
    test_widget.resize(200, 150)
    
    transition = BlockPuzzleFlipTransition(duration_ms=1000, grid_rows=2, grid_cols=3)
    
    with qtbot.waitSignal(transition.finished, timeout=5000):
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True
