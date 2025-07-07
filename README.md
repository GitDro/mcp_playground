# MCP Playground

A **modern** Streamlit chat app with Ollama integration and AI-powered tool calling capabilities.

> **🚀 Built with Modern Standards!** This project uses the Model Context Protocol (MCP) for scalable, standards-compliant tool execution.

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
- `analyze_url` - Website content analysis and summarization
- `arxiv_search` - Academic paper search with deep PDF analysis
- `get_stock_price` - Current stock prices and market data
- `get_stock_history` - Historical stock performance
- `get_crypto_price` - Cryptocurrency prices
- `get_market_summary` - Market indices overview
- `summarize_youtube_video` - AI-powered YouTube video summaries
- `query_youtube_transcript` - Answer questions about YouTube videos
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
- **🧠 Vector Memory System**: Semantic memory using ChromaDB + Ollama embeddings for intelligent fact storage and retrieval
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
- "Show Tesla's performance this month"  
- "Get Bitcoin price"
- "How are the markets doing?"

**YouTube Videos:**
- "Summarize this YouTube video: [paste URL]"
- "What are the main points discussed in this video?"
- "What does the video say about [specific topic]?"

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

**Memory & Preferences:**
- "Remember that I prefer concise responses"
- "I work as a software engineer at OpenAI"
- "Set my preferred model to llama3.2"
- "What do you remember about me?"
- "Show my conversation history about machine learning"

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
- **Memory**: `remember`, `recall`, `forget` - Vector-based semantic memory
- **Web**: `web_search`, `analyze_url` - Web search and content analysis
- **Media**: `summarize_youtube_video`, `query_youtube_transcript` - YouTube analysis
- **Finance**: `get_stock_price`, `get_crypto_price`, `get_market_summary` - Financial data
- **Research**: `arxiv_search` - Academic paper analysis
- **Weather**: `get_weather` - Location-based weather forecasts
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

### Memory Tools
- `remember`: Store user information (auto-categorizes)
- `recall`: Semantic search across all memories
- `forget`: Remove by description, not IDs

### Key Benefits
- **Solves "about me" problem**: Natural language queries work perfectly
- **Auto-context injection**: Relevant memories added to conversations
- **Future-ready**: Foundation for personal document RAG

**Example**: "what do you recall about me" → finds "User likes ice cream" (43.5% similarity)

## 📚 Documentation

- **[FastMCP Overview](docs/FASTMCP_OVERVIEW.md)** - How the @mcp.tool decorator eliminates boilerplate
- **[Memory System](docs/MEMORY_SYSTEM.md)** - Vector memory architecture and usage
- **[RAG Architecture](docs/RAG_ARCHITECTURE.md)** - Technical details of semantic search
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
- Use a recent model (llama3.2, llama3.1)

**Memory not working?**
- Ensure Ollama is running: `ollama serve`
- Check model availability: `ollama list`
- Memory falls back to TinyDB if ChromaDB/Ollama unavailable

**App won't start?**
```bash
uv sync
python --version  # Requires Python 3.12+
```
