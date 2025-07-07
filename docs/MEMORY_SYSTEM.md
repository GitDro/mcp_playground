# Memory System

## Overview

The AI can remember information about you across conversations using semantic search. Store facts with `remember`, retrieve them with `recall`, and remove them with `forget`.

## How It Works

```
User Query: "Any sci-fi book recommendations?"
     ↓
Semantic Search: Find stored facts >80% similarity
     ↓
Found: "User likes reading sci-fi books" (86% match)
     ↓
Inject as conversation history:
  User: "Just so you know, user likes reading sci-fi books"
  Assistant: "Got it!"
  User: "Any sci-fi book recommendations?"
     ↓
AI Response: "Since you enjoy sci-fi books, I'd recommend..."
```

## Tools

- **`remember(fact)`**: Store information ("User likes sci-fi books")
- **`recall(query)`**: Search stored facts ("what reading preferences?")
- **`forget(description)`**: Remove information ("reading preferences")

## Examples

**Store information:**
```
User: "Remember I like reading sci-fi books"
AI calls remember() → stored in ChromaDB
Response: "✓ Remembered: User likes reading sci-fi books"
```

**Automatic context:**
```
User: "Any book recommendations?"
System finds 86% similarity with stored fact
AI responds: "Since you enjoy sci-fi books, I'd recommend..."
```

**Explicit recall:**
```
User: "What do you remember about me?"
AI calls recall() → returns stored facts
Response: "• User likes reading sci-fi books"
```

## Technical Details

**Storage**: ChromaDB with Ollama embeddings (nomic-embed-text)
**Location**: `~/.cache/mcp_playground/chromadb`
**Threshold**: 80% similarity for automatic injection

**Key features:**
- Semantic search finds relevant facts by meaning, not keywords
- High threshold (80%+) prevents irrelevant memory injection
- Facts injected as conversation history for natural AI responses

## Setup

Requires Ollama with the embedding model:
```bash
ollama serve
ollama pull nomic-embed-text
```

Memory data stored locally at `~/.cache/mcp_playground/chromadb`