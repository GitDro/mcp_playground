# Memory Core Module

## Quick Reference

This module implements a three-tier memory system for the MCP Playground application. 

### Files in this directory:
- `memory.py` - Main memory management system
- `cache.py` - File-based caching utilities  
- `models.py` - Pydantic data models
- `utils.py` - General utility functions

## Memory System Overview

```
Working Memory (Session) → Short-term (7 days) → Long-term (Persistent)
      ↓                          ↓                       ↓
  Session State              Conversation           User Facts &
  Tool Usage                 Summaries              Preferences
  Context Cache              Topic Tracking         Interaction Patterns
```

## Key Classes

### MemoryManager
**Location**: `memory.py:78`  
**Purpose**: Central orchestrator for all memory operations

**Critical Methods**:
- `build_conversation_context()` - Injects memory into conversations
- `save_conversation_summary()` - Stores session summaries  
- `store_fact()` / `retrieve_facts()` - Manage user facts
- `set_preference()` / `get_preference()` - Handle user preferences

### Data Models  
**Location**: `memory.py:20-70`

```python
@dataclass
class ConversationSummary:
    session_id: str
    timestamp: datetime
    summary: str        # Max 300 chars
    topics: List[str]   # Extracted keywords
    tool_usage: Dict[str, int]
    message_count: int

@dataclass  
class UserFact:
    id: str
    content: str
    category: str       # "personal", "work", "preference", etc.
    timestamp: datetime
    relevance_score: float

@dataclass
class UserPreference:
    key: str           # "response_style", "preferred_model", etc.  
    value: Any
    timestamp: datetime
```

## Database Schema

**Storage**: TinyDB at `~/.cache/mcp_playground/memory.json`

**Tables**:
- `conversations` - Cross-session conversation summaries
- `facts` - Long-term user information storage
- `preferences` - User settings and behavioral preferences  
- `interactions` - Tool usage statistics and patterns

## Integration Points

### App Integration (`app.py`)
- Context injection in `chat_with_ollama_and_mcp()` at line ~154
- Session management and tool tracking in sync wrapper
- Conversation summary saving on session clear

### Tool Integration (`../tools/memory.py`)  
- 8 memory tools for AI interaction with memory system
- Direct access to MemoryManager instance
- Error handling and user-friendly responses

## Memory Algorithms

### Context Building (`memory.py:273`)
1. Extract keywords from current user query
2. Search relevant facts using keyword intersection scoring
3. Find related past conversations by topic/keyword matching  
4. Include current user preferences
5. Format as structured context string for system prompt

### Relevance Scoring (`memory.py:134`)
```python
# Simple keyword-based relevance for facts/conversations
query_words = set(query.lower().split())
content_words = set(content.lower().split())
common_words = query_words.intersection(content_words)
relevance_score = len(common_words) / len(query_words)
```

### Conversation Summarization (`memory.py:310`)
1. Extract user messages from conversation history
2. Take first sentence of each user message (up to 3)  
3. Join and truncate to max 300 characters
4. Extract topics using keyword pattern matching

## Configuration

### Memory Limits
```python
self.max_conversation_days = 7     # Short-term retention
self.max_facts = 1000             # Long-term fact limit  
self.max_summary_length = 300     # Summary character limit
```

### Topic Detection (`memory.py:329`)
Simple keyword-based topic extraction:
- "weather", "temperature" → "weather"  
- "stock", "price", "market" → "finance"
- "youtube", "video" → "youtube"
- etc.

## Maintenance Operations

### Automatic Cleanup
- `_cleanup_old_conversations()` - Removes conversations older than 7 days
- `_cleanup_old_facts()` - Removes oldest facts when limit exceeded  
- Called automatically after each save operation

### Manual Operations
```python
from src.core.memory import memory_manager

# View statistics
stats = memory_manager.get_memory_stats()

# Direct database access
conversations = memory_manager.conversations.all()
facts = memory_manager.facts.all()  
preferences = memory_manager.preferences.all()

# Manual cleanup
memory_manager._cleanup_old_conversations()
memory_manager._cleanup_old_facts()
```

## Error Handling

All public methods include try/catch blocks with logging:
- Database errors log warnings but don't crash the app
- Missing data returns empty results rather than exceptions
- Context building failures result in empty context strings

## Performance Considerations

- **TinyDB with CachingMiddleware** for faster database operations
- **Keyword-based search** avoids expensive semantic similarity calculations  
- **Relevance scoring limits** prevent processing large result sets
- **Automatic cleanup** prevents unlimited database growth

## Future Upgrade Path

For semantic search capability:
1. Add sentence-transformers dependency
2. Generate embeddings for facts/conversations during storage
3. Replace keyword matching with vector similarity search
4. Consider upgrading to Chroma or FAISS vector database

---

**See `docs/MEMORY_SYSTEM.md` for comprehensive documentation and architectural details.**