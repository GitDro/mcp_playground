# MCP Playground

A **modern** Streamlit chat app with Ollama integration and AI-powered tool calling capabilities.

> **🚀 Built with Modern Standards!** This project uses the Model Context Protocol (MCP) for scalable, standards-compliant tool execution.

## 🚀 Quick Start

### Prerequisites
1. **Install Ollama**: Visit https://ollama.ai
2. **Start Ollama**: `ollama serve`
3. **Pull a model**: `ollama pull llama3.2`

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
- **🧠 Memory System**: Persistent memory across conversations with fact storage, preferences, and conversation history
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
- "Show weather for Berlin" (coordinates: 52.52,13.41)

**Memory & Preferences:**
- "Remember that I prefer concise responses"
- "I work as a software engineer at OpenAI"
- "Set my preferred model to llama3.2"
- "What do you remember about me?"
- "Show my conversation history about machine learning"

## 🏗️ Architecture

### Core Files
```
app.py          # Main Streamlit application with in-memory MCP integration
app_subprocess.py # Alternative version using subprocess MCP transport
mcp_server.py   # MCP server with all tools using @mcp.tool decorators
ui_config.py    # UI styling and system prompts
```

### Key Benefits of Modern MCP Architecture

- **🏗️ Standards-Compliant**: Uses the official Model Context Protocol (MCP) standard
- **🎯 Automatic Schema Generation**: Automatically generates tool schemas from Python type hints
- **🔧 Simplified Tool Definition**: Clean `@mcp.tool` decorators replace manual schema definitions
- **📡 Multiple Transport Support**: Supports stdio, HTTP, and SSE transports
- **🔌 Better Integration**: Can be used as standalone server or embedded in applications
- **🚀 Scalable**: Built for production use with proper error handling and logging

## 🔧 Using the MCP Server

### As a Standalone Server

The MCP server can run independently and be used by any MCP-compatible client:

```bash
# Run in stdio mode (for local development)
uv run python mcp_server.py stdio

# Run as HTTP server (for web applications)
uv run python mcp_server.py http 8000

# Run as HTTP server with custom host
uv run python mcp_server.py http 8000 localhost
```

### Integration with Other Applications

The server provides all the same tools available in the Streamlit app:

- **web_search**: Real-time web search using DuckDuckGo
- **analyze_url**: Analyze and extract information from web pages
- **arxiv_search**: Search and analyze academic papers with deep PDF analysis
- **get_stock_price**: Current stock prices and information
- **get_stock_history**: Historical stock data and trends
- **get_crypto_price**: Cryptocurrency prices
- **get_market_summary**: Market indices overview
- **summarize_youtube_video**: AI-powered YouTube video summaries
- **query_youtube_transcript**: Answer questions about YouTube video content
- **get_weather**: Current weather and 7-day forecast by IP, city name, or coordinates
- **remember**: Store important facts about the user (auto-categorizes)
- **recall**: Retrieve all relevant information from memory  
- **forget**: Remove specific information by description

### MCP Client Usage

#### Option 1: In-Memory Transport (Recommended for embedded use)
```python
from fastmcp import Client
from mcp_server import mcp
import asyncio

async def use_mcp_tools():
    # Direct server instance - fastest, embedded approach
    async with Client(mcp) as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        
        # Call a tool
        result = await client.call_tool("web_search", {"query": "MCP framework"})
        print(result.content[0].text)

# Run the example
asyncio.run(use_mcp_tools())
```

#### Option 2: Subprocess Transport (For client-server separation)
```python
from fastmcp import Client
import asyncio

async def use_mcp_tools():
    # Auto-inferred subprocess transport - handles process management
    async with Client("mcp_server.py") as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        
        # Call a tool
        result = await client.call_tool("web_search", {"query": "MCP framework"})
        print(result.content[0].text)

# Run the example
asyncio.run(use_mcp_tools())
```

## 🧠 Memory System

The app includes a sophisticated memory system that enables persistent conversations and personalized interactions:

- **Working Memory**: Session-based conversation context and tool usage tracking
- **Short-Term Memory**: Cross-session conversation summaries (7-day retention)  
- **Long-Term Memory**: Persistent user facts, preferences, and interaction patterns
- **Storage**: Local TinyDB database at `~/.cache/mcp_playground/memory.json`
- **Privacy**: All memory data stays on your local machine

### Memory Tools  
- `remember`: Store any important user information (auto-categorizes)
- `recall`: Search and retrieve all relevant information from memory
- `forget`: Remove specific information by description

The system automatically injects relevant context from memory into conversations and saves conversation summaries when you clear the chat.

## 🔧 Troubleshooting

**No models found?**
```bash
ollama serve
ollama pull llama3.2
```

**Function calling not working?**
- Check internet connection
- Ensure "Tools" checkbox is enabled  
- Use a recent model (llama3.2, llama3.1)

**App won't start?**
```bash
uv sync
python --version  # Requires Python 3.12+
```

**Windsurf MCP integration issues?**
- Ensure you're using the full absolute path to the virtual environment Python
- Check that the path in `mcp_config.json` matches your actual project location
- Restart Windsurf after adding the configuration
- Test the server manually: `uv run python mcp_server.py stdio`
- Tools will appear in Cascade panel → Plugins after restart

---
