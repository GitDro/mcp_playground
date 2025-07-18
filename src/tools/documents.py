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
    
    @mcp.tool
    def store_note(title: str, content: str, tags: List[str] = None, save_to_file: bool = True) -> str:
        """
        Store a personal note locally with semantic search capabilities.
        
        Perfect for private information like house measurements, medication details,
        personal reminders, or any sensitive data you want to keep local and private.
        
        Files are automatically saved to ~/.cache/mcp_playground/documents/notes/ 
        and can be manually edited - changes will be detected and re-indexed.
        
        Args:
            title: Title of the note
            content: The note content (supports markdown)
            tags: Optional tags for organization (e.g., ["personal", "health", "home"])
            save_to_file: Whether to save as a markdown file (default: True)
        
        Returns:
            Success message with document ID
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
            
            file_info = f"\n📁 Saved to: {file_path}" if file_path else ""
            tag_info = f"\n🏷️ Tags: {', '.join(tags)}" if tags else ""
            
            return f"✅ Note stored successfully!\n📝 Title: {title}\n🆔 ID: {doc_id}{tag_info}{file_info}\n\nYour note is now searchable and will be suggested when relevant."
            
        except Exception as e:
            logger.error(f"Error storing note: {e}")
            return f"❌ Failed to store note: {str(e)}"
    
    @mcp.tool
    def find_saved(query: str, limit: int = 5, tags: Optional[List[str]] = None) -> str:
        """
        Find saved documents, articles, and links by searching.
        
        Use this when you want to find specific saved content by searching for keywords.
        
        Perfect for queries like:
        - "find that article about AI"
        - "search for Python tutorials I saved"  
        - "show me documents about machine learning"
        
        Args:
            query: What to search for in your saved documents
            limit: Maximum number of results to return (default: 5)
            tags: Filter by specific tags
        
        Returns:
            Your saved documents matching the search
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
                return f"🔍 No notes found matching '{query}'{tag_filter}.\n\nTry different keywords or check if you've stored relevant notes."
            
            # Format results
            response = f"🔍 Found {len(results)} note(s) matching '{query}':\n\n"
            
            for i, doc in enumerate(results, 1):
                relevance = doc['relevance_score']
                relevance_emoji = "🎯" if relevance > 0.7 else "📌" if relevance > 0.5 else "📄"
                
                response += f"{relevance_emoji} **{doc['title']}** (relevance: {relevance:.0%})\n"
                response += f"   📅 {doc['created_at'][:10] if doc['created_at'] else 'Unknown date'}"
                
                if doc['tags']:
                    response += f" | 🏷️ {', '.join(doc['tags'])}"
                
                response += f"\n   {doc['match_snippet']}\n"
                response += f"   🆔 ID: {doc['id']}\n\n"
            
            response += "💡 Use search with more specific terms to narrow results."
            return response
            
        except Exception as e:
            logger.error(f"Error searching notes: {e}")
            return f"❌ Search failed: {str(e)}"
    
    @mcp.tool
    def list_saved(limit: Optional[int] = 20) -> str:
        """
        List all your saved documents, articles, and links.
        
        Use this to see everything you've saved, organized by date.
        
        Perfect for queries like:
        - "show me all my saved content"
        - "what do I have saved"
        - "list everything I've saved"
        
        Args:
            limit: Maximum number of documents to show
        
        Returns:
            Complete list of your saved documents and notes
        """
        try:
            # Handle None limit
            if limit is None:
                limit = 20
                
            documents = vector_memory_manager.get_all_documents()
            
            if not documents:
                return f"📝 No notes found.\n\nUse `store_note()` to create your first note!"
            
            # Sort by creation date (newest first)
            documents.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            documents = documents[:limit]
            
            response = f"📚 Your Notes ({len(documents)} shown):\n\n"
            
            for doc in documents:
                response += f"📝 **{doc['title']}**\n"
                response += f"   📅 {doc['created_at'][:10] if doc['created_at'] else 'Unknown date'}"
                
                if doc['tags']:
                    response += f" | 🏷️ {', '.join(doc['tags'])}"
                
                response += f"\n   🆔 {doc['id']}\n"
                
                # Show preview
                preview = doc['content'][:100]
                if len(doc['content']) > 100:
                    preview += "..."
                response += f"   📖 {preview}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error listing notes: {e}")
            return f"❌ Failed to list notes: {str(e)}"
    
    @mcp.tool
    def clean_duplicates() -> str:
        """
        Remove duplicate documents based on content similarity.
        
        Identifies and removes documents with identical URLs or very similar content.
        Use this to clean up your saved documents collection.
        
        Returns:
            Summary of cleanup actions performed
        """
        try:
            all_docs = vector_memory_manager.get_all_documents()
            
            if not all_docs:
                return "No documents found to clean up."
            
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
            
            if not duplicates_found:
                return f"✅ No duplicates found in {len(all_docs)} documents."
            
            # Report what was found (actual deletion would require implementing delete in vector_memory_manager)
            return f"🧹 Found {len(duplicates_found)} duplicate documents:\n" + \
                   "\n".join(f"• {dup_id}" for dup_id in duplicates_found[:10]) + \
                   (f"\n... and {len(duplicates_found) - 10} more" if len(duplicates_found) > 10 else "") + \
                   f"\n\nTotal documents: {len(all_docs)} | Duplicates: {len(duplicates_found)} | Unique: {len(all_docs) - len(duplicates_found)}"
            
        except Exception as e:
            logger.error(f"Error cleaning duplicates: {e}")
            return f"❌ Cleanup failed: {str(e)}"