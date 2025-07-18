# MCP Playground

* A **modern** Streamlit chat app with Ollama integration and AI-powered tool calling capabilities.
* This project uses the **Model Context Protocol (MCP)** for scalable, standards-compliant tool execution.

## 🚀 Quick Start

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

#### Add to Windsurf IDE

You can use these tools directly in Windsurf IDE through MCP integration:

1. **Create Windsurf MCP config file**:
   ```bash
   mkdir -p ~/.codeium/windsurf
   ```

2. **Add this configuration** to `~/.codeium/windsurf/mcp_config.json`:
   ```json
   {
     "mcpServers": {
       "mcp-playground": {
         "command": "/Users/YOUR_USERNAME/Documents/GitHub/mcp_playground/.venv/bin/python3",
         "args": ["/Users/YOUR_USERNAME/Documents/GitHub/mcp_playground/mcp_server.py", "stdio"],
         "cwd": "/Users/YOUR_USERNAME/Documents/GitHub/mcp_playground"
       }
     }
   }
   ```
   
   **Note**: Replace `YOUR_USERNAME` with your actual username, or use the full path to your project.

3. **Restart Windsurf** and access tools via Cascade panel → Plugins

**Available Tools in Windsurf:**
- `web_search` - Real-time web search with DuckDuckGo
- `summarize_url` - Website content summarization and analysis
- `arxiv_search` - Academic paper search with deep PDF analysis
- `get_stock_overview` - Comprehensive financial data for stocks, crypto, and market indices with trend visualization
- `analyze_youtube_url` - AI-powered YouTube analysis - summaries or targeted Q&A
- `get_weather` - Current weather and forecasts by city name or coordinates
- `get_tide_info` - Canadian tide information with high/low times and heights
- `get_toronto_crime` - Toronto neighbourhood crime statistics with trend analysis and visualization

#### Standalone MCP Server
```bash
# Run as standalone MCP server (stdio mode)
uv run python mcp_server.py

# Run as HTTP server for web integration
uv run python mcp_server.py http 8000
```

## ✨ Capabilities

- **💬 Chat**: Direct integration with local Ollama models
- **🔍 Web Search**: Real-time DuckDuckGo search with current information
- **📄 URL Analysis**: Analyze and summarize content from any website  
- **📚 arXiv Search**: Find and deeply analyze academic papers with structured insights
- **📈 Financial Data**: Get stock prices, crypto rates, and market summaries without API keys
- **🎥 YouTube Analysis**: Analyze and summarize video content from YouTube links (includes beginning + ending for longer videos)
- **🌤️ Weather**: Get current weather and 7-day forecasts by IP location, city name, or coordinates (prefers Canada, no API keys needed)
- **🌊 Tide Information**: Canadian coastal tide times and heights with emoji indicators (Halifax, Vancouver, St. Johns, etc.)
- **🚨 Crime Analytics**: Toronto neighbourhood safety statistics with semantic neighbourhood search and trend visualization
- **🧠 Simple Memory System**: Natural conversation history injection with 80% relevance threshold (MVP - July 2025)
- **🎛️ Function Toggle**: Enable/disable AI tool usage per conversation

## 🎯 Example Prompts

**Web Search:**
- "Search for Python 3.13 features"
- "What's the latest news on AI?"

**URL Analysis:**
- "Analyze https://example.com"
- "Summarize the content at this URL"

**Academic Research:**
- "Find papers on transformer architectures"
- "Search for recent quantum computing research"

**Financial Data:**
- "What's Apple's stock price?"
- "Show Tesla's performance"  
- "Get Bitcoin price"
- "How is NVDA doing?"

**YouTube Videos:**
- "Analyze this YouTube video: [paste URL]"
- "What are the main points in this video: [URL]?"
- "What does this video say about AI: [URL]?"

**Weather:**
- "What's the weather like?"
- "Show me the weather forecast"
- "Get weather for Niagara Falls"
- "Weather in Toronto"

**Tide Information:**
- "When is high tide in Halifax today?"
- "Show me Halifax tide times for July 20th"
- "Get tide information for Vancouver tomorrow"
- "What are the tides like in St. Johns?"

**Crime Analytics:**
- "What is crime like in Rosedale?"
- "Show me car theft statistics for downtown Toronto"
- "How safe is Harbourfront neighbourhood?"
- "Compare assault rates in different Toronto areas"

**Memory & Preferences (MVP 2025):**
- "Remember I like reading sci-fi books"
- Next: "Any book recommendations?" (automatic context: "Since you enjoy sci-fi books...")
- "What do you remember about me?" (simple direct response)
- High precision: only 80%+ relevant facts injected

## 🏗️ Architecture

### Core Components
```
app.py                    # Main Streamlit application
mcp_server.py            # FastMCP server with all tools
src/core/vector_memory.py # Vector memory with ChromaDB + Ollama
src/tools/               # Organized tool modules
```

### Key Benefits
- **Standards-Compliant**: Uses Model Context Protocol (MCP)
- **Automatic Schema Generation**: From Python type hints
- **Vector Memory**: Semantic search with local embeddings
- **Modular Design**: Clean tool organization

## 🔧 MCP Server Usage

### Standalone Server
```bash
# Run as MCP server
uv run python mcp_server.py stdio

# Run as HTTP server
uv run python mcp_server.py http 8000
```

### Available Tools
- **Memory**: `remember`, `recall`, `forget` - Conversation context and preferences
- **Documents**: `store_note`, `find_saved`, `list_saved`, `clean_duplicates` - Knowledge base management
- **Web**: `web_search`, `summarize_url`, `save_link` - Web search, analysis, and content saving
- **Media**: `analyze_youtube_url` - YouTube analysis (summaries and Q&A)
- **Finance**: `get_stock_overview` - Comprehensive financial data with visualization
- **Research**: `arxiv_search` - Academic paper analysis
- **Weather**: `get_weather` - Location-based weather forecasts
- **Canadian Economy**: `analyze_canadian_economy` - Comprehensive economic analysis with Statistics Canada data (CPI, GDP, employment)
- **Tides**: `get_tide_info` - Canadian coastal tide times and heights
- **Crime**: `get_toronto_crime` - Toronto neighbourhood safety statistics with semantic search and visualization

### Client Integration
```python
from fastmcp import Client
from mcp_server import mcp

async def use_tools():
    async with Client(mcp) as client:
        result = await client.call_tool("web_search", {"query": "MCP framework"})
        print(result.content[0].text)
```

## 🧠 Vector Memory System

**Semantic memory that understands meaning, not just keywords.**

### Architecture
- **ChromaDB + Ollama**: `nomic-embed-text` embeddings (768d, 8K context)
- **Semantic Search**: "about me" finds "User likes ice cream" via meaning
- **Hybrid Storage**: Vector facts + TinyDB preferences
- **Local & Private**: All data at `~/.cache/mcp_playground/`

### Memory vs Documents
- **Memory Tools** (`remember`, `recall`, `forget`): Conversation context only
- **Document Tools** (`store_note`, `find_saved`, `list_saved`): Permanent knowledge base
- **Web Tools** (`save_link`, `summarize_url`): Content saving and analysis

### Key Benefits (MVP July 2025)
- **Simple & Effective**: Conversation history injection instead of complex prompt engineering
- **High Precision**: 80% similarity threshold prevents irrelevant memory injection
- **Natural Integration**: LLM treats memory as conversation context, not external data  
- **No Confusion**: Eliminates "I don't know X while showing X" responses
- **Minimal Code**: ~50 lines vs 500+ lines of complexity
- **Reliable**: ChromaDB semantic search with conversation history injection

**How It Works**:
1. `remember("User likes reading sci-fi books")` → stored in ChromaDB
2. "Any good book recommendations?" → 86% similarity found
3. System injects: "Just so you know, user likes reading sci-fi books"
4. LLM: "Since you enjoy sci-fi books, I'd recommend..." (natural response)

**Precision Examples**:
- ✅ "sci-fi book recs" → 86% similarity → memory injected
- ❌ "what's the weather" → <80% similarity → no injection
- ✅ Clean separation: tool queries vs memory queries

## 📚 Documentation

- **[FastMCP Overview](docs/FASTMCP_OVERVIEW.md)** - How the @mcp.tool decorator eliminates boilerplate
- **[Memory System](docs/MEMORY_SYSTEM.md)** - Simple MVP memory system with conversation history injection
- **[RAG Architecture](docs/RAG_ARCHITECTURE.md)** - Simplified RAG with high-precision filtering
- **[FastMCP Usage](docs/FASTMCP_USAGE.md)** - FastMCP framework documentation

## 🔧 Troubleshooting

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
