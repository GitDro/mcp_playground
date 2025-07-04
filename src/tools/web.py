"""
Web search and URL analysis tools
"""

from fastmcp import FastMCP


def register_web_tools(mcp: FastMCP):
    """Register web-related tools with the MCP server"""
    
    @mcp.tool
    def web_search(query: str, max_results: int = 5) -> str:
        """Search the web using DuckDuckGo and return current information with titles, URLs, and summaries. Returns up to 10 results (default: 5)."""
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
        """Fetch and analyze a URL to extract content type, size, and preview text. Best for HTML pages and basic content inspection."""
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