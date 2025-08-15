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
│   ├── retry_manager.py  # Tool retry logic and error recovery
│   ├── tool_wrapper.py   # @retry_tool decorator for enhanced reliability
│   ├── retry_state_manager.py  # Learning system for retry patterns
│   ├── models.py         # Pydantic models
│   └── utils.py          # General utilities
├── tools/
│   ├── memory.py         # remember, recall, forget (conversation context)
│   ├── documents.py      # store_note, search_documents, show_all_documents (automatic deduplication)
│   ├── web.py            # web_search, analyze_url, save_link
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

### FastMCP Tool Description Best Practices
**CRITICAL**: Tools without descriptions expose their full docstrings to LLMs, making them harder to parse and select correctly.

**How Tool Descriptions Work:**
- **`@mcp.tool`** (naked decorator) - LLM sees the full docstring as the description
- **`@mcp.tool(description="short description")`** - LLM sees only the short description

**PROBLEM**: Tools without descriptions expose their full docstrings to LLMs, making them harder to parse and select correctly.

**Best Practices:**
1. **Always use `@mcp.tool(description="...")`** with concise, clear descriptions
2. **Write descriptions that match user language** - how users would ask for this functionality
3. **Keep descriptions under 10-15 words** - LLMs process short descriptions better
4. **Include key distinguishing features** - what makes this tool unique vs similar ones
5. **Use action verbs** - "Search academic papers", "Get weather forecast", "Remember conversation context"
6. **Avoid technical jargon** - write for the user, not the developer

**Examples:**
- Good: `@mcp.tool(description="Search academic papers on arXiv with PDF analysis")`
- Bad: `@mcp.tool` (exposes full docstring to LLM)
- Bad: `@mcp.tool(description="tool")` (too vague)

**Tool Boundaries:**
- **Memory tools** (`remember`, `recall`, `forget`) - Conversation context only
- **Document tools** (`search_documents`, `show_all_documents`, `store_note`) - Permanent knowledge base
- **Web tools** - `save_link` (saves content), `analyze_url` (analysis only)

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
- **`analyze_url`** - Analysis only, no saving
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
- **Web Content**: URL saving (`save_link`) and analysis (`analyze_url`)
- **YouTube Enhancement**: Adaptive transcription for 2-3 hour videos
- **Automatic Deduplication**: Prevents duplicate URLs and identical content without user intervention
- **Context Scaling**: 24K+ tokens (96K+ characters) by default

### Data Visualization
- **Plot Generation**: Matplotlib charts returned as base64 images
- **Crime Trends**: Time series visualization for neighbourhood data
- **No External Dependencies**: Self-contained plotting system

## Tool Retry System

### Automatic Error Recovery
- **@retry_tool decorator**: Enhances existing tools with automatic type correction and retry logic
- **Smart type coercion**: Converts string "123" → int 123, "true" → bool True automatically
- **Learning system**: Uses vector memory to learn from successful corrections
- **LLM-friendly errors**: Clear, actionable error messages with correction suggestions

### Configuration
```bash
# Environment variables for retry behavior
export MCP_RETRY_MAX_ATTEMPTS=3
export MCP_RETRY_BASE_DELAY=0.5
export MCP_RETRY_TYPE_COERCION=true
```

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