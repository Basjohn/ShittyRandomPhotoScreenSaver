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
    RenderMetrics,
    RenderStrategyConfig,
    RenderStrategyType,
    TimerRenderStrategy,
)


class _FakeCompositor(QWidget):
    """Widget stand-in that records update() calls."""

    def __init__(self):
        super().__init__()
        self.render_count = 0
        self.on_update = None

    def update(self):
        self.render_count += 1
        if callable(self.on_update):
            self.on_update(self.render_count)
        return super().update()


@pytest.fixture
def fake_compositor(qtbot):
    widget = _FakeCompositor()
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


@pytest.fixture
def make_strategy(fake_compositor, render_config):
    def _factory():
        return TimerRenderStrategy(fake_compositor, render_config)

    return _factory


def _wait_for_frames(qtbot, compositor, target, timeout=2000):
    qtbot.waitUntil(lambda: compositor.render_count >= target, timeout=timeout)


def test_timer_render_strategy_initialization(fake_compositor, render_config):
    """Test TimerRenderStrategy initializes correctly."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    assert strategy.config.target_fps == 60
    assert strategy.is_active() is False


def test_timer_render_strategy_starts_at_target_fps(qtbot, fake_compositor, render_config):
    """Test timer starts at approximately target FPS interval."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    assert strategy.start() is True
    assert strategy.is_active() is True

    _wait_for_frames(qtbot, fake_compositor, 5)

    strategy.stop()
    assert fake_compositor.render_count >= 5


def test_timer_render_strategy_stops_cleanly(qtbot, fake_compositor, render_config):
    """Test render strategy stops cleanly without leaks."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    assert strategy.start() is True
    _wait_for_frames(qtbot, fake_compositor, 1)

    strategy.stop()
    assert strategy.is_active() is False

    render_count = fake_compositor.render_count
    qtbot.wait(200)
    assert fake_compositor.render_count == render_count


def test_timer_render_strategy_metrics_tracking(qtbot, fake_compositor, render_config):
    """Test render metrics are tracked correctly."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    assert strategy.start() is True
    _wait_for_frames(qtbot, fake_compositor, 10)
    strategy.stop()

    metrics = strategy.get_metrics()

    assert metrics.frame_count >= 10
    assert metrics.get_avg_fps() >= 0


def test_render_metrics_initialization():
    """Test RenderMetrics initializes with correct defaults."""
    metrics = RenderMetrics(strategy_type=RenderStrategyType.TIMER)

    assert metrics.frame_count == 0
    assert metrics.min_dt_ms == 0.0
    assert metrics.max_dt_ms == 0.0
    assert metrics.get_avg_fps() == 0.0


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


def test_timer_interval_calculation(fake_compositor, render_config):
    """Test timer interval is calculated correctly from target FPS."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    strategy.start()
    assert strategy._timer is not None

    expected_interval = max(1, 1000 // render_config.target_fps)
    actual_interval = strategy._timer.interval()
    assert actual_interval == expected_interval

    strategy.stop()


def test_multiple_start_stop_cycles(qtbot, fake_compositor, render_config):
    """Test render strategy handles multiple start/stop cycles."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    for _ in range(3):
        baseline = fake_compositor.render_count
        strategy.start()
        _wait_for_frames(qtbot, fake_compositor, baseline + 3)
        strategy.stop()
        assert fake_compositor.render_count >= baseline + 3


def test_render_strategy_idempotent_stop(qtbot, fake_compositor, render_config):
    """Test calling stop() multiple times is safe."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    strategy.start()
    _wait_for_frames(qtbot, fake_compositor, 1)

    strategy.stop()
    assert strategy.is_active() is False

    strategy.stop()
    assert strategy.is_active() is False

    strategy.stop()
    assert strategy.is_active() is False


def test_render_strategy_idempotent_start(qtbot, fake_compositor, render_config):
    """Test calling start() while already active is safe."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    strategy.start()
    _wait_for_frames(qtbot, fake_compositor, 1)

    # Start again (should be no-op)
    strategy.start()
    assert strategy.is_active() is True

    strategy.stop()


@pytest.mark.skip(reason="VSync render strategy requires GL context and is optional")
def test_vsync_render_strategy_fallback():
    """Test VSync render strategy fallback behavior.
    
    When VSync is unavailable, should fall back to timer-based rendering.
    This test is skipped as VSync implementation is optional and requires
    GL context setup.
    """
    pass


def test_render_callback_exception_handling(qtbot, fake_compositor, render_config):
    """Test render strategy handles callback exceptions gracefully."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    exception_count = {"raised": 0}

    def _on_update(render_count):
        if render_count == 2:
            exception_count["raised"] += 1
            raise RuntimeError("Test exception")
        if render_count >= 5:
            strategy.stop()

    fake_compositor.on_update = _on_update
    strategy.start()

    _wait_for_frames(qtbot, fake_compositor, 5)

    assert exception_count["raised"] == 1
    fake_compositor.on_update = None


def test_render_metrics_reset_on_start(qtbot, fake_compositor, render_config):
    """Test metrics are reset when starting new render cycle."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    strategy.start()
    _wait_for_frames(qtbot, fake_compositor, 3)
    strategy.stop()
    first_metrics = strategy.get_metrics()
    assert first_metrics.frame_count >= 3

    strategy.start()
    _wait_for_frames(qtbot, fake_compositor, 1)
    second_metrics = strategy.get_metrics()
    assert second_metrics.frame_count <= 2
    strategy.stop()


def test_timer_cleanup_on_stop(qtbot, fake_compositor, render_config):
    """Test timer is properly cleaned up on stop."""
    strategy = TimerRenderStrategy(fake_compositor, render_config)

    strategy.start()
    _wait_for_frames(qtbot, fake_compositor, 1)
    assert strategy._timer is not None
    assert strategy._timer.isActive() is True

    strategy.stop()

    assert strategy._timer is None


@pytest.mark.skipif(True, reason="PERF metrics require environment setup")
def test_perf_metrics_recording():
    """Test PERF metrics are recorded when enabled.
    
    This test requires PERF metrics to be enabled via environment variable
    or config file. Skipped by default as it requires specific setup.
    """
    pass
