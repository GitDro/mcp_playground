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


def _parse_paper_sections(text: str) -> Dict[str, List[str]]:
    """Parse academic paper text into structured bullet points"""
    # Clean and normalize text
    text = re.sub(r'\s+', ' ', text.strip())
    text_lower = text.lower()
    
    sections = {
        'introduction': [],
        'methods': [],
        'results': [],
        'discussion': []
    }
    
    # Enhanced section patterns with more variations
    section_patterns = {
        'introduction': [
            r'\b(?:\d+\.?\s*)?(?:introduction|background|motivation)\b',
            r'\babstract\b'
        ],
        'methods': [
            r'\b(?:\d+\.?\s*)?(?:methodology|methods|approach|model|algorithm|architecture)\b',
            r'\b(?:\d+\.?\s*)?(?:experimental setup|implementation|design)\b'
        ],
        'results': [
            r'\b(?:\d+\.?\s*)?(?:results|experiments|evaluation|performance|findings)\b',
            r'\b(?:\d+\.?\s*)?(?:experimental results|empirical)\b'
        ],
        'discussion': [
            r'\b(?:\d+\.?\s*)?(?:discussion|conclusion|conclusions|limitations)\b',
            r'\b(?:\d+\.?\s*)?(?:future work|analysis|related work)\b'
        ]
    }
    
    # Find section boundaries
    section_positions = {}
    for section_name, patterns in section_patterns.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, text_lower))
            if matches:
                section_positions[section_name] = matches[0].start()
                break
    
    # Extract content between sections
    sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
    
    for i, (section_name, start_pos) in enumerate(sorted_sections):
        # Find end position
        if i + 1 < len(sorted_sections):
            end_pos = sorted_sections[i + 1][1]
        else:
            end_pos = min(start_pos + 3000, len(text))  # Limit section length
        
        content = text[start_pos:end_pos]
        bullet_points = _extract_key_points_with_llm(content, section_name)
        sections[section_name] = bullet_points[:3]  # Max 3 points per section
    
    return sections


def _extract_key_points_with_llm(content: str, section_type: str) -> List[str]:
    """Use LLM to extract key bullet points from a section"""
    import requests
    
    # Limit content length to avoid overwhelming the LLM
    if len(content) > 2000:
        content = content[:2000] + "..."
    
    # Create section-specific prompts
    prompts = {
        'introduction': "Extract the key points from this research paper introduction. Output exactly 2-3 bullet points (one per line, starting with •) covering: main problem, key contribution, and novelty. Be concise and specific:\n\n",
        'methods': "Extract the key points from this methods section. Output exactly 2-3 bullet points (one per line, starting with •) covering: novel techniques, key innovations, and unique aspects. Be concise and specific:\n\n",
        'results': "Extract the key points from this results section. Output exactly 2-3 bullet points (one per line, starting with •) covering: performance improvements, comparisons, and significant findings. Include metrics when available:\n\n",
        'discussion': "Extract the key points from this discussion/conclusion. Output exactly 2-3 bullet points (one per line, starting with •) covering: main conclusions, limitations, and future work. Be concise and specific:\n\n"
    }
    
    prompt = prompts.get(section_type, "Summarize the key points from this text in 2-3 bullet points:\n\n")
    full_prompt = prompt + content
    
    try:
        # Call Ollama API for analysis
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",  # Use a fast model for analysis
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for focused analysis
                    "num_predict": 300   # Limit response length
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json().get('response', '')
            # Parse bullet points from LLM response
            bullet_points = _parse_llm_bullet_points(result)
            return bullet_points[:3]  # Max 3 points
        else:
            print(f"LLM analysis failed with status {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error in LLM analysis: {e}")
        return []


def _parse_llm_bullet_points(response: str) -> List[str]:
    """Parse bullet points from LLM response"""
    points = []
    
    # Split by common bullet point markers
    lines = response.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Remove common bullet markers
        if line.startswith(('•', '*', '-', '1.', '2.', '3.')):
            # Remove the marker and clean up
            clean_line = re.sub(r'^[•*\-\d\.]\s*', '', line).strip()
            if len(clean_line) > 20 and len(clean_line) < 300:
                points.append(clean_line)
        elif len(line) > 30 and len(line) < 300 and len(points) < 3:
            # If it's a substantial line without explicit bullets
            points.append(line)
    
    # If no bullet points found, try to split by sentences
    if not points:
        sentences = re.split(r'[.!?]+', response)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 30 and len(sentence) < 300:
                points.append(sentence + '.')
                if len(points) >= 3:
                    break
    
    return points




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
                    # Introduction/Background
                    if paper_content['introduction'] and any(paper_content['introduction']):
                        formatted_results += "*Introduction:*\n"
                        for point in paper_content['introduction']:
                            if point and len(point.strip()) > 20:
                                clean_point = _clean_markdown_text(point)
                                formatted_results += f"• {clean_point}\n"
                        formatted_results += "\n"
                    
                    # Methods/Approach
                    if paper_content['methods'] and any(paper_content['methods']):
                        formatted_results += "*Methods:*\n"
                        for point in paper_content['methods']:
                            if point and len(point.strip()) > 20:
                                clean_point = _clean_markdown_text(point)
                                formatted_results += f"• {clean_point}\n"
                        formatted_results += "\n"
                    
                    # Results
                    if paper_content['results'] and any(paper_content['results']):
                        formatted_results += "*Results:*\n"
                        for point in paper_content['results']:
                            if point and len(point.strip()) > 20:
                                clean_point = _clean_markdown_text(point)
                                formatted_results += f"• {clean_point}\n"
                        formatted_results += "\n"
                    
                    # Discussion/Limitations
                    if paper_content['discussion'] and any(paper_content['discussion']):
                        formatted_results += "*Discussion:*\n"
                        for point in paper_content['discussion']:
                            if point and len(point.strip()) > 20:
                                clean_point = _clean_markdown_text(point)
                                formatted_results += f"• {clean_point}\n"
                        formatted_results += "\n"
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