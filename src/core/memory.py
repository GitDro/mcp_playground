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
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

logger = logging.getLogger(__name__)

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
    
    # Memory Building for Conversations
    def build_conversation_context(self, current_query: str, 
                                  session_history: List[Dict]) -> str:
        """Build context from memories for conversation with privacy protection"""
        try:
            # Privacy protection: Skip memory injection for tool-focused queries
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
            
            query_lower = current_query.lower()
            if any(keyword in query_lower for keyword in tool_keywords):
                # This is a tool-focused query, don't inject personal memory
                return ""
            
            # Check for explicit memory requests
            memory_triggers = [
                'remember', 'recall', 'about me', 'my preferences', 
                'what do you know', 'stored information', 'my details',
                'personal info', 'user info'
            ]
            
            is_explicit_memory_request = any(trigger in query_lower for trigger in memory_triggers)
            
            context_parts = []
            
            # Add relevant facts with higher threshold for non-explicit requests
            if is_explicit_memory_request:
                # Lower threshold for explicit memory requests
                relevant_facts = self.retrieve_facts(current_query, limit=5)
            else:
                # Much higher threshold for general conversation to avoid irrelevant memories
                relevant_facts = []
                potential_facts = self.retrieve_facts(current_query, limit=3)
                # Only include facts with very high relevance
                for fact in potential_facts:
                    fact_words = set(fact.content.lower().split())
                    query_words = set(query_lower.split())
                    overlap_ratio = len(fact_words.intersection(query_words)) / len(query_words)
                    if overlap_ratio > 0.4:  # Require 40%+ word overlap
                        relevant_facts.append(fact)
            
            if relevant_facts:
                if is_explicit_memory_request:
                    facts_text = "[MEMORY CONTEXT - Information about this user from previous conversations:]\n"
                else:
                    facts_text = "Stored information:\n"
                for fact in relevant_facts:
                    facts_text += f"• {fact.content}\n"
                context_parts.append(facts_text)
            
            # Skip past conversations and preferences for non-explicit requests to reduce noise
            if is_explicit_memory_request:
                # Add relevant past conversations
                relevant_conversations = self.get_relevant_conversations(current_query, limit=2)
                if relevant_conversations:
                    conv_text = "Related past conversations:\n"
                    for conv in relevant_conversations:
                        conv_text += f"• {conv.summary}\n"
                    context_parts.append(conv_text)
                
                # Add user preferences
                preferences = self.get_all_preferences()
                if preferences:
                    pref_text = "User preferences:\n"
                    for key, value in preferences.items():
                        pref_text += f"• {key}: {value}\n"
                    context_parts.append(pref_text)
                
                # Add specific instruction for explicit memory queries
                if context_parts:
                    context_parts.append("\n[INSTRUCTION: The user is asking about stored information. Based on the memory context above, tell them what you know about them in a natural, conversational way.]")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to build conversation context: {e}")
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