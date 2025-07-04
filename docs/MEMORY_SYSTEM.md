# Memory System Documentation

## Overview

The MCP Playground memory system provides persistent, intelligent memory capabilities that enable the AI to remember user information, preferences, and conversation context across sessions. The system is designed with a three-tier architecture inspired by human memory systems.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Playground Memory System             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────┐│
│  │  Working Memory │   │ Short-term Memory│   │ Long-term   ││
│  │   (Session)     │   │  (Cross-session) │   │   Memory    ││
│  │                 │   │                  │   │ (Persistent)││
│  │ • Chat History  │   │ • Conversation   │   │ • User Facts││
│  │ • Tool Usage    │   │   Summaries      │   │ • Preferences││
│  │ • Context Cache │   │ • Recent Topics  │   │ • Patterns  ││
│  │ • Session Prefs │   │ • Tool Patterns  │   │ • Profile   ││
│  └─────────────────┘   └─────────────────┘   └─────────────┘│
│           │                       │                     │   │
│           │                       │                     │   │
│           ▼                       ▼                     ▼   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Memory Manager Core                        ││
│  │                                                         ││
│  │ • Context Building    • Relevance Scoring              ││
│  │ • Automatic Cleanup   • Memory Consolidation           ││
│  │ • Keyword Matching    • Session Management             ││
│  └─────────────────────────────────────────────────────────┘│
│                               │                             │
│                               ▼                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  Storage Layer                          ││
│  │                                                         ││
│  │         TinyDB (Local JSON Database)                   ││
│  │         ~/.cache/mcp_playground/memory.json            ││
│  │                                                         ││
│  │ Tables:                                                 ││
│  │ • conversations  • facts  • preferences  • interactions││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                    Tool Integration                         │
│                                                             │
│ Memory Tools (8):           App Integration:                │
│ • remember_fact            • Auto context injection        │
│ • recall_information       • Session persistence          │
│ • forget_information       • Tool usage tracking          │
│ • set_user_preference      • Conversation summarization   │
│ • get_user_preferences     • Memory-aware prompts         │
│ • get_conversation_history                                │
│ • get_memory_stats                                        │
│ • build_context_from_memory                               │
└─────────────────────────────────────────────────────────────┘
```

## Memory Types

### 1. Working Memory (Session-based)
**Purpose**: Manage current conversation context and immediate state  
**Scope**: Single session/conversation  
**Storage**: Streamlit session_state  
**Lifetime**: Until page refresh or session end  

**Components**:
- `messages`: Current conversation history
- `tool_usage`: Count of tools used in current session
- `session_id`: Unique identifier for session
- `memory_context`: Cached context from long-term memory

### 2. Short-term Memory (Cross-session)
**Purpose**: Bridge conversations and maintain recent context  
**Scope**: 7 days (configurable)  
**Storage**: TinyDB `conversations` table  
**Lifetime**: Auto-cleaned after 7 days  

**Components**:
- **Conversation Summaries**: Condensed summaries of completed conversations
- **Topic Extraction**: Key topics discussed in each conversation  
- **Tool Usage Patterns**: Which tools were used and how often
- **Temporal Context**: When conversations occurred

**Data Structure**:
```python
@dataclass
class ConversationSummary:
    session_id: str
    timestamp: datetime
    summary: str           # AI-generated summary of conversation
    topics: List[str]      # Extracted key topics
    tool_usage: Dict[str, int]  # Tool usage counts
    message_count: int     # Number of messages in conversation
```

### 3. Long-term Memory (Persistent)
**Purpose**: Store permanent user information and preferences  
**Scope**: Indefinite (with size limits)  
**Storage**: TinyDB `facts` and `preferences` tables  
**Lifetime**: Until manually removed or system limits reached  

**Components**:
- **User Facts**: Important information about the user
- **Preferences**: User settings and behavioral preferences  
- **Interaction Patterns**: Long-term usage statistics

**Data Structures**:
```python
@dataclass
class UserFact:
    id: str
    content: str          # The actual fact/information
    category: str         # e.g., "personal", "work", "preference"
    timestamp: datetime
    relevance_score: float

@dataclass
class UserPreference:
    key: str             # e.g., "response_style", "preferred_model"
    value: Any           # The preference value
    timestamp: datetime
```

## Core Components

### Memory Manager (`src/core/memory.py`)

The `MemoryManager` class is the central orchestrator of the memory system.

**Key Methods**:

#### Context Building
```python
def build_conversation_context(self, current_query: str, session_history: List[Dict]) -> str:
    """
    Builds comprehensive context from all memory types for the current conversation.
    
    Process:
    1. Retrieve relevant facts based on query keywords
    2. Find related past conversations 
    3. Include current user preferences
    4. Format as structured context string
    """
```

#### Conversation Management
```python
def save_conversation_summary(self, session_id: str, messages: List[Dict], tool_usage: Dict[str, int]) -> None:
    """
    Saves a conversation summary when a session ends.
    
    Process:
    1. Extract key topics from conversation
    2. Generate concise summary (max 300 chars)
    3. Store tool usage statistics
    4. Clean up old conversations beyond retention period
    """
```

#### Fact Storage and Retrieval
```python
def store_fact(self, content: str, category: str = 'general') -> str:
    """Store a user fact with automatic ID generation and cleanup."""

def retrieve_facts(self, query: str, category: Optional[str] = None, limit: int = 5) -> List[UserFact]:
    """
    Retrieve relevant facts using keyword matching and relevance scoring.
    
    Scoring Algorithm:
    - Calculate intersection of query words with fact content words
    - Relevance = (common_words / total_query_words)
    - Sort by relevance score, return top N results
    """
```

### Memory Tools (`src/tools/memory.py`)

Eight specialized tools that allow the AI to interact with the memory system:

#### Core Memory Tools
1. **`remember_fact`**: Store important user information
2. **`recall_information`**: Search and retrieve stored facts
3. **`forget_information`**: Remove outdated information

#### Preference Management
4. **`set_user_preference`**: Store user preferences
5. **`get_user_preferences`**: Retrieve all preferences

#### Conversation History
6. **`get_conversation_history`**: Access past conversation summaries
7. **`build_context_from_memory`**: Auto-build context for queries

#### System Management
8. **`get_memory_stats`**: View memory system statistics

### App Integration (`app.py`)

#### Context Injection
The memory system automatically injects relevant context into conversations:

```python
# In chat_with_ollama_and_mcp()
memory_context = memory_manager.build_conversation_context(message, conversation_history)
if memory_context:
    base_prompt += f"\n\n{memory_context}"
```

#### Session Management
- **Session ID**: Unique UUID generated per session
- **Tool Tracking**: Automatic counting of tool usage
- **Summary Saving**: Conversations summarized when cleared

#### Auto-cleanup
- **Conversation Retention**: 7 days for short-term memory
- **Fact Limits**: Maximum 1000 facts with LRU cleanup
- **Database Optimization**: Cached TinyDB operations

## Database Schema

### TinyDB Tables

#### `conversations`
```json
{
  "session_id": "uuid-string",
  "timestamp": "2024-01-01T12:00:00",
  "summary": "User discussed Python programming and asked about best practices",
  "topics": ["python", "programming", "best-practices"],
  "tool_usage": {"web_search": 2, "arxiv_search": 1},
  "message_count": 8
}
```

#### `facts`
```json
{
  "id": "fact_1234567890.123",
  "content": "User is a software engineer at OpenAI",
  "category": "work",
  "timestamp": "2024-01-01T12:00:00",
  "relevance_score": 1.0
}
```

#### `preferences`
```json
{
  "key": "response_style",
  "value": "concise",
  "timestamp": "2024-01-01T12:00:00"
}
```

#### `interactions`
```json
{
  "tool_name": "web_search",
  "usage_count": 15,
  "last_used": "2024-01-01T12:00:00",
  "success_rate": 0.95
}
```

## Configuration

### Environment Variables
- `CACHE_DIRECTORY`: Override default cache location
- `MAX_CACHE_DAYS`: Conversation retention period (default: 7)

### Memory Limits
```python
# In MemoryManager.__init__()
self.max_conversation_days = 7      # Short-term memory retention
self.max_facts = 1000              # Long-term fact limit
self.max_summary_length = 300      # Summary character limit
```

## Usage Patterns

### Automatic Context Injection
Every user message triggers context building:
1. Extract keywords from user query
2. Search relevant facts (top 3)
3. Find related conversations (top 2)  
4. Include current preferences
5. Format as system prompt addition

### Conversation Lifecycle
1. **Start**: New session ID generated
2. **During**: Tool usage tracked, context injected
3. **End**: Conversation summarized and stored
4. **Cleanup**: Old data removed based on retention policies

### Memory Consolidation
- **Facts**: Duplicate detection and relevance scoring
- **Conversations**: Topic-based clustering and summarization
- **Preferences**: Latest value wins, historical tracking

## Debugging and Maintenance

### Memory Statistics
Use `get_memory_stats` tool to check:
- Number of stored conversations, facts, preferences
- Database file size and location
- Cache directory status

### Manual Database Access
```python
from src.core.memory import memory_manager

# Direct database access
conversations = memory_manager.conversations.all()
facts = memory_manager.facts.all()
preferences = memory_manager.preferences.all()

# Memory statistics
stats = memory_manager.get_memory_stats()
```

### Common Issues

#### Performance
- **Large fact database**: Implemented relevance scoring and limits
- **Memory context size**: Limited to essential information only
- **Database locking**: Using CachingMiddleware for TinyDB

#### Data Integrity  
- **Duplicate facts**: Check content similarity before storing
- **Stale conversations**: Automatic cleanup after retention period
- **Corrupted preferences**: Timestamp-based conflict resolution

### Backup and Recovery
```bash
# Backup memory database
cp ~/.cache/mcp_playground/memory.json ~/memory_backup_$(date +%Y%m%d).json

# Restore from backup  
cp ~/memory_backup_20240101.json ~/.cache/mcp_playground/memory.json
```

## Future Enhancements

### Semantic Search
- **Vector Embeddings**: Replace keyword matching with semantic similarity
- **Embedding Model**: Local sentence-transformers integration
- **Vector Database**: Upgrade from TinyDB to Chroma/FAISS

### Memory Consolidation
- **LLM Summarization**: Use local LLM for better conversation summaries
- **Fact Merging**: Detect and merge related facts automatically
- **Topic Modeling**: Advanced topic extraction and clustering

### Privacy Controls
- **Memory Categories**: User-controlled fact categorization
- **Retention Policies**: Per-category retention settings
- **Export/Import**: User data portability features

### Analytics
- **Usage Patterns**: Detailed analytics on memory effectiveness
- **Conversation Quality**: Metrics on context relevance
- **Tool Efficiency**: Memory-driven tool recommendation

---

## Integration Notes for Developers

When modifying the memory system:

1. **Always test context building** - Memory context affects every conversation
2. **Consider retention policies** - New data types need cleanup strategies  
3. **Monitor database size** - Implement limits for new memory types
4. **Preserve privacy** - All data stays local, no external transmission
5. **Handle errors gracefully** - Memory failures shouldn't break conversations

The memory system is designed to be unobtrusive but powerful - it works behind the scenes to make conversations more natural and personalized while maintaining user privacy and system performance.