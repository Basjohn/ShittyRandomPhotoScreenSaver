"""
Tests for Widget Factory classes.

Tests the widget factory pattern implementation including:
- Factory registration
- Widget creation
- Configuration handling
- Factory registry
"""
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from rendering.widget_factories import (
    WidgetFactory,
    ClockWidgetFactory,
    WeatherWidgetFactory,
    MediaWidgetFactory,
    RedditWidgetFactory,
    SpotifyVisualizerFactory,
    SpotifyVolumeFactory,
    WidgetFactoryRegistry,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qt_app():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def parent_widget(qt_app):
    """Create a parent widget for testing."""
    parent = QWidget()
    parent.resize(1920, 1080)
    yield parent
    parent.deleteLater()


@pytest.fixture
def mock_settings():
    """Create a mock SettingsManager."""
    return MagicMock()


@pytest.fixture
def mock_thread_manager():
    """Create a mock ThreadManager."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Factory Base Tests
# ---------------------------------------------------------------------------

class TestWidgetFactoryBase:
    """Test WidgetFactory base class."""
    
    def test_factory_is_abstract(self):
        """Test that WidgetFactory cannot be instantiated directly."""
        with pytest.raises(TypeError):
            WidgetFactory(MagicMock())
    
    def test_shadow_config_extraction(self, mock_settings):
        """Test shadow config extraction helper."""
        factory = ClockWidgetFactory(mock_settings)
        
        # With shadow enabled
        config = {
            "shadow": {
                "enabled": True,
                "blur_radius": 20,
                "offset_x": 5,
                "offset_y": 5,
                "color": "#FF0000",
                "opacity": 0.8,
            }
        }
        shadow = factory._get_shadow_config(config)
        assert shadow is not None
        assert shadow["blur_radius"] == 20
        assert shadow["offset_x"] == 5
        assert shadow["color"] == "#FF0000"
        
        # With shadow disabled
        config_disabled = {"shadow": {"enabled": False}}
        shadow_disabled = factory._get_shadow_config(config_disabled)
        assert shadow_disabled is None


# ---------------------------------------------------------------------------
# Clock Widget Factory Tests
# ---------------------------------------------------------------------------

class TestClockWidgetFactory:
    """Test ClockWidgetFactory."""
    
    def test_get_widget_name(self, mock_settings):
        """Test factory returns correct widget name."""
        factory = ClockWidgetFactory(mock_settings)
        assert factory.get_widget_name() == "clock"
    
    def test_create_disabled_returns_none(self, mock_settings, parent_widget):
        """Test disabled widget returns None."""
        factory = ClockWidgetFactory(mock_settings)
        config = {"enabled": False}
        
        widget = factory.create(parent_widget, config)
        
        assert widget is None
    
    def test_create_enabled_returns_widget(self, mock_settings, parent_widget):
        """Test enabled widget is created."""
        factory = ClockWidgetFactory(mock_settings)
        config = {
            "enabled": True,
            "format": "24h",
            "position": "top_right",
            "show_seconds": True,
        }
        
        widget = factory.create(parent_widget, config)
        
        assert widget is not None
        # Clean up
        widget.deleteLater()
    
    def test_create_with_thread_manager(self, mock_settings, mock_thread_manager, parent_widget):
        """Test widget receives thread manager."""
        factory = ClockWidgetFactory(mock_settings, mock_thread_manager)
        config = {"enabled": True}
        
        widget = factory.create(parent_widget, config)
        
        assert widget is not None
        # Clean up
        widget.deleteLater()

    def test_create_applies_screen_specific_display_mode_override(self, mock_settings, parent_widget):
        from PySide6.QtGui import QGuiApplication

        from rendering.custom_layout_contract import get_screen_signature

        parent_widget._screen = QGuiApplication.primaryScreen()
        signature = get_screen_signature(parent_widget._screen)
        factory = ClockWidgetFactory(mock_settings)
        widget = factory.create(
            parent_widget,
            {
                "enabled": True,
                "display_mode": "digital",
                "display_mode_overrides": {signature: "analog"},
            },
        )

        assert widget is not None
        assert widget._display_mode == "analog"
        widget.deleteLater()

    def test_secondary_clock_inherits_calendar_style_but_uses_own_timezone(
        self,
        mock_settings,
        parent_widget,
    ):
        factory = ClockWidgetFactory(mock_settings)
        widget = factory.create(
            parent_widget,
            {"enabled": True, "timezone": "UTC+02:00"},
            settings_key="clock2",
            base_clock_settings={
                "show_day_of_week": True,
                "show_date": True,
                "show_digital_separator": True,
                "calendar_layout": "two_lines",
                "calendar_font_size": 27,
            },
        )

        assert widget is not None
        assert widget._timezone_str == "UTC+02:00"
        assert widget._show_day_of_week is True
        assert widget._show_date is True
        assert widget._show_digital_separator is True
        assert widget._calendar_layout == "two_lines"
        assert widget._calendar_font_size == 27
        widget.deleteLater()


# ---------------------------------------------------------------------------
# Weather Widget Factory Tests
# ---------------------------------------------------------------------------

class TestWeatherWidgetFactory:
    """Test WeatherWidgetFactory."""
    
    def test_get_widget_name(self, mock_settings):
        """Test factory returns correct widget name."""
        factory = WeatherWidgetFactory(mock_settings)
        assert factory.get_widget_name() == "weather"
    
    def test_create_disabled_returns_none(self, mock_settings, parent_widget):
        """Test disabled widget returns None."""
        factory = WeatherWidgetFactory(mock_settings)
        config = {"enabled": False}
        
        widget = factory.create(parent_widget, config)
        
        assert widget is None
    
    def test_create_enabled_returns_widget(self, mock_settings, parent_widget):
        """Test enabled widget is created."""
        factory = WeatherWidgetFactory(mock_settings)
        config = {
            "enabled": True,
            "position": "top_left",
            "api_key": "test_key",
            "location": "London",
        }
        
        widget = factory.create(parent_widget, config)
        
        assert widget is not None
        assert widget._runtime_service is None
        assert widget._owns_runtime_service is False
        # Clean up
        widget.deleteLater()


# ---------------------------------------------------------------------------
# Media Widget Factory Tests
# ---------------------------------------------------------------------------

class TestMediaWidgetFactory:
    """Test MediaWidgetFactory."""
    
    def test_get_widget_name(self, mock_settings):
        """Test factory returns correct widget name."""
        factory = MediaWidgetFactory(mock_settings)
        assert factory.get_widget_name() == "media"
    
    def test_create_disabled_returns_none(self, mock_settings, parent_widget):
        """Test disabled widget returns None."""
        factory = MediaWidgetFactory(mock_settings)
        config = {"enabled": False}
        
        widget = factory.create(parent_widget, config)
        
        assert widget is None

    def test_create_applies_timer_free_playback_progress_style(
        self,
        mock_settings,
        parent_widget,
    ):
        factory = MediaWidgetFactory(mock_settings)

        widget = factory.create(
            parent_widget,
            {
                "enabled": True,
                "playback_progress_enabled": True,
                "playback_progress_height": 9,
                "playback_progress_fill_color": [12, 130, 240, 220],
                "playback_progress_shadow_enabled": True,
                "playback_progress_glow_enabled": True,
                "playback_progress_glow_color": [40, 180, 255, 170],
            },
        )

        assert widget is not None
        assert widget._playback_progress_enabled is True
        assert widget._playback_progress_height == 9
        assert widget._playback_progress_fill_color.getRgb() == (12, 130, 240, 220)
        assert widget._playback_progress_shadow_enabled is True
        assert widget._playback_progress_glow_enabled is True
        assert widget._playback_progress_glow_color.getRgb() == (40, 180, 255, 170)
        assert not hasattr(widget, "_playback_progress_timer")
        assert widget._runtime_service is None
        widget.deleteLater()


# ---------------------------------------------------------------------------
# Reddit Widget Factory Tests
# ---------------------------------------------------------------------------

class TestRedditWidgetFactory:
    """Test RedditWidgetFactory."""
    
    def test_get_widget_name(self, mock_settings):
        """Test factory returns correct widget name."""
        factory = RedditWidgetFactory(mock_settings)
        assert factory.get_widget_name() == "reddit"
    
    def test_create_disabled_returns_none(self, mock_settings, parent_widget):
        """Test disabled widget returns None."""
        factory = RedditWidgetFactory(mock_settings)
        config = {"enabled": False}
        
        widget = factory.create(parent_widget, config)
        
        assert widget is None


# ---------------------------------------------------------------------------
# Spotify Visualizer Factory Tests
# ---------------------------------------------------------------------------

class TestSpotifyVisualizerFactory:
    """Test SpotifyVisualizerFactory."""
    
    def test_get_widget_name(self, mock_settings):
        """Test factory returns correct widget name."""
        factory = SpotifyVisualizerFactory(mock_settings)
        assert factory.get_widget_name() == "spotify_visualizer"
    
    def test_create_disabled_returns_none(self, mock_settings, parent_widget):
        """Test disabled widget returns None."""
        factory = SpotifyVisualizerFactory(mock_settings)
        config = {"enabled": False}
        
        widget = factory.create(parent_widget, config)
        
        assert widget is None


# ---------------------------------------------------------------------------
# Spotify Volume Factory Tests
# ---------------------------------------------------------------------------

class TestSpotifyVolumeFactory:
    """Test SpotifyVolumeFactory."""
    
    def test_get_widget_name(self, mock_settings):
        """Test factory returns correct widget name."""
        factory = SpotifyVolumeFactory(mock_settings)
        assert factory.get_widget_name() == "spotify_volume"


# ---------------------------------------------------------------------------
# Widget Factory Registry Tests
# ---------------------------------------------------------------------------

class TestWidgetFactoryRegistry:
    """Test WidgetFactoryRegistry."""
    
    def test_default_factories_registered(self, mock_settings):
        """Test default factories are registered on init."""
        registry = WidgetFactoryRegistry(mock_settings)
        
        assert registry.get_factory("clock") is not None
        assert registry.get_factory("weather") is not None
        assert registry.get_factory("media") is not None
        assert registry.get_factory("reddit") is not None
        assert registry.get_factory("spotify_visualizer") is not None
        assert registry.get_factory("spotify_volume") is not None
    
    def test_get_all_factory_names(self, mock_settings):
        """Test getting all factory names."""
        registry = WidgetFactoryRegistry(mock_settings)
        
        names = registry.get_all_factory_names()
        
        assert "clock" in names
        assert "weather" in names
        assert "media" in names
        assert "reddit" in names
        assert "spotify_visualizer" in names
        assert "spotify_volume" in names
    
    def test_get_unknown_factory_returns_none(self, mock_settings):
        """Test getting unknown factory returns None."""
        registry = WidgetFactoryRegistry(mock_settings)
        
        factory = registry.get_factory("unknown_widget")
        
        assert factory is None
    
    def test_create_widget_via_registry(self, mock_settings, parent_widget):
        """Test creating widget via registry."""
        registry = WidgetFactoryRegistry(mock_settings)
        config = {
            "enabled": True,
            "format": "12h",
            "position": "top_right",
        }
        
        widget = registry.create_widget("clock", parent_widget, config)
        
        assert widget is not None
        # Clean up
        widget.deleteLater()
    
    def test_create_unknown_widget_returns_none(self, mock_settings, parent_widget):
        """Test creating unknown widget returns None."""
        registry = WidgetFactoryRegistry(mock_settings)
        
        widget = registry.create_widget("unknown", parent_widget, {})
        
        assert widget is None
    
    def test_register_custom_factory(self, mock_settings):
        """Test registering a custom factory."""
        registry = WidgetFactoryRegistry(mock_settings)
        
        # Create a mock factory
        mock_factory = MagicMock(spec=WidgetFactory)
        mock_factory.get_widget_name.return_value = "custom"
        
        registry.register(mock_factory)
        
        assert registry.get_factory("custom") is mock_factory


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
