# MCP Arena

A simple, working Streamlit chat application with Ollama integration and function calling capabilities.

## Features

- 🤖 **Local AI Chat**: Direct integration with Ollama models
- 🔍 **Web Search**: Built-in DuckDuckGo search functionality  
- 📄 **URL Analysis**: Analyze and summarize content from any URL
- ⚙️ **Function Toggle**: Enable/disable AI tool usage
- 🧹 **Clean Interface**: Simple Streamlit UI that just works

## Quick Start

### Prerequisites

1. **Install Ollama** and have it running:
   ```bash
   # Install Ollama (visit https://ollama.ai for installation)
   ollama serve
   
   # Pull a model (required)
   ollama pull llama3.1:latest
   # or
   ollama pull llama3.2:latest
   ```

2. **Verify Ollama is working**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

### Installation & Running

1. **Clone and setup**:
   ```bash
   git clone <your-repo>
   cd mcp_arena
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Run the app**:
   ```bash
   uv run streamlit run app.py
   ```

4. **Open in browser**: http://localhost:8501

## Usage

### Basic Chat
1. Select an Ollama model from the sidebar
2. Type your message and press Enter
3. The AI will respond using the selected model

### Function Calling Examples

With function calling enabled (default), try these prompts:

**Web Search:**
- "Search for the latest news about artificial intelligence"
- "What's new with Python 3.13?"
- "Find recent research on quantum computing"

**URL Analysis:**
- "Analyze the content of https://www.anthropic.com"
- "What's on the OpenAI blog homepage?"
- "Summarize https://arxiv.org/abs/2301.00001"

**Mixed Queries:**
- "Search for recent ChatGPT updates and summarize the top result"
- "Find and analyze the latest Python release notes"

### Settings

- **Model Selection**: Choose from available Ollama models
- **Function Calling**: Toggle AI's ability to use web search and URL analysis
- **Clear Chat**: Reset the conversation

## Architecture

```
app.py                  # Main Streamlit application
├── get_ollama_models() # Fetch available models
├── web_search()        # DuckDuckGo search integration  
├── analyze_url()       # URL content analysis
└── chat_with_ollama()  # Chat with function calling
```

### Function Calling Flow

1. User sends message to AI
2. AI determines if tools are needed
3. If needed, AI calls `web_search()` or `analyze_url()`
4. Tool results are sent back to AI
5. AI responds with final answer incorporating tool results

## Dependencies

- **streamlit**: Web interface
- **requests**: HTTP client for Ollama API
- **duckduckgo-search**: Web search functionality
- **httpx**: Async HTTP client for URL analysis

## Configuration

The app automatically detects:
- Available Ollama models on localhost:11434
- Network connectivity for web search
- URL accessibility for analysis

No configuration files needed!

## Troubleshooting

### "No Ollama models found"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Pull a model if none exist  
ollama pull llama3.1:latest
```

### "Function calling not working"
- Ensure you're using a model that supports function calling (llama3.1, llama3.2, etc.)
- Check that "Enable function calling" is checked in the sidebar
- Verify internet connectivity for web search

### "App won't start"
```bash
# Reinstall dependencies
uv sync

# Check Python version
python --version  # Should be 3.12+

# Run with verbose output
uv run streamlit run app.py --logger.level=debug
```

## Development

The codebase is intentionally minimal and easy to modify:

- **Add new functions**: Define in `app.py` and add to `get_function_schema()`
- **Modify UI**: Update Streamlit components in the main section
- **Change models**: Update Ollama model detection logic

## Legacy Files

The following files are kept for reference but not used:
- `*.legacy` - Previous FastAPI/JavaScript implementation
- `data/` - Database files from previous version

## License

MIT License - See LICENSE file for details.

---

**Simple. Fast. Actually works.** 🚀