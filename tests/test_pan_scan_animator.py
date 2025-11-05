"""Tests for pan & scan animator."""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from rendering.pan_scan_animator import PanScanAnimator, PanDirection


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_pan_direction_enum():
    """Test PanDirection enum."""
    assert PanDirection.LEFT_TO_RIGHT.value == "left_to_right"
    assert PanDirection.RIGHT_TO_LEFT.value == "right_to_left"
    assert PanDirection.TOP_TO_BOTTOM.value == "top_to_bottom"
    assert PanDirection.BOTTOM_TO_TOP.value == "bottom_to_top"
    assert PanDirection.DIAGONAL_TL_BR.value == "diagonal_tl_br"
    assert PanDirection.DIAGONAL_TR_BL.value == "diagonal_tr_bl"
    assert PanDirection.RANDOM.value == "random"


def test_animator_creation(qapp):
    """Test pan scan animator creation."""
    animator = PanScanAnimator(
        zoom_min=1.2,
        zoom_max=1.5,
        duration_ms=5000,
        fps=30
    )
    
    assert animator is not None
    assert animator._zoom_min == 1.2
    assert animator._zoom_max == 1.5
    assert animator._duration_ms == 5000
    assert animator._fps == 30


def test_animator_start(qapp, qtbot):
    """Test starting animation."""
    animator = PanScanAnimator(duration_ms=100, fps=60)
    
    frame_called = []
    animator.frame_updated.connect(lambda rect: frame_called.append(rect))
    
    animator.start(
        image_size=(1920, 1080),
        viewport_size=(800, 600),
        direction=PanDirection.LEFT_TO_RIGHT
    )
    
    assert animator.is_active() is True
    
    # Should emit at least one frame
    qtbot.wait(50)
    assert len(frame_called) > 0
    
    animator.stop()


def test_animator_signals(qapp, qtbot):
    """Test animator signals."""
    animator = PanScanAnimator(duration_ms=200, fps=60)
    
    frame_updates = []
    finished_called = []
    
    animator.frame_updated.connect(lambda rect: frame_updates.append(rect))
    animator.animation_finished.connect(lambda: finished_called.append(True))
    
    with qtbot.waitSignal(animator.animation_finished, timeout=1000):
        animator.start(
            image_size=(1920, 1080),
            viewport_size=(800, 600),
            direction=PanDirection.LEFT_TO_RIGHT
        )
    
    assert len(frame_updates) > 0
    assert len(finished_called) == 1


def test_animator_stop(qapp, qtbot):
    """Test stopping animation."""
    animator = PanScanAnimator(duration_ms=5000, fps=30)
    
    animator.start(
        image_size=(1920, 1080),
        viewport_size=(800, 600),
        direction=PanDirection.TOP_TO_BOTTOM
    )
    
    assert animator.is_active() is True
    
    animator.stop()
    assert animator.is_active() is False


def test_animator_all_directions(qapp, qtbot):
    """Test all pan directions."""
    directions = [
        PanDirection.LEFT_TO_RIGHT,
        PanDirection.RIGHT_TO_LEFT,
        PanDirection.TOP_TO_BOTTOM,
        PanDirection.BOTTOM_TO_TOP,
        PanDirection.DIAGONAL_TL_BR,
        PanDirection.DIAGONAL_TR_BL
    ]
    
    for direction in directions:
        animator = PanScanAnimator(duration_ms=100, fps=60)
        
        frame_updates = []
        animator.frame_updated.connect(lambda rect: frame_updates.append(rect))
        
        with qtbot.waitSignal(animator.animation_finished, timeout=1000):
            animator.start(
                image_size=(1920, 1080),
                viewport_size=(800, 600),
                direction=direction
            )
        
        assert len(frame_updates) > 0


def test_animator_random_direction(qapp, qtbot):
    """Test random direction selection."""
    animator = PanScanAnimator(duration_ms=100, fps=60)
    
    with qtbot.waitSignal(animator.animation_finished, timeout=1000):
        animator.start(
            image_size=(1920, 1080),
            viewport_size=(800, 600),
            direction=PanDirection.RANDOM
        )
    
    # Should have selected a non-random direction
    assert animator._direction != PanDirection.RANDOM


def test_animator_viewport_rectangles(qapp, qtbot):
    """Test that viewport rectangles are valid."""
    animator = PanScanAnimator(duration_ms=200, fps=60)
    
    frame_updates = []
    animator.frame_updated.connect(lambda rect: frame_updates.append(rect))
    
    with qtbot.waitSignal(animator.animation_finished, timeout=1000):
        animator.start(
            image_size=(1920, 1080),
            viewport_size=(800, 600),
            direction=PanDirection.LEFT_TO_RIGHT
        )
    
    # All rectangles should be valid QRectF
    for rect in frame_updates:
        assert isinstance(rect, QRectF)
        assert rect.width() > 0
        assert rect.height() > 0
        # Rectangle should be within image bounds
        assert rect.left() >= 0
        assert rect.top() >= 0
        assert rect.right() <= 1920
        assert rect.bottom() <= 1080


def test_animator_set_zoom_range(qapp):
    """Test setting zoom range."""
    animator = PanScanAnimator()
    
    animator.set_zoom_range(1.3, 1.8)
    assert animator._zoom_min == 1.3
    assert animator._zoom_max == 1.8
    
    # Invalid range should fall back
    animator.set_zoom_range(0.5, 0.8)
    assert animator._zoom_min == 1.2
    assert animator._zoom_max == 1.5


def test_animator_set_duration(qapp):
    """Test setting duration."""
    animator = PanScanAnimator()
    
    animator.set_duration(15000)
    assert animator._duration_ms == 15000
    
    # Invalid duration should fall back
    animator.set_duration(-100)
    assert animator._duration_ms == 10000


def test_animator_set_fps(qapp):
    """Test setting FPS."""
    animator = PanScanAnimator()
    
    animator.set_fps(60)
    assert animator._fps == 60
    
    # Invalid FPS should fall back
    animator.set_fps(0)
    assert animator._fps == 30
    
    animator.set_fps(200)
    assert animator._fps == 30


def test_animator_progress_values(qapp, qtbot):
    """Test that animation progresses smoothly."""
    animator = PanScanAnimator(duration_ms=300, fps=60)
    
    frame_updates = []
    animator.frame_updated.connect(lambda rect: frame_updates.append(rect))
    
    with qtbot.waitSignal(animator.animation_finished, timeout=1000):
        animator.start(
            image_size=(1920, 1080),
            viewport_size=(800, 600),
            direction=PanDirection.LEFT_TO_RIGHT
        )
    
    # Should have multiple frames
    assert len(frame_updates) > 5
    
    # First and last frames should be different (movement occurred)
    first_rect = frame_updates[0]
    last_rect = frame_updates[-1]
    assert first_rect.x() != last_rect.x() or first_rect.y() != last_rect.y()


def test_animator_concurrent_prevention(qapp):
    """Test that starting while active stops first."""
    animator = PanScanAnimator(duration_ms=5000, fps=30)
    
    animator.start(
        image_size=(1920, 1080),
        viewport_size=(800, 600),
        direction=PanDirection.LEFT_TO_RIGHT
    )
    
    assert animator.is_active() is True
    
    # Starting again should stop first
    animator.start(
        image_size=(1920, 1080),
        viewport_size=(800, 600),
        direction=PanDirection.RIGHT_TO_LEFT
    )
    
    assert animator.is_active() is True
    
    animator.stop()


def test_ease_in_out_cubic(qapp):
    """Test easing function."""
    animator = PanScanAnimator()
    
    # Test easing at various points
    assert animator._ease_in_out_cubic(0.0) == 0.0
    assert 0.0 < animator._ease_in_out_cubic(0.25) < 0.25
    assert animator._ease_in_out_cubic(0.5) == 0.5
    assert 0.75 < animator._ease_in_out_cubic(0.75) < 1.0
    assert animator._ease_in_out_cubic(1.0) == 1.0


def test_animator_small_image(qapp, qtbot):
    """Test with image smaller than viewport."""
    animator = PanScanAnimator(duration_ms=100, fps=60, zoom_min=1.0, zoom_max=1.1)
    
    frame_updates = []
    animator.frame_updated.connect(lambda rect: frame_updates.append(rect))
    
    with qtbot.waitSignal(animator.animation_finished, timeout=1000):
        animator.start(
            image_size=(640, 480),
            viewport_size=(800, 600),
            direction=PanDirection.LEFT_TO_RIGHT
        )
    
    # Should still complete successfully
    assert len(frame_updates) > 0


def test_animator_multiple_runs(qapp, qtbot):
    """Test running animation multiple times."""
    animator = PanScanAnimator(duration_ms=100, fps=60)
    
    for _ in range(3):
        frame_updates = []
        animator.frame_updated.connect(lambda rect: frame_updates.append(rect))
        
        with qtbot.waitSignal(animator.animation_finished, timeout=1000):
            animator.start(
                image_size=(1920, 1080),
                viewport_size=(800, 600),
                direction=PanDirection.RANDOM
            )
        
        assert len(frame_updates) > 0
