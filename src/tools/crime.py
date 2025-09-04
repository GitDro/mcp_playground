"""
Toronto crime statistics tools using the Toronto Open Data API
"""

import logging
import tempfile
from datetime import datetime
from typing import Optional, Dict, List
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from ..core.unified_cache import get_cached_data, save_cached_data, cleanup_cache
from ..core.mcp_output import create_summary_and_chart_result, extract_chart_from_matplotlib, create_text_content

logger = logging.getLogger(__name__)


def register_crime_tools(mcp: FastMCP):
    """Register crime-related tools with the MCP server"""
    
    @mcp.tool(description="Get Toronto neighbourhood crime statistics and trends")
    def get_toronto_crime(neighbourhood: str, crime_type: str = "assault") -> ToolResult:
        """Analyze public safety statistics for Toronto neighbourhoods using official Toronto Police Service data. This tool provides historical crime trends with visualization for community safety awareness and urban planning purposes.
        
        Args:
            neighbourhood: Toronto neighbourhood name (e.g., 'Rosedale', 'Downtown', 'Harbourfront')
            crime_type: Type of incident to analyze (default: 'assault'). Options: assault, auto_theft, bike_theft, break_enter, homicide, robbery, shooting, theft_from_vehicle, theft_over
            
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
                return ToolResult(content=[create_text_content(f"❌ Invalid crime type '{crime_type}'. Available types: {available_types}")])
            
            crime_prefix = crime_map[crime_type.lower()]
            
            # Check cache first for full dataset
            cache_key = f"crime_data_toronto"
            cached_data = get_cached_data(cache_key, "crime_data")
            
            if cached_data and 'crime_data' in cached_data:
                crime_data = cached_data['crime_data']
            else:
                # Get the neighbourhood crime rates dataset
                package_url = base_url + "/api/3/action/package_show"
                package_params = {"id": "neighbourhood-crime-rates"}
                
                package_response = requests.get(package_url, params=package_params, timeout=10)
                if package_response.status_code != 200:
                    return ToolResult(content=[create_text_content(f"❌ Could not access Toronto crime data API. Status: {package_response.status_code}")])
                
                package_data = package_response.json()
                if not package_data.get('result', {}).get('resources'):
                    return ToolResult(content=[create_text_content("❌ No crime data resources found in the API")])
                
                # Get the first datastore-active resource
                resource_id = None
                for resource in package_data['result']['resources']:
                    if resource.get('datastore_active'):
                        resource_id = resource['id']
                        break
                
                if not resource_id:
                    return ToolResult(content=[create_text_content("❌ No active crime data resource found")])
                
                # Fetch the actual crime data
                data_url = base_url + "/api/3/action/datastore_search"
                data_params = {"id": resource_id, "limit": 1000}
                
                data_response = requests.get(data_url, params=data_params, timeout=10)
                if data_response.status_code != 200:
                    return ToolResult(content=[create_text_content(f"❌ Could not fetch crime data. Status: {data_response.status_code}")])
                
                data_result = data_response.json()
                if not data_result.get('result', {}).get('records'):
                    return ToolResult(content=[create_text_content("❌ No crime records found in the dataset")])
                
                crime_data = data_result['result']['records']
                
                # Cache the result
                save_cached_data(cache_key, {'crime_data': crime_data}, "crime_data", {'city': 'toronto'})
            
            # Check neighbourhood-specific cache first
            neighbourhood_cache_key = f"crime_neighbourhood_{neighbourhood.lower().replace(' ', '_')}"
            neighbourhood_cached = get_cached_data(neighbourhood_cache_key, "crime_neighbourhood")
            
            neighbourhood_match = None
            if neighbourhood_cached and 'neighbourhood_data' in neighbourhood_cached:
                neighbourhood_match = neighbourhood_cached['neighbourhood_data']
                logger.info(f"Using cached neighbourhood data for {neighbourhood}")
            else:
                # Find the neighbourhood using semantic search
                neighbourhood_match = _find_neighbourhood_string(crime_data, neighbourhood)
                if not neighbourhood_match:
                    # Show available neighbourhoods that partially match using string search
                    partial_matches = _get_partial_matches(crime_data, neighbourhood)
                    if partial_matches:
                        matches_str = ", ".join(partial_matches[:5])  # Show first 5 matches
                        return ToolResult(content=[create_text_content(f"❌ Neighbourhood '{neighbourhood}' not found. Did you mean: {matches_str}?")])
                    else:
                        return ToolResult(content=[create_text_content(f"❌ Neighbourhood '{neighbourhood}' not found. Use the 'list_toronto_neighbourhoods' tool to see all available neighbourhood names, or try names like 'Waterfront', 'Downtown', 'Harbourfront'.")])
                
                # Cache the neighbourhood data for future requests
                save_cached_data(neighbourhood_cache_key, {'neighbourhood_data': neighbourhood_match}, "crime_neighbourhood", {'neighbourhood': neighbourhood})
                logger.info(f"Cached neighbourhood data for {neighbourhood_match['AREA_NAME']}")
            
            # Extract crime data for the specific neighbourhood and crime type
            stats = _extract_crime_stats(neighbourhood_match, crime_prefix)
            if not stats:
                return ToolResult(content=[create_text_content(f"❌ No {crime_type} data found for {neighbourhood_match['AREA_NAME']}")])
            
            # Format the response using proper content blocks
            return _format_crime_report_with_content_blocks(neighbourhood_match['AREA_NAME'], crime_type, stats)
            
        except Exception as e:
            logger.error(f"Error getting Toronto crime data: {e}")
            return ToolResult(content=[create_text_content(f"❌ Error retrieving crime data: {str(e)}")])

    @mcp.tool(description="List all available Toronto neighbourhoods for crime data")
    def list_toronto_neighbourhoods() -> str:
        """Get a complete list of all Toronto neighbourhoods that have crime data available. Use this when you're unsure of the exact neighbourhood name to use with the crime statistics tool.
        
        Returns a formatted list of all 158 Toronto neighbourhoods organized alphabetically."""
        try:
            import requests
            
            # Clean up old cache periodically
            cleanup_old_cache()
            
            # Base URL for Toronto Open Data API
            base_url = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
            
            # Get the neighbourhood profiles dataset package info
            package_url = f"{base_url}/api/3/action/package_show?id=neighbourhood-crime-rates"
            package_response = requests.get(package_url, timeout=10)
            
            if package_response.status_code != 200:
                return f"❌ Could not access Toronto neighbourhood data API. Status: {package_response.status_code}"
            
            package_data = package_response.json()
            resources = package_data.get('result', {}).get('resources', [])
            
            if not resources:
                return "❌ No neighbourhood data resources found in the API"
            
            # Find the most recent CSV resource
            csv_resource = None
            for resource in resources:
                if resource.get('format', '').upper() == 'CSV':
                    csv_resource = resource
                    break
            
            if not csv_resource:
                return "❌ No active neighbourhood data resource found"
            
            # Get the data
            data_url = csv_resource['url']
            data_response = requests.get(data_url, timeout=30)
            
            if data_response.status_code != 200:
                return f"❌ Could not fetch neighbourhood data. Status: {data_response.status_code}"
            
            # Parse CSV data manually (lightweight approach)
            lines = data_response.text.strip().split('\n')
            if len(lines) <= 1:
                return "❌ No neighbourhood records found in the dataset"
            
            # Extract neighbourhood names from the data
            neighbourhoods = set()
            header = lines[0].split(',')
            area_name_idx = None
            
            for i, col in enumerate(header):
                if 'AREA_NAME' in col.upper():
                    area_name_idx = i
                    break
            
            if area_name_idx is None:
                return "❌ Could not find neighbourhood name column in the data"
            
            # Extract unique neighbourhood names
            for line in lines[1:]:
                parts = line.split(',')
                if len(parts) > area_name_idx:
                    area_name = parts[area_name_idx].strip().strip('"')
                    if area_name:
                        neighbourhoods.add(area_name)
            
            if not neighbourhoods:
                return "❌ No neighbourhood names found in the dataset"
            
            # Sort neighbourhoods alphabetically
            sorted_neighbourhoods = sorted(list(neighbourhoods))
            
            # Format the response
            result = f"📍 **Toronto Neighbourhoods ({len(sorted_neighbourhoods)} total)**\n\n"
            result += "Use any of these exact neighbourhood names with the crime statistics tool:\n\n"
            
            # Group by first letter for easier reading
            current_letter = ""
            for neighbourhood in sorted_neighbourhoods:
                first_letter = neighbourhood[0].upper()
                if first_letter != current_letter:
                    current_letter = first_letter
                    result += f"\n**{current_letter}**\n"
                result += f"• {neighbourhood}\n"
            
            result += f"\n💡 **Tip**: Use exact neighbourhood names for best results with the crime statistics tool."
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Toronto neighbourhoods: {e}")
            return f"❌ Error retrieving neighbourhood list: {str(e)}"



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


def _format_crime_report_with_content_blocks(area_name: str, crime_type: str, stats: Dict) -> ToolResult:
    """Format crime statistics using proper MCP content blocks"""
    years = sorted(stats.keys())
    latest_year = max(years)
    earliest_year = min(years)
    
    # Generate summary text
    latest_count = stats[latest_year]
    if len(years) > 1:
        earliest_count = stats[earliest_year] 
        trend = latest_count - earliest_count
        trend_text = "increasing" if trend > 0 else "decreasing" if trend < 0 else "stable"
        trend_emoji = "📈" if trend > 0 else "📉" if trend < 0 else "📊"
    else:
        trend_text = "data available"
        trend_emoji = "📊"
    
    # Build summary text
    summary = f"### **{area_name} - {crime_type.replace('_', ' ').title()} Statistics** {trend_emoji}\n\n"
    summary += f"- **Latest ({latest_year}):** {latest_count} incidents\n"
    
    if len(years) > 1:
        summary += f"- **{len(years)}-year trend:** {trend_text}\n"
        summary += f"- **Period:** {earliest_year}-{latest_year}\n\n"
        
        # Add yearly breakdown table
        summary += "| **Year** | **Incidents** | **Change** |\n"
        summary += "|----------|---------------|------------|\n"
        
        prev_count = None
        for year in years:
            count = stats[year]
            if prev_count is not None:
                change = count - prev_count
                change_str = f"+{change}" if change > 0 else str(change) if change < 0 else "0"
                change_emoji = "↗️" if change > 0 else "↘️" if change < 0 else "➡️"
                summary += f"| **{year}** | {count} | {change_str} {change_emoji} |\n"
            else:
                summary += f"| **{year}** | {count} | - |\n"
            prev_count = count
    
    # Generate chart
    chart_base64 = _generate_crime_plot_base64(area_name, crime_type, stats)
    
    # Create structured data for LLM processing
    structured_data = {
        "area_name": area_name,
        "crime_type": crime_type,
        "latest_year": latest_year,
        "latest_count": latest_count,
        "trend": trend_text if len(years) > 1 else "single_year",
        "year_range": f"{earliest_year}-{latest_year}",
        "yearly_data": stats
    }
    
    return create_summary_and_chart_result(
        summary_text=summary,
        chart_base64=chart_base64,
        structured_data=structured_data,
        chart_title=f"{crime_type.title()} Trends in {area_name}"
    )


def _generate_crime_plot_base64(area_name: str, crime_type: str, stats: Dict) -> Optional[str]:
    """Generate a crime plot and return base64 data"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        
        # Set seaborn style for clean, professional look
        sns.set_style("whitegrid")
        sns.set_palette("Set2")
        
        # Prepare data
        years = sorted(stats.keys())
        counts = [stats[year] for year in years]
        
        # Create DataFrame
        df = pd.DataFrame({'Year': years, 'Incidents': counts})
        
        # Create plot with optimal sizing
        plt.figure(figsize=(10, 6))
        
        # Main plot - line with markers
        ax = sns.lineplot(data=df, x='Year', y='Incidents', marker='o', 
                         linewidth=3, markersize=10)
        
        # Styling
        plt.title(f'{crime_type.replace("_", " ").title()} Incidents in {area_name}', 
                 fontsize=16, fontweight='bold', pad=20)
        plt.xlabel('Year', fontsize=14, fontweight='600')
        plt.ylabel('Number of Incidents', fontsize=14, fontweight='600')
        plt.xticks(fontsize=12)
        plt.yticks(fontsize=12)
        
        # Add value labels on points
        for i, (year, count) in enumerate(zip(years, counts)):
            plt.annotate(f'{count}', (year, count), 
                        textcoords="offset points", xytext=(0, 15), ha='center',
                        fontsize=11, fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
        
        # Grid styling for better readability
        plt.grid(True, alpha=0.3, linewidth=1)
        
        # Remove top and right spines for cleaner look
        sns.despine()
        
        # Tight layout with padding
        plt.tight_layout(pad=2.0)
        
        # Extract base64 data
        chart_base64 = extract_chart_from_matplotlib()
        sns.reset_defaults()
        
        return chart_base64
        
    except Exception as e:
        logger.error(f"Error generating crime plot: {e}")
        return None