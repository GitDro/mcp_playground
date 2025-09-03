# MCP Arena

A comprehensive research and analysis toolkit deployed via the Model Context Protocol (MCP). Access real-time data for research, financial analysis, crime statistics, weather, and more through both local Streamlit UI and cloud deployment.

## 🚀 Quick Start

### Local Development
```bash
git clone <your-repo>
cd mcp_arena
uv sync --extra local

# Run Streamlit UI for testing
uv run streamlit run app.py
```

### Cloud Deployment
**Live Server**: https://mcp-playground.fastmcp.app/mcp

Use with any MCP-compatible client (Claude Desktop, Claude Code, VS Code).

## 🔧 MCP Integration

### Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "mcp-arena": {
      "type": "http",
      "url": "https://mcp-playground.fastmcp.app/mcp",
      "authorization_token": "your-fastmcp-cloud-token"
    }
  }
}
```

### Claude Code / VS Code

**Claude Code Integration:**
1. Open Claude Code
2. Access MCP settings: `Cmd/Ctrl + Shift + P` → "MCP: Add Server"
3. Choose **"Add remote HTTP server"**
4. Configure:
   - **URL**: `https://mcp-playground.fastmcp.app/mcp`
   - **Authorization Token**: Get from FastMCP Cloud dashboard
   - **Scope**: Choose project/user/local based on needs
5. Save and start using tools in chat

**VS Code Integration:**
1. Install MCP extension or Claude Code extension
2. Add remote HTTP server with same URL and token
3. Access tools through the extension interface

### Local MCP Server
```bash
# For Claude Desktop (stdio mode)
uv run python mcp_server.py

# Test HTTP mode locally
uv run python -m src.server http 8000
```

## 📊 Available Tools

### Research & Analysis
- **`web_search(query)`** - DuckDuckGo web search with clean results
- **`analyze_url(url)`** - Extract and analyze webpage content  
- **`arxiv_search(query)`** - Academic paper search with full PDF text

### Financial & Economic Data
- **`get_stock_overview(symbol)`** - Real-time stock, crypto, and market data
- **`analyze_canadian_economy()`** - Economic indicators and analysis

### Media & Content  
- **`analyze_youtube_url(url)`** - Video transcription and analysis

### Location & Weather
- **`get_weather(location)`** - Weather forecasts by city or coordinates
- **`get_tide_info(location)`** - Canadian coastal tide times

### Toronto Data
- **`get_toronto_crime(neighbourhood, crime_type)`** - Crime statistics by area
- **`list_toronto_neighbourhoods()`** - Complete list of available neighborhoods

### System
- **`health_check()`** - Server health monitoring (cloud deployment)

## 💡 Example Usage

**Research:**
- "Search for recent developments in quantum computing"
- "Analyze this research paper: https://arxiv.org/abs/..."
- "What does this webpage say about climate change?"

**Financial Analysis:**  
- "Get Apple stock price and recent performance"
- "How is the Canadian economy doing?"
- "Bitcoin price and market trends"

**Location Services:**
- "Weather in Toronto this week"
- "High tide times in Vancouver today"  
- "Crime statistics for downtown Toronto"

**Media Analysis:**
- "Summarize this YouTube video about AI"
- "What are the key points from this lecture?"

## 🏗️ Architecture

### Unified Server Design
```
src/server.py           # Core server (stdio + HTTP modes)
├── mcp_server.py       # Local development entry point  
├── cloud_server.py     # FastMCP Cloud deployment entry
└── app.py              # Streamlit UI for local testing
```

### Deployment Modes

**Local Development (stdio)**:
```bash
uv run python mcp_server.py
# → Direct connection to Claude Desktop
```

**Local HTTP Testing**:  
```bash  
uv run python -m src.server http 8000
# → Test HTTP transport at localhost:8000
```

**Cloud Deployment**:
```bash
uv run python cloud_server.py  
# → FastMCP Cloud at https://mcp-playground.fastmcp.app/mcp
```

## 🛠️ Development

### Dependencies
```bash
# Core tools only
uv sync

# With Streamlit UI  
uv sync --extra local

# With development tools
uv sync --extra dev
```

### Configuration

#### Environment Files Explained

**For Local Development:**
```bash
# Copy the local template
cp .env.example .env

# Edit as needed for your local setup
# Contains: server settings, tool config, retry system
```

**For Cloud Deployment:**
```bash
# Usually no .env file needed at all!
# FastMCP Cloud provides all defaults automatically

# Only create .env if you need custom overrides (rare):
# Just create .env with the specific variables you want to override
```

#### Key Environment Variables

**Tool Configuration:**
- `YOUTUBE_MAX_TOKENS=24000` - Transcript processing limit
- `CACHE_DIRECTORY=cache` - Local cache storage location

**Server Settings (Local Only):**
- `HOST=0.0.0.0` - Server host for HTTP mode
- `PORT=8000` - Server port for HTTP mode  
- `LOG_LEVEL=INFO` - Logging verbosity

**Retry System:**
- `MCP_RETRY_MAX_ATTEMPTS=3` - Auto-retry failed tool calls
- `MCP_RETRY_TYPE_COERCION=true` - Auto-fix type mismatches

### Tool Development
Tools are organized in `src/tools/` modules:
- Each module registers tools with `@mcp.tool(description="...")`
- Automatic schema generation from Python type hints
- Built-in retry system with type coercion
- Error handling and logging

## 📚 Key Features

### Real-Time Data Access
- No API keys required for most tools
- Direct web scraping and API integration
- Cached responses for performance

### Robust Error Handling  
- Automatic retry with exponential backoff
- Type coercion (string → int/bool/float)
- Graceful fallbacks for network issues

### Stateless Design
- No local dependencies for cloud deployment
- Works anywhere with internet connection
- Optimized for serverless environments

### Standards Compliant
- Full MCP protocol implementation
- Compatible with any MCP client
- FastMCP framework for rapid development

## 🚀 Deployment

### FastMCP Cloud
1. **Push to main branch**
2. **FastMCP Cloud auto-deploys** from GitHub
3. **Get auth token** from dashboard
4. **Configure clients** with deployment URL

### Local Development  
1. **Clone repository**
2. **Install dependencies**: `uv sync --extra local`
3. **Run Streamlit UI**: `uv run streamlit run app.py`
4. **Test MCP server**: `uv run python mcp_server.py`

## 🆘 Troubleshooting

**Tools not working?**
- Check internet connection
- Verify MCP client configuration
- Check server logs for errors

**Authentication issues?**  
- Verify FastMCP Cloud token
- Check token hasn't expired
- Ensure correct deployment URL

**Local development issues?**
```bash
uv sync --extra local
python --version  # Requires Python 3.12+
```

## 📄 Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Detailed deployment guide
- **[CLAUDE.md](CLAUDE.md)** - Development notes and architecture
- **FastMCP Cloud**: https://fastmcp.cloud
- **MCP Protocol**: https://modelcontextprotocol.io

---

**🎉 Ready for both local development and global deployment!**