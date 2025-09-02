"""
Memory tools for the MCP server

Streamlined memory tools that allow the AI to store and retrieve information 
about the user and previous conversations. Uses vector-based semantic search
with ChromaDB and Ollama embeddings for better understanding.
"""

import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Check if vector memory should be disabled (for cloud deployment)
DISABLE_VECTOR_MEMORY = os.getenv("DISABLE_VECTOR_MEMORY", "false").lower() == "true"

if not DISABLE_VECTOR_MEMORY:
    try:
        from ..core.vector_memory import vector_memory_manager
        logger.info("Vector memory enabled - full functionality available")
    except Exception as e:
        logger.warning(f"Vector memory unavailable: {e}")
        DISABLE_VECTOR_MEMORY = True
        vector_memory_manager = None
else:
    vector_memory_manager = None
    logger.info("Vector memory disabled - memory tools will return friendly messages")

def register_memory_tools(mcp):
    """Register memory tools with cloud-aware fallbacks"""
    
    @mcp.tool(description="Remember conversation context and user preferences")
    def remember(content: str) -> str:
        """
        Store conversation context and preferences. Use for ongoing chat context only.
        NOT for articles, documents, or long-term knowledge - use store_note instead.
        
        Args:
            content: Conversation context or preference to remember (e.g., "I like coffee", "I work at Microsoft")
        """
        if DISABLE_VECTOR_MEMORY or not vector_memory_manager:
            return "💭 Memory storage is not available in cloud mode. I can only remember things within this conversation. For permanent storage, use the 'store_note' tool instead!"
        
        try:
            # Auto-categorize based content keywords
            content_lower = content.lower()
            if any(word in content_lower for word in ['prefer', 'like', 'favorite', 'style', 'want']):
                category = 'preference'
            elif any(word in content_lower for word in ['work', 'job', 'company', 'career', 'profession']):
                category = 'work'
            elif any(word in content_lower for word in ['live', 'location', 'address', 'home', 'family']):
                category = 'personal'
            elif any(word in content_lower for word in ['model', 'tool', 'setting', 'config']):
                category = 'preference'
            else:
                category = 'general'
            
            fact_id = vector_memory_manager.store_fact(content, category)
            if fact_id:
                return f"✓ Remembered: {content}\n\nThis information will be automatically included in future conversations when relevant."
            else:
                return "✗ Failed to store the information"
                
        except Exception as e:
            logger.error(f"Error in remember: {e}")
            return f"✗ Error storing information: {str(e)}"
    
    @mcp.tool(description="Recall conversation context and user preferences")
    def recall(query: str) -> str:
        """
        Show stored conversation context and preferences in bullet points.
        NOT for documents or articles - use search_documents instead.
        
        Args:
            query: What to recall (typically "what do you remember about me", "my preferences")
        """
        if DISABLE_VECTOR_MEMORY or not vector_memory_manager:
            return "💭 Memory recall is not available in cloud mode. I can only remember things from this conversation. For searching saved documents, use the 'search_documents' tool instead!"
        
        try:
            # Get all stored facts and present them simply
            all_facts = vector_memory_manager.get_all_facts()
            preferences = vector_memory_manager.get_all_preferences()
            
            result_parts = []
            
            if all_facts:
                facts_text = "What I remember about you:\n"
                for fact in all_facts:
                    facts_text += f"• {fact.content}\n"
                result_parts.append(facts_text.strip())
            
            if preferences:
                prefs_text = "Your preferences:\n"
                for key, value in preferences.items():
                    prefs_text += f"• {key}: {value}\n"
                result_parts.append(prefs_text.strip())
            
            if not result_parts:
                return "I don't have any stored information about you yet."
            
            return "\n\n".join(result_parts)
            
        except Exception as e:
            logger.error(f"Error in recall: {e}")
            return f"✗ Error retrieving information: {str(e)}"
    
    @mcp.tool(description="Delete conversation memory and preferences")
    def forget(description: str) -> str:
        """
        DANGEROUS: Remove conversation memory and preferences.
        
        WARNING: This permanently deletes information. Use with extreme caution.
        ONLY use when user explicitly and clearly requests deletion.
        NEVER use this tool automatically or based on unclear requests.
        
        For deleting saved documents/articles: Use document management tools instead.
        
        Confirmation required: Always confirm what will be deleted before proceeding.
        
        Examples of valid requests:
        - User says: "Please forget my communication preferences"
        - User says: "Delete my work information from memory"
        
        Args:
            description: Specific description of what conversation memory to remove
        
        Returns:
            Success message indicating what was removed
        """
        if DISABLE_VECTOR_MEMORY or not vector_memory_manager:
            return "💭 Memory deletion is not available in cloud mode. There are no stored memories to delete. For deleting saved documents, use the document management tools instead!"
        
        try:
            # Safety check: require explicit confirmation words
            description_lower = description.lower()
            confirmation_words = ['forget', 'remove', 'delete', 'clear']
            if not any(word in description_lower for word in confirmation_words):
                return f"⚠️ SAFETY: Deletion requires explicit confirmation. Please include words like 'forget', 'remove', or 'delete' in your request.\nExample: 'forget my work information'"
            
            # First, show what would be deleted (dry run)
            matching_facts = vector_memory_manager.retrieve_facts_semantic(description, limit=10, min_similarity=0.3)
            potential_deletions = []
            
            for fact in matching_facts:
                if any(word in fact.content.lower() for word in description.lower().split()):
                    preview = fact.content[:100] + "..." if len(fact.content) > 100 else fact.content
                    potential_deletions.append(preview)
            
            if not potential_deletions:
                return f"No matching information found for: {description}"
            
            # Show what would be deleted and require confirmation
            if len(potential_deletions) > 1:
                preview_text = f"⚠️ WARNING: This will permanently delete {len(potential_deletions)} items:\n"
                for i, item in enumerate(potential_deletions[:3], 1):  # Show first 3
                    preview_text += f"{i}. {item}\n"
                if len(potential_deletions) > 3:
                    preview_text += f"... and {len(potential_deletions) - 3} more items\n"
                preview_text += f"\nTo confirm deletion, user must explicitly say 'yes, delete these memories' or similar."
                return preview_text
            
            # For single item, proceed with deletion
            success, removed_items = vector_memory_manager.forget_fact(description)
            
            if success and removed_items:
                result = f"✓ Removed {len(removed_items)} item(s) from memory:\n"
                for item in removed_items:
                    result += f"• {item}\n"
                return result.strip()
            else:
                return f"No matching information was found to remove for: {description}"
                
        except Exception as e:
            logger.error(f"Error in forget: {e}")
            return f"✗ Error removing information: {str(e)}"