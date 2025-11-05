"""Manual test for RSS source - verify feed parsing and image downloading."""
import sys
import time
from pathlib import Path
from sources.rss_source import RSSSource, DEFAULT_RSS_FEEDS
from core.logging.logger import setup_logging, get_logger

setup_logging(debug=True)
logger = get_logger(__name__)


def test_default_feeds():
    """Test with default NASA feeds."""
    logger.info("=" * 60)
    logger.info("Testing RSS Source with Default Feeds")
    logger.info("=" * 60)
    
    # Create RSS source
    rss_source = RSSSource()
    
    # Show source info
    info = rss_source.get_source_info()
    logger.info(f"Source Type: {info['type']}")
    logger.info(f"Number of feeds: {info['feeds']}")
    logger.info(f"Cache directory: {info['cache_directory']}")
    
    # List feeds
    logger.info("\nConfigured feeds:")
    for name, url in DEFAULT_RSS_FEEDS.items():
        logger.info(f"  - {name}: {url}")
    
    # Check availability
    logger.info(f"\nSource available: {rss_source.is_available()}")
    
    # Refresh feeds
    logger.info("\nRefreshing feeds (this may take a while)...")
    start_time = time.time()
    rss_source.refresh()
    elapsed = time.time() - start_time
    
    # Get images
    images = rss_source.get_images()
    
    logger.info(f"\nRefresh complete in {elapsed:.2f}s")
    logger.info(f"Total images found: {len(images)}")
    
    # Show feed data
    info = rss_source.get_source_info()
    logger.info("\nFeed details:")
    for url, data in info.get('feed_data', {}).items():
        logger.info(f"  Feed: {data.get('title')}")
        logger.info(f"    Entries: {data.get('entries_count')}")
        logger.info(f"    Updated: {data.get('updated')}")
    
    # Show first few images
    logger.info("\nSample images:")
    for i, img in enumerate(images[:5], 1):
        logger.info(f"\n  Image {i}:")
        logger.info(f"    Title: {img.title}")
        logger.info(f"    Source: {img.source_identifier}")
        logger.info(f"    Path: {img.path}")
        logger.info(f"    Size: {img.file_size / 1024:.1f} KB")
        logger.info(f"    Format: {img.format}")
        if img.published_date:
            logger.info(f"    Published: {img.published_date}")
        
        # Verify file exists
        path = Path(img.path)
        if path.exists():
            logger.info(f"    ✓ File exists")
        else:
            logger.warning(f"    ✗ File not found!")
    
    logger.info("\n" + "=" * 60)
    logger.info("Test Complete")
    logger.info("=" * 60)


def test_custom_feed():
    """Test with a custom feed (Wikimedia)."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Custom Feed (Wikimedia Picture of the Day)")
    logger.info("=" * 60)
    
    wikimedia_feed = "https://commons.wikimedia.org/w/api.php?action=featuredfeed&feed=potd&feedformat=rss&language=en"
    
    rss_source = RSSSource(feed_urls=[wikimedia_feed])
    
    logger.info(f"Feed URL: {wikimedia_feed}")
    logger.info("\nRefreshing...")
    
    rss_source.refresh()
    images = rss_source.get_images()
    
    logger.info(f"Images found: {len(images)}")
    
    if images:
        img = images[0]
        logger.info(f"\nFirst image:")
        logger.info(f"  Title: {img.title}")
        logger.info(f"  Path: {img.path}")
        logger.info(f"  Size: {img.file_size / 1024:.1f} KB")


def test_cache_management():
    """Test cache cleanup."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Cache Management")
    logger.info("=" * 60)
    
    # Create source with small cache limit
    rss_source = RSSSource(max_cache_size_mb=1)  # Only 1MB cache
    
    logger.info("Cache limit: 1MB")
    logger.info("\nRefreshing feeds...")
    rss_source.refresh()
    
    images = rss_source.get_images()
    logger.info(f"Images cached: {len(images)}")
    
    # Check cache directory
    cache_dir = Path(rss_source.cache_dir)
    cache_files = list(cache_dir.glob('*'))
    total_size = sum(f.stat().st_size for f in cache_files if f.is_file())
    
    logger.info(f"\nCache statistics:")
    logger.info(f"  Files: {len(cache_files)}")
    logger.info(f"  Total size: {total_size / 1024 / 1024:.2f}MB")
    
    # Clear cache
    logger.info("\nClearing cache...")
    removed = rss_source.clear_cache()
    logger.info(f"Removed {removed} files")


if __name__ == "__main__":
    try:
        # Test 1: Default feeds
        test_default_feeds()
        
        # Test 2: Custom feed
        # test_custom_feed()
        
        # Test 3: Cache management
        # test_cache_management()
        
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)
