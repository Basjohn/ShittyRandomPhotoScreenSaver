"""
Tests for Settings dataclass models.

Tests the type-safe settings models including:
- Model creation with defaults
- Loading from SettingsManager
- Enum conversions
- Dictionary serialization
"""
from unittest.mock import MagicMock

import pytest

from core.settings.models import (
    DisplayMode,
    TransitionType,
    WidgetPosition,
    DisplaySettings,
    TransitionSettings,
    InputSettings,
    CacheSettings,
    SourceSettings,
    ShadowSettings,
    ClockWidgetSettings,
    WeatherWidgetSettings,
    MediaWidgetSettings,
    RedditWidgetSettings,
    AccessibilitySettings,
    AppSettings,
)


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------

class TestEnums:
    """Test enum definitions."""
    
    def test_display_mode_values(self):
        """Test DisplayMode enum values."""
        assert DisplayMode.FILL.value == "fill"
        assert DisplayMode.FIT.value == "fit"
        assert DisplayMode.SHRINK.value == "shrink"
    
    def test_transition_type_values(self):
        """Test TransitionType enum values."""
        assert TransitionType.CROSSFADE.value == "Crossfade"
        assert TransitionType.SLIDE.value == "Slide"
        assert TransitionType.WIPE.value == "Wipe"
        assert TransitionType.RIPPLE.value == "Ripple"
    
    def test_widget_position_values(self):
        """Test WidgetPosition enum values."""
        assert WidgetPosition.TOP_LEFT.value == "top_left"
        assert WidgetPosition.CENTER.value == "center"
        assert WidgetPosition.BOTTOM_RIGHT.value == "bottom_right"


# ---------------------------------------------------------------------------
# DisplaySettings Tests
# ---------------------------------------------------------------------------

class TestDisplaySettings:
    """Test DisplaySettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = DisplaySettings()
        
        assert settings.refresh_sync is True
        assert settings.hw_accel is True
        assert settings.mode == DisplayMode.FILL
        assert settings.same_image_all_monitors is False
        assert settings.rotation_interval == 45
    
    def test_from_settings(self):
        """Test loading from SettingsManager."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default: {
            "display.refresh_sync": False,
            "display.hw_accel": True,
            "display.mode": "fit",
            "display.same_image_all_monitors": True,
            "timing.interval": 60,
        }.get(key, default)
        
        settings = DisplaySettings.from_settings(mock_settings)
        
        assert settings.refresh_sync is False
        assert settings.hw_accel is True
        assert settings.mode == DisplayMode.FIT
        assert settings.same_image_all_monitors is True
        assert settings.rotation_interval == 60
    
    def test_to_dict(self):
        """Test dictionary serialization."""
        settings = DisplaySettings(
            refresh_sync=False,
            hw_accel=True,
            mode=DisplayMode.SHRINK,
            same_image_all_monitors=True,
            rotation_interval=30,
        )
        
        result = settings.to_dict()
        
        assert result["display.refresh_sync"] is False
        assert result["display.hw_accel"] is True
        assert result["display.mode"] == "shrink"
        assert result["display.same_image_all_monitors"] is True
        assert result["timing.interval"] == 30
    
    def test_invalid_mode_fallback(self):
        """Test fallback for invalid mode."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default: {
            "display.mode": "invalid_mode",
        }.get(key, default)
        
        settings = DisplaySettings.from_settings(mock_settings)
        
        assert settings.mode == DisplayMode.FILL


# ---------------------------------------------------------------------------
# TransitionSettings Tests
# ---------------------------------------------------------------------------

class TestTransitionSettings:
    """Test TransitionSettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = TransitionSettings()
        
        assert settings.type == TransitionType.CROSSFADE
        assert settings.random_always is True
        assert settings.random_choice is None
        assert settings.duration_ms == 2000
        assert settings.durations == {}
        assert settings.pool == {}
    
    def test_from_settings(self):
        """Test loading from SettingsManager."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default: {
            "transitions.type": "Slide",
            "transitions.random_always": False,
            "transitions.random_choice": "Wipe",
            "transitions.duration_ms": 3000,
            "transitions.durations": {"Slide": 2500},
            "transitions.pool": {"Crossfade": True},
        }.get(key, default)
        
        settings = TransitionSettings.from_settings(mock_settings)
        
        assert settings.type == TransitionType.SLIDE
        assert settings.random_always is False
        assert settings.random_choice == "Wipe"
        assert settings.duration_ms == 3000
        assert settings.durations == {"Slide": 2500}
        assert settings.pool == {"Crossfade": True}


# ---------------------------------------------------------------------------
# CacheSettings Tests
# ---------------------------------------------------------------------------

class TestCacheSettings:
    """Test CacheSettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = CacheSettings()
        
        assert settings.prefetch_ahead == 5
        assert settings.max_items == 24
        assert settings.max_memory_mb == 1024
        assert settings.max_concurrent == 2
    
    def test_from_settings(self):
        """Test loading from SettingsManager."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default: {
            "cache.prefetch_ahead": 10,
            "cache.max_items": 50,
            "cache.max_memory_mb": 2048,
            "cache.max_concurrent": 4,
        }.get(key, default)
        
        settings = CacheSettings.from_settings(mock_settings)
        
        assert settings.prefetch_ahead == 10
        assert settings.max_items == 50
        assert settings.max_memory_mb == 2048
        assert settings.max_concurrent == 4


# ---------------------------------------------------------------------------
# SourceSettings Tests
# ---------------------------------------------------------------------------

class TestSourceSettings:
    """Test SourceSettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = SourceSettings()
        
        assert settings.folders == []
        assert settings.rss_feeds == []
        assert settings.rss_save_to_disk is False
        assert settings.local_ratio == 60
    
    def test_from_settings(self):
        """Test loading from SettingsManager."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default: {
            "sources.folders": ["/path/to/images"],
            "sources.rss_feeds": ["https://example.com/feed"],
            "sources.local_ratio": 80,
        }.get(key, default)
        
        settings = SourceSettings.from_settings(mock_settings)
        
        assert settings.folders == ["/path/to/images"]
        assert settings.rss_feeds == ["https://example.com/feed"]
        assert settings.local_ratio == 80


# ---------------------------------------------------------------------------
# Widget Settings Tests
# ---------------------------------------------------------------------------

class TestClockWidgetSettings:
    """Test ClockWidgetSettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = ClockWidgetSettings()
        
        assert settings.enabled is True
        assert settings.monitor == "ALL"
        assert settings.position == WidgetPosition.TOP_RIGHT
        assert settings.format == "12h"
        assert settings.show_seconds is True
    
    def test_from_settings_with_prefix(self):
        """Test loading with custom prefix."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default: {
            "widgets.clock2.enabled": True,
            "widgets.clock2.position": "bottom_left",
            "widgets.clock2.format": "24h",
        }.get(key, default)
        
        settings = ClockWidgetSettings.from_settings(mock_settings, prefix="widgets.clock2")
        
        assert settings.enabled is True
        assert settings.position == WidgetPosition.BOTTOM_LEFT
        assert settings.format == "24h"


class TestWeatherWidgetSettings:
    """Test WeatherWidgetSettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = WeatherWidgetSettings()
        
        assert settings.enabled is False
        assert settings.position == WidgetPosition.BOTTOM_LEFT
        assert settings.location == ""


class TestMediaWidgetSettings:
    """Test MediaWidgetSettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = MediaWidgetSettings()
        
        assert settings.enabled is False
        assert settings.position == WidgetPosition.BOTTOM_LEFT
        assert settings.artwork_size == 200
        assert settings.show_controls is True


class TestRedditWidgetSettings:
    """Test RedditWidgetSettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = RedditWidgetSettings()
        
        assert settings.enabled is False
        assert settings.position == WidgetPosition.TOP_LEFT
        assert settings.subreddit == "technology"
        assert settings.item_limit == 10


# ---------------------------------------------------------------------------
# AccessibilitySettings Tests
# ---------------------------------------------------------------------------

class TestAccessibilitySettings:
    """Test AccessibilitySettings dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = AccessibilitySettings()
        
        assert settings.dimming_enabled is False
        assert settings.dimming_opacity == 30
        assert settings.pixel_shift_enabled is False
        assert settings.pixel_shift_rate == 1
    
    def test_to_dict(self):
        """Test dictionary serialization."""
        settings = AccessibilitySettings(
            dimming_enabled=True,
            dimming_opacity=50,
            pixel_shift_enabled=True,
            pixel_shift_rate=3,
        )
        
        result = settings.to_dict()
        
        assert result["accessibility.dimming.enabled"] is True
        assert result["accessibility.dimming.opacity"] == 50
        assert result["accessibility.pixel_shift.enabled"] is True
        assert result["accessibility.pixel_shift.rate"] == 3


# ---------------------------------------------------------------------------
# AppSettings Tests
# ---------------------------------------------------------------------------

class TestAppSettings:
    """Test AppSettings container dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        settings = AppSettings()
        
        assert isinstance(settings.display, DisplaySettings)
        assert isinstance(settings.transitions, TransitionSettings)
        assert isinstance(settings.input, InputSettings)
        assert isinstance(settings.cache, CacheSettings)
        assert isinstance(settings.sources, SourceSettings)
        assert isinstance(settings.shadows, ShadowSettings)
        assert isinstance(settings.accessibility, AccessibilitySettings)
    
    def test_from_settings(self):
        """Test loading all settings from SettingsManager."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default: default
        
        settings = AppSettings.from_settings(mock_settings)
        
        assert settings.display.hw_accel is True
        assert settings.transitions.type == TransitionType.CROSSFADE
        assert settings.cache.max_memory_mb == 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
