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


def extract_paper_content(pdf_url: str) -> Optional[Dict[str, str]]:
    """Extract structured content from arXiv PDF"""
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
            
            # Parse sections
            sections = _parse_paper_sections(full_text)
            return sections
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        print(f"Error extracting paper content: {e}")
        return None


def _parse_paper_sections(text: str) -> Dict[str, str]:
    """Parse academic paper text into structured sections"""
    # Clean and normalize text
    text = re.sub(r'\s+', ' ', text.strip())
    text_lower = text.lower()
    
    sections = {
        'introduction': '',
        'methodology': '',
        'results': '',
        'conclusion': '',
        'key_contributions': ''
    }
    
    # Define section patterns (case insensitive)
    section_patterns = {
        'introduction': [
            r'\b(?:1\.?\s*)?introduction\b',
            r'\bintroduction\b',
            r'\b1\.\s*background\b'
        ],
        'methodology': [
            r'\b(?:\d+\.?\s*)?(?:methodology|methods|approach|model|algorithm)\b',
            r'\b(?:\d+\.?\s*)?(?:experimental setup|implementation)\b'
        ],
        'results': [
            r'\b(?:\d+\.?\s*)?(?:results|experiments|evaluation|performance)\b',
            r'\b(?:\d+\.?\s*)?(?:experimental results|findings)\b'
        ],
        'conclusion': [
            r'\b(?:\d+\.?\s*)?(?:conclusion|conclusions|discussion)\b',
            r'\b(?:\d+\.?\s*)?(?:summary|future work)\b'
        ]
    }
    
    # Find section boundaries
    section_positions = {}
    for section_name, patterns in section_patterns.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, text_lower))
            if matches:
                # Take the first match
                section_positions[section_name] = matches[0].start()
                break
    
    # Extract content between sections
    sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
    
    for i, (section_name, start_pos) in enumerate(sorted_sections):
        # Find end position (start of next section or end of text)
        if i + 1 < len(sorted_sections):
            end_pos = sorted_sections[i + 1][1]
        else:
            end_pos = len(text)
        
        # Extract section content
        content = text[start_pos:end_pos].strip()
        
        # Clean section header and take first few sentences
        lines = content.split('\n')
        clean_lines = []
        for line in lines[1:]:  # Skip header line
            if line.strip() and not re.match(r'^\d+\.?\s*[A-Z]', line.strip()):
                clean_lines.append(line.strip())
        
        # Take first 3-4 sentences
        section_text = ' '.join(clean_lines)
        sentences = re.split(r'[.!?]+', section_text)
        key_sentences = [s.strip() for s in sentences[:4] if s.strip()]
        
        sections[section_name] = '. '.join(key_sentences)
        if sections[section_name]:
            sections[section_name] += '.'
    
    # Extract key contributions from abstract/introduction
    _extract_key_contributions(text, sections)
    
    return sections


def _extract_key_contributions(text: str, sections: Dict[str, str]):
    """Extract key contributions and findings"""
    # Look for contribution indicators
    contribution_patterns = [
        r'we propose',
        r'we present',
        r'we introduce',
        r'our contribution',
        r'our main contribution',
        r'we show that',
        r'we demonstrate'
    ]
    
    text_lower = text.lower()
    contributions = []
    
    for pattern in contribution_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            # Extract sentence containing the contribution
            start = match.start()
            # Find sentence boundaries
            sentence_start = text.rfind('.', 0, start) + 1
            sentence_end = text.find('.', start + len(pattern))
            if sentence_end == -1:
                sentence_end = len(text)
            
            sentence = text[sentence_start:sentence_end + 1].strip()
            if len(sentence) > 20 and len(sentence) < 300:
                contributions.append(sentence)
    
    # Take top 2-3 contributions
    sections['key_contributions'] = ' '.join(contributions[:3])


def _clean_markdown_text(text: str) -> str:
    """Clean text to prevent markdown formatting issues"""
    if not text:
        return text
    
    # Escape markdown characters that could cause formatting issues
    text = text.replace('#', '\\#')  # Escape headers
    text = text.replace('*', '\\*')  # Escape emphasis (except our own)
    text = text.replace('_', '\\_')  # Escape emphasis
    text = text.replace('`', '\\`')  # Escape code
    text = text.replace('[', '\\[')  # Escape links
    text = text.replace(']', '\\]')  # Escape links
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Limit length to prevent overly long sections
    if len(text) > 500:
        text = text[:497] + "..."
    
    return text


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
        
        # Format results as markdown with enhanced analysis for top papers
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
            formatted_results += f"**PDF**: {result.pdf_url}\n"
            
            # Deep analysis for top 2 papers
            if i <= 2:
                formatted_results += "\n**📄 Deep Analysis:**\n"
                paper_content = extract_paper_content(result.pdf_url)
                
                if paper_content:
                    if paper_content['key_contributions']:
                        clean_contrib = _clean_markdown_text(paper_content['key_contributions'])
                        formatted_results += f"*Key Contributions:* {clean_contrib}\n\n"
                    
                    if paper_content['methodology']:
                        clean_method = _clean_markdown_text(paper_content['methodology'])
                        formatted_results += f"*Approach:* {clean_method}\n\n"
                    
                    if paper_content['results']:
                        clean_results = _clean_markdown_text(paper_content['results'])
                        formatted_results += f"*Results:* {clean_results}\n\n"
                    
                    if paper_content['conclusion']:
                        clean_conclusion = _clean_markdown_text(paper_content['conclusion'])
                        formatted_results += f"*Conclusion:* {clean_conclusion}\n\n"
                else:
                    formatted_results += "*PDF analysis unavailable - using abstract only.*\n\n"
            
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