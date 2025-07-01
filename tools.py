"""
Function calling tools for MCP Playground

This module contains all the tool functions and their schemas for the
Ollama function calling system.
"""

from typing import List, Dict, Optional, Tuple
from duckduckgo_search import DDGS
import httpx
import re
import tempfile
import os
import json
import requests
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUTS
# ============================================================================

class SectionAnalysis(BaseModel):
    """Analysis of a single paper section"""
    bullet_points: List[str] = Field(
        description="2-3 concise bullet points with key insights",
        min_length=1,
        max_length=3
    )

class PaperAnalysis(BaseModel):
    """Complete structured analysis of a research paper"""
    introduction: Optional[SectionAnalysis] = Field(
        default=None,
        description="Main problem, key contribution, and novelty"
    )
    methods: Optional[SectionAnalysis] = Field(
        default=None,
        description="Novel techniques, innovations, and unique aspects"
    )
    results: Optional[SectionAnalysis] = Field(
        default=None,
        description="Performance improvements, comparisons, and metrics"
    )
    discussion: Optional[SectionAnalysis] = Field(
        default=None,
        description="Conclusions, limitations, and future work"
    )


# ============================================================================
# TOOL FUNCTIONS
# ============================================================================

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo"""
    try:
        # Ensure max_results is an integer (in case it comes as string from JSON)
        if isinstance(max_results, str):
            max_results = int(max_results)
        max_results = max(1, min(max_results or 5, 10))  # Clamp between 1 and 10
        
        # Validate query
        if not query or not query.strip():
            return "Error: Search query cannot be empty"
        
        query = query.strip()
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"No search results found for: {query}"
        
        # Format results as markdown
        formatted_results = f"#### Search Results for: {query}\n\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"**{i}. {result.get('title', 'No Title')}**\n"
            formatted_results += f"**URL**: {result.get('href', 'No URL')}\n"
            formatted_results += f"**Summary**: {result.get('body', 'No description available')}\n\n"
            formatted_results += "---\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Error performing search: {str(e)}"


def analyze_url(url: str) -> str:
    """Analyze a URL and return basic info"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content)
            
            summary = f"# URL Analysis\n\n"
            summary += f"**URL**: {url}\n"
            summary += f"**Content Type**: {content_type}\n"
            summary += f"**Content Length**: {content_length:,} bytes\n\n"
            
            if 'text/html' in content_type:
                # Basic text extraction for web pages
                text_content = response.text[:1000]  # First 1000 chars
                summary += f"**Preview**: {text_content}...\n"
            else:
                summary += f"**Note**: Non-HTML content detected.\n"
            
            return summary
            
    except Exception as e:
        return f"Error analyzing URL: {str(e)}"


def _enhance_arxiv_query(query: str) -> str:
    """Enhance search query for better arXiv results"""
    original_query = query.strip()
    query = query.lower().strip()
    
    # If query already has field specifiers, use as-is
    if any(field in query for field in ['ti:', 'abs:', 'au:', 'cat:']):
        return query
    
    # If query is very long (like paper titles), use as-is but quoted
    if len(query.split()) > 6:
        return f'"{original_query}"'
    
    # For 3+ word queries, treat as phrase in title, or individual words in abstract
    if len(query.split()) >= 3:
        return f'ti:"{original_query}" OR abs:{query}'
    
    # For 1-2 word queries, search in both title and abstract
    return f"ti:{query} OR abs:{query}"


def _filter_relevant_papers(results, original_query: str, max_results: int):
    """Filter papers for relevance to the original query"""
    if not results:
        return []
    
    # Simple relevance scoring based on keyword presence
    query_words = set(original_query.lower().split())
    scored_results = []
    
    for paper in results:
        score = 0
        title_words = set(paper.title.lower().split())
        abstract_words = set(paper.summary.lower().split())
        
        # Score based on keyword matches in title (higher weight) and abstract
        title_matches = len(query_words.intersection(title_words))
        abstract_matches = len(query_words.intersection(abstract_words))
        
        score = title_matches * 3 + abstract_matches
        
        # Boost score for papers in relevant categories
        relevant_categories = ['cs.LG', 'cs.AI', 'cs.CV', 'cs.CL', 'stat.ML', 'cs.IR']
        if any(cat in paper.categories for cat in relevant_categories):
            score += 1
            
        scored_results.append((score, paper))
    
    # Sort by score and return top results
    scored_results.sort(key=lambda x: x[0], reverse=True)
    return [paper for score, paper in scored_results[:max_results] if score > 0]


def extract_paper_content(pdf_url: str) -> Optional[PaperAnalysis]:
    """Extract structured content from arXiv PDF using LLM analysis"""
    try:
        import fitz  # PyMuPDF
        
        # Download PDF to temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            response = httpx.get(pdf_url, timeout=30)
            response.raise_for_status()
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        try:
            # Extract text from PDF
            doc = fitz.open(tmp_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()
            
            # Analyze with structured LLM output
            analysis = _analyze_paper_with_structured_output(full_text)
            return analysis
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        print(f"Error extracting paper content: {e}")
        return None


def _analyze_paper_with_structured_output(full_text: str) -> Optional[PaperAnalysis]:
    """Use Ollama structured output to analyze a research paper"""
    try:
        from ollama import chat
        
        # Limit text length to avoid overwhelming the LLM
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "..."
        
        # Create comprehensive prompt for paper analysis
        prompt = f"""Analyze this research paper and extract key insights for each section.

For each section that exists in the paper, provide 2-3 concise bullet points:

Introduction: Focus on the main problem/gap, key contribution, and novelty
Methods: Focus on novel techniques, key innovations, and unique aspects  
Results: Focus on performance improvements, comparisons, and significant findings
Discussion: Focus on conclusions, limitations, and future work (be sure to include limitations)

Paper text:
{full_text}"""

        # Use structured output with Pydantic schema
        response = chat(
            messages=[{
                'role': 'user',
                'content': prompt,
            }],
            model='llama3.2',  # Use available model
            format=PaperAnalysis.model_json_schema(),
            options={
                'temperature': 0.2,  # Lower temperature for consistency
                'num_predict': 800   # Enough tokens for structured response
            }
        )
        
        # Parse and validate the structured response
        analysis = PaperAnalysis.model_validate_json(response.message.content)
        return analysis
        
    except Exception as e:
        print(f"Error in structured LLM analysis: {e}")
        return None






def _clean_markdown_text(text: str) -> str:
    """Clean text to prevent overly long sections and problematic headers"""
    if not text:
        return text
    
    # Remove any header markers that could interfere with layout
    text = text.replace('####', '').replace('###', '').replace('##', '').replace('#', '')
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Limit length to prevent overly long sections
    if len(text) > 500:
        text = text[:497] + "..."
    
    return text


def arxiv_search(query: str, max_results: int = 3) -> str:
    """Search arXiv for academic papers"""
    try:
        import arxiv
        
        # Validate and sanitize inputs
        if isinstance(max_results, str):
            max_results = int(max_results)
        max_results = max(1, min(max_results or 5, 10))
        
        if not query or not query.strip():
            return "Error: Search query cannot be empty"
        
        query = query.strip()
        
        # Enhanced query processing for better relevance
        enhanced_query = _enhance_arxiv_query(query)
        
        # Create client and search - sort by RELEVANCE for better results
        client = arxiv.Client()
        search = arxiv.Search(
            query=enhanced_query,
            max_results=max_results * 2,  # Get more results to filter
            sort_by=arxiv.SortCriterion.Relevance  # Changed from SubmittedDate
        )
        
        results = list(client.results(search))
        
        # Filter results for better relevance
        filtered_results = _filter_relevant_papers(results, query, max_results)
        
        if not filtered_results:
            return f"No relevant papers found for: {query}. Try different keywords or be more specific."
        
        # Format results as markdown with enhanced analysis for top papers
        formatted_results = f"### arXiv Papers for: {query}\n\n"
        
        for i, result in enumerate(filtered_results, 1):
            # Truncate abstract for readability
            abstract = result.summary.replace('\n', ' ').strip()
            if len(abstract) > 250:
                abstract = abstract[:247] + "..."
            
            # Ensure each paper starts fresh with proper formatting and clean markdown reset
            if i > 1:
                formatted_results += "\n\n"  # Extra spacing between papers
            formatted_results += f"**{i}. {result.title}**\n"
            formatted_results += f"**Authors**: {', '.join([author.name for author in result.authors[:3]])}"
            if len(result.authors) > 3:
                formatted_results += f" (and {len(result.authors) - 3} others)"
            formatted_results += "\n"
            formatted_results += f"**Published**: {result.published.strftime('%Y-%m-%d')}\n"
            formatted_results += f"**arXiv ID**: {result.entry_id.split('/')[-1]}\n"
            formatted_results += f"**Categories**: {', '.join(result.categories[:2])}\n"
            formatted_results += f"**Abstract**: {abstract}\n"
            formatted_results += f"**PDF**: {result.pdf_url}\n"
            
            # Deep analysis for top 1 paper only
            if i <= 1:
                formatted_results += "\n**📄 Deep Analysis:**\n"
                paper_content = extract_paper_content(result.pdf_url)
                
                if paper_content:
                    # Introduction/Background
                    if paper_content.introduction and paper_content.introduction.bullet_points:
                        formatted_results += "\n**Introduction:**\n\n"
                        for point in paper_content.introduction.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"• {clean_point}\n\n"
                        formatted_results += "\n"
                    
                    # Methods/Approach
                    if paper_content.methods and paper_content.methods.bullet_points:
                        formatted_results += "\n**Methods:**\n\n"
                        for point in paper_content.methods.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"• {clean_point}\n\n"
                        formatted_results += "\n"
                    
                    # Results
                    if paper_content.results and paper_content.results.bullet_points:
                        formatted_results += "\n**Results:**\n\n"
                        for point in paper_content.results.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"• {clean_point}\n\n"
                        formatted_results += "\n"
                    
                    # Discussion/Limitations
                    if paper_content.discussion and paper_content.discussion.bullet_points:
                        formatted_results += "\n**Discussion:**\n\n"
                        for point in paper_content.discussion.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"• {clean_point}\n\n"
                        formatted_results += "\n"
                else:
                    formatted_results += "*PDF analysis unavailable - using abstract only.*\n\n"
            
            # Add separator with proper spacing to prevent markdown bleeding
            formatted_results += "\n---\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"


# ============================================================================
# FINANCIAL DATA FUNCTIONS - ALPHA VANTAGE WITH CACHING
# ============================================================================

# Alpha Vantage configuration
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
CACHE_DIR = os.getenv('CACHE_DIRECTORY', 'cache')
MAX_CACHE_DAYS = int(os.getenv('MAX_CACHE_DAYS', '7'))

def _get_cache_file_path(ticker: str, date_str: str = None) -> str:
    """Get the cache file path for a ticker on a specific date"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    cache_date_dir = os.path.join(CACHE_DIR, date_str)
    os.makedirs(cache_date_dir, exist_ok=True)
    return os.path.join(cache_date_dir, f"{ticker.upper()}.json")

def _load_cached_data(ticker: str) -> Optional[Dict]:
    """Load cached stock data for today if it exists"""
    try:
        cache_file = _get_cache_file_path(ticker)
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                data = json.load(f)
                # Check if data is from today
                if data.get('date') == datetime.now().strftime('%Y-%m-%d'):
                    return data
        return None
    except Exception:
        return None

def _save_cached_data(ticker: str, data: Dict) -> None:
    """Save stock data to cache"""
    try:
        data['date'] = datetime.now().strftime('%Y-%m-%d')
        data['cached_at'] = datetime.now().isoformat()
        
        cache_file = _get_cache_file_path(ticker)
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to cache data for {ticker}: {e}")

def _cleanup_old_cache() -> None:
    """Remove cache directories older than MAX_CACHE_DAYS"""
    try:
        if not os.path.exists(CACHE_DIR):
            return
            
        cutoff_date = datetime.now() - timedelta(days=MAX_CACHE_DAYS)
        
        for item in os.listdir(CACHE_DIR):
            item_path = os.path.join(CACHE_DIR, item)
            if os.path.isdir(item_path):
                try:
                    # Check if directory name is a date
                    dir_date = datetime.strptime(item, '%Y-%m-%d')
                    if dir_date < cutoff_date:
                        import shutil
                        shutil.rmtree(item_path)
                        print(f"Cleaned up old cache directory: {item}")
                except ValueError:
                    # Not a date directory, skip
                    continue
    except Exception as e:
        print(f"Warning: Cache cleanup failed: {e}")

def _make_alpha_vantage_request(function: str, symbol: str, **kwargs) -> Optional[Dict]:
    """Make a request to Alpha Vantage API"""
    if not ALPHA_VANTAGE_API_KEY:
        raise ValueError("Alpha Vantage API key not found. Please set ALPHA_VANTAGE_API_KEY in .env file.")
    
    try:
        params = {
            'function': function,
            'symbol': symbol,
            'apikey': ALPHA_VANTAGE_API_KEY,
            **kwargs
        }
        
        response = requests.get(
            'https://www.alphavantage.co/query',
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Check for API errors
        if 'Error Message' in data:
            raise ValueError(f"Alpha Vantage API Error: {data['Error Message']}")
        if 'Note' in data:
            raise ValueError(f"Alpha Vantage API Note: {data['Note']}")
            
        return data
        
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Network error: {str(e)}")

def get_stock_price(ticker: str) -> str:
    """Get current stock price and basic information using Alpha Vantage"""
    try:
        # Clean up old cache periodically
        _cleanup_old_cache()
        
        # Check cache first
        cached_data = _load_cached_data(ticker)
        if cached_data and 'quote' in cached_data:
            quote_data = cached_data['quote']
        else:
            # Make API request
            data = _make_alpha_vantage_request('GLOBAL_QUOTE', ticker)
            quote_data = data.get('Global Quote', {})
            
            # Cache the result
            _save_cached_data(ticker, {'quote': quote_data})
        
        if not quote_data:
            return f"Could not find data for ticker: {ticker}"
        
        # Parse Alpha Vantage response
        symbol = quote_data.get('01. symbol', ticker.upper())
        current_price = float(quote_data.get('05. price', 0))
        prev_close = float(quote_data.get('08. previous close', 0))
        change = float(quote_data.get('09. change', 0))
        change_pct = float(quote_data.get('10. change percent', '0%').replace('%', ''))
        
        # Ultra simple formatting - no special characters
        trend_symbol = "📈" if change >= 0 else "📉"
        formatted_result = f"**{symbol}** {trend_symbol}\n\n"
        
        # Price with simple +/- 
        if change >= 0:
            formatted_result += f"• **${current_price:.2f}** +{change:.2f} (+{change_pct:.2f}%)\n"
        else:
            formatted_result += f"• **${current_price:.2f}** {change:.2f} ({change_pct:.2f}%)\n"
        
        # Add key metrics as simple bullet points
        if quote_data.get('03. high'):
            high = float(quote_data.get('03. high', 0))
            low = float(quote_data.get('04. low', 0))
            formatted_result += f"• Range: ${low:.2f} to ${high:.2f}\n"
        
        if quote_data.get('06. volume'):
            volume = int(quote_data.get('06. volume', 0))
            if volume > 1e9:
                formatted_result += f"• Volume: {volume/1e9:.1f}B shares\n"
            elif volume > 1e6:
                formatted_result += f"• Volume: {volume/1e6:.1f}M shares\n"
            else:
                formatted_result += f"• Volume: {volume:,} shares\n"
        
        return formatted_result
        
    except Exception as e:
        if "API" in str(e) or "rate limit" in str(e).lower():
            return f"Unable to fetch stock data for {ticker}: {str(e)}"
        return f"Error fetching stock data for {ticker}: {str(e)}"

def get_stock_history(ticker: str, period: str = "1mo") -> str:
    """Get historical stock price data using Alpha Vantage"""
    try:
        # For historical data, we'll use TIME_SERIES_DAILY
        # Note: Alpha Vantage free tier gives last 100 data points for daily
        
        cache_key = f"{ticker}_history"
        cached_data = _load_cached_data(cache_key)
        
        if cached_data and 'history' in cached_data:
            time_series = cached_data['history']
        else:
            # Make API request for daily data
            data = _make_alpha_vantage_request('TIME_SERIES_DAILY', ticker, outputsize='compact')
            time_series = data.get('Time Series (Daily)', {})
            
            # Cache the result
            _save_cached_data(cache_key, {'history': time_series})
        
        if not time_series:
            return f"Could not find historical data for ticker: {ticker}"
        
        # Convert to list of dates and sort
        dates = sorted(time_series.keys(), reverse=True)
        
        # Calculate period-specific data
        period_days = {
            '1d': 1, '5d': 5, '1mo': 22, '3mo': 66, 
            '6mo': 132, '1y': 252, 'ytd': None
        }
        
        days = period_days.get(period, 22)  # Default to 1 month
        if days:
            recent_dates = dates[:days]
        else:
            # YTD calculation
            current_year = datetime.now().year
            recent_dates = [d for d in dates if d.startswith(str(current_year))]
        
        if not recent_dates:
            return f"Insufficient historical data for {ticker}"
        
        # Get current and start prices
        current_data = time_series[recent_dates[0]]
        start_data = time_series[recent_dates[-1]]
        
        current_price = float(current_data['4. close'])
        start_price = float(start_data['4. close'])
        
        # Calculate statistics
        high_price = max(float(time_series[d]['2. high']) for d in recent_dates)
        low_price = min(float(time_series[d]['3. low']) for d in recent_dates)
        total_return = ((current_price - start_price) / start_price) * 100
        
        # Ultra simple historical data formatting
        trend_symbol = "📈" if total_return >= 0 else "📉"
        formatted_result = f"**{ticker.upper()} {period.upper()}** {trend_symbol}\n\n"
        
        # Period return with simple +/-
        if total_return >= 0:
            formatted_result += f"• Period return: **+{total_return:.2f}%**\n"
        else:
            formatted_result += f"• Period return: **{total_return:.2f}%**\n"
            
        formatted_result += f"• Current price: ${current_price:.2f}\n"
        formatted_result += f"• Period high: ${high_price:.2f}\n"
        formatted_result += f"• Period low: ${low_price:.2f}\n\n"
        
        # Recent trend with bullet points
        formatted_result += f"**Recent trading days:**\n"
        for date in recent_dates[:3]:
            day_data = time_series[date]
            close_price = float(day_data['4. close'])
            open_price = float(day_data['1. open'])
            daily_change = close_price - open_price
            trend = "📈" if daily_change >= 0 else "📉"
            formatted_result += f"• {date}: ${close_price:.2f} {trend}\n"
        
        return formatted_result
        
    except Exception as e:
        if "API" in str(e) or "rate limit" in str(e).lower():
            return f"Unable to fetch historical data for {ticker}: {str(e)}"
        return f"Error fetching historical data for {ticker}: {str(e)}"

def get_crypto_price(symbol: str) -> str:
    """Get current cryptocurrency price using Alpha Vantage"""
    try:
        # Alpha Vantage uses different function for crypto
        cache_key = f"{symbol}_crypto"
        cached_data = _load_cached_data(cache_key)
        
        if cached_data and 'crypto' in cached_data:
            # Use cached data
            data = cached_data['crypto']
            current_price = data['price']
            change_pct = data.get('change_pct', 0)
        else:
            # Make API request for crypto
            data = _make_alpha_vantage_request('DIGITAL_CURRENCY_DAILY', symbol, market='USD')
            time_series = data.get('Time Series (Digital Currency Daily)', {})
            
            if not time_series:
                return f"Could not find data for cryptocurrency: {symbol}"
            
            # Get most recent date
            recent_date = max(time_series.keys())
            recent_data = time_series[recent_date]
            
            current_price = float(recent_data['4. close'])
            
            # Try to calculate change (if we have previous day)
            dates = sorted(time_series.keys(), reverse=True)
            if len(dates) > 1:
                prev_data = time_series[dates[1]]
                prev_price = float(prev_data['4. close'])
                change_pct = ((current_price - prev_price) / prev_price) * 100
            else:
                change_pct = 0
            
            # Cache the result
            crypto_data = {'price': current_price, 'change_pct': change_pct}
            _save_cached_data(cache_key, {'crypto': crypto_data})
        
        symbol_icon = "🟢" if change_pct >= 0 else "🔴"
        formatted_result = f"**{symbol.upper()}** {symbol_icon}\n\n"
        
        # Simple price with +/- handling
        if change_pct >= 0:
            formatted_result += f"• **${current_price:,.2f}** +{change_pct:.2f}%\n"
        else:
            formatted_result += f"• **${current_price:,.2f}** {change_pct:.2f}%\n"
        
        return formatted_result
        
    except Exception as e:
        if "API" in str(e) or "rate limit" in str(e).lower():
            return f"Unable to fetch crypto data for {symbol}: {str(e)}"
        return f"Error fetching crypto data for {symbol}: {str(e)}"

def get_market_summary() -> str:
    """Get summary of major market indices using Alpha Vantage"""
    try:
        indices = {
            "S&P 500": "SPY",  # Using ETF tickers for better Alpha Vantage support
            "NASDAQ": "QQQ",
            "Dow Jones": "DIA",
            "Russell 2000": "IWM"
        }
        
        formatted_result = "**Markets**\n\n"
        
        for name, symbol in indices.items():
            try:
                # Check cache first
                cached_data = _load_cached_data(f"{symbol}_market")
                if cached_data and 'quote' in cached_data:
                    quote_data = cached_data['quote']
                else:
                    # Make API request
                    data = _make_alpha_vantage_request('GLOBAL_QUOTE', symbol)
                    quote_data = data.get('Global Quote', {})
                    
                    # Cache the result
                    _save_cached_data(f"{symbol}_market", {'quote': quote_data})
                
                if quote_data:
                    current_price = float(quote_data.get('05. price', 0))
                    change_pct = float(quote_data.get('10. change percent', '0%').replace('%', ''))
                    
                    trend = "📈" if change_pct >= 0 else "📉"
                    if change_pct >= 0:
                        formatted_result += f"• {name}: ${current_price:.2f} +{change_pct:.2f}% {trend}\n"
                    else:
                        formatted_result += f"• {name}: ${current_price:.2f} {change_pct:.2f}% {trend}\n"
                else:
                    formatted_result += f"• {name}: unavailable\n"
                    
            except Exception as e:
                formatted_result += f"• {name}: error\n"
        
        return formatted_result
        
    except Exception as e:
        if "API" in str(e) or "rate limit" in str(e).lower():
            return f"Unable to fetch market data: {str(e)}"
        return f"Error fetching market summary: {str(e)}"


def get_function_schema() -> List[Dict]:
    """
    Define available functions for Ollama function calling.
    
    Returns:
        List of function schemas in OpenAI format
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "RESTRICTED: Only use when user EXPLICITLY asks for current/recent/latest information with keywords like 'search', 'find', 'latest', 'current', 'recent', 'today', 'now'. Never use for general questions or explanations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for time-sensitive information explicitly requested by user"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5)"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_url",
                "description": "RESTRICTED: Only use when user explicitly provides a URL/link and asks to analyze it. Never use unless user specifically mentions a URL to analyze.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The specific URL provided by user to analyze"
                        }
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "arxiv_search",
                "description": "RESTRICTED: Only use when user explicitly asks to search for academic papers, research, or scientific literature with keywords like 'papers', 'research', 'arxiv', 'academic', 'study'. Never use for general questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Academic search query for finding research papers"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of papers to return (default: 3)"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "RESTRICTED: Only use when user explicitly asks for stock prices, stock information, or financial data for specific companies with keywords like 'stock price', 'share price', 'ticker', company names, or stock symbols.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., AAPL, MSFT, TSLA)"
                        }
                    },
                    "required": ["ticker"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_stock_history",
                "description": "RESTRICTED: Only use when user explicitly asks for historical stock data, price trends, or performance over time with keywords like 'historical', 'trend', 'performance', 'chart'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., AAPL, MSFT, TSLA)"
                        },
                        "period": {
                            "type": "string",
                            "description": "Time period for historical data (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)"
                        }
                    },
                    "required": ["ticker"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_crypto_price",
                "description": "RESTRICTED: Only use when user explicitly asks for cryptocurrency prices or crypto information with keywords like 'crypto', 'bitcoin', 'ethereum', 'cryptocurrency'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Cryptocurrency symbol (e.g., BTC, ETH, ADA, DOGE)"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_market_summary",
                "description": "RESTRICTED: Only use when user explicitly asks for market overview, market summary, or general market performance with keywords like 'market', 'indices', 'dow', 'nasdaq', 's&p'.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]


def execute_function(function_name: str, arguments: dict) -> str:
    """Execute a function call with proper type conversion"""
    try:
        if function_name == "web_search":
            query = str(arguments.get("query", ""))
            max_results = arguments.get("max_results", 5)
            # Convert max_results to int if it's a string
            if isinstance(max_results, str):
                max_results = int(max_results)
            return web_search(query, max_results)
        elif function_name == "analyze_url":
            url = str(arguments.get("url", ""))
            return analyze_url(url)
        elif function_name == "arxiv_search":
            query = str(arguments.get("query", ""))
            max_results = arguments.get("max_results", 3)
            # Convert max_results to int if it's a string
            if isinstance(max_results, str):
                max_results = int(max_results)
            return arxiv_search(query, max_results)
        elif function_name == "get_stock_price":
            ticker = str(arguments.get("ticker", ""))
            return get_stock_price(ticker)
        elif function_name == "get_stock_history":
            ticker = str(arguments.get("ticker", ""))
            period = str(arguments.get("period", "1mo"))
            return get_stock_history(ticker, period)
        elif function_name == "get_crypto_price":
            symbol = str(arguments.get("symbol", ""))
            return get_crypto_price(symbol)
        elif function_name == "get_market_summary":
            return get_market_summary()
        else:
            return f"Unknown function: {function_name}"
    except Exception as e:
        return f"Error executing {function_name}: {str(e)}"