# Memory System Documentation - MVP Version

## Overview

The MCP Playground implements a **simple, effective memory system** that enables the AI to naturally remember user information across conversations. The system uses **ChromaDB with Ollama embeddings** for semantic search and **conversation history injection** for natural integration.

## MVP Architecture - Simple & Effective

```
┌─────────────────────────────────────────────────────────────────┐
│                 Simple Memory System (MVP)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐                    ┌─────────────────┐   │
│  │   User Query    │                    │ Conversation     │   │
│  │                 │                    │ History          │   │
│  │ "Any sci-fi     │ ─────────────────►│ Injection        │   │
│  │ book recs?"     │                    │                  │   │
│  └─────────────────┘                    │ IF similarity    │   │
│           │                              │ > 80%:           │   │
│           │                              │                  │   │
│           ▼                              │ Add fake         │   │
│  ┌─────────────────────────────────────────┐ │ conversation:    │   │
│  │     Semantic Search                 │ │ "Just so you     │   │
│  │                                     │ │ know, user       │   │
│  │ 1. Embed query with nomic-embed    │ │ likes sci-fi"    │   │
│  │ 2. Search ChromaDB facts           │ │                  │   │
│  │ 3. Filter by 80% similarity        │ │ LLM Response:    │   │
│  │ 4. Take top 2 facts maximum        │ │ "Got it!"        │   │
│  └─────────────────────────────────────────┘ └─────────────────┘   │
│           │                                        │           │
│           ▼                                        ▼           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                Natural LLM Response                        │ │
│  │                                                             │ │
│  │ "Since you enjoy sci-fi books, I'd recommend..."           │ │
│  │                                                             │ │
│  │ ✓ Natural integration (treats memory as conversation)      │ │
│  │ ✓ No "I don't know X while showing X" confusion           │ │
│  │ ✓ High precision (only 80%+ relevant facts)               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                      Storage Layer                             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ ChromaDB (Vector Storage)                                   │ │
│  │ • User facts with semantic embeddings                      │ │
│  │ • nomic-embed-text model (768 dimensions)                  │ │
│  │ • Cosine similarity search                                 │ │
│  │ • ~/.cache/mcp_playground/chromadb                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Memory Tools: remember, recall, forget                        │
│  Key: Simple storage, high-threshold retrieval (80%+)          │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### Files:
- `src/core/vector_memory.py` - ChromaDB vector storage for user facts
- `src/tools/memory.py` - Simple memory tools (remember, recall, forget)
- `app.py` - Conversation history injection logic

### Memory Tools - Simple & Focused

**3 essential memory tools**:

1. **`remember(fact)`**: Store user information in ChromaDB
   - Auto-categorizes content
   - Returns simple confirmation
   - Example: `remember("User likes sci-fi books")`

2. **`recall(query)`**: Search stored facts
   - Semantic search across all stored information
   - Used for explicit user requests only
   - Example: `recall("what do you remember about my reading preferences")`

3. **`forget(description)`**: Remove stored information
   - Find and remove facts by description
   - Example: `forget("reading preferences")`

## How It Works - MVP Approach

### Core Principle: Conversation History Injection

**The Problem**: Complex system prompts confuse LLMs, causing "I don't know X while showing X" responses.

**The Solution**: Inject relevant facts as fake conversation history entries.

### Step-by-Step Process

1. **User Query**: "Any good sci-fi book recommendations?"

2. **Semantic Search**: 
   - Embed query using nomic-embed-text
   - Search ChromaDB for similar facts
   - Filter for 80%+ similarity only

3. **High-Relevance Check**:
   - Found: "User likes reading sci-fi books" (86% similarity)
   - Passes 80% threshold ✅

4. **Conversation History Injection**:
   ```json
   [
     {"role": "user", "content": "Just so you know, user likes reading sci-fi books"},
     {"role": "assistant", "content": "Got it, I'll keep that in mind!"},
     {"role": "user", "content": "Any good sci-fi book recommendations?"}
   ]
   ```

5. **Natural LLM Response**: 
   "Since you enjoy sci-fi books, I'd recommend..."

## Technical Implementation

### Key Components

```python
# In app.py - Simple conversation history injection
def inject_memory_as_conversation(message, conversation_history):
    # 1. Skip tool-focused queries
    if is_tool_query(message):
        return conversation_history
    
    # 2. Get high-relevance facts only
    facts = memory_manager.retrieve_facts_semantic(message, limit=5)
    high_relevance_facts = [f for f in facts if f.relevance_score > 0.8]
    
    # 3. Inject max 2 facts as fake conversation
    for fact in high_relevance_facts[:2]:
        conversation_history.append({
            "role": "user",
            "content": f"Just so you know, {fact.content.lower()}"
        })
        conversation_history.append({
            "role": "assistant", 
            "content": "Got it, I'll keep that in mind!"
        })
    
    return conversation_history
```

### ChromaDB Storage

- **Model**: nomic-embed-text (768 dimensions)
- **Storage**: ~/.cache/mcp_playground/chromadb
- **Search**: Cosine similarity
- **Threshold**: 80% minimum for injection (vs previous 10%)

### High-Precision Filtering

**NEW Threshold System**:
- **80%+ similarity**: Inject into conversation ✅
- **<80% similarity**: Skip injection ❌

**Example Results**:
- Query: "sci-fi books recommendation" → "User likes reading sci-fi books" = **81% similarity** ✅ (injected)
- Query: "reading sci-fi" → "User likes reading sci-fi books" = **86% similarity** ✅ (injected)  
- Query: "I like reading books" → "User likes reading sci-fi books" = **76% similarity** ❌ (not injected)
- Query: "what's the weather" → No relevant facts >80% ❌ (not injected)

## App Integration - Simple & Clean

### No Complex State Management

The MVP removes all complex architecture:

❌ Memory states and prompt engineering  
❌ Automatic tool filtering  
❌ Complex system prompt injection  
❌ Memory-aware prompt generation  

✅ Simple conversation history injection  
✅ High-threshold relevance filtering (80%+)  
✅ Standard system prompts  
✅ Clean, maintainable code  

### Integration Code

```python
# Simple integration in app.py
if not is_tool_query(message):
    # Get high-relevance facts
    relevant_facts = memory_manager.retrieve_facts_semantic(message, limit=5)
    high_relevance_facts = [fact for fact in relevant_facts if fact.relevance_score > 0.8]
    
    # Inject max 2 facts as conversation history
    for fact in high_relevance_facts[:2]:
        messages.append({
            "role": "user",
            "content": f"Just so you know, {fact.content.lower()}"
        })
        messages.append({
            "role": "assistant", 
            "content": "Got it, I'll keep that in mind!"
        })
```

### Tool Query Filtering

Simple keyword filtering prevents memory injection during tool-focused queries:

```python
tool_keywords = [
    'stock', 'price', 'crypto', 'weather', 'youtube', 
    'arxiv', 'crime', 'search', 'url'
]

is_tool_query = any(keyword in message.lower() for keyword in tool_keywords)
```

### Tool Usage Examples - Simplified

```python
# Store information
remember("User likes reading sci-fi books")  
# Returns: "✓ Remembered: User likes reading sci-fi books
#          This information will be automatically included in future conversations when relevant."

# Search memory (for explicit user requests)
recall("what do you remember about my reading preferences")  
# Returns: "Stored information about you:
#          • User likes reading sci-fi books"

# Remove information
forget("reading preferences")  # Finds and removes by description
```

### Automatic Context Injection - Simplified

**Every user message triggers simple workflow**:

1. **Tool Query Check**: Skip memory for stock/weather/youtube queries
2. **Semantic Search**: Find facts with 80%+ similarity to user query
3. **Conversation Injection**: Add top 2 relevant facts as fake conversation history
4. **Natural Response**: LLM treats injected facts as part of conversation flow

**No complex state management, no tool filtering, no prompt engineering.**

### MVP Benefits

#### ✅ Solves Core Problems
- **"I don't know X while showing X"**: Eliminated through conversation history injection
- **Complex prompt confusion**: Removed all complex system prompts  
- **Tool overuse**: No automatic tool filtering needed
- **Memory disconnect**: Single ChromaDB system for storage and retrieval

#### ✅ Simple & Maintainable
- **High precision**: 80% similarity threshold prevents irrelevant injection
- **Natural integration**: LLM treats memory as conversation context
- **Minimal code**: ~50 lines vs previous 500+ lines of complexity
- **Easy debugging**: Clear conversation history injection logs

### Common Issues

#### Setup Requirements
- **Ollama**: Must be running (`ollama serve`)
- **Embedding model**: Requires `ollama pull nomic-embed-text`
- **Storage**: ChromaDB stored in `~/.cache/mcp_playground/chromadb`

#### Performance
- **Embedding generation**: ~200ms per query (local Ollama)
- **Vector search**: ~50ms for 1000+ facts
- **Memory injection**: Only for 80%+ relevant queries (minimal overhead)

## Quick Start

```bash
# Install dependencies
uv add chromadb ollama

# Pull embedding model
ollama pull nomic-embed-text

# Test MVP memory system
from src.core.vector_memory import vector_memory_manager

# Store a fact
vector_memory_manager.store_fact("User likes reading sci-fi books", "preference")

# Test similarity threshold
facts = vector_memory_manager.retrieve_facts_semantic("sci-fi book recommendations", limit=5)
print(f"Relevance: {facts[0].relevance_score:.2f}")  # Should be >0.8 for injection
```

## Expected User Experience (MVP)

1. **Store Information**: "Remember I like reading sci-fi books"
   - LLM calls `remember` tool → fact stored in ChromaDB
   - Response: "✓ Remembered: User likes reading sci-fi books. This information will be automatically included in future conversations when relevant."

2. **Automatic Context**: "Any good sci-fi book recommendations?"
   - System finds 86% similarity with stored fact
   - Injects as conversation history: "Just so you know, user likes reading sci-fi books"
   - LLM responds naturally: "Since you enjoy sci-fi books, I'd recommend..."
   - **No separate memory blocks, no confusion**

3. **Memory Queries**: "What do you remember about me?"
   - LLM calls `recall` tool
   - Returns: "Stored information about you: • User likes reading sci-fi books"
   - Simple, direct response

## Why This Works

- **Natural**: LLM treats injected facts as conversation context, not external data
- **Precise**: 80% threshold ensures only highly relevant facts are injected
- **Simple**: No complex prompt engineering or state management
- **Reliable**: Conversation history injection is intuitive for LLMs

The MVP memory system prioritizes **simplicity and effectiveness** over architectural complexity.

## Debugging & Monitoring

### Debug Output

The system provides clear debug logs:

```
DEBUG - Injected memory: User likes reading sci-fi books (relevance: 0.86)
DEBUG - Skipping tool query: What's Apple's stock price?
DEBUG - No high-relevance facts found for: What's the weather?
```

### Memory Statistics

```python
stats = vector_memory_manager.get_memory_stats()
# Returns:
{
    'vector_facts_stored': 15,
    'chroma_path': '/Users/user/.cache/mcp_playground/chromadb',
    'embedding_model': 'nomic-embed-text'
}
```