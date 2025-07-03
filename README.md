# MCP Playground

A **minimal** Streamlit chat app with Ollama integration and function calling capabilities.

## 🚀 Quick Start

### Prerequisites
1. **Install Ollama**: Visit https://ollama.ai
2. **Start Ollama**: `ollama serve`
3. **Pull a model**: `ollama pull llama3.2`

### Run the App
```bash
git clone <your-repo>
cd mcp_arena
uv sync
uv run streamlit run app.py
```

Open http://localhost:8501

## ✨ Capabilities

- **💬 Chat**: Direct integration with local Ollama models
- **🔍 Web Search**: Real-time DuckDuckGo search with current information
- **📄 URL Analysis**: Analyze and summarize content from any website  
- **📚 arXiv Search**: Find and deeply analyze academic papers with structured insights
- **📈 Financial Data**: Get stock prices, crypto rates, and market summaries without API keys
- **🎥 YouTube Transcripts**: Extract, summarize, and query video content from YouTube links
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
- "Extract transcript from https://youtu.be/VIDEO_ID"
- "Summarize this YouTube video: [paste URL]"
- "What are the main points discussed in this video?"

## 🏗️ Architecture

```
app.py          # Main Streamlit application & chat logic
tools.py        # Function calling: web search, URL analysis, arXiv
ui_config.py    # UI styling and system prompts
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

**Simple. Fast. Actually works.** 🚀