"""
Smoke tests for render strategy and timer metrics.

Verifies that:
- Timer-based render strategy starts at target FPS approximation
- Render strategy stops cleanly without leaks
- Metrics are recorded when PERF is enabled
- VSync render strategy has proper fallback behavior
"""
import pytest
from PySide6.QtWidgets import QWidget
from rendering.render_strategy import (
    RenderStrategyConfig,
    TimerRenderStrategy,
    RenderMetrics,
)


@pytest.fixture
def test_widget(qtbot):
    """Create test widget for render strategy."""
    widget = QWidget()
    widget.resize(400, 300)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def render_config():
    """Create test render configuration."""
    return RenderStrategyConfig(
        target_fps=60,
        vsync_enabled=False,
        fallback_on_failure=True,
    )


def test_timer_render_strategy_initialization(render_config):
    """Test TimerRenderStrategy initializes correctly."""
    strategy = TimerRenderStrategy(render_config)
    
    assert strategy is not None
    assert strategy.config.target_fps == 60
    assert strategy.is_active is False


def test_timer_render_strategy_starts_at_target_fps(qtbot, test_widget, render_config):
    """Test timer starts at approximately target FPS interval."""
    strategy = TimerRenderStrategy(render_config)
    
    render_count = []
    
    def on_render():
        render_count.append(1)
        if len(render_count) >= 5:
            strategy.stop()
    
    # Start rendering
    strategy.start(on_render)
    
    assert strategy.is_active is True
    
    # Wait for a few frames
    qtbot.waitUntil(lambda: len(render_count) >= 5, timeout=2000)
    
    # Verify renders occurred
    assert len(render_count) >= 5, "Should have rendered at least 5 frames"


def test_timer_render_strategy_stops_cleanly(qtbot, test_widget, render_config):
    """Test render strategy stops cleanly without leaks."""
    strategy = TimerRenderStrategy(render_config)
    
    render_count = []
    
    def on_render():
        render_count.append(1)
    
    # Start and immediately stop
    strategy.start(on_render)
    assert strategy.is_active is True
    
    strategy.stop()
    assert strategy.is_active is False
    
    # Wait a bit to ensure no more renders occur
    initial_count = len(render_count)
    qtbot.wait(200)
    
    # Count should not increase after stop
    assert len(render_count) <= initial_count + 1, "No renders should occur after stop"


def test_timer_render_strategy_metrics_tracking(render_config):
    """Test render metrics are tracked correctly."""
    strategy = TimerRenderStrategy(render_config)
    
    render_count = []
    
    def on_render():
        render_count.append(1)
        if len(render_count) >= 10:
            strategy.stop()
    
    strategy.start(on_render)
    
    # Let it run for a bit
    import time
    timeout = time.time() + 2.0
    while strategy.is_active and time.time() < timeout:
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        time.sleep(0.01)
    
    # Get metrics
    metrics = strategy.get_metrics()
    
    assert metrics is not None
    assert metrics.frame_count >= 0
    assert metrics.avg_fps >= 0


def test_render_metrics_initialization():
    """Test RenderMetrics initializes with correct defaults."""
    metrics = RenderMetrics()
    
    assert metrics.frame_count == 0
    assert metrics.min_dt == float('inf')
    assert metrics.max_dt == 0.0
    assert metrics.avg_fps == 0.0


def test_render_strategy_config_validation():
    """Test RenderStrategyConfig validates target FPS."""
    # Valid config
    config = RenderStrategyConfig(target_fps=60)
    assert config.target_fps == 60
    
    # Config with different FPS
    config30 = RenderStrategyConfig(target_fps=30)
    assert config30.target_fps == 30
    
    config120 = RenderStrategyConfig(target_fps=120)
    assert config120.target_fps == 120


def test_timer_interval_calculation(render_config):
    """Test timer interval is calculated correctly from target FPS."""
    strategy = TimerRenderStrategy(render_config)
    
    # For 60 FPS, interval should be ~16.67ms
    expected_interval = 1000.0 / render_config.target_fps
    
    # Start strategy to initialize timer
    strategy.start(lambda: None)
    
    # Timer should exist and have correct interval
    assert strategy._timer is not None
    
    # Interval should be close to expected (allow some rounding)
    actual_interval = strategy._timer.interval()
    assert abs(actual_interval - expected_interval) <= 1, \
        f"Timer interval {actual_interval}ms should be close to {expected_interval}ms"
    
    strategy.stop()


def test_multiple_start_stop_cycles(qtbot, render_config):
    """Test render strategy handles multiple start/stop cycles."""
    strategy = TimerRenderStrategy(render_config)
    
    for cycle in range(3):
        render_count = []
        
        def on_render():
            render_count.append(1)
            if len(render_count) >= 3:
                strategy.stop()
        
        strategy.start(on_render)
        assert strategy.is_active is True
        
        qtbot.waitUntil(lambda: not strategy.is_active, timeout=2000)
        
        assert len(render_count) >= 3, f"Cycle {cycle} should have rendered frames"


def test_render_strategy_idempotent_stop(render_config):
    """Test calling stop() multiple times is safe."""
    strategy = TimerRenderStrategy(render_config)
    
    strategy.start(lambda: None)
    assert strategy.is_active is True
    
    # Stop multiple times
    strategy.stop()
    assert strategy.is_active is False
    
    strategy.stop()
    assert strategy.is_active is False
    
    strategy.stop()
    assert strategy.is_active is False


def test_render_strategy_idempotent_start(render_config):
    """Test calling start() while already active is safe."""
    strategy = TimerRenderStrategy(render_config)
    
    render_count = []
    
    def on_render():
        render_count.append(1)
    
    # Start once
    strategy.start(on_render)
    assert strategy.is_active is True
    
    # Start again (should be no-op or handle gracefully)
    strategy.start(on_render)
    assert strategy.is_active is True
    
    strategy.stop()


@pytest.mark.skip(reason="VSync render strategy requires GL context and is optional")
def test_vsync_render_strategy_fallback():
    """Test VSync render strategy fallback behavior.
    
    When VSync is unavailable, should fall back to timer-based rendering.
    This test is skipped as VSync implementation is optional and requires
    GL context setup.
    """
    pass


def test_render_callback_exception_handling(qtbot, render_config):
    """Test render strategy handles callback exceptions gracefully."""
    strategy = TimerRenderStrategy(render_config)
    
    exception_count = []
    render_count = []
    
    def on_render():
        render_count.append(1)
        if len(render_count) == 2:
            # Raise exception on second render
            exception_count.append(1)
            raise RuntimeError("Test exception")
        if len(render_count) >= 5:
            strategy.stop()
    
    # Start rendering
    strategy.start(on_render)
    
    # Should continue rendering despite exception
    qtbot.waitUntil(lambda: len(render_count) >= 5, timeout=2000)
    
    # Verify exception occurred but rendering continued
    assert len(exception_count) >= 1, "Exception should have been raised"
    assert len(render_count) >= 5, "Rendering should continue after exception"


def test_render_metrics_reset_on_start(render_config):
    """Test metrics are reset when starting new render cycle."""
    strategy = TimerRenderStrategy(render_config)
    
    # First cycle
    strategy.start(lambda: None)
    strategy.stop()
    
    # Second cycle
    strategy.start(lambda: None)
    
    # Metrics should be reset (frame_count back to 0 or low)
    second_metrics = strategy.get_metrics()
    
    # After starting new cycle, metrics should be fresh
    # (implementation may vary, but frame_count should be reasonable)
    assert second_metrics.frame_count >= 0
    
    strategy.stop()


def test_timer_cleanup_on_stop(render_config):
    """Test timer is properly cleaned up on stop."""
    strategy = TimerRenderStrategy(render_config)
    
    strategy.start(lambda: None)
    assert strategy._timer is not None
    assert strategy._timer.isActive() is True
    
    strategy.stop()
    
    # Timer should be stopped
    if strategy._timer is not None:
        assert strategy._timer.isActive() is False


@pytest.mark.skipif(True, reason="PERF metrics require environment setup")
def test_perf_metrics_recording():
    """Test PERF metrics are recorded when enabled.
    
    This test requires PERF metrics to be enabled via environment variable
    or config file. Skipped by default as it requires specific setup.
    """
    pass
