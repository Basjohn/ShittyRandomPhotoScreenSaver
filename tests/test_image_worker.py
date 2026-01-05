"""
Tests for ImageWorker process.

Tests cover:
- Image decode correctness
- Prescale with different display modes (fill, fit, shrink)
- Cache key strategy preservation
- Error handling for missing/invalid files
"""
import os
import tempfile
import pytest

from PIL import Image

from core.process.types import MessageType, WorkerMessage, WorkerType
from core.process.workers.image_worker import ImageWorker


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
    
    def get_all(self):
        items = self._items[:]
        self._items.clear()
        return items


@pytest.fixture
def worker():
    """Create an ImageWorker with mock queues."""
    req_queue = MockQueue()
    resp_queue = MockQueue()
    w = ImageWorker(req_queue, resp_queue)
    return w, req_queue, resp_queue


@pytest.fixture
def test_image_path():
    """Create a temporary test image."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        # Create a 100x100 red image
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img.save(f.name, "PNG")
        yield f.name
    # Cleanup
    try:
        os.unlink(f.name)
    except Exception:
        pass


@pytest.fixture
def large_test_image_path():
    """Create a larger temporary test image for prescale tests."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        # Create a 1920x1080 gradient image
        img = Image.new("RGB", (1920, 1080), color=(0, 128, 255))
        img.save(f.name, "PNG")
        yield f.name
    try:
        os.unlink(f.name)
    except Exception:
        pass


class TestImageWorkerDecode:
    """Tests for image decode functionality."""
    
    def test_decode_success(self, worker, test_image_path):
        """Test successful image decode."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,
            seq_no=1,
            correlation_id="test-001",
            payload={"path": test_image_path},
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is True
        assert response.msg_type == MessageType.IMAGE_RESULT
        assert response.payload["width"] == 100
        assert response.payload["height"] == 100
        assert response.payload["format"] == "RGBA"
        assert "rgba_data" in response.payload
        assert len(response.payload["rgba_data"]) == 100 * 100 * 4  # RGBA
    
    def test_decode_missing_file(self, worker):
        """Test decode with missing file."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,
            seq_no=1,
            correlation_id="test-002",
            payload={"path": "/nonexistent/path/image.jpg"},
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is False
        assert "not found" in response.error.lower()
    
    def test_decode_missing_path_param(self, worker):
        """Test decode without path parameter."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,
            seq_no=1,
            correlation_id="test-003",
            payload={},
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is False
        assert "path" in response.error.lower()


class TestImageWorkerPrescale:
    """Tests for image prescale functionality."""
    
    def test_prescale_fill_mode(self, worker, large_test_image_path):
        """Test prescale with fill mode (covers target, crops excess)."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="test-fill-001",
            payload={
                "path": large_test_image_path,
                "target_width": 800,
                "target_height": 600,
                "mode": "fill",
            },
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is True
        assert response.payload["width"] == 800
        assert response.payload["height"] == 600
        assert response.payload["mode"] == "fill"
        assert "scaled:800x600" in response.payload["cache_key"]
    
    def test_prescale_fit_mode(self, worker, large_test_image_path):
        """Test prescale with fit mode (fits within target, may have bars)."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="test-fit-001",
            payload={
                "path": large_test_image_path,
                "target_width": 800,
                "target_height": 600,
                "mode": "fit",
            },
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is True
        # Fit mode should produce exact target size with padding
        assert response.payload["width"] == 800
        assert response.payload["height"] == 600
    
    def test_prescale_shrink_mode_larger_image(self, worker, large_test_image_path):
        """Test prescale with shrink mode on larger image (should shrink)."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="test-shrink-001",
            payload={
                "path": large_test_image_path,
                "target_width": 800,
                "target_height": 600,
                "mode": "shrink",
            },
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is True
        # Shrink should produce target size for larger images
        assert response.payload["width"] == 800
        assert response.payload["height"] == 600
    
    def test_prescale_shrink_mode_smaller_image(self, worker, test_image_path):
        """Test prescale with shrink mode on smaller image (should not upscale)."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="test-shrink-002",
            payload={
                "path": test_image_path,  # 100x100 image
                "target_width": 800,
                "target_height": 600,
                "mode": "shrink",
            },
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is True
        # Shrink should preserve original size (100x100) centered in 800x600
        assert response.payload["width"] == 800
        assert response.payload["height"] == 600
        # Original size should be preserved
        assert response.payload["original_width"] == 100
        assert response.payload["original_height"] == 100
    
    def test_prescale_invalid_target_size(self, worker, test_image_path):
        """Test prescale with invalid target size."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="test-invalid-001",
            payload={
                "path": test_image_path,
                "target_width": 0,
                "target_height": -100,
                "mode": "fill",
            },
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is False
        assert "invalid" in response.error.lower()


class TestImageWorkerCacheKey:
    """Tests for cache key strategy preservation."""
    
    def test_cache_key_format_decode(self, worker, test_image_path):
        """Test cache key format for decode (path only)."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,
            seq_no=1,
            correlation_id="test-cache-001",
            payload={"path": test_image_path},
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        assert response.payload["cache_key"] == test_image_path
    
    def test_cache_key_format_prescale(self, worker, test_image_path):
        """Test cache key format for prescale (path|scaled:WxH)."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="test-cache-002",
            payload={
                "path": test_image_path,
                "target_width": 640,
                "target_height": 480,
                "mode": "fill",
            },
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        expected_key = f"{test_image_path}|scaled:640x480"
        assert response.payload["cache_key"] == expected_key


class TestImageWorkerLatency:
    """Tests for worker latency requirements."""
    
    def test_prescale_latency_reasonable(self, worker, large_test_image_path):
        """Test that prescale completes within reasonable time."""
        w, req_q, resp_q = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id="test-latency-001",
            payload={
                "path": large_test_image_path,
                "target_width": 1920,
                "target_height": 1080,
                "mode": "fill",
            },
            worker_type=WorkerType.IMAGE,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        # Should complete within 500ms for a 1920x1080 image
        assert response.processing_time_ms < 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
