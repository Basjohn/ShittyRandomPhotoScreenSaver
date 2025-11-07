"""Tests for block puzzle flip transition (mask-based)."""
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from transitions.block_puzzle_flip_transition import BlockPuzzleFlipTransition


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def test_widget(qapp):
    widget = QWidget()
    widget.resize(400, 300)
    yield widget
    widget.deleteLater()
    qapp.processEvents()


@pytest.fixture
def test_pixmap():
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.red)
    return pixmap


@pytest.fixture
def test_pixmap2():
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.blue)
    return pixmap


def test_block_puzzle_creation():
    t = BlockPuzzleFlipTransition(duration_ms=3000, grid_rows=4, grid_cols=6, flip_duration_ms=500)
    assert t is not None
    assert t.get_duration() == 3000
    assert t._grid_rows == 4
    assert t._grid_cols == 6


def test_block_puzzle_runs_and_labels(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    t = BlockPuzzleFlipTransition(duration_ms=300, grid_rows=3, grid_cols=4, flip_duration_ms=80)
    started = []
    t.started.connect(lambda: started.append(True))
    with qtbot.waitSignal(t.finished, timeout=4000):
        assert t.start(test_pixmap, test_pixmap2, test_widget) is True
        # Structural assertions
        assert hasattr(t, "_new_label") and t._new_label is not None
        assert hasattr(t, "_old_label") and t._old_label is not None
        assert t._new_label.scaledContents() is False
        assert t._old_label.scaledContents() is False
        # Geometry matches widget
        assert t._new_label.width() == test_widget.width()
        assert t._new_label.height() == test_widget.height()

    assert len(started) == 1


def test_block_puzzle_cleanup(qapp, test_widget, test_pixmap, test_pixmap2):
    t = BlockPuzzleFlipTransition(duration_ms=200, grid_rows=2, grid_cols=2)
    t.start(test_pixmap, test_pixmap2, test_widget)
    t.stop()
    t.cleanup()
    # Internal handles should be cleared
    assert t._blocks == []


def test_block_puzzle_invalid_pixmap(qapp, test_widget):
    t = BlockPuzzleFlipTransition(duration_ms=100)
    null_pix = QPixmap()
    assert t.start(None, null_pix, test_widget) is False


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




def test_block_puzzle_small_widget(qapp, test_widget, test_pixmap, test_pixmap2, qtbot):
    """Test block puzzle with small widget."""
    test_widget.resize(200, 150)
    
    transition = BlockPuzzleFlipTransition(duration_ms=1000, grid_rows=2, grid_cols=3)
    
    with qtbot.waitSignal(transition.finished, timeout=5000):
        result = transition.start(test_pixmap, test_pixmap2, test_widget)
        assert result is True
