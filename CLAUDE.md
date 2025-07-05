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
├── app.py                # Main Streamlit application
├── mcp_server.py         # FastMCP server entry point
├── CLAUDE.md             # This development notes file
├── README.md             # Project documentation
├── pyproject.toml        # Dependencies and project config
├── docs/                 # Documentation folder
│   ├── MEMORY_SYSTEM.md      # Vector memory system guide
│   ├── RAG_ARCHITECTURE.md   # Technical RAG implementation details
│   └── FASTMCP_USAGE.md      # FastMCP framework documentation
├── src/
│   ├── core/
│   │   ├── vector_memory.py  # Vector-based memory with ChromaDB + Ollama
│   │   ├── memory.py         # TinyDB memory manager (fallback)
│   │   ├── cache.py          # Financial data caching
│   │   ├── models.py         # Pydantic models
│   │   └── utils.py          # General utilities
│   ├── tools/
│   │   ├── memory.py         # 3 streamlined memory tools
│   │   ├── web.py            # web_search, analyze_url
│   │   ├── arxiv.py          # arxiv_search + paper analysis
│   │   ├── financial.py      # stock/crypto/market tools
│   │   ├── youtube.py        # YouTube analysis tools
│   │   ├── weather.py        # weather tools
│   │   └── tides.py          # Canadian tide information
│   └── server.py             # FastMCP server setup
└── cache/                # Runtime cache directory
```

### Adding New Tools
- Add to appropriate `src/tools/` module or create new category
- Register in `src/server.py` with `@mcp.tool` decorator
- Tools automatically generate schemas from Python type hints

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

## YouTube Enhancement
- **Adaptive Transcription**: Handles 2-3 hour videos with smart truncation
- **Context Scaling**: 24K+ tokens (96K+ characters) by default
- **Multi-language Support**: Auto-generated captions and multiple languages