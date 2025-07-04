# Claude Development Notes

## Dependency Management
- **Always use `uv` for dependency management** instead of `pip` or `python -m`
- Run commands with `uv run python` instead of just `python`
- Install packages with `uv add package-name`

## FastMCP Schema Modernization

### Issue Fixed
The `create_function_schema_from_mcp_tools` function was manually inferring OpenAI function schemas based on tool names, which is unnecessary since FastMCP automatically generates proper schemas from Python type hints.

### Before (Manual Schema Inference)
```python
# 70+ lines of manual parameter inference
if "search" in tool_name:
    schema["function"]["parameters"]["properties"]["query"] = {
        "type": "string",
        "description": "Search query"
    }
    # ... more manual work
```

### After (Native FastMCP Schemas)
```python
def create_function_schema_from_mcp_tools(mcp_tools: List[Dict]) -> List[Dict]:
    """Convert MCP tools to OpenAI function schema format using FastMCP's native schemas"""
    schemas = []
    for tool in mcp_tools:
        # Use FastMCP's native schema generation instead of manual inference
        schema = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("inputSchema", {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            }
        }
        schemas.append(schema)
    
    return schemas
```

### Benefits
- **90% less code** - Eliminated 70+ lines of manual schema inference
- **Automatic accuracy** - FastMCP generates schemas directly from Python type hints
- **Maintainability** - No need to manually update schemas when tools change
- **Type safety** - Proper validation and defaults from actual function signatures

### Example Generated Schema
```python
# From @mcp.tool decorator:
# def web_search(query: str, max_results: int = 5) -> str:

# FastMCP automatically generates:
{
    'properties': {
        'query': {'title': 'Query', 'type': 'string'}, 
        'max_results': {'default': 5, 'title': 'Max Results', 'type': 'integer'}
    }, 
    'required': ['query'], 
    'type': 'object'
}
```

## Testing Commands
```bash
# Test MCP server
uv run python test_mcp.py

# Run Streamlit apps
uv run streamlit run app.py              # Main app (in-memory transport)
uv run streamlit run app_subprocess.py  # Subprocess transport version
```

## Modular Code Organization

### Directory Structure
```
src/
├── core/
│   ├── cache.py      # Financial data caching utilities
│   ├── models.py     # Pydantic models (PaperAnalysis, SectionAnalysis)
│   └── utils.py      # General utilities and formatting helpers
├── tools/
│   ├── web.py        # web_search, analyze_url
│   ├── arxiv.py      # arxiv_search + paper analysis logic
│   ├── financial.py  # stock/crypto/market tools + caching
│   ├── youtube.py    # YouTube analysis tools + transcript handling
│   └── weather.py    # weather tools + location utilities
└── server.py         # FastMCP server setup and tool registration
```

### Adding New Tools
- **Web-related tools**: Add to `src/tools/web.py`
- **Data analysis tools**: Add to `src/tools/arxiv.py` 
- **Financial tools**: Add to `src/tools/financial.py`
- **Media tools**: Add to `src/tools/youtube.py`
- **Location tools**: Add to `src/tools/weather.py`
- **New category**: Create new file in `src/tools/` and register in `src/server.py`

### Tool Module Pattern
```python
def register_category_tools(mcp: FastMCP):
    @mcp.tool
    def your_tool(param: str) -> str:
        """Tool description"""
        # Implementation
```

### Import Examples
```python
# External clients (Windsurf, test scripts)
from mcp_server import mcp

# Streamlit apps
from src import mcp

# Internal tool modules
from ..core.models import PaperAnalysis
from ..core.utils import clean_markdown_text
```

### Compatibility
- `mcp_server.py` remains the main entry point for external clients (Windsurf, etc.)
- `src/__init__.py` exposes the server instance for internal use
- All existing functionality preserved, just better organized with proper Python packages

## Recent Fixes

### YouTube Transcript Issues (Fixed)

**Issue 1: No Transcript Available**
- **Problem**: YouTube tools returned "No transcript available" for videos with captions
- **Root cause**: Using `entry['text']` instead of `entry.text` (API object vs dict)
- **Fix**: Updated to use newer `YouTubeTranscriptApi` methods with proper attribute access
- **Result**: Now supports multiple languages and auto-generated captions

**Issue 2: Tiny Context Window**
- **Problem**: Only 8,000 characters (~2K tokens) severely limited video analysis
- **Fix**: Enhanced to support 24K+ tokens (96K+ characters) by default
- **Configuration**: Set `YOUTUBE_MAX_TOKENS` environment variable (default: 24000)
- **Adaptive truncation**: Scales based on video length vs context limit:
  - 1.5x limit: Keep 50% beginning + 30% end (80% of limit)
  - 3x limit: Keep 35% beginning + 25% end (60% of limit)  
  - 5x limit: Keep 25% beginning + 20% end (45% of limit)
  - 5x+ limit: Keep 20% beginning + 15% end (35% of limit)
- **Result**: Can now analyze videos up to 2-3 hours vs previous ~10 minute limit

## Architecture Notes
- **In-memory transport**: `Client(mcp)` - Direct server instance, fastest
- **Subprocess transport**: `Client("mcp_server.py")` - Auto-inferred, client-server separation
- Both approaches use identical tool schemas generated automatically from type hints