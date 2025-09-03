"""
Weather and location tools
"""

import logging
from typing import Optional, Dict
from datetime import datetime

from fastmcp import FastMCP
from ..core.utils import get_weather_emoji
from ..core.unified_cache import get_cached_data, save_cached_data

logger = logging.getLogger(__name__)


def register_weather_tools(mcp: FastMCP):
    """Register weather-related tools with the MCP server"""
    
    def _get_ip_location() -> Optional[Dict]:
        """Get location data from user's IP using ipapi.is"""
        try:
            import requests
            
            # Use ipapi.is free API (1000 requests/day, no auth)
            response = requests.get("https://api.ipapi.is", timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Extract latitude and longitude
                if data.get('location') and data['location'].get('latitude') and data['location'].get('longitude'):
                    return {
                        'latitude': data['location']['latitude'],
                        'longitude': data['location']['longitude'],
                        'city': data.get('location', {}).get('city', 'Unknown'),
                        'country': data.get('location', {}).get('country', 'Unknown'),
                        'country_code': data.get('location', {}).get('country_code', 'XX')
                    }
            return None
        except Exception as e:
            logger.warning(f"Failed to get IP location: {e}")
            return None
    
    def _geocode_city(city_name: str) -> Optional[Dict]:
        """Convert city name to coordinates using Open-Meteo Geocoding API"""
        try:
            import requests
            
            # Use Open-Meteo Geocoding API (free, no auth)
            url = "https://geocoding-api.open-meteo.com/v1/search"
            params = {
                'name': city_name.strip(),
                'count': 10,  # Get multiple results to find best match
                'language': 'en'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    return None
                
                # Preference logic: Canada first, then other countries
                # Also prefer exact name matches
                best_result = None
                canada_result = None
                exact_match = None
                
                search_lower = city_name.lower()
                
                for result in results:
                    result_name = result.get('name', '').lower()
                    country_code = result.get('country_code', '')
                    
                    # Check for exact name match
                    if result_name == search_lower and not exact_match:
                        exact_match = result
                    
                    # Check for Canada match
                    if country_code == 'CA' and not canada_result:
                        canada_result = result
                    
                    # Take first result as fallback
                    if not best_result:
                        best_result = result
                
                # Priority: Exact match in Canada > Any Canada result > Exact match anywhere > First result
                chosen_result = None
                if exact_match and exact_match.get('country_code') == 'CA':
                    chosen_result = exact_match
                elif canada_result:
                    chosen_result = canada_result
                elif exact_match:
                    chosen_result = exact_match
                else:
                    chosen_result = best_result
                
                if chosen_result:
                    return {
                        'latitude': chosen_result.get('latitude'),
                        'longitude': chosen_result.get('longitude'),
                        'city': chosen_result.get('name', city_name),
                        'country': chosen_result.get('country', 'Unknown'),
                        'country_code': chosen_result.get('country_code', 'XX'),
                        'admin1': chosen_result.get('admin1', ''),  # State/Province
                    }
            return None
        except Exception as e:
            logger.warning(f"Failed to geocode city '{city_name}': {e}")
            return None
    
    def _get_weather_data(latitude: float, longitude: float) -> Optional[Dict]:
        """Get weather data from Open-Meteo API with caching"""
        try:
            import requests
            
            # Check cache first (cache for 30 minutes)
            cache_key = f"weather_{latitude:.2f}_{longitude:.2f}"
            cached_data = get_cached_data(cache_key, "weather_data")
            if cached_data:
                # Check if data is less than 30 minutes old
                from datetime import timedelta
                if datetime.now() - datetime.fromisoformat(cached_data['timestamp']) < timedelta(minutes=30):
                    return cached_data['weather_data']
            
            # Open-Meteo API - free, no auth, 10k requests/day
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': latitude,
                'longitude': longitude,
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
                'timezone': 'auto',
                'forecast_days': 7
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                weather_data = response.json()
                
                # Cache the weather data
                cache_data = {
                    'weather_data': weather_data,
                    'timestamp': datetime.now().isoformat(),
                    'latitude': latitude,
                    'longitude': longitude
                }
                save_cached_data(cache_key, cache_data, "weather_data", {'lat': latitude, 'lng': longitude})
                
                return weather_data
            return None
        except Exception as e:
            logger.warning(f"Failed to get weather data: {e}")
            return None
    
    def _format_weather_response(weather_data: Dict, location_data: Dict) -> str:
        """Format weather data into a nice markdown response with emojis"""
        try:
            current = weather_data.get('current', {})
            daily = weather_data.get('daily', {})
            
            # Location info with province/state if available
            city = location_data.get('city', 'Unknown')
            country = location_data.get('country', 'Unknown')
            admin1 = location_data.get('admin1', '')
            
            # Build location string
            location_str = city
            if admin1 and admin1 != city:
                location_str += f", {admin1}"
            location_str += f", {country}"
            
            # Current weather
            temp = current.get('temperature_2m', 0)
            feels_like = current.get('apparent_temperature', temp)
            humidity = current.get('relative_humidity_2m', 0)
            wind_speed = current.get('wind_speed_10m', 0)
            wind_dir = current.get('wind_direction_10m', 0)
            weather_code = current.get('weather_code', 0)
            
            # Get weather emoji
            weather_emoji = get_weather_emoji(weather_code)
            
            # Wind direction
            wind_directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                              'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
            wind_dir_text = wind_directions[int((wind_dir + 11.25) / 22.5) % 16]
            
            # Start building response
            response = f"## {weather_emoji} Weather for {location_str}\n\n"
            
            # Current conditions
            response += "### Current Conditions\n"
            response += f"- 🌡️ **{temp:.1f}°C** (feels like {feels_like:.1f}°C)\n"
            response += f"- {weather_emoji} **Current weather**\n"
            response += f"- 💧 **Humidity:** {humidity}%\n"
            response += f"- 💨 **Wind:** {wind_speed:.1f} km/h {wind_dir_text}\n\n"
            
            # 7-day forecast
            if daily.get('time') and daily.get('temperature_2m_max'):
                response += "### 7-Day Forecast\n\n"
                response += "| Day | Weather | High | Low | Rain |\n"
                response += "|-----|---------|------|-----|------|\n"
                
                times = daily['time']
                max_temps = daily['temperature_2m_max']
                min_temps = daily['temperature_2m_min']
                weather_codes = daily.get('weather_code', [])
                precipitation = daily.get('precipitation_probability_max', [])
                
                for i in range(min(7, len(times))):
                    try:
                        date = datetime.fromisoformat(times[i])
                        day_name = date.strftime('%a')
                        
                        day_emoji = get_weather_emoji(weather_codes[i] if i < len(weather_codes) else 0)
                        high_temp = max_temps[i] if i < len(max_temps) else 0
                        low_temp = min_temps[i] if i < len(min_temps) else 0
                        rain_prob = precipitation[i] if i < len(precipitation) else 0
                        
                        response += f"| {day_name} | {day_emoji} | {high_temp:.0f}°C | {low_temp:.0f}°C | {rain_prob:.0f}% |\n"
                    except (ValueError, IndexError):
                        continue
            
            response += "\n"
            return response
            
        except Exception as e:
            logger.error(f"Error formatting weather response: {e}")
            return f"Error formatting weather data: {str(e)}"
    
    @mcp.tool(description="Get current weather and 7-day forecast for any location or your current location")
    def get_weather(location: Optional[str] = None) -> str:
        """Get current weather conditions and 7-day forecast.
        
        Args:
            location (str, optional): Three ways to specify location:
                • Leave empty for automatic detection using your IP address
                • City name (e.g., 'Toronto', 'Vancouver') - Canadian cities prioritized
                • Coordinates as 'latitude,longitude' (e.g., '43.6532,-79.3832')
        
        Returns:
            str: Formatted weather report with current conditions and 7-day forecast.
        """
        try:
            if location:
                location = location.strip()
                # Check if it looks like coordinates (lat,lng)
                if ',' in location and len(location.split(',')) == 2:
                    try:
                        lat_str, lng_str = location.split(',', 1)
                        latitude = float(lat_str.strip())
                        longitude = float(lng_str.strip())
                        location_data = {
                            'latitude': latitude,
                            'longitude': longitude,
                            'city': f"Location {latitude:.2f}",
                            'country': f"{longitude:.2f}",
                            'country_code': 'XX'
                        }
                    except ValueError:
                        return "Invalid coordinates. Use format 'latitude,longitude' (e.g., '43.65,-79.38')."
                else:
                    # Treat as city name
                    location_data = _geocode_city(location)
                    if not location_data:
                        return f"Location '{location}' not found. Try a different city name or coordinates (e.g., '43.65,-79.38')."
            else:
                # Get location from IP
                location_data = _get_ip_location()
                if not location_data:
                    return "Could not detect your location automatically. Please provide a city name or coordinates (e.g., '43.65,-79.38')."
            
            # Get weather data
            weather_data = _get_weather_data(location_data['latitude'], location_data['longitude'])
            if not weather_data:
                return "Could not fetch weather data. Please try again later."
            
            # Format and return response
            return _format_weather_response(weather_data, location_data)
            
        except Exception as e:
            return f"Error getting weather: {str(e)}"