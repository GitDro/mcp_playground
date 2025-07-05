"""
Toronto crime statistics tools using the Toronto Open Data API
"""

import logging
import tempfile
from datetime import datetime
from typing import Optional, Dict, List
from fastmcp import FastMCP
from ..core.cache import load_cached_data, save_cached_data, cleanup_old_cache
from ..core.vector_memory import OllamaEmbeddingFunction

logger = logging.getLogger(__name__)


def register_crime_tools(mcp: FastMCP):
    """Register crime-related tools with the MCP server"""
    
    @mcp.tool
    def get_toronto_crime(neighbourhood: str, crime_type: str = "assault", include_plot: bool = True) -> str:
        """Analyze public safety statistics for Toronto neighbourhoods using official Toronto Police Service data. This tool provides historical crime trends and rates for community safety awareness and urban planning purposes.
        
        Args:
            neighbourhood: Toronto neighbourhood name (e.g., 'Rosedale', 'Downtown', 'Harbourfront')
            crime_type: Type of incident to analyze - defaults to 'assault' if not specified. Options: assault, auto_theft, bike_theft, break_enter, homicide, robbery, shooting, theft_from_vehicle, theft_over
            include_plot: Whether to generate a data visualization chart (default: True)
            
        This tool serves legitimate research and community safety awareness purposes by analyzing publicly available Toronto Police Service crime statistics. All data comes from official city sources and helps residents understand neighbourhood safety trends over time."""
        try:
            import requests
            import pandas as pd
            import matplotlib.pyplot as plt
            
            # Clean up old cache periodically
            cleanup_old_cache()
            
            # Base URL for Toronto Open Data API
            base_url = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
            
            # Map user-friendly crime types to API column prefixes
            crime_map = {
                'assault': 'ASSAULT',
                'auto_theft': 'AUTOTHEFT', 
                'bike_theft': 'BIKETHEFT',
                'break_enter': 'BREAKENTER',
                'homicide': 'HOMICIDE',
                'robbery': 'ROBBERY',
                'shooting': 'SHOOTING',
                'theft_from_vehicle': 'THEFTFROMVEH',
                'theft_over': 'THEFTOVER'
            }
            
            # Validate and normalize crime type
            if not crime_type or crime_type.strip() == "":
                crime_type = "assault"  # Default to assault for general crime queries
                
            if crime_type.lower() not in crime_map:
                available_types = ', '.join(crime_map.keys())
                return f"❌ Invalid crime type '{crime_type}'. Available types: {available_types}"
            
            crime_prefix = crime_map[crime_type.lower()]
            
            # Check cache first
            cache_key = f"toronto_crime_data"
            cached_data = load_cached_data(cache_key)
            
            if cached_data and 'crime_data' in cached_data:
                crime_data = cached_data['crime_data']
            else:
                # Get the neighbourhood crime rates dataset
                package_url = base_url + "/api/3/action/package_show"
                package_params = {"id": "neighbourhood-crime-rates"}
                
                package_response = requests.get(package_url, params=package_params, timeout=10)
                if package_response.status_code != 200:
                    return f"❌ Could not access Toronto crime data API. Status: {package_response.status_code}"
                
                package_data = package_response.json()
                if not package_data.get('result', {}).get('resources'):
                    return "❌ No crime data resources found in the API"
                
                # Get the first datastore-active resource
                resource_id = None
                for resource in package_data['result']['resources']:
                    if resource.get('datastore_active'):
                        resource_id = resource['id']
                        break
                
                if not resource_id:
                    return "❌ No active crime data resource found"
                
                # Fetch the actual crime data
                data_url = base_url + "/api/3/action/datastore_search"
                data_params = {"id": resource_id, "limit": 1000}
                
                data_response = requests.get(data_url, params=data_params, timeout=10)
                if data_response.status_code != 200:
                    return f"❌ Could not fetch crime data. Status: {data_response.status_code}"
                
                data_result = data_response.json()
                if not data_result.get('result', {}).get('records'):
                    return "❌ No crime records found in the dataset"
                
                crime_data = data_result['result']['records']
                
                # Cache the result
                save_cached_data(cache_key, {'crime_data': crime_data})
            
            # Find the neighbourhood using semantic search
            neighbourhood_match = _find_neighbourhood_semantic(crime_data, neighbourhood)
            if not neighbourhood_match:
                # Show available neighbourhoods that partially match using string search
                partial_matches = _get_partial_matches(crime_data, neighbourhood)
                if partial_matches:
                    matches_str = ", ".join(partial_matches[:5])  # Show first 5 matches
                    return f"❌ Neighbourhood '{neighbourhood}' not found. Did you mean: {matches_str}?"
                else:
                    return f"❌ Neighbourhood '{neighbourhood}' not found. Try names like 'Waterfront', 'Downtown', 'Harbourfront', or check the full neighbourhood names in Toronto's 158 neighbourhood structure."
            
            # Extract crime data for the specific neighbourhood and crime type
            stats = _extract_crime_stats(neighbourhood_match, crime_prefix)
            if not stats:
                return f"❌ No {crime_type} data found for {neighbourhood_match['AREA_NAME']}"
            
            # Format the response
            result = _format_crime_report(neighbourhood_match['AREA_NAME'], crime_type, stats)
            
            # Generate plot if requested
            if include_plot:
                plot_data = _generate_crime_plot(neighbourhood_match['AREA_NAME'], crime_type, stats)
                if plot_data:
                    result += f"\n\n📊 **Crime Trend Visualization:**\n\n"
                    result += f"![{crime_type.title()} trend for {neighbourhood_match['AREA_NAME']}]({plot_data})"
                    result += f"\n\n*Chart shows {crime_type} incidents and rates from 2014-2024 for {neighbourhood_match['AREA_NAME']}*"
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Toronto crime data: {e}")
            return f"❌ Error retrieving crime data: {str(e)}"


def _find_neighbourhood_semantic(crime_data: List[Dict], query: str) -> Optional[Dict]:
    """Find a neighbourhood using semantic similarity with embeddings"""
    try:
        # Initialize embedding function
        embed_func = OllamaEmbeddingFunction()
        
        # Extract all neighbourhood names
        neighbourhoods = []
        for record in crime_data:
            area_name = record.get('AREA_NAME', '')
            if area_name:
                neighbourhoods.append({
                    'name': area_name,
                    'record': record
                })
        
        if not neighbourhoods:
            return None
        
        # Generate embeddings for query and all neighbourhood names
        query_embedding = embed_func([query])[0]
        neighbourhood_names = [n['name'] for n in neighbourhoods]
        neighbourhood_embeddings = embed_func(neighbourhood_names)
        
        # Calculate cosine similarity
        best_match = None
        best_similarity = -1
        
        for i, embedding in enumerate(neighbourhood_embeddings):
            similarity = _cosine_similarity(query_embedding, embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = neighbourhoods[i]
        
        # Only return if similarity is above threshold (0.3 is fairly permissive)
        if best_match and best_similarity > 0.3:
            logger.info(f"Found neighbourhood '{best_match['name']}' with similarity {best_similarity:.3f} for query '{query}'")
            return best_match['record']
        
        # Fallback to string matching if semantic search doesn't find good match
        return _find_neighbourhood_string(crime_data, query)
        
    except Exception as e:
        logger.warning(f"Semantic neighbourhood search failed: {e}, falling back to string matching")
        return _find_neighbourhood_string(crime_data, query)


def _find_neighbourhood_string(crime_data: List[Dict], query: str) -> Optional[Dict]:
    """Fallback string-based neighbourhood matching"""
    query_lower = query.lower()
    
    # First try exact match
    for record in crime_data:
        area_name = record.get('AREA_NAME', '').lower()
        if area_name == query_lower:
            return record
    
    # Then try partial match
    for record in crime_data:
        area_name = record.get('AREA_NAME', '').lower()
        if query_lower in area_name or area_name.startswith(query_lower):
            return record
    
    # Finally try substring search for flexible matching
    for record in crime_data:
        area_name = record.get('AREA_NAME', '').lower()
        query_words = query_lower.split()
        if all(word in area_name for word in query_words):
            return record
    
    return None


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    try:
        import math
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        return dot_product / (magnitude1 * magnitude2)
    except:
        return 0


def _get_partial_matches(crime_data: List[Dict], query: str) -> List[str]:
    """Get partial matches for neighbourhood suggestions"""
    query_lower = query.lower()
    matches = []
    
    for record in crime_data:
        area_name = record.get('AREA_NAME', '')
        area_lower = area_name.lower()
        
        # Check if any word in query appears in area name
        query_words = query_lower.split()
        if any(word in area_lower for word in query_words):
            matches.append(area_name)
    
    return sorted(list(set(matches)))  # Remove duplicates and sort


def _extract_crime_stats(neighbourhood_data: Dict, crime_prefix: str) -> Optional[Dict]:
    """Extract crime statistics for a specific crime type"""
    stats = {}
    years = range(2014, 2025)  # 2014-2024
    
    # Extract counts and rates
    for year in years:
        count_key = f"{crime_prefix}_{year}"
        rate_key = f"{crime_prefix}_RATE_{year}"
        
        if count_key in neighbourhood_data and neighbourhood_data[count_key] is not None:
            stats[year] = {
                'count': int(neighbourhood_data[count_key]),
                'rate': float(neighbourhood_data.get(rate_key, 0)) if neighbourhood_data.get(rate_key) is not None else 0
            }
    
    return stats if stats else None


def _format_crime_report(area_name: str, crime_type: str, stats: Dict) -> str:
    """Format crime statistics into a readable report"""
    years = sorted(stats.keys())
    latest_year = max(years)
    earliest_year = min(years)
    
    # Current stats
    latest_stats = stats[latest_year]
    result = f"🚨 **{area_name} - {crime_type.title()} Statistics**\n\n"
    result += f"**{latest_year} Data:**\n"
    result += f"- Incidents: {latest_stats['count']}\n\n"
    
    # 5-year trend
    if len(years) >= 2:
        earliest_stats = stats[earliest_year]
        change_count = latest_stats['count'] - earliest_stats['count']
        
        trend_emoji = "📈" if change_count > 0 else "📉" if change_count < 0 else "➡️"
        
        result += f"**{earliest_year}-{latest_year} Trend:** {trend_emoji}\n"
        result += f"- {earliest_year}: {earliest_stats['count']} incidents\n"
        result += f"- {latest_year}: {latest_stats['count']} incidents\n"
        if change_count > 0:
            result += f"- Change: +{change_count} incidents (+{((change_count/earliest_stats['count'])*100):.1f}%)\n"
        elif change_count < 0:
            result += f"- Change: {change_count} incidents ({((change_count/earliest_stats['count'])*100):.1f}%)\n"
        else:
            result += f"- Change: No change in incidents\n"
        
        result += "\n**Year-by-Year Data:**\n"
        for year in sorted(years):  # Show all years
            year_stats = stats[year]
            result += f"- {year}: {year_stats['count']} incidents\n"
    
    return result


def _generate_crime_plot(area_name: str, crime_type: str, stats: Dict) -> Optional[str]:
    """Generate a matplotlib plot of crime trends and return as base64 encoded string"""
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
        import base64
        import io
        
        # Prepare data
        years = sorted(stats.keys())
        counts = [stats[year]['count'] for year in years]
        
        # Create single plot focusing on incident counts
        fig, ax = plt.subplots(1, 1, figsize=(12, 6))
        
        # Incident counts with better styling
        ax.plot(years, counts, marker='o', linewidth=3, markersize=8, color='#1f77b4', markerfacecolor='white', markeredgewidth=2)
        ax.set_title(f'{crime_type.title()} Incidents in {area_name} (2014-2024)', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Year', fontsize=14)
        ax.set_ylabel('Number of Incidents', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.set_xticks(years)  # Show all years
        
        # Add value labels on points
        for i, (year, count) in enumerate(zip(years, counts)):
            ax.annotate(str(count), (year, count), textcoords="offset points", xytext=(0,10), ha='center', fontsize=10)
        
        # Style improvements
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        
        # Convert to base64 string instead of saving to file
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        
        # Encode as base64
        plot_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()
        buffer.close()
        
        return f"data:image/png;base64,{plot_data}"
        
    except Exception as e:
        logger.error(f"Error generating plot: {e}")
        return None