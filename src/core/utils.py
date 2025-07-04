"""
General utility functions for MCP tools
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def clean_markdown_text(text: str) -> str:
    """Clean text to prevent overly long sections and problematic headers"""
    if not text:
        return text
    
    # Remove any header markers that could interfere with layout
    text = text.replace('####', '').replace('###', '').replace('##', '').replace('#', '')
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Limit length to prevent overly long sections
    if len(text) > 500:
        text = text[:497] + "..."
    
    return text


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats and clean parameters"""
    import re
    
    # Clean up common URL issues (remove extra spaces, fix protocols)
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        if url.startswith('www.') or url.startswith('youtube.') or url.startswith('youtu.be'):
            url = 'https://' + url
    
    # YouTube URL patterns - comprehensive to handle all parameters including playlists
    patterns = [
        # Standard watch URLs with any parameters (timestamps, playlists, etc.)
        r'youtube\.com/watch\?.*[?&]?v=([a-zA-Z0-9_-]{11})',
        # Playlist URLs - extract video ID while ignoring list/index parameters
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11}).*(?:&list=|&index=)',
        # Short URLs
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        # Embed URLs
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        # Mobile URLs
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        # Share URLs with parameters
        r'youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def filter_sponsor_content(transcript_text: str) -> str:
    """Remove sponsor segments and promotional content from transcript"""
    import re
    
    # Common patterns for sponsor/ad content
    sponsor_patterns = [
        # Sponsor mentions
        r'this video is sponsored by[^.]*\.',
        r'our sponsor[^.]*\.',
        r'today\'?s sponsor[^.]*\.',
        r'brought to you by[^.]*\.',
        r'special thanks to[^.]*\.',
        r'thanks to.*?for sponsoring[^.]*\.',
        
        # Common sponsor transitions
        r'but first[^.]*sponsor[^.]*\.',
        r'before we get started[^.]*sponsor[^.]*\.',
        r'speaking of[^.]*\.',
        
        # Skillshare/common sponsors
        r'skillshare[^.]*\.',
        r'nordvpn[^.]*\.',
        r'squarespace[^.]*\.',
        r'brilliant[^.]*\.',
        r'audible[^.]*\.',
        r'honey[^.]*\.',
        r'raid shadow legends[^.]*\.',
        
        # Subscribe/like requests (often clustered with ads)
        r'don\'?t forget to like and subscribe[^.]*\.',
        r'if you enjoyed this video[^.]*subscribe[^.]*\.',
        r'smash that like button[^.]*\.',
        
        # Merchandise/channel promotion
        r'check out my merch[^.]*\.',
        r'link in the description[^.]*\.',
        r'patreon[^.]*\.',
    ]
    
    # Apply filters (case insensitive)
    filtered_text = transcript_text
    for pattern in sponsor_patterns:
        filtered_text = re.sub(pattern, '', filtered_text, flags=re.IGNORECASE)
    
    # Remove multiple spaces and clean up
    filtered_text = re.sub(r'\s+', ' ', filtered_text)
    filtered_text = filtered_text.strip()
    
    return filtered_text


def get_weather_emoji(weather_code: int) -> str:
    """Map Open-Meteo weather codes to emojis"""
    # Open-Meteo WMO Weather interpretation codes
    weather_emojis = {
        0: "☀️",   # Clear sky
        1: "🌤️",   # Mainly clear
        2: "⛅",   # Partly cloudy
        3: "☁️",   # Overcast
        45: "🌫️",  # Fog
        48: "🌫️",  # Depositing rime fog
        51: "🌦️",  # Light drizzle
        53: "🌦️",  # Moderate drizzle
        55: "🌧️",  # Dense drizzle
        56: "🌨️",  # Light freezing drizzle
        57: "🌨️",  # Dense freezing drizzle
        61: "🌧️",  # Slight rain
        63: "🌧️",  # Moderate rain
        65: "🌧️",  # Heavy rain
        66: "🌨️",  # Light freezing rain
        67: "🌨️",  # Heavy freezing rain
        71: "❄️",  # Slight snow fall
        73: "❄️",  # Moderate snow fall
        75: "❄️",  # Heavy snow fall
        77: "❄️",  # Snow grains
        80: "🌦️",  # Slight rain showers
        81: "🌧️",  # Moderate rain showers
        82: "🌧️",  # Violent rain showers
        85: "🌨️",  # Slight snow showers
        86: "❄️",  # Heavy snow showers
        95: "⛈️",  # Thunderstorm
        96: "⛈️",  # Thunderstorm with slight hail
        99: "⛈️",  # Thunderstorm with heavy hail
    }
    return weather_emojis.get(weather_code, "🌤️")