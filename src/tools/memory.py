"""
Memory tools for the MCP server

Streamlined memory tools that allow the AI to store and retrieve information 
about the user and previous conversations. Reduced from 8 tools to 3 for clarity.
"""

import logging
from typing import Dict, List, Optional
from ..core.memory import memory_manager

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
            
            fact_id = memory_manager.store_fact(content, category)
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
            # Search facts
            facts = memory_manager.retrieve_facts(query, limit=5)
            
            # Search conversation history  
            conversations = memory_manager.get_relevant_conversations(query, limit=3)
            
            # Get all preferences if query is about preferences
            preferences = {}
            if any(word in query.lower() for word in ['preference', 'setting', 'config', 'like', 'prefer']):
                preferences = memory_manager.get_all_preferences()
            
            # Build comprehensive response
            result_parts = []
            
            if facts:
                facts_text = "Stored information:\n"
                for fact in facts:
                    facts_text += f"• {fact.content}\n"
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
            # Search for matching facts to remove
            facts = memory_manager.retrieve_facts(description, limit=10)
            
            if not facts:
                return f"No information found matching: {description}"
            
            removed_count = 0
            removed_items = []
            
            for fact in facts:
                # Check if the fact content is similar to what user wants to forget
                if any(word in fact.content.lower() for word in description.lower().split()):
                    success = memory_manager.forget_fact(fact.id)
                    if success:
                        removed_count += 1
                        removed_items.append(fact.content[:50] + "..." if len(fact.content) > 50 else fact.content)
            
            if removed_count > 0:
                result = f"✓ Removed {removed_count} item(s) from memory:\n"
                for item in removed_items:
                    result += f"• {item}\n"
                return result.strip()
            else:
                return f"No matching information was removed for: {description}"
                
        except Exception as e:
            logger.error(f"Error in forget: {e}")
            return f"✗ Error removing information: {str(e)}"