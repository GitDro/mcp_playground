"""
Document management tools for the MCP server

Simplified tools for storing and searching local documents with
vector-based semantic search capabilities.
"""

import logging
import os
from typing import List, Optional
from datetime import datetime
from ..core.vector_memory import vector_memory_manager

logger = logging.getLogger(__name__)

def register_document_tools(mcp):
    """Register simplified document management tools with the FastMCP server"""
    
    @mcp.tool(description="Store notes and documents for permanent knowledge base")
    def store_note(title: str, content: str, tags: List[str] = None, save_to_file: bool = True) -> str:
        """
        Store personal notes, articles, and documents with semantic search. Use for long-term knowledge.
        NOT for conversation context - use remember instead. Files saved to documents/notes/.
        
        Args:
            title: Note title
            content: Note content (supports markdown)
            tags: Optional tags for organization
            save_to_file: Save as markdown file (default: True)
        """
        try:
            # Determine file path if saving to file
            file_path = None
            if save_to_file:
                cache_dir = os.path.expanduser('~/.cache/mcp_playground/documents/notes')
                # Create safe filename from title
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{safe_title}.md"
                file_path = os.path.join(cache_dir, filename)
            
            # Store the document
            doc_id = vector_memory_manager.store_document(
                title=title,
                content=content,
                doc_type="note",
                tags=tags or [],
                file_path=file_path
            )
            
            file_info = f"\nSaved to: {file_path}" if file_path else ""
            tag_info = f"\nTags: {', '.join(tags)}" if tags else ""
            
            return f"Note stored successfully!\nTitle: {title}\nID: {doc_id}{tag_info}{file_info}\n\nYour note is now searchable and will be suggested when relevant."
            
        except Exception as e:
            logger.error(f"Error storing note: {e}")
            return f"Failed to store note: {str(e)}"
    
    @mcp.tool(description="Search documents and notes by topic with full content")
    def search_documents(query: str, limit: int = 5, tags: Optional[List[str]] = None) -> str:
        """
        Search saved documents by topic/keyword and return their full content. 
        Use when looking for specific documents (e.g., "find my ChatGPT note", "search my Python articles").
        NOT for conversation context - use recall instead.
        
        Args:
            query: What to search for (topic, keyword, title)
            limit: Maximum results (default: 5)
            tags: Filter by tags
        """
        try:
            # Search documents using vector similarity
            results = vector_memory_manager.search_documents(
                query=query,
                limit=limit,
                min_similarity=0.3,  # Lower threshold for personal notes
                tags=tags
            )
            
            if not results:
                tag_filter = f" with tags {tags}" if tags else ""
                return f"No documents found matching '{query}'{tag_filter}.\n\nTry different keywords or check if you've stored relevant documents."
            
            # Format results with clean excerpts
            response = f"Found {len(results)} document(s) matching '{query}':\n\n"
            
            for i, doc in enumerate(results, 1):
                relevance = doc['relevance_score']
                
                response += f"**{doc['title']}** (relevance: {relevance:.0%})\n"
                response += f"{doc['created_at'][:10] if doc['created_at'] else 'Unknown date'}"
                
                # Add domain from URL if available
                if doc.get('source_url'):
                    from urllib.parse import urlparse
                    try:
                        domain = urlparse(doc['source_url']).netloc.replace('www.', '')
                        response += f" | {domain}"
                    except:
                        pass
                
                if doc['tags']:
                    response += f" | {', '.join(doc['tags'])}"
                
                response += f"\nID: {doc['id']}\n"
                
                # Generate summary
                content = doc['content']
                sentences = content.replace('\n', ' ').split('. ')
                summary = '. '.join(sentences[:2])[:200]
                if len(summary) < len(content):
                    summary += "..."
                
                response += f"Summary: {summary}\n"
                
                # Show relevant excerpt from match_snippet
                if doc.get('match_snippet'):
                    excerpt = doc['match_snippet'][:300]
                    if len(doc['match_snippet']) > 300:
                        excerpt += "..."
                    response += f"Relevant excerpt: \"{excerpt}\"\n"
                
                response += "\n"
            return response
            
        except Exception as e:
            logger.error(f"Error searching notes: {e}")
            return f"Search failed: {str(e)}"
    
    @mcp.tool(description="List all saved documents chronologically")
    def show_all_documents(limit: Optional[int] = 20) -> str:
        """
        List ALL saved documents with full content, organized by date (newest first).
        Use when user asks to "show all notes", "list all documents", "see everything saved", etc.
        
        Args:
            limit: Maximum documents to show (default: 20)
        """
        try:
            # Handle None limit
            if limit is None:
                limit = 20
                
            documents = vector_memory_manager.get_all_documents()
            
            if not documents:
                return f"No documents found.\n\nUse store_note() to create your first document!"
            
            # Sort by creation date (newest first)
            documents.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            documents = documents[:limit]
            
            response = f"Your Saved Documents ({len(documents)} total):\n\n"
            
            for doc in documents:
                response += f"**{doc['title']}**\n"
                response += f"{doc['created_at'][:10] if doc['created_at'] else 'Unknown date'}"
                
                # Add domain from URL if available
                if doc.get('source_url'):
                    from urllib.parse import urlparse
                    try:
                        domain = urlparse(doc['source_url']).netloc.replace('www.', '')
                        response += f" | {domain}"
                    except:
                        pass
                
                if doc['tags']:
                    response += f" | {', '.join(doc['tags'])}"
                
                response += f"\nID: {doc['id']}\n"
                
                # Generate clean summary (first 2-3 sentences)
                content = doc['content']
                sentences = content.replace('\n', ' ').split('. ')
                summary = '. '.join(sentences[:3])[:300]
                if len(summary) < len(content):
                    summary += "..."
                
                response += f"Summary: {summary}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error listing notes: {e}")
            return f"Failed to list documents: {str(e)}"
    
    def _find_duplicates(self) -> List[str]:
        """
        Internal method to find duplicate documents.
        Returns list of duplicate document IDs to be removed.
        """
        try:
            all_docs = vector_memory_manager.get_all_documents()
            
            if not all_docs:
                return []
            
            # Group by URL for exact duplicates
            url_groups = {}
            content_hashes = {}
            duplicates_found = []
            
            for doc in all_docs:
                source_url = doc.get('source_url')
                
                # Check URL duplicates
                if source_url:
                    if source_url in url_groups:
                        duplicates_found.append(doc['id'])
                        logger.info(f"Found URL duplicate: {doc['id']} (URL: {source_url})")
                    else:
                        url_groups[source_url] = doc['id']
                
                # Check content hash duplicates (for non-URL content)
                else:
                    import hashlib
                    content_hash = hashlib.md5(doc.get('content', '').encode()).hexdigest()
                    if content_hash in content_hashes:
                        duplicates_found.append(doc['id'])
                        logger.info(f"Found content duplicate: {doc['id']}")
                    else:
                        content_hashes[content_hash] = doc['id']
            
            return duplicates_found
            
        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            return []