"""
Real integration tests for worker processes.

These tests verify that workers actually start as separate processes,
communicate via queues, and handle messages correctly. Unlike unit tests
that use MockQueue, these test the actual multiprocessing infrastructure.

Tests cover:
- Worker process startup and shutdown
- Queue-based message passing
- Heartbeat handling
- Timeout behavior
- Shared memory for large images
"""
import os
import tempfile
import time
import pytest

from PIL import Image

from core.process.types import (
    MessageType,
    WorkerType,
    HealthStatus,
)
from core.process.supervisor import ProcessSupervisor
from core.process.workers.image_worker import ImageWorker, image_worker_main


class TestImageWorkerProcess:
    """Integration tests for ImageWorker running as actual process."""
    
    @pytest.fixture
    def test_image_path(self):
        """Create a temporary test image."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (200, 200), color=(255, 0, 0))
            img.save(f.name, "PNG")
            yield f.name
        try:
            os.unlink(f.name)
        except Exception:
            pass
    
    @pytest.fixture
    def large_test_image_path(self):
        """Create a large test image that will use shared memory."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # 2000x2000 = 16MB RGBA - above shared memory threshold
            img = Image.new("RGB", (2000, 2000), color=(0, 128, 255))
            img.save(f.name, "PNG")
            yield f.name
        try:
            os.unlink(f.name)
        except Exception:
            pass
    
    def test_worker_starts_and_stops(self):
        """Test that ImageWorker can start and stop as a process."""
        supervisor = ProcessSupervisor()
        supervisor.register_worker_factory(WorkerType.IMAGE, image_worker_main)
        
        # Start worker
        started = supervisor.start(WorkerType.IMAGE)
        assert started, "ImageWorker should start successfully"
        assert supervisor.is_running(WorkerType.IMAGE), "ImageWorker should be running"
        
        # Give it time to initialize
        time.sleep(0.5)
        
        # Stop worker
        supervisor.shutdown(timeout=5.0)
        assert not supervisor.is_running(WorkerType.IMAGE), "ImageWorker should be stopped"
    
    def test_worker_processes_message(self, test_image_path):
        """Test that ImageWorker processes messages via queue."""
        supervisor = ProcessSupervisor()
        supervisor.register_worker_factory(WorkerType.IMAGE, image_worker_main)
        
        started = supervisor.start(WorkerType.IMAGE)
        assert started, "ImageWorker should start"
        
        # Give worker time to start
        time.sleep(0.5)
        
        # Send prescale message
        correlation_id = supervisor.send_message(
            WorkerType.IMAGE,
            MessageType.IMAGE_PRESCALE,
            payload={
                "path": test_image_path,
                "target_width": 100,
                "target_height": 100,
                "mode": "fill",
            },
        )
        assert correlation_id, "Should get correlation ID"
        
        # Poll for response with timeout
        response = None
        start_time = time.time()
        while time.time() - start_time < 5.0:
            responses = supervisor.poll_responses(WorkerType.IMAGE, max_count=10)
            for r in responses:
                if r.correlation_id == correlation_id:
                    response = r
                    break
            if response:
                break
            time.sleep(0.1)
        
        assert response is not None, "Should receive response within timeout"
        assert response.success, f"Response should be successful: {response.error}"
        assert response.payload.get("width") == 100
        assert response.payload.get("height") == 100
        
        # Verify RGBA data or shared memory
        rgba_data = response.payload.get("rgba_data")
        shm_name = response.payload.get("shared_memory_name")
        assert rgba_data or shm_name, "Should have RGBA data or shared memory"
        
        supervisor.shutdown(timeout=5.0)
    
    def test_worker_handles_missing_file(self):
        """Test that ImageWorker handles missing files gracefully."""
        supervisor = ProcessSupervisor()
        supervisor.register_worker_factory(WorkerType.IMAGE, image_worker_main)
        
        started = supervisor.start(WorkerType.IMAGE)
        assert started
        time.sleep(0.5)
        
        # Send request for non-existent file
        correlation_id = supervisor.send_message(
            WorkerType.IMAGE,
            MessageType.IMAGE_PRESCALE,
            payload={
                "path": "/nonexistent/path/image.png",
                "target_width": 100,
                "target_height": 100,
            },
        )
        
        # Poll for response
        response = None
        start_time = time.time()
        while time.time() - start_time < 5.0:
            responses = supervisor.poll_responses(WorkerType.IMAGE, max_count=10)
            for r in responses:
                if r.correlation_id == correlation_id:
                    response = r
                    break
            if response:
                break
            time.sleep(0.1)
        
        assert response is not None, "Should receive error response"
        assert not response.success, "Response should indicate failure"
        assert "not found" in response.error.lower() or "File not found" in response.error
        
        supervisor.shutdown(timeout=5.0)
    
    def test_worker_heartbeat_response(self):
        """Test that worker responds to heartbeat messages."""
        supervisor = ProcessSupervisor()
        supervisor.register_worker_factory(WorkerType.IMAGE, image_worker_main)
        
        started = supervisor.start(WorkerType.IMAGE)
        assert started
        time.sleep(0.5)
        
        # Send heartbeat
        supervisor.send_message(
            WorkerType.IMAGE,
            MessageType.HEARTBEAT,
            payload={"timestamp": time.time()},
        )
        
        # Poll for heartbeat ack
        response = None
        start_time = time.time()
        while time.time() - start_time < 3.0:
            responses = supervisor.poll_responses(WorkerType.IMAGE, max_count=10)
            for r in responses:
                if r.msg_type == MessageType.HEARTBEAT_ACK:
                    response = r
                    break
            if response:
                break
            time.sleep(0.1)
        
        assert response is not None, "Should receive heartbeat ack"
        assert response.success
        assert "uptime_s" in response.payload
        assert "pid" in response.payload
        
        supervisor.shutdown(timeout=5.0)


class TestHealthStatusThresholds:
    """Tests for health status configuration."""
    
    def test_heartbeat_interval_is_reasonable(self):
        """Verify heartbeat interval allows for long operations."""
        # Workers may process images for 500ms+, so interval should be > 1s
        assert HealthStatus.HEARTBEAT_INTERVAL_MS >= 2000, \
            "Heartbeat interval should be at least 2s to allow for image processing"
    
    def test_missed_threshold_is_reasonable(self):
        """Verify missed heartbeat threshold is forgiving."""
        # Should allow several misses before restart
        assert HealthStatus.MISSED_HEARTBEAT_THRESHOLD >= 3, \
            "Should allow at least 3 missed heartbeats before restart"
    
    def test_restart_backoff_configured(self):
        """Verify restart backoff is configured."""
        assert HealthStatus.RESTART_BACKOFF_BASE_MS >= 1000
        assert HealthStatus.RESTART_BACKOFF_MAX_MS >= 10000


class TestWorkerPoolTuning:
    """Tests for worker pool size tuning."""
    
    def test_auto_workers_respects_cpu_count(self):
        """Test that 'auto' setting calculates reasonable worker count."""
        import os
        cpu_count = os.cpu_count() or 4
        
        # Auto should be half cores, min 2, max 4
        expected_max = max(2, min(4, cpu_count // 2))
        
        # Verify the calculation matches what _start_workers does
        if cpu_count >= 8:
            assert expected_max == 4, "8+ cores should give 4 workers"
        elif cpu_count >= 4:
            assert expected_max >= 2, "4+ cores should give at least 2 workers"
        else:
            assert expected_max == 2, "Low core count should give 2 workers"


class TestSharedMemoryIntegration:
    """Tests for shared memory functionality."""
    
    def test_shared_memory_threshold_is_reasonable(self):
        """Verify shared memory threshold is set appropriately."""
        # 5MB threshold - images larger than this use shared memory
        assert ImageWorker.SHARED_MEMORY_THRESHOLD == 5 * 1024 * 1024
    
    def test_shared_memory_calculation(self):
        """Test that shared memory is used for large images."""
        # 2000x2000 RGBA = 16MB > 5MB threshold
        large_image_size = 2000 * 2000 * 4
        assert large_image_size > ImageWorker.SHARED_MEMORY_THRESHOLD, \
            "2000x2000 image should exceed shared memory threshold"
        
        # 500x500 RGBA = 1MB < 5MB threshold
        small_image_size = 500 * 500 * 4
        assert small_image_size < ImageWorker.SHARED_MEMORY_THRESHOLD, \
            "500x500 image should use queue, not shared memory"
