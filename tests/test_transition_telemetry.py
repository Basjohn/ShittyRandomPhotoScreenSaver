"""
Tests for transition telemetry tracking (Phase 2.2).

Tests the performance timing tracking added to base transition class
and all transition implementations.
"""
import pytest
import time
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from transitions.base_transition import BaseTransition


@pytest.fixture
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def dummy_widget(qapp):
    """Create a dummy widget for testing."""
    widget = QWidget()
    widget.setGeometry(0, 0, 100, 100)
    yield widget
    widget.close()


@pytest.fixture
def dummy_pixmap():
    """Create a small test pixmap."""
    pm = QPixmap(10, 10)
    pm.fill(Qt.GlobalColor.black)
    return pm


class TestBaseTelemetry:
    """Test base transition telemetry methods."""
    
    def test_transition_has_telemetry_fields(self):
        """Base transition should have telemetry fields."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        assert hasattr(trans, '_start_time')
        assert hasattr(trans, '_end_time')
        assert trans._start_time is None
        assert trans._end_time is None
    
    def test_mark_start_sets_time(self):
        """_mark_start should set start time."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        trans._mark_start()
        
        assert trans._start_time is not None
        assert isinstance(trans._start_time, float)
    
    def test_mark_end_sets_time(self):
        """_mark_end should set end time."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        trans._mark_start()
        time.sleep(0.01)
        trans._mark_end()
        
        assert trans._end_time is not None
        assert trans._end_time > trans._start_time
    
    def test_get_elapsed_ms_returns_none_without_start(self):
        """get_elapsed_ms should return None if not started."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        elapsed = trans.get_elapsed_ms()
        
        assert elapsed is None
    
    def test_get_elapsed_ms_returns_time_after_start(self):
        """get_elapsed_ms should return elapsed time after start."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        trans._mark_start()
        time.sleep(0.05)  # 50ms
        
        elapsed = trans.get_elapsed_ms()
        
        assert elapsed is not None
        assert 40 < elapsed < 100  # Should be ~50ms with tolerance


class TestTelemetryLogging:
    """Test telemetry logging behavior."""
    
    def test_mark_start_logs_debug(self, caplog):
        """_mark_start should log debug message."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        with caplog.at_level("DEBUG"):
            trans._mark_start()
        
        # Check for PERF log
        perf_logs = [r for r in caplog.records if "[PERF]" in r.message]
        assert len(perf_logs) > 0
    
    def test_mark_end_logs_performance(self, caplog):
        """_mark_end should log performance metrics."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        trans._mark_start()
        time.sleep(0.05)
        
        with caplog.at_level("INFO"):
            trans._mark_end()
        
        # Should log completion time
        perf_logs = [r for r in caplog.records if "[PERF]" in r.message and "completed" in r.message]
        assert len(perf_logs) > 0
    
    def test_mark_end_warns_on_timing_drift(self, caplog):
        """_mark_end should warn if actual time differs from expected."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=100)  # Expect 100ms
        trans._mark_start()
        time.sleep(0.2)  # Actually take 200ms
        
        with caplog.at_level("WARNING"):
            trans._mark_end()
        
        # Should log timing drift warning
        drift_logs = [r for r in caplog.records if "TIMING DRIFT" in r.message]
        assert len(drift_logs) > 0


class TestGLTransitionTelemetry:
    """Test GL transition telemetry integration."""
    
    def test_gl_crossfade_calls_mark_start(self, qapp, dummy_widget, dummy_pixmap):
        """GL Crossfade should call _mark_start on transition start."""
        from transitions.gl_crossfade_transition import GLCrossfadeTransition
        
        trans = GLCrossfadeTransition(duration_ms=1000)
        
        trans.start(dummy_pixmap, dummy_pixmap, dummy_widget)
        
        # Should have start time set
        assert trans._start_time is not None
    
    def test_gl_crossfade_calls_mark_end_on_complete(self, qapp, dummy_widget, dummy_pixmap):
        """GL Crossfade should call _mark_end when animation completes."""
        from transitions.gl_crossfade_transition import GLCrossfadeTransition
        
        trans = GLCrossfadeTransition(duration_ms=100)
        trans.start(dummy_pixmap, dummy_pixmap, dummy_widget)
        
        # Manually trigger completion
        trans._on_anim_complete()
        
        # Should have end time set
        assert trans._end_time is not None


class TestSWTransitionTelemetry:
    """Test SW transition telemetry integration."""
    
    def test_sw_crossfade_has_telemetry(self, qapp, dummy_widget, dummy_pixmap):
        """SW Crossfade should have telemetry tracking."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        assert hasattr(trans, '_mark_start')
        assert hasattr(trans, '_mark_end')
        assert hasattr(trans, 'get_elapsed_ms')


class TestPerformanceMetrics:
    """Test actual performance measurement."""
    
    def test_elapsed_time_accuracy(self):
        """Elapsed time calculation should be accurate."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=1000)
        
        trans._mark_start()
        sleep_time = 0.1  # 100ms
        time.sleep(sleep_time)
        
        elapsed = trans.get_elapsed_ms()
        
        # Should be within 20ms of expected
        assert abs(elapsed - (sleep_time * 1000)) < 20
    
    def test_delta_calculation(self):
        """Delta from expected duration should be calculated."""
        from transitions.crossfade_transition import CrossfadeTransition
        
        trans = CrossfadeTransition(duration_ms=100)
        trans._mark_start()
        time.sleep(0.15)  # 150ms actual vs 100ms expected
        trans._mark_end()
        
        # Delta should be ~50ms
        delta = (trans._end_time - trans._start_time) * 1000 - trans.duration_ms
        assert 30 < delta < 70  # ~50ms with tolerance


class TestTelemetryThreadSafety:
    """Test telemetry in multi-threaded context."""
    
    def test_elapsed_time_thread_safe(self):
        """get_elapsed_ms should be safe to call from multiple threads."""
        from transitions.crossfade_transition import CrossfadeTransition
        import threading
        
        trans = CrossfadeTransition(duration_ms=1000)
        trans._mark_start()
        
        results = []
        errors = []
        
        def check_elapsed():
            try:
                for _ in range(50):
                    elapsed = trans.get_elapsed_ms()
                    results.append(elapsed)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Spawn threads
        threads = [threading.Thread(target=check_elapsed) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 150  # 3 threads × 50 checks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
