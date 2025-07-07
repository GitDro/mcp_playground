"""
Consolidated financial data tool for stocks, cryptocurrency, and market data
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from fastmcp import FastMCP
from ..core.cache import load_cached_data, save_cached_data, cleanup_old_cache

logger = logging.getLogger(__name__)

# Common headers for all Yahoo Finance requests
YAHOO_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def register_financial_tools(mcp: FastMCP):
    """Register financial-related tools with the MCP server"""
    
    @mcp.tool(description="stock market data")
    def get_stock_overview(symbol: str) -> str:
        """Get comprehensive stock market data for any asset - stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA), crypto (BTC, ETH), or market indices (SPY, QQQ). Shows current price, daily change, volume, 1-month performance, and trend visualization."""
        try:
            cleanup_old_cache()
            
            # Format symbol and detect asset type
            formatted_symbol, asset_type = _format_symbol(symbol)
            
            # Get current market data
            quote_data = _get_current_data(formatted_symbol)
            if not quote_data:
                return f"❌ Could not find data for symbol: {symbol}"
            
            # Get historical data (1-month and 1-year)
            hist_data = _get_historical_data(formatted_symbol, "1mo")
            year_data = _get_historical_data(formatted_symbol, "1y", year_only=True)
            
            # Format and return the output
            asset_name = _get_asset_name(symbol, asset_type, quote_data)
            return _format_financial_output(quote_data, hist_data, year_data, asset_name, asset_type)
            
        except Exception as e:
            logger.error(f"Error getting stock overview for {symbol}: {e}")
            return f"❌ Error retrieving stock data for {symbol}: {str(e)}"


def _format_symbol(symbol: str) -> Tuple[str, str]:
    """Format symbol for Yahoo Finance and detect asset type"""
    crypto_symbols = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'LTC', 'XRP', 'DOGE', 'MATIC', 'SOL']
    
    if symbol.upper() in crypto_symbols:
        return f"{symbol.upper()}-USD", "crypto"
    else:
        return symbol.upper(), "stock"


def _get_current_data(formatted_symbol: str) -> Optional[Dict]:
    """Get current market data with caching"""
    cache_key = f"{formatted_symbol}_current"
    cached_data = load_cached_data(cache_key)
    
    if cached_data and 'quote' in cached_data:
        return cached_data['quote']
    
    # Fetch fresh data
    data = _fetch_yahoo_data(formatted_symbol)
    if not data:
        return None
    
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


def _get_historical_data(formatted_symbol: str, range_param: str, year_only: bool = False) -> Optional[Dict]:
    """Get historical data with caching"""
    cache_key = f"{formatted_symbol}_history_{range_param}"
    cache_type = 'year_data' if year_only else 'history'
    cached_data = load_cached_data(cache_key)
    
    if cached_data and cache_type in cached_data:
        return cached_data[cache_type]
    
    # Fetch fresh data
    data = _fetch_yahoo_data(formatted_symbol, range_param)
    if not data:
        return None
    
    result = data['chart']['result'][0]
    timestamps = result.get('timestamp', [])
    indicators = result.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]
    
    if not timestamps or not quote:
        return None
    
    closes = quote.get('close', [])
    valid_data = []
    
    for i, ts in enumerate(timestamps):
        if i < len(closes) and closes[i] is not None:
            if year_only:
                valid_data.append(closes[i])
            else:
                valid_data.append({'timestamp': ts, 'close': closes[i]})
    
    if not valid_data:
        return None
    
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


def _fetch_yahoo_data(symbol: str, range_param: str = None) -> Optional[Dict]:
    """Unified Yahoo Finance API fetching"""
    import requests
    
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    if range_param:
        url += f'?range={range_param}&interval=1d'
    
    try:
        response = requests.get(url, headers=YAHOO_HEADERS, timeout=10)
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data.get('chart') or not data['chart'].get('result'):
            return None
        
        return data
    except Exception as e:
        logger.error(f"Error fetching Yahoo data for {symbol}: {e}")
        return None


def _get_asset_name(symbol: str, asset_type: str, quote_data: Dict) -> str:
    """Generate display name for the asset"""
    if asset_type == "crypto":
        return f"{symbol.upper()} (Cryptocurrency)"
    else:
        return quote_data.get('symbol', symbol.upper())


def _format_financial_output(quote_data: Dict, hist_data: Optional[Dict], year_data: Optional[Dict], 
                           asset_name: str, asset_type: str) -> str:
    """Format the comprehensive financial output"""
    current_price = float(quote_data.get('current_price', 0))
    change = float(quote_data.get('change', 0))
    change_pct = float(quote_data.get('change_pct', 0))
    trend_emoji = "📈" if change >= 0 else "📉"
    
    # Start building output
    result = f"### **{asset_name} - Financial Overview**\n\n"
    
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
    
    # Add trend chart
    if hist_data:
        plot_data = _generate_financial_plot(asset_name, hist_data)
        if plot_data:
            result += f"\n\n![{asset_name} 1-Month Trend]({plot_data})"
    
    return result


def _generate_financial_plot(asset_name: str, hist_data: Dict) -> Optional[str]:
    """Generate a financial trend plot"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        import base64
        import io
        
        sns.set_style("whitegrid")
        sns.set_palette("husl")
        
        # Prepare data
        price_data = hist_data['price_data']
        dates = [datetime.fromtimestamp(d['timestamp']).strftime('%m/%d') for d in price_data]
        prices = [d['close'] for d in price_data]
        
        df = pd.DataFrame({'Date': dates, 'Price': prices})
        
        # Create plot
        plt.figure(figsize=(10, 6))
        ax = sns.lineplot(data=df, x='Date', y='Price', marker='o', linewidth=3, markersize=8)
        
        plt.title(f'{asset_name} - 1-Month Price Trend', fontsize=18, fontweight='bold', pad=25)
        plt.xlabel('Date', fontsize=16, fontweight='600')
        plt.ylabel('Price ($)', fontsize=16, fontweight='600')
        plt.xticks(fontsize=12, rotation=45)
        plt.yticks(fontsize=12)
        
        # Add price labels
        key_indices = [0, len(prices)//4, len(prices)//2, 3*len(prices)//4, -1]
        for i in key_indices:
            if i < len(prices):
                plt.annotate(f'${prices[i]:.2f}', (dates[i], prices[i]),
                           textcoords="offset points", xytext=(0, 12), ha='center', 
                           fontsize=11, fontweight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
        
        plt.grid(True, alpha=0.3, linewidth=1)
        sns.despine()
        plt.tight_layout(pad=2.0)
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        buffer.seek(0)
        
        plot_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()
        buffer.close()
        sns.reset_defaults()
        
        return f"data:image/png;base64,{plot_data}"
        
    except Exception as e:
        logger.error(f"Error generating financial plot: {e}")
        return None