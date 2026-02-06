"""Test for slide transition jitter/judder.

Measures frame timing during slide transitions to detect UI thread blocking.
"""
import threading
import time
import pytest
from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import QImage, QPixmap, QColor
from PySide6.QtWidgets import QWidget

from rendering.gl_compositor import GLCompositorWidget
from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve


class FrameTimingCollector:
    """Collects frame timing data during transitions."""
    
    def __init__(self):
        self.frame_times = []
        self.last_time = None
    
    def record_frame(self):
        now = time.perf_counter()
        if self.last_time is not None:
            dt = (now - self.last_time) * 1000  # ms
            self.frame_times.append(dt)
        self.last_time = now
    
    def get_stats(self):
        if not self.frame_times:
            return {'count': 0, 'min': 0, 'max': 0, 'mean': 0}
        return {
            'count': len(self.frame_times),
            'min': min(self.frame_times),
            'max': max(self.frame_times),
            'mean': sum(self.frame_times) / len(self.frame_times),
        }


@pytest.fixture
def test_pixmap():
    """Create test pixmap."""
    image = QImage(QSize(1920, 1080), QImage.Format.Format_RGB32)
    image.fill(QColor(255, 0, 0))
    return QPixmap.fromImage(image)


@pytest.fixture
def test_pixmap2():
    """Create second test pixmap."""
    image = QImage(QSize(1920, 1080), QImage.Format.Format_RGB32)
    image.fill(QColor(0, 255, 0))
    return QPixmap.fromImage(image)


class _MockThreadManager:
    """Minimal TM mock for adaptive timer."""
    def __init__(self):
        self._threads = []
    def submit_task(self, pool_type, fn, *, task_id=None):
        t = threading.Thread(target=fn, daemon=True, name=task_id or "mock")
        t.start()
        self._threads.append(t)
    def shutdown(self):
        for t in self._threads:
            t.join(timeout=2)


@pytest.fixture
def compositor_parent(qtbot):
    """Parent widget with _thread_manager for GLCompositorWidget."""
    parent = QWidget()
    parent._thread_manager = _MockThreadManager()
    parent._resource_manager = None
    qtbot.addWidget(parent)
    parent.resize(1920, 1080)
    yield parent
    parent._thread_manager.shutdown()


class TestSlideJitter:
    """Test slide transition for jitter/judder."""
    
    def test_slide_dt_max_under_threshold(self, qtbot, test_pixmap, test_pixmap2, compositor_parent):
        """Slide transition should have dt_max < 50ms (no major UI blocking)."""
        compositor = GLCompositorWidget(parent=compositor_parent)
        compositor.resize(1920, 1080)
        compositor.show()
        qtbot.waitExposed(compositor)
        
        # Set initial image
        compositor.set_base_pixmap(test_pixmap)
        
        # Create animation manager
        anim_manager = AnimationManager(fps=60)
        
        # Frame timing collector
        collector = FrameTimingCollector()
        
        # Hook into compositor's update to record frame times
        original_update = compositor.update
        def timed_update():
            collector.record_frame()
            original_update()
        compositor.update = timed_update
        
        # Start slide transition (left direction)
        width = compositor.width()
        completed = [False]
        def on_complete():
            completed[0] = True
        
        compositor.start_slide(
            old_pixmap=test_pixmap,
            new_pixmap=test_pixmap2,
            old_start=QPoint(0, 0),
            old_end=QPoint(-width, 0),
            new_start=QPoint(width, 0),
            new_end=QPoint(0, 0),
            duration_ms=1000,
            easing=EasingCurve.QUAD_IN_OUT,
            animation_manager=anim_manager,
            on_finished=on_complete,
        )
        
        # Wait for completion with timeout
        start = time.time()
        while not completed[0] and time.time() - start < 3.0:
            qtbot.wait(16)  # ~60fps
        
        # Stop animation manager
        anim_manager.stop()
        
        # Get stats
        stats = collector.get_stats()
        print("\nSlide transition frame timing:")
        print(f"  Frames: {stats['count']}")
        print(f"  dt_min: {stats['min']:.2f}ms")
        print(f"  dt_max: {stats['max']:.2f}ms")
        print(f"  dt_mean: {stats['mean']:.2f}ms")
        
        # Assert dt_max is under threshold
        # 50ms = 3 frames at 60fps, indicates significant UI blocking
        assert stats['max'] < 50.0, f"dt_max {stats['max']:.2f}ms exceeds 50ms threshold - UI thread blocking detected"
        
        # Cleanup
        compositor.close()
    
    def test_slide_frame_count_reasonable(self, qtbot, test_pixmap, test_pixmap2, compositor_parent):
        """Slide transition should render enough frames (no massive drops)."""
        compositor = GLCompositorWidget(parent=compositor_parent)
        compositor.resize(1920, 1080)
        compositor.show()
        qtbot.waitExposed(compositor)
        
        compositor.set_base_pixmap(test_pixmap)
        anim_manager = AnimationManager(fps=60)
        
        collector = FrameTimingCollector()
        original_update = compositor.update
        def timed_update():
            collector.record_frame()
            original_update()
        compositor.update = timed_update
        
        width = compositor.width()
        completed = [False]
        def on_complete():
            completed[0] = True
        
        # 1 second transition at 60fps should give ~60 frames
        compositor.start_slide(
            old_pixmap=test_pixmap,
            new_pixmap=test_pixmap2,
            old_start=QPoint(0, 0),
            old_end=QPoint(-width, 0),
            new_start=QPoint(width, 0),
            new_end=QPoint(0, 0),
            duration_ms=1000,
            easing=EasingCurve.QUAD_IN_OUT,
            animation_manager=anim_manager,
            on_finished=on_complete,
        )
        
        start = time.time()
        while not completed[0] and time.time() - start < 3.0:
            qtbot.wait(16)
        
        anim_manager.stop()
        stats = collector.get_stats()
        
        # Should have at least 30 frames for a 1 second transition (50% of target)
        assert stats['count'] >= 30, f"Only {stats['count']} frames rendered - expected at least 30"
        
        compositor.close()
