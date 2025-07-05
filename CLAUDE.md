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
│   ├── memory.py         # 3 streamlined memory tools
│   ├── web.py            # web_search, analyze_url
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

## Tool Categories

### Data Analysis & Research
- **Financial Tools**: Real-time stock/crypto prices with caching
- **Academic Research**: arXiv search with PDF analysis
- **Crime Analytics**: Toronto neighbourhood safety statistics with semantic search
- **Weather Data**: Location-based forecasts (IP/city/coordinates)
- **Tide Information**: Canadian coastal tide times and heights

### Content Analysis
- **YouTube Enhancement**: Adaptive transcription for 2-3 hour videos
- **Web Analysis**: URL content extraction and summarization
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
- [Toronto Open Data](https://open.toronto.ca/) - Crime statistics source
- [FastMCP Framework](https://github.com/jlowin/fastmcp) - MCP implementation
- [ChromaDB Documentation](https://docs.trychroma.com/) - Vector database
- [Ollama Models](https://ollama.ai/library) - Local LLM and embedding models