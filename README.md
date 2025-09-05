# MCP Playground

Research and analysis toolkit with real-time data access via Model Context Protocol (MCP).

**Live Server**: https://mcp-playground.fastmcp.app/mcp

## Quick Start

```bash
git clone <your-repo>
cd mcp_arena
uv sync --extra local
uv run streamlit run app.py
```

## MCP Client Setup

### Claude Desktop

**Option 1: Remote Server (Recommended)**
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "mcp-playground": {
      "type": "http",
      "url": "https://mcp-playground.fastmcp.app/mcp"
    }
  }
}
```

**Option 2: Local Development**
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "mcp-playground-local": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"]
    }
  }
}
```
*Note: Run this command from your mcp_arena directory*

### Claude Code
1. `Cmd/Ctrl + Shift + P` → "MCP: Add Server"
2. Choose "Add remote HTTP server"
3. URL: `https://mcp-playground.fastmcp.app/mcp`


### LMStudio (v0.3.17+)
1. Program tab → "Edit mcp.json"
2. Add configuration:
```json
{
  "mcp-arena": {
    "url": "https://mcp-playground.fastmcp.app/mcp",
  }
}
```

## Available Tools

### Research & Analysis
- `web_search(query)` - DuckDuckGo web search
- `analyze_url(url)` - Extract and analyze webpage content
- `arxiv_search(query)` - Academic paper search with full PDF text

### Financial & Economic Data
- `get_stock_overview(symbol)` - Real-time stock, crypto, and market data
- `analyze_canadian_economy()` - Economic indicators and analysis

### Media & Content
- `analyze_youtube_url(url)` - Video transcription and analysis

### Location & Weather
- `get_weather(location)` - Weather forecasts by city or coordinates
- `get_tide_info(location)` - Canadian coastal tide times

### Toronto Data
- `get_toronto_crime(neighbourhood, crime_type)` - Crime statistics by area
- `list_toronto_neighbourhoods()` - Available neighborhoods

## Development

### Local Setup
```bash
# Core dependencies
uv sync

# With Streamlit UI
uv sync --extra local

# With development tools
uv sync --extra dev
```

### Testing Commands
```bash
# Streamlit UI
uv run streamlit run app.py

# MCP server for Claude Desktop
uv run python mcp_server.py

# HTTP mode testing
uv run python -m src.server http 8000
```

### Environment Variables
- `YOUTUBE_MAX_TOKENS=24000` - Transcript processing limit
- `WEBSHARE_PROXIES="ip:port:user:pass,..."` - Proxies for YouTube cloud deployment
- `MCP_RETRY_MAX_ATTEMPTS=3` - Auto-retry failed tool calls
- `MCP_RETRY_TYPE_COERCION=true` - Auto-fix type mismatches

### Tool Development
Tools in `src/tools/` modules use `@mcp.tool(description="...")` decorator with automatic schema generation from Python type hints.

## Deployment

### Cloud (FastMCP)
1. Push to main branch
2. FastMCP Cloud auto-deploys from GitHub
3. Get auth token from dashboard
4. Configure clients with deployment URL

### Local Development
1. Clone repository
2. `uv sync --extra local`
3. `uv run streamlit run app.py`

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [CLAUDE.md](CLAUDE.md) - Development notes
- [FastMCP Cloud](https://fastmcp.cloud)
- [MCP Protocol](https://modelcontextprotocol.io)
