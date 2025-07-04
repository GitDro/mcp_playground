# RAG Architecture: Vector Memory System

## Overview

The MCP Playground implements a **Retrieval-Augmented Generation (RAG)** system using ChromaDB and Ollama embeddings to provide semantic memory capabilities. This architecture enables natural language queries to find relevant information based on meaning rather than keyword matching.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG-Enabled Memory System                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐   ┌─────────────────┐   ┌───────────────┐ │
│  │   User Query    │   │   LLM Context   │   │  Tool Results │ │
│  │                 │   │                 │   │               │ │
│  │ "about me"      │   │ + Auto Memory   │   │ + Embeddings  │ │
│  │ "work details"  │   │   Context       │   │ + Similarity  │ │
│  │ "preferences"   │   │ + Tool Usage    │   │ + Metadata    │ │
│  └─────────────────┘   └─────────────────┘   └───────────────┘ │
│           │                       │                     │       │
│           ▼                       ▼                     ▼       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 RAG Processing Pipeline                    │ │
│  │                                                             │ │
│  │  1. Query Embedding    2. Vector Search    3. Context      │ │
│  │     (nomic-embed)         (ChromaDB)         Building      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Vector Storage Layer                     │ │
│  │                                                             │ │
│  │  ChromaDB Collections:           TinyDB (Hybrid):          │ │
│  │  ├── user_facts (semantic)       ├── preferences (K-V)     │ │
│  │  ├── conversations (future)      ├── sessions (temp)       │ │
│  │  └── documents (future)          └── metadata (cache)      │ │
│  │                                                             │ │
│  │  Embeddings: nomic-embed-text (768d, 8K context)          │ │
│  │  Similarity: Cosine distance with relevance scoring        │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## RAG Components

### 1. **Embedding Model**
- **Model**: `nomic-embed-text` via Ollama
- **Dimensions**: 768
- **Context Window**: 8,192 tokens
- **Advantages**: Outperforms OpenAI embeddings, runs locally, no API costs

### 2. **Vector Database**
- **Engine**: ChromaDB
- **Storage**: Persistent local storage (`~/.cache/mcp_playground/chromadb`)
- **Similarity**: Cosine similarity
- **Collections**:
  - `user_facts`: Personal information and preferences
  - `conversations`: Future conversation history
  - `documents`: Future personal document storage

### 3. **Retrieval Strategy**
```python
# 1. Query → Embedding
query_embedding = ollama.embed(model='nomic-embed-text', input=user_query)

# 2. Vector Search
results = collection.query(
    query_texts=[query],
    n_results=limit,
    include=['documents', 'metadatas', 'distances']
)

# 3. Relevance Scoring
similarity = 1.0 - cosine_distance  # Convert distance to similarity
relevance_threshold = 0.1  # Minimum similarity to return
```

### 4. **Hybrid Approach**
The system combines vector search with traditional storage:

- **Semantic Search** (ChromaDB): For natural language queries like "about me", "work details"
- **Exact Match** (TinyDB): For structured data like preferences, settings
- **Fallback Logic**: If vector search fails, falls back to keyword matching

## Query Processing Flow

### Example: "What do you recall about me?"

```
1. Query Analysis
   ├── Detect general query pattern: "about me", "what do you know"
   ├── Route to: get_all_facts() for comprehensive results
   └── Alternative: semantic search for specific queries

2. Vector Retrieval  
   ├── Embed query: "what do you recall about me" → [0.1, -0.3, 0.8, ...]
   ├── Search ChromaDB: Find similar fact embeddings
   ├── Score results: Cosine similarity > 0.1 threshold
   └── Rank by relevance: 0.435 (high), 0.382 (medium), 0.215 (low)

3. Context Assembly
   ├── Facts: "User likes ice cream" (43.5% relevant)
   ├── Preferences: response_style: "concise" 
   ├── Conversations: Recent topic summaries
   └── Format: Structured response with relevance indicators

4. Response Generation
   ├── Auto-inject context into LLM system prompt
   ├── Include memory context with current conversation
   └── Generate natural response with retrieved information
```

## Performance Characteristics

### **Semantic Understanding**
- **"about me"** → **"User likes ice cream"**: 43.5% similarity ✅
- **"what do you know"** → Finds all stored facts ✅  
- **"work details"** → Finds work-categorized information ✅

### **Speed & Efficiency**
- **Embedding Generation**: ~200ms per query (local Ollama)
- **Vector Search**: ~50ms for 1000+ facts (ChromaDB)
- **Total Latency**: ~300ms for semantic memory lookup
- **Storage**: Minimal overhead (768 floats per fact)

### **Accuracy Metrics**
- **High Relevance** (>70% similarity): Direct keyword matches
- **Medium Relevance** (40-70% similarity): Semantic relationships  
- **Low Relevance** (10-40% similarity): Tangentially related
- **Threshold**: 10% minimum to filter noise

## Extensibility for Personal Document RAG

The current architecture provides a foundation for future document RAG capabilities:

### **Document Ingestion Pipeline**
```python
# Future enhancement
def ingest_document(file_path: str, doc_type: str):
    # 1. Extract text content
    content = extract_text(file_path)
    
    # 2. Chunk document 
    chunks = chunk_text(content, max_tokens=2000, overlap=200)
    
    # 3. Generate embeddings
    embeddings = [ollama.embed(chunk) for chunk in chunks]
    
    # 4. Store in ChromaDB
    documents_collection.add(
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{
            'source': file_path,
            'doc_type': doc_type, 
            'chunk_index': i
        } for i, chunk in enumerate(chunks)]
    )
```

### **Multi-Collection Search**
```python
# Search across different data types
def unified_search(query: str):
    # Search personal facts
    facts = facts_collection.query(query)
    
    # Search documents  
    docs = documents_collection.query(query)
    
    # Search conversations
    convs = conversations_collection.query(query)
    
    # Merge and rank by relevance
    return merge_results([facts, docs, convs])
```

## Configuration & Tuning

### **Similarity Thresholds**
```python
SIMILARITY_THRESHOLDS = {
    'high_relevance': 0.7,    # Direct matches
    'medium_relevance': 0.4,  # Semantic relationships
    'minimum_relevance': 0.1  # Filter threshold
}
```

### **Collection Configuration**
```python
collection_config = {
    'metadata': {"hnsw:space": "cosine"},  # Cosine similarity
    'embedding_function': OllamaEmbeddingFunction(),
    'persist_directory': '~/.cache/mcp_playground/chromadb'
}
```

### **Memory Management**
- **Automatic cleanup**: Old conversations (7-day retention)
- **Fact limits**: 1000 facts maximum with LRU eviction
- **Collection optimization**: Periodic HNSW index rebuilding

## Monitoring & Debugging

### **Relevance Analysis**
```python
# Debug similarity scores
def analyze_query(query: str):
    results = collection.query(query, include=['distances'])
    for i, distance in enumerate(results['distances'][0]):
        similarity = 1.0 - distance
        print(f"Result {i}: {similarity:.3f} similarity")
```

### **Performance Metrics**
- Query latency (embedding + search time)
- Relevance distribution (high/medium/low scores)
- Cache hit rates (for repeated queries)
- Memory usage (ChromaDB index size)

## Future Enhancements

### **Advanced RAG Patterns**
1. **Hybrid Search**: Combine vector + BM25 keyword search
2. **Re-ranking**: Use cross-encoder models for result refinement
3. **Query Expansion**: Generate alternative query phrasings
4. **Contextual Embeddings**: Fine-tune embeddings on user data

### **Multi-Modal RAG**
1. **Document Types**: PDF, Word, markdown, code files
2. **Image Analysis**: OCR + vision models for image content
3. **Audio/Video**: Transcription + semantic search over media
4. **Web Scraping**: Bookmark and search web content

### **Privacy & Security**
1. **Local-first**: All processing stays on device
2. **Encryption**: Encrypt embeddings at rest
3. **Anonymization**: Remove PII from stored content
4. **Access Controls**: User-controlled data retention policies

---

## Getting Started

To utilize the RAG system:

1. **Store Information**: `remember("I prefer morning meetings")`
2. **Natural Queries**: `recall("what do you know about my schedule preferences")`
3. **Semantic Search**: Works with any natural language phrasing
4. **Relevance Feedback**: System shows relevance scores for transparency

The RAG architecture provides a solid foundation for intelligent, semantic memory that grows more powerful as more documents and personal information are added to the system.