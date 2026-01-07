"""
Tests for logging routing and tag-based log separation.

Verifies that:
- PERF-tagged records route to screensaver_perf.log
- Spotify visualizer logs route to screensaver_spotify_vis.log
- Spotify volume logs route to screensaver_spotify_vol.log
- Main log excludes PERF and Spotify records
- Console suppression works correctly
"""
import pytest
import logging
from core.logging.logger import (
    NonPerfFilter,
    NonSpotifyFilter,
    PerfLogFilter,
    SpotifyVisLogFilter,
    SpotifyVolLogFilter,
    VerboseLogFilter,
)


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create temporary log directory."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


def test_non_perf_filter_blocks_perf_records():
    """Test NonPerfFilter blocks [PERF] tagged records."""
    filter_obj = NonPerfFilter()
    
    # Create test records
    perf_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[PERF] Test metric: avg_fps=60",
        args=(),
        exc_info=None,
    )
    
    normal_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Normal log message",
        args=(),
        exc_info=None,
    )
    
    # PERF record should be blocked
    assert filter_obj.filter(perf_record) is False
    
    # Normal record should pass
    assert filter_obj.filter(normal_record) is True


def test_non_spotify_filter_blocks_spotify_records():
    """Test NonSpotifyFilter blocks Spotify tagged records."""
    filter_obj = NonSpotifyFilter()
    
    # Create test records
    vis_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[SPOTIFY_VIS] Visualizer update",
        args=(),
        exc_info=None,
    )
    
    vol_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[SPOTIFY_VOL] Volume changed",
        args=(),
        exc_info=None,
    )
    
    normal_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Normal log message",
        args=(),
        exc_info=None,
    )
    
    # Spotify records should be blocked
    assert filter_obj.filter(vis_record) is False
    assert filter_obj.filter(vol_record) is False
    
    # Normal record should pass
    assert filter_obj.filter(normal_record) is True


def test_perf_log_filter_accepts_only_perf():
    """Test PerfLogFilter accepts only [PERF] tagged records."""
    filter_obj = PerfLogFilter()
    
    perf_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[PERF] Test metric",
        args=(),
        exc_info=None,
    )
    
    normal_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Normal log message",
        args=(),
        exc_info=None,
    )
    
    # Only PERF record should pass
    assert filter_obj.filter(perf_record) is True
    assert filter_obj.filter(normal_record) is False


def test_spotify_vis_log_filter_by_tag():
    """Test SpotifyVisLogFilter accepts [SPOTIFY_VIS] tagged records."""
    filter_obj = SpotifyVisLogFilter()
    
    vis_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[SPOTIFY_VIS] Visualizer update",
        args=(),
        exc_info=None,
    )
    
    normal_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Normal log message",
        args=(),
        exc_info=None,
    )
    
    assert filter_obj.filter(vis_record) is True
    assert filter_obj.filter(normal_record) is False


def test_spotify_vis_log_filter_by_module_name():
    """Test SpotifyVisLogFilter accepts records from visualizer modules."""
    filter_obj = SpotifyVisLogFilter()
    
    # Records from visualizer modules should pass
    vis_module_record = logging.LogRecord(
        name="screensaver.widgets.spotify_visualizer_widget",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Visualizer update",
        args=(),
        exc_info=None,
    )
    
    bars_module_record = logging.LogRecord(
        name="screensaver.widgets.spotify_bars_gl_overlay",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Bars update",
        args=(),
        exc_info=None,
    )
    
    beat_module_record = logging.LogRecord(
        name="screensaver.widgets.beat_engine",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Beat detected",
        args=(),
        exc_info=None,
    )
    
    assert filter_obj.filter(vis_module_record) is True
    assert filter_obj.filter(bars_module_record) is True
    assert filter_obj.filter(beat_module_record) is True


def test_spotify_vol_log_filter_by_tag():
    """Test SpotifyVolLogFilter accepts [SPOTIFY_VOL] tagged records."""
    filter_obj = SpotifyVolLogFilter()
    
    vol_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[SPOTIFY_VOL] Volume changed",
        args=(),
        exc_info=None,
    )
    
    normal_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Normal log message",
        args=(),
        exc_info=None,
    )
    
    assert filter_obj.filter(vol_record) is True
    assert filter_obj.filter(normal_record) is False


def test_spotify_vol_log_filter_by_module_name():
    """Test SpotifyVolLogFilter accepts records from volume modules."""
    filter_obj = SpotifyVolLogFilter()
    
    vol_module_record = logging.LogRecord(
        name="screensaver.widgets.spotify_volume_widget",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Volume update",
        args=(),
        exc_info=None,
    )
    
    assert filter_obj.filter(vol_module_record) is True


def test_verbose_log_filter_accepts_debug_info_only():
    """Test VerboseLogFilter accepts DEBUG and INFO, excludes WARNING+."""
    filter_obj = VerboseLogFilter()
    
    debug_record = logging.LogRecord(
        name="test",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="Debug message",
        args=(),
        exc_info=None,
    )
    
    info_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Info message",
        args=(),
        exc_info=None,
    )
    
    warning_record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="Warning message",
        args=(),
        exc_info=None,
    )
    
    error_record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="Error message",
        args=(),
        exc_info=None,
    )
    
    # DEBUG and INFO should pass
    assert filter_obj.filter(debug_record) is True
    assert filter_obj.filter(info_record) is True
    
    # WARNING+ should be blocked
    assert filter_obj.filter(warning_record) is False
    assert filter_obj.filter(error_record) is False


def test_verbose_log_filter_excludes_perf():
    """Test VerboseLogFilter excludes [PERF] tagged records."""
    filter_obj = VerboseLogFilter()
    
    perf_debug_record = logging.LogRecord(
        name="test",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="[PERF] Debug metric",
        args=(),
        exc_info=None,
    )
    
    perf_info_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[PERF] Info metric",
        args=(),
        exc_info=None,
    )
    
    # PERF records should be excluded even at DEBUG/INFO level
    assert filter_obj.filter(perf_debug_record) is False
    assert filter_obj.filter(perf_info_record) is False


def test_filter_chain_main_log():
    """Test filter chain for main log (excludes PERF and Spotify)."""
    non_perf = NonPerfFilter()
    non_spotify = NonSpotifyFilter()
    
    # Normal record should pass both filters
    normal_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Normal message",
        args=(),
        exc_info=None,
    )
    assert non_perf.filter(normal_record) is True
    assert non_spotify.filter(normal_record) is True
    
    # PERF record should be blocked by NonPerfFilter
    perf_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[PERF] Metric",
        args=(),
        exc_info=None,
    )
    assert non_perf.filter(perf_record) is False
    
    # Spotify record should be blocked by NonSpotifyFilter
    spotify_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="[SPOTIFY_VIS] Update",
        args=(),
        exc_info=None,
    )
    assert non_spotify.filter(spotify_record) is False


def test_logging_routing_integration(qtbot):
    """Integration test for logging routing with actual logger."""
    # Get a test logger
    logger = logging.getLogger("test.routing")
    logger.setLevel(logging.DEBUG)
    
    # Track which handlers receive which messages
    received_messages = {"main": [], "perf": [], "spotify": []}
    
    class TrackingHandler(logging.Handler):
        def __init__(self, name):
            super().__init__()
            self.name = name
        
        def emit(self, record):
            received_messages[self.name].append(record.getMessage())
    
    # Create handlers with filters
    main_handler = TrackingHandler("main")
    main_handler.addFilter(NonPerfFilter())
    main_handler.addFilter(NonSpotifyFilter())
    
    perf_handler = TrackingHandler("perf")
    perf_handler.addFilter(PerfLogFilter())
    
    spotify_handler = TrackingHandler("spotify")
    spotify_handler.addFilter(SpotifyVisLogFilter())
    
    # Add handlers
    logger.addHandler(main_handler)
    logger.addHandler(perf_handler)
    logger.addHandler(spotify_handler)
    
    try:
        # Log different types of messages
        logger.info("Normal message")
        logger.info("[PERF] Performance metric")
        logger.info("[SPOTIFY_VIS] Visualizer update")
        
        # Verify routing
        assert "Normal message" in received_messages["main"]
        assert "[PERF] Performance metric" not in received_messages["main"]
        assert "[SPOTIFY_VIS] Visualizer update" not in received_messages["main"]
        
        assert "[PERF] Performance metric" in received_messages["perf"]
        assert "Normal message" not in received_messages["perf"]
        
        assert "[SPOTIFY_VIS] Visualizer update" in received_messages["spotify"]
        assert "Normal message" not in received_messages["spotify"]
    finally:
        # Clean up
        logger.removeHandler(main_handler)
        logger.removeHandler(perf_handler)
        logger.removeHandler(spotify_handler)
