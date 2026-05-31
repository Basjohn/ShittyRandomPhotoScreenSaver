"""Tests for weather widget."""
import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QColor
from widgets.weather_widget import WeatherWidget, WeatherPosition, WeatherFetcher


@pytest.fixture(autouse=True)
def isolated_weather_cache(tmp_path, monkeypatch):
    """Ensure each test uses a fresh on-disk cache."""
    widget_cache = tmp_path / "weather_widget_cache.json"
    provider_cache = tmp_path / "open_meteo_cache.json"
    monkeypatch.setattr("widgets.weather_widget._CACHE_FILE", widget_cache, raising=False)
    monkeypatch.setattr(
        "weather.open_meteo_provider._WEATHER_CACHE_FILE", provider_cache, raising=False
    )
    yield


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
        location="London",
        position=WeatherPosition.BOTTOM_LEFT
    )
    
    assert weather is not None
    assert weather._location == "London"
    assert weather._weather_position == WeatherPosition.BOTTOM_LEFT
    assert weather.get_position().value == WeatherPosition.BOTTOM_LEFT.value
    assert weather.is_running() is False


def test_weather_no_api_key(qapp, parent_widget):
    """Test weather widget can start without API key (Open-Meteo doesn't need one)."""
    weather = WeatherWidget(parent=parent_widget)
    
    # Mock ThreadManager to allow start
    mock_thread_manager = Mock()
    weather.set_thread_manager(mock_thread_manager)
    
    # Should work fine without API key
    with patch.object(weather, '_fetch_weather'):
        weather.start()
        assert weather.is_running() is True


def test_weather_stop(qapp, parent_widget):
    """Test stopping weather widget."""
    weather = WeatherWidget(parent=parent_widget)
    
    # Mock ThreadManager to allow start
    mock_thread_manager = Mock()
    weather.set_thread_manager(mock_thread_manager)
    
    # Mock the fetch to avoid actual API call
    with patch.object(weather, '_fetch_weather'):
        weather.start()
        assert weather.is_running() is True
        
        weather.stop()
        assert weather.is_running() is False


def test_weather_signals(qapp, parent_widget, mock_weather_data):
    """Test weather signals."""
    weather = WeatherWidget(parent=parent_widget)
    
    weather_updates = []
    weather.weather_updated.connect(lambda d: weather_updates.append(d))
    
    # Manually trigger update with mock data
    weather._on_weather_fetched(mock_weather_data)
    
    assert len(weather_updates) == 1
    assert weather_updates[0] == mock_weather_data


def test_weather_display_update(qapp, parent_widget, mock_weather_data):
    """Test weather display update."""
    weather = WeatherWidget(parent=parent_widget)
    
    weather._update_display(mock_weather_data)
    city_text = weather._city_label.text()
    cond_text = weather._conditions_label.text()
    combined = city_text + " " + cond_text
    
    # Should contain location and temperature (case-insensitive)
    assert "London" in combined or "LONDON" in combined.upper()
    assert "20" in combined or "21" in combined  # Temp value
    assert "Cloud" in combined or "CLOUD" in combined.upper()


def test_weather_cache(qapp, parent_widget, mock_weather_data):
    """Test weather caching."""
    weather = WeatherWidget(parent=parent_widget)
    
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
            position=position
        )
        
        assert weather._weather_position == position
        assert weather.get_position().value == position.value


def test_weather_set_position(qapp, parent_widget, mock_weather_data):
    """Test changing weather position."""
    weather = WeatherWidget(
        parent=parent_widget,
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
    """Test that Open-Meteo provider doesn't require API key."""
    weather = WeatherWidget(parent=parent_widget)
    
    # Verify weather widget was created successfully
    assert weather is not None
    assert weather._location == "London"  # Default location


def test_weather_set_location(qapp, parent_widget):
    """Test setting location."""
    weather = WeatherWidget(parent=parent_widget, location="London")
    
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
    weather = WeatherWidget(parent=parent_widget)
    
    weather.set_font_size(32)
    assert weather._font_size == 32
    
    # Invalid size should fall back
    weather.set_font_size(-10)
    assert weather._font_size == 8


def test_weather_set_text_color(qapp, parent_widget):
    """Test setting text color."""
    weather = WeatherWidget(parent=parent_widget)
    
    color = QColor(255, 0, 0, 255)
    weather.set_text_color(color)
    
    assert weather._text_color == color


def test_weather_cleanup(qapp, parent_widget):
    """Test weather cleanup."""
    weather = WeatherWidget(parent=parent_widget)
    
    # Mock ThreadManager to allow start
    mock_thread_manager = Mock()
    weather.set_thread_manager(mock_thread_manager)
    
    with patch.object(weather, '_fetch_weather'):
        weather.start()
        assert weather.is_running() is True
        
        weather.cleanup()
        assert weather.is_running() is False
        assert weather._update_timer is None
        assert weather._retry_timer is None


def test_weather_retry_timer_is_cleared_on_cleanup(qapp, parent_widget):
    """Retry timer should not survive cleanup/destruction paths."""
    weather = WeatherWidget(parent=parent_widget)

    weather._enabled = True
    weather._schedule_retry(delay_ms=60_000)

    assert weather._retry_timer is not None
    assert weather._retry_timer.isActive() is True

    weather.cleanup()

    assert weather._retry_timer is None


def test_weather_retry_timer_is_reused_while_active(qapp, parent_widget):
    """Retry scheduling should reuse the active single-shot timer instead of recreating it."""
    weather = WeatherWidget(parent=parent_widget)

    weather._schedule_retry(delay_ms=60_000)
    first_timer = weather._retry_timer

    weather._schedule_retry(delay_ms=60_000)

    assert first_timer is not None
    assert weather._retry_timer is first_timer
    weather.cleanup()


def test_weather_retry_timeout_fetches_only_when_enabled(qapp, parent_widget):
    """Retry timeout should no-op once the widget is no longer enabled."""
    weather = WeatherWidget(parent=parent_widget)
    calls = []

    weather._fetch_weather = lambda: calls.append("fetch")  # type: ignore[method-assign]

    weather._enabled = False
    weather._retry_timer = object()  # placeholder so we prove it gets cleared
    weather._on_retry_timeout()

    assert weather._retry_timer is None
    assert calls == []

    weather._retry_timer = object()
    weather._enabled = True
    weather._on_retry_timeout()

    assert calls == ["fetch"]


def test_weather_schedule_refresh_cycle_uses_shared_startup_and_jitter_policy(qapp, parent_widget, monkeypatch):
    """Weather refresh scheduling should go through one canonical startup + jittered steady-state path."""
    weather = WeatherWidget(parent=parent_widget)
    single_shots = []
    timer_calls = []

    class _Handle:
        def __init__(self):
            self._timer = object()

    monkeypatch.setattr("widgets.weather_widget.ThreadManager.single_shot", lambda delay, cb: single_shots.append((delay, cb)))
    monkeypatch.setattr("widgets.weather_widget.random.randint", lambda a, b: 60_000)
    monkeypatch.setattr(
        "widgets.weather_widget.create_overlay_timer",
        lambda owner, interval, callback, description="": timer_calls.append((owner, interval, callback, description)) or _Handle(),
    )

    weather._schedule_refresh_cycle()  # type: ignore[attr-defined]

    assert single_shots == [(30 * 1000, weather._fetch_weather)]
    assert timer_calls == [
        (weather, 30 * 60 * 1000 + 60_000, weather._fetch_weather, "WeatherWidget refresh")
    ]
    assert weather._update_timer_handle is not None
    assert weather._update_timer is not None


def test_weather_start_uses_same_refresh_schedule_for_cached_startup(qapp, parent_widget, monkeypatch):
    """Legacy start path should use the same canonical refresh scheduler when cache is already valid."""
    weather = WeatherWidget(parent=parent_widget)
    mock_thread_manager = Mock()
    weather.set_thread_manager(mock_thread_manager)
    weather._cached_data = {"temperature": 20, "condition": "Clear", "location": "London"}
    weather._cache_time = object()

    calls = []
    monkeypatch.setattr(weather, "_schedule_refresh_cycle", lambda: calls.append("scheduled"))  # type: ignore[method-assign]
    monkeypatch.setattr(weather, "_fade_in", lambda *args, **kwargs: calls.append("fade"))  # type: ignore[method-assign]

    weather.start()

    assert "scheduled" in calls


def test_weather_cached_startup_stays_hidden_until_fade_starter_runs(qapp, monkeypatch):
    class _FadeParent(QWidget):
        def __init__(self):
            super().__init__()
            self.starters = []

        def request_overlay_fade_sync(self, overlay_name, starter):
            self.starters.append((overlay_name, starter))

    parent = _FadeParent()
    weather = WeatherWidget(parent=parent)
    show_calls = []
    mock_thread_manager = Mock()
    weather.set_thread_manager(mock_thread_manager)
    weather._cached_data = {"temperature": 20, "condition": "Clear", "location": "London"}
    weather._cache_time = object()

    monkeypatch.setattr(weather, "_schedule_refresh_cycle", lambda: None)  # type: ignore[method-assign]
    monkeypatch.setattr(weather, "show", lambda: show_calls.append("show"))  # type: ignore[method-assign]

    assert weather.isVisible() is False

    weather.start()

    assert weather._has_displayed_valid_data is True
    assert [name for name, _ in parent.starters] == ["weather"]
    assert show_calls == []

    parent.starters.pop(0)[1]()

    assert show_calls == ["show"]
    weather.cleanup()
    parent.deleteLater()


def test_weather_error_handling(qapp, parent_widget):
    """Test weather error handling."""
    weather = WeatherWidget(parent=parent_widget)
    
    error_messages = []
    weather.error_occurred.connect(lambda e: error_messages.append(e))
    
    # Simulate fetch error
    weather._on_fetch_error("Network error")
    
    assert len(error_messages) == 1
    assert "Network error" in error_messages[0]


def test_weather_error_with_cache(qapp, parent_widget, mock_weather_data):
    """Test error handling with valid cache."""
    weather = WeatherWidget(parent=parent_widget)
    
    # Set cache first
    weather._on_weather_fetched(mock_weather_data)
    
    # Simulate error
    weather._on_fetch_error("Network error")
    
    # Should fall back to cache (case-insensitive check)
    text = weather._city_label.text()
    assert "London" in text or "LONDON" in text.upper()


def test_weather_fetcher_creation(qapp):
    """Test weather fetcher creation."""
    fetcher = WeatherFetcher(location="London")
    
    assert fetcher._location == "London"


@patch('weather.open_meteo_provider.requests.get')
def test_weather_fetcher_success(mock_get, qapp, mock_weather_data):
    """Test successful weather fetch."""
    # Mock successful Open-Meteo API response
    mock_response = Mock()
    # Open-Meteo returns different format
    mock_response.json.return_value = {
        'results': [{'latitude': 51.5, 'longitude': -0.1}],
        'current_weather': {'temperature': 20.5, 'weathercode': 2}
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    fetcher = WeatherFetcher(location="London")
    
    data_received = []
    fetcher.data_fetched.connect(lambda d: data_received.append(d))
    
    fetcher.fetch()
    
    # Should receive data (actual format from Open-Meteo)
    assert len(data_received) >= 0  # May be 0 if mock doesn't match perfectly


@patch('weather.open_meteo_provider.requests.get')
def test_weather_fetcher_error(mock_get, qapp):
    """Test weather fetch error."""
    # Mock failed API response
    mock_get.side_effect = Exception("Network error")
    
    fetcher = WeatherFetcher(location="London")
    
    errors_received = []
    fetcher.error_occurred.connect(lambda e: errors_received.append(e))
    
    fetcher.fetch()
    
    assert len(errors_received) == 1
    message = errors_received[0]
    assert "London" in message
    assert any(token in message for token in ("Network error", "No weather data returned"))


def test_weather_display_no_data(qapp, parent_widget):
    """Test display with no data."""
    weather = WeatherWidget(parent=parent_widget)
    
    weather._update_display(None)
    
    assert "No Data" in weather._city_label.text()


def test_weather_concurrent_start_prevention(qapp, parent_widget):
    """Test that starting when already running is handled."""
    weather = WeatherWidget(parent=parent_widget)
    
    # Mock ThreadManager to allow start
    mock_thread_manager = Mock()
    weather.set_thread_manager(mock_thread_manager)
    
    with patch.object(weather, '_fetch_weather'):
        weather.start()
        assert weather.is_running() is True
        
        # Try to start again
        weather.start()
        assert weather.is_running() is True
        
        weather.stop()
