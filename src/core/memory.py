"""
Memory management system for MCP Playground

Provides working memory (session-based), short-term memory (cross-session),
and long-term memory (persistent) capabilities for the conversational AI system.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

logger = logging.getLogger(__name__)

class MemoryState(Enum):
    """Explicit memory states for prompt generation"""
    NO_MEMORY = "no_memory"
    HAS_PERSONAL_FACTS = "has_personal_facts"
    HAS_PREFERENCES = "has_preferences"
    HAS_BOTH = "has_both"
    EXPLICIT_MEMORY_QUERY = "explicit_memory_query"
    TOOL_FOCUSED_QUERY = "tool_focused_query"

@dataclass
class ConversationSummary:
    """Summary of a conversation session"""
    session_id: str
    timestamp: datetime
    summary: str
    topics: List[str]
    tool_usage: Dict[str, int]
    message_count: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationSummary':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class UserFact:
    """A stored fact about the user"""
    id: str
    content: str
    category: str
    timestamp: datetime
    relevance_score: float = 1.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserFact':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class UserPreference:
    """User preference setting"""
    key: str
    value: Any
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserPreference':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class MemoryManager:
    """Unified memory management system"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize memory manager with database connections"""
        self.cache_dir = cache_dir or self._get_cache_directory()
        self.db_path = os.path.join(self.cache_dir, 'memory.json')
        
        # Initialize TinyDB with caching middleware for better performance
        self.db = TinyDB(
            self.db_path,
            storage=CachingMiddleware(JSONStorage)
        )
        
        # Initialize tables
        self.conversations = self.db.table('conversations')
        self.facts = self.db.table('facts')
        self.preferences = self.db.table('preferences')
        self.interactions = self.db.table('interactions')
        
        # Initialize query objects
        self.ConversationQuery = Query()
        self.FactQuery = Query()
        self.PreferenceQuery = Query()
        
        # Memory configuration
        self.max_conversation_days = 7
        self.max_facts = 1000
        self.max_summary_length = 300
        
    def _get_cache_directory(self) -> str:
        """Get memory cache directory"""
        cache_dir = os.path.expanduser('~/.cache/mcp_playground')
        try:
            os.makedirs(cache_dir, exist_ok=True)
            return cache_dir
        except (OSError, PermissionError):
            return os.path.join(os.path.expanduser('~'), '.mcp_playground')
    
    # Working Memory (Session-based)
    def get_working_memory(self, session_id: str) -> Dict[str, Any]:
        """Get working memory for current session"""
        return {
            'conversation_history': [],
            'tool_usage': {},
            'context_keywords': [],
            'session_preferences': {}
        }
    
    def update_working_memory(self, session_id: str, key: str, value: Any) -> None:
        """Update working memory for current session"""
        # This is handled by Streamlit session_state in the app
        pass
    
    # Short-term Memory (Cross-session)
    def save_conversation_summary(self, session_id: str, messages: List[Dict], 
                                 tool_usage: Dict[str, int]) -> None:
        """Save conversation summary to short-term memory"""
        try:
            # Create summary from messages
            summary = self._create_conversation_summary(messages)
            topics = self._extract_topics(messages)
            
            conversation = ConversationSummary(
                session_id=session_id,
                timestamp=datetime.now(),
                summary=summary,
                topics=topics,
                tool_usage=tool_usage,
                message_count=len(messages)
            )
            
            # Save to database
            self.conversations.insert(conversation.to_dict())
            
            # Cleanup old conversations
            self._cleanup_old_conversations()
            
        except Exception as e:
            logger.error(f"Failed to save conversation summary: {e}")
    
    def get_relevant_conversations(self, query: str, limit: int = 3) -> List[ConversationSummary]:
        """Get relevant past conversations for context"""
        try:
            # Get recent conversations
            cutoff_date = datetime.now() - timedelta(days=self.max_conversation_days)
            recent_conversations = self.conversations.search(
                self.ConversationQuery.timestamp > cutoff_date.isoformat()
            )
            
            # Simple relevance scoring based on keyword matching
            scored_conversations = []
            query_words = set(query.lower().split())
            
            for conv_data in recent_conversations:
                conv = ConversationSummary.from_dict(conv_data)
                
                # Calculate relevance score
                summary_words = set(conv.summary.lower().split())
                topic_words = set(' '.join(conv.topics).lower().split())
                
                common_words = query_words.intersection(summary_words.union(topic_words))
                relevance_score = len(common_words) / len(query_words) if query_words else 0
                
                if relevance_score > 0:
                    scored_conversations.append((conv, relevance_score))
            
            # Sort by relevance and return top results
            scored_conversations.sort(key=lambda x: x[1], reverse=True)
            return [conv for conv, _ in scored_conversations[:limit]]
            
        except Exception as e:
            logger.error(f"Failed to get relevant conversations: {e}")
            return []
    
    # Long-term Memory (Persistent)
    def store_fact(self, content: str, category: str = 'general') -> str:
        """Store a fact in long-term memory"""
        try:
            fact_id = f"fact_{datetime.now().timestamp()}"
            fact = UserFact(
                id=fact_id,
                content=content,
                category=category,
                timestamp=datetime.now()
            )
            
            self.facts.insert(fact.to_dict())
            
            # Cleanup old facts if needed
            self._cleanup_old_facts()
            
            return fact_id
            
        except Exception as e:
            logger.error(f"Failed to store fact: {e}")
            return ""
    
    def retrieve_facts(self, query: str, category: Optional[str] = None, 
                      limit: int = 5) -> List[UserFact]:
        """Retrieve relevant facts from long-term memory"""
        try:
            # Build query conditions
            conditions = []
            if category:
                conditions.append(self.FactQuery.category == category)
            
            # Get all facts or filtered by category
            if conditions:
                fact_data = self.facts.search(conditions[0])
            else:
                fact_data = self.facts.all()
            
            # Score facts by relevance
            query_words = set(query.lower().split())
            scored_facts = []
            
            for fact_dict in fact_data:
                fact = UserFact.from_dict(fact_dict)
                content_words = set(fact.content.lower().split())
                
                # Calculate relevance score
                common_words = query_words.intersection(content_words)
                relevance_score = len(common_words) / len(query_words) if query_words else 0
                
                if relevance_score > 0:
                    scored_facts.append((fact, relevance_score))
            
            # Sort by relevance and return top results
            scored_facts.sort(key=lambda x: x[1], reverse=True)
            return [fact for fact, _ in scored_facts[:limit]]
            
        except Exception as e:
            logger.error(f"Failed to retrieve facts: {e}")
            return []
    
    def forget_fact(self, fact_id: str) -> bool:
        """Remove a fact from long-term memory"""
        try:
            result = self.facts.remove(self.FactQuery.id == fact_id)
            return len(result) > 0
        except Exception as e:
            logger.error(f"Failed to forget fact: {e}")
            return False
    
    # User Preferences
    def set_preference(self, key: str, value: Any) -> None:
        """Set user preference"""
        try:
            preference = UserPreference(
                key=key,
                value=value,
                timestamp=datetime.now()
            )
            
            # Remove existing preference with same key
            self.preferences.remove(self.PreferenceQuery.key == key)
            
            # Insert new preference
            self.preferences.insert(preference.to_dict())
            
        except Exception as e:
            logger.error(f"Failed to set preference: {e}")
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference"""
        try:
            result = self.preferences.search(self.PreferenceQuery.key == key)
            if result:
                preference = UserPreference.from_dict(result[0])
                return preference.value
            return default
        except Exception as e:
            logger.error(f"Failed to get preference: {e}")
            return default
    
    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all user preferences"""
        try:
            prefs = {}
            for pref_data in self.preferences.all():
                pref = UserPreference.from_dict(pref_data)
                prefs[pref.key] = pref.value
            return prefs
        except Exception as e:
            logger.error(f"Failed to get all preferences: {e}")
            return {}
    
    # Memory Building for Conversations - NEW MEMORY-FIRST ARCHITECTURE
    def build_memory_aware_prompt(self, current_query: str, 
                                 session_history: List[Dict]) -> Tuple[str, MemoryState, bool]:
        """Build memory-aware prompt with explicit state management
        
        Returns:
            Tuple of (system_prompt, memory_state, should_disable_memory_tools)
        """
        try:
            # Determine memory state and content
            memory_state = self._determine_memory_state(current_query)
            memory_content = self._get_memory_content(current_query, memory_state)
            
            # Generate state-specific system prompt
            system_prompt = self._generate_state_prompt(memory_state, memory_content)
            
            # Determine if memory tools should be disabled
            should_disable_memory_tools = self._should_disable_memory_tools(memory_state)
            
            return system_prompt, memory_state, should_disable_memory_tools
            
        except Exception as e:
            logger.error(f"Failed to build memory-aware prompt: {e}")
            return "", MemoryState.NO_MEMORY, False
    
    def _determine_memory_state(self, query: str) -> MemoryState:
        """Determine the appropriate memory state for the query"""
        query_lower = query.lower()
        
        # Check for tool-focused queries (skip memory injection)
        tool_keywords = [
            'youtube', 'video', 'analyze', 'summarize', 'transcript',
            'stock', 'price', 'crypto', 'market', 'finance', 'ticker',
            'weather', 'forecast', 'temperature', 'climate',
            'crime', 'safety', 'toronto', 'neighbourhood',
            'tide', 'tides', 'water', 'ocean',
            'arxiv', 'paper', 'research', 'academic', 'study',
            'search', 'web search', 'find', 'google',
            'url', 'website', 'link', 'analyze url'
        ]
        
        if any(keyword in query_lower for keyword in tool_keywords):
            return MemoryState.TOOL_FOCUSED_QUERY
        
        # Check for explicit memory requests
        memory_triggers = [
            'remember', 'recall', 'about me', 'my preferences', 
            'what do you know', 'stored information', 'my details',
            'personal info', 'user info', 'what do you remember',
            'what have you learned', 'tell me about myself'
        ]
        
        if any(trigger in query_lower for trigger in memory_triggers):
            return MemoryState.EXPLICIT_MEMORY_QUERY
        
        # Check what memory content we have
        facts = self.retrieve_facts(query, limit=3)
        preferences = self.get_all_preferences()
        
        has_facts = len(facts) > 0
        has_preferences = len(preferences) > 0
        
        if has_facts and has_preferences:
            return MemoryState.HAS_BOTH
        elif has_facts:
            return MemoryState.HAS_PERSONAL_FACTS
        elif has_preferences:
            return MemoryState.HAS_PREFERENCES
        else:
            return MemoryState.NO_MEMORY
    
    def _get_memory_content(self, query: str, memory_state: MemoryState) -> Dict[str, Any]:
        """Get relevant memory content based on state"""
        content = {
            'facts': [],
            'preferences': {},
            'conversations': []
        }
        
        if memory_state == MemoryState.TOOL_FOCUSED_QUERY:
            return content  # No memory content for tool queries
        
        # Get facts
        if memory_state == MemoryState.EXPLICIT_MEMORY_QUERY:
            # For explicit queries, get all facts
            content['facts'] = self.retrieve_facts("", limit=10)  # Empty query gets all facts
        else:
            # For general queries, get relevant facts
            content['facts'] = self.retrieve_facts(query, limit=3)
        
        # Get preferences
        if memory_state in [MemoryState.HAS_PREFERENCES, MemoryState.HAS_BOTH, MemoryState.EXPLICIT_MEMORY_QUERY]:
            content['preferences'] = self.get_all_preferences()
        
        # Get conversations for explicit memory queries
        if memory_state == MemoryState.EXPLICIT_MEMORY_QUERY:
            content['conversations'] = self.get_relevant_conversations(query, limit=2)
        
        return content
    
    def _generate_state_prompt(self, memory_state: MemoryState, memory_content: Dict[str, Any]) -> str:
        """Generate system prompt based on memory state"""
        base_date = datetime.now().strftime("%Y-%m-%d")
        
        if memory_state == MemoryState.NO_MEMORY:
            return f"""You are a helpful AI assistant. Today's date is {base_date}. You don't have any stored information about this user yet."""
        
        elif memory_state == MemoryState.TOOL_FOCUSED_QUERY:
            return f"""You are a helpful AI assistant. Today's date is {base_date}. This appears to be a tool-focused query, so I'm not including personal memory context to avoid irrelevant information."""
        
        elif memory_state == MemoryState.EXPLICIT_MEMORY_QUERY:
            memory_sections = []
            
            if memory_content['facts']:
                facts_text = "**Personal Facts:**\n"
                for fact in memory_content['facts']:
                    facts_text += f"• {fact.content}\n"
                memory_sections.append(facts_text)
            
            if memory_content['preferences']:
                prefs_text = "**User Preferences:**\n"
                for key, value in memory_content['preferences'].items():
                    prefs_text += f"• {key}: {value}\n"
                memory_sections.append(prefs_text)
            
            if memory_content['conversations']:
                conv_text = "**Past Conversation Topics:**\n"
                for conv in memory_content['conversations']:
                    conv_text += f"• {conv.summary}\n"
                memory_sections.append(conv_text)
            
            if memory_sections:
                stored_info = "\n\n".join(memory_sections)
                return f"""You are a helpful AI assistant. Today's date is {base_date}. The user is asking what you remember about them.

STORED INFORMATION ABOUT THE USER:
{stored_info}

Present this information in a natural, conversational way. This is what you know about them. Do NOT use the memory tools (remember, recall, forget) since you already have the information."""
            else:
                return f"""You are a helpful AI assistant. Today's date is {base_date}. The user is asking what you remember about them, but you don't have any stored information about them yet."""
        
        else:  # HAS_PERSONAL_FACTS, HAS_PREFERENCES, HAS_BOTH
            memory_sections = []
            
            if memory_content['facts']:
                facts_text = "**Stored Facts About This User:**\n"
                for fact in memory_content['facts']:
                    facts_text += f"• {fact.content}\n"
                memory_sections.append(facts_text)
            
            if memory_content['preferences']:
                prefs_text = "**User Preferences:**\n"
                for key, value in memory_content['preferences'].items():
                    prefs_text += f"• {key}: {value}\n"
                memory_sections.append(prefs_text)
            
            stored_info = "\n\n".join(memory_sections)
            return f"""You are a helpful AI assistant. Today's date is {base_date}. You have access to stored information about the user.

{stored_info}

Use this information naturally in your responses when relevant, but don't mention the memory system mechanics. You don't need to use memory tools since you already have the relevant information."""
    
    def _should_disable_memory_tools(self, memory_state: MemoryState) -> bool:
        """Determine if memory tools should be disabled"""
        # Disable memory tools when we're providing memory context
        # or when it's a tool-focused query
        return memory_state in [
            MemoryState.EXPLICIT_MEMORY_QUERY,
            MemoryState.HAS_PERSONAL_FACTS,
            MemoryState.HAS_PREFERENCES,
            MemoryState.HAS_BOTH,
            MemoryState.TOOL_FOCUSED_QUERY
        ]
    
    # Legacy method for backward compatibility
    def build_conversation_context(self, current_query: str, 
                                  session_history: List[Dict]) -> str:
        """Legacy method - use build_memory_aware_prompt instead"""
        system_prompt, memory_state, _ = self.build_memory_aware_prompt(current_query, session_history)
        # Extract just the memory content from the system prompt for backward compatibility
        if memory_state == MemoryState.NO_MEMORY or memory_state == MemoryState.TOOL_FOCUSED_QUERY:
            return ""
        
        # Return empty string - the new system handles this in the prompt
        return ""
    
    # Helper Methods
    def _create_conversation_summary(self, messages: List[Dict]) -> str:
        """Create a summary of the conversation"""
        try:
            # Extract main topics and key information
            text_content = []
            for msg in messages:
                if msg.get('role') == 'user':
                    text_content.append(msg.get('content', ''))
            
            # Simple summarization - take first sentence of each user message
            summary_parts = []
            for content in text_content:
                sentences = content.split('.')
                if sentences:
                    summary_parts.append(sentences[0].strip())
            
            summary = '. '.join(summary_parts[:3])  # First 3 topics
            
            # Limit summary length
            if len(summary) > self.max_summary_length:
                summary = summary[:self.max_summary_length] + "..."
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to create conversation summary: {e}")
            return "Conversation summary unavailable"
    
    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """Extract main topics from conversation"""
        try:
            topics = []
            for msg in messages:
                if msg.get('role') == 'user':
                    content = msg.get('content', '').lower()
                    # Simple topic extraction - look for key phrases
                    if any(word in content for word in ['weather', 'temperature', 'forecast']):
                        topics.append('weather')
                    if any(word in content for word in ['stock', 'price', 'market', 'crypto']):
                        topics.append('finance')
                    if any(word in content for word in ['youtube', 'video', 'watch']):
                        topics.append('youtube')
                    if any(word in content for word in ['search', 'find', 'google']):
                        topics.append('search')
                    if any(word in content for word in ['paper', 'research', 'arxiv']):
                        topics.append('research')
            
            return list(set(topics))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Failed to extract topics: {e}")
            return []
    
    def _cleanup_old_conversations(self) -> None:
        """Remove old conversations beyond retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.max_conversation_days)
            self.conversations.remove(
                self.ConversationQuery.timestamp < cutoff_date.isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to cleanup old conversations: {e}")
    
    def _cleanup_old_facts(self) -> None:
        """Remove old facts if we exceed the maximum"""
        try:
            all_facts = self.facts.all()
            if len(all_facts) > self.max_facts:
                # Sort by timestamp and remove oldest
                all_facts.sort(key=lambda x: x['timestamp'])
                facts_to_remove = all_facts[:-self.max_facts]
                
                for fact in facts_to_remove:
                    self.facts.remove(self.FactQuery.id == fact['id'])
        except Exception as e:
            logger.error(f"Failed to cleanup old facts: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        try:
            return {
                'conversations_stored': len(self.conversations.all()),
                'facts_stored': len(self.facts.all()),
                'preferences_stored': len(self.preferences.all()),
                'database_size': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                'cache_directory': self.cache_dir
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}

# Global memory manager instance
memory_manager = MemoryManager()