"""
UI Configuration for MCP Playground

This module contains CSS styles and UI constants for the Streamlit app.
"""

# CSS Styles for the app
STREAMLIT_STYLE = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    header {visibility: hidden;}
    
    /* Style the chat input - centered and prominent */
    .stChatInput > div {
        position: fixed;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 60%;
        max-width: 800px;
        background: white;
        z-index: 999;
        padding: 1.5rem;
        border: 2px solid #4F8A8B;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
    }
    
    /* Style the input field itself */
    .stChatInput input {
        border: none !important;
        font-size: 16px !important;
        padding: 12px 16px !important;
    }
    
    /* Fix send button alignment */
    .stChatInput button {
        margin-left: 8px !important;
        align-self: center !important;
    }
    
    /* Add padding to content to account for fixed input */
    .main .block-container {
        padding-bottom: 140px;
    }
    </style>
"""

# Help text for the Tools section
TOOLS_HELP_TEXT = """
With **Tools** enabled, I can:
- **Search** the web for current information
- **Analyze** content from any URL
- **Find** academic papers on arXiv
- **Get** comprehensive financial data for stocks, crypto, and market indices

**Example prompts:**
- *"Search for Python 3.13 features"*
- *"What's new on the OpenAI blog?"*
- *"Analyze https://example.com"*
- *"Find papers on quantum computing"*
- *"What's Apple's stock price?"*
- *"Show Tesla's performance"*
- *"Get Bitcoin price"*
- *"How is NVDA doing?"*
"""

# System prompt for function calling guidance
def get_system_prompt(current_date: str) -> str:
    """Generate the system prompt with current date"""
    return f"""You are a helpful AI assistant. Today's date is {current_date}. You have access to tools but should use them ONLY when absolutely necessary.

STRICT RULES FOR TOOL USAGE:
1. NEVER use tools for:
   - Greetings, casual conversation, or small talk
   - General knowledge questions you can answer from training
   - Explaining concepts, definitions, or how-to questions
   - Math, coding problems, or theoretical discussions

2. ONLY use web_search when user EXPLICITLY requests:
   - Current/recent/latest news or events
   - Real-time information with keywords like "today", "now", "current"
   - Specific searches with phrases like "search for", "find", "look up"

3. ONLY use analyze_url when user provides a specific URL/link

4. ONLY use arxiv_search when user explicitly asks for academic papers or research with keywords like "papers", "research", "arxiv", "academic", "study"

5. ONLY use financial tools when user explicitly asks for:
   - Financial data: get_financial_data for stocks, crypto, or market indices (e.g., AAPL, BTC, SPY)

ALWAYS try to answer from your knowledge first. Only use tools as a last resort when current information is specifically requested.

IMPORTANT: When you use tools, the results are already perfectly formatted. DO NOT rewrite, summarize, or reformat the tool results. Simply present them as-is. The tool outputs are designed to be user-ready.

Examples - DO NOT use tools:
- "Hello" → Just greet back
- "What is Python?" → Explain from knowledge  
- "How do I use Git?" → Provide instructions from training
- "Explain AI" → Use your knowledge

Examples - USE tools:
- "Search for Python 3.13 news" → Use web_search
- "What's the latest on OpenAI?" → Use web_search  
- "Analyze https://example.com" → Use analyze_url
- "What's Apple's stock price?" → Use get_financial_data
- "Show Tesla's performance" → Use get_financial_data
- "Get Bitcoin price" → Use get_financial_data
- "How is NVDA doing?" → Use get_financial_data
- "Find papers on quantum computing" → Use arxiv_search
- "Search for research on transformers" → Use arxiv_search"""