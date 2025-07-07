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
    
    @mcp.tool
    def remember(content: str) -> str:
        """
        Store important information about the user for future conversations.
        
        Use this tool when the user shares personal information, preferences,
        work details, or anything else that should be remembered. The system
        will automatically categorize the information appropriately.
        
        Examples:
        - "User prefers concise responses" (preference)
        - "User works as a software engineer at OpenAI" (work)
        - "User lives in Toronto" (personal)
        - "User's favorite programming language is Python" (preference)
        
        Args:
            content: The information to remember about the user
        
        Returns:
            Success message confirming what was stored
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
    
    @mcp.tool
    def recall(query: str) -> str:
        """
        Search memory for specific information about the user.
        
        Use this tool when the user explicitly asks you to search memory
        or when you need to find specific stored information.
        
        Note: For "What do you remember about me?" queries, the memory system
        automatically provides stored facts in conversation context, so this
        tool may not be needed in those cases.
        
        Examples:
        - When user asks: "What do you remember about my work?"
        - When user asks: "What did we discuss about machine learning?"
        - For specific searches of stored facts and preferences
        
        Args:
            query: What to search for in memory
        
        Returns:
            Relevant stored information matching the query
        """
        try:
            # For "what do you remember about me" queries, return all facts
            query_lower = query.lower()
            general_queries = ['about me', 'what do you know', 'what do you recall', 'tell me about myself', 
                             'what do you remember', 'about this user']
            
            if any(phrase in query_lower for phrase in general_queries):
                # Return all stored information
                all_facts = vector_memory_manager.get_all_facts()
                preferences = vector_memory_manager.get_all_preferences()
                
                result_parts = []
                
                if all_facts:
                    facts_text = "Stored information about you:\n"
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
            
            # For specific queries, use semantic search
            facts = vector_memory_manager.retrieve_facts_semantic(query, limit=5)
            
            if not facts:
                return f"No stored information found matching '{query}'."
            
            result_text = "Stored information:\n"
            for fact in facts:
                result_text += f"• {fact.content}\n"
            
            return result_text.strip()
            
        except Exception as e:
            logger.error(f"Error in recall: {e}")
            return f"✗ Error retrieving information: {str(e)}"
    
    @mcp.tool
    def forget(description: str) -> str:
        """
        Remove information from memory based on a description.
        
        Use this tool only when the user explicitly asks to forget specific
        information. Provide a description of what to forget rather than
        technical IDs.
        
        Examples:
        - "forget my work details"
        - "remove information about my location"
        - "delete my preference for concise responses"
        
        Args:
            description: Description of what information to remove
        
        Returns:
            Success message indicating what was removed
        """
        try:
            # Use vector memory manager to forget facts
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