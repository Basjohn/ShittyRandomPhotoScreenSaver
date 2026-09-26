"""
Tests for ProcessSupervisor and process isolation types.

Tests cover:
- Supervisor lifecycle (start/stop/restart)
- Health monitoring (heartbeat, missed heartbeat threshold)
- Message schema validation
- Shared memory header serialization
- Worker state transitions
"""
import queue
import threading

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
        assert WorkerType.IMAGE_PREFETCH.value == "image_prefetch"
        # WorkerType.RSS was retired: it was registered but never started;
        # wallpaper feeds run in-process on the shared feed core.
        # WorkerType.TRANSITION was retired: transitions are GPU/Quick-owned and
        # no longer run in a supervised worker process.
    
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
        # MessageType.TRANSITION_PRECOMPUTE was retired with the transition worker.


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
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=42,
            correlation_id="corr-456",
            payload={"path": "a.jpg", "target_size": [4, 4]},
            worker_type=WorkerType.IMAGE_PREFETCH,
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
            msg_type=MessageType.IMAGE_RESULT,
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
            worker_type=WorkerType.IMAGE_PREFETCH,
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
            worker_type=WorkerType.IMAGE,
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
            worker_type=WorkerType.IMAGE_PREFETCH,
            state=WorkerState.RUNNING,
            pid=54321,
        )
        health.record_heartbeat()
        
        data = health.to_dict()
        assert data["worker_type"] == "image_prefetch"
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
        seq_prefetch = supervisor._next_seq(WorkerType.IMAGE_PREFETCH)
        assert seq_prefetch == 1
        
        supervisor.shutdown()

    def test_cleanup_worker_closes_process_and_queues(self):
        """Worker cleanup should release parent-side process and queue resources."""
        supervisor = ProcessSupervisor()

        class FakeProcess:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class FakeQueue:
            def __init__(self):
                self.cancelled = False
                self.closed = False
                self.joined = False

            def cancel_join_thread(self):
                self.cancelled = True

            def close(self):
                self.closed = True

            def join_thread(self):
                self.joined = True

        process = FakeProcess()
        req_queue = FakeQueue()
        resp_queue = FakeQueue()

        supervisor._workers[WorkerType.IMAGE] = process
        supervisor._request_queues[WorkerType.IMAGE] = req_queue
        supervisor._response_queues[WorkerType.IMAGE] = resp_queue
        supervisor._health[WorkerType.IMAGE].state = WorkerState.RUNNING

        supervisor._cleanup_worker(WorkerType.IMAGE)

        assert process.closed is True
        assert req_queue.cancelled is True
        assert req_queue.closed is True
        assert req_queue.joined is True
        assert resp_queue.cancelled is True
        assert resp_queue.closed is True
        assert resp_queue.joined is True
        assert supervisor.get_health(WorkerType.IMAGE).state == WorkerState.STOPPED

    def test_await_response_buffers_unmatched_responses_for_later_poll(self):
        supervisor = ProcessSupervisor()

        class FakeQueue:
            def __init__(self, items):
                self._items = list(items)

            def get(self, timeout=None):
                if not self._items:
                    raise Exception("empty")
                return self._items.pop(0)

            def get_nowait(self):
                if not self._items:
                    raise Exception("empty")
                return self._items.pop(0)

        supervisor._response_queues[WorkerType.IMAGE] = FakeQueue([
            WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=1,
                correlation_id="other",
                success=True,
                payload={"value": "other"},
            ).to_dict(),
            WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=2,
                correlation_id="wanted",
                success=True,
                payload={"value": "wanted"},
            ).to_dict(),
        ])

        response = supervisor.await_response(WorkerType.IMAGE, "wanted", timeout_ms=50, poll_slice_ms=1)

        assert response is not None
        assert response.correlation_id == "wanted"

        later = supervisor.poll_responses(WorkerType.IMAGE, max_count=5)
        assert len(later) == 1
        assert later[0].correlation_id == "other"

        supervisor.shutdown()

    def test_await_response_processes_internal_messages_without_returning_them(self):
        supervisor = ProcessSupervisor()

        class FakeQueue:
            def __init__(self, items):
                self._items = list(items)

            def get(self, timeout=None):
                if not self._items:
                    raise Exception("empty")
                return self._items.pop(0)

            def get_nowait(self):
                if not self._items:
                    raise Exception("empty")
                return self._items.pop(0)

        supervisor._health[WorkerType.IMAGE].state = WorkerState.RUNNING
        supervisor._health[WorkerType.IMAGE].missed_heartbeats = 2
        supervisor._response_queues[WorkerType.IMAGE] = FakeQueue([
            WorkerResponse(
                msg_type=MessageType.HEARTBEAT_ACK,
                seq_no=1,
                correlation_id="hb",
                success=True,
            ).to_dict(),
            WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=2,
                correlation_id="wanted",
                success=True,
                payload={"value": "wanted"},
            ).to_dict(),
        ])

        response = supervisor.await_response(WorkerType.IMAGE, "wanted", timeout_ms=50, poll_slice_ms=1)

        assert response is not None
        assert response.correlation_id == "wanted"
        assert supervisor.get_health(WorkerType.IMAGE).missed_heartbeats == 0

        supervisor.shutdown()

    def test_response_listener_dispatches_callback_and_buffers_unmatched(self):
        supervisor = ProcessSupervisor()
        responses = queue.Queue()
        supervisor._response_queues[WorkerType.IMAGE_PREFETCH] = responses
        supervisor._health[WorkerType.IMAGE_PREFETCH].state = WorkerState.RUNNING
        supervisor._health[WorkerType.IMAGE_PREFETCH].missed_heartbeats = 2

        delivered = []
        done = threading.Event()

        def _on_response(response):
            delivered.append(response)
            done.set()

        assert supervisor.register_response_callback(
            WorkerType.IMAGE_PREFETCH,
            "wanted",
            _on_response,
        ) is True

        responses.put(
            WorkerResponse(
                msg_type=MessageType.HEARTBEAT_ACK,
                seq_no=1,
                correlation_id="heartbeat",
                success=True,
            ).to_dict()
        )
        responses.put(
            WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=2,
                correlation_id="other",
                success=True,
                payload={"value": "other"},
            ).to_dict()
        )
        responses.put(
            WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=3,
                correlation_id="wanted",
                success=True,
                payload={"value": "wanted"},
            ).to_dict()
        )

        assert done.wait(1.0) is True
        assert len(delivered) == 1
        assert delivered[0] is not None
        assert delivered[0].correlation_id == "wanted"
        assert supervisor.get_health(WorkerType.IMAGE_PREFETCH).missed_heartbeats == 0

        later = supervisor.poll_responses(WorkerType.IMAGE_PREFETCH, max_count=5)
        assert [item.correlation_id for item in later] == ["other"]
        diag = supervisor.get_detailed_health(WorkerType.IMAGE_PREFETCH)
        assert diag["response_listener_active"] is True
        assert diag["response_callbacks_pending"] == 0

        supervisor.shutdown()

    def test_response_listener_abandon_removes_callback_and_drops_late_reply(self):
        supervisor = ProcessSupervisor()
        responses = queue.Queue()
        supervisor._response_queues[WorkerType.IMAGE_PREFETCH] = responses

        delivered = []
        assert supervisor.register_response_callback(
            WorkerType.IMAGE_PREFETCH,
            "cancel-me",
            delivered.append,
        ) is True
        assert supervisor.abandon_response(
            WorkerType.IMAGE_PREFETCH,
            "cancel-me",
            reason="generation_cancelled",
        ) == 0

        responses.put(
            WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=1,
                correlation_id="cancel-me",
                success=True,
                payload={"value": "late"},
            ).to_dict()
        )

        # The listener must consume the late response without resurrecting the
        # cancelled callback. A second buffered response proves it advanced.
        buffered_done = threading.Event()
        assert supervisor.register_response_callback(
            WorkerType.IMAGE_PREFETCH,
            "after",
            lambda response: buffered_done.set(),
        ) is True
        responses.put(
            WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=2,
                correlation_id="after",
                success=True,
            ).to_dict()
        )
        assert buffered_done.wait(1.0) is True
        assert delivered == []
        assert "cancel-me" not in supervisor._abandoned_correlations[
            WorkerType.IMAGE_PREFETCH
        ]

        supervisor.shutdown()

    def test_response_listener_shutdown_cancels_pending_callback_once(self):
        supervisor = ProcessSupervisor()
        supervisor._response_queues[WorkerType.IMAGE_PREFETCH] = queue.Queue()

        delivered = []
        cancelled = threading.Event()

        def _on_response(response):
            delivered.append(response)
            cancelled.set()

        assert supervisor.register_response_callback(
            WorkerType.IMAGE_PREFETCH,
            "pending",
            _on_response,
        ) is True

        supervisor.shutdown()

        assert cancelled.wait(1.0) is True
        assert delivered == [None]
        assert not supervisor._response_callbacks[WorkerType.IMAGE_PREFETCH]


class TestWorkerContracts:
    """Tests for worker contract validation."""
    
    def test_speculative_image_worker_contract(self):
        """Speculative image requests use a distinct worker identity."""
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="prefetch-001",
            payload={
                "path": "/path/to/image.jpg",
                "target_width": 1920,
                "target_height": 1080,
                "mode": "fill",
                "use_lanczos": False,
                "sharpen": False,
            },
            worker_type=WorkerType.IMAGE_PREFETCH,
        )
        assert msg.validate_size() is True
        assert msg.worker_type == WorkerType.IMAGE_PREFETCH

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
    
    # Removed test_transition_worker_contract: the TransitionPrepWorker and its
    # MessageType.TRANSITION_PRECOMPUTE / WorkerType.TRANSITION were retired when
    # transitions became GPU/Quick-owned. No supervised transition worker exists.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestHeartbeatThreadLifetime:
    """R-97: heartbeat monitoring must never create a new OS thread per tick.

    The NVIDIA OpenGL driver keeps ~70 KB of per-thread state for every thread
    a GL process ever creates, so a threading.Timer per 3 s tick was a steady
    86 MB/h commit slope.
    """

    def test_heartbeat_runs_on_one_persistent_thread_and_stops_on_shutdown(self, monkeypatch):
        supervisor = ProcessSupervisor()
        supervisor._heartbeat_interval_s = 0.02
        checks = []
        monkeypatch.setattr(supervisor, "_heartbeat_check", lambda: checks.append(threading.get_ident()))
        started = []
        real_start = threading.Thread.start

        def counting_start(thread):
            started.append(thread.name)
            return real_start(thread)

        monkeypatch.setattr(threading.Thread, "start", counting_start)
        try:
            supervisor._ensure_heartbeat_monitoring()
            supervisor._ensure_heartbeat_monitoring()  # idempotent while running
            deadline = threading.Event()
            for _ in range(200):
                if len(checks) >= 5:
                    break
                deadline.wait(0.01)
            assert len(checks) >= 5
            # Every check ran on the same thread, and only one thread was ever started.
            assert len(set(checks)) == 1
            assert started == ["srpss-worker-heartbeat"]
        finally:
            thread = supervisor._heartbeat_thread
            supervisor.shutdown(timeout=0.1)
        if thread is not None:
            thread.join(1.0)
            assert not thread.is_alive()
        count = len(checks)
        threading.Event().wait(0.1)
        assert len(checks) == count  # no checks after shutdown
