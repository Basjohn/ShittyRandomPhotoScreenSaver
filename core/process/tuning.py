"""
Performance Tuning Configuration for Worker Processes.

Provides centralized configuration for queue sizes, backpressure policies,
and latency targets across all worker types.

Design Goals:
- Minimize dt_max impact on UI thread (target < 100ms)
- Optimize queue depth vs memory tradeoff
- Support drop-old backpressure for non-critical workers
- Enable per-worker type tuning based on workload characteristics
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict

from core.process.types import WorkerType
from core.logging.logger import get_logger

logger = get_logger(__name__)


class BackpressurePolicy(Enum):
    """Backpressure handling policy for worker queues."""
    BLOCK = auto()      # Block sender until queue has space (default)
    DROP_OLD = auto()   # Drop oldest message when queue full
    DROP_NEW = auto()   # Reject new message when queue full


@dataclass
class WorkerTuningConfig:
    """Tuning configuration for a single worker type."""
    
    # Queue sizes
    request_queue_size: int = 64
    response_queue_size: int = 64
    
    # Backpressure
    backpressure_policy: BackpressurePolicy = BackpressurePolicy.DROP_OLD
    
    # Timing
    poll_timeout_ms: int = 10
    heartbeat_interval_ms: int = 5000
    heartbeat_timeout_ms: int = 15000
    
    # Restart policy
    max_restart_attempts: int = 3
    restart_backoff_base_ms: int = 1000
    restart_backoff_max_ms: int = 30000
    
    # Latency targets
    target_latency_ms: int = 50
    max_latency_ms: int = 100


# Default configurations per worker type
_DEFAULT_CONFIGS: Dict[WorkerType, WorkerTuningConfig] = {
    WorkerType.IMAGE: WorkerTuningConfig(
        request_queue_size=32,      # Images are large, limit queue depth
        response_queue_size=16,     # Processed images consume memory
        backpressure_policy=BackpressurePolicy.DROP_OLD,
        target_latency_ms=100,      # Image decode can be slow
        max_latency_ms=500,
    ),
    WorkerType.RSS: WorkerTuningConfig(
        request_queue_size=16,      # RSS fetches are infrequent
        response_queue_size=32,     # Multiple images per feed
        backpressure_policy=BackpressurePolicy.DROP_OLD,
        target_latency_ms=1000,     # Network latency expected
        max_latency_ms=10000,
    ),
    WorkerType.FFT: WorkerTuningConfig(
        request_queue_size=128,     # High-frequency audio frames
        response_queue_size=64,     # Bar data is small
        backpressure_policy=BackpressurePolicy.DROP_OLD,
        poll_timeout_ms=5,          # Low latency for audio
        target_latency_ms=16,       # 60fps target
        max_latency_ms=33,          # 30fps minimum
    ),
    WorkerType.TRANSITION: WorkerTuningConfig(
        request_queue_size=8,       # Precompute requests are rare
        response_queue_size=8,      # Precomputed data cached
        backpressure_policy=BackpressurePolicy.DROP_NEW,
        target_latency_ms=200,      # Precompute can be slow
        max_latency_ms=1000,
    ),
}


def get_worker_config(worker_type: WorkerType) -> WorkerTuningConfig:
    """
    Get tuning configuration for a worker type.
    
    Args:
        worker_type: The worker type to get config for
        
    Returns:
        WorkerTuningConfig for the specified worker type
    """
    return _DEFAULT_CONFIGS.get(worker_type, WorkerTuningConfig())


def get_all_configs() -> Dict[WorkerType, WorkerTuningConfig]:
    """Get all worker tuning configurations."""
    return dict(_DEFAULT_CONFIGS)


@dataclass
class LatencyMetrics:
    """Latency metrics for a worker."""
    
    worker_type: WorkerType
    sample_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    
    def record(self, latency_ms: float) -> None:
        """Record a latency sample."""
        self.sample_count += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
    
    @property
    def avg_latency_ms(self) -> float:
        """Get average latency."""
        if self.sample_count == 0:
            return 0.0
        return self.total_latency_ms / self.sample_count
    
    def is_within_target(self, config: WorkerTuningConfig) -> bool:
        """Check if latency is within target."""
        return self.max_latency_ms <= config.max_latency_ms
    
    def reset(self) -> None:
        """Reset metrics."""
        self.sample_count = 0
        self.total_latency_ms = 0.0
        self.min_latency_ms = float('inf')
        self.max_latency_ms = 0.0


class LatencyMonitor:
    """
    Monitor latency metrics across all workers.
    
    Provides centralized latency tracking and alerting when
    workers exceed their configured latency targets.
    """
    
    def __init__(self):
        """Initialize the latency monitor."""
        self._metrics: Dict[WorkerType, LatencyMetrics] = {
            wt: LatencyMetrics(worker_type=wt) for wt in WorkerType
        }
        self._alert_callbacks: list = []
    
    def record_latency(self, worker_type: WorkerType, latency_ms: float) -> None:
        """
        Record a latency measurement.
        
        Args:
            worker_type: The worker type
            latency_ms: Latency in milliseconds
        """
        metrics = self._metrics.get(worker_type)
        if metrics is None:
            return
        
        metrics.record(latency_ms)
        
        # Check for threshold violation
        config = get_worker_config(worker_type)
        if latency_ms > config.max_latency_ms:
            self._trigger_alert(worker_type, latency_ms, config.max_latency_ms)
    
    def _trigger_alert(
        self, 
        worker_type: WorkerType, 
        latency_ms: float, 
        threshold_ms: float
    ) -> None:
        """Trigger latency alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                callback(worker_type, latency_ms, threshold_ms)
            except Exception as e:
                logger.debug("[MISC] Exception suppressed: %s", e)
    
    def register_alert_callback(self, callback) -> None:
        """Register a callback for latency alerts."""
        self._alert_callbacks.append(callback)
    
    def get_metrics(self, worker_type: WorkerType) -> LatencyMetrics:
        """Get metrics for a worker type."""
        return self._metrics.get(worker_type, LatencyMetrics(worker_type=worker_type))
    
    def get_all_metrics(self) -> Dict[WorkerType, LatencyMetrics]:
        """Get all metrics."""
        return dict(self._metrics)
    
    def reset_all(self) -> None:
        """Reset all metrics."""
        for metrics in self._metrics.values():
            metrics.reset()
    
    def get_summary(self) -> str:
        """Get a summary of all latency metrics."""
        lines = ["Worker Latency Summary:"]
        for wt, metrics in self._metrics.items():
            if metrics.sample_count == 0:
                continue
            config = get_worker_config(wt)
            status = "OK" if metrics.is_within_target(config) else "EXCEEDED"
            lines.append(
                f"  {wt.name}: avg={metrics.avg_latency_ms:.1f}ms, "
                f"max={metrics.max_latency_ms:.1f}ms, "
                f"target={config.target_latency_ms}ms [{status}]"
            )
        return "\n".join(lines)
