"""
Test RSS image fetching and queue behavior.

This test verifies:
1. RSS sources fetch images from multiple feeds
2. Images are properly cached and not re-downloaded
3. Queue properly rotates through RSS images
4. Duplicate detection works correctly
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime


class TestRSSBehavior:
    """Test RSS image fetching and queue behavior."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        cache_dir = Path(tempfile.mkdtemp(prefix="test_rss_cache_"))
        yield cache_dir
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_reddit_response(self):
        """Create a mock Reddit JSON response with multiple images."""
        def create_response(subreddit: str, num_posts: int = 10):
            posts = []
            for i in range(num_posts):
                # Create unique image URLs for each post
                image_url = f"https://i.redd.it/{subreddit}_{i}_unique_image.jpg"
                posts.append({
                    "kind": "t3",
                    "data": {
                        "title": f"Test Post {i} from {subreddit}",
                        "url_overridden_by_dest": image_url,
                        "url": image_url,
                        "author": f"test_user_{i}",
                        "created_utc": datetime.utcnow().timestamp(),
                        "preview": {
                            "images": [{
                                "source": {"width": 3840, "height": 2160}
                            }]
                        }
                    }
                })
            return {
                "kind": "Listing",
                "data": {
                    "children": posts
                }
            }
        return create_response
    
    def test_rss_source_fetches_from_multiple_feeds(self, temp_cache_dir, mock_reddit_response):
        """Test that RSSSource fetches images from all configured feeds."""
        from sources.rss_source import RSSSource
        
        feeds = [
            "https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=10",
            "https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=10",
            "https://www.reddit.com/r/SpacePorn/top/.json?t=day&limit=10",
        ]
        
        # Mock requests.get to return different images for each feed
        def mock_get(url, **kwargs):
            mock_resp = Mock()
            mock_resp.raise_for_status = Mock()
            
            if "EarthPorn" in url and "json" in url:
                mock_resp.json.return_value = mock_reddit_response("EarthPorn", 5)
            elif "CityPorn" in url and "json" in url:
                mock_resp.json.return_value = mock_reddit_response("CityPorn", 5)
            elif "SpacePorn" in url and "json" in url:
                mock_resp.json.return_value = mock_reddit_response("SpacePorn", 5)
            elif "i.redd.it" in url:
                # Mock image download - iter_content must return an iterator
                mock_resp.headers = {"Content-Type": "image/jpeg"}
                # Create valid JPEG header bytes
                jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF' + b'\x00' * 1000
                mock_resp.iter_content = lambda chunk_size=8192: iter([jpeg_data])
            else:
                mock_resp.json.return_value = {"kind": "Listing", "data": {"children": []}}
            
            return mock_resp
        
        with patch('requests.get', side_effect=mock_get):
            source = RSSSource(
                feed_urls=feeds,
                cache_dir=temp_cache_dir,
            )
            source.refresh()
            images = source.get_images()
        
        # Should have images from all 3 feeds
        print("\n=== RSS Source Test Results ===")
        print(f"Feeds configured: {len(feeds)}")
        print(f"Images fetched: {len(images)}")
        print(f"Unique source IDs: {len(set(img.source_id for img in images))}")
        
        # Verify we got images from multiple feeds
        source_ids = set(img.source_id for img in images)
        assert len(source_ids) >= 2, f"Expected images from multiple feeds, got: {source_ids}"
        assert len(images) >= 6, f"Expected at least 6 images, got {len(images)}"
    
    def test_rss_source_tracks_cached_urls(self, temp_cache_dir, mock_reddit_response):
        """Test that RSSSource tracks cached URLs and doesn't re-download."""
        from sources.rss_source import RSSSource
        
        feeds = ["https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=5"]
        download_count = [0]
        
        def mock_get(url, **kwargs):
            mock_resp = Mock()
            mock_resp.raise_for_status = Mock()
            
            if "EarthPorn" in url and "json" in url:
                mock_resp.json.return_value = mock_reddit_response("EarthPorn", 5)
            elif "i.redd.it" in url:
                download_count[0] += 1
                mock_resp.headers = {"Content-Type": "image/jpeg"}
                jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF' + b'\x00' * 1000
                mock_resp.iter_content = lambda chunk_size=8192: iter([jpeg_data])
            else:
                mock_resp.json.return_value = {"kind": "Listing", "data": {"children": []}}
            
            return mock_resp
        
        with patch('requests.get', side_effect=mock_get):
            source = RSSSource(feed_urls=feeds, cache_dir=temp_cache_dir)
            
            # First refresh - should download images
            source.refresh()
            first_download_count = download_count[0]
            first_image_count = len(source.get_images())
            
            print("\n=== Cache Tracking Test ===")
            print(f"First refresh: {first_download_count} downloads, {first_image_count} images")
            
            # Second refresh - should NOT re-download same images
            source.refresh()
            second_download_count = download_count[0]
            second_image_count = len(source.get_images())
            
            print(f"Second refresh: {second_download_count - first_download_count} new downloads, {second_image_count} images")
        
        # Second refresh should not download the same images again
        assert second_download_count == first_download_count, \
            f"Expected no new downloads on second refresh, but got {second_download_count - first_download_count}"
    
    def test_image_queue_rotates_rss_images(self, temp_cache_dir):
        """Test that ImageQueue properly rotates through RSS images."""
        from engine.image_queue import ImageQueue
        from sources.base_provider import ImageMetadata, ImageSourceType
        
        # Create test images
        rss_images = []
        for i in range(10):
            rss_images.append(ImageMetadata(
                source_type=ImageSourceType.RSS,
                source_id=f"feed_{i % 3}",  # 3 different feeds
                image_id=f"rss_image_{i}",
                local_path=temp_cache_dir / f"rss_{i}.jpg",
                url=f"https://example.com/rss_{i}.jpg",
                title=f"RSS Image {i}",
            ))
        
        local_images = []
        for i in range(20):
            local_images.append(ImageMetadata(
                source_type=ImageSourceType.FOLDER,
                source_id="local",
                image_id=f"local_image_{i}",
                local_path=temp_cache_dir / f"local_{i}.jpg",
                title=f"Local Image {i}",
            ))
        
        queue = ImageQueue(local_ratio=70, history_size=50)
        queue.add_images(local_images)
        queue.add_images(rss_images)
        
        # Get 30 images and track which ones we get
        selected_images = []
        rss_selected = []
        local_selected = []
        
        for _ in range(30):
            img = queue.next()
            if img:
                selected_images.append(img)
                if img.source_type == ImageSourceType.RSS:
                    rss_selected.append(img.image_id)
                else:
                    local_selected.append(img.image_id)
        
        print("\n=== Queue Rotation Test ===")
        print(f"Total images in queue: {len(local_images) + len(rss_images)}")
        print(f"Images selected: {len(selected_images)}")
        print(f"RSS selected: {len(rss_selected)} ({len(set(rss_selected))} unique)")
        print(f"Local selected: {len(local_selected)} ({len(set(local_selected))} unique)")
        
        # With 70/30 ratio, we should see roughly 30% RSS images
        rss_ratio = len(rss_selected) / len(selected_images) * 100
        print(f"Actual RSS ratio: {rss_ratio:.1f}%")
        
        # Verify we're getting a mix
        assert len(rss_selected) > 0, "Expected some RSS images to be selected"
        assert len(local_selected) > 0, "Expected some local images to be selected"
        
        # Verify we're not just repeating the same RSS image
        unique_rss = len(set(rss_selected))
        assert unique_rss >= min(3, len(rss_selected)), \
            f"Expected at least 3 unique RSS images, got {unique_rss}"
    
    def test_image_queue_history_prevents_duplicates(self, temp_cache_dir):
        """Test that ImageQueue history prevents immediate duplicates."""
        from engine.image_queue import ImageQueue
        from sources.base_provider import ImageMetadata, ImageSourceType
        
        # Create a small pool of RSS images to force potential duplicates
        rss_images = []
        for i in range(3):  # Only 3 RSS images
            rss_images.append(ImageMetadata(
                source_type=ImageSourceType.RSS,
                source_id="test_feed",
                image_id=f"rss_image_{i}",
                local_path=temp_cache_dir / f"rss_{i}.jpg",
                url=f"https://example.com/rss_{i}.jpg",
                title=f"RSS Image {i}",
            ))
        
        # No local images - force RSS selection
        queue = ImageQueue(local_ratio=0, history_size=50)  # 0% local = 100% RSS
        queue.add_images(rss_images)
        
        # Get 10 images and check for consecutive duplicates
        selected = []
        for _ in range(10):
            img = queue.next()
            if img:
                selected.append(img.image_id)
        
        print("\n=== Duplicate Prevention Test ===")
        print(f"RSS pool size: {len(rss_images)}")
        print(f"Selected sequence: {selected}")
        
        # Check for consecutive duplicates
        consecutive_duplicates = 0
        for i in range(1, len(selected)):
            if selected[i] == selected[i-1]:
                consecutive_duplicates += 1
        
        print(f"Consecutive duplicates: {consecutive_duplicates}")
        
        # With history check, we should have minimal consecutive duplicates
        # (some may occur if pool is exhausted)
        assert consecutive_duplicates <= 2, \
            f"Too many consecutive duplicates: {consecutive_duplicates}"
    
    def test_rss_refresh_adds_new_images_only(self, temp_cache_dir, mock_reddit_response):
        """Test that refresh only adds NEW images, not duplicates."""
        from sources.rss_source import RSSSource
        
        feeds = ["https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=10"]
        
        call_count = [0]
        
        def mock_get(url, **kwargs):
            mock_resp = Mock()
            mock_resp.raise_for_status = Mock()
            
            if "EarthPorn" in url and "json" in url:
                call_count[0] += 1
                # Return same images on both calls
                mock_resp.json.return_value = mock_reddit_response("EarthPorn", 5)
            elif "i.redd.it" in url:
                mock_resp.headers = {"Content-Type": "image/jpeg"}
                jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF' + b'\x00' * 1000
                mock_resp.iter_content = lambda chunk_size=8192: iter([jpeg_data])
            else:
                mock_resp.json.return_value = {"kind": "Listing", "data": {"children": []}}
            
            return mock_resp
        
        with patch('requests.get', side_effect=mock_get):
            source = RSSSource(feed_urls=feeds, cache_dir=temp_cache_dir)
            
            # First refresh
            source.refresh()
            first_count = len(source._images)
            
            # Second refresh with same feed data
            source.refresh()
            second_count = len(source._images)
        
        print("\n=== Refresh Deduplication Test ===")
        print(f"After first refresh: {first_count} images")
        print(f"After second refresh: {second_count} images")
        print(f"Feed API calls: {call_count[0]}")
        
        # Second refresh should NOT add duplicates
        assert second_count == first_count, \
            f"Expected {first_count} images after second refresh, got {second_count}"


class TestRSSIntegration:
    """Integration tests for RSS behavior with real network calls (optional)."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        cache_dir = Path(tempfile.mkdtemp(prefix="test_rss_integration_"))
        yield cache_dir
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    @pytest.mark.skip(reason="Requires network access - run manually with: pytest -k test_real -s")
    def test_real_reddit_feed(self, temp_cache_dir):
        """Test with real Reddit feed (requires network).
        
        Run with: pytest tests/test_rss_behavior.py::TestRSSIntegration::test_real_reddit_feed -s --timeout=300
        """
        import time
        from sources.rss_source import RSSSource
        
        feeds = [
            "https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=10",
            "https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=10",
            "https://www.reddit.com/r/SpacePorn/top/.json?t=day&limit=10",
        ]
        
        print("\n=== Real Reddit Feed Test (with rate limiting) ===")
        print(f"Testing {len(feeds)} feeds with 2s delays between each...")
        
        source = RSSSource(feed_urls=feeds, cache_dir=temp_cache_dir)
        
        start_time = time.time()
        source.refresh()
        elapsed = time.time() - start_time
        
        images = source.get_images()
        
        print(f"Time elapsed: {elapsed:.1f}s")
        print(f"Images fetched: {len(images)}")
        print(f"Unique sources: {len(set(img.source_id for img in images))}")
        
        for img in images[:10]:
            print(f"  - {img.title[:50]}... ({img.file_size // 1024}KB)")
        
        assert len(images) > 0, "Expected at least one image from Reddit"
        
    @pytest.mark.skip(reason="Requires network access - run manually")
    def test_rate_limiting_behavior(self, temp_cache_dir):
        """Test that rate limiting detection and retry works.
        
        This test intentionally triggers rate limiting by making rapid requests.
        """
        import time
        from sources.rss_source import RSSSource, RATE_LIMIT_DELAY_SECONDS
        
        print("\n=== Rate Limiting Test ===")
        
        # Create multiple sources that will be hit in sequence
        feeds = [
            "https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=5",
            "https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=5",
        ]
        
        source = RSSSource(feed_urls=feeds, cache_dir=temp_cache_dir)
        
        print(f"Rate limit delay: {RATE_LIMIT_DELAY_SECONDS}s between feeds")
        
        start_time = time.time()
        source.refresh()
        elapsed = time.time() - start_time
        
        images = source.get_images()
        
        print(f"Time elapsed: {elapsed:.1f}s (expected >= {RATE_LIMIT_DELAY_SECONDS * (len(feeds) - 1):.1f}s)")
        print(f"Images fetched: {len(images)}")
        
        # Verify we waited between feeds
        min_expected_time = RATE_LIMIT_DELAY_SECONDS * (len(feeds) - 1)
        assert elapsed >= min_expected_time * 0.9, \
            f"Expected at least {min_expected_time}s delay, got {elapsed}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
