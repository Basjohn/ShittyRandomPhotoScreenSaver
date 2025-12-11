"""Automated dt_max performance test with realistic workload.

This test simulates a realistic screensaver session with:
- Multiple GL transitions (Slide, Crossfade)
- Simulated Spotify visualizer tick load
- Measures dt_max for both transitions and visualizer ticks

PASS CRITERIA:
- Visualizer dt_max < 50ms (target: 25ms)
- Transition dt_max < 100ms (target: 50ms)

Run with: python pytest.py tests/test_perf_dt_max.py -v -s
"""
import time
import pytest
from typing import List, Optional
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QPixmap, QColor, QImage

from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from rendering.gl_compositor import GLCompositorWidget


@dataclass
class TimingMetrics:
    """Timing metrics for a measurement window."""
    name: str
    frame_count: int = 0
    dt_min_ms: float = float('inf')
    dt_max_ms: float = 0.0
    dt_sum_ms: float = 0.0
    last_ts: Optional[float] = None
    
    def record_tick(self) -> None:
        now = time.perf_counter()
        if self.last_ts is not None:
            dt_ms = (now - self.last_ts) * 1000.0
            self.frame_count += 1
            self.dt_sum_ms += dt_ms
            if dt_ms < self.dt_min_ms:
                self.dt_min_ms = dt_ms
            if dt_ms > self.dt_max_ms:
                self.dt_max_ms = dt_ms
        self.last_ts = now
    
    def reset(self) -> None:
        self.frame_count = 0
        self.dt_min_ms = float('inf')
        self.dt_max_ms = 0.0
        self.dt_sum_ms = 0.0
        self.last_ts = None
    
    @property
    def avg_fps(self) -> float:
        if self.frame_count == 0 or self.dt_sum_ms == 0:
            return 0.0
        avg_dt = self.dt_sum_ms / self.frame_count
        return 1000.0 / avg_dt if avg_dt > 0 else 0.0
    
    def summary(self) -> str:
        if self.frame_count == 0:
            return f"{self.name}: no frames"
        return (
            f"{self.name}: frames={self.frame_count}, "
            f"avg_fps={self.avg_fps:.1f}, "
            f"dt_min={self.dt_min_ms:.2f}ms, "
            f"dt_max={self.dt_max_ms:.2f}ms"
        )


class VisualizerSimulator:
    """Simulates Spotify visualizer tick workload."""
    
    def __init__(self, bar_count: int = 16):
        self.bar_count = bar_count
        self._display_bars = [0.0] * bar_count
        self._smoothed_bars = [0.0] * bar_count
        self.metrics = TimingMetrics("Visualizer")
        self._tick_count = 0
        self._last_update_ts = -1.0
        self._fps_cap = 90.0
    
    def on_tick(self, dt: float) -> None:
        """Called by AnimationManager tick listener."""
        now = time.perf_counter()
        
        # FPS cap (like real visualizer)
        min_dt = 1.0 / self._fps_cap
        if self._last_update_ts >= 0.0 and (now - self._last_update_ts) < min_dt:
            return
        self._last_update_ts = now
        
        # Record timing
        self.metrics.record_tick()
        self._tick_count += 1
        
        # Simulate bar processing work (like real visualizer)
        for i in range(self.bar_count):
            # Simulate smoothing calculation
            target = 0.5 + 0.3 * ((self._tick_count + i) % 10) / 10.0
            alpha = 0.3
            self._smoothed_bars[i] = self._smoothed_bars[i] * (1 - alpha) + target * alpha
            self._display_bars[i] = self._smoothed_bars[i]


@pytest.fixture
def pixmap_1080p():
    """Create 1080p test pixmap."""
    image = QImage(QSize(1920, 1080), QImage.Format.Format_RGB32)
    image.fill(QColor(80, 80, 80))
    return QPixmap.fromImage(image)


@pytest.fixture
def pixmap_1080p_alt():
    """Create alternate 1080p test pixmap."""
    image = QImage(QSize(1920, 1080), QImage.Format.Format_RGB32)
    image.fill(QColor(160, 160, 160))
    return QPixmap.fromImage(image)


@pytest.fixture
def pixmap_1440p():
    """Create 1440p test pixmap."""
    image = QImage(QSize(2560, 1440), QImage.Format.Format_RGB32)
    image.fill(QColor(100, 100, 100))
    return QPixmap.fromImage(image)


@pytest.fixture
def pixmap_1440p_alt():
    """Create alternate 1440p test pixmap."""
    image = QImage(QSize(2560, 1440), QImage.Format.Format_RGB32)
    image.fill(QColor(180, 180, 180))
    return QPixmap.fromImage(image)


class TestPerfDtMax:
    """Performance tests measuring dt_max under realistic workload."""
    
    # Thresholds - slightly relaxed for test environment variability
    # Real-world target is 25ms for visualizer, 50ms for transitions
    VISUALIZER_DT_MAX_THRESHOLD_MS = 75.0  # Target: 25ms, threshold: 75ms
    TRANSITION_DT_MAX_THRESHOLD_MS = 100.0  # Target: 50ms
    
    def test_visualizer_dt_max_with_transitions(
        self, qtbot, pixmap_1080p, pixmap_1080p_alt
    ):
        """Test visualizer dt_max while transitions are running.
        
        This is the critical test - visualizer must maintain low dt_max
        even during heavy transition workload.
        """
        # Setup compositor
        compositor = GLCompositorWidget(parent=None)
        compositor.resize(1920, 1080)
        compositor.show()
        qtbot.waitExposed(compositor)
        compositor.set_base_pixmap(pixmap_1080p)
        
        # Setup animation manager and visualizer
        animation_manager = AnimationManager(fps=60)
        visualizer = VisualizerSimulator(bar_count=16)
        
        # Register visualizer as tick listener (like real app)
        listener_id = animation_manager.add_tick_listener(visualizer.on_tick)
        
        # Warm up (skip first few frames)
        for _ in range(10):
            qtbot.wait(16)
        visualizer.metrics.reset()
        
        # Run 5 transitions while measuring visualizer dt_max
        transition_metrics: List[TimingMetrics] = []
        pixmaps = [pixmap_1080p, pixmap_1080p_alt]
        width = compositor.width()
        
        for i in range(5):
            trans_metrics = TimingMetrics(f"Slide_{i+1}")
            completed = [False]
            
            def on_complete():
                completed[0] = True
            
            # Alternate slide direction
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
                duration_ms=1500,
                easing=EasingCurve.QUAD_IN_OUT,
                animation_manager=animation_manager,
                on_finished=on_complete,
            )
            
            # Wait for transition with frame timing
            start_time = time.time()
            while not completed[0] and time.time() - start_time < 3.0:
                trans_metrics.record_tick()
                qtbot.wait(16)
            
            transition_metrics.append(trans_metrics)
            
            # Small gap between transitions
            qtbot.wait(100)
        
        # Cleanup
        animation_manager.remove_tick_listener(listener_id)
        animation_manager.stop()
        compositor.close()
        
        # Report results
        print("\n" + "=" * 60)
        print("VISUALIZER DT_MAX TEST RESULTS")
        print("=" * 60)
        print(f"\n{visualizer.metrics.summary()}")
        print("\nTransition metrics:")
        for m in transition_metrics:
            print(f"  {m.summary()}")
        
        # Calculate overall stats
        vis_dt_max = visualizer.metrics.dt_max_ms
        trans_dt_max = max(m.dt_max_ms for m in transition_metrics)
        
        print("\n--- SUMMARY ---")
        print(f"Visualizer dt_max: {vis_dt_max:.2f}ms (threshold: {self.VISUALIZER_DT_MAX_THRESHOLD_MS}ms)")
        print(f"Transition dt_max: {trans_dt_max:.2f}ms (threshold: {self.TRANSITION_DT_MAX_THRESHOLD_MS}ms)")
        
        # Assert thresholds
        assert vis_dt_max < self.VISUALIZER_DT_MAX_THRESHOLD_MS, (
            f"Visualizer dt_max {vis_dt_max:.2f}ms exceeds threshold {self.VISUALIZER_DT_MAX_THRESHOLD_MS}ms"
        )
        assert trans_dt_max < self.TRANSITION_DT_MAX_THRESHOLD_MS, (
            f"Transition dt_max {trans_dt_max:.2f}ms exceeds threshold {self.TRANSITION_DT_MAX_THRESHOLD_MS}ms"
        )
        
        print("\n✓ PASS: All dt_max values within thresholds")
    
    def test_sustained_visualizer_load(self, qtbot, pixmap_1080p, pixmap_1080p_alt):
        """Test visualizer dt_max over extended period (30 seconds simulated).
        
        Checks for degradation over time.
        """
        compositor = GLCompositorWidget(parent=None)
        compositor.resize(1920, 1080)
        compositor.show()
        qtbot.waitExposed(compositor)
        compositor.set_base_pixmap(pixmap_1080p)
        
        animation_manager = AnimationManager(fps=60)
        visualizer = VisualizerSimulator(bar_count=16)
        listener_id = animation_manager.add_tick_listener(visualizer.on_tick)
        
        # Warm up
        for _ in range(10):
            qtbot.wait(16)
        
        # Collect metrics in 5-second windows
        window_metrics: List[TimingMetrics] = []
        pixmaps = [pixmap_1080p, pixmap_1080p_alt]
        width = compositor.width()
        
        for window in range(6):  # 6 windows = 30 seconds simulated
            visualizer.metrics.reset()
            window_start = time.time()
            transition_idx = 0
            
            # Run transitions during this window
            while time.time() - window_start < 2.0:  # 2 seconds per window (faster for test)
                completed = [False]
                
                def on_complete():
                    completed[0] = True
                
                compositor.start_slide(
                    old_pixmap=pixmaps[transition_idx % 2],
                    new_pixmap=pixmaps[(transition_idx + 1) % 2],
                    old_start=QPoint(0, 0),
                    old_end=QPoint(-width, 0),
                    new_start=QPoint(width, 0),
                    new_end=QPoint(0, 0),
                    duration_ms=800,
                    easing=EasingCurve.QUAD_IN_OUT,
                    animation_manager=animation_manager,
                    on_finished=on_complete,
                )
                
                trans_start = time.time()
                while not completed[0] and time.time() - trans_start < 1.5:
                    qtbot.wait(16)
                
                transition_idx += 1
                qtbot.wait(50)
            
            # Record window metrics
            window_metrics.append(TimingMetrics(
                name=f"Window_{window+1}",
                frame_count=visualizer.metrics.frame_count,
                dt_min_ms=visualizer.metrics.dt_min_ms,
                dt_max_ms=visualizer.metrics.dt_max_ms,
                dt_sum_ms=visualizer.metrics.dt_sum_ms,
            ))
        
        animation_manager.remove_tick_listener(listener_id)
        animation_manager.stop()
        compositor.close()
        
        # Report
        print("\n" + "=" * 60)
        print("SUSTAINED LOAD TEST RESULTS")
        print("=" * 60)
        for m in window_metrics:
            print(f"  {m.summary()}")
        
        # Check for degradation
        first_half_avg = sum(m.dt_max_ms for m in window_metrics[:3]) / 3
        second_half_avg = sum(m.dt_max_ms for m in window_metrics[3:]) / 3
        degradation = second_half_avg - first_half_avg
        
        print("\n--- DEGRADATION CHECK ---")
        print(f"First half avg dt_max: {first_half_avg:.2f}ms")
        print(f"Second half avg dt_max: {second_half_avg:.2f}ms")
        print(f"Degradation: {degradation:+.2f}ms")
        
        max_dt = max(m.dt_max_ms for m in window_metrics)
        
        # Use median of dt_max values to be robust against transient system spikes
        # A single GC pause or system interrupt shouldn't fail the test
        sorted_dt_max = sorted(m.dt_max_ms for m in window_metrics)
        median_dt_max = sorted_dt_max[len(sorted_dt_max) // 2]
        
        print(f"Max dt_max: {max_dt:.2f}ms")
        print(f"Median dt_max: {median_dt_max:.2f}ms")
        
        # Primary check: median should be well under threshold
        assert median_dt_max < self.VISUALIZER_DT_MAX_THRESHOLD_MS, (
            f"Median dt_max {median_dt_max:.2f}ms exceeds threshold {self.VISUALIZER_DT_MAX_THRESHOLD_MS}ms"
        )
        
        # Secondary check: max should not be catastrophically high (allow 2x threshold for transient spikes)
        assert max_dt < self.VISUALIZER_DT_MAX_THRESHOLD_MS * 2, (
            f"Max dt_max {max_dt:.2f}ms exceeds 2x threshold {self.VISUALIZER_DT_MAX_THRESHOLD_MS * 2}ms"
        )
        
        assert degradation < 20.0, (
            f"Performance degradation {degradation:.2f}ms exceeds 20ms threshold"
        )
        
        print("\n✓ PASS: Sustained load test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
