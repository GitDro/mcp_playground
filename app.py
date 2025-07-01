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

# Page config
st.set_page_config(
    page_title="MCP Arena",
    page_icon="🤖",
    layout="wide"
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
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"No search results found for: {query}"
        
        # Format results as markdown
        formatted_results = f"# 🔍 Search Results for: {query}\n\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"## {i}. {result.get('title', 'No Title')}\n"
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
            
            summary = f"# 📄 URL Analysis\n\n"
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
                "description": "Search the web using DuckDuckGo for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
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
                "description": "Analyze and summarize content from a URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to analyze"
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    ]

def execute_function(function_name: str, arguments: dict) -> str:
    """Execute a function call"""
    if function_name == "web_search":
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        return web_search(query, max_results)
    elif function_name == "analyze_url":
        url = arguments.get("url", "")
        return analyze_url(url)
    else:
        return f"Unknown function: {function_name}"

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
        # Format conversation for Ollama
        messages = []
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
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=request_data,
            timeout=60
        )
        
        if response.status_code != 200:
            return f"Error: {response.status_code}"
        
        data = response.json()
        assistant_message = data.get("message", {})
        
        # Check if there are tool calls (only if functions are enabled)
        tool_calls = assistant_message.get("tool_calls", [])
        
        if tool_calls and use_functions:
            # Execute function calls
            function_results = []
            
            for tool_call in tool_calls:
                function_info = tool_call.get("function", {})
                function_name = function_info.get("name", "")
                arguments = function_info.get("arguments", {})
                
                # Execute the function
                result = execute_function(function_name, arguments)
                function_results.append(result)
                
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
                
                # Combine function results with final response
                combined_response = ""
                for result in function_results:
                    combined_response += result + "\n\n"
                combined_response += final_content
                
                return combined_response
            else:
                return f"Error in final response: {final_response.status_code}"
        else:
            # No tool calls, return regular response
            return assistant_message.get("content", "No response")
            
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"

# ============================================================================
# STREAMLIT APP
# ============================================================================

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_model" not in st.session_state:
    st.session_state.selected_model = None

if "use_functions" not in st.session_state:
    st.session_state.use_functions = True

# Header
st.title("🤖 MCP Arena")
st.markdown("**Chat with AI that can search the web and analyze URLs**")

# Add function calling info
with st.expander("🛠️ Available Functions"):
    st.markdown("""
    Your AI assistant can automatically use these tools when needed:
    
    - **🔍 Web Search**: Search the web using DuckDuckGo for current information
    - **📄 URL Analysis**: Analyze and summarize content from any URL
    
    Just ask naturally! For example:
    - "Search for the latest news about AI"
    - "What's the content of https://example.com"
    """)

# Sidebar for model selection
with st.sidebar:
    st.header("Model Selection")
    
    models = get_ollama_models()
    
    if models:
        selected_model = st.selectbox(
            "Choose a model:",
            models,
            index=0 if not st.session_state.selected_model else models.index(st.session_state.selected_model) if st.session_state.selected_model in models else 0
        )
        st.session_state.selected_model = selected_model
        st.success(f"Using: {selected_model}")
    else:
        st.error("⚠️ No Ollama models found!")
        st.info("Make sure Ollama is running:\n```\nollama serve\nollama pull llama3.1\n```")
        st.session_state.selected_model = None
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.header("Function Calling")
    st.session_state.use_functions = st.checkbox(
        "Enable function calling", 
        value=st.session_state.use_functions,
        help="Allow AI to use web search and URL analysis tools"
    )

# Main chat area
if st.session_state.selected_model:
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
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
    st.info("👈 Please select a model from the sidebar to start chatting")

# Footer
with st.sidebar:
    st.markdown("---")
    st.markdown("**Status:**")
    if models:
        st.markdown("🟢 Ollama Connected")
        st.markdown(f"📊 {len(models)} models available")
    else:
        st.markdown("🔴 Ollama Disconnected")