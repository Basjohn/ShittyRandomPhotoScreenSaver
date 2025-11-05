"""Tests for weather widget."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QColor
from widgets.weather_widget import WeatherWidget, WeatherPosition, WeatherFetcher


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def parent_widget(qapp):
    """Create parent widget."""
    widget = QWidget()
    widget.resize(800, 600)
    yield widget
    widget.deleteLater()


@pytest.fixture
def mock_weather_data():
    """Mock weather API response."""
    return {
        'main': {
            'temp': 20.5,
            'humidity': 65
        },
        'weather': [
            {
                'main': 'Clouds',
                'description': 'scattered clouds'
            }
        ],
        'name': 'London'
    }


def test_weather_position_enum():
    """Test WeatherPosition enum."""
    assert WeatherPosition.TOP_LEFT.value == "top_left"
    assert WeatherPosition.TOP_RIGHT.value == "top_right"
    assert WeatherPosition.BOTTOM_LEFT.value == "bottom_left"
    assert WeatherPosition.BOTTOM_RIGHT.value == "bottom_right"


def test_weather_creation(qapp, parent_widget):
    """Test weather widget creation."""
    weather = WeatherWidget(
        parent=parent_widget,
        api_key="test_key",
        location="London",
        position=WeatherPosition.BOTTOM_LEFT
    )
    
    assert weather is not None
    assert weather._api_key == "test_key"
    assert weather._location == "London"
    assert weather._position == WeatherPosition.BOTTOM_LEFT
    assert weather.is_running() is False


def test_weather_no_api_key(qapp, parent_widget):
    """Test weather widget without API key."""
    weather = WeatherWidget(parent=parent_widget, api_key="")
    
    error_emitted = []
    weather.error_occurred.connect(lambda e: error_emitted.append(e))
    
    weather.start()
    
    # Should emit error
    assert len(error_emitted) > 0
    assert "No API Key" in weather.text()


def test_weather_stop(qapp, parent_widget):
    """Test stopping weather widget."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    # Mock the fetch to avoid actual API call
    with patch.object(weather, '_fetch_weather'):
        weather.start()
        assert weather.is_running() is True
        
        weather.stop()
        assert weather.is_running() is False


def test_weather_signals(qapp, parent_widget, mock_weather_data):
    """Test weather signals."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    weather_updates = []
    weather.weather_updated.connect(lambda d: weather_updates.append(d))
    
    # Manually trigger update with mock data
    weather._on_weather_fetched(mock_weather_data)
    
    assert len(weather_updates) == 1
    assert weather_updates[0] == mock_weather_data


def test_weather_display_update(qapp, parent_widget, mock_weather_data):
    """Test weather display update."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    weather._update_display(mock_weather_data)
    text = weather.text()
    
    # Should contain location and temperature
    assert "London" in text
    assert "20°C" in text or "21°C" in text  # Rounded
    assert "Clouds" in text


def test_weather_cache(qapp, parent_widget, mock_weather_data):
    """Test weather caching."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    # Initially no cache
    assert weather._is_cache_valid() is False
    
    # Set cache
    weather._on_weather_fetched(mock_weather_data)
    
    # Cache should be valid
    assert weather._is_cache_valid() is True
    assert weather._cached_data == mock_weather_data


def test_weather_all_positions(qapp, parent_widget):
    """Test all weather positions."""
    positions = [
        WeatherPosition.TOP_LEFT,
        WeatherPosition.TOP_RIGHT,
        WeatherPosition.BOTTOM_LEFT,
        WeatherPosition.BOTTOM_RIGHT
    ]
    
    for position in positions:
        weather = WeatherWidget(
            parent=parent_widget,
            api_key="test_key",
            position=position
        )
        
        assert weather._position == position


def test_weather_set_position(qapp, parent_widget, mock_weather_data):
    """Test changing weather position."""
    weather = WeatherWidget(
        parent=parent_widget,
        api_key="test_key",
        position=WeatherPosition.TOP_LEFT
    )
    
    # Manually set display to get size
    weather._update_display(mock_weather_data)
    old_x, old_y = weather.x(), weather.y()
    
    weather.set_position(WeatherPosition.BOTTOM_RIGHT)
    weather._update_display(mock_weather_data)  # Update position
    new_x, new_y = weather.x(), weather.y()
    
    # Position should have changed
    assert (new_x, new_y) != (old_x, old_y)


def test_weather_set_api_key(qapp, parent_widget):
    """Test setting API key."""
    weather = WeatherWidget(parent=parent_widget, api_key="old_key")
    
    weather.set_api_key("new_key")
    assert weather._api_key == "new_key"
    
    # Cache should be cleared
    assert weather._cached_data is None


def test_weather_set_location(qapp, parent_widget):
    """Test setting location."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key", location="London")
    
    with patch.object(weather, '_fetch_weather') as mock_fetch:
        weather._enabled = True  # Simulate running
        weather.set_location("Paris")
        
        assert weather._location == "Paris"
        # Should trigger fetch
        mock_fetch.assert_called_once()
    
    # Cache should be cleared
    assert weather._cached_data is None


def test_weather_set_font_size(qapp, parent_widget):
    """Test setting font size."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    weather.set_font_size(32)
    assert weather._font_size == 32
    
    # Invalid size should fall back
    weather.set_font_size(-10)
    assert weather._font_size == 24


def test_weather_set_text_color(qapp, parent_widget):
    """Test setting text color."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    color = QColor(255, 0, 0, 255)
    weather.set_text_color(color)
    
    assert weather._text_color == color


def test_weather_cleanup(qapp, parent_widget):
    """Test weather cleanup."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    with patch.object(weather, '_fetch_weather'):
        weather.start()
        assert weather.is_running() is True
        
        weather.cleanup()
        assert weather.is_running() is False
        assert weather._update_timer is None


def test_weather_error_handling(qapp, parent_widget):
    """Test weather error handling."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    error_messages = []
    weather.error_occurred.connect(lambda e: error_messages.append(e))
    
    # Simulate fetch error
    weather._on_fetch_error("Network error")
    
    assert len(error_messages) == 1
    assert "Network error" in error_messages[0]


def test_weather_error_with_cache(qapp, parent_widget, mock_weather_data):
    """Test error handling with valid cache."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    # Set cache first
    weather._on_weather_fetched(mock_weather_data)
    
    # Simulate error
    weather._on_fetch_error("Network error")
    
    # Should fall back to cache
    text = weather.text()
    assert "London" in text


def test_weather_fetcher_creation(qapp):
    """Test WeatherFetcher creation."""
    fetcher = WeatherFetcher(api_key="test_key", location="London")
    
    assert fetcher._api_key == "test_key"
    assert fetcher._location == "London"


@patch('widgets.weather_widget.requests.get')
def test_weather_fetcher_success(mock_get, qapp, mock_weather_data):
    """Test successful weather fetch."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.json.return_value = mock_weather_data
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    fetcher = WeatherFetcher(api_key="test_key", location="London")
    
    data_received = []
    fetcher.data_fetched.connect(lambda d: data_received.append(d))
    
    fetcher.fetch()
    
    assert len(data_received) == 1
    assert data_received[0] == mock_weather_data


@patch('widgets.weather_widget.requests.get')
def test_weather_fetcher_error(mock_get, qapp):
    """Test weather fetch error."""
    # Mock failed API response
    mock_get.side_effect = Exception("Network error")
    
    fetcher = WeatherFetcher(api_key="test_key", location="London")
    
    errors_received = []
    fetcher.error_occurred.connect(lambda e: errors_received.append(e))
    
    fetcher.fetch()
    
    assert len(errors_received) == 1
    assert "Network error" in errors_received[0]


def test_weather_display_no_data(qapp, parent_widget):
    """Test display with no data."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    weather._update_display(None)
    
    assert "No Data" in weather.text()


def test_weather_concurrent_start_prevention(qapp, parent_widget):
    """Test that starting when already running is handled."""
    weather = WeatherWidget(parent=parent_widget, api_key="test_key")
    
    with patch.object(weather, '_fetch_weather'):
        weather.start()
        assert weather.is_running() is True
        
        # Try to start again
        weather.start()
        assert weather.is_running() is True
        
        weather.stop()
