# RAG Architecture: Simple Memory System (MVP)

## Overview

The MCP Playground implements a **simplified RAG system** using ChromaDB and Ollama embeddings for semantic memory retrieval. The key innovation is **conversation history injection** instead of complex prompt engineering, making memory integration natural and reliable.

## MVP Architecture - Conversation History Injection

```
┌─────────────────────────────────────────────────────────────────┐
│              RAG-Based Memory System (Simplified)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐ │
│  │   User Query    │   │   Semantic      │   │  Conversation   │ │
│  │                 │   │   Search        │   │   History       │ │
│  │ "Any sci-fi     │──►│   Pipeline      │──►│   Injection     │ │
│  │ book recs?"     │   │                 │   │                 │ │
│  │                 │   │ • nomic-embed   │   │ • 80% threshold │ │
│  └─────────────────┘   │ • ChromaDB      │   │ • Max 2 facts   │ │
│                         │ • Cosine sim    │   │ • Fake convo    │ │
│                         └─────────────────┘   └─────────────────┘ │
│                                 │                       │         │
│                                 ▼                       ▼         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                ChromaDB Vector Storage                      │ │
│  │                                                             │ │
│  │ Collection: user_facts                                      │ │
│  │ • Embedding: nomic-embed-text (768d)                       │ │
│  │ • Similarity: Cosine distance                              │ │
│  │ • Storage: ~/.cache/mcp_playground/chromadb                │ │
│  │                                                             │ │
│  │ Query: "sci-fi book recommendations"                        │ │
│  │ Result: "User likes reading sci-fi books" (86% similarity) │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                 │                               │
│                                 ▼                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │            Natural LLM Integration                          │ │
│  │                                                             │ │
│  │ Conversation History:                                       │ │
│  │ [                                                           │ │
│  │   {"role": "user", "content": "Just so you know, user      │ │
│  │    likes reading sci-fi books"},                            │ │
│  │   {"role": "assistant", "content": "Got it!"},              │ │
│  │   {"role": "user", "content": "Any sci-fi book recs?"}     │ │
│  │ ]                                                           │ │
│  │                                                             │ │
│  │ LLM Response: "Since you enjoy sci-fi books, I'd           │ │
│  │ recommend Foundation by Asimov..."                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## RAG Components - Simplified

### 1. **Embedding Model**
- **Model**: `nomic-embed-text` via Ollama
- **Dimensions**: 768
- **Context Window**: 8,192 tokens
- **Advantages**: Outperforms OpenAI embeddings, runs locally, no API costs

### 2. **Vector Database**
- **Engine**: ChromaDB
- **Storage**: Local persistent storage (`~/.cache/mcp_playground/chromadb`)
- **Similarity**: Cosine similarity
- **Collection**: `user_facts` only (simplified from multiple collections)

### 3. **Retrieval Strategy - High Precision**
```python
# Simplified retrieval with high threshold
def get_relevant_memory(query: str):
    # 1. Embed query
    query_embedding = ollama.embed(model='nomic-embed-text', input=query)
    
    # 2. Search ChromaDB
    results = collection.query(
        query_texts=[query],
        n_results=5,
        include=['documents', 'metadatas', 'distances']
    )
    
    # 3. High-precision filtering (NEW)
    high_relevance_facts = []
    for i, distance in enumerate(results['distances'][0]):
        similarity = 1.0 - distance
        if similarity > 0.8:  # Only 80%+ similarity
            high_relevance_facts.append(results['documents'][0][i])
    
    return high_relevance_facts[:2]  # Max 2 facts
```

### 4. **Conversation History Injection (Key Innovation)**
Instead of complex prompt injection:
```python
# OLD: Complex system prompt injection
system_prompt = f"You have access to: {memory_context}"  # Confusing for LLM

# NEW: Natural conversation history
conversation_history.extend([
    {"role": "user", "content": "Just so you know, user likes sci-fi books"},
    {"role": "assistant", "content": "Got it, I'll keep that in mind!"}
])
# LLM treats this as natural conversation context
```

## Query Processing Flow - Simplified

### Example: "Any good sci-fi book recommendations?"

```
1. Query Analysis (Simple)
   ├── Skip tool-focused queries: "stock", "weather", "youtube"
   ├── Process general queries: "book recommendations"
   └── Route to: semantic search

2. Vector Retrieval (High Precision)
   ├── Embed query: "sci-fi book recommendations" → [0.1, -0.3, 0.8, ...]
   ├── Search ChromaDB: Find similar fact embeddings
   ├── Filter results: Only similarity > 0.8 (vs previous 0.1)
   └── Found: "User likes reading sci-fi books" (86% similarity)

3. Conversation History Injection (Natural)
   ├── Add fake conversation entry:
   │   User: "Just so you know, user likes reading sci-fi books"
   │   Assistant: "Got it, I'll keep that in mind!"
   ├── Add current query: "Any good sci-fi book recommendations?"
   └── Send to LLM as natural conversation

4. Natural Response Generation (Improved)
   ├── LLM receives memory as conversation context
   ├── No complex system prompts to confuse LLM
   ├── Response naturally integrates stored information
   └── Result: "Since you enjoy sci-fi books, I'd recommend..."
```

## Performance Characteristics

### **Semantic Understanding - High Precision**
- **"sci-fi books recommendation"** → **"User likes reading sci-fi books"**: 81% similarity ✅ (injected)
- **"reading sci-fi"** → **"User likes reading sci-fi books"**: 86% similarity ✅ (injected)
- **"I like reading books"** → **"User likes reading sci-fi books"**: 76% similarity ❌ (not injected)
- **"what's the weather"** → No relevant facts >80% ❌ (not injected)

### **Speed & Efficiency**
- **Embedding Generation**: ~200ms per query (local Ollama)
- **Vector Search**: ~50ms for 1000+ facts (ChromaDB)
- **Total Latency**: ~300ms for semantic memory lookup
- **Memory Injection**: Only when 80%+ relevant (minimal overhead)

### **Accuracy Metrics**
- **High Relevance** (>80% similarity): Inject into conversation ✅
- **Lower Relevance** (<80% similarity): Skip injection ❌
- **Precision**: Prevents irrelevant memory injection
- **Recall**: High-relevance facts reliably found and injected

## Comparison: Old vs New Architecture

### **Previous Complex System** ❌
- Multiple memory states (`NO_MEMORY`, `HAS_FACTS`, etc.)
- Complex system prompt engineering
- Automatic tool filtering logic
- Memory-aware prompt generation
- "I don't know X while showing X" confusion

### **New Simple System** ✅
- Single ChromaDB storage system
- Conversation history injection
- High-threshold filtering (80%+)
- No complex state management
- Natural LLM integration

## Technical Implementation

### **Key Code Changes**

```python
# app.py - Simple memory injection
if not is_tool_query(message):
    relevant_facts = memory_manager.retrieve_facts_semantic(message, limit=5)
    high_relevance_facts = [f for f in relevant_facts if f.relevance_score > 0.8]
    
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

### **ChromaDB Configuration**
```python
collection_config = {
    'metadata': {"hnsw:space": "cosine"},  
    'embedding_function': OllamaEmbeddingFunction(),
    'persist_directory': '~/.cache/mcp_playground/chromadb'
}
```

### **Tool Query Filtering**
```python
tool_keywords = [
    'stock', 'price', 'crypto', 'weather', 'youtube', 
    'arxiv', 'crime', 'search', 'url'
]
is_tool_query = any(keyword in message.lower() for keyword in tool_keywords)
```

## Future Enhancements - Keep It Simple

### **Document RAG Extension**
The current architecture provides a foundation for document RAG:
1. **Document Ingestion**: Chunk documents, embed, store in ChromaDB
2. **Multi-Source Search**: Search across facts + documents with same threshold
3. **Same Injection Method**: Use conversation history injection for document content

### **Performance Optimizations**
1. **Embedding Caching**: Cache embeddings for repeated queries
2. **Index Optimization**: Periodic ChromaDB index rebuilding
3. **Threshold Tuning**: Adjust 80% threshold based on user feedback

## Monitoring & Debugging

### **Debug Output**
```
DEBUG - Query: "sci-fi book recommendations"
DEBUG - Found fact: "User likes reading sci-fi books" (relevance: 0.86)
DEBUG - Injected memory: User likes reading sci-fi books
DEBUG - Skipping tool query: "What's Apple's stock price?"
```

### **Performance Metrics**
- Query latency (embedding + search time)
- Injection rate (% of queries that trigger memory injection)
- Relevance distribution (high precision filtering effectiveness)

## Getting Started - Updated

To utilize the simplified RAG system:

1. **Store Information**: `remember("I prefer sci-fi books")`
   - Stored in ChromaDB with embeddings
   - Ready for semantic search

2. **Automatic Context**: Ask "What should I read next?"
   - System finds high relevance (>80%) to sci-fi preference
   - Injects as conversation history: "Just so you know, user prefers sci-fi books"
   - LLM responds naturally: "Since you prefer sci-fi, I'd recommend..."

3. **High Precision**: Ask "What's the weather?"
   - No relevant facts >80% similarity
   - No memory injection (clean response)

4. **Explicit Memory**: Ask "What do you remember about me?"
   - LLM calls `recall` tool
   - Returns stored facts directly

## Key Benefits

- **Eliminates Confusion**: No more "I don't know X while showing X"
- **Natural Integration**: LLM treats memory as conversation context
- **High Precision**: 80% threshold prevents irrelevant injection
- **Simple Architecture**: ~50 lines vs 500+ lines of complexity
- **Reliable**: Conversation history injection is intuitive for LLMs

The simplified RAG architecture proves that **less complexity can lead to better results** when the implementation aligns with how LLMs naturally process information.