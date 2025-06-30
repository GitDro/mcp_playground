#!/usr/bin/env python3
"""
Web Search MCP Server

A Model Context Protocol (MCP) server providing web search capabilities
and local LLM integration. Built with FastMCP for minimal boilerplate.

Features:
- Web search via DuckDuckGo's free API (no API key required)
- Local LLM queries through Ollama
- Search with AI summarization
- Type-safe with Pydantic models

Usage:
    python web_search_server.py

Author: MCP Arena
"""

import logging
from typing import List, Optional
import re
import urllib.parse
import requests
import ollama
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Web Search & LLM Server")


class SearchResult(BaseModel):
    """Web search result data model."""
    title: str = Field(description="Title of the search result")
    snippet: str = Field(description="Brief text excerpt from the result")
    url: str = Field(description="Full URL of the search result")
    source: str = Field(description="Search engine or API source")


@mcp.tool()
def web_search(query: str, num_results: int = 5) -> List[SearchResult]:
    """
    Search the web using DuckDuckGo's instant answer API.
    
    Returns structured search results including titles, snippets, URLs, 
    and source information.
    
    Args:
        query: The search query string
        num_results: Maximum number of results to return (default: 5)
        
    Returns:
        List of SearchResult objects containing search results
        
    Raises:
        Exception: If the web search request fails or times out
    """
    logger.info(f"Web search: '{query}' (max {num_results} results)")
    
    try:
        # Use DuckDuckGo HTML search for better results
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        # Parse HTML to extract search results
        results = _parse_duckduckgo_results(response.text, num_results)
        
        logger.info(f"Retrieved {len(results)} search results")
        return results
        
    except requests.exceptions.Timeout:
        logger.error("Search request timed out")
        raise Exception("Search request timed out after 10 seconds")
    except requests.exceptions.RequestException as e:
        logger.error(f"Search request failed: {e}")
        raise Exception(f"Search request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected search error: {e}")
        raise Exception(f"Search failed: {str(e)}")


@mcp.tool()
def llm_query(
    prompt: str, 
    model: str = "llama3.2",
    enable_tools: bool = False
) -> str:
    """
    Query a local Ollama LLM with optional function calling.
    
    Args:
        prompt: The text prompt to send to the LLM
        model: The Ollama model to use (default: "llama3.2")
        enable_tools: Whether to enable function calling (default: False)
        
    Returns:
        The model's response text
        
    Raises:
        Exception: If the Ollama service is unavailable or query fails
    """
    logger.info(f"LLM query with model '{model}'")
    
    try:
        chat_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        # Add tools if enabled
        if enable_tools:
            chat_kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web for current information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "num_results": {
                                    "type": "integer",
                                    "description": "Number of results",
                                    "default": 5
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]
        
        response = ollama.chat(**chat_kwargs)
        content = response.get("message", {}).get("content", "")
        
        logger.info(f"LLM query completed using model '{model}'")
        return content
        
    except ollama.ResponseError as e:
        logger.error(f"Ollama service error: {e}")
        raise Exception(f"LLM service error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected LLM error: {e}")
        raise Exception(f"LLM query failed: {str(e)}")


@mcp.tool()
def search_and_summarize(
    query: str,
    summary_model: str = "llama3.2",
    max_results: int = 3
) -> str:
    """
    Search the web and provide an AI-generated summary of results.
    
    This composite tool combines web search with LLM processing to provide
    intelligent summaries without manually reviewing multiple results.
    
    Args:
        query: The search query to look up
        summary_model: The Ollama model to use for summarization
        max_results: Maximum number of search results to include
        
    Returns:
        An AI-generated summary combining information from search results
    """
    logger.info(f"Search and summarize: '{query}'")
    
    try:
        # Step 1: Perform web search
        search_results = _perform_web_search(query, max_results)
        
        if not search_results:
            return "No search results found for the given query."
        
        # Step 2: Format results for LLM processing
        formatted_results = []
        for i, result in enumerate(search_results, 1):
            formatted_results.append(
                f"{i}. {result.title}\n"
                f"   Source: {result.source}\n"
                f"   URL: {result.url}\n"
                f"   Content: {result.snippet}\n"
            )
        
        results_text = "\n".join(formatted_results)
        
        # Step 3: Create summarization prompt
        summary_prompt = f"""
Please provide a comprehensive summary of the following search results for "{query}":

{results_text}

Create a well-structured summary that:
1. Combines key information from all sources
2. Identifies common themes and important points
3. Notes any conflicting information
4. Provides a clear, concise overview

Summary:
"""
        
        # Step 4: Get LLM summary
        response = ollama.chat(
            model=summary_model,
            messages=[{"role": "user", "content": summary_prompt}]
        )
        
        summary_content = response["message"]["content"]
        logger.info("Search and summarize completed successfully")
        return summary_content
        
    except Exception as e:
        logger.error(f"Search and summarize error: {e}")
        raise Exception(f"Search and summarize failed: {str(e)}")


def _parse_duckduckgo_results(html_content: str, max_results: int) -> List[SearchResult]:
    """
    Parse DuckDuckGo HTML search results.
    
    Extracts titles, URLs, and snippets from the HTML response.
    """
    results = []
    
    try:
        # Try multiple patterns to extract search results
        patterns_to_try = [
            # Pattern 1: Standard result divs
            r'<div class="result[^"]*"[^>]*>.*?</div>',
            # Pattern 2: Links result container
            r'<div class="links_main[^"]*"[^>]*>.*?</div>',
            # Pattern 3: Any div with result-like content
            r'<div[^>]*>.*?<a[^>]*href="http[^"]*"[^>]*>.*?</a>.*?</div>'
        ]
        
        result_blocks = []
        for pattern in patterns_to_try:
            result_blocks = re.findall(pattern, html_content, re.DOTALL)
            if result_blocks:
                break
        
        for block in result_blocks[:max_results * 2]:  # Process more blocks to account for filtering
            # Try different link extraction patterns
            link_patterns = [
                r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>',
                r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            ]
            
            title_match = None
            for link_pattern in link_patterns:
                title_match = re.search(link_pattern, block, re.DOTALL)
                if title_match:
                    break
            
            if not title_match:
                continue
                
            url = title_match.group(1).strip()
            title = title_match.group(2).strip()
            
            # Skip invalid URLs
            if not url.startswith('http') or 'duckduckgo.com' in url:
                continue
            
            # Clean up URL (DuckDuckGo uses redirect URLs)
            if '/l/?uddg=' in url:
                url_match = re.search(r'uddg=([^&]+)', url)
                if url_match:
                    url = urllib.parse.unquote(url_match.group(1))
            
            # Extract snippet text with multiple patterns
            snippet_patterns = [
                r'<span class="result__snippet[^"]*"[^>]*>([^<]+)</span>',
                r'<div class="snippet[^"]*"[^>]*>([^<]+)</div>',
                r'<p[^>]*>([^<]{20,200})</p>'
            ]
            
            snippet = ""
            for snippet_pattern in snippet_patterns:
                snippet_match = re.search(snippet_pattern, block)
                if snippet_match:
                    snippet = snippet_match.group(1).strip()
                    break
            
            # Clean up text
            title = re.sub(r'<[^>]+>', '', title).strip()
            title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            snippet = re.sub(r'\s+', ' ', snippet)  # Normalize whitespace
            
            # Only add results with reasonable content
            if len(title) >= 5 and len(title) <= 200 and url.startswith('http'):
                results.append(SearchResult(
                    title=title,
                    snippet=snippet if snippet else "No description available",
                    url=url,
                    source="DuckDuckGo Search"
                ))
                
                if len(results) >= max_results:
                    break
        
        # If regex parsing fails, try a simpler approach
        if not results:
            # Fallback: extract any links with decent text
            link_pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]{10,100})</a>'
            links = re.findall(link_pattern, html_content)
            
            for url, title in links[:max_results]:
                # Skip internal DuckDuckGo links
                if not url.startswith('http') or 'duckduckgo.com' in url:
                    continue
                
                # Clean up title text
                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                clean_title = re.sub(r'\s+', ' ', clean_title)  # Normalize whitespace
                
                if len(clean_title) >= 10:  # Only titles with reasonable length
                    results.append(SearchResult(
                        title=clean_title,
                        snippet="Search result from web",
                        url=url,
                        source="DuckDuckGo Search"
                    ))
        
    except Exception as e:
        logger.error(f"Error parsing search results: {e}")
    
    return results


def _perform_web_search(query: str, max_results: int) -> List[SearchResult]:
    """
    Internal helper function to perform web search.
    
    This avoids code duplication between web_search and search_and_summarize tools.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        # Parse HTML to extract search results
        results = _parse_duckduckgo_results(response.text, max_results)
        return results
        
    except Exception as e:
        logger.error(f"Internal web search error: {e}")
        return []


def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Web Search & LLM MCP Server")
    logger.info("Available tools: web_search, llm_query, search_and_summarize")
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()