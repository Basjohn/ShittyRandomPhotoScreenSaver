"""
Open-Meteo weather provider.

Free weather API with no API key required.
- Geocoding: City name → lat/lon
- Weather: Current weather data
"""
from typing import Optional, Dict, Any, Tuple
import requests
from core.logging.logger import get_logger

logger = get_logger(__name__)


class OpenMeteoProvider:
    """
    Weather provider using Open-Meteo API (free, no API key).
    
    Features:
    - Geocoding (city → coordinates)
    - Current weather data
    - No API key required
    - Free tier: 10,000 requests/day
    
    API Documentation: https://open-meteo.com/
    """
    
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    
    # Weather code mapping (WMO Weather interpretation codes)
    WEATHER_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }
    
    def __init__(self, timeout: int = 10):
        """
        Initialize Open-Meteo provider.
        
        Args:
            timeout: Request timeout in seconds
        """
        self._timeout = timeout
        self._cached_coords: Dict[str, Tuple[float, float]] = {}  # City → (lat, lon)
        
        logger.debug("OpenMeteoProvider initialized")
    
    def geocode(self, city: str) -> Optional[Tuple[float, float]]:
        """
        Convert city name to coordinates.
        
        Args:
            city: City name (e.g., "London", "New York", "Tokyo")
        
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        # Check cache
        if city in self._cached_coords:
            logger.debug(f"Using cached coordinates for {city}")
            return self._cached_coords[city]
        
        try:
            logger.debug(f"Geocoding city: {city}")
            
            params = {
                'name': city,
                'count': 1,  # Only need top result
                'language': 'en',
                'format': 'json'
            }
            
            response = requests.get(self.GEOCODING_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if results exist
            if not data.get('results'):
                logger.warning(f"No geocoding results for city: {city}")
                return None
            
            # Get first result
            result = data['results'][0]
            latitude = result['latitude']
            longitude = result['longitude']
            result_name = result.get('name', city)
            country = result.get('country', '')
            
            logger.info(f"Geocoded {city} → {result_name}, {country} ({latitude:.2f}, {longitude:.2f})")
            
            # Cache result
            coords = (latitude, longitude)
            self._cached_coords[city] = coords
            
            return coords
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Geocoding request failed for {city}: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Failed to parse geocoding response for {city}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error during geocoding for {city}: {e}")
            return None
    
    def get_current_weather(self, city: str) -> Optional[Dict[str, Any]]:
        """
        Get current weather for a city.
        
        Args:
            city: City name
        
        Returns:
            Dictionary with weather data:
            {
                'location': str,        # City name
                'temperature': float,   # Temperature in Celsius
                'condition': str,       # Weather condition description
                'weather_code': int,    # WMO weather code
                'windspeed': float,     # Wind speed in km/h
                'humidity': float       # Relative humidity %
            }
            or None if request fails
        """
        # Geocode city to coordinates
        coords = self.geocode(city)
        if not coords:
            logger.error(f"Cannot fetch weather - failed to geocode: {city}")
            return None
        
        latitude, longitude = coords
        
        try:
            logger.debug(f"Fetching weather for {city} ({latitude:.2f}, {longitude:.2f})")
            
            params = {
                'latitude': latitude,
                'longitude': longitude,
                'current_weather': 'true',
                'current': 'relative_humidity_2m',  # Additional current data
                'daily': 'temperature_2m_max,temperature_2m_min,weathercode',  # Tomorrow's forecast
                'forecast_days': 2,  # Today + tomorrow
                'timezone': 'auto'
            }
            
            response = requests.get(self.WEATHER_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract current weather
            current = data.get('current_weather', {})
            current_units = data.get('current', {})
            
            temperature = current.get('temperature')
            weather_code = current.get('weathercode', 0)
            windspeed = current.get('windspeed', 0.0)
            
            # Get humidity from extended current data (if available)
            humidity = None
            if 'relative_humidity_2m' in current_units:
                humidity = current_units['relative_humidity_2m']
            
            # Map weather code to condition
            condition = self.WEATHER_CODES.get(weather_code, "Unknown")
            
            # Extract tomorrow's forecast (index 1 = tomorrow)
            forecast_text = None
            daily = data.get('daily', {})
            if daily:
                try:
                    temps_max = daily.get('temperature_2m_max', [])
                    temps_min = daily.get('temperature_2m_min', [])
                    codes = daily.get('weathercode', [])
                    if len(temps_max) > 1 and len(temps_min) > 1 and len(codes) > 1:
                        tomorrow_max = temps_max[1]
                        tomorrow_min = temps_min[1]
                        tomorrow_code = codes[1]
                        tomorrow_condition = self.WEATHER_CODES.get(tomorrow_code, "")
                        forecast_text = f"Tomorrow: {tomorrow_min:.0f}°-{tomorrow_max:.0f}°C {tomorrow_condition}"
                except Exception:
                    pass
            
            weather_data = {
                'location': city,
                'temperature': temperature,
                'condition': condition,
                'weather_code': weather_code,
                'windspeed': windspeed,
                'humidity': humidity,
                'forecast': forecast_text
            }
            
            logger.info(f"Weather fetched for {city}: {temperature}°C, {condition}")
            
            return weather_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather request failed for {city}: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse weather response for {city}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error fetching weather for {city}: {e}")
            return None
    
    def get_weather_by_coords(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Get current weather by coordinates.
        
        Args:
            latitude: Latitude
            longitude: Longitude
        
        Returns:
            Dictionary with weather data (same format as get_current_weather)
            or None if request fails
        """
        try:
            logger.debug(f"Fetching weather for coordinates ({latitude:.2f}, {longitude:.2f})")
            
            params = {
                'latitude': latitude,
                'longitude': longitude,
                'current_weather': 'true',
                'current': 'relative_humidity_2m',
                'timezone': 'auto'
            }
            
            response = requests.get(self.WEATHER_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract current weather
            current = data.get('current_weather', {})
            current_units = data.get('current', {})
            
            temperature = current.get('temperature')
            weather_code = current.get('weathercode', 0)
            windspeed = current.get('windspeed', 0.0)
            
            # Get humidity
            humidity = None
            if 'relative_humidity_2m' in current_units:
                humidity = current_units['relative_humidity_2m']
            
            # Map weather code to condition
            condition = self.WEATHER_CODES.get(weather_code, "Unknown")
            
            weather_data = {
                'location': f"{latitude:.2f}, {longitude:.2f}",
                'temperature': temperature,
                'condition': condition,
                'weather_code': weather_code,
                'windspeed': windspeed,
                'humidity': humidity
            }
            
            logger.info(f"Weather fetched for coords: {temperature}°C, {condition}")
            
            return weather_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather request failed for coordinates: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse weather response: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error fetching weather by coords: {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear geocoding cache."""
        self._cached_coords.clear()
        logger.debug("Geocoding cache cleared")
