"""
Web search and URL analysis tools
"""

from fastmcp import FastMCP
import os
from datetime import datetime

def _save_web_content(url: str, html_content: str) -> str:
    """Save web content as a markdown document"""
    try:
        from bs4 import BeautifulSoup
        import html2text
        from ..core.vector_memory import vector_memory_manager
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()
        
        # Get title
        title_tag = soup.find('title')
        page_title = title_tag.get_text().strip() if title_tag else ""
        
        # Convert to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0  # Don't wrap lines
        
        # Get main content - try to find article, main, or body
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            markdown_content = h.handle(str(main_content))
        else:
            markdown_content = h.handle(html_content)
        
        # Clean up the markdown
        lines = markdown_content.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('* * *'):  # Remove separator lines
                cleaned_lines.append(line)
        
        # Generate title if not provided
        if not page_title:
            # Try to extract from first heading or URL
            for line in cleaned_lines[:5]:
                if line.startswith('#'):
                    page_title = line.strip('# ').strip()
                    break
            if not page_title:
                page_title = f"Web Capture - {url}"
        
        # Create formatted content
        formatted_content = f"# {page_title}\n\n"
        formatted_content += f"**Source:** {url}\n"
        formatted_content += f"**Captured:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        formatted_content += "---\n\n"
        formatted_content += '\n'.join(cleaned_lines)
        
        # Determine file path
        cache_dir = os.path.expanduser('~/.cache/mcp_playground/documents/captures')
        safe_title = "".join(c for c in page_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_title}.md"
        file_path = os.path.join(cache_dir, filename)
        
        # Store the document
        doc_id = vector_memory_manager.store_document(
            title=page_title,
            content=formatted_content,
            doc_type="capture",
            tags=["web-capture"],
            file_path=file_path,
            source_url=url
        )
        
        return f"✅ Web content saved successfully!\n📝 Title: {page_title}\n🆔 ID: {doc_id}\n📁 File: {file_path}\n\nContent is now searchable and available offline."
        
    except ImportError:
        return "❌ Error: Required packages (beautifulsoup4, html2text) not available. Install with: uv add beautifulsoup4 html2text"
    except Exception as e:
        return f"❌ Error saving web content: {str(e)}"


def register_web_tools(mcp: FastMCP):
    """Register web-related tools with the MCP server"""
    
    @mcp.tool(description="Search the web using DuckDuckGo with rate limiting protection")
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
    
    @mcp.tool(description="Summarize webpage content from any URL with optional offline saving")
    def summarize_url(url: str, save_content: bool = False) -> str:
        """
        Summarize and analyze webpage content from any URL with optional offline saving.
        
        This tool fetches webpages, extracts clean content, provides a summary preview,
        and can optionally save the content as markdown for offline access and search.
        
        IMPORTANT: Do not use this for YouTube URLs - use analyze_youtube_url instead.
        
        Args:
            url (str): The complete URL to summarize (must include http:// or https://)
            save_content (bool): If True, saves cleaned markdown content to documents/captures/
                                If False (default), only shows summary without saving
        
        Returns:
            str: Content summary including title, preview, and optional save confirmation
            
        Examples:
            - summarize_url("https://example.com") → Summary only
            - summarize_url("https://example.com", True) → Summary + save content
            - summarize_url("https://example.com", "true") → Also works (string converted)
        
        Common Issues:
            - URL must include protocol (http:// or https://)
            - Some sites may block automated requests
            - Large files may timeout (30 second limit)
            - Non-HTML content cannot be saved as markdown
        """
        try:
            import httpx
            from urllib.parse import urlparse
            
            # Input validation
            if not url or not isinstance(url, str):
                return "❌ Error: URL is required and must be a string"
            
            url = url.strip()
            if not url:
                return "❌ Error: URL cannot be empty"
            
            # Validate URL format
            parsed = urlparse(url)
            if not parsed.scheme:
                return "❌ Error: URL must include protocol (http:// or https://)"
            
            if parsed.scheme not in ['http', 'https']:
                return "❌ Error: Only HTTP and HTTPS URLs are supported"
            
            if not parsed.netloc:
                return "❌ Error: Invalid URL format - missing domain"
            
            # Handle string boolean parameters (common when called by LLM)
            if isinstance(save_content, str):
                save_content_lower = save_content.lower().strip()
                save_content = save_content_lower in ('true', '1', 'yes', 'on', 'save')
            
            # Check for YouTube URLs
            if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
                return "❌ Error: Use analyze_youtube_url tool for YouTube videos, not summarize_url"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            with httpx.Client(follow_redirects=True) as client:
                try:
                    response = client.get(url, headers=headers, timeout=30)
                    response.raise_for_status()
                except httpx.TimeoutException:
                    return f"❌ Error: Request timed out after 30 seconds. Site may be slow or unresponsive."
                except httpx.ConnectError:
                    return f"❌ Error: Could not connect to {parsed.netloc}. Check if the URL is correct."
                except httpx.HTTPStatusError as e:
                    return f"❌ Error: HTTP {e.response.status_code} - {e.response.reason_phrase}"
                
                content_type = response.headers.get('content-type', 'unknown').split(';')[0]
                content_length = len(response.content)
                final_url = str(response.url)
                
                # Build analysis summary
                summary = f"# 🌐 URL Analysis Results\n\n"
                summary += f"**Original URL**: {url}\n"
                if final_url != url:
                    summary += f"**Final URL**: {final_url} (redirected)\n"
                summary += f"**Content Type**: {content_type}\n"
                summary += f"**Content Size**: {content_length:,} bytes\n"
                summary += f"**Status**: ✅ Successfully loaded\n\n"
                
                if 'text/html' in content_type:
                    # Extract and show preview for HTML content
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Get title
                        title_tag = soup.find('title')
                        title = title_tag.get_text().strip() if title_tag else "No title found"
                        summary += f"**Page Title**: {title}\n"
                        
                        # Get clean text preview
                        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                            element.decompose()
                        
                        text_content = soup.get_text()
                        clean_lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                        preview_text = '\n'.join(clean_lines[:10])  # First 10 non-empty lines
                        
                        if len(preview_text) > 500:
                            preview_text = preview_text[:500] + "..."
                        
                        summary += f"\n**Content Preview**:\n{preview_text}\n"
                        
                    except ImportError:
                        # Fallback if beautifulsoup not available
                        text_content = response.text[:800]
                        summary += f"\n**Raw Content Preview**:\n{text_content}...\n"
                    
                    # Handle content saving
                    if save_content:
                        try:
                            saved_result = _save_web_content(final_url, response.text)
                            summary += f"\n---\n\n📁 **Content Saved**\n{saved_result}"
                        except Exception as e:
                            summary += f"\n---\n\n❌ **Save Failed**: {str(e)}"
                    else:
                        summary += f"\n💡 **Tip**: Add `save_content=True` to save this content for offline access"
                        
                elif 'application/json' in content_type:
                    try:
                        json_preview = response.text[:500]
                        summary += f"**JSON Preview**:\n```json\n{json_preview}...\n```\n"
                    except:
                        summary += f"**Note**: JSON content detected but could not preview\n"
                        
                elif content_type.startswith('image/'):
                    summary += f"**Note**: Image file detected ({content_type})\n"
                    if save_content:
                        summary += f"**Note**: Cannot save image content as markdown\n"
                        
                else:
                    summary += f"**Note**: Non-HTML content type: {content_type}\n"
                    if save_content:
                        summary += f"**Note**: Cannot save {content_type} content as markdown\n"
                
                return summary
                
        except Exception as e:
            return f"❌ Unexpected error analyzing URL: {str(e)}\n\nPlease check that the URL is valid and accessible."