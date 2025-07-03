"""
FastMCP Server for MCP Playground

This module contains all the tool functions converted to FastMCP format.
The server provides web search, URL analysis, arXiv search, financial data,
and YouTube analysis capabilities.
"""

import os
import json
import tempfile
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastMCP server
mcp = FastMCP(name="MCPPlaygroundServer")

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
# HELPER FUNCTIONS AND UTILITIES
# ============================================================================

# Financial data cache configuration
def _get_cache_directory() -> str:
    """Get writable cache directory, falling back to temp if needed"""
    cache_dir = os.getenv('CACHE_DIRECTORY')
    if not cache_dir:
        # Try user cache directory first
        cache_dir = os.path.expanduser('~/.cache/mcp_playground')
    
    try:
        os.makedirs(cache_dir, exist_ok=True)
        # Test if directory is writable
        test_file = os.path.join(cache_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return cache_dir
    except (OSError, PermissionError):
        # Fallback to temp directory
        import tempfile
        return tempfile.gettempdir()

CACHE_DIR = _get_cache_directory()
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
        logger.warning(f"Failed to cache data for {ticker}: {e}")

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
                        logger.info(f"Cleaned up old cache directory: {item}")
                except ValueError:
                    # Not a date directory, skip
                    continue
    except Exception as e:
        logger.warning(f"Cache cleanup failed: {e}")

# ============================================================================
# FASTMCP TOOLS - WEB SEARCH AND URL ANALYSIS
# ============================================================================

@mcp.tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo for current information"""
    try:
        from duckduckgo_search import DDGS
        
        # Ensure max_results is an integer and within bounds
        max_results = max(1, min(max_results or 5, 10))
        
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

@mcp.tool
def analyze_url(url: str) -> str:
    """Analyze a URL and return basic information about the webpage"""
    try:
        import httpx
        
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

# ============================================================================
# FASTMCP TOOLS - ARXIV SEARCH AND ACADEMIC PAPERS
# ============================================================================

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

def _extract_paper_content(pdf_url: str) -> Optional[PaperAnalysis]:
    """Extract structured content from arXiv PDF using LLM analysis"""
    try:
        import fitz  # PyMuPDF
        import httpx
        logger.info(f"Starting PDF analysis for {pdf_url}")
        
        # Download PDF to temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            response = httpx.get(pdf_url, timeout=30)
            response.raise_for_status()
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
            logger.info(f"PDF downloaded, size: {len(response.content)} bytes")
        
        try:
            # Extract text from PDF
            doc = fitz.open(tmp_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()
            logger.info(f"Extracted {len(full_text)} characters of text")
            
            if len(full_text.strip()) < 100:
                logger.warning(f"Very little text extracted from PDF")
                return None
            
            # Analyze with structured LLM output
            analysis = _analyze_paper_with_structured_output(full_text)
            if analysis:
                logger.info("LLM analysis completed successfully")
            else:
                logger.warning("LLM analysis returned None")
            return analysis
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Error extracting paper content: {e}")
        return None

def _analyze_paper_with_structured_output(full_text: str) -> Optional[PaperAnalysis]:
    """Use Ollama structured output to analyze a research paper"""
    try:
        from ollama import chat
        
        # Limit text length to avoid overwhelming the LLM
        original_length = len(full_text)
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "..."
            logger.info(f"Truncated text from {original_length} to {len(full_text)} chars")
        
        # Create comprehensive prompt for paper analysis
        prompt = f"""You must analyze this research paper and provide structured insights in JSON format.

Examine the paper text and provide analysis for these sections (include ALL sections that apply):

1. Introduction: What is the main problem/gap? What is the key contribution? What makes this novel?
2. Methods: What novel techniques are used? What are the key innovations? What unique approaches?
3. Results: What performance improvements are shown? What comparisons are made? What significant findings?
4. Discussion: What conclusions are drawn? What limitations exist? What future work is suggested?

For each section that exists in the paper, provide 2-3 specific, informative bullet points.
You MUST respond in the exact JSON format requested. Do not include any text outside the JSON.

Paper text:
{full_text}"""

        logger.info("Calling Ollama for structured analysis")
        # Use structured output with Pydantic schema
        response = chat(
            messages=[{
                'role': 'user',
                'content': prompt,
            }],
            model='llama3.2',  # Use available model, might make it dynamic
            format=PaperAnalysis.model_json_schema(),
            options={
                'temperature': 0.2,  # Slightly higher temperature for more content
                'num_predict': 1200,  # More tokens for complete analysis
                'top_p': 0.9,  # Add top_p for better generation
                'repeat_penalty': 1.1  # Prevent repetition
            }
        )
        
        logger.info(f"Got Ollama response, length: {len(response.message.content)}")
        
        # Check if response is too short (likely an error)
        if len(response.message.content.strip()) < 20:
            logger.warning(f"Ollama response too short: '{response.message.content}'")
            return None
        
        # Parse and validate the structured response
        try:
            analysis = PaperAnalysis.model_validate_json(response.message.content)
        except Exception as parse_error:
            logger.error(f"Failed to parse Ollama response as JSON: {parse_error}")
            logger.error(f"Raw response: {response.message.content}")
            return None
        
        # Check if analysis has content
        sections_with_content = sum([
            bool(analysis.introduction and analysis.introduction.bullet_points),
            bool(analysis.methods and analysis.methods.bullet_points),
            bool(analysis.results and analysis.results.bullet_points),
            bool(analysis.discussion and analysis.discussion.bullet_points)
        ])
        
        logger.info(f"Analysis parsed with {sections_with_content} sections containing content")
        
        # If no sections have content, return None to indicate failure
        if sections_with_content == 0:
            logger.warning("Analysis succeeded but contains no content in any section")
            return None
            
        return analysis
        
    except Exception as e:
        logger.error(f"Error in structured LLM analysis: {e}")
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

@mcp.tool
def arxiv_search(query: str, max_results: Optional[int] = 3) -> str:
    """Search arXiv for academic papers and research publications"""
    try:
        import arxiv
        
        # Validate and sanitize inputs - handle None case explicitly
        if max_results is None:
            max_results = 3
        max_results = max(1, min(max_results, 10))
        
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
                paper_content = _extract_paper_content(result.pdf_url)
                
                if paper_content:
                    # Introduction/Background
                    if paper_content.introduction and paper_content.introduction.bullet_points:
                        formatted_results += "\n**Introduction:**\n\n"
                        for point in paper_content.introduction.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"- {clean_point}\n\n"
                        formatted_results += "\n"
                    
                    # Methods/Approach
                    if paper_content.methods and paper_content.methods.bullet_points:
                        formatted_results += "\n**Methods:**\n\n"
                        for point in paper_content.methods.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"- {clean_point}\n\n"
                        formatted_results += "\n"
                    
                    # Results
                    if paper_content.results and paper_content.results.bullet_points:
                        formatted_results += "\n**Results:**\n\n"
                        for point in paper_content.results.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"- {clean_point}\n\n"
                        formatted_results += "\n"
                    
                    # Discussion/Limitations
                    if paper_content.discussion and paper_content.discussion.bullet_points:
                        formatted_results += "\n**Discussion:**\n\n"
                        for point in paper_content.discussion.bullet_points:
                            clean_point = _clean_markdown_text(point)
                            formatted_results += f"- {clean_point}\n\n"
                        formatted_results += "\n"
                else:
                    formatted_results += "*PDF analysis unavailable - using abstract only.*\n\n"
            
            # Add separator with proper spacing to prevent markdown bleeding
            formatted_results += "\n---\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"

# ============================================================================
# FASTMCP TOOLS - FINANCIAL DATA (STOCKS, CRYPTO, MARKETS)
# ============================================================================

@mcp.tool
def get_stock_price(ticker: str) -> str:
    """Get current stock price and basic information using Yahoo Finance API"""
    try:
        import requests
        
        # Clean up old cache periodically
        _cleanup_old_cache()
        
        # Check cache first
        cached_data = _load_cached_data(ticker)
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
            _save_cached_data(ticker, {'quote': quote_data})
        
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
    """Get historical stock price data using Yahoo Finance API"""
    try:
        import requests
        
        cache_key = f"{ticker}_history_{period}"
        cached_data = _load_cached_data(cache_key)
        
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
            _save_cached_data(cache_key, {'history': hist_data})
        
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
    """Get current cryptocurrency price using Yahoo Finance API"""
    try:
        import requests
        
        # Convert symbol to Yahoo Finance format for crypto (e.g., BTC -> BTC-USD)
        if not symbol.endswith('-USD'):
            crypto_ticker = f"{symbol.upper()}-USD"
        else:
            crypto_ticker = symbol.upper()
        
        cache_key = f"{symbol}_crypto"
        cached_data = _load_cached_data(cache_key)
        
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
            _save_cached_data(cache_key, {'crypto': crypto_data})
        
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
    """Get summary of major market indices using Yahoo Finance API"""
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
                cached_data = _load_cached_data(f"{symbol}_market")
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
                    _save_cached_data(f"{symbol}_market", {'quote': quote_data})
                
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

# ============================================================================
# FASTMCP TOOLS - YOUTUBE ANALYSIS
# ============================================================================

def _extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats and clean parameters"""
    import re
    
    # Clean up common URL issues (remove extra spaces, fix protocols)
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        if url.startswith('www.') or url.startswith('youtube.') or url.startswith('youtu.be'):
            url = 'https://' + url
    
    # YouTube URL patterns - comprehensive to handle all parameters including playlists
    patterns = [
        # Standard watch URLs with any parameters (timestamps, playlists, etc.)
        r'youtube\.com/watch\?.*[?&]?v=([a-zA-Z0-9_-]{11})',
        # Playlist URLs - extract video ID while ignoring list/index parameters
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11}).*(?:&list=|&index=)',
        # Short URLs
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        # Embed URLs
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        # Mobile URLs
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        # Share URLs with parameters
        r'youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def _get_transcript_db():
    """Get or create TinyDB database for transcripts"""
    from tinydb import TinyDB
    import tempfile
    import os
    
    # Use user's cache directory or temp directory if read-only
    cache_dir = os.path.expanduser('~/.cache/mcp_playground')
    try:
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, 'transcripts.json')
    except (OSError, PermissionError):
        # Fallback to temp directory if cache dir is not writable
        db_path = os.path.join(tempfile.gettempdir(), 'mcp_playground_transcripts.json')
    
    return TinyDB(db_path)

def _filter_sponsor_content(transcript_text: str) -> str:
    """Remove sponsor segments and promotional content from transcript"""
    import re
    
    # Common patterns for sponsor/ad content
    sponsor_patterns = [
        # Sponsor mentions
        r'this video is sponsored by[^.]*\.',
        r'our sponsor[^.]*\.',
        r'today\'?s sponsor[^.]*\.',
        r'brought to you by[^.]*\.',
        r'special thanks to[^.]*\.',
        r'thanks to.*?for sponsoring[^.]*\.',
        
        # Common sponsor transitions
        r'but first[^.]*sponsor[^.]*\.',
        r'before we get started[^.]*sponsor[^.]*\.',
        r'speaking of[^.]*\.',
        
        # Skillshare/common sponsors
        r'skillshare[^.]*\.',
        r'nordvpn[^.]*\.',
        r'squarespace[^.]*\.',
        r'brilliant[^.]*\.',
        r'audible[^.]*\.',
        r'honey[^.]*\.',
        r'raid shadow legends[^.]*\.',
        
        # Subscribe/like requests (often clustered with ads)
        r'don\'?t forget to like and subscribe[^.]*\.',
        r'if you enjoyed this video[^.]*subscribe[^.]*\.',
        r'smash that like button[^.]*\.',
        
        # Merchandise/channel promotion
        r'check out my merch[^.]*\.',
        r'link in the description[^.]*\.',
        r'patreon[^.]*\.',
    ]
    
    # Apply filters (case insensitive)
    filtered_text = transcript_text
    for pattern in sponsor_patterns:
        filtered_text = re.sub(pattern, '', filtered_text, flags=re.IGNORECASE)
    
    # Remove multiple spaces and clean up
    filtered_text = re.sub(r'\s+', ' ', filtered_text)
    filtered_text = filtered_text.strip()
    
    return filtered_text

def _get_youtube_transcript(url: str) -> str:
    """Internal function to extract transcript from YouTube video with caching"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from tinydb import Query
        
        # Extract video ID
        video_id = _extract_video_id(url)
        if not video_id:
            return f"Invalid YouTube URL. Please provide a valid YouTube video URL."
        
        # Check cache first
        db = _get_transcript_db()
        Video = Query()
        cached = db.search(Video.video_id == video_id)
        
        if cached:
            cached_data = cached[0]
            return f"**{cached_data.get('title', 'YouTube Video')}**\n\n{cached_data['transcript']}"
        
        # Get transcript from YouTube
        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.fetch(video_id)
            transcript_text = ' '.join([entry['text'] for entry in transcript_list])
        except Exception as e:
            # Try to get any available transcript
            try:
                api = YouTubeTranscriptApi()
                transcript_list = api.list(video_id)
                transcript = transcript_list.find_generated_transcript(['en'])
                transcript_data = transcript.fetch()
                transcript_text = ' '.join([entry['text'] for entry in transcript_data])
            except:
                return f"No transcript available for this video. The video may not have captions or subtitles."
        
        # Try to get video title (basic approach)
        title = f"YouTube Video ({video_id})"
        
        # Cache the transcript
        db.insert({
            'video_id': video_id,
            'url': url,
            'title': title,
            'transcript': transcript_text,
            'created_at': datetime.now().isoformat(),
            'language': 'en'
        })
        
        return f"**{title}**\n\n{transcript_text}"
        
    except Exception as e:
        return f"Error extracting transcript: {str(e)}"

@mcp.tool
def summarize_youtube_video(url: str) -> str:
    """Generate AI summary of YouTube video content"""
    try:
        # Get the transcript
        transcript_result = _get_youtube_transcript(url)
        
        if transcript_result.startswith("Error") or transcript_result.startswith("Invalid") or transcript_result.startswith("No transcript"):
            return transcript_result
        
        # Extract title and transcript text  
        lines = transcript_result.split('\n', 2)
        title = lines[0].replace('**', '') if lines else "YouTube Video"
        transcript_text = lines[2] if len(lines) > 2 else transcript_result
        
        # Filter out sponsor/ad content
        transcript_text = _filter_sponsor_content(transcript_text)
        
        # Calculate some basic stats
        word_count = len(transcript_text.split())
        duration_estimate = f"~{word_count // 150} minutes" if word_count > 150 else "< 1 minute"
        
        # Prepare content for LLM analysis with natural prompt
        max_content_length = 8000  # Total character budget (~8k tokens)
        
        if len(transcript_text) <= max_content_length:
            content = transcript_text
            note = ""
        else:
            # For long videos, include beginning + end (many videos have summaries at the end)
            words = transcript_text.split()
            total_words = len(words)
            
            # Use ~75% for beginning, ~25% for end
            beginning_chars = int(max_content_length * 0.75)
            end_words = min(2000, total_words // 4)  # Last ~2k words or 25% of video
            
            # Get beginning portion
            beginning = transcript_text[:beginning_chars]
            
            # Get end portion
            end_text = ' '.join(words[-end_words:])
            
            # Combine with separator
            content = f"{beginning}\n\n--- [MIDDLE SECTION OMITTED] ---\n\n{end_text}"
            note = "\n\n*Note: This includes the beginning and ending of a longer video, with the middle section omitted.*"
        
        # Return formatted content that naturally prompts the LLM to summarize
        return f"""Analyze this YouTube video content and provide a focused summary.

Video: {title} ({duration_estimate}, {word_count:,} words)

Transcript content:
{content}{note}

Provide a concise summary focusing on the main content, key points, and conclusions. Ignore any sponsor mentions, advertisements, or channel promotion content."""
            
    except Exception as e:
        return f"Error summarizing video: {str(e)}"

@mcp.tool
def query_youtube_transcript(url: str, question: str) -> str:
    """Answer questions about YouTube video content using AI analysis"""
    try:
        # Get the transcript
        transcript_result = _get_youtube_transcript(url)
        
        if transcript_result.startswith("Error") or transcript_result.startswith("Invalid") or transcript_result.startswith("No transcript"):
            return transcript_result
        
        # Extract title and transcript text
        lines = transcript_result.split('\n', 2)
        title = lines[0].replace('**', '') if lines else "YouTube Video"
        transcript_text = lines[2] if len(lines) > 2 else transcript_result
        
        # Filter out sponsor/ad content
        transcript_text = _filter_sponsor_content(transcript_text)
        
        # Calculate some basic stats
        word_count = len(transcript_text.split())
        duration_estimate = f"~{word_count // 150} minutes" if word_count > 150 else "< 1 minute"
        
        # Prepare content for LLM analysis with natural prompt  
        max_content_length = 8000  # Total character budget (~8k tokens)
        
        if len(transcript_text) <= max_content_length:
            content = transcript_text
            note = ""
        else:
            # For long videos, include beginning + end (many videos have summaries at the end)
            words = transcript_text.split()
            total_words = len(words)
            
            # Use ~75% for beginning, ~25% for end
            beginning_chars = int(max_content_length * 0.75)
            end_words = min(2000, total_words // 4)  # Last ~2k words or 25% of video
            
            # Get beginning portion
            beginning = transcript_text[:beginning_chars]
            
            # Get end portion
            end_text = ' '.join(words[-end_words:])
            
            # Combine with separator
            content = f"{beginning}\n\n--- [MIDDLE SECTION OMITTED] ---\n\n{end_text}"
            note = "\n\n*Note: This includes the beginning and ending of a longer video, with the middle section omitted.*"
        
        # Return formatted content that clearly directs the LLM to answer the specific question
        return f"""Please answer this specific question about the YouTube video: "{question}"

Video: {title} ({duration_estimate}, {word_count:,} words)

Transcript content:
{content}{note}

Focus on answering "{question}" based on the main video content. Ignore any sponsor mentions, advertisements, or channel promotion content."""
            
    except Exception as e:
        return f"Error querying video transcript: {str(e)}"

# ============================================================================
# MAIN FUNCTION TO RUN THE SERVER
# ============================================================================

def main():
    """Main function to run the FastMCP server"""
    import sys
    
    # Check for command line arguments for different modes
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "http":
            # Run as HTTP server for web-based clients
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
            host = sys.argv[3] if len(sys.argv) > 3 else "0.0.0.0"
            print(f"Starting FastMCP HTTP server on {host}:{port}")
            mcp.run(transport="http", host=host, port=port)
        elif mode == "stdio":
            # Run as stdio server (default for local clients)
            print("Starting FastMCP stdio server")
            mcp.run(transport="stdio")
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python mcp_server.py [stdio|http] [port] [host]")
            sys.exit(1)
    else:
        # Default to stdio transport for local development
        print("Starting FastMCP server in stdio mode (default)")
        print("Use 'python mcp_server.py http 8000' for web mode")
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()