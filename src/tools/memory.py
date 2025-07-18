"""
Memory tools for the MCP server

Streamlined memory tools that allow the AI to store and retrieve information 
about the user and previous conversations. Uses vector-based semantic search
with ChromaDB and Ollama embeddings for better understanding.
"""

import logging
from typing import Dict, List, Optional
from ..core.vector_memory import vector_memory_manager

logger = logging.getLogger(__name__)

def register_memory_tools(mcp):
    """Register streamlined memory tools with the FastMCP server"""
    
    @mcp.tool(description="Store conversation context and user preferences")
    def remember(content: str) -> str:
        """
        Store conversation context and preferences. Use for ongoing chat context only.
        
        Args:
            content: Conversation context or preference to remember
        """
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
    
    @mcp.tool(description="Show stored conversation context and preferences")
    def recall(query: str) -> str:
        """
        Show stored conversation context and preferences in bullet points.
        
        Args:
            query: What to recall (typically "what do you remember about me")
        """
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
    
    @mcp.tool(description="Remove conversation memory and preferences (DANGEROUS)")
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