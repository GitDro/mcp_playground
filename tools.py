"""
Function calling tools for MCP Playground

This module contains all the tool functions and their schemas for the
Ollama function calling system.
"""

from typing import List, Dict
from duckduckgo_search import DDGS
import httpx


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


def arxiv_search(query: str, max_results: int = 5) -> str:
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
        
        # Format results as markdown
        formatted_results = f"#### arXiv Papers for: {query}\n\n"
        for i, result in enumerate(filtered_results, 1):
            # Truncate abstract for readability
            abstract = result.summary.replace('\n', ' ').strip()
            if len(abstract) > 250:
                abstract = abstract[:247] + "..."
            
            formatted_results += f"**{i}. {result.title}**\n"
            formatted_results += f"**Authors**: {', '.join([author.name for author in result.authors[:3]])}"
            if len(result.authors) > 3:
                formatted_results += f" (and {len(result.authors) - 3} others)"
            formatted_results += "\n"
            formatted_results += f"**Published**: {result.published.strftime('%Y-%m-%d')}\n"
            formatted_results += f"**arXiv ID**: {result.entry_id.split('/')[-1]}\n"
            formatted_results += f"**Categories**: {', '.join(result.categories[:2])}\n"
            formatted_results += f"**Abstract**: {abstract}\n"
            formatted_results += f"**PDF**: {result.pdf_url}\n\n"
            formatted_results += "---\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"


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
                            "description": "Maximum number of papers to return (default: 5)"
                        }
                    },
                    "required": ["query"]
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
            max_results = arguments.get("max_results", 5)
            # Convert max_results to int if it's a string
            if isinstance(max_results, str):
                max_results = int(max_results)
            return arxiv_search(query, max_results)
        else:
            return f"Unknown function: {function_name}"
    except Exception as e:
        return f"Error executing {function_name}: {str(e)}"