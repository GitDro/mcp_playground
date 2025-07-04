"""
arXiv search and academic paper analysis tools
"""

import os
import tempfile
import logging
from typing import List, Optional
from datetime import datetime

from fastmcp import FastMCP
from ..core.models import PaperAnalysis
from ..core.utils import clean_markdown_text

logger = logging.getLogger(__name__)


def register_arxiv_tools(mcp: FastMCP):
    """Register arXiv-related tools with the MCP server"""
    
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
    
    @mcp.tool
    def arxiv_search(query: str, max_results: Optional[int] = 3) -> str:
        """Search arXiv database for academic papers and extract key insights including abstract, methodology, and conclusions. Returns detailed analysis of up to 10 papers (default: 3)."""
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
                                clean_point = clean_markdown_text(point)
                                formatted_results += f"- {clean_point}\n\n"
                            formatted_results += "\n"
                        
                        # Methods/Approach
                        if paper_content.methods and paper_content.methods.bullet_points:
                            formatted_results += "\n**Methods:**\n\n"
                            for point in paper_content.methods.bullet_points:
                                clean_point = clean_markdown_text(point)
                                formatted_results += f"- {clean_point}\n\n"
                            formatted_results += "\n"
                        
                        # Results
                        if paper_content.results and paper_content.results.bullet_points:
                            formatted_results += "\n**Results:**\n\n"
                            for point in paper_content.results.bullet_points:
                                clean_point = clean_markdown_text(point)
                                formatted_results += f"- {clean_point}\n\n"
                            formatted_results += "\n"
                        
                        # Discussion/Limitations
                        if paper_content.discussion and paper_content.discussion.bullet_points:
                            formatted_results += "\n**Discussion:**\n\n"
                            for point in paper_content.discussion.bullet_points:
                                clean_point = clean_markdown_text(point)
                                formatted_results += f"- {clean_point}\n\n"
                            formatted_results += "\n"
                    else:
                        formatted_results += "*PDF analysis unavailable - using abstract only.*\n\n"
                
                # Add separator with proper spacing to prevent markdown bleeding
                formatted_results += "\n---\n\n"
            
            return formatted_results
            
        except Exception as e:
            return f"Error searching arXiv: {str(e)}"