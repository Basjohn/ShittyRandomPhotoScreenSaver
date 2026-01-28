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
    SpotifyVisualizerSettings,
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
        assert settings.max_items == 30
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
    
    def test_from_settings_accepts_prefixed_position(self):
        """WidgetPosition.* strings should coerce correctly."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default=None: {
            "widgets.clock.enabled": True,
            "widgets.clock.position": "WidgetPosition.BOTTOM_RIGHT",
        }.get(key, default)

        model = ClockWidgetSettings.from_settings(mock_settings)

        assert model.position == WidgetPosition.BOTTOM_RIGHT

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
    
    def test_from_settings_accepts_prefixed_position(self):
        """Ensure legacy WidgetPosition.* strings are handled."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default=None: {
            "widgets.weather.position": "WidgetPosition.TOP_CENTER",
        }.get(key, default)

        model = WeatherWidgetSettings.from_settings(mock_settings)

        assert model.position == WidgetPosition.TOP_CENTER

    def test_default_values(self):
        """Test default values."""
        settings = WeatherWidgetSettings()
        
        assert settings.enabled is False
        assert settings.position == WidgetPosition.BOTTOM_LEFT
        assert settings.location == ""


class TestMediaWidgetSettings:
    """Test MediaWidgetSettings dataclass."""
    
    def test_from_settings_accepts_prefixed_position(self):
        """Ensure WidgetPosition.* strings are coerced."""
        stub = MagicMock()
        stub.get.side_effect = lambda key, default=None: {
            "widgets.media.position": "WidgetPosition.MIDDLE_RIGHT",
        }.get(key, default)

        model = MediaWidgetSettings.from_settings(stub)

        assert model.position == WidgetPosition.MIDDLE_RIGHT

    def test_default_values(self):
        """Test default values."""
        settings = MediaWidgetSettings()
        
        assert settings.enabled is False
        assert settings.position == WidgetPosition.BOTTOM_LEFT
        assert settings.artwork_size == 200
        assert settings.show_controls is True

    def test_round_trip_from_settings_and_to_dict(self):
        """Ensure loading from settings and writing back preserves values."""
        backing = {
            "widgets.media.enabled": True,
            "widgets.media.monitor": "2",
            "widgets.media.position": "bottom_left",
            "widgets.media.font_family": "Segoe UI",
            "widgets.media.font_size": 22,
            "widgets.media.text_color": "#ff00ff",
            "widgets.media.show_background": False,
            "widgets.media.background_color": "#101010",
            "widgets.media.background_opacity": 0.8,
            "widgets.media.show_controls": False,
            "widgets.media.show_header_frame": False,
            "widgets.media.artwork_size": 180,
            "widgets.media.intense_shadow": True,
            "widgets.media.margin": 12,
            "widgets.media.border_color": [1, 2, 3, 4],
            "widgets.media.border_opacity": 0.4,
            "widgets.media.color": [9, 8, 7, 6],
            "widgets.media.bg_color": [5, 6, 7, 8],
            "widgets.media.rounded_artwork_border": False,
            "widgets.media.spotify_volume_enabled": False,
            "widgets.media.spotify_volume_fill_color": [10, 11, 12, 13],
        }
        stub = MagicMock()
        stub.get.side_effect = lambda key, default=None: backing.get(key, default)

        model = MediaWidgetSettings.from_settings(stub)
        out = model.to_dict()

        assert out == backing

    def test_from_mapping_accepts_plain_keys(self):
        """Ensure from_mapping can read plain section dicts (non-dotted)."""
        plain = {
            "enabled": True,
            "monitor": "ALL",
            "position": "center",
            "font_family": "Inter",
            "font_size": 18,
            "text_color": "#ffffff",
            "show_background": True,
            "background_color": "#000000",
            "background_opacity": 0.4,
            "show_controls": True,
            "show_header_frame": True,
            "artwork_size": 160,
            "intense_shadow": False,
            "margin": 14,
            "border_color": [10, 20, 30, 40],
            "border_opacity": 0.7,
            "color": [200, 201, 202, 128],
            "bg_color": [11, 22, 33, 44],
            "rounded_artwork_border": True,
            "spotify_volume_enabled": True,
            "spotify_volume_fill_color": [1, 2, 3, 4],
        }

        model = MediaWidgetSettings.from_mapping(plain)

        assert model.enabled is True
        assert model.monitor == "ALL"
        assert model.position == WidgetPosition.CENTER
        assert model.font_family == "Inter"
        assert model.font_size == 18
        assert model.text_color == "#ffffff"
        assert model.show_background is True
        assert model.background_color == "#000000"
        assert model.background_opacity == 0.4
        assert model.show_controls is True
        assert model.show_header_frame is True
        assert model.artwork_size == 160
        assert model.intense_shadow is False
        assert model.margin == 14
        assert model.border_color == [10, 20, 30, 40]
        assert model.border_opacity == 0.7
        assert model.color == [200, 201, 202, 128]
        assert model.bg_color == [11, 22, 33, 44]
        assert model.rounded_artwork_border is True
        assert model.spotify_volume_enabled is True
        assert model.spotify_volume_fill_color == [1, 2, 3, 4]


class TestRedditWidgetSettings:
    """Test RedditWidgetSettings dataclass."""
    
    def test_from_settings_accepts_prefixed_position(self):
        """Ensure WidgetPosition.* strings are coerced."""
        stub = MagicMock()
        stub.get.side_effect = lambda key, default=None: {
            "widgets.reddit.position": "WidgetPosition.BOTTOM_CENTER",
        }.get(key, default)

        model = RedditWidgetSettings.from_settings(stub)

        assert model.position == WidgetPosition.BOTTOM_CENTER

    def test_default_values(self):
        """Test default values."""
        settings = RedditWidgetSettings()
        
        assert settings.enabled is False
        assert settings.position == WidgetPosition.TOP_RIGHT
        assert settings.subreddit == "technology"
        assert settings.limit == 10

    def test_round_trip_from_settings_and_to_dict(self):
        """Ensure loading from settings and writing back preserves values."""
        backing = {
            "widgets.reddit.enabled": True,
            "widgets.reddit.monitor": "1",
            "widgets.reddit.position": "bottom_center",
            "widgets.reddit.subreddit": "wallpapers",
            "widgets.reddit.limit": 20,
            "widgets.reddit.font_family": "Segoe UI",
            "widgets.reddit.font_size": 16,
            "widgets.reddit.text_color": "#123456",
            "widgets.reddit.show_background": False,
            "widgets.reddit.background_color": "#111111",
            "widgets.reddit.background_opacity": 0.6,
            "widgets.reddit.show_separators": False,
            "widgets.reddit.intense_shadow": True,
            "widgets.reddit.margin": 15,
            "widgets.reddit.border_color": [1, 2, 3, 255],
            "widgets.reddit.border_opacity": 0.5,
            "widgets.reddit.color": [5, 6, 7, 8],
        }
        stub = MagicMock()
        stub.get.side_effect = lambda key, default=None: backing.get(key, default)

        model = RedditWidgetSettings.from_settings(stub)
        out = model.to_dict()

        assert out == backing

    def test_from_mapping_accepts_plain_keys(self):
        """Ensure from_mapping can read plain section dicts (non-dotted)."""
        plain = {
            "enabled": True,
            "monitor": "ALL",
            "position": "top_right",
            "subreddit": "pics",
            "limit": 4,
            "font_family": "Inter",
            "font_size": 20,
            "text_color": "#ffffff",
            "show_background": True,
            "background_color": "#000000",
            "background_opacity": 0.4,
            "show_separators": False,
            "intense_shadow": False,
            "margin": 9,
            "border_color": [9, 9, 9, 9],
            "border_opacity": 0.9,
            "color": [1, 2, 3, 4],
        }

        model = RedditWidgetSettings.from_mapping(plain)

        assert model.enabled is True
        assert model.monitor == "ALL"
        assert model.position == WidgetPosition.TOP_RIGHT
        assert model.subreddit == "pics"
        assert model.limit == 4
        assert model.font_family == "Inter"
        assert model.font_size == 20
        assert model.text_color == "#ffffff"
        assert model.show_background is True
        assert model.background_color == "#000000"
        assert model.background_opacity == 0.4
        assert model.show_separators is False
        assert model.intense_shadow is False
        assert model.margin == 9
        assert model.border_color == [9, 9, 9, 9]
        assert model.border_opacity == 0.9
        assert model.color == [1, 2, 3, 4]


class TestSpotifyVisualizerSettings:
    """Test SpotifyVisualizerSettings dataclass."""

    def test_round_trip_from_settings_and_to_dict(self):
        """Ensure loading from settings and writing back preserves values."""
        backing = {
            "widgets.spotify_visualizer.enabled": True,
            "widgets.spotify_visualizer.monitor": "2",
            "widgets.spotify_visualizer.bar_count": 48,
            "widgets.spotify_visualizer.audio_block_size": 512,
            "widgets.spotify_visualizer.ghosting_enabled": False,
            "widgets.spotify_visualizer.ghost_alpha": 0.25,
            "widgets.spotify_visualizer.ghost_decay": 0.55,
            "widgets.spotify_visualizer.adaptive_sensitivity": False,
            "widgets.spotify_visualizer.sensitivity": 2.2,
            "widgets.spotify_visualizer.dynamic_floor": False,
            "widgets.spotify_visualizer.manual_floor": 1.7,
            "widgets.spotify_visualizer.dynamic_range_enabled": True,
            "widgets.spotify_visualizer.mode": "spectrum",
            "widgets.spotify_visualizer.software_visualizer_enabled": True,
        }
        stub = MagicMock()
        stub.get.side_effect = lambda key, default=None: backing.get(key, default)

        model = SpotifyVisualizerSettings.from_settings(stub)
        out = model.to_dict()

        assert out == backing

    def test_from_mapping_accepts_plain_keys(self):
        """Ensure from_mapping can read plain section dicts (non-dotted)."""
        plain = {
            "enabled": True,
            "monitor": "ALL",
            "bar_count": 24,
            "audio_block_size": 256,
            "ghosting_enabled": True,
            "ghost_alpha": 0.6,
            "ghost_decay": 0.4,
            "adaptive_sensitivity": True,
            "sensitivity": 1.3,
            "dynamic_floor": False,
            "manual_floor": 1.1,
            "dynamic_range_enabled": False,
            "mode": "spectrum",
            "software_visualizer_enabled": False,
        }

        model = SpotifyVisualizerSettings.from_mapping(plain)

        assert model.enabled is True
        assert model.monitor == "ALL"
        assert model.bar_count == 24
        assert model.audio_block_size == 256
        assert model.ghosting_enabled is True
        assert model.ghost_alpha == 0.6
        assert model.ghost_decay == 0.4
        assert model.adaptive_sensitivity is True
        assert model.sensitivity == 1.3
        assert model.dynamic_floor is False
        assert model.manual_floor == 1.1
        assert model.dynamic_range_enabled is False
        assert model.mode == "spectrum"
        assert model.software_visualizer_enabled is False

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
