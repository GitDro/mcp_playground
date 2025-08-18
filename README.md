# MCP Playground

A modern Streamlit chat application with Ollama integration and AI-powered tool calling capabilities. Built using the Model Context Protocol (MCP) for scalable, standards-compliant tool execution.

## Quick Start

### Prerequisites
1. **Install Ollama**: Visit https://ollama.ai
2. **Start Ollama**: `ollama serve`
3. **Pull a model**: `ollama pull llama3.2`
4. **Pull embedding model**: `ollama pull nomic-embed-text` (required for vector memory)

### Run the App

```bash
git clone <your-repo>
cd mcp_playground
uv sync

# Run the main application
uv run streamlit run app.py

# Or run the subprocess version
uv run streamlit run app_subprocess.py
```

Open http://localhost:8501

#### MCP Client Integration

You can use these tools with any MCP-compatible client through standard MCP configuration:

**Example MCP Configuration**:
```json
{
  "mcpServers": {
    "mcp-playground": {
      "command": "/path/to/your/project/.venv/bin/python3",
      "args": ["/path/to/your/project/mcp_server.py", "stdio"]
    }
  }
}
```

**Note**: Replace `/path/to/your/project/` with the actual path to your cloned repository. The configuration format may vary depending on your MCP client.

**Available Tools:**
- `web_search`, `analyze_url`, `save_link` - Web search, analysis, and content saving
- `arxiv_search` - Academic paper search with PDF analysis
- `get_stock_overview` - Financial data for stocks, crypto, and market indices
- `analyze_youtube_url` - YouTube video analysis and summarization
- `get_weather` - Weather forecasts by location
- `get_tide_info` - Canadian tide information
- `get_toronto_crime` - Toronto neighbourhood crime statistics
- `remember`, `recall`, `forget` - Conversation memory
- `store_note`, `search_documents`, `show_all_documents` - Document management

#### Standalone MCP Server
```bash
# Run as standalone MCP server (stdio mode)
uv run python mcp_server.py

# Run as HTTP server for web integration
uv run python mcp_server.py http 8000
```

## Capabilities

- **Local LLM Integration**: Direct integration with Ollama models
- **Web Search & Analysis**: Real-time web search and URL content analysis
- **Academic Research**: arXiv paper search with PDF analysis
- **Financial Data**: Stock prices, crypto rates, and market data without API keys
- **Media Analysis**: YouTube video analysis and summarization
- **Weather & Tides**: Location-based forecasts and Canadian tide information
- **Crime Analytics**: Toronto neighbourhood safety statistics with visualization
- **Vector Memory**: Semantic memory system with conversation context
- **Tool Management**: Enable/disable AI tool usage per conversation

## Example Usage

**Web & Research:**
- "Search for Python 3.13 features"
- "Analyze https://example.com"
- "Find papers on transformer architectures"

**Financial & Market Data:**
- "What's Apple's stock price?"
- "Get Bitcoin price"

**Media & Content:**
- "Analyze this YouTube video: [URL]"
- "Summarize the content at this URL"

**Location Services:**
- "Weather in Toronto"
- "When is high tide in Halifax today?"
- "Crime statistics for downtown Toronto"

**Memory:**
- "Remember I like reading sci-fi books"
- "What do you remember about me?"

## Architecture

### Core Components
```
app.py                    # Main Streamlit application
mcp_server.py            # FastMCP server with all tools
src/core/vector_memory.py # Vector memory with ChromaDB + Ollama
src/tools/               # Organized tool modules
```

### Key Features
- Standards-compliant MCP implementation
- Automatic schema generation from Python type hints
- Vector memory with semantic search
- Intelligent retry system with error recovery
- Modular tool organization

## MCP Server Usage

### Standalone Server
```bash
# Run as MCP server
uv run python mcp_server.py stdio

# Run as HTTP server
uv run python mcp_server.py http 8000
```

### Client Integration
```python
from fastmcp import Client
from mcp_server import mcp

async def use_tools():
    async with Client(mcp) as client:
        result = await client.call_tool("web_search", {"query": "MCP framework"})
        print(result.content[0].text)
```

## Vector Memory System

Semantic memory system that understands meaning, not just keywords.

### Architecture
- **ChromaDB + Ollama**: Uses `nomic-embed-text` embeddings for semantic search
- **Hybrid Storage**: Vector facts with TinyDB fallback
- **Local & Private**: All data stored at `~/.cache/mcp_playground/`

### Tool Categories
- **Memory Tools** (`remember`, `recall`, `forget`): Conversation context
- **Document Tools** (`store_note`, `search_documents`, `show_all_documents`): Knowledge base
- **Web Tools** (`save_link`, `analyze_url`): Content saving and analysis

### Key Features
- High precision with 80% similarity threshold
- Natural conversation history injection
- Eliminates irrelevant memory injection
- Automatic context awareness

## Documentation

- **[FastMCP Overview](docs/FASTMCP_OVERVIEW.md)** - How the @mcp.tool decorator eliminates boilerplate
- **[Memory System](docs/MEMORY_SYSTEM.md)** - Simple MVP memory system with conversation history injection
- **[RAG Architecture](docs/RAG_ARCHITECTURE.md)** - Simplified RAG with high-precision filtering
- **[FastMCP Usage](docs/FASTMCP_USAGE.md)** - FastMCP framework documentation

## Troubleshooting

**No models found?**
```bash
ollama serve
ollama pull llama3.2
ollama pull nomic-embed-text
```

**Function calling not working?**
- Check internet connection
- Ensure "Tools" checkbox is enabled  
- Use a recent model (llama3.2, devstral)

**Memory not working?**
- Ensure Ollama is running: `ollama serve`
- Check model availability: `ollama list`
- Memory falls back to TinyDB if ChromaDB/Ollama unavailable

**App won't start?**
```bash
uv sync
python --version  # Requires Python 3.12+
```
