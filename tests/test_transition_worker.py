"""
Tests for TransitionWorker process.

Tests cover:
- Block pattern precomputation for Diffuse transitions
- Block grid precomputation for BlockFlip transitions
- Particle initial state generation
- Cache key generation and caching behavior
"""
import pytest

from core.process.types import MessageType, WorkerMessage, WorkerType
from core.process.workers.transition_worker import TransitionWorker, TransitionPrecomputeConfig


class MockQueue:
    """Mock queue for testing without multiprocessing."""
    
    def __init__(self):
        self._items = []
    
    def put_nowait(self, item):
        self._items.append(item)
    
    def get_nowait(self):
        if self._items:
            return self._items.pop(0)
        raise Exception("Queue empty")
    
    def empty(self):
        return len(self._items) == 0


@pytest.fixture
def worker():
    """Create a TransitionWorker with mock queues."""
    req_queue = MockQueue()
    resp_queue = MockQueue()
    w = TransitionWorker(req_queue, resp_queue)
    return w, req_queue, resp_queue


class TestTransitionConfig:
    """Tests for transition configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TransitionPrecomputeConfig()
        assert config.diffuse_block_size == 16
        assert config.block_cols == 8
        assert config.block_rows == 6
        assert config.particle_count == 1000
        assert config.screen_width == 1920
        assert config.screen_height == 1080


class TestDiffusePrecompute:
    """Tests for Diffuse transition precomputation."""
    
    def test_diffuse_basic(self, worker):
        """Test basic Diffuse precomputation."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-001",
            payload={
                "transition_type": "Diffuse",
                "params": {
                    "block_size": 32,
                    "screen_width": 640,
                    "screen_height": 480,
                    "seed": 42,
                },
            },
            worker_type=WorkerType.TRANSITION,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        data = response.payload["data"]
        assert data["precomputed"] is True
        assert data["block_size"] == 32
        assert "dissolution_order" in data
        assert "blocks" in data
    
    def test_diffuse_block_count(self, worker):
        """Test Diffuse block count is correct."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-002",
            payload={
                "transition_type": "Diffuse",
                "params": {
                    "block_size": 100,
                    "screen_width": 400,
                    "screen_height": 300,
                    "seed": 42,
                },
            },
            worker_type=WorkerType.TRANSITION,
        )
        
        response = w.handle_message(msg)
        data = response.payload["data"]
        
        # 400/100 = 4 cols, 300/100 = 3 rows = 12 blocks
        assert data["cols"] == 4
        assert data["rows"] == 3
        assert data["total_blocks"] == 12
        assert len(data["blocks"]) == 12
    
    def test_diffuse_deterministic_with_seed(self, worker):
        """Test Diffuse is deterministic with same seed."""
        w, _, _ = worker
        
        params = {
            "transition_type": "Diffuse",
            "params": {
                "block_size": 50,
                "screen_width": 200,
                "screen_height": 200,
                "seed": 12345,
            },
            "use_cache": False,
        }
        
        msg1 = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-003a",
            payload=params,
            worker_type=WorkerType.TRANSITION,
        )
        
        msg2 = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=2,
            correlation_id="test-003b",
            payload=params,
            worker_type=WorkerType.TRANSITION,
        )
        
        r1 = w.handle_message(msg1)
        r2 = w.handle_message(msg2)
        
        # Same seed should produce same dissolution order
        assert r1.payload["data"]["dissolution_order"] == r2.payload["data"]["dissolution_order"]


class TestBlockPrecompute:
    """Tests for BlockFlip/BlockSpin precomputation."""
    
    def test_blockflip_basic(self, worker):
        """Test basic BlockFlip precomputation."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-004",
            payload={
                "transition_type": "BlockFlip",
                "params": {
                    "cols": 4,
                    "rows": 3,
                    "screen_width": 800,
                    "screen_height": 600,
                    "seed": 42,
                },
            },
            worker_type=WorkerType.TRANSITION,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        data = response.payload["data"]
        assert data["precomputed"] is True
        assert data["cols"] == 4
        assert data["rows"] == 3
        assert data["total_blocks"] == 12
        assert len(data["blocks"]) == 12
    
    def test_blocks_have_flip_axis(self, worker):
        """Test that blocks have flip axis assigned."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-005",
            payload={
                "transition_type": "BlockSpin",
                "params": {"seed": 42},
            },
            worker_type=WorkerType.TRANSITION,
        )
        
        response = w.handle_message(msg)
        data = response.payload["data"]
        
        for block in data["blocks"]:
            assert "flip_axis" in block
            assert block["flip_axis"] in ("x", "y")


class TestParticlePrecompute:
    """Tests for Particle transition precomputation."""
    
    def test_particle_basic(self, worker):
        """Test basic Particle precomputation."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-006",
            payload={
                "transition_type": "Particle",
                "params": {
                    "particle_count": 100,
                    "screen_width": 800,
                    "screen_height": 600,
                    "seed": 42,
                },
            },
            worker_type=WorkerType.TRANSITION,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        data = response.payload["data"]
        assert data["precomputed"] is True
        assert data["particle_count"] == 100
        assert len(data["particles"]) == 100
    
    def test_particle_properties(self, worker):
        """Test particle properties are valid."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-007",
            payload={
                "transition_type": "Particle",
                "params": {"particle_count": 10, "seed": 42},
            },
            worker_type=WorkerType.TRANSITION,
        )
        
        response = w.handle_message(msg)
        data = response.payload["data"]
        
        for p in data["particles"]:
            assert "x" in p and "y" in p
            assert "vx" in p and "vy" in p
            assert "size" in p and p["size"] > 0
            assert "alpha" in p and 0 <= p["alpha"] <= 1
            assert "rotation" in p


class TestCaching:
    """Tests for precomputation caching."""
    
    def test_cache_hit(self, worker):
        """Test that cache is used on repeated requests."""
        w, _, _ = worker
        
        params = {
            "transition_type": "Diffuse",
            "params": {"block_size": 20, "seed": 123},
            "use_cache": True,
        }
        
        msg1 = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-008a",
            payload=params,
            worker_type=WorkerType.TRANSITION,
        )
        
        msg2 = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=2,
            correlation_id="test-008b",
            payload=params,
            worker_type=WorkerType.TRANSITION,
        )
        
        r1 = w.handle_message(msg1)
        r2 = w.handle_message(msg2)
        
        assert r1.payload.get("cached") is False
        assert r2.payload.get("cached") is True
        assert r2.processing_time_ms == 0.0  # Cache hit = no compute time
    
    def test_cache_key_changes(self, worker):
        """Test that different params produce different cache keys."""
        w, _, _ = worker
        
        key1 = w._generate_cache_key("Diffuse", {"block_size": 16})
        key2 = w._generate_cache_key("Diffuse", {"block_size": 32})
        key3 = w._generate_cache_key("BlockFlip", {"block_size": 16})
        
        assert key1 != key2  # Different block size
        assert key1 != key3  # Different transition type


class TestSimpleTransitions:
    """Tests for simple transitions without precomputation."""
    
    def test_crossfade_no_precompute(self, worker):
        """Test Crossfade returns precomputed=False."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.TRANSITION_PRECOMPUTE,
            seq_no=1,
            correlation_id="test-009",
            payload={"transition_type": "Crossfade"},
            worker_type=WorkerType.TRANSITION,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        assert response.payload["data"]["precomputed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
