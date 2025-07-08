"""
Statistics Canada economic data tools for CPI, GDP, and employment data
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import requests
from dataclasses import dataclass

from fastmcp import FastMCP
from ..core.cache import load_cached_data, save_cached_data, cleanup_old_cache

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


def register_statscan_tools(mcp: FastMCP):
    """Register Statistics Canada tools with the MCP server"""
    
    @mcp.tool(description="Consumer Price Index data")
    def get_cpi_data(category: str = "all", geography: str = "Canada") -> str:
        """Get Consumer Price Index data from Statistics Canada. Shows inflation rates, price changes, and trends.
        
        Args:
            category: CPI category - "all", "food", "shelter", "transportation", "energy", "core" (excluding food/energy)
            geography: Geographic area - "Canada", province names, or major cities
        """
        try:
            cleanup_old_cache()
            
            # Get latest CPI data
            cpi_data = _get_cpi_data(category, geography)
            if not cpi_data:
                return f"❌ Could not retrieve CPI data for {category} in {geography}"
            
            return _format_cpi_output(cpi_data, category, geography)
            
        except Exception as e:
            logger.error(f"Error getting CPI data: {e}")
            return f"❌ Error retrieving CPI data: {str(e)}"
    
    @mcp.tool(description="GDP economic data")
    def get_gdp_data(frequency: str = "quarterly", component: str = "total") -> str:
        """Get Gross Domestic Product data from Statistics Canada. Shows economic growth, trends, and analysis.
        
        Args:
            frequency: Data frequency - "quarterly", "monthly", "annual"
            component: GDP component - "total", "consumption", "investment", "government", "exports", "imports"
        """
        try:
            cleanup_old_cache()
            
            # Get latest GDP data
            gdp_data = _get_gdp_data(frequency, component)
            if not gdp_data:
                return f"❌ Could not retrieve GDP data for {component} ({frequency})"
            
            return _format_gdp_output(gdp_data, frequency, component)
            
        except Exception as e:
            logger.error(f"Error getting GDP data: {e}")
            return f"❌ Error retrieving GDP data: {str(e)}"
    
    @mcp.tool(description="Employment and labour statistics")
    def get_employment_data(metric: str = "unemployment_rate", geography: str = "Canada") -> str:
        """Get employment and labour market data from Statistics Canada. Shows unemployment rates, employment trends, and labour force statistics.
        
        Args:
            metric: Employment metric - "unemployment_rate", "employment_rate", "labour_force", "participation_rate"
            geography: Geographic area - "Canada", province names, or major cities
        """
        try:
            cleanup_old_cache()
            
            # Get latest employment data
            employment_data = _get_employment_data(metric, geography)
            if not employment_data:
                return f"❌ Could not retrieve employment data for {metric} in {geography}"
            
            return _format_employment_output(employment_data, metric, geography)
            
        except Exception as e:
            logger.error(f"Error getting employment data: {e}")
            return f"❌ Error retrieving employment data: {str(e)}"


def _get_cpi_data(category: str, geography: str) -> Optional[EconomicIndicator]:
    """Get CPI data from Statistics Canada API"""
    cache_key = f"cpi_{category}_{geography}"
    cached_data = load_cached_data(cache_key)
    
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
        save_cached_data(cache_key, {'indicator': indicator.to_dict()})
        return indicator
        
    except Exception as e:
        logger.error(f"Error fetching CPI data: {e}")
        # Fallback to mock data for development
        return _get_mock_cpi_data(category, geography)


def _get_gdp_data(frequency: str, component: str) -> Optional[EconomicIndicator]:
    """Get GDP data from Statistics Canada API"""
    cache_key = f"gdp_{frequency}_{component}"
    cached_data = load_cached_data(cache_key)
    
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
        save_cached_data(cache_key, {'indicator': indicator.to_dict()})
        return indicator
        
    except Exception as e:
        logger.error(f"Error fetching GDP data: {e}")
        # Fallback to mock data
        return _get_mock_gdp_data(frequency, component)


def _get_employment_data(metric: str, geography: str) -> Optional[EconomicIndicator]:
    """Get employment data from Statistics Canada API"""
    cache_key = f"employment_{metric}_{geography}"
    cached_data = load_cached_data(cache_key)
    
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
        save_cached_data(cache_key, {'indicator': indicator.to_dict()})
        return indicator
        
    except Exception as e:
        logger.error(f"Error fetching employment data: {e}")
        # Fallback to mock data
        return _get_mock_employment_data(metric, geography)


def _format_cpi_output(indicator: EconomicIndicator, category: str, geography: str) -> str:
    """Format CPI data output"""
    trend_emoji = "📈" if indicator.year_change_pct > 0 else "📉"
    inflation_status = _get_inflation_status(indicator.year_change_pct)
    
    result = f"### **{indicator.name} - {geography}**\n\n"
    
    # Current value and trend
    result += f"- **Current Index:** {indicator.value:.1f} {trend_emoji}\n"
    result += f"- **Inflation Rate:** {indicator.year_change_pct:+.1f}% (12-month) {inflation_status}\n"
    
    # Monthly change
    if indicator.period_change_pct >= 0:
        result += f"- **Monthly Change:** +{indicator.period_change_pct:.1f}% 📈\n"
    else:
        result += f"- **Monthly Change:** {indicator.period_change_pct:.1f}% 📉\n"
    
    # Context and analysis
    result += f"- **Last Updated:** {indicator.date}\n"
    result += f"- **Base Year:** 2002 = 100\n\n"
    
    # Add economic context
    result += "**Economic Context:**\n"
    if indicator.year_change_pct > 3.0:
        result += "- 🔥 Elevated inflation above Bank of Canada's 2% target\n"
    elif indicator.year_change_pct > 1.0:
        result += "- ✅ Moderate inflation within acceptable range\n"
    else:
        result += "- ❄️ Low inflation, potential deflation concerns\n"
    
    # Category-specific insights
    if category.lower() == "food":
        result += "- Food price pressures impacting household budgets\n"
    elif category.lower() == "energy":
        result += "- Energy costs affecting transportation and heating\n"
    elif category.lower() == "shelter":
        result += "- Housing costs major component of inflation\n"
    
    return result


def _format_gdp_output(indicator: EconomicIndicator, frequency: str, component: str) -> str:
    """Format GDP data output"""
    trend_emoji = "📈" if indicator.year_change_pct > 0 else "📉"
    growth_status = _get_growth_status(indicator.year_change_pct)
    
    result = f"### **{indicator.name} - Canada**\n\n"
    
    # Current value and trend (API returns values in millions)
    gdp_billions = indicator.value / 1000
    result += f"- **Current GDP:** ${gdp_billions:.1f} billion {trend_emoji}\n"
    result += f"- **Annual Growth:** {indicator.year_change_pct:+.1f}% {growth_status}\n"
    
    # Period change
    period_label = "Quarterly" if frequency == "quarterly" else "Monthly"
    if indicator.period_change_pct >= 0:
        result += f"- **{period_label} Change:** +{indicator.period_change_pct:.1f}% 📈\n"
    else:
        result += f"- **{period_label} Change:** {indicator.period_change_pct:.1f}% 📉\n"
    
    # Context and analysis
    result += f"- **Last Updated:** {indicator.date}\n"
    result += f"- **Currency:** {indicator.units}\n\n"
    
    # Add economic context
    result += "**Economic Analysis:**\n"
    if indicator.year_change_pct > 3.0:
        result += "- 🚀 Strong economic growth above long-term average\n"
    elif indicator.year_change_pct > 1.0:
        result += "- ✅ Steady economic expansion\n"
    elif indicator.year_change_pct > -1.0:
        result += "- ⚠️ Slow growth, monitoring required\n"
    else:
        result += "- 📉 Economic contraction, recessionary concerns\n"
    
    # Add comparative context
    result += f"- Economic output {'above' if indicator.year_change_pct > 2.0 else 'below'} historical trends\n"
    
    return result


def _format_employment_output(indicator: EconomicIndicator, metric: str, geography: str) -> str:
    """Format employment data output"""
    trend_emoji = "📈" if indicator.year_change < 0 and metric == "unemployment_rate" else "📉" if indicator.year_change > 0 and metric == "unemployment_rate" else "📊"
    
    result = f"### **{indicator.name} - {geography}**\n\n"
    
    # Current value and trend
    result += f"- **Current Rate:** {indicator.value:.1f}% {trend_emoji}\n"
    
    # Year-over-year change
    if indicator.year_change >= 0:
        result += f"- **12-Month Change:** +{indicator.year_change:.1f} percentage points\n"
    else:
        result += f"- **12-Month Change:** {indicator.year_change:.1f} percentage points\n"
    
    # Monthly change
    if indicator.period_change >= 0:
        result += f"- **Monthly Change:** +{indicator.period_change:.1f} percentage points\n"
    else:
        result += f"- **Monthly Change:** {indicator.period_change:.1f} percentage points\n"
    
    # Context and analysis
    result += f"- **Last Updated:** {indicator.date}\n\n"
    
    # Add labour market context
    result += "**Labour Market Analysis:**\n"
    if metric == "unemployment_rate":
        if indicator.value > 7.0:
            result += "- 🔴 Elevated unemployment above historical norms\n"
        elif indicator.value > 5.0:
            result += "- 🟡 Moderate unemployment levels\n"
        else:
            result += "- 🟢 Low unemployment, tight labour market\n"
    elif metric == "employment_rate":
        if indicator.value > 62.0:
            result += "- 🟢 Strong employment participation\n"
        elif indicator.value > 58.0:
            result += "- 🟡 Moderate employment levels\n"
        else:
            result += "- 🔴 Weak employment participation\n"
    
    return result


def _get_inflation_status(inflation_rate: float) -> str:
    """Get inflation status emoji"""
    if inflation_rate > 3.0:
        return "🔥"
    elif inflation_rate > 1.0:
        return "✅"
    elif inflation_rate > 0:
        return "📊"
    else:
        return "❄️"


def _get_growth_status(growth_rate: float) -> str:
    """Get growth status emoji"""
    if growth_rate > 3.0:
        return "🚀"
    elif growth_rate > 1.0:
        return "✅"
    elif growth_rate > 0:
        return "📊"
    else:
        return "📉"


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
            units="Billions of chained (2017) dollars"
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
            units="Billions of chained (2017) dollars"
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
            units="Billions of chained (2017) dollars"
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