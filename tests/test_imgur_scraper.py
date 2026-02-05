"""Unit tests for ImgurScraper.

Tests cover:
- HTML parsing
- Rate limiting behavior
- Image extraction
- Error handling
"""
import pytest
from unittest.mock import patch, MagicMock
import time

from widgets.imgur.scraper import (
    ImgurScraper, ImgurImage, ScrapeResult,
    IMGUR_TAG_URL, IMGUR_HOT_URL,
    MIN_REQUEST_INTERVAL_MS, BACKOFF_MULTIPLIER,
)


class TestImgurImage:
    """Tests for ImgurImage dataclass."""
    
    def test_image_creation(self):
        """Test basic image creation."""
        img = ImgurImage(
            id="abc123",
            url="https://i.imgur.com/abc123l.jpg",
            thumbnail_url="https://i.imgur.com/abc123t.jpg",
            gallery_url="https://imgur.com/gallery/abc123",
        )
        assert img.id == "abc123"
        assert img.is_animated == False
        assert img.extension == "jpg"
    
    def test_get_large_url(self):
        """Test large URL generation."""
        img = ImgurImage(
            id="test123",
            url="",
            thumbnail_url="",
            gallery_url="",
            extension="png",
        )
        assert img.get_large_url() == "https://i.imgur.com/test123l.png"
    
    def test_get_original_url(self):
        """Test original URL generation."""
        img = ImgurImage(
            id="test123",
            url="",
            thumbnail_url="",
            gallery_url="",
            extension="gif",
        )
        assert img.get_original_url() == "https://i.imgur.com/test123.gif"


class TestScrapeResult:
    """Tests for ScrapeResult dataclass."""
    
    def test_success_result(self):
        """Test successful scrape result."""
        result = ScrapeResult(
            images=[ImgurImage("a", "", "", "")],
            success=True,
        )
        assert result.success
        assert len(result.images) == 1
        assert result.error is None
    
    def test_error_result(self):
        """Test error scrape result."""
        result = ScrapeResult(
            success=False,
            error="Network error",
        )
        assert not result.success
        assert result.error == "Network error"
        assert len(result.images) == 0
    
    def test_rate_limited_result(self):
        """Test rate-limited result."""
        result = ScrapeResult(
            success=False,
            rate_limited=True,
            retry_after_ms=60000,
        )
        assert not result.success
        assert result.rate_limited
        assert result.retry_after_ms == 60000


class TestImgurScraper:
    """Tests for ImgurScraper class."""
    
    def test_init(self):
        """Test scraper initialization."""
        scraper = ImgurScraper()
        assert scraper._backoff_ms == MIN_REQUEST_INTERVAL_MS
        assert scraper._consecutive_failures == 0
    
    def test_build_tag_url_regular(self):
        """Test URL building for regular tags."""
        scraper = ImgurScraper()
        url = scraper._build_tag_url("cats")
        assert url == IMGUR_TAG_URL.format(tag="cats")
    
    def test_build_tag_url_hot(self):
        """Test URL building for hot/most_viral."""
        scraper = ImgurScraper()
        assert scraper._build_tag_url("most_viral") == IMGUR_HOT_URL
        assert scraper._build_tag_url("hot") == IMGUR_HOT_URL
    
    def test_build_tag_url_sanitization(self):
        """Test that special characters are removed from tags."""
        scraper = ImgurScraper()
        url = scraper._build_tag_url("my<script>tag")
        assert "<script>" not in url
    
    def test_record_success_resets_backoff(self):
        """Test that success resets backoff."""
        scraper = ImgurScraper()
        scraper._backoff_ms = 5000
        scraper._consecutive_failures = 3
        
        scraper._record_success()
        
        assert scraper._backoff_ms == MIN_REQUEST_INTERVAL_MS
        assert scraper._consecutive_failures == 0
    
    def test_record_failure_increases_backoff(self):
        """Test that rate limit failures increase backoff."""
        scraper = ImgurScraper()
        initial_backoff = scraper._backoff_ms
        
        scraper._record_failure(is_rate_limit=True)
        
        assert scraper._backoff_ms == int(initial_backoff * BACKOFF_MULTIPLIER)
        assert scraper._consecutive_failures == 1
    
    def test_get_headers_has_user_agent(self):
        """Test that headers include User-Agent."""
        scraper = ImgurScraper()
        headers = scraper._get_headers()
        assert "User-Agent" in headers
        assert len(headers["User-Agent"]) > 0
    
    @patch('widgets.imgur.scraper.requests.get')
    def test_scrape_tag_success(self, mock_get):
        """Test successful scrape with mock response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <div class="post" data-id="abc123">
            <a href="/gallery/abc123"><img src="//i.imgur.com/abc123l.jpg"/></a>
        </div>
        <div class="post" data-id="def456">
            <a href="/gallery/def456"><img src="//i.imgur.com/def456l.jpg"/></a>
        </div>
        </html>
        '''
        mock_get.return_value = mock_response
        
        scraper = ImgurScraper()
        result = scraper.scrape_tag("test")
        
        assert result.success
        assert len(result.images) >= 1
    
    @patch('widgets.imgur.scraper.requests.get')
    def test_scrape_tag_rate_limited(self, mock_get):
        """Test rate-limited response handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_get.return_value = mock_response
        
        scraper = ImgurScraper()
        result = scraper.scrape_tag("test")
        
        assert not result.success
        assert result.rate_limited
        assert result.retry_after_ms == 30000
    
    @patch('widgets.imgur.scraper.requests.get')
    def test_scrape_tag_network_error(self, mock_get):
        """Test network error handling."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")
        
        scraper = ImgurScraper()
        result = scraper.scrape_tag("test")
        
        assert not result.success
        assert "Connection failed" in result.error
    
    def test_popular_tags_list(self):
        """Test that popular tags are defined."""
        assert len(ImgurScraper.POPULAR_TAGS) > 0
        for tag_id, display_name in ImgurScraper.POPULAR_TAGS:
            assert isinstance(tag_id, str)
            assert isinstance(display_name, str)


class TestImgurScraperParsing:
    """Tests for HTML parsing."""
    
    def test_parse_html_with_gallery_links(self):
        """Test parsing HTML with gallery links."""
        html = '''
        <a href="/gallery/test12345">Image 1</a>
        <a href="/gallery/abcde67890">Image 2</a>
        '''
        scraper = ImgurScraper()
        images = scraper._parse_html(html)
        
        # Should find at least some images from regex fallback
        assert len(images) >= 2
    
    def test_parse_html_empty(self):
        """Test parsing empty HTML."""
        scraper = ImgurScraper()
        images = scraper._parse_html("")
        assert len(images) == 0
    
    def test_parse_html_no_images(self):
        """Test parsing HTML with no images."""
        html = "<html><body><p>No images here</p></body></html>"
        scraper = ImgurScraper()
        images = scraper._parse_html(html)
        assert len(images) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
