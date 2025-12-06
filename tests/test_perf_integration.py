"""Integration performance test - runs actual app components.

This test runs the REAL visualizer and transitions to measure actual dt_max.
It identifies which component is causing UI thread blocks.

Run with: python pytest.py tests/test_perf_integration.py -v -s
Or directly: python tests/test_perf_integration.py
"""
import os
import sys
import time
import gc
import threading
from typing import Optional, List
from dataclasses import dataclass, field

# Set perf metrics before imports
os.environ['SRPSS_PERF_METRICS'] = '1'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap, QImage, QColor

from core.threading.manager import ThreadManager
from core.animation.animator import AnimationManager


@dataclass
class ComponentMetrics:
    """Metrics for a single component."""
    name: str
    tick_count: int = 0
    dt_min_ms: float = float('inf')
    dt_max_ms: float = 0.0
    dt_sum_ms: float = 0.0
    last_ts: float = 0.0
    slow_ticks: List[float] = field(default_factory=list)
    
    def record_tick(self) -> None:
        now = time.perf_counter()
        if self.last_ts > 0:
            dt_ms = (now - self.last_ts) * 1000.0
            self.tick_count += 1
            self.dt_sum_ms += dt_ms
            if dt_ms < self.dt_min_ms:
                self.dt_min_ms = dt_ms
            if dt_ms > self.dt_max_ms:
                self.dt_max_ms = dt_ms
            if dt_ms > 50.0:
                self.slow_ticks.append(dt_ms)
        self.last_ts = now
    
    @property
    def avg_fps(self) -> float:
        if self.tick_count == 0 or self.dt_sum_ms == 0:
            return 0.0
        return 1000.0 / (self.dt_sum_ms / self.tick_count)
    
    def report(self) -> str:
        if self.tick_count == 0:
            return f"{self.name}: NO TICKS"
        slow_count = len(self.slow_ticks)
        slow_pct = (slow_count / self.tick_count) * 100.0 if self.tick_count > 0 else 0.0
        status = "PASS" if self.dt_max_ms < 50.0 else "FAIL"
        return (
            f"{self.name}: {status} | "
            f"ticks={self.tick_count}, avg_fps={self.avg_fps:.1f}, "
            f"dt_min={self.dt_min_ms:.2f}ms, dt_max={self.dt_max_ms:.2f}ms, "
            f"slow_ticks={slow_count} ({slow_pct:.1f}%)"
        )


class IsolatedTimerTest:
    """Test isolated QTimer performance without any other components."""
    
    def __init__(self, interval_ms: int = 16):
        self.interval_ms = interval_ms
        self.metrics = ComponentMetrics(name=f"IsolatedTimer({interval_ms}ms)")
        self._timer: Optional[QTimer] = None
    
    def start(self) -> None:
        self._timer = QTimer()
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(self.interval_ms)
    
    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
    
    def _on_tick(self) -> None:
        self.metrics.record_tick()


class MultiTimerTest:
    """Test multiple QTimers running simultaneously."""
    
    def __init__(self, timer_count: int = 6, interval_ms: int = 16):
        self.timer_count = timer_count
        self.interval_ms = interval_ms
        self.metrics = ComponentMetrics(name=f"MultiTimer({timer_count}x{interval_ms}ms)")
        self._timers: List[QTimer] = []
    
    def start(self) -> None:
        for i in range(self.timer_count):
            timer = QTimer()
            timer.setTimerType(Qt.TimerType.PreciseTimer)
            timer.timeout.connect(self._on_tick)
            timer.start(self.interval_ms)
            self._timers.append(timer)
    
    def stop(self) -> None:
        for timer in self._timers:
            timer.stop()
        self._timers.clear()
    
    def _on_tick(self) -> None:
        self.metrics.record_tick()


class GLWidgetTest:
    """Test QOpenGLWidget update performance."""
    
    def __init__(self, interval_ms: int = 16):
        self.interval_ms = interval_ms
        self.metrics = ComponentMetrics(name=f"GLWidget({interval_ms}ms)")
        self._timer: Optional[QTimer] = None
        self._widget: Optional[QWidget] = None
    
    def start(self, parent: QWidget) -> None:
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            self._widget = QOpenGLWidget(parent)
            self._widget.setGeometry(0, 0, 200, 200)
            self._widget.show()
        except Exception as e:
            print(f"  [SKIP] GLWidget test - no OpenGL: {e}")
            return
        
        self._timer = QTimer()
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(self.interval_ms)
    
    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        if self._widget:
            self._widget.hide()
            self._widget.deleteLater()
            self._widget = None
    
    def _on_tick(self) -> None:
        self.metrics.record_tick()
        if self._widget:
            self._widget.update()


class VisualizerTest:
    """Test actual Spotify visualizer component."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="SpotifyVisualizer")
        self._widget = None
        self._engine = None
        self._measure_timer: Optional[QTimer] = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from widgets.spotify_visualizer_widget import (
                SpotifyVisualizerWidget,
                get_shared_spotify_beat_engine,
            )
            
            self._widget = SpotifyVisualizerWidget(parent)
            self._widget.setGeometry(20, 20, 300, 150)
            self._widget._thread_manager = thread_manager
            self._widget.show()
            self._widget.start()
            
            # Use a separate timer to measure tick gaps
            # This runs at the same rate and measures event loop responsiveness
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
        except Exception as e:
            print(f"  [SKIP] Visualizer test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        if self._widget:
            try:
                self._widget.stop()
                self._widget.hide()
                self._widget.deleteLater()
            except Exception:
                pass
            self._widget = None


class VisualizerNoAudioTest:
    """Test visualizer WITHOUT audio capture (isolate audio from UI)."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="VisualizerNoAudio")
        self._widget = None
        self._measure_timer: Optional[QTimer] = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
            
            self._widget = SpotifyVisualizerWidget(parent)
            self._widget.setGeometry(20, 20, 300, 150)
            self._widget._thread_manager = thread_manager
            self._widget.show()
            # DON'T call start() - this skips audio capture
            # Just enable the widget directly
            self._widget._enabled = True
            
            # Measurement timer
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
        except Exception as e:
            print(f"  [SKIP] VisualizerNoAudio test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        if self._widget:
            try:
                self._widget._enabled = False
                self._widget.hide()
                self._widget.deleteLater()
            except Exception:
                pass
            self._widget = None


class VisualizerWithGLOverlayTest:
    """Test visualizer WITH SpotifyBarsGLOverlay (the actual GPU path)."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="VisualizerWithGLOverlay")
        self._widget = None
        self._overlay = None
        self._measure_timer: Optional[QTimer] = None
        self._update_timer: Optional[QTimer] = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
            from PySide6.QtCore import QRect
            from PySide6.QtGui import QColor
            
            # Create the GL overlay directly
            self._overlay = SpotifyBarsGLOverlay(parent)
            self._overlay.setGeometry(20, 20, 300, 150)
            self._overlay.show()
            
            # Timer to simulate visualizer updates (push bar data)
            self._update_timer = QTimer()
            self._update_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._update_timer.timeout.connect(self._on_update)
            self._update_timer.start(16)
            
            # Measurement timer
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
            self._bar_count = 16
            self._bars = [0.5] * self._bar_count
            
        except Exception as e:
            print(f"  [SKIP] VisualizerWithGLOverlay test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_update(self) -> None:
        if self._overlay is None:
            return
        try:
            from PySide6.QtCore import QRect
            from PySide6.QtGui import QColor
            import random
            
            # Simulate bar updates
            for i in range(self._bar_count):
                self._bars[i] = random.random()
            
            self._overlay.set_state(
                rect=QRect(20, 20, 300, 150),
                bars=self._bars,
                bar_count=self._bar_count,
                segments=8,
                fill_color=QColor(0, 255, 0),
                border_color=QColor(0, 200, 0),
                fade=1.0,
                playing=True,
                visible=True,
            )
        except Exception:
            pass
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer = None
        if self._overlay:
            try:
                self._overlay.hide()
                self._overlay.deleteLater()
            except Exception:
                pass
            self._overlay = None


class TwoVisualizersTest:
    """Test with 2 visualizers (simulates real app with 2 displays)."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="TwoVisualizers")
        self._widgets = []
        self._measure_timer: Optional[QTimer] = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
            
            # Create 2 visualizers (like real app with 2 displays)
            for i in range(2):
                vis = SpotifyVisualizerWidget(parent)
                vis.setGeometry(20 + i * 320, 20, 300, 150)
                vis._thread_manager = thread_manager
                vis.show()
                vis.start()
                self._widgets.append(vis)
            
            # Measurement timer
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
        except Exception as e:
            print(f"  [SKIP] TwoVisualizers test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        for widget in self._widgets:
            try:
                widget.stop()
                widget.hide()
                widget.deleteLater()
            except Exception:
                pass
        self._widgets.clear()


class MediaWidgetTest:
    """Test media widget (GSMTC polling)."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="MediaWidget")
        self._widget = None
        self._measure_timer: Optional[QTimer] = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from widgets.media_widget import MediaWidget
            from core.media.media_controller import create_media_controller
            
            controller = create_media_controller()
            self._widget = MediaWidget(parent=parent, controller=controller)
            self._widget.setGeometry(20, 200, 400, 100)
            self._widget._thread_manager = thread_manager
            self._widget.show()
            
            # Measurement timer
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
        except Exception as e:
            print(f"  [SKIP] MediaWidget test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        if self._widget:
            try:
                self._widget.hide()
                self._widget.deleteLater()
            except Exception:
                pass
            self._widget = None


class GLCompositorTransitionTest:
    """Test GL compositor with actual GLSL transitions."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="GLCompositorTransition")
        self._compositor = None
        self._measure_timer: Optional[QTimer] = None
        self._animation_manager = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from rendering.gl_compositor import GLCompositorWidget
            from core.animation.animator import AnimationManager
            from PySide6.QtGui import QPixmap, QImage, QColor
            
            # Create GL compositor
            self._compositor = GLCompositorWidget(parent)
            self._compositor.setGeometry(0, 0, 800, 600)
            self._compositor.show()
            
            # Create animation manager
            self._animation_manager = AnimationManager(fps=60)
            
            # Create test images
            img1 = QImage(800, 600, QImage.Format.Format_ARGB32)
            img1.fill(QColor(100, 50, 50))
            img2 = QImage(800, 600, QImage.Format.Format_ARGB32)
            img2.fill(QColor(50, 100, 50))
            self._pix1 = QPixmap.fromImage(img1)
            self._pix2 = QPixmap.fromImage(img2)
            
            # Set initial image
            self._compositor.set_base_pixmap(self._pix1)
            
            # Start a slide transition
            self._start_transition()
            
            # Measurement timer
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
            # Transition restart timer - use shorter transitions to test completion more often
            self._transition_timer = QTimer()
            self._transition_timer.timeout.connect(self._start_transition)
            self._transition_timer.start(1500)  # Restart transition every 1.5s
            
        except Exception as e:
            print(f"  [SKIP] GLCompositorTransition test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _start_transition(self) -> None:
        if self._compositor is None:
            return
        try:
            # Use the compositor's slide transition with shorter duration
            self._compositor.start_slide_transition(
                self._pix2 if hasattr(self, '_use_pix2') and self._use_pix2 else self._pix1,
                duration_ms=1000,  # Shorter to test completion more often
                direction="right",
            )
            self._use_pix2 = not getattr(self, '_use_pix2', False)
        except Exception:
            pass
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        if hasattr(self, '_transition_timer') and self._transition_timer:
            self._transition_timer.stop()
            self._transition_timer = None
        if self._animation_manager:
            try:
                self._animation_manager.stop()
            except Exception:
                pass
            self._animation_manager = None
        if self._compositor:
            try:
                self._compositor.hide()
                self._compositor.deleteLater()
            except Exception:
                pass
            self._compositor = None


class FullAppSimulationTest:
    """Simulate full app: 2 visualizers + 2 GL overlays + media widget + transitions."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="FullAppSimulation")
        self._widgets = []
        self._overlays = []
        self._measure_timer: Optional[QTimer] = None
        self._update_timer: Optional[QTimer] = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
            from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
            from widgets.media_widget import MediaWidget
            from core.media.media_controller import create_media_controller
            from PySide6.QtCore import QRect
            from PySide6.QtGui import QColor
            
            # Create 2 visualizers
            for i in range(2):
                vis = SpotifyVisualizerWidget(parent)
                vis.setGeometry(20 + i * 320, 20, 300, 150)
                vis._thread_manager = thread_manager
                vis.show()
                vis.start()
                self._widgets.append(vis)
            
            # Create 2 GL overlays
            for i in range(2):
                overlay = SpotifyBarsGLOverlay(parent)
                overlay.setGeometry(20 + i * 320, 180, 300, 150)
                overlay.show()
                self._overlays.append(overlay)
            
            # Create media widget
            controller = create_media_controller()
            media = MediaWidget(parent=parent, controller=controller)
            media.setGeometry(20, 350, 400, 100)
            media._thread_manager = thread_manager
            media.show()
            self._widgets.append(media)
            
            self._bar_count = 16
            self._bars = [0.5] * self._bar_count
            
            # Update timer for overlays
            self._update_timer = QTimer()
            self._update_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._update_timer.timeout.connect(self._on_update)
            self._update_timer.start(16)
            
            # Measurement timer
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
        except Exception as e:
            print(f"  [SKIP] FullAppSimulation test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_update(self) -> None:
        import random
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor
        
        for i in range(self._bar_count):
            self._bars[i] = random.random()
        
        for idx, overlay in enumerate(self._overlays):
            try:
                overlay.set_state(
                    rect=QRect(20 + idx * 320, 180, 300, 150),
                    bars=self._bars,
                    bar_count=self._bar_count,
                    segments=8,
                    fill_color=QColor(0, 255, 0),
                    border_color=QColor(0, 200, 0),
                    fade=1.0,
                    playing=True,
                    visible=True,
                )
            except Exception:
                pass
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer = None
        for widget in self._widgets:
            try:
                if hasattr(widget, 'stop'):
                    widget.stop()
                widget.hide()
                widget.deleteLater()
            except Exception:
                pass
        self._widgets.clear()
        for overlay in self._overlays:
            try:
                overlay.hide()
                overlay.deleteLater()
            except Exception:
                pass
        self._overlays.clear()


class ImageLoadingTest:
    """Test image loading pipeline (the async image loader)."""
    
    def __init__(self):
        self.metrics = ComponentMetrics(name="ImageLoading")
        self._measure_timer: Optional[QTimer] = None
        self._load_timer: Optional[QTimer] = None
        self._thread_manager = None
    
    def start(self, parent: QWidget, thread_manager: ThreadManager) -> None:
        try:
            from PySide6.QtGui import QImage, QPixmap
            import os
            
            self._thread_manager = thread_manager
            self._parent = parent
            
            # Find some test images
            self._test_images = []
            wallpaper_dir = os.path.expanduser("~\\Documents\\[4] WALLPAPERS\\PERSONALSET")
            if os.path.exists(wallpaper_dir):
                for f in os.listdir(wallpaper_dir)[:10]:  # First 10 images
                    if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                        self._test_images.append(os.path.join(wallpaper_dir, f))
            
            if not self._test_images:
                print(f"  [WARN] No test images found in {wallpaper_dir}")
            
            self._current_idx = 0
            
            # Timer to trigger image loads
            self._load_timer = QTimer()
            self._load_timer.timeout.connect(self._load_next_image)
            self._load_timer.start(500)  # Load an image every 500ms
            
            # Measurement timer
            self._measure_timer = QTimer()
            self._measure_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._measure_timer.timeout.connect(self._on_measure)
            self._measure_timer.start(16)
            
        except Exception as e:
            print(f"  [SKIP] ImageLoading test - error: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_next_image(self) -> None:
        if not self._test_images:
            return
        
        path = self._test_images[self._current_idx % len(self._test_images)]
        self._current_idx += 1
        
        def _load():
            from PySide6.QtGui import QImage, QPixmap
            img = QImage(path)
            if not img.isNull():
                # Scale to 1920x1080
                scaled = img.scaled(1920, 1080)
                pix = QPixmap.fromImage(scaled)
                return pix
            return None
        
        def _on_done(result):
            pass  # Just discard the result
        
        if self._thread_manager:
            self._thread_manager.submit_io_task(_load, callback=_on_done)
    
    def _on_measure(self) -> None:
        self.metrics.record_tick()
    
    def stop(self) -> None:
        if self._measure_timer:
            self._measure_timer.stop()
            self._measure_timer = None
        if self._load_timer:
            self._load_timer.stop()
            self._load_timer = None


def run_test(name: str, test_obj, duration_sec: float, parent: QWidget, 
             thread_manager: Optional[ThreadManager] = None) -> ComponentMetrics:
    """Run a single test for the specified duration."""
    print(f"\n[TEST] {name} for {duration_sec}s...")
    
    if hasattr(test_obj, 'start'):
        if thread_manager and 'thread_manager' in test_obj.start.__code__.co_varnames:
            test_obj.start(parent, thread_manager)
        elif 'parent' in test_obj.start.__code__.co_varnames:
            test_obj.start(parent)
        else:
            test_obj.start()
    
    # Process events for the duration
    app = QApplication.instance()
    start_time = time.perf_counter()
    while (time.perf_counter() - start_time) < duration_sec:
        app.processEvents()
        time.sleep(0.001)  # Small sleep to not spin CPU
    
    if hasattr(test_obj, 'stop'):
        test_obj.stop()
    
    print(f"  {test_obj.metrics.report()}")
    return test_obj.metrics


def main():
    """Run all performance tests."""
    print("=" * 70)
    print("PERFORMANCE INTEGRATION TEST")
    print("=" * 70)
    
    # Initialize Qt
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create a parent widget
    parent = QWidget()
    parent.setGeometry(100, 100, 800, 600)
    parent.setWindowTitle("Performance Test")
    parent.show()
    
    # Initialize ThreadManager
    thread_manager = ThreadManager()
    
    # Force GC before tests
    gc.collect()
    
    test_duration = 5.0  # seconds per test
    results = []
    
    # Test 1: Isolated timer (baseline)
    test1 = IsolatedTimerTest(interval_ms=16)
    results.append(run_test("Isolated 16ms Timer", test1, test_duration, parent))
    gc.collect()
    
    # Test 2: Multiple timers (simulates real app)
    test2 = MultiTimerTest(timer_count=6, interval_ms=16)
    results.append(run_test("6x 16ms Timers", test2, test_duration, parent))
    gc.collect()
    
    # Test 3: GL widget updates
    test3 = GLWidgetTest(interval_ms=16)
    results.append(run_test("GL Widget Updates", test3, test_duration, parent))
    gc.collect()
    
    # Test 4: Visualizer WITHOUT audio (isolate audio from UI)
    test4 = VisualizerNoAudioTest()
    results.append(run_test("Visualizer (No Audio)", test4, test_duration, parent, thread_manager))
    gc.collect()
    
    # Test 5: Actual visualizer WITH audio
    test5 = VisualizerTest()
    results.append(run_test("Visualizer (With Audio)", test5, test_duration, parent, thread_manager))
    gc.collect()
    
    # Test 6: GL Overlay directly (the GPU bar rendering path)
    test6 = VisualizerWithGLOverlayTest()
    results.append(run_test("GL Overlay (Bars)", test6, test_duration, parent, thread_manager))
    gc.collect()
    
    # Test 7: Two visualizers (simulates 2-display setup)
    test7 = TwoVisualizersTest()
    results.append(run_test("Two Visualizers", test7, test_duration, parent, thread_manager))
    gc.collect()
    
    # Test 8: Media widget (GSMTC polling)
    test8 = MediaWidgetTest()
    results.append(run_test("Media Widget", test8, test_duration, parent, thread_manager))
    gc.collect()
    
    # Test 9: GL Compositor with transitions
    test9 = GLCompositorTransitionTest()
    results.append(run_test("GL Compositor + Transitions", test9, 10.0, parent, thread_manager))
    gc.collect()
    
    # Test 10: Full app simulation
    test10 = FullAppSimulationTest()
    results.append(run_test("Full App Simulation", test10, 15.0, parent, thread_manager))
    gc.collect()
    
    # Test 11: Image loading pipeline
    test11 = ImageLoadingTest()
    results.append(run_test("Image Loading", test11, 10.0, parent, thread_manager))
    gc.collect()
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_pass = True
    for metrics in results:
        status = "PASS" if metrics.dt_max_ms < 50.0 else "FAIL"
        if metrics.dt_max_ms >= 50.0:
            all_pass = False
        print(f"  [{status}] {metrics.name}: dt_max={metrics.dt_max_ms:.2f}ms")
    
    print("\n" + "=" * 70)
    if all_pass:
        print("RESULT: ALL TESTS PASSED")
    else:
        print("RESULT: SOME TESTS FAILED - UI THREAD BLOCKING DETECTED")
    print("=" * 70)
    
    # Cleanup
    parent.hide()
    parent.deleteLater()
    thread_manager.shutdown()
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
