# Memory System Documentation

## Overview

The MCP Playground implements a sophisticated **vector-based memory system** that enables the AI to remember user information, preferences, and conversation context across sessions. The system uses **ChromaDB with Ollama embeddings** for semantic understanding and **TinyDB for exact matches**.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                Vector-Based Memory System                   │
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
│           ▼                       ▼                     ▼   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Vector Memory Manager                      ││
│  │                                                         ││
│  │ • Semantic Search     • Relevance Scoring              ││
│  │ • Embedding Generation• Memory Consolidation           ││
│  │ • Hybrid Retrieval    • Session Management             ││
│  └─────────────────────────────────────────────────────────┘│
│                               │                             │
│                               ▼                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  Hybrid Storage Layer                   ││
│  │                                                         ││
│  │  ChromaDB (Vector Search)    TinyDB (Exact Match)      ││
│  │  • User facts (semantic)     • Preferences (K-V)       ││
│  │  • nomic-embed-text          • Conversations (cache)   ││
│  │  • 768 dimensions            • Session data            ││
│  │  • Cosine similarity         • ~/.cache/memory.json   ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                    Tool Integration                         │
│                                                             │
│ Memory Tools (3):           App Integration:                │
│ • remember                 • Auto context injection        │
│ • recall                   • Session persistence          │
│ • forget                   • Tool usage tracking          │
│                            • Conversation summarization   │
│                            • Memory-aware prompts         │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### Files in src/core/:
- `vector_memory.py` - Vector-based memory manager with ChromaDB + Ollama
- `memory.py` - Original TinyDB memory manager (used for fallback)
- `cache.py` - File-based caching utilities  
- `models.py` - Pydantic data models
- `utils.py` - General utility functions

### Memory Tools (`src/tools/memory.py`)

**3 streamlined memory tools** for AI interaction:

1. **`remember`**: Store any important user information (auto-categorizes as work/personal/preference)
2. **`recall`**: Semantic search across all stored information - understands natural queries  
3. **`forget`**: Remove information by description, not technical IDs

**Key improvement**: Reduced from 8 confusing tools to 3 clear tools with distinct purposes.

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

### 3. Long-term Memory (Persistent)
**Purpose**: Store permanent user information with semantic search  
**Scope**: Indefinite (with size limits)  
**Storage**: ChromaDB with vector embeddings  
**Lifetime**: Until manually removed or system limits reached  

## Vector Search Implementation

### VectorMemoryManager (`src/core/vector_memory.py`)

**Key Classes**:

```python
@dataclass
class VectorFact:
    id: str
    content: str
    category: str
    timestamp: datetime
    relevance_score: float = 1.0

class OllamaEmbeddingFunction:
    """Custom embedding function using Ollama's nomic-embed-text model"""
    model_name = "nomic-embed-text"  # 768 dimensions, 8K context

class VectorMemoryManager:
    """Hybrid memory manager using ChromaDB + TinyDB"""
```

**Critical Methods**:
- `store_fact()` - Store with embeddings in ChromaDB + fallback to TinyDB
- `retrieve_facts_semantic()` - Vector similarity search  
- `retrieve_facts_hybrid()` - Combines semantic + keyword search
- `forget_fact()` - Remove by semantic description matching

### Semantic Search Algorithm

```python
# Query Processing Flow
def retrieve_facts_semantic(query: str, limit: int = 5):
    # 1. Generate query embedding
    query_embedding = ollama.embed(model='nomic-embed-text', input=query)
    
    # 2. Vector search in ChromaDB
    results = collection.query(
        query_texts=[query],
        n_results=limit,
        include=['documents', 'metadatas', 'distances']
    )
    
    # 3. Convert distance to similarity
    for distance in results['distances']:
        similarity = 1.0 - distance  # Cosine distance → similarity
        
    # 4. Filter by relevance threshold
    return facts where similarity > 0.1
```

### Relevance Scoring

- **High Relevance** (>70% similarity): Direct keyword matches, exact content
- **Medium Relevance** (40-70% similarity): Semantic relationships, related concepts  
- **Low Relevance** (10-40% similarity): Tangentially related content
- **Threshold**: 10% minimum to filter noise

**Example Results**:
- Query: "about me" → "User likes ice cream" = **43.5% similarity** ✅
- Query: "ice cream" → "User likes ice cream" = **85.0% similarity** ✅  
- Query: "work details" → "User works as software engineer" = **65.2% similarity** ✅

## App Integration (`app.py`)

### Context Injection
Memory context automatically injected into conversations:

```python
# In chat_with_ollama_and_mcp()
memory_context = memory_manager.build_conversation_context(message, conversation_history)
if memory_context:
    base_prompt += f"\n\n{memory_context}"
```

### Session Management
- **Session ID**: Unique UUID generated per session
- **Tool Tracking**: Automatic counting of tool usage
- **Summary Saving**: Conversations summarized when cleared
- **Hybrid Storage**: Facts in ChromaDB, preferences in TinyDB

### Smart Query Handling
- **General queries** ("about me"): Return all stored information
- **Specific queries** ("ice cream"): Semantic search with relevance scoring
- **Preference queries** ("settings"): Direct TinyDB lookup for speed
- **Fallback logic**: ChromaDB → TinyDB → empty results

## Database Schema

### ChromaDB Collections

#### `user_facts`
```python
{
    "id": "fact_1234567890.123",
    "document": "User likes ice cream",
    "metadata": {
        "category": "preference",
        "timestamp": "2024-01-01T12:00:00",
        "relevance_score": 1.0
    },
    "embedding": [0.1, -0.3, 0.8, ...]  # 768 dimensions
}
```

### TinyDB Tables  

#### `preferences`
```json
{
  "key": "response_style",
  "value": "concise", 
  "timestamp": "2024-01-01T12:00:00"
}
```

#### `conversations`
```json
{
  "session_id": "uuid-string",
  "timestamp": "2024-01-01T12:00:00", 
  "summary": "User discussed Python programming and asked about best practices",
  "topics": ["python", "programming", "best-practices"],
  "tool_usage": {"web_search": 2, "recall": 1},
  "message_count": 8
}
```

## Configuration & Performance

### Memory Limits
```python
# In VectorMemoryManager.__init__()
self.max_conversation_days = 7      # Short-term retention
self.max_facts = 1000              # Long-term fact limit  
self.min_similarity = 0.1          # Relevance threshold
```

### Performance Metrics
- **Embedding Generation**: ~200ms per query (local Ollama)
- **Vector Search**: ~50ms for 1000+ facts (ChromaDB)
- **Total Latency**: ~300ms for semantic memory lookup
- **Storage Overhead**: 768 floats per fact (minimal)

### Environment Variables
- `CACHE_DIRECTORY`: Override default cache location
- `MAX_CACHE_DAYS`: Conversation retention period (default: 7)

## Usage Patterns

### Automatic Context Injection
Every user message triggers context building:
1. Extract keywords from user query
2. Search relevant facts (top 3) via semantic similarity
3. Find related conversations (top 2) via keyword matching
4. Include current preferences from TinyDB
5. Format as system prompt addition

### Conversation Lifecycle
1. **Start**: New session ID generated, vector memory initialized
2. **During**: Tool usage tracked, semantic context injected per message
3. **End**: Conversation summarized and stored in both systems
4. **Cleanup**: Old data removed based on retention policies

### Tool Usage Examples
```python
# Store information
remember("User prefers morning meetings")  # Auto-categorized as "preference"

# Natural language queries  
recall("what do you know about my schedule preferences")  # Semantic search
recall("about me")  # Returns all stored facts

# Remove information
forget("schedule preferences")  # Finds and removes by description
```

## Debugging and Maintenance

### Memory Statistics
```python
stats = vector_memory_manager.get_memory_stats()
# Returns:
{
    'vector_facts_stored': 15,
    'chroma_path': '/Users/user/.cache/mcp_playground/chromadb',
    'embedding_model': 'nomic-embed-text',
    'tinydb_facts': 15,           # Hybrid storage
    'tinydb_conversations': 5,
    'tinydb_preferences': 3
}
```

### Common Issues

#### Performance
- **Large fact database**: Relevance scoring limits and ChromaDB indexing
- **Memory context size**: Limited to essential information (top 3 facts)
- **Embedding generation**: Local Ollama may be slower than cloud APIs

#### Connectivity
- **Ollama connection**: Graceful fallback to TinyDB if Ollama unavailable
- **Model availability**: Requires `ollama pull nomic-embed-text`
- **Database permissions**: Automatic fallback to temp directory

### Manual Database Access
```python
from src.core.vector_memory import vector_memory_manager

# Direct ChromaDB access
all_facts = vector_memory_manager.get_all_facts()
semantic_results = vector_memory_manager.retrieve_facts_semantic("query")

# Direct TinyDB access  
preferences = vector_memory_manager.get_all_preferences()
conversations = vector_memory_manager.get_relevant_conversations("topic")
```

## Future Enhancements

### Document RAG Extension
The current vector architecture provides foundation for:

1. **Document Ingestion**: PDF, Word, markdown processing with chunking
2. **Multi-Collection Search**: Personal docs, web bookmarks, conversation history
3. **Advanced Retrieval**: Hybrid search (vector + BM25), re-ranking, query expansion
4. **Privacy Controls**: Local encryption, user-controlled retention policies

### Semantic Improvements
1. **Better Embeddings**: Fine-tune models on user data
2. **Query Understanding**: Intent classification, entity extraction  
3. **Memory Consolidation**: Merge related facts, detect contradictions
4. **Context Awareness**: Time-based relevance, conversation threading

---

## Quick Start

```bash
# Install dependencies
uv add chromadb ollama

# Pull embedding model
ollama pull nomic-embed-text

# Test vector memory
from src.core.vector_memory import vector_memory_manager
vector_memory_manager.store_fact("User likes ice cream", "preference")
facts = vector_memory_manager.retrieve_facts_semantic("about me")
```

The vector memory system provides intelligent, semantic understanding that makes conversations more natural and personalized while maintaining privacy through local-only processing.