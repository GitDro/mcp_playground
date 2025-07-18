# Claude Development Notes

## Dependency Management
- **Always use `uv` for dependency management** instead of `pip` or `python -m`
- Run commands with `uv run python` instead of just `python`
- Install packages with `uv add package-name`

## Testing Commands
```bash
# Test MCP server
uv run python test_mcp.py

# Run main app
uv run streamlit run app.py
```

## Architecture

### Directory Structure
```
src/
├── core/
│   ├── vector_memory.py  # Vector-based memory with ChromaDB + Ollama
│   ├── memory.py         # TinyDB memory manager (fallback)
│   ├── cache.py          # Financial data caching
│   ├── models.py         # Pydantic models
│   └── utils.py          # General utilities
├── tools/
│   ├── memory.py         # remember, recall, forget (conversation context)
│   ├── documents.py      # store_note, search_documents, show_all_documents (automatic deduplication)
│   ├── web.py            # web_search, summarize_url, save_link
│   ├── arxiv.py          # arxiv_search + paper analysis
│   ├── financial.py      # stock/crypto/market tools
│   ├── youtube.py        # YouTube analysis tools
│   ├── weather.py        # weather tools
│   ├── tides.py          # Canadian tide information
│   └── crime.py          # Toronto crime statistics
└── server.py             # FastMCP server setup
```

### Adding New Tools
- Add to appropriate `src/tools/` module or create new category
- Register in `src/server.py` with `@mcp.tool` decorator
- Tools automatically generate schemas from Python type hints
- **UI Descriptions**: Update tool display names in `app.py:535-581` (lines with `elif 'tool_name' in tool_name:` logic)
- **Design Philosophy**: Use emojis extremely sparingly. Aesthetics should come from clean typography and simple yet elegant design, not endless emojis

## Planned Refinements (Future Deep Dives)

### App Architecture
- **Consolidate app files**: Decide if we need both `app.py` and `app_subprocess.py` or standardize on one approach
- **Tool registration system**: Create more systematic tool registration with automatic description generation
- **Configuration management**: Centralize settings, constants, and configuration in dedicated config files

### Code Quality
- **Error handling patterns**: Standardize error handling across all tools with consistent formatting and user feedback
- **Import optimization**: Systematic review and cleanup of unused imports across all modules
- **Function naming**: Ensure consistent naming patterns and conventions throughout codebase

### UI/UX Improvements
- **Responsive design**: Ensure UI works well on different screen sizes and devices
- **Loading states**: Add better loading indicators and progress feedback for long-running operations
- **Error messaging**: Standardize error message formatting and make them more user-friendly

## Memory System

### Vector-Based Memory Architecture
- **ChromaDB + Ollama**: Semantic search using `nomic-embed-text` embeddings
- **Hybrid Storage**: Vector search for facts + TinyDB for preferences
- **3 Streamlined Tools**: `remember`, `recall`, `forget`
- **Semantic Understanding**: "about me" finds "User likes ice cream" via meaning

### Key Benefits
- Solves the "about me" problem with semantic search
- Auto-context injection from relevant memories
- Local & private (no external API calls)
- Foundation for future document RAG

## Simplified Workflows

### Knowledge Base Building
1. **Save Content**: `save_link(url)` - Saves full webpage content with clean formatting
2. **Search Content**: `search_documents("topic")` - Semantic search across saved content
3. **Browse All**: `show_all_documents()` - See everything you've saved, organized by date

### URL Management
- **`save_link`** - Direct URL saving with full content extraction
- **`summarize_url`** - Analysis only, no saving
- **Auto-deduplication** - Automatically prevents saving duplicate URLs or identical content

### Memory vs Documents
- **Memory tools** (`remember`, `recall`, `forget`) - Conversation context only
- **Document tools** (`search_documents`, `show_all_documents`, `store_note`) - Permanent knowledge base
- **Clear boundaries** - No more tool selection confusion

## Tool Categories

### Data Analysis & Research
- **Financial Tools**: Real-time stock/crypto prices with caching
- **Canadian Economy**: Comprehensive economic analysis with Statistics Canada data (CPI, GDP, employment)
- **Academic Research**: arXiv search with PDF analysis
- **Crime Analytics**: Toronto neighbourhood safety statistics with semantic search
- **Weather Data**: Location-based forecasts (IP/city/coordinates)
- **Tide Information**: Canadian coastal tide times and heights

### Content Analysis & Document Management
- **Document Storage**: `store_note`, `search_documents`, `show_all_documents` with semantic search
- **Web Content**: URL saving (`save_link`) and analysis (`summarize_url`)
- **YouTube Enhancement**: Adaptive transcription for 2-3 hour videos
- **Automatic Deduplication**: Prevents duplicate URLs and identical content without user intervention
- **Context Scaling**: 24K+ tokens (96K+ characters) by default

### Data Visualization
- **Plot Generation**: Matplotlib charts returned as base64 images
- **Crime Trends**: Time series visualization for neighbourhood data
- **No External Dependencies**: Self-contained plotting system

## Helpful Links

### Documentation
- [Memory System](docs/MEMORY_SYSTEM.md) - Vector memory architecture
- [RAG Architecture](docs/RAG_ARCHITECTURE.md) - Technical semantic search details  
- [FastMCP Usage](docs/FASTMCP_USAGE.md) - MCP framework documentation

### External References
- [Statistics Canada Open Data](https://www.statcan.gc.ca/en/developers) - Economic indicators API
- [Toronto Open Data](https://open.toronto.ca/) - Crime statistics source
- [FastMCP Framework](https://github.com/jlowin/fastmcp) - MCP implementation
- [ChromaDB Documentation](https://docs.trychroma.com/) - Vector database
- [Ollama Models](https://ollama.ai/library) - Local LLM and embedding models