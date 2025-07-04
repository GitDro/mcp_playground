"""
Memory tools for the MCP server

These tools allow the AI to store and retrieve information about the user
and previous conversations, enabling persistent memory across sessions.
"""

import logging
from typing import Dict, List, Optional
from ..core.memory import memory_manager

logger = logging.getLogger(__name__)

def register_memory_tools(mcp):
    """Register memory tools with the FastMCP server"""
    
    @mcp.tool
    def remember_fact(content: str, category: str = "general") -> str:
        """
        Store an important fact about the user for future reference.
        
        Use this tool when the user shares personal information, preferences,
        or other details that should be remembered for future conversations.
        
        Args:
            content: The fact to remember (e.g., "User prefers concise answers")
            category: Category for the fact (e.g., "preference", "personal", "work")
        
        Returns:
            Success message with fact ID
        """
        try:
            fact_id = memory_manager.store_fact(content, category)
            if fact_id:
                return f"✓ Remembered: {content}"
            else:
                return "✗ Failed to store the fact"
        except Exception as e:
            logger.error(f"Error in remember_fact: {e}")
            return f"✗ Error storing fact: {str(e)}"
    
    @mcp.tool
    def recall_information(query: str, category: Optional[str] = None) -> str:
        """
        Retrieve relevant information from memory about the user.
        
        Use this tool to recall facts, preferences, or other stored information
        that might be relevant to the current conversation.
        
        Args:
            query: What to search for (e.g., "user preferences", "work details")
            category: Optional category to filter by
        
        Returns:
            Relevant information from memory
        """
        try:
            facts = memory_manager.retrieve_facts(query, category, limit=5)
            
            if not facts:
                return "No relevant information found in memory."
            
            result = "Relevant information from memory:\n"
            for fact in facts:
                result += f"• {fact.content} (category: {fact.category})\n"
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Error in recall_information: {e}")
            return f"✗ Error retrieving information: {str(e)}"
    
    @mcp.tool
    def forget_information(fact_id: str) -> str:
        """
        Remove specific information from memory.
        
        Use this tool when the user asks to forget something or when
        information becomes outdated.
        
        Args:
            fact_id: ID of the fact to forget
        
        Returns:
            Success or failure message
        """
        try:
            success = memory_manager.forget_fact(fact_id)
            if success:
                return f"✓ Forgotten information with ID: {fact_id}"
            else:
                return f"✗ Could not find information with ID: {fact_id}"
        except Exception as e:
            logger.error(f"Error in forget_information: {e}")
            return f"✗ Error removing information: {str(e)}"
    
    @mcp.tool
    def set_user_preference(key: str, value: str) -> str:
        """
        Set a user preference for future conversations.
        
        Use this tool to store user preferences about how they like to interact,
        what tools they prefer, response styles, etc.
        
        Args:
            key: Preference name (e.g., "response_style", "preferred_model")
            value: Preference value (e.g., "concise", "llama3.2")
        
        Returns:
            Success message
        """
        try:
            memory_manager.set_preference(key, value)
            return f"✓ Set preference: {key} = {value}"
        except Exception as e:
            logger.error(f"Error in set_user_preference: {e}")
            return f"✗ Error setting preference: {str(e)}"
    
    @mcp.tool
    def get_user_preferences() -> str:
        """
        Get all stored user preferences.
        
        Use this tool to check what preferences are currently stored
        and apply them to the conversation.
        
        Returns:
            List of all user preferences
        """
        try:
            preferences = memory_manager.get_all_preferences()
            
            if not preferences:
                return "No user preferences stored."
            
            result = "User preferences:\n"
            for key, value in preferences.items():
                result += f"• {key}: {value}\n"
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Error in get_user_preferences: {e}")
            return f"✗ Error retrieving preferences: {str(e)}"
    
    @mcp.tool
    def get_conversation_history(query: str) -> str:
        """
        Get summaries of relevant past conversations.
        
        Use this tool to recall what was discussed in previous sessions
        that might be relevant to the current conversation.
        
        Args:
            query: What to search for in past conversations
        
        Returns:
            Summaries of relevant past conversations
        """
        try:
            conversations = memory_manager.get_relevant_conversations(query, limit=3)
            
            if not conversations:
                return "No relevant past conversations found."
            
            result = "Relevant past conversations:\n"
            for conv in conversations:
                result += f"• {conv.timestamp.strftime('%Y-%m-%d')}: {conv.summary}\n"
                if conv.topics:
                    result += f"  Topics: {', '.join(conv.topics)}\n"
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Error in get_conversation_history: {e}")
            return f"✗ Error retrieving conversation history: {str(e)}"
    
    @mcp.tool
    def get_memory_stats() -> str:
        """
        Get statistics about the memory system.
        
        Use this tool to check how much information is stored
        and the status of the memory system.
        
        Returns:
            Memory system statistics
        """
        try:
            stats = memory_manager.get_memory_stats()
            
            result = "Memory system statistics:\n"
            result += f"• Conversations stored: {stats.get('conversations_stored', 0)}\n"
            result += f"• Facts stored: {stats.get('facts_stored', 0)}\n"
            result += f"• Preferences stored: {stats.get('preferences_stored', 0)}\n"
            result += f"• Database size: {stats.get('database_size', 0)} bytes\n"
            result += f"• Cache directory: {stats.get('cache_directory', 'unknown')}\n"
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Error in get_memory_stats: {e}")
            return f"✗ Error retrieving memory stats: {str(e)}"
    
    @mcp.tool
    def build_context_from_memory(current_query: str) -> str:
        """
        Build conversation context from stored memories.
        
        This tool automatically retrieves relevant facts, preferences,
        and conversation history to provide context for the current query.
        
        Args:
            current_query: The user's current question or request
        
        Returns:
            Contextual information from memory
        """
        try:
            context = memory_manager.build_conversation_context(
                current_query, 
                []  # Session history will be provided by the app
            )
            
            if not context:
                return "No relevant context found in memory."
            
            return f"Relevant context from memory:\n{context}"
            
        except Exception as e:
            logger.error(f"Error in build_context_from_memory: {e}")
            return f"✗ Error building context: {str(e)}"