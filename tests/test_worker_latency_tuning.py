"""
Tests for Worker Latency Tuning Configuration.

Tests cover:
- Default configurations per worker type
- Backpressure policy settings
- Latency metrics recording
- Latency monitoring and alerts
"""
import pytest

from core.process.types import WorkerType
from core.process.tuning import (
    BackpressurePolicy,
    WorkerTuningConfig,
    LatencyMetrics,
    LatencyMonitor,
    get_worker_config,
    get_all_configs,
)


class TestBackpressurePolicy:
    """Tests for backpressure policy enum."""
    
    def test_policies_exist(self):
        """Test all expected policies exist."""
        assert BackpressurePolicy.BLOCK is not None
        assert BackpressurePolicy.DROP_OLD is not None
        assert BackpressurePolicy.DROP_NEW is not None


class TestWorkerTuningConfig:
    """Tests for worker tuning configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = WorkerTuningConfig()
        assert config.request_queue_size == 64
        assert config.response_queue_size == 64
        assert config.backpressure_policy == BackpressurePolicy.DROP_OLD
        assert config.poll_timeout_ms == 10
        assert config.target_latency_ms == 50
        assert config.max_latency_ms == 100
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = WorkerTuningConfig(
            request_queue_size=32,
            backpressure_policy=BackpressurePolicy.BLOCK,
            target_latency_ms=25,
        )
        assert config.request_queue_size == 32
        assert config.backpressure_policy == BackpressurePolicy.BLOCK
        assert config.target_latency_ms == 25


class TestGetWorkerConfig:
    """Tests for get_worker_config function."""
    
    def test_image_worker_config(self):
        """Test IMAGE worker has appropriate config."""
        config = get_worker_config(WorkerType.IMAGE)
        assert config.request_queue_size == 32
        assert config.backpressure_policy == BackpressurePolicy.DROP_OLD
        assert config.target_latency_ms == 100
    
    def test_rss_worker_config(self):
        """Test RSS worker has network-tolerant config."""
        config = get_worker_config(WorkerType.RSS)
        assert config.target_latency_ms == 1000
        assert config.max_latency_ms == 10000
    
    def test_transition_worker_config(self):
        """Test TRANSITION worker has precompute config."""
        config = get_worker_config(WorkerType.TRANSITION)
        assert config.request_queue_size == 8
        assert config.backpressure_policy == BackpressurePolicy.DROP_NEW


class TestGetAllConfigs:
    """Tests for get_all_configs function."""
    
    def test_returns_all_worker_types(self):
        """Test all worker types have configs."""
        configs = get_all_configs()
        for wt in WorkerType:
            assert wt in configs
    
    def test_returns_copy(self):
        """Test returns a copy, not the original."""
        configs1 = get_all_configs()
        configs2 = get_all_configs()
        assert configs1 is not configs2


class TestLatencyMetrics:
    """Tests for latency metrics tracking."""
    
    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = LatencyMetrics(worker_type=WorkerType.IMAGE)
        assert metrics.sample_count == 0
        assert metrics.total_latency_ms == 0.0
        assert metrics.avg_latency_ms == 0.0
    
    def test_record_single(self):
        """Test recording a single latency."""
        metrics = LatencyMetrics(worker_type=WorkerType.IMAGE)
        metrics.record(50.0)
        assert metrics.sample_count == 1
        assert metrics.avg_latency_ms == 50.0
        assert metrics.min_latency_ms == 50.0
        assert metrics.max_latency_ms == 50.0
    
    def test_record_multiple(self):
        """Test recording multiple latencies."""
        metrics = LatencyMetrics(worker_type=WorkerType.IMAGE)
        metrics.record(10.0)
        metrics.record(20.0)
        metrics.record(30.0)
        assert metrics.sample_count == 3
        assert metrics.avg_latency_ms == 20.0
        assert metrics.min_latency_ms == 10.0
        assert metrics.max_latency_ms == 30.0
    
    def test_is_within_target(self):
        """Test target checking."""
        config = WorkerTuningConfig(max_latency_ms=100)
        
        metrics = LatencyMetrics(worker_type=WorkerType.IMAGE)
        metrics.record(50.0)
        assert metrics.is_within_target(config) is True
        
        metrics.record(150.0)
        assert metrics.is_within_target(config) is False
    
    def test_reset(self):
        """Test resetting metrics."""
        metrics = LatencyMetrics(worker_type=WorkerType.IMAGE)
        metrics.record(50.0)
        metrics.reset()
        assert metrics.sample_count == 0
        assert metrics.total_latency_ms == 0.0


class TestLatencyMonitor:
    """Tests for latency monitor."""
    
    def test_initial_state(self):
        """Test initial monitor state."""
        monitor = LatencyMonitor()
        for wt in WorkerType:
            metrics = monitor.get_metrics(wt)
            assert metrics.sample_count == 0
    
    def test_record_latency(self):
        """Test recording latency through monitor."""
        monitor = LatencyMonitor()
        monitor.record_latency(WorkerType.IMAGE, 50.0)
        
        metrics = monitor.get_metrics(WorkerType.IMAGE)
        assert metrics.sample_count == 1
        assert metrics.avg_latency_ms == 50.0
    
    def test_alert_callback(self):
        """Test alert callback on threshold violation."""
        monitor = LatencyMonitor()
        
        alerts = []
        def on_alert(wt, latency, threshold):
            alerts.append((wt, latency, threshold))
        
        monitor.register_alert_callback(on_alert)
        
        # Record latency exceeding IMAGE max (500ms)
        monitor.record_latency(WorkerType.IMAGE, 600.0)
        
        assert len(alerts) == 1
        assert alerts[0][0] == WorkerType.IMAGE
        assert alerts[0][1] == 600.0
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        monitor = LatencyMonitor()
        monitor.record_latency(WorkerType.IMAGE, 50.0)
        monitor.record_latency(WorkerType.RSS, 10.0)
        
        all_metrics = monitor.get_all_metrics()
        assert WorkerType.IMAGE in all_metrics
        assert WorkerType.RSS in all_metrics
    
    def test_reset_all(self):
        """Test resetting all metrics."""
        monitor = LatencyMonitor()
        monitor.record_latency(WorkerType.IMAGE, 50.0)
        monitor.reset_all()
        
        metrics = monitor.get_metrics(WorkerType.IMAGE)
        assert metrics.sample_count == 0
    
    def test_get_summary(self):
        """Test getting summary string."""
        monitor = LatencyMonitor()
        monitor.record_latency(WorkerType.IMAGE, 50.0)
        
        summary = monitor.get_summary()
        assert "Worker Latency Summary" in summary
        assert "IMAGE" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
