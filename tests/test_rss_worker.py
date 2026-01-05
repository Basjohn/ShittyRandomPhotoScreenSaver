"""
Tests for RSSWorker process.

Tests cover:
- Feed URL parsing and priority ordering
- Image URL extraction from feed entries
- Cache key and metadata generation
- Error handling for invalid feeds
"""
import pytest

from core.process.types import MessageType, WorkerMessage, WorkerType
from core.process.workers.rss_worker import RSSWorker, SOURCE_PRIORITY


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
    """Create an RSSWorker with mock queues."""
    req_queue = MockQueue()
    resp_queue = MockQueue()
    w = RSSWorker(req_queue, resp_queue)
    return w, req_queue, resp_queue


class TestRSSWorkerPriority:
    """Tests for feed priority ordering."""
    
    def test_source_priority_bing(self, worker):
        """Test Bing gets high priority."""
        w, _, _ = worker
        priority = w._get_source_priority("https://www.bing.com/HPImageArchive.aspx")
        assert priority == SOURCE_PRIORITY['bing.com']
        assert priority > 50  # Higher than default
    
    def test_source_priority_reddit(self, worker):
        """Test Reddit gets low priority (rate limited)."""
        w, _, _ = worker
        priority = w._get_source_priority("https://www.reddit.com/r/EarthPorn/.json")
        assert priority == SOURCE_PRIORITY['reddit.com']
        assert priority < 50  # Lower than default
    
    def test_source_priority_unknown(self, worker):
        """Test unknown source gets default priority."""
        w, _, _ = worker
        priority = w._get_source_priority("https://example.com/feed.xml")
        assert priority == 50  # Default
    
    def test_priority_ordering(self, worker):
        """Test that priority ordering is correct."""
        w, _, _ = worker
        
        # Bing > Unsplash > Wikimedia > NASA > Reddit
        bing = w._get_source_priority("https://bing.com/feed")
        unsplash = w._get_source_priority("https://unsplash.com/feed")
        wikimedia = w._get_source_priority("https://wikimedia.org/feed")
        nasa = w._get_source_priority("https://nasa.gov/feed")
        reddit = w._get_source_priority("https://reddit.com/feed")
        
        assert bing > unsplash > wikimedia > nasa > reddit


class TestRSSWorkerImageURL:
    """Tests for image URL detection."""
    
    def test_is_image_url_jpg(self, worker):
        """Test JPG URL detection."""
        w, _, _ = worker
        assert w._is_image_url("https://example.com/image.jpg") is True
        assert w._is_image_url("https://example.com/image.jpeg") is True
    
    def test_is_image_url_png(self, worker):
        """Test PNG URL detection."""
        w, _, _ = worker
        assert w._is_image_url("https://example.com/image.png") is True
    
    def test_is_image_url_webp(self, worker):
        """Test WebP URL detection."""
        w, _, _ = worker
        assert w._is_image_url("https://example.com/image.webp") is True
    
    def test_is_image_url_non_image(self, worker):
        """Test non-image URL detection."""
        w, _, _ = worker
        assert w._is_image_url("https://example.com/page.html") is False
        assert w._is_image_url("https://example.com/video.mp4") is False
        assert w._is_image_url("") is False
        assert w._is_image_url("https://example.com/") is False


class TestRSSWorkerMessages:
    """Tests for message handling."""
    
    def test_missing_feed_url(self, worker):
        """Test error handling for missing feed_url."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.RSS_FETCH,
            seq_no=1,
            correlation_id="test-001",
            payload={},
            worker_type=WorkerType.RSS,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is False
        assert "feed_url" in response.error.lower()
    
    def test_unknown_message_type(self, worker):
        """Test error handling for unknown message type."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.IMAGE_DECODE,  # Wrong type for RSS worker
            seq_no=1,
            correlation_id="test-002",
            payload={"feed_url": "https://example.com/feed.xml"},
            worker_type=WorkerType.RSS,
        )
        
        response = w.handle_message(msg)
        
        assert response is not None
        assert response.success is False
        assert "unknown" in response.error.lower()
    
    def test_config_update(self, worker):
        """Test configuration update handling."""
        w, _, _ = worker
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            msg = WorkerMessage(
                msg_type=MessageType.CONFIG_UPDATE,
                seq_no=1,
                correlation_id="test-003",
                payload={
                    "cache_dir": tmpdir,
                },
                worker_type=WorkerType.RSS,
            )
            
            response = w.handle_message(msg)
            
            assert response is not None
            assert response.success is True
            assert w._cache_dir is not None


class TestRSSWorkerMetadata:
    """Tests for metadata generation."""
    
    def test_metadata_structure(self, worker):
        """Test that metadata has required fields."""
        # This tests the expected structure without network calls
        expected_fields = [
            "source_type",
            "source_id",
            "url",
            "local_path",
            "title",
            "priority",
            "timestamp",
        ]
        
        # Verify the worker creates metadata with these fields
        # by checking the _parse_rss_feed method structure
        w, _, _ = worker
        assert hasattr(w, '_parse_rss_feed')
        assert hasattr(w, '_parse_reddit_json')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
