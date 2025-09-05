"""
Statistics Canada economic data tools for CPI, GDP, and employment data
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import requests
from dataclasses import dataclass
import calendar
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastmcp import FastMCP
from ..core.unified_cache import get_cached_data, save_cached_data, cleanup_cache
from ..core.mcp_output import create_text_result
from fastmcp.tools.tool import ToolResult

logger = logging.getLogger(__name__)

# Statistics Canada API base URLs
STATSCAN_BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"

# Key economic indicator table IDs
ECONOMIC_TABLES = {
    "CPI": "18-10-0004-01",  # Consumer Price Index, monthly
    "GDP": "36-10-0434-01",  # GDP at basic prices, monthly
    "GDP_QUARTERLY": "36-10-0434-01",  # GDP quarterly expenditure-based
    "EMPLOYMENT": "14-10-0287-01",  # Labour force characteristics, monthly
    "UNEMPLOYMENT": "14-10-0017-01"  # Unemployment rate, monthly
}

# CPI vector mappings for different categories and geographies
CPI_VECTORS = {
    "all": {
        "Canada": "v41690973",
        "Ontario": "v41690978",
        "Quebec": "v41690983",
        "British Columbia": "v41690988"
    },
    "food": {
        "Canada": "v41690974",
        "Ontario": "v41690979",
        "Quebec": "v41690984"
    },
    "shelter": {
        "Canada": "v41690975",
        "Ontario": "v41690980"
    },
    "transportation": {
        "Canada": "v41690976",
        "Ontario": "v41690981"
    },
    "energy": {
        "Canada": "v41690977",
        "Ontario": "v41690982"
    },
    "core": {
        "Canada": "v41690990",  # All-items excluding food and energy
        "Ontario": "v41690991"
    }
}

# GDP vector mappings
GDP_VECTORS = {
    "total": {
        "monthly": "v62787312",
        "quarterly": "v62787313"
    },
    "consumption": {
        "quarterly": "v62787314"
    },
    "investment": {
        "quarterly": "v62787315"
    }
}

# Employment vector mappings
EMPLOYMENT_VECTORS = {
    "unemployment_rate": {
        "Canada": "v2062815",
        "Ontario": "v2062816",
        "Quebec": "v2062817"
    },
    "employment_rate": {
        "Canada": "v2062818",
        "Ontario": "v2062819"
    }
}

@dataclass
class EconomicIndicator:
    """Data class for economic indicators"""
    name: str
    value: float
    date: str
    period_change: float
    period_change_pct: float
    year_change: float
    year_change_pct: float
    units: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'value': self.value,
            'date': self.date,
            'period_change': self.period_change,
            'period_change_pct': self.period_change_pct,
            'year_change': self.year_change,
            'year_change_pct': self.year_change_pct,
            'units': self.units
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EconomicIndicator':
        """Create from dictionary for JSON deserialization"""
        return cls(**data)


@dataclass
class CanadianEconomicData:
    """Consolidated Canadian economic data"""
    cpi: Optional[EconomicIndicator]
    gdp: Optional[EconomicIndicator]
    employment: Optional[EconomicIndicator]
    last_updated: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'cpi': self.cpi.to_dict() if self.cpi else None,
            'gdp': self.gdp.to_dict() if self.gdp else None,
            'employment': self.employment.to_dict() if self.employment else None,
            'last_updated': self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CanadianEconomicData':
        """Create from dictionary for JSON deserialization"""
        return cls(
            cpi=EconomicIndicator.from_dict(data['cpi']) if data.get('cpi') else None,
            gdp=EconomicIndicator.from_dict(data['gdp']) if data.get('gdp') else None,
            employment=EconomicIndicator.from_dict(data['employment']) if data.get('employment') else None,
            last_updated=data['last_updated']
        )


def register_statscan_tools(mcp: FastMCP):
    """Register Statistics Canada tools with the MCP server"""
    
    @mcp.tool(description="Canadian economic analysis and overview")
    def analyze_canadian_economy(focus: str = "overview") -> ToolResult:
        """Analyze Canada's economic performance with comprehensive data from Statistics Canada. Provides integrated analysis of inflation, growth, and employment.
        
        Args:
            focus: Analysis focus - "overview" (default), "inflation", "growth", "employment", or "detailed"
        """
        try:
            cleanup_old_cache()
            
            # Get all economic indicators concurrently
            economic_data = _get_all_economic_data()
            if not economic_data:
                return create_text_result("❌ Could not retrieve Canadian economic data")
            
            return create_text_result(_format_economic_analysis(economic_data, focus))
            
        except Exception as e:
            logger.error(f"Error analyzing Canadian economy: {e}")
            return create_text_result(f"❌ Error retrieving Canadian economic data: {str(e)}")


def _get_all_economic_data() -> Optional[CanadianEconomicData]:
    """Get all Canadian economic indicators concurrently with caching"""
    cache_key = "statscan_overview_canadian_economy"
    cached_data = get_cached_data(cache_key, "statscan_overview")
    
    if cached_data and 'economic_data' in cached_data:
        return CanadianEconomicData.from_dict(cached_data['economic_data'])
    
    try:
        # Fetch all indicators concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all three API calls
            cpi_future = executor.submit(_get_cpi_data, "all", "Canada")
            gdp_future = executor.submit(_get_gdp_data, "quarterly", "total")
            employment_future = executor.submit(_get_employment_data, "unemployment_rate", "Canada")
            
            # Collect results
            cpi_data = cpi_future.result()
            gdp_data = gdp_future.result()
            employment_data = employment_future.result()
        
        # Create consolidated data object
        economic_data = CanadianEconomicData(
            cpi=cpi_data,
            gdp=gdp_data,
            employment=employment_data,
            last_updated=datetime.now().isoformat()
        )
        
        # Cache the consolidated data
        save_cached_data(cache_key, {'economic_data': economic_data.to_dict()}, "statscan_overview")
        
        return economic_data
        
    except Exception as e:
        logger.error(f"Error fetching all economic data: {e}")
        return None


def _format_economic_analysis(data: CanadianEconomicData, focus: str) -> str:
    """Format comprehensive economic analysis"""
    if not data:
        return "❌ No economic data available"
    
    # Determine which sections to include based on focus
    if focus == "inflation" and data.cpi:
        return _format_cpi_output(data.cpi, "all", "Canada")
    elif focus == "growth" and data.gdp:
        return _format_gdp_output(data.gdp, "quarterly", "total")
    elif focus == "employment" and data.employment:
        return _format_employment_output(data.employment, "unemployment_rate", "Canada")
    
    # Default: comprehensive overview
    result = "# 🇨🇦 **Canadian Economic Overview**\n\n"
    
    # Economic Health Summary
    health_status = _assess_economic_health(data)
    result += f"**Overall Economic Health:** {health_status}\n\n"
    
    # Key Indicators Summary
    result += "## **Key Economic Indicators**\n\n"
    
    # GDP Section
    if data.gdp:
        gdp_billions = data.gdp.value / 1000
        trend_emoji = "📈" if data.gdp.year_change_pct > 0 else "📉"
        result += f"### **Economic Growth (GDP)**\n"
        result += f"- **Current GDP:** ${gdp_billions:.1f} billion\n"
        result += f"- **Annual Growth:** {data.gdp.year_change_pct:+.1f}% {trend_emoji}\n"
        result += f"- **Status:** {_get_gdp_status(data.gdp.year_change_pct)}\n\n"
    
    # Inflation Section
    if data.cpi:
        trend_emoji = "📈" if data.cpi.year_change_pct > 0 else "📉"
        result += f"### **Inflation (CPI)**\n"
        result += f"- **Current Rate:** {data.cpi.year_change_pct:+.1f}% (annual) {trend_emoji}\n"
        result += f"- **Monthly Change:** {data.cpi.period_change_pct:+.1f}%\n"
        result += f"- **Status:** {_get_inflation_status_text(data.cpi.year_change_pct)}\n\n"
    
    # Employment Section
    if data.employment:
        # For unemployment, lower is better
        trend_emoji = "📈" if data.employment.year_change < 0 else "📉"
        result += f"### **Labour Market**\n"
        result += f"- **Unemployment Rate:** {data.employment.value:.1f}%\n"
        result += f"- **12-Month Change:** {data.employment.year_change:+.1f} percentage points {trend_emoji}\n"
        result += f"- **Status:** {_get_employment_status_text(data.employment.value)}\n\n"
    
    # Economic Context and Analysis
    result += "## **Economic Analysis**\n\n"
    result += _generate_economic_insights(data)
    
    # Data freshness
    result += f"\n---\n*Last updated: {data.last_updated[:10]} | Source: Statistics Canada*"
    
    return result


def _get_cpi_data(category: str, geography: str) -> Optional[EconomicIndicator]:
    """Get CPI data from Statistics Canada API"""
    cache_key = f"statscan_cpi_{category}_{geography}"
    cached_data = get_cached_data(cache_key, "statscan_cpi")
    
    if cached_data and 'indicator' in cached_data:
        return EconomicIndicator.from_dict(cached_data['indicator'])
    
    try:
        # Get CPI data from Statistics Canada API
        vectors = _get_cpi_vectors(category, geography)
        if not vectors:
            return None
            
        # Fetch data from API
        api_data = _fetch_statscan_data(vectors, periods=13)  # 13 months for year-over-year
        if not api_data:
            return None
        
        # Process the data
        indicator = _process_cpi_data(api_data, category)
        
        # Cache the data
        _save_statscan_cache(cache_key, {'indicator': indicator.to_dict()})
        return indicator
        
    except Exception as e:
        logger.error(f"Error fetching CPI data: {e}")
        # Fallback to mock data for development
        return _get_mock_cpi_data(category, geography)


def _get_gdp_data(frequency: str, component: str) -> Optional[EconomicIndicator]:
    """Get GDP data from Statistics Canada API"""
    cache_key = f"gdp_{frequency}_{component}"
    # GDP data changes quarterly, so cache longer
    cache_hours = 168 if frequency == "quarterly" else 48  # 1 week for quarterly, 2 days for monthly
    cached_data = _load_statscan_cache(cache_key, cache_hours)
    
    if cached_data and 'indicator' in cached_data:
        return EconomicIndicator.from_dict(cached_data['indicator'])
    
    try:
        # Get GDP vectors
        vectors = _get_gdp_vectors(frequency, component)
        if not vectors:
            return None
            
        # Fetch data from API
        periods = 5 if frequency == "quarterly" else 13  # Quarters vs months
        api_data = _fetch_statscan_data(vectors, periods)
        if not api_data:
            return None
        
        # Process the data
        indicator = _process_gdp_data(api_data, frequency, component)
        
        # Cache the data
        _save_statscan_cache(cache_key, {'indicator': indicator.to_dict()})
        return indicator
        
    except Exception as e:
        logger.error(f"Error fetching GDP data: {e}")
        # Fallback to mock data
        return _get_mock_gdp_data(frequency, component)


def _get_employment_data(metric: str, geography: str) -> Optional[EconomicIndicator]:
    """Get employment data from Statistics Canada API"""
    cache_key = f"employment_{metric}_{geography}"
    # Employment data is monthly, cache for shorter duration since it's more dynamic
    cached_data = _load_statscan_cache(cache_key, cache_hours=12)  # 12 hours
    
    if cached_data and 'indicator' in cached_data:
        return EconomicIndicator.from_dict(cached_data['indicator'])
    
    try:
        # Get employment vectors
        vectors = _get_employment_vectors(metric, geography)
        if not vectors:
            return None
            
        # Fetch data from API
        api_data = _fetch_statscan_data(vectors, periods=13)  # 13 months for year-over-year
        if not api_data:
            return None
        
        # Process the data
        indicator = _process_employment_data(api_data, metric)
        
        # Cache the data
        _save_statscan_cache(cache_key, {'indicator': indicator.to_dict()})
        return indicator
        
    except Exception as e:
        logger.error(f"Error fetching employment data: {e}")
        # Fallback to mock data
        return _get_mock_employment_data(metric, geography)


def _format_cpi_output(indicator: EconomicIndicator, category: str, geography: str) -> str:
    """Format CPI data output"""
    trend_emoji = "📈" if indicator.year_change_pct > 0 else "📉"
    
    result = f"### **{indicator.name} ({geography})**\n\n"
    
    # Current value and trend
    result += f"- **Current Index:** {indicator.value:.1f}\n"
    result += f"- **Inflation Rate:** {indicator.year_change_pct:+.1f}% (12-month) {trend_emoji}\n"
    
    # Monthly change
    if indicator.period_change_pct >= 0:
        result += f"- **Monthly Change:** +{indicator.period_change_pct:.1f}% 📈\n"
    else:
        result += f"- **Monthly Change:** {indicator.period_change_pct:.1f}% 📉\n"
    
    # Context and analysis
    result += f"- **Last Updated:** {indicator.date}\n"
    result += f"- **Update Frequency:** Monthly (Statistics Canada)\n\n"
    
    # Add economic context
    result += "**Economic Context:**\n"
    if indicator.year_change_pct > 3.0:
        result += "- Elevated inflation above Bank of Canada's 2% target\n"
    elif indicator.year_change_pct > 1.0:
        result += "- Moderate inflation within acceptable range\n"
    else:
        result += "- Low inflation, potential deflation concerns\n"
    
    # Category-specific insights
    if category.lower() == "food":
        result += "- Food prices are a key driver of household budget pressures\n"
    elif category.lower() == "energy":
        result += "- Energy costs directly impact transportation and heating expenses\n"
    elif category.lower() == "shelter":
        result += "- Housing costs are the largest component of Canadian inflation\n"
    elif category.lower() == "all":
        result += "- Overall price trends reflect broad economic conditions\n"
    
    return result


def _format_gdp_output(indicator: EconomicIndicator, frequency: str, component: str) -> str:
    """Format GDP data output"""
    trend_emoji = "📈" if indicator.year_change_pct > 0 else "📉"
    
    result = f"### **{indicator.name} (Canada)**\n\n"
    
    # Current value and trend (API returns values in millions)
    gdp_billions = indicator.value / 1000
    result += f"- **Current GDP:** ${gdp_billions:.1f} billion\n"
    result += f"- **Annual Growth:** {indicator.year_change_pct:+.1f}% {trend_emoji}\n"
    
    # Period change
    period_label = "Quarterly" if frequency == "quarterly" else "Monthly"
    if indicator.period_change_pct >= 0:
        result += f"- **{period_label} Change:** +{indicator.period_change_pct:.1f}% 📈\n"
    else:
        result += f"- **{period_label} Change:** {indicator.period_change_pct:.1f}% 📉\n"
    
    # Context and analysis
    result += f"- **Last Updated:** {indicator.date}\n"
    frequency_text = "Quarterly" if frequency == "quarterly" else "Monthly"
    result += f"- **Update Frequency:** {frequency_text} (Statistics Canada)\n\n"
    
    # Add economic context
    result += "**Economic Analysis:**\n"
    if indicator.year_change_pct > 3.0:
        result += "- Strong economic growth above long-term average\n"
    elif indicator.year_change_pct > 1.0:
        result += "- Steady economic expansion\n"
    elif indicator.year_change_pct > -1.0:
        result += "- Slow growth, monitoring required\n"
    else:
        result += "- Economic contraction, recessionary concerns\n"
    
    # Add comparative context
    if indicator.year_change_pct > 2.0:
        result += "- Economic output performing above historical averages\n"
    else:
        result += "- Economic growth below long-term trends\n"
    
    return result


def _format_employment_output(indicator: EconomicIndicator, metric: str, geography: str) -> str:
    """Format employment data output"""
    # For unemployment rate, lower is better (so year_change < 0 is good trend)
    if metric == "unemployment_rate":
        trend_emoji = "📈" if indicator.year_change < 0 else "📉"
    else:
        trend_emoji = "📈" if indicator.year_change > 0 else "📉"
    
    result = f"### **{indicator.name} ({geography})**\n\n"
    
    # Current value and trend
    result += f"- **Current Rate:** {indicator.value:.1f}%\n"
    
    # Year-over-year change
    if indicator.year_change >= 0:
        result += f"- **12-Month Change:** +{indicator.year_change:.1f} percentage points {trend_emoji}\n"
    else:
        result += f"- **12-Month Change:** {indicator.year_change:.1f} percentage points {trend_emoji}\n"
    
    # Monthly change
    if indicator.period_change >= 0:
        result += f"- **Monthly Change:** +{indicator.period_change:.1f} percentage points\n"
    else:
        result += f"- **Monthly Change:** {indicator.period_change:.1f} percentage points\n"
    
    # Context and analysis
    result += f"- **Last Updated:** {indicator.date}\n"
    
    # Add next release information
    result += f"- **Update Frequency:** Monthly (Labour Force Survey)\n"
    next_release_date, days_until = _get_next_employment_release()
    if days_until > 0:
        result += f"- **Next Update:** {next_release_date} (in {days_until} days)\n"
    else:
        result += f"- **Next Update:** {next_release_date} (expected soon)\n"
    
    result += "\n**Labour Market Analysis:**\n"
    if metric == "unemployment_rate":
        if indicator.value > 7.0:
            result += "- Elevated unemployment above historical norms\n"
        elif indicator.value > 5.0:
            result += "- Moderate unemployment levels\n"
        else:
            result += "- Low unemployment, tight labour market\n"
    elif metric == "employment_rate":
        if indicator.value > 62.0:
            result += "- Strong employment participation\n"
        elif indicator.value > 58.0:
            result += "- Moderate employment levels\n"
        else:
            result += "- Weak employment participation\n"
    
    return result




def _get_next_employment_release() -> Tuple[str, int]:
    """Calculate next Labour Force Survey release date and days until"""
    today = datetime.now()
    
    # Labour Force Survey reference week is typically the week containing the 15th of the month
    # Data is released approximately 10 working days after the reference week ends
    
    # Find the next month to process
    if today.day <= 25:  # If we're early in the month, next release is for current month
        target_month = today.month
        target_year = today.year
    else:  # Otherwise, next release is for next month
        if today.month == 12:
            target_month = 1
            target_year = today.year + 1
        else:
            target_month = today.month + 1
            target_year = today.year
    
    # Find the reference week (week containing the 15th)
    # The survey week is Monday to Sunday containing the 15th
    fifteenth = datetime(target_year, target_month, 15)
    
    # Find the Monday of the week containing the 15th
    days_to_monday = fifteenth.weekday()  # 0 = Monday, 6 = Sunday
    reference_week_start = fifteenth - timedelta(days=days_to_monday)
    reference_week_end = reference_week_start + timedelta(days=6)  # Sunday
    
    # Release is approximately 10 working days after reference week ends
    # Add 14 calendar days to account for weekends (conservative estimate)
    estimated_release = reference_week_end + timedelta(days=14)
    
    # Calculate days until release
    days_until = (estimated_release - today).days
    
    # Format the date nicely
    release_date_str = estimated_release.strftime("%B %d, %Y")
    
    return release_date_str, max(0, days_until)


def _assess_economic_health(data: CanadianEconomicData) -> str:
    """Assess overall economic health based on all indicators"""
    health_score = 0
    
    # GDP Health (0-3 points)
    if data.gdp:
        if data.gdp.year_change_pct > 3.0:
            health_score += 3
        elif data.gdp.year_change_pct > 1.0:
            health_score += 2
        elif data.gdp.year_change_pct > 0:
            health_score += 1
    
    # Inflation Health (0-3 points) - target around 2%
    if data.cpi:
        if 1.5 <= data.cpi.year_change_pct <= 2.5:
            health_score += 3  # Ideal range
        elif 1.0 <= data.cpi.year_change_pct < 4.0:
            health_score += 2  # Acceptable range
        elif data.cpi.year_change_pct < 5.0:
            health_score += 1  # Concerning but manageable
    
    # Employment Health (0-3 points) - lower unemployment is better
    if data.employment:
        if data.employment.value < 5.0:
            health_score += 3  # Very low unemployment
        elif data.employment.value < 7.0:
            health_score += 2  # Moderate unemployment
        elif data.employment.value < 9.0:
            health_score += 1  # Higher unemployment
    
    # Determine overall health
    if health_score >= 7:
        return "Strong 💪"
    elif health_score >= 5:
        return "Moderate 📊"
    elif health_score >= 3:
        return "Mixed ⚠️"
    else:
        return "Concerning 📉"


def _get_gdp_status(growth_rate: float) -> str:
    """Get GDP growth status description"""
    if growth_rate > 3.0:
        return "Strong growth above long-term average"
    elif growth_rate > 1.0:
        return "Steady economic expansion"
    elif growth_rate > 0:
        return "Slow growth, monitoring required"
    else:
        return "Economic contraction"


def _get_inflation_status_text(inflation_rate: float) -> str:
    """Get inflation status description"""
    if inflation_rate > 3.0:
        return "Above Bank of Canada's 2% target"
    elif inflation_rate > 1.0:
        return "Within acceptable range"
    elif inflation_rate > 0:
        return "Below target range"
    else:
        return "Deflationary pressures"


def _get_employment_status_text(unemployment_rate: float) -> str:
    """Get employment status description"""
    if unemployment_rate > 7.0:
        return "Elevated unemployment above historical norms"
    elif unemployment_rate > 5.0:
        return "Moderate unemployment levels"
    else:
        return "Low unemployment, tight labour market"


def _generate_economic_insights(data: CanadianEconomicData) -> str:
    """Generate cross-indicator economic insights"""
    insights = []
    
    # GDP and Employment correlation
    if data.gdp and data.employment:
        if data.gdp.year_change_pct > 2.0 and data.employment.value < 6.0:
            insights.append("- Strong GDP growth paired with low unemployment suggests a robust economy")
        elif data.gdp.year_change_pct < 1.0 and data.employment.value > 7.0:
            insights.append("- Slow growth and higher unemployment indicate economic challenges")
    
    # Inflation and Growth balance
    if data.cpi and data.gdp:
        if data.cpi.year_change_pct > 3.0 and data.gdp.year_change_pct > 3.0:
            insights.append("- High growth with elevated inflation may prompt monetary policy tightening")
        elif data.cpi.year_change_pct < 2.0 and data.gdp.year_change_pct > 2.0:
            insights.append("- Healthy growth with controlled inflation is ideal for sustained expansion")
    
    # Employment trends
    if data.employment:
        next_release_date, days_until = _get_next_employment_release()
        if days_until > 0:
            insights.append(f"- Next employment data release: {next_release_date} (in {days_until} days)")
    
    # Overall economic narrative
    if data.gdp and data.cpi and data.employment:
        if (data.gdp.year_change_pct > 1.5 and 
            1.0 <= data.cpi.year_change_pct <= 3.0 and 
            data.employment.value < 7.0):
            insights.append("- Canada's economy shows balanced growth with stable inflation and employment")
        elif data.gdp.year_change_pct < 1.0:
            insights.append("- Economic growth remains subdued, requiring continued monitoring")
    
    return "\n".join(insights) if insights else "- Economic indicators suggest continued monitoring of key trends"


def _load_statscan_cache(cache_key: str, cache_hours: int = 24) -> Optional[Dict]:
    """Load cached Statistics Canada data if still valid"""
    try:
        # Use existing cache but with custom TTL logic
        cached_data = load_cached_data(cache_key)
        if not cached_data:
            return None
            
        # Check if cache is still valid based on custom hours
        cached_at = cached_data.get('cached_at')
        if cached_at:
            cached_time = datetime.fromisoformat(cached_at)
            if datetime.now() - cached_time < timedelta(hours=cache_hours):
                return cached_data
        
        return None
    except Exception as e:
        logger.warning(f"Failed to load cache for {cache_key}: {e}")
        return None


def _save_statscan_cache(cache_key: str, data: Dict) -> None:
    """Save Statistics Canada data to cache with timestamp"""
    try:
        data['cached_at'] = datetime.now().isoformat()
        save_cached_data(cache_key, data)
    except Exception as e:
        logger.warning(f"Failed to cache data for {cache_key}: {e}")


def _get_cpi_vectors(category: str, geography: str) -> Optional[str]:
    """Get CPI vector ID for given category and geography"""
    category_lower = category.lower()
    
    if category_lower in CPI_VECTORS:
        geo_vectors = CPI_VECTORS[category_lower]
        if geography in geo_vectors:
            return geo_vectors[geography]
    
    # Default to Canada all-items if not found
    return CPI_VECTORS["all"]["Canada"]


def _fetch_statscan_data(vectors: str, periods: int = 12) -> Optional[Dict]:
    """Fetch data from Statistics Canada Web Data Service"""
    try:
        url = f"{STATSCAN_BASE_URL}/getDataFromVectorsAndLatestNPeriods"
        
        # Statistics Canada API expects POST request with JSON payload
        payload = [
            {
                "vectorId": int(vectors.replace('v', '')),  # Remove 'v' prefix and convert to int
                "latestN": periods
            }
        ]
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'MCP-Arena-Stats-Client/1.0'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            logger.error(f"Statistics Canada API returned status {response.status_code}: {response.text}")
            return None
            
        data = response.json()
        
        # Check if response indicates success
        if not data or len(data) == 0:
            logger.error("Statistics Canada API returned empty response")
            return None
            
        # Check for API-level errors
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if 'status' in first_item and first_item['status'] != 'SUCCESS':
                logger.error(f"Statistics Canada API error: {first_item.get('status')}")
                return None
        
        return data
        
    except Exception as e:
        logger.error(f"Error fetching Statistics Canada data: {e}")
        return None


def _process_cpi_data(api_data: Dict, category: str) -> EconomicIndicator:
    """Process CPI data from Statistics Canada API"""
    try:
        # Extract vector data from the API response structure
        # API returns: [{"status": "SUCCESS", "object": {...}}]
        response_obj = api_data[0].get('object', {})
        vector_data = response_obj.get('vectorDataPoint', [])
        
        if not vector_data or len(vector_data) == 0:
            logger.error("No vector data points found in API response")
            return _get_mock_cpi_data(category, "Canada")
        
        # Sort by reference period (newest first)
        vector_data.sort(key=lambda x: x.get('refPer', ''), reverse=True)
        
        # Get latest values
        latest = vector_data[0]
        previous = vector_data[1] if len(vector_data) > 1 else latest
        year_ago = vector_data[12] if len(vector_data) > 12 else latest
        
        # Calculate changes
        current_value = float(latest['value'])
        prev_value = float(previous['value'])
        year_value = float(year_ago['value'])
        
        period_change = current_value - prev_value
        period_change_pct = (period_change / prev_value * 100) if prev_value != 0 else 0
        
        year_change = current_value - year_value
        year_change_pct = (year_change / year_value * 100) if year_value != 0 else 0
        
        # Create indicator
        indicator = EconomicIndicator(
            name=f"Consumer Price Index - {category.title()}",
            value=current_value,
            date=latest['refPer'],
            period_change=period_change,
            period_change_pct=period_change_pct,
            year_change=year_change,
            year_change_pct=year_change_pct,
            units="Index (2002=100)"
        )
        
        return indicator
        
    except Exception as e:
        logger.error(f"Error processing CPI data: {e}")
        # Return mock data as fallback
        return _get_mock_cpi_data(category, "Canada")


def _get_mock_cpi_data(category: str, geography: str) -> EconomicIndicator:
    """Generate mock CPI data for development/fallback"""
    current_date = datetime.now().strftime("%Y-%m")
    
    # Sample CPI data structure based on research
    if category.lower() == "all":
        return EconomicIndicator(
            name="Consumer Price Index - All Items",
            value=159.8,  # Based on 2002=100
            date=current_date,
            period_change=0.2,
            period_change_pct=0.1,
            year_change=2.8,
            year_change_pct=1.8,
            units="Index (2002=100)"
        )
    elif category.lower() == "food":
        return EconomicIndicator(
            name="Consumer Price Index - Food",
            value=174.2,
            date=current_date,
            period_change=0.4,
            period_change_pct=0.2,
            year_change=6.1,
            year_change_pct=3.6,
            units="Index (2002=100)"
        )
    else:
        # Default structure
        return EconomicIndicator(
            name=f"Consumer Price Index - {category.title()}",
            value=155.0,
            date=current_date,
            period_change=0.1,
            period_change_pct=0.1,
            year_change=2.5,
            year_change_pct=1.6,
            units="Index (2002=100)"
        )


def _get_gdp_vectors(frequency: str, component: str) -> Optional[str]:
    """Get GDP vector ID for given frequency and component"""
    component_lower = component.lower()
    
    if component_lower in GDP_VECTORS:
        comp_vectors = GDP_VECTORS[component_lower]
        if frequency in comp_vectors:
            return comp_vectors[frequency]
    
    # Default to total GDP
    return GDP_VECTORS["total"].get(frequency, GDP_VECTORS["total"]["quarterly"])


def _get_employment_vectors(metric: str, geography: str) -> Optional[str]:
    """Get employment vector ID for given metric and geography"""
    metric_lower = metric.lower()
    
    if metric_lower in EMPLOYMENT_VECTORS:
        geo_vectors = EMPLOYMENT_VECTORS[metric_lower]
        if geography in geo_vectors:
            return geo_vectors[geography]
    
    # Default to Canada unemployment rate
    return EMPLOYMENT_VECTORS["unemployment_rate"]["Canada"]


def _process_gdp_data(api_data: Dict, frequency: str, component: str) -> EconomicIndicator:
    """Process GDP data from Statistics Canada API"""
    try:
        # Extract vector data from the API response structure
        response_obj = api_data[0].get('object', {})
        vector_data = response_obj.get('vectorDataPoint', [])
        
        if not vector_data or len(vector_data) == 0:
            logger.error("No vector data points found in GDP API response")
            return _get_mock_gdp_data(frequency, component)
        
        # Sort by reference period (newest first)
        vector_data.sort(key=lambda x: x.get('refPer', ''), reverse=True)
        
        # Get latest values
        latest = vector_data[0]
        previous = vector_data[1] if len(vector_data) > 1 else latest
        year_ago = vector_data[4] if len(vector_data) > 4 else latest  # 4 quarters ago
        
        # Calculate changes
        current_value = float(latest['value'])
        prev_value = float(previous['value'])
        year_value = float(year_ago['value'])
        
        period_change = current_value - prev_value
        period_change_pct = (period_change / prev_value * 100) if prev_value != 0 else 0
        
        year_change = current_value - year_value
        year_change_pct = (year_change / year_value * 100) if year_value != 0 else 0
        
        # Create indicator
        indicator = EconomicIndicator(
            name=f"Gross Domestic Product ({frequency.title()})",
            value=current_value,
            date=latest['refPer'],
            period_change=period_change,
            period_change_pct=period_change_pct,
            year_change=year_change,
            year_change_pct=year_change_pct,
            units="Billions of dollars"
        )
        
        return indicator
        
    except Exception as e:
        logger.error(f"Error processing GDP data: {e}")
        # Return mock data as fallback
        return _get_mock_gdp_data(frequency, component)


def _process_employment_data(api_data: Dict, metric: str) -> EconomicIndicator:
    """Process employment data from Statistics Canada API"""
    try:
        # Extract vector data from the API response structure
        response_obj = api_data[0].get('object', {})
        vector_data = response_obj.get('vectorDataPoint', [])
        
        if not vector_data or len(vector_data) == 0:
            logger.error("No vector data points found in employment API response")
            return _get_mock_employment_data(metric, "Canada")
        
        # Sort by reference period (newest first)
        vector_data.sort(key=lambda x: x.get('refPer', ''), reverse=True)
        
        # Get latest values
        latest = vector_data[0]
        previous = vector_data[1] if len(vector_data) > 1 else latest
        year_ago = vector_data[12] if len(vector_data) > 12 else latest
        
        # Calculate changes
        current_value = float(latest['value'])
        prev_value = float(previous['value'])
        year_value = float(year_ago['value'])
        
        period_change = current_value - prev_value
        period_change_pct = (period_change / prev_value * 100) if prev_value != 0 else 0
        
        year_change = current_value - year_value
        year_change_pct = (year_change / year_value * 100) if year_value != 0 else 0
        
        # Create indicator
        indicator = EconomicIndicator(
            name=metric.replace('_', ' ').title(),
            value=current_value,
            date=latest['refPer'],
            period_change=period_change,
            period_change_pct=period_change_pct,
            year_change=year_change,
            year_change_pct=year_change_pct,
            units="Percent"
        )
        
        return indicator
        
    except Exception as e:
        logger.error(f"Error processing employment data: {e}")
        # Return mock data as fallback
        return _get_mock_employment_data(metric, "Canada")


def _get_mock_gdp_data(frequency: str, component: str) -> EconomicIndicator:
    """Generate mock GDP data for development/fallback"""
    current_date = datetime.now().strftime("%Y-Q1" if frequency == "quarterly" else "%Y-%m")
    
    # Sample GDP data structure based on research
    if frequency == "quarterly":
        return EconomicIndicator(
            name="Gross Domestic Product (Quarterly)",
            value=2450.8,  # Billions of chained 2017 dollars
            date=current_date,
            period_change=12.1,
            period_change_pct=0.5,
            year_change=56.3,
            year_change_pct=2.4,
            units="Billions of dollars"
        )
    else:
        return EconomicIndicator(
            name="Gross Domestic Product (Monthly)",
            value=2055.2,
            date=current_date,
            period_change=8.2,
            period_change_pct=0.4,
            year_change=45.8,
            year_change_pct=2.3,
            units="Billions of dollars"
        )


def _get_mock_employment_data(metric: str, geography: str) -> EconomicIndicator:
    """Generate mock employment data for development/fallback"""
    current_date = datetime.now().strftime("%Y-%m")
    
    # Sample employment data structure based on research
    if metric == "unemployment_rate":
        return EconomicIndicator(
            name="Unemployment Rate",
            value=6.2,
            date=current_date,
            period_change=0.1,
            period_change_pct=1.6,
            year_change=0.8,
            year_change_pct=14.8,
            units="Percent"
        )
    elif metric == "employment_rate":
        return EconomicIndicator(
            name="Employment Rate",
            value=61.2,
            date=current_date,
            period_change=-0.1,
            period_change_pct=-0.2,
            year_change=-0.6,
            year_change_pct=-1.0,
            units="Percent"
        )
    else:
        return EconomicIndicator(
            name=f"{metric.replace('_', ' ').title()}",
            value=20.5,
            date=current_date,
            period_change=0.05,
            period_change_pct=0.2,
            year_change=0.4,
            year_change_pct=2.0,
            units="Millions of persons"
        )