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
    
    @mcp.tool(description="crime statistics")
    def get_toronto_crime(neighbourhood: str, crime_type: str = "assault") -> str:
        """Analyze public safety statistics for Toronto neighbourhoods using official Toronto Police Service data. This tool provides historical crime trends with visualization for community safety awareness and urban planning purposes.
        
        Args:
            neighbourhood: Toronto neighbourhood name (e.g., 'Rosedale', 'Downtown', 'Harbourfront')
            crime_type: Type of incident to analyze - defaults to 'assault' if not specified. Options: assault, auto_theft, bike_theft, break_enter, homicide, robbery, shooting, theft_from_vehicle, theft_over
            
        This tool serves legitimate research and community safety awareness purposes by analyzing publicly available Toronto Police Service crime statistics. All data comes from official city sources and includes both summary statistics and detailed trend visualization."""
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
            
            # Check cache first for full dataset
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
            
            # Check neighbourhood-specific cache first
            neighbourhood_cache_key = f"toronto_neighbourhood_{neighbourhood.lower().replace(' ', '_')}"
            neighbourhood_cached = load_cached_data(neighbourhood_cache_key)
            
            neighbourhood_match = None
            if neighbourhood_cached and 'neighbourhood_data' in neighbourhood_cached:
                neighbourhood_match = neighbourhood_cached['neighbourhood_data']
                logger.info(f"Using cached neighbourhood data for {neighbourhood}")
            else:
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
                
                # Cache the neighbourhood data for future requests
                save_cached_data(neighbourhood_cache_key, {'neighbourhood_data': neighbourhood_match})
                logger.info(f"Cached neighbourhood data for {neighbourhood_match['AREA_NAME']}")
            
            # Extract crime data for the specific neighbourhood and crime type
            stats = _extract_crime_stats(neighbourhood_match, crime_prefix)
            if not stats:
                return f"❌ No {crime_type} data found for {neighbourhood_match['AREA_NAME']}"
            
            # Format the response
            result = _format_crime_report(neighbourhood_match['AREA_NAME'], crime_type, stats)
            
            # Always include trend chart (separate from table)
            plot_data = _generate_crime_plot(neighbourhood_match['AREA_NAME'], crime_type, stats)
            if plot_data:
                result += f"\n\n![{crime_type.title()} trend for {neighbourhood_match['AREA_NAME']}]({plot_data})"
            
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
    """Format crime statistics into a concise, readable markdown summary"""
    years = sorted(stats.keys())
    latest_year = max(years)
    earliest_year = min(years)

    # Find peak year
    peak_year = max(years, key=lambda y: stats[y]['count'])
    peak_count = stats[peak_year]['count']

    # Current stats and trend analysis
    latest_stats = stats[latest_year]
    earliest_stats = stats[earliest_year]
    change_count = latest_stats['count'] - earliest_stats['count']
    trend_emoji = "📈" if change_count > 0 else "📉" if change_count < 0 else "➡️"
    percent_change = ((change_count/earliest_stats['count'])*100) if earliest_stats['count'] else 0

    # Markdown summary table only
    result = f"### **{area_name} – {crime_type.title()} Summary**\n\n"
    result += "| **Metric**     | **Value**                     |\n"
    result += "|---------------|---------------------------------|\n"
    result += f"| **Current year**   | **{latest_year}**: {latest_stats['count']} incidents |\n"
    result += f"| **Peak year**      | **{peak_year}**: {peak_count} incidents |\n"
    if change_count > 0:
        trend = f"{trend_emoji} **+{change_count} incidents** (+{percent_change:.0f}%) since {earliest_year}"
    elif change_count < 0:
        trend = f"{trend_emoji} **{change_count} incidents** ({percent_change:.0f}%) since {earliest_year}"
    else:
        trend = f"{trend_emoji} **No change** since {earliest_year}"
    result += f"| **10-year trend**  | {trend} |\n"
    return result


def _generate_crime_plot(area_name: str, crime_type: str, stats: Dict) -> Optional[str]:
    """Generate a seaborn plot of crime trends optimized for small windows"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        import base64
        import io
        
        # Set seaborn style for clean, professional look
        sns.set_style("whitegrid")
        sns.set_palette("husl")
        
        # Prepare data as DataFrame for seaborn
        years = sorted(stats.keys())
        counts = [stats[year]['count'] for year in years]
        df = pd.DataFrame({'Year': years, 'Incidents': counts})
        
        # Create figure with optimal size for small windows
        plt.figure(figsize=(10, 6))
        
        # Create line plot with seaborn
        ax = sns.lineplot(data=df, x='Year', y='Incidents', 
                         marker='o', linewidth=3, markersize=10)
        
        # Enhance for small window visibility
        plt.title(f'{crime_type.title()} Incidents in {area_name}', 
                 fontsize=18, fontweight='bold', pad=25)
        plt.xlabel('Year', fontsize=16, fontweight='600')
        plt.ylabel('Incidents', fontsize=16, fontweight='600')
        
        # Larger tick labels for better visibility
        plt.xticks(fontsize=14, rotation=45)
        plt.yticks(fontsize=14)
        
        # Add value labels on points with larger font
        for i, (year, count) in enumerate(zip(years, counts)):
            plt.annotate(str(count), (year, count), 
                        textcoords="offset points", xytext=(0,12), 
                        ha='center', fontsize=12, fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
        
        # Grid styling for better readability
        plt.grid(True, alpha=0.3, linewidth=1)
        
        # Remove top and right spines for cleaner look
        sns.despine()
        
        # Tight layout with padding
        plt.tight_layout(pad=2.0)
        
        # Convert to base64 string
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        buffer.seek(0)
        
        # Encode as base64
        plot_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()
        buffer.close()
        
        # Reset seaborn style to avoid affecting other plots
        sns.reset_defaults()
        
        return f"data:image/png;base64,{plot_data}"
        
    except Exception as e:
        logger.error(f"Error generating plot: {e}")
        return None