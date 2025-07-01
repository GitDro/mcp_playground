"""
MCP Arena - Simple Streamlit Chat App with Function Calling

A minimal, working chat application that integrates with Ollama for local AI
and includes web search and URL analysis capabilities.

Author: MCP Arena Team
Version: 1.0.0
"""

import streamlit as st
import requests
import json
from typing import List, Dict
from duckduckgo_search import DDGS
import httpx

# Page config - Minimalist setup
st.set_page_config(
    page_title="MCP Playground",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ollama_models() -> List[str]:
    """
    Fetch available Ollama models from the local Ollama instance.
    
    Returns:
        List of model names, empty list if Ollama is not accessible
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        else:
            return []
    except:
        return []

# ============================================================================
# FUNCTION CALLING TOOLS
# ============================================================================

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo"""
    try:
        # Ensure max_results is an integer (in case it comes as string from JSON)
        if isinstance(max_results, str):
            max_results = int(max_results)
        max_results = max(1, min(max_results or 5, 10))  # Clamp between 1 and 10
        
        # Validate query
        if not query or not query.strip():
            return "Error: Search query cannot be empty"
        
        query = query.strip()
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"No search results found for: {query}"
        
        # Format results as markdown
        formatted_results = f"#### Search Results for: {query}\n\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"**{i}. {result.get('title', 'No Title')}**\n"
            formatted_results += f"**URL**: {result.get('href', 'No URL')}\n"
            formatted_results += f"**Summary**: {result.get('body', 'No description available')}\n\n"
            formatted_results += "---\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Error performing search: {str(e)}"

def analyze_url(url: str) -> str:
    """Analyze a URL and return basic info"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content)
            
            summary = f"# URL Analysis\n\n"
            summary += f"**URL**: {url}\n"
            summary += f"**Content Type**: {content_type}\n"
            summary += f"**Content Length**: {content_length:,} bytes\n\n"
            
            if 'text/html' in content_type:
                # Basic text extraction for web pages
                text_content = response.text[:1000]  # First 1000 chars
                summary += f"**Preview**: {text_content}...\n"
            else:
                summary += f"**Note**: Non-HTML content detected.\n"
            
            return summary
            
    except Exception as e:
        return f"Error analyzing URL: {str(e)}"

def arxiv_search(query: str, max_results: int = 5) -> str:
    """Search arXiv for academic papers"""
    try:
        import arxiv
        
        # Validate and sanitize inputs
        if isinstance(max_results, str):
            max_results = int(max_results)
        max_results = max(1, min(max_results or 5, 10))
        
        if not query or not query.strip():
            return "Error: Search query cannot be empty"
        
        query = query.strip()
        
        # Create client and search
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        
        results = list(client.results(search))
        
        if not results:
            return f"No papers found for: {query}"
        
        # Format results as markdown
        formatted_results = f"#### arXiv Papers for: {query}\n\n"
        for i, result in enumerate(results, 1):
            # Truncate abstract for readability
            abstract = result.summary.replace('\n', ' ').strip()
            if len(abstract) > 250:
                abstract = abstract[:247] + "..."
            
            formatted_results += f"**{i}. {result.title}**\n"
            formatted_results += f"**Authors**: {', '.join([author.name for author in result.authors[:3]])}"
            if len(result.authors) > 3:
                formatted_results += f" (and {len(result.authors) - 3} others)"
            formatted_results += "\n"
            formatted_results += f"**Published**: {result.published.strftime('%Y-%m-%d')}\n"
            formatted_results += f"**arXiv ID**: {result.entry_id.split('/')[-1]}\n"
            formatted_results += f"**Categories**: {', '.join(result.categories[:2])}\n"
            formatted_results += f"**Abstract**: {abstract}\n"
            formatted_results += f"**PDF**: {result.pdf_url}\n\n"
            formatted_results += "---\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"

# ============================================================================
# FUNCTION CALLING CONFIGURATION
# ============================================================================

def get_function_schema():
    """
    Define available functions for Ollama function calling.
    
    Returns:
        List of function schemas in OpenAI format
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "RESTRICTED: Only use when user EXPLICITLY asks for current/recent/latest information with keywords like 'search', 'find', 'latest', 'current', 'recent', 'today', 'now'. Never use for general questions or explanations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for time-sensitive information explicitly requested by user"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5)"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_url",
                "description": "RESTRICTED: Only use when user explicitly provides a URL/link and asks to analyze it. Never use unless user specifically mentions a URL to analyze.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The specific URL provided by user to analyze"
                        }
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "arxiv_search",
                "description": "RESTRICTED: Only use when user explicitly asks to search for academic papers, research, or scientific literature with keywords like 'papers', 'research', 'arxiv', 'academic', 'study'. Never use for general questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Academic search query for finding research papers"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of papers to return (default: 5)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

def execute_function(function_name: str, arguments: dict) -> str:
    """Execute a function call with proper type conversion"""
    try:
        if function_name == "web_search":
            query = str(arguments.get("query", ""))
            max_results = arguments.get("max_results", 5)
            # Convert max_results to int if it's a string
            if isinstance(max_results, str):
                max_results = int(max_results)
            return web_search(query, max_results)
        elif function_name == "analyze_url":
            url = str(arguments.get("url", ""))
            return analyze_url(url)
        elif function_name == "arxiv_search":
            query = str(arguments.get("query", ""))
            max_results = arguments.get("max_results", 5)
            # Convert max_results to int if it's a string
            if isinstance(max_results, str):
                max_results = int(max_results)
            return arxiv_search(query, max_results)
        else:
            return f"Unknown function: {function_name}"
    except Exception as e:
        return f"Error executing {function_name}: {str(e)}"

# ============================================================================
# MAIN CHAT FUNCTION
# ============================================================================

def chat_with_ollama(model: str, message: str, conversation_history: List[Dict], use_functions: bool = True) -> str:
    """
    Send chat message to Ollama with optional function calling support.
    
    Args:
        model: Ollama model name to use
        message: User's message
        conversation_history: Previous messages in the conversation
        use_functions: Whether to enable function calling
        
    Returns:
        AI response string, potentially including function call results
    """
    try:
        # Format conversation for Ollama with system guidance
        messages = []
        
        # Add system message for function calling guidance
        if use_functions:
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            system_message = {
                "role": "system",
                "content": f"""You are a helpful AI assistant. Today's date is {current_date}. You have access to tools but should use them ONLY when absolutely necessary.

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

ALWAYS try to answer from your knowledge first. Only use tools as a last resort when current information is specifically requested.

Examples - DO NOT use tools:
- "Hello" → Just greet back
- "What is Python?" → Explain from knowledge  
- "How do I use Git?" → Provide instructions from training
- "Explain AI" → Use your knowledge

Examples - USE tools:
- "Search for Python 3.13 news" → Use web_search
- "What's the latest on OpenAI?" → Use web_search  
- "Analyze https://example.com" → Use analyze_url
- "Find papers on quantum computing" → Use arxiv_search
- "Search for research on transformers" → Use arxiv_search"""
            }
            messages.append(system_message)
        
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})
        
        # Prepare request data
        request_data = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        # Add tools if function calling is enabled
        if use_functions:
            request_data["tools"] = get_function_schema()
        
        # First request with or without tools
        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json=request_data,
                timeout=60
            )
            
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", "Unknown error")
                except:
                    error_detail = response.text or "No error details available"
                
                # If function calling fails, try without tools
                if response.status_code == 400 and use_functions:
                    print(f"DEBUG: Function calling failed for model {model}, retrying without tools")
                    request_data_fallback = {
                        "model": model,
                        "messages": messages,
                        "stream": False
                    }
                    fallback_response = requests.post(
                        "http://localhost:11434/api/chat",
                        json=request_data_fallback,
                        timeout=60
                    )
                    if fallback_response.status_code == 200:
                        data = fallback_response.json()
                        return data.get("message", {}).get("content", "No response")
                
                return f"Error {response.status_code}: {error_detail}"
        except requests.exceptions.Timeout:
            return "Error: Request timed out. Ollama may be overloaded."
        except requests.exceptions.ConnectionError:
            return "Error: Could not connect to Ollama. Is it running on localhost:11434?"
        
        data = response.json()
        assistant_message = data.get("message", {})
        
        # Check if there are tool calls (only if functions are enabled)
        tool_calls = assistant_message.get("tool_calls", [])
        
        # Debug: Log when functions are called vs not called
        if use_functions:
            if tool_calls:
                print(f"DEBUG: AI chose to use {len(tool_calls)} function(s)")
            else:
                print("DEBUG: AI chose NOT to use any functions")
        
        if tool_calls and use_functions:
            # Execute function calls
            function_results = []
            
            for tool_call in tool_calls:
                function_info = tool_call.get("function", {})
                function_name = function_info.get("name", "")
                arguments = function_info.get("arguments", {})
                
                # Debug: Show function call info
                debug_info = f"**{function_name}** `{arguments.get('query', arguments.get('url', ''))}`\n\n"
                
                # Execute the function
                result = execute_function(function_name, arguments)
                function_results.append(debug_info + result)
                
                # Add tool call and result to conversation
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.get("content", ""),
                    "tool_calls": tool_calls
                })
                messages.append({
                    "role": "tool",
                    "content": result
                })
            
            # Get final response with tool results
            try:
                final_response = requests.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False
                    },
                    timeout=60
                )
                
                if final_response.status_code == 200:
                    final_data = final_response.json()
                    final_content = final_data.get("message", {}).get("content", "")
                    
                    # Format response with sources
                    if final_content.strip():
                        combined_response = final_content + "\n\n---\n\n**Sources:**\n"
                    else:
                        combined_response = "**Sources:**\n"
                    
                    # Add compact function results  
                    for result in function_results:
                        # Split result into header and content
                        lines = result.split('\n', 2)
                        if len(lines) >= 1:
                            header = lines[0]  # Function name and query
                            combined_response += f"- {header}\n"
                            
                            # Add full content if available
                            if len(lines) > 2:
                                full_content = '\n'.join(lines[2:])
                                combined_response += f"\n{full_content}\n"
                    
                    return combined_response
                else:
                    error_detail = ""
                    try:
                        error_data = final_response.json()
                        error_detail = error_data.get("error", "Unknown error")
                    except:
                        error_detail = final_response.text or "No error details available"
                    return f"Error in final response {final_response.status_code}: {error_detail}"
            except requests.exceptions.RequestException as e:
                return f"Error in final response: {str(e)}"
        else:
            # No tool calls, return regular response
            return assistant_message.get("content", "No response")
            
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"

# ============================================================================
# STREAMLIT APP - MINIMALIST UI
# ============================================================================

# Hide Streamlit default elements for cleaner look
hide_streamlit_style = """
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
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_model" not in st.session_state:
    st.session_state.selected_model = None

if "use_functions" not in st.session_state:
    st.session_state.use_functions = True

# Centered layout with breathing room
col1, col2, col3 = st.columns([1, 3, 1])

with col2:
    # Clean header
    st.markdown("# **MCP Playground**")
    
    # Status section with hierarchy
    models = get_ollama_models()
    if models:
        # Create status tree
        tool_count = len(get_function_schema()) if st.session_state.get('use_functions', True) else 0
        status_text = f"""
        <div style='color: #666; font-size: 14px; margin-bottom: 1rem; font-family: monospace;'>
        ├── {len(models)} models available<br>
        └── {tool_count} tools available
        </div>
        """
        st.markdown(status_text, unsafe_allow_html=True)
    else:
        st.markdown("<div style='color: #ff6b6b; font-size: 14px; margin-bottom: 1rem;'>⭕ Ollama disconnected</div>", unsafe_allow_html=True)
    
    # Model selection - inline and minimal
    if models:
        # Simple inline controls
        col_model, col_func = st.columns([3, 1])
        
        with col_model:
            # Default to llama3.2 if available, otherwise first model
            default_index = 0
            if not st.session_state.selected_model:
                # Look for llama3.2 variants
                for i, model in enumerate(models):
                    if 'llama3.2' in model.lower():
                        default_index = i
                        break
            else:
                # Use current selection if still available
                if st.session_state.selected_model in models:
                    default_index = models.index(st.session_state.selected_model)
            
            # Create shorter display names for models
            model_display = []
            for model in models:
                # Truncate long model names for display
                display_name = model
                if len(model) > 25:
                    display_name = model[:22] + "..."
                model_display.append(display_name)
            
            selected_index = st.selectbox(
                "Model:",
                range(len(models)),
                format_func=lambda x: model_display[x],
                index=default_index,
                label_visibility="collapsed"
            )
            st.session_state.selected_model = models[selected_index]
        
        with col_func:
            st.session_state.use_functions = st.checkbox(
                "Tools", 
                value=st.session_state.use_functions,
                help="Enable web search, URL analysis, and arXiv paper search"
            )
        
    else:
        st.error("**⚠️ No Ollama models found**")
        st.info("Start Ollama: `ollama serve` then `ollama pull llama3.1`")
        st.session_state.selected_model = None
    
    st.divider()
    
    # Main chat area - content first
    if st.session_state.selected_model:
        # Clear button - positioned above chat
        if st.session_state.messages:
            if st.button("Clear conversation", type="secondary", help="Clear all messages"):
                st.session_state.messages = []
                st.rerun()
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                content = message["content"]
                
                # Check if this is a response with function call results
                if "---\n\n**Sources:**" in content:
                    # Split the content into main response and sources
                    parts = content.split("---\n\n**Sources:**")
                    main_content = parts[0].strip()
                    sources_content = parts[1].strip() if len(parts) > 1 else ""
                    
                    # Display main content prominently
                    st.markdown(main_content)
                    
                    # Display sources in smaller, collapsible section
                    if sources_content:
                        with st.expander("View Sources", expanded=False):
                            st.markdown(f"<small>{sources_content}</small>", unsafe_allow_html=True)
                else:
                    # Regular message display
                    st.markdown(content)
    
    # Chat input - fixed at bottom for all states
    if st.session_state.selected_model:
        if prompt := st.chat_input("Ask me anything..."):
            # Add user message to chat
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = chat_with_ollama(
                        st.session_state.selected_model, 
                        prompt, 
                        st.session_state.messages[:-1],  # Exclude the just-added user message
                        st.session_state.use_functions
                    )
                st.markdown(response)
            
            # Add assistant response to chat
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    else:
        # Clean empty state
        st.markdown("### Welcome")
        st.markdown("Select a model above to start chatting")
        
        # Subtle help section
        with st.expander("What can I do?"):
            st.markdown("""
            With **Tools** enabled, I can:
            - **Search** the web for current information
            - **Analyze** content from any URL
            - **Find** academic papers on arXiv
            
            **Example prompts:**
            - *"Search for Python 3.13 features"*
            - *"What's new on the OpenAI blog?"*
            - *"Analyze https://example.com"*
            - *"Find papers on quantum computing"*
            - *"Search for research on transformers"*
            """)
    
    # Add some spacing at bottom
    st.empty()
    st.empty()