"""
Web search and URL analysis tools
"""

from fastmcp import FastMCP
import os
from datetime import datetime
from typing import Union, Tuple, Optional, Dict, Any
import httpx
from urllib.parse import urlparse
import json
import re
from bs4 import BeautifulSoup
import html2text

def _validate_url(url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate URL format and return validation result.
    
    Returns:
        Tuple of (is_valid, validated_url, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "", "Error: URL is required and must be a string"
    
    url = url.strip()
    if not url:
        return False, "", "Error: URL cannot be empty"
    
    # Validate URL format
    parsed = urlparse(url)
    if not parsed.scheme:
        return False, "", "Error: URL must include protocol (http:// or https://)"
    
    if parsed.scheme not in ['http', 'https']:
        return False, "", "Error: Only HTTP and HTTPS URLs are supported"
    
    if not parsed.netloc:
        return False, "", "Error: Invalid URL format - missing domain"
    
    # Check for YouTube URLs
    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        return False, "", "Error: Use analyze_youtube_url tool for YouTube videos, not this tool"
    
    return True, url, None

def _fetch_url_content(url: str) -> Tuple[bool, Union[httpx.Response, str]]:
    """
    Fetch content from URL with proper error handling.
    
    Returns:
        Tuple of (success, response_or_error_message)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    parsed = urlparse(url)
    
    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return True, response
    except httpx.TimeoutException:
        return False, f"Error: Request timed out after 30 seconds. Site may be slow or unresponsive."
    except httpx.ConnectError:
        return False, f"Error: Could not connect to {parsed.netloc}. Check if the URL is correct."
    except httpx.HTTPStatusError as e:
        return False, f"Error: HTTP {e.response.status_code} - {e.response.reason_phrase}"
    except Exception as e:
        return False, f"Unexpected error fetching URL: {str(e)}"

def _extract_page_metadata(soup) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from HTML soup.
    
    Returns:
        Dictionary containing title, description, keywords, author, etc.
    """
    metadata = {}
    
    # Basic title
    title_tag = soup.find('title')
    metadata['title'] = title_tag.get_text().strip() if title_tag else ""
    
    # Meta description
    desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    metadata['description'] = desc_tag.get('content', '').strip() if desc_tag else ""
    
    # Keywords
    keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
    metadata['keywords'] = keywords_tag.get('content', '').strip() if keywords_tag else ""
    
    # Author
    author_tag = soup.find('meta', attrs={'name': 'author'}) or soup.find('meta', attrs={'property': 'article:author'})
    metadata['author'] = author_tag.get('content', '').strip() if author_tag else ""
    
    # Publish date
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('meta', attrs={'name': 'date'})
    metadata['publish_date'] = date_tag.get('content', '').strip() if date_tag else ""
    
    # Canonical URL
    canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
    metadata['canonical_url'] = canonical_tag.get('href', '').strip() if canonical_tag else ""
    
    # OpenGraph data
    og_data = {}
    for og_tag in soup.find_all('meta', attrs={'property': lambda x: x and x.startswith('og:')}):
        prop = og_tag.get('property', '').replace('og:', '')
        content = og_tag.get('content', '').strip()
        if prop and content:
            og_data[prop] = content
    metadata['opengraph'] = og_data
    
    # Twitter Card data
    twitter_data = {}
    for twitter_tag in soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')}):
        name = twitter_tag.get('name', '').replace('twitter:', '')
        content = twitter_tag.get('content', '').strip()
        if name and content:
            twitter_data[name] = content
    metadata['twitter'] = twitter_data
    
    # JSON-LD structured data
    json_ld_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})
    json_ld_data = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string or '')
            json_ld_data.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    metadata['json_ld'] = json_ld_data
    
    return metadata

def _extract_clean_content(soup) -> Tuple[str, Dict[str, Any]]:
    """
    Extract clean, structured content from HTML soup optimized for LLM analysis.
    
    Returns:
        Tuple of (clean_content, content_stats)
    """
    
    # Make a copy to avoid modifying original
    content_soup = BeautifulSoup(str(soup), 'html.parser')
    
    # Remove noise elements
    for element in content_soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe', 'noscript']):
        element.decompose()
    
    # Remove common noise classes/IDs
    noise_selectors = [
        '[class*="sidebar"]', '[class*="nav"]', '[class*="menu"]', '[class*="ad"]',
        '[class*="banner"]', '[class*="footer"]', '[class*="header"]', '[class*="widget"]',
        '[id*="sidebar"]', '[id*="nav"]', '[id*="menu"]', '[id*="ad"]',
        '[id*="banner"]', '[id*="footer"]', '[id*="header"]'
    ]
    
    for selector in noise_selectors:
        for element in content_soup.select(selector):
            element.decompose()
    
    # Try to find main content area
    main_content = None
    content_selectors = [
        'main', 'article', '[role="main"]', '.main-content', '.content', 
        '.post', '.entry', '.article-content', '#content', '#main'
    ]
    
    for selector in content_selectors:
        main_content = content_soup.select_one(selector)
        if main_content:
            break
    
    # If no main content found, use body but remove more noise
    if not main_content:
        main_content = content_soup.find('body') or content_soup
        # Remove additional noise for body content
        for element in main_content.select('.sidebar, .navigation, .breadcrumb, .share, .social'):
            element.decompose()
    
    # Convert to markdown with optimized settings
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.body_width = 0  # Don't wrap lines
    h.protect_links = True
    h.wrap_links = False
    h.unicode_snob = True
    h.decode_errors = 'ignore'
    
    # Convert to markdown
    markdown_content = h.handle(str(main_content))
    
    # Clean up the markdown
    lines = markdown_content.split('\n')
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        line = line.strip()
        # Skip multiple empty lines
        if not line:
            if not prev_empty:
                cleaned_lines.append('')
            prev_empty = True
            continue
        prev_empty = False
        
        # Skip noise patterns
        if (line.startswith('* * *') or 
            line.startswith('---') and len(line) > 10 or
            line.lower().startswith('advertisement') or
            re.match(r'^#+\s*$', line)):  # Empty headers
            continue
            
        cleaned_lines.append(line)
    
    clean_content = '\n'.join(cleaned_lines).strip()
    
    # Calculate content statistics
    word_count = len(clean_content.split())
    char_count = len(clean_content)
    reading_time = max(1, word_count // 200)  # Assume 200 WPM reading speed
    
    # Extract headings for structure analysis
    headings = re.findall(r'^#+\s+(.+)$', clean_content, re.MULTILINE)
    
    content_stats = {
        'word_count': word_count,
        'character_count': char_count,
        'estimated_reading_time_minutes': reading_time,
        'heading_count': len(headings),
        'headings': headings[:10],  # First 10 headings
        'has_main_content_area': main_content is not None and main_content.name in ['main', 'article']
    }
    
    return clean_content, content_stats

def _save_web_content(url: str, html_content: str) -> str:
    """Save web content as a markdown document"""
    try:
        from ..core.vector_memory import vector_memory_manager
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract metadata and clean content using shared functions
        metadata = _extract_page_metadata(soup)
        clean_content, content_stats = _extract_clean_content(soup)
        
        # Use extracted title or generate one
        page_title = metadata['title']
        if not page_title:
            # Try to extract from first heading in content
            if content_stats['headings']:
                page_title = content_stats['headings'][0]
            else:
                page_title = f"Web Capture - {url}"
        
        # Create formatted content
        formatted_content = f"# {page_title}\n\n"
        formatted_content += f"**Source:** {url}\n"
        formatted_content += f"**Captured:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        formatted_content += "---\n\n"
        formatted_content += clean_content
        
        # Determine file path
        cache_dir = os.path.expanduser('~/.cache/mcp_playground/documents/captures')
        safe_title = "".join(c for c in page_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_title}.md"
        file_path = os.path.join(cache_dir, filename)
        
        # Store the document (deduplication handled automatically by vector_memory_manager)
        doc_id = vector_memory_manager.store_document(
            title=page_title,
            content=formatted_content,
            doc_type="capture",
            tags=["web-capture"],
            file_path=file_path,
            source_url=url
        )
        
        # Check if this was a duplicate (existing ID returned)
        existing_docs = vector_memory_manager.get_all_documents()
        existing_doc = next((doc for doc in existing_docs if doc['id'] == doc_id), None)
        
        if existing_doc and existing_doc.get('source_url') == url:
            # This was a duplicate URL
            return f"URL already saved!\nTitle: {existing_doc['title']}\nID: {doc_id}\nUse find_saved or list_saved to access your saved content."
        else:
            # This is a new document
            return f"Title: {page_title}\nID: {doc_id}\nFile: {file_path}\nContent is now searchable and available offline."
        
    except Exception as e:
        return f"❌ Error saving web content: {str(e)}"


def register_web_tools(mcp: FastMCP):
    """Register web-related tools with the MCP server"""
    
    @mcp.tool(description="Search web for current information using DuckDuckGo")
    def web_search(query: str, max_results: int = 5) -> str:
        """Search the web using DuckDuckGo and return current information with titles, URLs, and summaries. Returns up to 10 results (default: 5). Uses timeout configuration for reliability."""
        try:
            from ddgs import DDGS
            from ddgs.exceptions import RatelimitException, TimeoutException
            
            # Ensure max_results is an integer and within bounds
            max_results = max(1, min(max_results or 5, 10))
            
            # Validate query
            if not query or not query.strip():
                return "Error: Search query cannot be empty"
            
            query = query.strip()
            
            # Initialize DDGS with timeout (headers no longer supported in ddgs package)
            ddgs = DDGS(timeout=20)
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
            
        except RatelimitException:
            return "Error: DuckDuckGo rate limit exceeded. Please try again in a few moments."
        except TimeoutException:
            return "Error: Search request timed out. Please try again."
        except Exception as e:
            return f"Error performing search: {str(e)}"
    
    @mcp.tool(description="Comprehensive analysis of webpage content optimized for LLM understanding")
    def analyze_url(url: str) -> str:
        """
        Perform comprehensive analysis of webpage content without saving. 
        Extracts full content, metadata, and structure optimized for LLM analysis.
        
        Args:
            url: Complete URL with http:// or https://
        """
        # Validate URL
        is_valid, validated_url, error_msg = _validate_url(url)
        if not is_valid:
            return error_msg
        
        # Fetch content
        success, response_or_error = _fetch_url_content(validated_url)
        if not success:
            return response_or_error
        
        response = response_or_error
        content_type = response.headers.get('content-type', 'unknown').split(';')[0]
        content_length = len(response.content)
        final_url = str(response.url)
        
        # Build comprehensive analysis
        analysis = f"# WEBPAGE ANALYSIS\n\n"
        analysis += f"**URL**: {final_url}\n"
        if final_url != validated_url:
            analysis += f"**Original URL**: {validated_url}\n"
        analysis += f"**Content Type**: `{content_type}`\n"
        analysis += f"**Content Size**: {content_length:,} bytes\n\n"
        
        if 'text/html' in content_type:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract metadata
                metadata = _extract_page_metadata(soup)
                
                # Extract clean content and statistics
                clean_content, content_stats = _extract_clean_content(soup)
                
                # Build metadata section
                analysis += "## PAGE METADATA\n\n"
                if metadata['title']:
                    analysis += f"**Title**: {metadata['title']}\n"
                if metadata['description']:
                    analysis += f"**Description**: {metadata['description']}\n"
                if metadata['author']:
                    analysis += f"**Author**: {metadata['author']}\n"
                if metadata['publish_date']:
                    analysis += f"**Published**: {metadata['publish_date']}\n"
                if metadata['keywords']:
                    analysis += f"**Keywords**: {metadata['keywords']}\n"
                if metadata['canonical_url']:
                    analysis += f"**Canonical URL**: {metadata['canonical_url']}\n"
                
                # OpenGraph data
                if metadata['opengraph']:
                    analysis += f"\n**OpenGraph Data**:\n"
                    for key, value in metadata['opengraph'].items():
                        if len(value) < 200:  # Only show short values
                            analysis += f"- {key}: {value}\n"
                
                # Twitter Card data
                if metadata['twitter']:
                    analysis += f"\n**Twitter Card Data**:\n"
                    for key, value in metadata['twitter'].items():
                        if len(value) < 200:  # Only show short values
                            analysis += f"- {key}: {value}\n"
                
                # JSON-LD structured data summary
                if metadata['json_ld']:
                    analysis += f"\n**Structured Data**: {len(metadata['json_ld'])} JSON-LD blocks found\n"
                    for i, data in enumerate(metadata['json_ld'][:3]):  # Show first 3
                        if isinstance(data, dict) and '@type' in data:
                            analysis += f"- Block {i+1}: {data.get('@type', 'Unknown')}\n"
                
                # Content statistics
                analysis += f"\n## CONTENT STATISTICS\n\n"
                analysis += f"**Word Count**: {content_stats['word_count']:,}\n"
                analysis += f"**Character Count**: {content_stats['character_count']:,}\n"
                analysis += f"**Estimated Reading Time**: {content_stats['estimated_reading_time_minutes']} minutes\n"
                analysis += f"**Headings Found**: {content_stats['heading_count']}\n"
                analysis += f"**Main Content Area Detected**: {'Yes' if content_stats['has_main_content_area'] else 'No'}\n"
                
                if content_stats['headings']:
                    analysis += f"\n**Content Structure** (First 10 headings):\n"
                    for heading in content_stats['headings']:
                        analysis += f"- {heading}\n"
                
                # Full content section
                analysis += f"\n## FULL CONTENT\n\n"
                if content_stats['word_count'] > 2000:
                    analysis += f"*Note: Large content ({content_stats['word_count']:,} words). Consider using save_link for offline access.*\n\n"
                
                analysis += clean_content
                
                analysis += f"\n\n---\n\n**To save this content for offline access and knowledge building, use the `save_link` tool.**"
                
            except Exception as e:
                analysis += f"Error processing HTML content: {str(e)}\n"
                
        elif 'application/json' in content_type:
            try:
                json_content = response.text
                if len(json_content) > 2000:
                    json_preview = json_content[:2000] + "..."
                    analysis += f"## JSON Content (First 2000 characters)\n\n```json\n{json_preview}\n```\n"
                else:
                    analysis += f"## JSON Content\n\n```json\n{json_content}\n```\n"
            except:
                analysis += f"**Note**: JSON content detected but could not display\n"
                
        elif content_type.startswith('image/'):
            analysis += f"## Image File\n\n**Type**: {content_type}\n**Size**: {content_length:,} bytes\n\n*This is an image file. Use appropriate image analysis tools for content extraction.*\n"
            
        else:
            analysis += f"## Non-HTML Content\n\n**Content Type**: {content_type}\n**Size**: {content_length:,} bytes\n\n*This content type is not directly analyzable as text. Consider downloading for manual review.*\n"
        
        return analysis
    
    @mcp.tool(description="Save webpage content for offline access and knowledge building")
    def save_link(url: str, title: str = None) -> str:
        """
        Save webpage content for offline access and knowledge building.
        
        Args:
            url: URL to save (must include http:// or https://)
            title: Optional custom title (auto-generated if not provided)
        """
        # Validate URL
        is_valid, validated_url, error_msg = _validate_url(url)
        if not is_valid:
            return error_msg
        
        # Fetch content
        success, response_or_error = _fetch_url_content(validated_url)
        if not success:
            return response_or_error
        
        response = response_or_error
        final_url = str(response.url)
        content_type = response.headers.get('content-type', 'unknown').split(';')[0]
        
        if 'text/html' in content_type:
            # Save the content using existing function
            saved_result = _save_web_content(final_url, response.text)
            return f"**LINK SAVED**\n{saved_result}"
        else:
            return f"Error: Cannot save {content_type} content as markdown. Only HTML pages can be saved."