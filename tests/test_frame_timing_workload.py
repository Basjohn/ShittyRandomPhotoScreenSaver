"""Automated frame timing test with realistic workload.

Simulates a realistic screensaver session with multiple transitions
and measures dt_max to detect UI thread blocking.

Run with: python tests/pytest.py tests/test_frame_timing_workload.py -v
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import pytest
from PySide6.QtCore import QPoint, QSize, QTimer
from PySide6.QtGui import QPixmap, QColor, QImage
from PySide6.QtWidgets import QWidget

from core.threading.manager import ThreadPoolType
from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from rendering.gl_compositor import GLCompositorWidget

pytestmark = pytest.mark.frame_timing_isolated


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


@dataclass
class _LoggerSilencer:
    names: tuple[str, ...]
    level: int = logging.WARNING

    def __post_init__(self) -> None:
        self._originals: list[tuple[logging.Logger, int]] = []
        for name in self.names:
            logger = logging.getLogger(name)
            self._originals.append((logger, logger.level if logger.level else logging.NOTSET))
            logger.setLevel(self.level)

    def restore(self) -> None:
        for logger, level in self._originals:
            logger.setLevel(level)


class FrameTimingHarness:
    """Provides isolated GL compositor + animation manager for frame timing tests."""

    def __init__(self, qtbot, *, loggers_to_silence: tuple[str, ...]) -> None:
        self.qtbot = qtbot
        self.collector = FrameTimingCollector()
        self.parent = QWidget()
        self.parent.resize(1920, 1080)
        self.parent._thread_manager = _HarnessThreadManager()
        self.parent._resource_manager = None
        self.qtbot.addWidget(self.parent)
        self.parent.show()
        self.compositor = GLCompositorWidget(parent=self.parent)
        self.qtbot.addWidget(self.compositor)
        self.compositor.resize(1920, 1080)
        self.compositor.show()
        self.qtbot.waitExposed(self.compositor)
        self.animation_manager = AnimationManager(fps=60)
        self._original_update: Callable[[], None] = self.compositor.update
        self._frame_sampling_enabled = False
        self._silencer = _LoggerSilencer(loggers_to_silence)

    def set_base_pixmap(self, pixmap: QPixmap) -> None:
        self.compositor.set_base_pixmap(pixmap)

    def enable_frame_sampling(self) -> None:
        """Record render cadence by wrapping compositor.update."""
        if self._frame_sampling_enabled:
            return

        def timed_update():
            self.collector.record_frame()
            self._original_update()

        self.compositor.update = timed_update
        self._frame_sampling_enabled = True

    def reset_metrics(self) -> None:
        self.collector.reset()

    def teardown(self) -> None:
        self.compositor.update = self._original_update
        try:
            self.animation_manager.stop()
        except Exception:
            pass
        try:
            self.animation_manager.cleanup()
        except Exception:
            pass
        try:
            self.parent._thread_manager.shutdown()
        except Exception:
            pass
        self.compositor.hide()
        self.compositor.setParent(None)
        self.compositor.deleteLater()
        self.parent.hide()
        self.parent.deleteLater()
        self.qtbot.wait(0)
        self._silencer.restore()


class _HarnessThreadManager:
    """Minimal production-shaped ThreadManager for compositor timing tests."""

    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []

    def submit_task(self, pool_type: ThreadPoolType, fn: Callable, *, task_id: str | None = None, **_kwargs) -> str:
        thread = threading.Thread(target=fn, daemon=True, name=task_id or f"{pool_type.value}_test")
        thread.start()
        self._threads.append(thread)
        return task_id or thread.name

    def single_shot(self, delay_ms: int, fn: Callable, *args, **kwargs) -> None:
        QTimer.singleShot(max(0, int(delay_ms)), lambda: fn(*args, **kwargs))

    def shutdown(self) -> None:
        for thread in list(self._threads):
            thread.join(timeout=2.0)


@pytest.fixture
def frame_timing_harness(qtbot):
    harness = FrameTimingHarness(
        qtbot,
        loggers_to_silence=(
            "rendering.gl_compositor",
            "rendering.display_widget",
        ),
    )
    yield harness
    harness.teardown()


class TestFrameTimingWorkload:
    """Test frame timing under realistic workload conditions."""
    
    def test_slide_with_visualizer_load(self, qtbot, test_pixmap, test_pixmap2, frame_timing_harness):
        """Test slide transition with simulated visualizer load."""
        collector = frame_timing_harness.collector
        collector.reset()
        visualizer = MockSpotifyVisualizer(collector)
        
        compositor = frame_timing_harness.compositor
        frame_timing_harness.set_base_pixmap(test_pixmap)
        try:
            compositor._ensure_transition_program_ready("slide")
            compositor.warm_transition_resources("GLCompositorSlideTransition", test_pixmap, test_pixmap2)
        except Exception:
            pass
        qtbot.wait(0)
        
        animation_manager = frame_timing_harness.animation_manager
        listener_id = animation_manager.add_tick_listener(lambda dt: visualizer.on_tick())
        # Prime the standalone listener before measuring. Visualizer ticks are
        # no longer transition-manager work in production, and this keeps the
        # legacy harness from counting its startup gap as transition cadence.
        qtbot.wait(50)
        collector.reset()
        
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
        
        cold_dt = collector.transition_metrics[0]["max"]
        steady_dt = max(m["max"] for m in collector.transition_metrics[1:])
        print(f"\n  Cold dt_max: {cold_dt:.2f}ms")
        print(f"  Steady dt_max: {steady_dt:.2f}ms")

        assert steady_dt < 50, f"steady dt_max {steady_dt:.2f}ms is unacceptably high"
        assert cold_dt < 350, f"cold dt_max {cold_dt:.2f}ms is unacceptably high"
    
    def test_sustained_workload(self, qtbot, test_pixmap, test_pixmap2, frame_timing_harness):
        """Test 10 back-to-back transitions for degradation."""
        collector = frame_timing_harness.collector
        collector.reset()
        
        compositor = frame_timing_harness.compositor
        frame_timing_harness.set_base_pixmap(test_pixmap)
        frame_timing_harness.enable_frame_sampling()
        
        animation_manager = frame_timing_harness.animation_manager
        
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
