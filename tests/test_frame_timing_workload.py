"""Automated frame timing test with realistic workload.

Simulates a realistic screensaver session with multiple transitions
and measures dt_max to detect UI thread blocking.

Run with: python pytest.py tests/test_frame_timing_workload.py -v
"""
import time
import pytest
from typing import List, Optional

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QPixmap, QColor, QImage

from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from rendering.gl_compositor import GLCompositorWidget


class FrameTimingCollector:
    """Collects frame timing data during test runs."""
    
    def __init__(self):
        self.frame_times: List[float] = []
        self.last_time: Optional[float] = None
        self.transition_metrics: List[dict] = []
    
    def record_frame(self):
        now = time.perf_counter()
        if self.last_time is not None:
            dt = (now - self.last_time) * 1000.0
            self.frame_times.append(dt)
        self.last_time = now
    
    def reset(self):
        self.frame_times.clear()
        self.last_time = None
    
    def get_stats(self) -> dict:
        if not self.frame_times:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": len(self.frame_times),
            "avg": sum(self.frame_times) / len(self.frame_times),
            "min": min(self.frame_times),
            "max": max(self.frame_times),
        }
    
    def record_transition(self, name: str):
        stats = self.get_stats()
        stats["transition"] = name
        self.transition_metrics.append(stats)
        self.reset()


class MockSpotifyVisualizer:
    """Simulates Spotify visualizer tick load."""
    
    def __init__(self, collector: FrameTimingCollector):
        self.collector = collector
        self.tick_count = 0
        self._display_bars = [0.0] * 16
    
    def on_tick(self):
        self.tick_count += 1
        for i in range(16):
            self._display_bars[i] = min(1.0, self._display_bars[i] + 0.01)
        self.collector.record_frame()


@pytest.fixture
def test_pixmap():
    """Create test pixmap."""
    image = QImage(QSize(1920, 1080), QImage.Format.Format_RGB32)
    image.fill(QColor(100, 100, 100))
    return QPixmap.fromImage(image)


@pytest.fixture
def test_pixmap2():
    """Create second test pixmap."""
    image = QImage(QSize(1920, 1080), QImage.Format.Format_RGB32)
    image.fill(QColor(200, 200, 200))
    return QPixmap.fromImage(image)


class TestFrameTimingWorkload:
    """Test frame timing under realistic workload conditions."""
    
    def test_slide_with_visualizer_load(self, qtbot, test_pixmap, test_pixmap2):
        """Test slide transition with simulated visualizer load."""
        collector = FrameTimingCollector()
        visualizer = MockSpotifyVisualizer(collector)
        
        compositor = GLCompositorWidget(parent=None)
        compositor.resize(1920, 1080)
        compositor.show()
        qtbot.waitExposed(compositor)
        compositor.set_base_pixmap(test_pixmap)
        
        animation_manager = AnimationManager(fps=60)
        listener_id = animation_manager.add_tick_listener(lambda dt: visualizer.on_tick())
        
        duration_ms = 1500
        width = compositor.width()
        pixmaps = [test_pixmap, test_pixmap2]
        
        for i in range(3):
            collector.reset()
            completed = [False]
            
            def on_complete():
                completed[0] = True
            
            compositor.start_slide(
                old_pixmap=pixmaps[i % 2],
                new_pixmap=pixmaps[(i + 1) % 2],
                old_start=QPoint(0, 0),
                old_end=QPoint(-width, 0),
                new_start=QPoint(width, 0),
                new_end=QPoint(0, 0),
                duration_ms=duration_ms,
                easing=EasingCurve.QUAD_IN_OUT,
                animation_manager=animation_manager,
                on_finished=on_complete,
            )
            
            start_time = time.time()
            while not completed[0] and time.time() - start_time < 3.0:
                qtbot.wait(16)
            
            collector.record_transition(f"Slide_{i+1}")
        
        animation_manager.remove_tick_listener(listener_id)
        animation_manager.stop()
        
        print("\n=== Frame Timing (with visualizer) ===")
        for m in collector.transition_metrics:
            print(f"  {m['transition']}: frames={m['count']}, avg={m['avg']:.2f}ms, dt_max={m['max']:.2f}ms")
        
        max_dt = max(m["max"] for m in collector.transition_metrics)
        print(f"\n  Overall dt_max: {max_dt:.2f}ms")
        
        assert max_dt < 200, f"dt_max {max_dt:.2f}ms is unacceptably high"
    
    def test_sustained_workload(self, qtbot, test_pixmap, test_pixmap2):
        """Test 10 back-to-back transitions for degradation."""
        collector = FrameTimingCollector()
        
        compositor = GLCompositorWidget(parent=None)
        compositor.resize(1920, 1080)
        compositor.show()
        qtbot.waitExposed(compositor)
        compositor.set_base_pixmap(test_pixmap)
        
        animation_manager = AnimationManager(fps=60)
        
        original_update = compositor.update
        def timed_update():
            collector.record_frame()
            original_update()
        compositor.update = timed_update
        
        duration_ms = 800
        width = compositor.width()
        pixmaps = [test_pixmap, test_pixmap2]
        
        for i in range(10):
            collector.reset()
            completed = [False]
            
            def on_complete():
                completed[0] = True
            
            if i % 2 == 0:
                old_s, old_e = QPoint(0, 0), QPoint(-width, 0)
                new_s, new_e = QPoint(width, 0), QPoint(0, 0)
            else:
                old_s, old_e = QPoint(0, 0), QPoint(width, 0)
                new_s, new_e = QPoint(-width, 0), QPoint(0, 0)
            
            compositor.start_slide(
                old_pixmap=pixmaps[i % 2],
                new_pixmap=pixmaps[(i + 1) % 2],
                old_start=old_s,
                old_end=old_e,
                new_start=new_s,
                new_end=new_e,
                duration_ms=duration_ms,
                easing=EasingCurve.QUAD_IN_OUT,
                animation_manager=animation_manager,
                on_finished=on_complete,
            )
            
            start_time = time.time()
            while not completed[0] and time.time() - start_time < 2.0:
                qtbot.wait(16)
            
            collector.record_transition(f"Slide_{i+1}")
        
        animation_manager.stop()
        
        print("\n=== Sustained Workload ===")
        dt_maxes = []
        for m in collector.transition_metrics:
            dt_maxes.append(m["max"])
            print(f"  {m['transition']}: dt_max={m['max']:.2f}ms")
        
        first_half = sum(dt_maxes[:5]) / 5
        second_half = sum(dt_maxes[5:]) / 5
        degradation = second_half - first_half
        
        print(f"\n  First half avg: {first_half:.2f}ms")
        print(f"  Second half avg: {second_half:.2f}ms")
        print(f"  Degradation: {degradation:+.2f}ms")
        
        assert max(dt_maxes) < 200, f"Max dt_max {max(dt_maxes):.2f}ms too high"
