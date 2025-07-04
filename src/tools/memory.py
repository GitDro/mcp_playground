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
            # Auto-categorize based on content keywords
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
                return f"✓ Remembered: {content}"
            else:
                return "✗ Failed to store the information"
                
        except Exception as e:
            logger.error(f"Error in remember: {e}")
            return f"✗ Error storing information: {str(e)}"
    
    @mcp.tool
    def recall(query: str) -> str:
        """
        Retrieve relevant information from memory about the user and past conversations.
        
        This tool searches across all stored information including user facts,
        preferences, and conversation history to find anything relevant to your query.
        
        Use this tool when you need to check what you know about the user or
        reference previous conversations.
        
        Examples:
        - "user preferences" - Get user's stored preferences
        - "work details" - Find work-related information
        - "machine learning" - Find facts and conversations about ML
        - "what do I know about this user?" - Get general user profile
        
        Args:
            query: What to search for in memory
        
        Returns:
            All relevant information found in memory
        """
        try:
            query_lower = query.lower()
            
            # Handle general "about me" or "what do you know" queries by returning everything
            general_queries = ['about me', 'what do you know', 'what do you recall', 'tell me about', 
                             'what do you remember', 'about this user', 'what have we discussed']
            
            is_general_query = any(phrase in query_lower for phrase in general_queries)
            
            if is_general_query:
                # Return all stored information for general queries
                all_facts = vector_memory_manager.get_all_facts()
                all_preferences = vector_memory_manager.get_all_preferences()
                recent_conversations = vector_memory_manager.get_relevant_conversations("", limit=3)
                
                result_parts = []
                
                if all_facts:
                    facts_text = "Stored information about you:\n"
                    for fact in all_facts:
                        facts_text += f"• {fact.content}\n"
                    result_parts.append(facts_text.strip())
                
                if all_preferences:
                    prefs_text = "Your preferences:\n"
                    for key, value in all_preferences.items():
                        prefs_text += f"• {key}: {value}\n"
                    result_parts.append(prefs_text.strip())
                
                if recent_conversations:
                    conv_text = "Recent conversation topics:\n"
                    for conv in recent_conversations:
                        conv_text += f"• {conv.timestamp.strftime('%Y-%m-%d')}: {conv.summary}\n"
                    result_parts.append(conv_text.strip())
                
                if not result_parts:
                    return "No information stored in memory yet."
                
                return "\n\n".join(result_parts)
            
            else:
                # For specific queries, use semantic search
                facts = vector_memory_manager.retrieve_facts_hybrid(query, limit=5)
                conversations = vector_memory_manager.get_relevant_conversations(query, limit=3)
                
                # Get all preferences if query is about preferences
                preferences = {}
                if any(word in query_lower for word in ['preference', 'setting', 'config', 'like', 'prefer']):
                    preferences = vector_memory_manager.get_all_preferences()
                
                # Build comprehensive response
                result_parts = []
                
                if facts:
                    facts_text = "Stored information:\n"
                    for fact in facts:
                        # Include relevance score for semantic matches
                        relevance_indicator = ""
                        if fact.relevance_score > 0.7:
                            relevance_indicator = " (highly relevant)"
                        elif fact.relevance_score > 0.4:
                            relevance_indicator = " (relevant)"
                        facts_text += f"• {fact.content}{relevance_indicator}\n"
                    result_parts.append(facts_text.strip())
                
                if preferences:
                    prefs_text = "User preferences:\n"
                    for key, value in preferences.items():
                        prefs_text += f"• {key}: {value}\n"
                    result_parts.append(prefs_text.strip())
                
                if conversations:
                    conv_text = "Related past conversations:\n"
                    for conv in conversations:
                        conv_text += f"• {conv.timestamp.strftime('%Y-%m-%d')}: {conv.summary}\n"
                    result_parts.append(conv_text.strip())
                
                if not result_parts:
                    return "No relevant information found in memory."
                
                return "\n\n".join(result_parts)
            
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