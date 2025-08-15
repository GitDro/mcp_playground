"""
Example: Converting existing financial tool to use retry functionality.

This shows how to retrofit an existing tool with retry capabilities by:
1. Adding the @retry_tool decorator
2. Enhancing input validation 
3. Maintaining original functionality

Compare this with the original src/tools/financial.py to see the differences.
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from fastmcp import FastMCP
from src.core.cache import load_cached_data, save_cached_data, cleanup_old_cache
from src.core.tool_wrapper import retry_tool

logger = logging.getLogger(__name__)

# Common headers for all Yahoo Finance requests
YAHOO_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def register_financial_tools_with_retry(mcp: FastMCP):
    """Register financial tools with enhanced retry capabilities"""
    
    @retry_tool(
        mcp, 
        description="Get comprehensive stock, crypto, and market data with automatic error recovery",
        max_attempts=3,
        enable_type_coercion=True
    )
    def get_stock_overview_with_retry(symbol: str, include_chart: bool = True) -> str:
        """Get comprehensive stock market data with retry-enhanced error handling.
        
        Enhanced version of the original tool that demonstrates:
        - Automatic type correction for boolean parameters
        - Retry logic for network failures
        - Input validation with helpful error messages
        
        Args:
            symbol: Stock symbol, crypto symbol, or market index (e.g., "AAPL", "BTC", "SPY")
            include_chart: Whether to include trend visualization chart (default: True)
        """
        
        # Enhanced input validation
        if not isinstance(symbol, str):
            raise TypeError(f"Symbol must be a string, got {type(symbol).__name__}: {symbol}")
        
        if not isinstance(include_chart, bool):
            raise TypeError(f"include_chart must be boolean (True/False), got {type(include_chart).__name__}: {include_chart}")
        
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("Symbol cannot be empty")
        
        # Validate symbol format (basic check)
        if len(symbol) > 10 or not symbol.replace('-', '').replace('.', '').isalnum():
            raise ValueError(f"Invalid symbol format: {symbol}")
        
        try:
            cleanup_old_cache()
            
            # Format symbol and detect asset type
            formatted_symbol, asset_type = _format_symbol(symbol)
            
            # Get current market data with retry-friendly error handling
            quote_data = _get_current_data_with_retry(formatted_symbol)
            if not quote_data:
                raise ConnectionError(f"Could not retrieve market data for symbol: {symbol}")
            
            # Get historical data (1-month and 1-year)
            hist_data = _get_historical_data_with_retry(formatted_symbol, "1mo")
            year_data = _get_historical_data_with_retry(formatted_symbol, "1y", year_only=True)
            
            # Format and return the output
            asset_name = _get_asset_name(symbol, asset_type, quote_data)
            return _format_financial_output_enhanced(
                quote_data, hist_data, year_data, asset_name, asset_type, include_chart
            )
            
        except ConnectionError:
            # Re-raise connection errors for retry handling
            raise
        except Exception as e:
            logger.error(f"Error getting stock overview for {symbol}: {e}")
            raise RuntimeError(f"Failed to retrieve stock data for {symbol}: {str(e)}")

    @retry_tool(
        mcp,
        description="Compare multiple stock symbols with retry-enhanced reliability",
        max_attempts=2
    )
    def compare_stocks_with_retry(symbols: str, metric: str = "price") -> str:
        """Compare multiple stock symbols with enhanced error recovery.
        
        Args:
            symbols: Comma-separated stock symbols (e.g., "AAPL,MSFT,GOOGL")
            metric: Comparison metric ("price", "change", "volume")
        """
        
        # Input validation with helpful error messages
        if not isinstance(symbols, str):
            raise TypeError(f"Symbols must be a string of comma-separated symbols, got {type(symbols).__name__}")
        
        if not isinstance(metric, str):
            raise TypeError(f"Metric must be a string, got {type(metric).__name__}")
        
        valid_metrics = ["price", "change", "volume"]
        if metric not in valid_metrics:
            raise ValueError(f"Metric must be one of {valid_metrics}, got: {metric}")
        
        # Parse and validate symbols
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise ValueError("At least one symbol must be provided")
        
        if len(symbol_list) > 10:
            raise ValueError("Maximum 10 symbols allowed for comparison")
        
        try:
            comparison_data = []
            
            for symbol in symbol_list:
                formatted_symbol, asset_type = _format_symbol(symbol)
                quote_data = _get_current_data_with_retry(formatted_symbol)
                
                if quote_data:
                    comparison_data.append({
                        'symbol': symbol,
                        'price': quote_data.get('current_price', 0),
                        'change': quote_data.get('change_pct', 0),
                        'volume': quote_data.get('volume', 0),
                        'asset_type': asset_type
                    })
                else:
                    logger.warning(f"Could not retrieve data for {symbol}")
            
            if not comparison_data:
                raise ConnectionError("Could not retrieve data for any of the requested symbols")
            
            return _format_comparison_output(comparison_data, metric)
            
        except ConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error comparing stocks: {e}")
            raise RuntimeError(f"Failed to compare stocks: {str(e)}")


def _format_symbol(symbol: str) -> Tuple[str, str]:
    """Format symbol for Yahoo Finance and detect asset type - enhanced with error handling"""
    try:
        crypto_symbols = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'LTC', 'XRP', 'DOGE', 'MATIC', 'SOL']
        
        if symbol.upper() in crypto_symbols:
            return f"{symbol.upper()}-USD", "crypto"
        else:
            return symbol.upper(), "stock"
    except Exception as e:
        raise ValueError(f"Error formatting symbol {symbol}: {e}")


def _get_current_data_with_retry(formatted_symbol: str) -> Optional[Dict]:
    """Get current market data with enhanced error handling for retry system"""
    try:
        cache_key = f"{formatted_symbol}_current"
        cached_data = load_cached_data(cache_key)
        
        if cached_data and 'quote' in cached_data:
            return cached_data['quote']
        
        # Fetch fresh data with better error messages
        data = _fetch_yahoo_data_with_retry(formatted_symbol)
        if not data:
            raise ConnectionError(f"Yahoo Finance API returned no data for {formatted_symbol}")
        
        if not data.get('chart') or not data['chart'].get('result'):
            raise ConnectionError(f"Invalid response format from Yahoo Finance for {formatted_symbol}")
        
        meta = data['chart']['result'][0].get('meta', {})
        current_price = meta.get('regularMarketPrice', 0)
        prev_close = meta.get('previousClose', current_price)
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close != 0 else 0
        
        quote_data = {
            'symbol': meta.get('symbol', formatted_symbol),
            'current_price': current_price,
            'change': change,
            'change_pct': change_pct,
            'high': meta.get('regularMarketDayHigh', current_price),
            'low': meta.get('regularMarketDayLow', current_price),
            'volume': meta.get('regularMarketVolume', 0)
        }
        
        save_cached_data(cache_key, {'quote': quote_data})
        return quote_data
        
    except ConnectionError:
        raise  # Re-raise connection errors for retry handling
    except Exception as e:
        logger.error(f"Error getting current data for {formatted_symbol}: {e}")
        raise RuntimeError(f"Data processing error for {formatted_symbol}: {e}")


def _get_historical_data_with_retry(formatted_symbol: str, range_param: str, year_only: bool = False) -> Optional[Dict]:
    """Get historical data with enhanced error handling"""
    try:
        cache_key = f"{formatted_symbol}_history_{range_param}"
        cache_type = 'year_data' if year_only else 'history'
        cached_data = load_cached_data(cache_key)
        
        if cached_data and cache_type in cached_data:
            return cached_data[cache_type]
        
        # Fetch fresh data
        data = _fetch_yahoo_data_with_retry(formatted_symbol, range_param)
        if not data:
            raise ConnectionError(f"Could not fetch historical data for {formatted_symbol}")
        
        result = data['chart']['result'][0]
        timestamps = result.get('timestamp', [])
        indicators = result.get('indicators', {})
        quote = indicators.get('quote', [{}])[0]
        
        if not timestamps or not quote:
            raise ValueError(f"Invalid historical data format for {formatted_symbol}")
        
        closes = quote.get('close', [])
        valid_data = []
        
        for i, ts in enumerate(timestamps):
            if i < len(closes) and closes[i] is not None:
                if year_only:
                    valid_data.append(closes[i])
                else:
                    valid_data.append({'timestamp': ts, 'close': closes[i]})
        
        if not valid_data:
            raise ValueError(f"No valid historical data found for {formatted_symbol}")
        
        if year_only:
            hist_data = {
                'year_high': max(valid_data),
                'year_low': min(valid_data)
            }
        else:
            hist_data = {
                'current_price': valid_data[-1]['close'],
                'start_price': valid_data[0]['close'],
                'high_price': max(d['close'] for d in valid_data),
                'low_price': min(d['close'] for d in valid_data),
                'price_data': valid_data
            }
        
        save_cached_data(cache_key, {cache_type: hist_data})
        return hist_data
        
    except (ConnectionError, ValueError):
        raise  # Re-raise for retry handling
    except Exception as e:
        logger.error(f"Error getting historical data for {formatted_symbol}: {e}")
        raise RuntimeError(f"Historical data processing error: {e}")


def _fetch_yahoo_data_with_retry(symbol: str, range_param: str = None) -> Optional[Dict]:
    """Unified Yahoo Finance API fetching with enhanced error handling"""
    import requests
    
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    if range_param:
        url += f'?range={range_param}&interval=1d'
    
    try:
        response = requests.get(url, headers=YAHOO_HEADERS, timeout=10)
        
        if response.status_code == 404:
            raise ValueError(f"Symbol not found: {symbol}")
        elif response.status_code == 429:
            raise ConnectionError("Rate limit exceeded - too many requests to Yahoo Finance")
        elif response.status_code >= 500:
            raise ConnectionError(f"Yahoo Finance server error: HTTP {response.status_code}")
        elif response.status_code != 200:
            raise ConnectionError(f"HTTP error {response.status_code} fetching data for {symbol}")
        
        data = response.json()
        if not data.get('chart') or not data['chart'].get('result'):
            raise ValueError(f"Invalid response format for {symbol}")
        
        return data
        
    except requests.exceptions.Timeout:
        raise ConnectionError(f"Request timeout fetching data for {symbol}")
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Network connection error fetching data for {symbol}")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Network error fetching data for {symbol}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching Yahoo data for {symbol}: {e}")
        raise RuntimeError(f"Data fetch error: {e}")


def _get_asset_name(symbol: str, asset_type: str, quote_data: Dict) -> str:
    """Generate display name for the asset"""
    if asset_type == "crypto":
        return f"{symbol.upper()} (Cryptocurrency)"
    else:
        return quote_data.get('symbol', symbol.upper())


def _format_financial_output_enhanced(quote_data: Dict, hist_data: Optional[Dict], year_data: Optional[Dict], 
                                     asset_name: str, asset_type: str, include_chart: bool) -> str:
    """Format the comprehensive financial output with retry-enhanced features"""
    current_price = float(quote_data.get('current_price', 0))
    change = float(quote_data.get('change', 0))
    change_pct = float(quote_data.get('change_pct', 0))
    trend_emoji = "📈" if change >= 0 else "📉"
    
    # Start building output with retry success indicator
    result = f"### **{asset_name} - Financial Overview** 🔄✅\n\n"
    
    # Current price
    if change >= 0:
        result += f"- **Current Price:** ${current_price:,.2f} {trend_emoji} +${change:.2f} (+{change_pct:.2f}%)\n"
    else:
        result += f"- **Current Price:** ${current_price:,.2f} {trend_emoji} ${change:.2f} ({change_pct:.2f}%)\n"
    
    # 1-month performance
    if hist_data:
        month_return = ((hist_data['current_price'] - hist_data['start_price']) / hist_data['start_price']) * 100
        month_emoji = "📈" if month_return >= 0 else "📉"
        sign = "+" if month_return >= 0 else ""
        result += f"- **1-Month Return:** {sign}{month_return:.2f}% {month_emoji}\n"
    
    # Volume (stocks only)
    if quote_data.get('volume') and asset_type != "crypto":
        volume = int(quote_data.get('volume', 0))
        if volume > 1e9:
            volume_str = f"{volume/1e9:.1f}B shares"
        elif volume > 1e6:
            volume_str = f"{volume/1e6:.1f}M shares"
        else:
            volume_str = f"{volume:,} shares"
        result += f"- **Volume:** {volume_str}\n"
    
    # Ranges table
    result += "\n| **Period** | **Low** | **High** |\n"
    result += "|-----------|---------|----------|\n"
    
    # Day range
    if quote_data.get('high') and quote_data.get('low'):
        high = float(quote_data.get('high', 0))
        low = float(quote_data.get('low', 0))
        result += f"| **Day** | ${low:,.2f} | ${high:,.2f} |\n"
    
    # Month range
    if hist_data:
        result += f"| **Month** | ${hist_data['low_price']:,.2f} | ${hist_data['high_price']:,.2f} |\n"
    
    # Year range
    if year_data:
        result += f"| **Year** | ${year_data['year_low']:,.2f} | ${year_data['year_high']:,.2f} |\n"
    
    # Add trend chart if requested and available
    if include_chart and hist_data:
        try:
            plot_data = _generate_financial_plot_safe(asset_name, hist_data)
            if plot_data:
                result += f"\n\n![{asset_name} 1-Month Trend]({plot_data})"
        except Exception as e:
            logger.warning(f"Chart generation failed: {e}")
            result += f"\n\n*Chart generation temporarily unavailable*"
    
    result += f"\n\n*🔄 Data retrieved with retry-enhanced reliability*"
    
    return result


def _format_comparison_output(comparison_data: List[Dict], metric: str) -> str:
    """Format comparison output"""
    result = f"### Stock Comparison - {metric.title()}\n\n"
    
    # Sort by the requested metric
    if metric == "price":
        sorted_data = sorted(comparison_data, key=lambda x: x['price'], reverse=True)
        result += "| Symbol | Price | Change % | Type |\n"
        result += "|--------|-------|----------|------|\n"
        for item in sorted_data:
            result += f"| {item['symbol']} | ${item['price']:,.2f} | {item['change']:+.2f}% | {item['asset_type']} |\n"
    
    elif metric == "change":
        sorted_data = sorted(comparison_data, key=lambda x: x['change'], reverse=True)
        result += "| Symbol | Change % | Price | Type |\n"
        result += "|--------|----------|-------|------|\n"
        for item in sorted_data:
            emoji = "📈" if item['change'] >= 0 else "📉"
            result += f"| {item['symbol']} | {item['change']:+.2f}% {emoji} | ${item['price']:,.2f} | {item['asset_type']} |\n"
    
    else:  # volume
        sorted_data = sorted(comparison_data, key=lambda x: x['volume'], reverse=True)
        result += "| Symbol | Volume | Price | Type |\n"
        result += "|--------|--------|-------|------|\n"
        for item in sorted_data:
            vol = item['volume']
            vol_str = f"{vol/1e9:.1f}B" if vol > 1e9 else f"{vol/1e6:.1f}M" if vol > 1e6 else f"{vol:,}"
            result += f"| {item['symbol']} | {vol_str} | ${item['price']:,.2f} | {item['asset_type']} |\n"
    
    result += f"\n*Comparison data retrieved with enhanced reliability*"
    return result


def _generate_financial_plot_safe(asset_name: str, hist_data: Dict) -> Optional[str]:
    """Generate financial plot with error handling"""
    try:
        # Import plotting libraries with error handling
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        import base64
        import io
        
        # Generate plot (similar to original but with error handling)
        # ... plot generation code ...
        
        return "data:image/png;base64,placeholder"  # Placeholder for brevity
        
    except ImportError as e:
        logger.warning(f"Plotting libraries not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Error generating financial plot: {e}")
        return None


if __name__ == "__main__":
    # Example usage and testing
    print("Financial tools with retry - Example implementation")
    print("This demonstrates how to enhance existing tools with retry capabilities.")