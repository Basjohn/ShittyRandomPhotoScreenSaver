from unittest.mock import Mock, patch

from weather.open_meteo_provider import OpenMeteoProvider


@patch("weather.open_meteo_provider._weather_get")
def test_get_current_weather_uses_documented_current_block(
    mock_get,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "weather.open_meteo_provider._WEATHER_CACHE_FILE",
        tmp_path / "weather.json",
    )
    geocode_response = Mock()
    geocode_response.raise_for_status = Mock()
    geocode_response.json.return_value = {
        "results": [{"latitude": -26.104, "longitude": 28.054, "name": "Sandton", "country": "South Africa"}]
    }

    weather_response = Mock()
    weather_response.raise_for_status = Mock()
    weather_response.json.return_value = {
        "current": {
            "temperature_2m": 18.5,
            "weather_code": 2,
            "wind_speed_10m": 12.0,
            "is_day": 1,
            "relative_humidity_2m": 48,
            "precipitation": 0.0,
            "rain": 0.0,
        },
        "hourly": {"precipitation_probability": [15]},
        "daily": {
            "time": [
                "2026-09-18", "2026-09-19", "2026-09-20",
                "2026-09-21", "2026-09-22", "2026-09-23",
            ],
            "temperature_2m_max": [20.0, 23.0, 24.0, 25.0, 21.0, 19.0],
            "temperature_2m_min": [11.0, 13.0, 14.0, 15.0, 12.0, 10.0],
            "weathercode": [2, 3, 1, 0, 61, 63],
        },
    }
    mock_get.side_effect = [geocode_response, weather_response]

    provider = OpenMeteoProvider()
    weather = provider.get_current_weather("Sandton, South Africa")

    assert weather is not None
    assert weather["temperature"] == 18.5
    assert weather["weather_code"] == 2
    assert weather["windspeed"] == 12.0
    assert weather["humidity"] == 48
    assert weather["precipitation_probability"] == 15
    assert len(weather["forecast_days"]) == 5
    assert weather["forecast_days"][0].startswith("Sat: 13°-23°C")
    params = mock_get.call_args_list[1].kwargs["params"]
    assert "current_weather" not in params
    assert params["current"].startswith("temperature_2m,weather_code,wind_speed_10m")
    assert params["forecast_days"] == 6
