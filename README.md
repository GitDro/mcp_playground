# MCP Playground

A **modern** Streamlit chat app with Ollama integration and FastMCP-powered function calling capabilities.

> **🚀 Now Modernized with FastMCP!** This project has been upgraded to use the FastMCP framework for scalable, standards-compliant tool execution.

## 🚀 Quick Start

### Prerequisites
1. **Install Ollama**: Visit https://ollama.ai
2. **Start Ollama**: `ollama serve`
3. **Pull a model**: `ollama pull llama3.2`

### Run the App

#### Option 1: FastMCP Version (Recommended)
```bash
git clone <your-repo>
cd mcp_playground
uv sync

# Run the modern FastMCP version
uv run streamlit run app_fastmcp.py
```

#### Option 2: Legacy Version
```bash
# Run the original version (legacy)
uv run streamlit run app.py
```

Open http://localhost:8501

#### Option 3: Standalone FastMCP Server
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

## 🏗️ Architecture

### FastMCP Version (Modern)
```
app_fastmcp.py  # Modern Streamlit app with FastMCP client integration
mcp_server.py   # FastMCP server with all tools using @mcp.tool decorators
ui_config.py    # UI styling and system prompts (shared)
```

### Legacy Version
```
app.py          # Original Streamlit application & chat logic
tools.py        # Legacy function calling implementation
ui_config.py    # UI styling and system prompts (shared)
```

### Key Improvements with FastMCP

- **🏗️ Standards-Compliant**: Uses the official Model Context Protocol (MCP) standard
- **🎯 Automatic Schema Generation**: FastMCP automatically generates tool schemas from type hints
- **🔧 Simplified Tool Definition**: Clean `@mcp.tool` decorators replace manual schema definitions
- **📡 Multiple Transport Support**: Supports stdio, HTTP, and SSE transports
- **🔌 Better Integration**: Can be used as standalone server or embedded in applications
- **🚀 Scalable**: Built for production use with proper error handling and logging

## 🔧 Using the FastMCP Server

### As a Standalone Server

The FastMCP server can run independently and be used by any MCP-compatible client:

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

### FastMCP Client Usage

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
        result = await client.call_tool("web_search", {"query": "FastMCP framework"})
        print(result.content[0].text)

# Run the example
asyncio.run(use_mcp_tools())
```

#### Option 2: Subprocess Transport (For client-server separation)
```python
from fastmcp import Client
import asyncio

async def use_mcp_tools():
    # Auto-inferred subprocess transport - FastMCP handles process management
    async with Client("mcp_server.py") as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        
        # Call a tool
        result = await client.call_tool("web_search", {"query": "FastMCP framework"})
        print(result.content[0].text)

# Run the example
asyncio.run(use_mcp_tools())
```

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

---

## 🔄 Migration from Legacy to FastMCP

If you're using the legacy version (`app.py` + `tools.py`), you can easily migrate to the FastMCP version:

### Legacy (tools.py)
```python
def get_function_schema() -> List[Dict]:
    return [{
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        }
    }]

def execute_function(function_name: str, arguments: dict) -> str:
    if function_name == "web_search":
        return web_search(arguments.get("query", ""))
```

### FastMCP (mcp_server.py)
```python
from fastmcp import FastMCP

mcp = FastMCP(name="MCPPlaygroundServer")

@mcp.tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo for current information"""
    # Implementation here
    return results
```

### Benefits of Migration

- ✅ **90% less boilerplate code** - No manual schema definitions
- ✅ **Automatic type validation** - FastMCP handles parameter validation  
- ✅ **Better error handling** - Built-in error management and logging
- ✅ **Multiple deployment options** - stdio, HTTP, SSE transports
- ✅ **Standards compliance** - Official MCP protocol implementation
- ✅ **Future-proof** - Active development and community support

---

**Modern. Scalable. Standards-compliant.** 🚀