"""
Tests for ProcessSupervisor and process isolation types.

Tests cover:
- Supervisor lifecycle (start/stop/restart)
- Health monitoring (heartbeat, missed heartbeat threshold)
- Message schema validation
- Shared memory header serialization
- Worker state transitions
"""
import pytest

from core.process.types import (
    HealthStatus,
    MessageType,
    RGBAHeader,
    SharedMemoryHeader,
    WorkerMessage,
    WorkerResponse,
    WorkerState,
    WorkerType,
)
from core.process.supervisor import ProcessSupervisor


class TestWorkerTypes:
    """Tests for WorkerType enum."""
    
    def test_worker_types_exist(self):
        """Verify all expected worker types are defined."""
        assert WorkerType.IMAGE.value == "image"
        assert WorkerType.RSS.value == "rss"
        assert WorkerType.TRANSITION.value == "transition"
    
    def test_worker_types_unique(self):
        """Verify all worker type values are unique."""
        values = [wt.value for wt in WorkerType]
        assert len(values) == len(set(values))


class TestWorkerState:
    """Tests for WorkerState enum."""
    
    def test_worker_states_exist(self):
        """Verify all expected worker states are defined."""
        states = [s.name for s in WorkerState]
        assert "STOPPED" in states
        assert "STARTING" in states
        assert "RUNNING" in states
        assert "STOPPING" in states
        assert "ERROR" in states
        assert "RESTARTING" in states


class TestMessageType:
    """Tests for MessageType enum."""
    
    def test_control_messages(self):
        """Verify control message types exist."""
        assert MessageType.SHUTDOWN.value == "shutdown"
        assert MessageType.HEARTBEAT.value == "heartbeat"
        assert MessageType.HEARTBEAT_ACK.value == "heartbeat_ack"
    
    def test_worker_specific_messages(self):
        """Verify worker-specific message types exist."""
        assert MessageType.IMAGE_DECODE.value == "image_decode"
        assert MessageType.RSS_FETCH.value == "rss_fetch"
        assert MessageType.TRANSITION_PRECOMPUTE.value == "transition_precompute"


class TestWorkerMessage:
    """Tests for WorkerMessage dataclass."""
    
    def test_message_creation(self):
        """Test creating a worker message."""
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,
            seq_no=1,
            correlation_id="test-123",
            payload={"path": "/test/image.jpg"},
            worker_type=WorkerType.IMAGE,
        )
        assert msg.msg_type == MessageType.IMAGE_DECODE
        assert msg.seq_no == 1
        assert msg.correlation_id == "test-123"
        assert msg.payload["path"] == "/test/image.jpg"
        assert msg.worker_type == WorkerType.IMAGE
        assert msg.timestamp > 0
    
    def test_message_serialization(self):
        """Test message to_dict and from_dict."""
        original = WorkerMessage(
            msg_type=MessageType.RSS_FETCH,
            seq_no=42,
            correlation_id="corr-456",
            payload={"feeds": ["feed1", "feed2"]},
            worker_type=WorkerType.RSS,
        )
        
        data = original.to_dict()
        restored = WorkerMessage.from_dict(data)
        
        assert restored.msg_type == original.msg_type
        assert restored.seq_no == original.seq_no
        assert restored.correlation_id == original.correlation_id
        assert restored.payload == original.payload
        assert restored.worker_type == original.worker_type
    
    def test_message_size_validation(self):
        """Test message size validation."""
        small_msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,
            seq_no=1,
            correlation_id="test",
            payload={"data": [0.0] * 100},
            worker_type=WorkerType.IMAGE,
        )
        assert small_msg.validate_size() is True


class TestWorkerResponse:
    """Tests for WorkerResponse dataclass."""
    
    def test_response_creation(self):
        """Test creating a worker response."""
        resp = WorkerResponse(
            msg_type=MessageType.IMAGE_RESULT,
            seq_no=1,
            correlation_id="test-123",
            success=True,
            payload={"width": 1920, "height": 1080},
            processing_time_ms=45.5,
        )
        assert resp.success is True
        assert resp.processing_time_ms == 45.5
        assert resp.error is None
    
    def test_response_error(self):
        """Test creating an error response."""
        resp = WorkerResponse(
            msg_type=MessageType.ERROR,
            seq_no=2,
            correlation_id="test-456",
            success=False,
            error="File not found",
            error_code=404,
        )
        assert resp.success is False
        assert resp.error == "File not found"
        assert resp.error_code == 404
    
    def test_response_serialization(self):
        """Test response to_dict and from_dict."""
        original = WorkerResponse(
            msg_type=MessageType.RSS_RESULT,
            seq_no=10,
            correlation_id="corr-789",
            success=True,
            payload={"items": 5},
            shm_handle="shm_test",
            processing_time_ms=123.4,
        )
        
        data = original.to_dict()
        restored = WorkerResponse.from_dict(data)
        
        assert restored.msg_type == original.msg_type
        assert restored.success == original.success
        assert restored.shm_handle == original.shm_handle
        assert restored.processing_time_ms == original.processing_time_ms


class TestSharedMemoryHeader:
    """Tests for SharedMemoryHeader serialization."""
    
    def test_header_creation(self):
        """Test creating a shared memory header."""
        header = SharedMemoryHeader(
            handle="shm_test_123",
            size_bytes=1024 * 1024,
            producer_pid=12345,
            generation=1,
        )
        assert header.handle == "shm_test_123"
        assert header.size_bytes == 1024 * 1024
        assert header.producer_pid == 12345
        assert header.generation == 1
        assert header.valid is True
    
    def test_header_serialization(self):
        """Test header to_bytes and from_bytes."""
        original = SharedMemoryHeader(
            handle="test_handle",
            size_bytes=2048,
            producer_pid=9999,
            generation=42,
            valid=True,
        )
        
        data = original.to_bytes()
        assert len(data) == SharedMemoryHeader.HEADER_SIZE
        
        restored = SharedMemoryHeader.from_bytes(data)
        assert restored.handle == original.handle
        assert restored.size_bytes == original.size_bytes
        assert restored.producer_pid == original.producer_pid
        assert restored.generation == original.generation
        assert restored.valid == original.valid


class TestRGBAHeader:
    """Tests for RGBAHeader serialization."""
    
    def test_rgba_header_creation(self):
        """Test creating an RGBA header."""
        header = RGBAHeader(
            handle="rgba_test",
            size_bytes=1920 * 1080 * 4,
            producer_pid=12345,
            generation=1,
            width=1920,
            height=1080,
            stride=1920 * 4,
            format="RGBA8",
        )
        assert header.width == 1920
        assert header.height == 1080
        assert header.format == "RGBA8"
    
    def test_rgba_header_serialization(self):
        """Test RGBA header to_bytes and from_bytes."""
        original = RGBAHeader(
            handle="rgba_shm",
            size_bytes=3840 * 2160 * 4,
            producer_pid=5678,
            generation=10,
            width=3840,
            height=2160,
            stride=3840 * 4,
            format="RGBA8",
        )
        
        data = original.to_bytes()
        assert len(data) == RGBAHeader.HEADER_SIZE
        
        restored = RGBAHeader.from_bytes(data)
        assert restored.width == original.width
        assert restored.height == original.height
        assert restored.stride == original.stride
        assert restored.format == original.format


class TestHealthStatus:
    """Tests for HealthStatus health monitoring."""
    
    def test_health_status_creation(self):
        """Test creating a health status."""
        health = HealthStatus(
            worker_type=WorkerType.IMAGE,
            state=WorkerState.RUNNING,
            pid=12345,
        )
        assert health.worker_type == WorkerType.IMAGE
        assert health.state == WorkerState.RUNNING
        assert health.pid == 12345
        assert health.missed_heartbeats == 0
        assert health.restart_count == 0
    
    def test_healthy_check(self):
        """Test is_healthy() method."""
        health = HealthStatus(
            worker_type=WorkerType.RSS,
            state=WorkerState.RUNNING,
        )
        health.record_heartbeat()
        assert health.is_healthy() is True
        
        # Not healthy if not running
        health.state = WorkerState.STOPPED
        assert health.is_healthy() is False
        
        # Not healthy if too many missed heartbeats
        health.state = WorkerState.RUNNING
        for _ in range(HealthStatus.MISSED_HEARTBEAT_THRESHOLD):
            health.record_missed_heartbeat()
        assert health.is_healthy() is False
    
    def test_heartbeat_recording(self):
        """Test heartbeat recording."""
        health = HealthStatus(
            worker_type=WorkerType.IMAGE,
            state=WorkerState.RUNNING,
        )
        
        # Record missed heartbeats
        health.record_missed_heartbeat()
        health.record_missed_heartbeat()
        assert health.missed_heartbeats == 2
        
        # Successful heartbeat resets counter
        health.record_heartbeat()
        assert health.missed_heartbeats == 0
        assert health.last_heartbeat > 0
    
    def test_restart_backoff(self):
        """Test exponential backoff calculation."""
        health = HealthStatus(
            worker_type=WorkerType.TRANSITION,
            state=WorkerState.ERROR,
        )
        
        # First restart - base delay
        assert health.get_restart_backoff_ms() == HealthStatus.RESTART_BACKOFF_BASE_MS
        
        # Record restarts and verify backoff increases
        health.record_restart()
        backoff1 = health.get_restart_backoff_ms()
        
        health.record_restart()
        backoff2 = health.get_restart_backoff_ms()
        
        assert backoff2 > backoff1
        assert backoff2 <= HealthStatus.RESTART_BACKOFF_MAX_MS
    
    def test_restart_limit(self):
        """Test restart limit enforcement."""
        health = HealthStatus(
            worker_type=WorkerType.IMAGE,
            state=WorkerState.ERROR,
        )
        
        # Should be able to restart initially
        assert health.should_restart() is True
        
        # Record max restarts
        for _ in range(HealthStatus.MAX_RESTARTS_PER_WINDOW):
            health.record_restart()
        
        # Should not be able to restart after limit
        assert health._can_restart() is False
    
    def test_health_serialization(self):
        """Test health status to_dict."""
        health = HealthStatus(
            worker_type=WorkerType.RSS,
            state=WorkerState.RUNNING,
            pid=54321,
        )
        health.record_heartbeat()
        
        data = health.to_dict()
        assert data["worker_type"] == "rss"
        assert data["state"] == "RUNNING"
        assert data["pid"] == 54321
        assert data["is_healthy"] is True


class TestProcessSupervisor:
    """Tests for ProcessSupervisor."""
    
    def test_supervisor_initialization(self):
        """Test supervisor initializes correctly."""
        supervisor = ProcessSupervisor()
        assert supervisor._initialized is True
        assert supervisor._shutdown is False
        
        # All worker types should have health status
        for wt in WorkerType:
            health = supervisor.get_health(wt)
            assert health.state == WorkerState.STOPPED
        
        supervisor.shutdown()
    
    def test_supervisor_get_all_health(self):
        """Test getting health for all workers."""
        supervisor = ProcessSupervisor()
        
        all_health = supervisor.get_all_health()
        assert len(all_health) == len(WorkerType)
        
        for wt in WorkerType:
            assert wt in all_health
            assert all_health[wt].worker_type == wt
        
        supervisor.shutdown()
    
    def test_supervisor_shutdown(self):
        """Test supervisor shutdown."""
        supervisor = ProcessSupervisor()
        supervisor.shutdown()
        
        assert supervisor._shutdown is True
    
    def test_supervisor_factory_registration(self):
        """Test registering a worker factory."""
        supervisor = ProcessSupervisor()
        
        def dummy_factory(req_queue, resp_queue):
            pass
        
        supervisor.register_worker_factory(WorkerType.IMAGE, dummy_factory)
        assert WorkerType.IMAGE in supervisor._worker_factories
        
        supervisor.shutdown()
    
    def test_supervisor_start_without_factory(self):
        """Test starting worker without registered factory fails."""
        supervisor = ProcessSupervisor()
        
        result = supervisor.start(WorkerType.IMAGE)
        assert result is False  # No factory registered
        
        supervisor.shutdown()
    
    def test_supervisor_message_creation(self):
        """Test message creation with proper sequencing."""
        supervisor = ProcessSupervisor()
        
        # Sequence numbers should increment
        seq1 = supervisor._next_seq(WorkerType.IMAGE)
        seq2 = supervisor._next_seq(WorkerType.IMAGE)
        assert seq2 == seq1 + 1
        
        # Different worker types have separate sequences
        seq_rss = supervisor._next_seq(WorkerType.RSS)
        assert seq_rss == 1
        
        supervisor.shutdown()


class TestWorkerContracts:
    """Tests for worker contract validation."""
    
    def test_image_worker_contract(self):
        """Test ImageWorker message contract."""
        # Valid request
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,
            seq_no=1,
            correlation_id="img-001",
            payload={
                "path": "/path/to/image.jpg",
                "target_size": (1920, 1080),
                "cache_key": "path|scaled:1920x1080",
            },
            worker_type=WorkerType.IMAGE,
        )
        assert msg.validate_size() is True
        assert "path" in msg.payload
        assert "target_size" in msg.payload
        assert "cache_key" in msg.payload
    
    def test_rss_worker_contract(self):
        """Test RSSWorker message contract."""
        msg = WorkerMessage(
            msg_type=MessageType.RSS_FETCH,
            seq_no=1,
            correlation_id="rss-001",
            payload={
                "feeds": ["https://example.com/feed.xml"],
                "max_items": 20,
                "ttl_hint": 3600,
            },
            worker_type=WorkerType.RSS,
        )
        assert "feeds" in msg.payload
        assert "max_items" in msg.payload
    
    def test_transition_worker_contract(self):
        """Test TransitionPrepWorker message contract."""
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="trans-001",
            payload={
                "transition_type": "Diffuse",
                "params": {"block_size": 16, "shape": "Rectangle"},
                "duration_ms": 2000,
                "direction": "LEFT",
            },
            worker_type=WorkerType.TRANSITION,
        )
        assert "transition_type" in msg.payload
        assert "params" in msg.payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
