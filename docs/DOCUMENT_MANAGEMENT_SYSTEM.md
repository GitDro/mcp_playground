# Document Management System - Simplified

## Overview

The MCP Playground now includes a streamlined document management system that provides local, private storage and semantic search for personal notes and web captures. This system builds on the existing RAG architecture with a clean, focused approach.

## Features ✅

### **Core Document Storage**
- **Local markdown/text files** with semantic search using existing ChromaDB + Ollama embeddings
- **Personal notes storage** (house measurements, medications, sensitive info)
- **Web page captures** via enhanced `summarize_url` tool  
- **File watching** - automatically re-indexes when you manually edit files
- **Local-first privacy** - everything stored locally, no cloud dependency

### **3 Streamlined Tools**

1. **`store_note(title, content, tags)`** - Store private notes locally with auto-save
2. **`search_notes(query, limit, tags)`** - Semantic search across all documents  
3. **`list_notes(limit)`** - List all stored notes

### **Enhanced Web Analysis**
- **`summarize_url(url, save_content=False)`** - Now with optional content saving
- When `save_content=True`, saves cleaned markdown to `documents/captures/`
- Provides analysis + save confirmation in one tool

## Technical Architecture

### **Simplified Storage Structure**
```
~/.cache/mcp_playground/
├── chromadb/           # Existing vector storage + new documents collection
├── documents/          # Document storage
│   ├── notes/         # Personal markdown notes (store_note + manual)
│   └── captures/      # Web content saves (summarize_url)
└── [other existing folders]
```

### **File Watching System**
- **Background thread** monitors `documents/` folder every 10 seconds
- **Automatic re-indexing** when markdown/text files change
- **Frontmatter parsing** - reads title, tags, doc_type from YAML frontmatter
- **Smart filename handling** - cleans up timestamp-based filenames

### **Vector Integration**
- **ChromaDB Documents Collection** alongside existing `user_facts`
- **Same embedding pipeline** - uses existing Ollama `nomic-embed-text` (768d)
- **Lower similarity threshold** (30% vs 80% for facts) for personal notes
- **Hybrid storage** - vector search + file persistence

## Example Usage

### **Store Private Information**
```python
# Store sensitive personal information
store_note(
    title="Medication Schedule", 
    content="Take vitamin D: 1000 IU daily\nOmega-3: 2 capsules with dinner",
    tags=["health", "medication"]
)
# → Saved to notes/20250716_225726_Medication_Schedule.md
```

### **Semantic Search**
```python
# Find information by meaning, not keywords
search_notes("daily supplements")  # Finds "Medication Schedule" note
search_notes("room dimensions")    # Finds "House Measurements" note
search_notes("bedroom size")       # Also finds house measurements
```

### **Save Web Content**
```python
# Analyze and optionally save interesting web content
summarize_url("https://example.com/article", save_content=True)
# → Analysis + saves to captures/20250716_230000_Article_Title.md
```

### **Manual Editing**
- Edit any `.md` file in `documents/notes/` or `documents/captures/`
- File watcher automatically detects changes and re-indexes
- Frontmatter preserved and parsed for metadata

## Integration Benefits

### **Leverages Existing Architecture**
✅ Uses current ChromaDB vector storage  
✅ Uses current Ollama embedding pipeline  
✅ Follows established tool patterns  
✅ Maintains existing memory system separation  

### **Clean Separation**
- **Personal documents** (notes/captures) separate from **conversational facts**
- **Different similarity thresholds** prevent cross-contamination
- **Explicit search** - documents don't auto-inject into conversations
- **Manual control** over what gets stored and searched

## Privacy & Security

### **Local-First Design**
✅ All data stays on local machine  
✅ No cloud storage of sensitive information  
✅ Full control over data access and sharing  
✅ Markdown files are portable and readable  

### **File Organization**
✅ Clean directory structure with logical separation  
✅ Timestamp-based filenames prevent conflicts  
✅ YAML frontmatter for metadata  
✅ Manual editing fully supported  

## System Status

- **Tools**: 15 total (down from 19) - focused and streamlined
- **Storage**: 2 directories (notes + captures) instead of 4
- **File watching**: Active background monitoring with 10-second intervals
- **Testing**: Comprehensive test suite passing ✅

## Usage Examples

### **Store Personal Notes**
Perfect for sensitive information you want to keep private and searchable:
- House measurements and dimensions
- Medication schedules and dosages  
- Personal reminders and important dates
- Work-related notes and project details

### **Search by Meaning**
The semantic search finds information even when you don't remember exact words:
- Search "room dimensions" → finds "House Measurements" 
- Search "daily supplements" → finds "Medication Schedule"
- Search "health routine" → finds medication and exercise notes

### **Web Content Archival**
Save interesting web content for offline reference:
- Research articles and blog posts
- Technical documentation and tutorials
- News articles and reference material
- Clean markdown format preserves readability

### **Manual File Management**
Edit documents directly in your preferred editor:
- Files automatically re-indexed when saved
- Frontmatter preserved for metadata
- Standard markdown format ensures compatibility
- Full control over organization and naming

The simplified document management system transforms MCP Playground into a practical personal knowledge base while maintaining the privacy and local-first principles that make it trustworthy for sensitive information.