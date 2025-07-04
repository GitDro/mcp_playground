"""
Financial data tools for stocks, cryptocurrency, and market data
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
    def get_stock_price(ticker: str) -> str:
        """Get real-time stock price, daily change, and market data for any stock ticker (e.g., AAPL, TSLA, NVDA) using Yahoo Finance."""
        try:
            import requests
            
            # Clean up old cache periodically
            cleanup_old_cache()
            
            # Check cache first
            cached_data = load_cached_data(ticker)
            if cached_data and 'quote' in cached_data:
                quote_data = cached_data['quote']
            else:
                # Get data using Yahoo Finance API directly
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}'
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    return f"Could not find data for ticker: {ticker}"
                
                data = response.json()
                if not data.get('chart') or not data['chart'].get('result'):
                    return f"Could not find data for ticker: {ticker}"
                
                result = data['chart']['result'][0]
                meta = result.get('meta', {})
                
                current_price = meta.get('regularMarketPrice', 0)
                prev_close = meta.get('previousClose', current_price)
                change = current_price - prev_close
                change_pct = (change / prev_close * 100) if prev_close != 0 else 0
                
                quote_data = {
                    'symbol': meta.get('symbol', ticker.upper()),
                    'current_price': current_price,
                    'change': change,
                    'change_pct': change_pct,
                    'high': meta.get('regularMarketDayHigh', current_price),
                    'low': meta.get('regularMarketDayLow', current_price),
                    'volume': meta.get('regularMarketVolume', 0)
                }
                
                # Cache the result
                save_cached_data(ticker, {'quote': quote_data})
            
            if not quote_data:
                return f"Could not find data for ticker: {ticker}"
            
            # Parse data
            symbol = quote_data.get('symbol', ticker.upper())
            current_price = float(quote_data.get('current_price', 0))
            change = float(quote_data.get('change', 0))
            change_pct = float(quote_data.get('change_pct', 0))
            
            # Plain text only - no markdown at all
            trend_symbol = "📈" if change >= 0 else "📉"
            formatted_result = f"{symbol} {trend_symbol}\n\n"
            
            # Price with simple +/- - NO MARKDOWN
            if change >= 0:
                formatted_result += f"- {current_price:.2f} USD +{change:.2f} (+{change_pct:.2f}%)\n\n"
            else:
                formatted_result += f"- {current_price:.2f} USD {change:.2f} ({change_pct:.2f}%)\n\n"
            
            # Add key metrics as simple bullet points - NO DOLLAR SIGNS
            if quote_data.get('high') and quote_data.get('low'):
                high = float(quote_data.get('high', 0))
                low = float(quote_data.get('low', 0))
                formatted_result += f"- Range: {low:.2f} to {high:.2f}\n\n"
            
            if quote_data.get('volume'):
                volume = int(quote_data.get('volume', 0))
                if volume > 1e9:
                    formatted_result += f"- Volume: {volume/1e9:.1f}B shares\n"
                elif volume > 1e6:
                    formatted_result += f"- Volume: {volume/1e6:.1f}M shares\n"
                else:
                    formatted_result += f"- Volume: {volume:,} shares\n"
            
            return formatted_result
            
        except Exception as e:
            return f"Error fetching stock data for {ticker}: {str(e)}"
    
    @mcp.tool
    def get_stock_history(ticker: str, period: str = "1mo") -> str:
        """Get historical stock price data and performance trends. Period options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max."""
        try:
            import requests
            
            cache_key = f"{ticker}_history_{period}"
            cached_data = load_cached_data(cache_key)
            
            if cached_data and 'history' in cached_data:
                hist_data = cached_data['history']
            else:
                # Map period to range parameter for Yahoo Finance
                period_map = {
                    '1d': '1d', '5d': '5d', '1mo': '1mo', '3mo': '3mo',
                    '6mo': '6mo', '1y': '1y', '2y': '2y', '5y': '5y', 
                    '10y': '10y', 'ytd': 'ytd', 'max': 'max'
                }
                range_param = period_map.get(period, '1mo')
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_param}&interval=1d'
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    return f"Could not find historical data for ticker: {ticker}"
                
                data = response.json()
                if not data.get('chart') or not data['chart'].get('result'):
                    return f"Could not find historical data for ticker: {ticker}"
                
                result = data['chart']['result'][0]
                timestamps = result.get('timestamp', [])
                indicators = result.get('indicators', {})
                quote = indicators.get('quote', [{}])[0]
                
                if not timestamps or not quote:
                    return f"Could not find historical data for ticker: {ticker}"
                
                closes = quote.get('close', [])
                opens = quote.get('open', [])
                highs = quote.get('high', [])
                lows = quote.get('low', [])
                
                # Filter out None values and get valid data
                valid_data = []
                for i, ts in enumerate(timestamps):
                    if (i < len(closes) and closes[i] is not None and
                        i < len(opens) and opens[i] is not None):
                        valid_data.append({
                            'timestamp': ts,
                            'close': closes[i],
                            'open': opens[i],
                            'high': highs[i] if i < len(highs) and highs[i] is not None else closes[i],
                            'low': lows[i] if i < len(lows) and lows[i] is not None else closes[i]
                        })
                
                if not valid_data:
                    return f"Could not find valid historical data for ticker: {ticker}"
                
                # Calculate statistics
                current_price = valid_data[-1]['close']
                start_price = valid_data[0]['close']
                high_price = max(d['high'] for d in valid_data)
                low_price = min(d['low'] for d in valid_data)
                
                hist_data = {
                    'current_price': current_price,
                    'start_price': start_price,
                    'high_price': high_price,
                    'low_price': low_price,
                    'recent_days': []
                }
                
                # Get last 3 days of data
                for i in range(min(3, len(valid_data))):
                    day_data = valid_data[-(i+1)]  # Start from most recent
                    date_str = datetime.fromtimestamp(day_data['timestamp']).strftime('%Y-%m-%d')
                    hist_data['recent_days'].append({
                        'date': date_str,
                        'close': day_data['close'],
                        'open': day_data['open']
                    })
                
                # Cache the result
                save_cached_data(cache_key, {'history': hist_data})
            
            if not hist_data:
                return f"Could not find historical data for ticker: {ticker}"
            
            # Calculate statistics
            current_price = float(hist_data['current_price'])
            start_price = float(hist_data['start_price'])
            high_price = float(hist_data['high_price'])
            low_price = float(hist_data['low_price'])
            total_return = ((current_price - start_price) / start_price) * 100
            
            # Plain text historical data formatting
            trend_symbol = "📈" if total_return >= 0 else "📉"
            formatted_result = f"{ticker.upper()} {period.upper()} {trend_symbol}\n\n"
            
            # Period return with simple +/-
            if total_return >= 0:
                formatted_result += f"- Period return: +{total_return:.2f}%\n\n"
            else:
                formatted_result += f"- Period return: {total_return:.2f}%\n\n"
                
            formatted_result += f"- Current price: {current_price:.2f} USD\n\n"
            formatted_result += f"- Period high: {high_price:.2f} USD\n\n"
            formatted_result += f"- Period low: {low_price:.2f} USD\n\n"
            
            # Recent trend with bullet points
            formatted_result += f"Recent trading days:\n\n"
            for day_data in hist_data['recent_days']:
                close_price = float(day_data['close'])
                open_price = float(day_data['open'])
                daily_change = close_price - open_price
                trend = "📈" if daily_change >= 0 else "📉"
                formatted_result += f"- {day_data['date']}: {close_price:.2f} USD {trend}\n\n"
            
            return formatted_result
            
        except Exception as e:
            return f"Error fetching historical data for {ticker}: {str(e)}"
    
    @mcp.tool
    def get_crypto_price(symbol: str) -> str:
        """Get real-time cryptocurrency price and 24h change for major coins (e.g., BTC-USD, ETH-USD, ADA-USD) using Yahoo Finance."""
        try:
            import requests
            
            # Convert symbol to Yahoo Finance format for crypto (e.g., BTC -> BTC-USD)
            if not symbol.endswith('-USD'):
                crypto_ticker = f"{symbol.upper()}-USD"
            else:
                crypto_ticker = symbol.upper()
            
            cache_key = f"{symbol}_crypto"
            cached_data = load_cached_data(cache_key)
            
            if cached_data and 'crypto' in cached_data:
                # Use cached data
                data = cached_data['crypto']
                current_price = data['price']
                change_pct = data.get('change_pct', 0)
            else:
                # Get data using Yahoo Finance API directly
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{crypto_ticker}'
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    return f"Could not find data for cryptocurrency: {symbol}"
                
                data = response.json()
                if not data.get('chart') or not data['chart'].get('result'):
                    return f"Could not find data for cryptocurrency: {symbol}"
                
                result = data['chart']['result'][0]
                meta = result.get('meta', {})
                
                current_price = meta.get('regularMarketPrice', 0)
                prev_close = meta.get('previousClose', current_price)
                change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                
                # Cache the result
                crypto_data = {'price': current_price, 'change_pct': change_pct}
                save_cached_data(cache_key, {'crypto': crypto_data})
            
            symbol_icon = "🟢" if change_pct >= 0 else "🔴"
            formatted_result = f"{symbol.upper()} {symbol_icon}\n\n"
            
            # Simple price with +/- handling - NO MARKDOWN
            if change_pct >= 0:
                formatted_result += f"- {current_price:,.2f} USD +{change_pct:.2f}%\n"
            else:
                formatted_result += f"- {current_price:,.2f} USD {change_pct:.2f}%\n"
            
            return formatted_result
            
        except Exception as e:
            return f"Error fetching crypto data for {symbol}: {str(e)}"
    
    @mcp.tool
    def get_market_summary() -> str:
        """Get current performance overview of major market indices including S&P 500, Dow Jones, NASDAQ, and other key market indicators."""
        try:
            import requests
            
            indices = {
                "S&P 500": "SPY",
                "NASDAQ": "QQQ", 
                "Dow Jones": "DIA",
                "Russell 2000": "IWM"
            }
            
            formatted_result = "Markets\n\n"
            
            for name, symbol in indices.items():
                try:
                    # Check cache first
                    cached_data = load_cached_data(f"{symbol}_market")
                    if cached_data and 'quote' in cached_data:
                        quote_data = cached_data['quote']
                    else:
                        # Get data using Yahoo Finance API directly
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                        }
                        
                        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
                        response = requests.get(url, headers=headers, timeout=10)
                        
                        if response.status_code != 200:
                            formatted_result += f"- {name}: unavailable\n\n"
                            continue
                        
                        data = response.json()
                        if not data.get('chart') or not data['chart'].get('result'):
                            formatted_result += f"- {name}: unavailable\n\n"
                            continue
                        
                        result = data['chart']['result'][0]
                        meta = result.get('meta', {})
                        
                        current_price = meta.get('regularMarketPrice', 0)
                        prev_close = meta.get('previousClose', current_price)
                        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                        
                        quote_data = {
                            'current_price': current_price,
                            'change_pct': change_pct
                        }
                        
                        # Cache the result
                        save_cached_data(f"{symbol}_market", {'quote': quote_data})
                    
                    if quote_data:
                        current_price = float(quote_data.get('current_price', 0))
                        change_pct = float(quote_data.get('change_pct', 0))
                        
                        trend = "📈" if change_pct >= 0 else "📉"
                        if change_pct >= 0:
                            formatted_result += f"- {name}: {current_price:.2f} USD +{change_pct:.2f}% {trend}\n\n"
                        else:
                            formatted_result += f"- {name}: {current_price:.2f} USD {change_pct:.2f}% {trend}\n\n"
                    else:
                        formatted_result += f"- {name}: unavailable\n\n"
                        
                except Exception as e:
                    formatted_result += f"- {name}: error\n\n"
            
            return formatted_result
            
        except Exception as e:
            return f"Error fetching market summary: {str(e)}"