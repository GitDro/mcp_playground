# Claude Development Notes

## Recent Changes (Sept 2025)

### 🚀 Unified Architecture & Simplified Deployment
- **Consolidated servers**: Single `src/server.py` handles both local (stdio) and cloud (HTTP) modes
- **Streamlined dependencies**: Removed vector memory and ChromaDB dependencies for cloud compatibility  
- **Simplified UI**: Single `app.py` using proper FastMCP subprocess transport
- **Updated documentation**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) reflects current tool capabilities

### 🔧 Code Simplifications
- **Removed vector memory system**: No more ChromaDB/Ollama dependencies for cloud deployment
- **Moved TinyDB to core dependencies**: Fixes YouTube transcript caching in cloud deployment
- **Unified configuration**: Single .env approach for both local and cloud
- **Clean tool set**: Focus on real-time API-based tools that work everywhere
- **Better error handling**: Improved tool descriptions and neighborhood listing for crime data
- **YouTube Cloud Fix**: Added WebShare proxy support to bypass YouTube's IP blocking for cloud deployments

### 🎥 **YouTube Transcript API Stability (Sept 2025)**
- **CRITICAL**: Use only 2025 API instance methods: `api = YouTubeTranscriptApi()` then `api.fetch(video_id)` and `api.list(video_id)`
- **Never use**: Static methods like `YouTubeTranscriptApi.get_transcript()` - they don't exist and will break
- **Session handling**: Only pass custom `http_client=session` when proxies are configured, otherwise use default session
- **Proxy configuration**: `WEBSHARE_PROXIES` in .env for cloud deployment, empty for local development

### 📊 **Complete MCP ToolResult Migration (2025)**
- **All tools migrated**: Every tool now returns `ToolResult` following 2024-2025 FastMCP best practices
- **Chart tools optimized**: financial.py, crime.py use `TextContent` + `ImageContent` for direct IDE display
- **Text tools standardized**: web.py, weather.py, youtube.py, tides.py, statscan.py, arxiv.py use consistent `ToolResult`
- **Token savings achieved**: Eliminated redundant structured_content duplication
- **IDE compatibility maintained**: Charts still display directly in VS Code/Cursor
- **Streamlit backward compatibility**: No changes to existing UI experience
- **See**: [MCP Client Rendering Guide](docs/MCP_CLIENT_RENDERING.md) for complete technical details

## Dependency Management
- **Always use `uv` for dependency management** instead of `pip` or `python -m`
- Run commands with `uv run python` instead of just `python`
- Install packages with `uv add package-name`
- **Cloud deployment**: Uses core dependencies only (auto-detected from pyproject.toml)
- **Local development**: `uv sync --extra local` for Streamlit UI

## Testing Commands
```bash
# Run Streamlit UI (local development)
uv run streamlit run app.py

# Test MCP server for Claude Desktop (local)
uv run python mcp_server.py

# Test HTTP mode locally
uv run python -m src.server http 8000

# Test cloud server locally
uv run python cloud_server.py
```

## Cloud Deployment Workflow
1. **Commit changes**: `git add . && git commit -m "Deploy updates" && git push`
2. **Access workspace**: `https://fastmcp.cloud/dro-serve`
3. **Monitor deployment**: Check logs and status in FastMCP Cloud dashboard
4. **Get URL**: Your server will be available at `https://your-project-name.fastmcp.app/mcp`
5. **Configure client**: Add bearer token to Claude Desktop config

## Architecture

### Directory Structure
```
src/
├── core/
│   ├── cache.py          # Financial data caching
│   ├── retry_manager.py  # Tool retry logic and error recovery
│   ├── tool_wrapper.py   # @retry_tool decorator for enhanced reliability
│   ├── models.py         # Pydantic models
│   └── utils.py          # General utilities
├── tools/
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

**MCP Content Block Audience Control:**
- **Text content**: `audience=None` - Both user (VS Code display) and LLM can access content
- **Chart images**: `audience=["user"]` - Only user sees charts in VS Code, LLM gets text summary
- **Critical Fix (Sept 2025)**: Changed from `audience=["user"]` to `audience=None` for text content to fix LLM access issue where VS Code showed results but LLM couldn't process them

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

## Cloud Deployment Optimizations

### Local vs Host LLM Processing
- **arXiv Tool**: Extracts raw PDF text and metadata for host LLM analysis (no local processing)
- **Vector Memory**: Uses Ollama embeddings locally (appropriate for search indexing)
- **All Other Tools**: Return raw data for host LLM analysis (web content, financial data, etc.)
- **Design Principle**: MCP server handles data retrieval, host LLM handles analysis and insights

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
- **Academic Research**: arXiv search with full text extraction for host LLM analysis
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

# YouTube cloud deployment (bypasses IP blocking)
export WEBSHARE_PROXIES="ip:port:user:pass,ip2:port2:user2:pass2,..."
```

## Helpful Links

### Documentation
- [Deployment Guide](docs/DEPLOYMENT.md) - Cloud and local deployment instructions
- [MCP Client Rendering](docs/MCP_CLIENT_RENDERING.md) - Content block optimization for IDE clients
- [FastMCP Usage](docs/FASTMCP_USAGE.md) - MCP framework documentation
- [FastMCP Overview](docs/FASTMCP_OVERVIEW.md) - Framework architecture overview

### External References
- [Statistics Canada Open Data](https://www.statcan.gc.ca/en/developers) - Economic indicators API
- [Toronto Open Data](https://open.toronto.ca/) - Crime statistics source
- [FastMCP Framework](https://github.com/jlowin/fastmcp) - MCP implementation
- [ChromaDB Documentation](https://docs.trychroma.com/) - Vector database
- [Ollama Models](https://ollama.ai/library) - Local LLM and embedding models