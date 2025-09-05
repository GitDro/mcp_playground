"""
Canadian tide information tools using the Integrated Water Level System (IWLS) API
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from fastmcp import FastMCP
from ..core.mcp_output import create_text_result
from fastmcp.tools.tool import ToolResult

logger = logging.getLogger(__name__)


def register_tide_tools(mcp: FastMCP):
    """Register tide-related tools with the MCP server"""
    
    @mcp.tool(description="Get Canadian coastal tide times and heights")
    def get_tide_info(location: str, date: Optional[str] = None) -> ToolResult:
        """Get tide information (high/low times and heights) for Canadian coastal locations. Supports major ports like Halifax, Vancouver, St. Johns. Specify date as 'July 20 2024', 'tomorrow', or leave blank for today. Returns formatted table with times and heights.
        
        Args:
            location: Canadian coastal location (e.g., "Halifax", "Vancouver", "St. Johns")
            date: Optional date as 'July 20 2024', 'tomorrow', or leave blank for today
        """
        try:
            import requests
            from dateutil import parser as date_parser
            from dateutil.relativedelta import relativedelta
            
            # Parse and normalize the location
            location_normalized = location.strip().title()
            
            # Find the station ID for the location
            station_info = _find_station(location_normalized)
            if not station_info:
                return create_text_result(f"No tide station found for '{location}'. Try locations like Halifax, Vancouver, St. Johns, or other major Canadian coastal cities.")
            
            station_id = station_info['id']
            station_name = station_info['name']
            
            # Parse the date
            target_date = _parse_date(date)
            if not target_date:
                return create_text_result(f"Could not parse date '{date}'. Try formats like 'July 20 2024', '2024-07-20', 'tomorrow', or leave blank for today.")
            
            # Format date range for API (get the full day)
            start_date = target_date.strftime('%Y-%m-%dT00:00:00Z')
            end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z')
            
            # Get tide data from API
            api_url = f"https://api.iwls-sine.azure.cloud-nuage.dfo-mpo.gc.ca/api/v1/stations/{station_id}/data"
            params = {
                'time-series-code': 'wlp-hilo',
                'from': start_date,
                'to': end_date
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            if response.status_code != 200:
                return create_text_result(f"Could not retrieve tide data for {station_name}. API returned status {response.status_code}.")
            
            tide_data = response.json()
            if not tide_data:
                return create_text_result(f"No tide data available for {station_name} on {target_date.strftime('%B %d, %Y')}.")
            
            # Format the response
            formatted_result = _format_tide_data(station_name, target_date, tide_data)
            return create_text_result(formatted_result)
            
        except Exception as e:
            logger.error(f"Error getting tide info: {e}")
            return create_text_result(f"Error retrieving tide information: {str(e)}")


def _find_station(location: str) -> Optional[Dict]:
    """Find a tide station matching the given location"""
    try:
        import requests
        
        # Get all stations
        response = requests.get("https://api.iwls-sine.azure.cloud-nuage.dfo-mpo.gc.ca/api/v1/stations", timeout=10)
        if response.status_code != 200:
            return None
        
        stations = response.json()
        
        # Search for exact match first
        for station in stations:
            if station.get('officialName', '').lower() == location.lower():
                return {
                    'id': station['id'],
                    'name': station['officialName'],
                    'code': station['code']
                }
        
        # Search for partial match
        for station in stations:
            station_name = station.get('officialName', '').lower()
            if location.lower() in station_name or station_name.startswith(location.lower()):
                return {
                    'id': station['id'],
                    'name': station['officialName'],
                    'code': station['code']
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Error finding station: {e}")
        return None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse various date formats into a datetime object"""
    if not date_str:
        return datetime.now()
    
    date_str = date_str.strip().lower()
    
    # Handle relative dates
    if date_str == 'today':
        return datetime.now()
    elif date_str == 'tomorrow':
        return datetime.now() + timedelta(days=1)
    elif date_str == 'yesterday':
        return datetime.now() - timedelta(days=1)
    
    try:
        # Try to parse with dateutil (handles many formats)
        from dateutil import parser as date_parser
        parsed_date = date_parser.parse(date_str)
        return parsed_date
    except:
        # Try some common formats manually
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d %Y',
            '%B %d, %Y',
            '%b %d %Y',
            '%b %d, %Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        return None


def _format_tide_data(station_name: str, date: datetime, tide_data: List[Dict]) -> str:
    """Format tide data into a clean markdown table with height visualization"""
    try:
        # Sort tide data by time
        sorted_tides = sorted(tide_data, key=lambda x: x['eventDate'])
        
        # Build the header
        date_str = date.strftime('%B %d, %Y')
        result = f"**{station_name} Tides - {date_str}**\n\n"
        
        if not sorted_tides:
            return result + "No tide data available for this date."
        
        # Find min/max heights for visualization scaling
        heights = [float(tide['value']) for tide in sorted_tides]
        min_height = min(heights)
        max_height = max(heights)
        height_range = max_height - min_height
        
        # Build the table
        result += "| Time | Type | Height | Level |\n"
        result += "|------|------|--------|-------|\n"
        
        # Use UTC current time for comparison with tide times
        from datetime import timezone
        current_time = datetime.now(timezone.utc)
        next_tide = None
        
        for tide in sorted_tides:
            # Parse the event time
            event_time = datetime.fromisoformat(tide['eventDate'].replace('Z', '+00:00'))
            height = float(tide['value'])
            
            # Convert to local time (assuming user is in same timezone as station)
            local_time = event_time.strftime('%I:%M %p').lstrip('0')
            
            # Determine tide type based on height
            if height > (min_height + height_range * 0.7):
                tide_type = "High"
            elif height > (min_height + height_range * 0.3):
                tide_type = "Mid"
            else:
                tide_type = "Low"
            
            # Create clean height visualization with bars
            if height_range > 0:
                # Normalize height to 0-1 range
                normalized_height = (height - min_height) / height_range
                # Create a bar representation using block characters
                bar_length = int(normalized_height * 10)
                bar = "█" * bar_length + "░" * (10 - bar_length)
                height_viz = f"`{bar}`"
            else:
                height_viz = "`██████████`"
            
            # Add to table
            result += f"| {local_time} | {tide_type} | {height:.2f}m | {height_viz} |\n"
            
            # Track next tide
            if event_time > current_time and not next_tide:
                next_tide = {
                    'time': local_time,
                    'type': tide_type.lower(),
                    'datetime': event_time
                }
        
        # Add next tide information
        if next_tide:
            time_diff = next_tide['datetime'] - current_time
            hours = int(time_diff.total_seconds() // 3600)
            minutes = int((time_diff.total_seconds() % 3600) // 60)
            
            if hours > 0:
                time_until = f"{hours}h {minutes}m"
            else:
                time_until = f"{minutes}m"
            
            result += f"\n**Next tide:** {next_tide['type'].title()} at {next_tide['time']} (in {time_until})"
        
        return result
        
    except Exception as e:
        logger.error(f"Error formatting tide data: {e}")
        return f"Error formatting tide data: {str(e)}"