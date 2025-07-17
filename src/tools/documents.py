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
    def search_notes(query: str, limit: int = 5, tags: List[str] = None) -> str:
        """
        Search your stored notes using semantic similarity.
        
        Finds notes based on meaning, not just keywords. Perfect for finding
        that note about "house size" when you search for "room dimensions".
        
        Searches across all stored notes including manually edited files.
        
        Args:
            query: What you're looking for (e.g., "medication schedule", "house measurements")
            limit: Maximum number of results to return (default: 5)
            tags: Filter by specific tags
        
        Returns:
            Formatted list of matching notes with relevance scores
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
    def list_notes(limit: int = 20) -> str:
        """
        List all your stored notes.
        
        Shows both notes created with store_note() and any manually added 
        markdown files in the documents folder.
        
        Args:
            limit: Maximum number of notes to show
        
        Returns:
            Formatted list of all notes
        """
        try:
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