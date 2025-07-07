"""
Consolidated financial data tool for stocks, cryptocurrency, and market data
"""

import logging
from typing import Dict
from datetime import datetime

from fastmcp import FastMCP
from ..core.cache import load_cached_data, save_cached_data, cleanup_old_cache

logger = logging.getLogger(__name__)


def register_financial_tools(mcp: FastMCP):
    """Register financial-related tools with the MCP server"""
    
    @mcp.tool
    def get_financial_data(symbol: str) -> str:
        """Get comprehensive financial data for any asset - stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA), crypto (BTC, ETH), or market indices (SPY, QQQ). Shows current price, daily change, volume, 1-month performance, and trend visualization."""
        try:
            import requests
            import matplotlib.pyplot as plt
            import pandas as pd
            import base64
            import io
            
            # Clean up old cache periodically
            cleanup_old_cache()
            
            # Auto-detect asset type and format symbol
            original_symbol = symbol
            if symbol.upper() in ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'LTC', 'XRP', 'DOGE', 'MATIC', 'SOL']:
                # Crypto - format for Yahoo Finance
                formatted_symbol = f"{symbol.upper()}-USD"
                asset_type = "crypto"
            else:
                # Stock or ETF
                formatted_symbol = symbol.upper()
                asset_type = "stock"
            
            # Get current data
            cache_key = f"{formatted_symbol}_current"
            cached_data = load_cached_data(cache_key)
            
            if cached_data and 'quote' in cached_data:
                quote_data = cached_data['quote']
            else:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{formatted_symbol}'
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    return f"❌ Could not find data for symbol: {original_symbol}"
                
                data = response.json()
                if not data.get('chart') or not data['chart'].get('result'):
                    return f"❌ Could not find data for symbol: {original_symbol}"
                
                result = data['chart']['result'][0]
                meta = result.get('meta', {})
                
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
            
            # Get 1-month historical data
            hist_cache_key = f"{formatted_symbol}_history_1mo"
            cached_hist = load_cached_data(hist_cache_key)
            
            if cached_hist and 'history' in cached_hist:
                hist_data = cached_hist['history']
            else:
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{formatted_symbol}?range=1mo&interval=1d'
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('chart') and data['chart'].get('result'):
                        result = data['chart']['result'][0]
                        timestamps = result.get('timestamp', [])
                        indicators = result.get('indicators', {})
                        quote = indicators.get('quote', [{}])[0]
                        
                        if timestamps and quote:
                            closes = quote.get('close', [])
                            valid_data = []
                            
                            for i, ts in enumerate(timestamps):
                                if i < len(closes) and closes[i] is not None:
                                    valid_data.append({
                                        'timestamp': ts,
                                        'close': closes[i]
                                    })
                            
                            if valid_data:
                                hist_data = {
                                    'current_price': valid_data[-1]['close'],
                                    'start_price': valid_data[0]['close'],
                                    'high_price': max(d['close'] for d in valid_data),
                                    'low_price': min(d['close'] for d in valid_data),
                                    'price_data': valid_data
                                }
                                
                                save_cached_data(hist_cache_key, {'history': hist_data})
                            else:
                                hist_data = None
                        else:
                            hist_data = None
                    else:
                        hist_data = None
                else:
                    hist_data = None
            
            # Format the comprehensive response
            symbol_display = quote_data.get('symbol', original_symbol.upper())
            current_price = float(quote_data.get('current_price', 0))
            change = float(quote_data.get('change', 0))
            change_pct = float(quote_data.get('change_pct', 0))
            
            # Determine asset name for display
            if asset_type == "crypto":
                asset_name = f"{original_symbol.upper()} (Cryptocurrency)"
            else:
                asset_name = symbol_display
            
            # Create markdown table
            trend_emoji = "📈" if change >= 0 else "📉"
            result_text = f"### **{asset_name} - Financial Overview**\n\n"
            result_text += "| **Metric** | **Value** |\n"
            result_text += "|------------|-----------|\n"
            
            # Current price with change
            if change >= 0:
                price_display = f"**${current_price:,.2f}** {trend_emoji} +${change:.2f} (+{change_pct:.2f}%)"
            else:
                price_display = f"**${current_price:,.2f}** {trend_emoji} ${change:.2f} ({change_pct:.2f}%)"
            result_text += f"| **Current Price** | {price_display} |\n"
            
            # Day range
            if quote_data.get('high') and quote_data.get('low'):
                high = float(quote_data.get('high', 0))
                low = float(quote_data.get('low', 0))
                result_text += f"| **Day Range** | ${low:,.2f} - ${high:,.2f} |\n"
            
            # Volume
            if quote_data.get('volume') and asset_type != "crypto":
                volume = int(quote_data.get('volume', 0))
                if volume > 1e9:
                    volume_display = f"{volume/1e9:.1f}B shares"
                elif volume > 1e6:
                    volume_display = f"{volume/1e6:.1f}M shares"
                else:
                    volume_display = f"{volume:,} shares"
                result_text += f"| **Volume** | {volume_display} |\n"
            
            # 1-month performance
            if hist_data:
                hist_current = float(hist_data['current_price'])
                hist_start = float(hist_data['start_price'])
                hist_high = float(hist_data['high_price'])
                hist_low = float(hist_data['low_price'])
                
                month_return = ((hist_current - hist_start) / hist_start) * 100
                month_emoji = "📈" if month_return >= 0 else "📉"
                
                if month_return >= 0:
                    return_display = f"+{month_return:.2f}% {month_emoji}"
                else:
                    return_display = f"{month_return:.2f}% {month_emoji}"
                
                result_text += f"| **1-Month Return** | {return_display} |\n"
                result_text += f"| **Month High** | ${hist_high:,.2f} |\n"
                result_text += f"| **Month Low** | ${hist_low:,.2f} |\n"
                
                # Generate trend chart
                plot_data = _generate_financial_plot(asset_name, hist_data)
                if plot_data:
                    result_text += f"\n\n![{asset_name} 1-Month Trend]({plot_data})"
            
            return result_text
            
        except Exception as e:
            logger.error(f"Error getting financial data for {symbol}: {e}")
            return f"❌ Error retrieving financial data for {symbol}: {str(e)}"


def _generate_financial_plot(asset_name: str, hist_data: Dict) -> str:
    """Generate a financial trend plot similar to crime.py"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        import base64
        import io
        
        # Set seaborn style for clean look
        sns.set_style("whitegrid")
        sns.set_palette("husl")
        
        # Prepare data
        price_data = hist_data['price_data']
        dates = [datetime.fromtimestamp(d['timestamp']).strftime('%m/%d') for d in price_data]
        prices = [d['close'] for d in price_data]
        
        df = pd.DataFrame({'Date': dates, 'Price': prices})
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Create line plot
        ax = sns.lineplot(data=df, x='Date', y='Price', 
                         marker='o', linewidth=3, markersize=8)
        
        # Enhance for visibility
        plt.title(f'{asset_name} - 1-Month Price Trend', 
                 fontsize=18, fontweight='bold', pad=25)
        plt.xlabel('Date', fontsize=16, fontweight='600')
        plt.ylabel('Price ($)', fontsize=16, fontweight='600')
        
        # Larger tick labels
        plt.xticks(fontsize=12, rotation=45)
        plt.yticks(fontsize=12)
        
        # Add price labels on key points (first, last, and a few middle points)
        key_indices = [0, len(prices)//4, len(prices)//2, 3*len(prices)//4, -1]
        for i in key_indices:
            if i < len(prices):
                plt.annotate(f'${prices[i]:.2f}', 
                           (dates[i], prices[i]),
                           textcoords="offset points", 
                           xytext=(0, 12), 
                           ha='center', 
                           fontsize=11, 
                           fontweight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", 
                                   facecolor='white', 
                                   alpha=0.8))
        
        # Grid and styling
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