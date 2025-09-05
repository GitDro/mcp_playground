"""
arXiv search and academic paper analysis tools
"""

import os
import tempfile
import logging
from typing import List, Optional
from datetime import datetime

from fastmcp import FastMCP
from ..core.utils import clean_markdown_text
from ..core.mcp_output import create_text_result
from fastmcp.tools.tool import ToolResult

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
    
    def _extract_paper_text(pdf_url: str) -> Optional[str]:
        """Extract raw text content from arXiv PDF for host LLM analysis"""
        try:
            import fitz  # PyMuPDF
            import httpx
            logger.info(f"Extracting text from PDF: {pdf_url}")
            
            # Download PDF to temporary file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                response = httpx.get(pdf_url, timeout=30, follow_redirects=True)
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
                
                # Clean up the text for better readability
                full_text = clean_markdown_text(full_text)
                
                # Truncate if too long (keep reasonable length for host LLM)
                if len(full_text) > 12000:  # Increased limit since host LLM will handle it
                    full_text = full_text[:12000] + "\n\n[Content truncated for length]"
                    logger.info(f"Text truncated to 12000 characters")
                
                return full_text
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            logger.error(f"Error extracting paper text: {e}")
            return None
    
    
    @mcp.tool(description="Search academic papers on arXiv with full text extraction")
    def arxiv_search(query: str, max_results: Optional[int] = 3) -> ToolResult:
        """Search arXiv database for academic papers and provide full text content for analysis. Returns paper metadata, abstracts, and full PDF text for up to 10 papers (default: 3). The host LLM can then analyze methodology, findings, and contributions.
        
        Args:
            query: Search terms for academic papers (e.g., "machine learning", "quantum computing")
            max_results: Maximum number of papers to retrieve (default: 3, max: 10)
        """
        try:
            import arxiv
            
            # Validate and sanitize inputs - handle None case explicitly
            if max_results is None:
                max_results = 3
            max_results = max(1, min(max_results, 10))
            
            if not query or not query.strip():
                return create_text_result("Error: Search query cannot be empty")
            
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
                return create_text_result(f"No relevant papers found for: {query}. Try different keywords or be more specific.")
            
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
                
                # Extract full paper text for top 1-2 papers for host LLM analysis
                if i <= 2:
                    paper_text = _extract_paper_text(result.pdf_url)
                    
                    if paper_text:
                        formatted_results += "\n**📄 Full Paper Text (for analysis):**\n"
                        formatted_results += f"```\n{paper_text}\n```\n\n"
                        formatted_results += "*Note: Above is the full paper content extracted for your analysis. Please provide insights on methodology, key findings, and contributions.*\n\n"
                    else:
                        formatted_results += "*PDF text extraction unavailable - analysis will be based on abstract only.*\n\n"
                
                # Add separator with proper spacing to prevent markdown bleeding
                formatted_results += "\n---\n\n"
            
            return create_text_result(formatted_results)
            
        except Exception as e:
            return create_text_result(f"Error searching arXiv: {str(e)}")