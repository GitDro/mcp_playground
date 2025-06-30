#!/usr/bin/env python3
"""
MCP Chat Interface

A beautiful Streamlit chat interface for interacting with MCP servers
and Ollama models. Features real-time tool call visualization and
model selection.

Features:
- Model selection from available Ollama models
- Real-time chat with tool call visualization
- MCP server integration for web search
- Beautiful, minimal UI design
- Chat history management

Usage:
    streamlit run chat_interface.py

Author: MCP Arena
"""

import streamlit as st
import ollama
import json
import re
import subprocess
import sys
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Data class for tracking tool calls made by the LLM."""
    name: str
    arguments: Dict[str, Any]
    timestamp: datetime
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ChatMessage:
    """Data class for chat messages with metadata."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime
    model: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class MCPChatInterface:
    """
    Main chat interface class handling MCP server communication
    and Ollama model interactions.
    """
    
    def __init__(self):
        self.mcp_server_process = None
        self.available_models = self._get_available_models()
        
    def _get_available_models(self) -> List[str]:
        """Get list of available Ollama models."""
        try:
            result = subprocess.run(
                ["ollama", "list"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            models = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if line.strip():
                    model_name = line.split()[0]  # First column is model name
                    models.append(model_name)
            
            return models if models else ["llama3.2:latest"]  # Fallback
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get Ollama models: {e}")
            return ["llama3.2:latest"]  # Fallback
    
    def _start_mcp_server(self) -> bool:
        """Start the MCP server process if not already running."""
        if self.mcp_server_process is None or self.mcp_server_process.poll() is not None:
            try:
                self.mcp_server_process = subprocess.Popen(
                    [sys.executable, "web_search_server.py"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Initialize the MCP server
                init_request = {
                    "jsonrpc": "2.0",
                    "id": "init",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "streamlit-chat", "version": "1.0.0"}
                    }
                }
                
                self.mcp_server_process.stdin.write(json.dumps(init_request) + "\n")
                self.mcp_server_process.stdin.flush()
                
                # Read initialization response
                init_response = self.mcp_server_process.stdout.readline()
                init_data = json.loads(init_response.strip())
                
                if "error" in init_data:
                    raise Exception(f"MCP initialization failed: {init_data['error']}")
                
                # Send initialized notification to complete handshake
                initialized_notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized"
                }
                
                self.mcp_server_process.stdin.write(json.dumps(initialized_notification) + "\n")
                self.mcp_server_process.stdin.flush()
                
                logger.info("MCP server initialized successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start MCP server: {e}")
                return False
        
        return True
    
    def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool and return the response."""
        if not self._start_mcp_server():
            return {"error": "MCP server not available"}
        
        try:
            # Ensure arguments is a dictionary
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            request = {
                "jsonrpc": "2.0",
                "id": str(int(time.time())),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            logger.info(f"Calling MCP tool '{tool_name}' with arguments: {arguments}")
            
            self.mcp_server_process.stdin.write(json.dumps(request) + "\n")
            self.mcp_server_process.stdin.flush()
            
            response_line = self.mcp_server_process.stdout.readline()
            
            if not response_line:
                return {"error": "No response from MCP server"}
                
            response = json.loads(response_line.strip())
            
            if "error" in response:
                logger.error(f"MCP tool call error: {response['error']}")
            else:
                logger.info(f"MCP tool call successful for '{tool_name}'")
            
            return response
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MCP response: {e}")
            return {"error": f"Invalid JSON response: {str(e)}"}
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return {"error": str(e)}
    
    def chat_with_model(
        self, 
        model: str, 
        messages: List[Dict[str, str]], 
        enable_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Chat with an Ollama model, optionally with tool calling enabled.
        
        Args:
            model: The Ollama model to use
            messages: List of chat messages
            enable_tools: Whether to enable tool calling
            
        Returns:
            Dict containing response content, tool calls, and metadata
        """
        try:
            # Define available tools for the model
            tools = []
            if enable_tools:
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "description": "Get raw web search results (titles, URLs, snippets) from DuckDuckGo",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Search query"
                                    },
                                    "num_results": {
                                        "type": "integer", 
                                        "description": "Number of results to return",
                                        "default": 3
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "search_and_summarize",
                            "description": "Search the web AND get an AI-generated summary of the results",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Search query"
                                    },
                                    "max_results": {
                                        "type": "integer",
                                        "description": "Maximum results to summarize",
                                        "default": 3
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }
                ]
            
            # Make the chat request
            chat_kwargs = {
                "model": model,
                "messages": messages
            }
            
            if tools:
                chat_kwargs["tools"] = tools
            
            response = ollama.chat(**chat_kwargs)
            
            # Process any tool calls
            tool_calls = []
            message = response.get("message", {})
            final_content = message.get("content", "")
            
            if message.get("tool_calls"):
                # Execute all tool calls
                tool_results_for_model = []
                
                for tool_call in message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    function_args = tool_call["function"]["arguments"]
                    
                    # Execute the tool call via MCP
                    tool_result = self._call_mcp_tool(function_name, function_args)
                    
                    tool_calls.append(ToolCall(
                        name=function_name,
                        arguments=function_args,
                        timestamp=datetime.now(),
                        result=tool_result,
                        error=tool_result.get("error")
                    ))
                    
                    # Prepare tool result for model
                    if tool_result and "result" in tool_result:
                        content = tool_result["result"].get("content", [])
                        if isinstance(content, list) and content:
                            result_text = content[0].get("text", str(content))
                        else:
                            result_text = str(content)
                        
                        tool_results_for_model.append({
                            "role": "tool",
                            "content": result_text,
                            "tool_call_id": tool_call.get("id", function_name)
                        })
                
                # If we have tool results, make another model call to get the final response
                if tool_results_for_model:
                    # Create the tool call message format that Ollama expects
                    assistant_message = {
                        "role": "assistant",
                        "content": final_content if final_content else "",
                        "tool_calls": [
                            {
                                "id": f"call_{i}",
                                "type": "function", 
                                "function": {
                                    "name": tc.name, 
                                    "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments
                                }
                            } for i, tc in enumerate(tool_calls)
                        ]
                    }
                    
                    # Add tool results in the format Ollama expects
                    tool_messages = []
                    for i, result_msg in enumerate(tool_results_for_model):
                        tool_messages.append({
                            "role": "tool",
                            "content": result_msg["content"],
                            "tool_call_id": f"call_{i}"
                        })
                    
                    # Build the conversation with tool results
                    follow_up_messages = messages + [assistant_message] + tool_messages
                    
                    try:
                        # Get final response from model with tool results
                        follow_up_response = ollama.chat(
                            model=model,
                            messages=follow_up_messages
                        )
                        
                        new_content = follow_up_response.get("message", {}).get("content", "")
                        if new_content and new_content.strip():
                            final_content = new_content
                        elif not final_content:
                            # If no content from either call, create a basic response
                            final_content = "I've executed the requested tools and retrieved the information."
                            
                    except Exception as e:
                        logger.error(f"Follow-up model call failed: {e}")
                        if not final_content:
                            final_content = "I've executed the requested tools but couldn't generate a summary response."
            
            return {
                "content": final_content,
                "tool_calls": tool_calls,
                "model": model,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Chat with model failed: {e}")
            return {
                "content": f"Error: {str(e)}",
                "tool_calls": [],
                "model": model,
                "success": False,
                "error": str(e)
            }


@st.cache_resource
def get_chat_interface() -> MCPChatInterface:
    """Get cached chat interface instance."""
    return MCPChatInterface()


def parse_thinking_content(content: str) -> tuple[str, str]:
    """
    Parse content to separate thinking/reasoning from main response.
    
    Args:
        content: The raw model response
        
    Returns:
        Tuple of (thinking_content, main_content)
    """
    if not content:
        return "", ""
    
    # Look for <think>...</think> or <thinking>...</thinking> tags
    thinking_patterns = [
        r'<think>(.*?)</think>',
        r'<thinking>(.*?)</thinking>',
        r'<reasoning>(.*?)</reasoning>'
    ]
    
    thinking_content = ""
    main_content = content
    
    # Process each pattern to extract thinking content and remove from main
    for pattern in thinking_patterns:
        matches = re.findall(pattern, main_content, re.DOTALL | re.IGNORECASE)
        if matches:
            # Combine all thinking blocks
            thinking_content += "\n\n".join(matches).strip()
            # Remove ALL occurrences of this pattern from main content
            main_content = re.sub(pattern, "", main_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up whitespace in main content
    main_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', main_content)  # Replace multiple newlines
    main_content = re.sub(r'^\s*\n+', '', main_content)  # Remove leading newlines
    main_content = re.sub(r'\n+\s*$', '', main_content)  # Remove trailing newlines
    main_content = main_content.strip()
    
    return thinking_content.strip(), main_content


def render_thinking_content(thinking_content: str) -> None:
    """Render thinking content with special styling."""
    if thinking_content:
        st.markdown(
            f'<div class="thinking-content"><strong>Model Reasoning:</strong><br/>{thinking_content}</div>',
            unsafe_allow_html=True
        )


def render_tool_call(tool_call: ToolCall) -> None:
    """Render a tool call in the UI with minimal technical details."""
    with st.expander(f"🔧 {tool_call.name}", expanded=False):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**Parameters:**")
            st.json(tool_call.arguments)
        
        with col2:
            st.markdown("**Executed:**")
            st.text(tool_call.timestamp.strftime("%H:%M:%S"))
            
            if tool_call.error:
                st.markdown("**Error:**")
                st.error(tool_call.error)
            else:
                st.markdown("**Status:**")
                st.success("✅ Completed successfully")
                
                # Show technical details only if needed for debugging
                if tool_call.result and isinstance(tool_call.result, dict):
                    if "result" in tool_call.result:
                        result_data = tool_call.result["result"]
                        if isinstance(result_data, dict) and "content" in result_data:
                            content = result_data["content"]
                            if isinstance(content, list) and len(content) > 0:
                                st.markdown(f"**Results:** {len(content)} items retrieved")
                            else:
                                st.markdown("**Results:** Data retrieved")
                        else:
                            st.markdown("**Results:** Tool executed")
                    else:
                        st.markdown("**Results:** Tool executed")


def setup_page_config() -> None:
    """Configure Streamlit page settings and custom CSS."""
    st.set_page_config(
        page_title="MCP Chat Interface",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Minimal CSS with adaptive gray color scheme
    st.markdown("""
    <style>
    /* CSS Variables for adaptive gray theming */
    :root {
        --text-primary: #2c2c2c;
        --text-secondary: #707070;
        --text-muted: #9a9a9a;
        --bg-primary: #fafafa;
        --bg-secondary: #f5f5f5;
        --bg-tertiary: #eeeeee;
        --border-color: #dddddd;
        --border-subtle: #e8e8e8;
        --thinking-bg: #f8f8f8;
        --thinking-border: #d4d4d4;
        --button-bg: #8a8a8a;
        --button-hover: #757575;
        --button-text: #ffffff;
        --accent-subtle: #b8b8b8;
    }
    
    @media (prefers-color-scheme: dark) {
        :root {
            --text-primary: #e8e8e8;
            --text-secondary: #b0b0b0;
            --text-muted: #888888;
            --bg-primary: #1c1c1c;
            --bg-secondary: #262626;
            --bg-tertiary: #303030;
            --border-color: #404040;
            --border-subtle: #353535;
            --thinking-bg: #242424;
            --thinking-border: #404040;
            --button-bg: #606060;
            --button-hover: #707070;
            --button-text: #ffffff;
            --accent-subtle: #505050;
        }
    }
    
    /* Global styles - minimal and clean */
    .main {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: var(--text-primary);
        background-color: var(--bg-primary);
    }
    
    /* Streamlit form elements - subtle grays */
    .stSelectbox > div > div {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-subtle) !important;
        color: var(--text-primary) !important;
        border-radius: 0.25rem !important;
    }
    
    .stSelectbox > div > div > div {
        color: var(--text-primary) !important;
        background-color: var(--bg-secondary) !important;
    }
    
    .stSelectbox > div > div[data-baseweb="select"] > div {
        background-color: var(--bg-secondary) !important;
        border-color: var(--border-subtle) !important;
    }
    
    /* Checkboxes - muted colors */
    .stCheckbox > label {
        color: var(--text-secondary) !important;
        font-size: 0.9rem;
    }
    
    .stCheckbox > label > div {
        background-color: var(--bg-tertiary) !important;
        border-color: var(--border-color) !important;
    }
    
    /* Thinking content - subtle and readable */
    .thinking-content {
        background-color: var(--thinking-bg);
        border-left: 2px solid var(--thinking-border);
        padding: 0.875rem;
        margin: 0.75rem 0;
        border-radius: 0.375rem;
        font-style: italic;
        color: var(--text-muted);
        font-size: 0.85rem;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
        line-height: 1.4;
    }
    
    /* Buttons - clean gray styling */
    .stButton > button {
        background-color: var(--button-bg) !important;
        color: var(--button-text) !important;
        border: none !important;
        border-radius: 0.375rem !important;
        font-weight: 400 !important;
        transition: all 0.2s ease !important;
        padding: 0.5rem 1rem !important;
        font-size: 0.9rem !important;
    }
    
    .stButton > button:hover {
        background-color: var(--button-hover) !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Tool expanders - minimal gray theme */
    .streamlit-expanderHeader {
        background-color: var(--bg-tertiary) !important;
        border: 1px solid var(--border-subtle) !important;
        color: var(--text-secondary) !important;
        border-radius: 0.375rem !important;
    }
    
    /* Main content container - clean spacing */
    .block-container {
        padding-top: 1.5rem;
        max-width: 48rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Sidebar - subtle background */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-secondary);
        border-right: 1px solid var(--border-subtle);
    }
    
    section[data-testid="stSidebar"] > div {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Code blocks - consistent theming */
    code {
        background-color: var(--bg-tertiary);
        color: var(--text-primary);
        padding: 0.125rem 0.375rem;
        border-radius: 0.25rem;
        font-size: 0.875rem;
        border: 1px solid var(--border-subtle);
    }
    
    /* Chat messages - clean appearance */
    .stChatMessage {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-subtle);
        border-radius: 0.5rem;
    }
    
    /* Input field styling */
    .stTextInput > div > div > input {
        background-color: var(--bg-secondary) !important;
        border-color: var(--border-subtle) !important;
        color: var(--text-primary) !important;
    }
    
    /* Footer - minimal and muted */
    .footer {
        margin-top: 3rem;
        padding: 1.5rem 0;
        border-top: 1px solid var(--border-subtle);
        text-align: center;
        color: var(--text-muted);
        font-size: 0.8rem;
        line-height: 1.4;
    }
    
    /* Fix jarring bright elements in dark mode */
    
    /* Dropdown menu options */
    .stSelectbox div[data-baseweb="popover"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    .stSelectbox div[role="option"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }
    
    .stSelectbox div[role="option"]:hover {
        background-color: var(--bg-tertiary) !important;
    }
    
    /* Spinner - muted colors */
    .stSpinner > div {
        border-color: var(--accent-subtle) transparent var(--accent-subtle) transparent !important;
    }
    
    /* Success/Error messages - subtle */
    .stSuccess {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    .stError {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    /* JSON display - consistent theming */
    .stJson {
        background-color: var(--bg-tertiary) !important;
        border: 1px solid var(--border-subtle) !important;
    }
    
    /* Chat input field */
    .stChatInput > div > div > div > div {
        background-color: var(--bg-secondary) !important;
        border-color: var(--border-subtle) !important;
        color: var(--text-primary) !important;
    }
    
    /* Remove bright focus outlines */
    input:focus, select:focus, textarea:focus, button:focus {
        outline: 1px solid var(--accent-subtle) !important;
        outline-offset: -1px;
        box-shadow: none !important;
    }
    
    /* Expander content */
    .streamlit-expanderContent {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-subtle) !important;
        border-top: none !important;
    }
    
    /* Hide streamlit branding elements that might be bright */
    .viewerBadge_container__1QSob {
        display: none !important;
    }
    
    /* Markdown elements - consistent styling */
    .element-container h1, .element-container h2, .element-container h3 {
        color: var(--text-primary) !important;
    }
    
    .element-container p {
        color: var(--text-primary) !important;
    }
    
    /* Tab styling if present */
    .stTabs [data-baseweb="tab-list"] {
        background-color: var(--bg-tertiary) !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-secondary) !important;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar(chat_interface: MCPChatInterface) -> tuple:
    """Render minimal sidebar with essential controls."""
    with st.sidebar:
        # Model selection
        selected_model = st.selectbox(
            "Model",
            options=chat_interface.available_models,
            index=0,
            key="model_selector"
        )
        
        st.markdown("---")
        
        # Essential toggles
        enable_tools = st.checkbox("Web Search", value=True)
        show_reasoning = st.checkbox("Show Reasoning", value=False)
        
        st.markdown("---")
        
        # Clear button
        if st.button("Clear", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        
        # Minimal footer in sidebar
        st.markdown("---")
        st.markdown(
            '<div style="text-align: center; color: var(--text-muted); font-size: 0.75rem; margin-top: 1rem;">MCP Arena</div>',
            unsafe_allow_html=True
        )
    
    return selected_model, enable_tools, show_reasoning


def main():
    """Main Streamlit application."""
    # Page setup
    setup_page_config()
    
    # Initialize chat interface
    chat_interface = get_chat_interface()
    
    # Render sidebar
    selected_model, enable_tools, show_reasoning = render_sidebar(chat_interface)
    
    # Main content - minimal header
    st.markdown("### MCP Chat")
    st.markdown("_AI conversation with web search_")
    
    # Initialize chat history and thinking state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "is_thinking" not in st.session_state:
        st.session_state.is_thinking = False
    if "thinking_model" not in st.session_state:
        st.session_state.thinking_model = ""
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Parse thinking content for assistant messages
            if message["role"] == "assistant":
                thinking_content, main_content = parse_thinking_content(message["content"])
                
                # Show thinking if enabled and present
                if show_reasoning and thinking_content:
                    render_thinking_content(thinking_content)
                
                # Show main content
                if main_content:
                    st.markdown(main_content)
            else:
                # User messages - display as normal
                st.markdown(message["content"])
            
            # Display tool calls if any
            if "tool_calls" in message and message["tool_calls"]:
                st.markdown("---")
                for tool_call in message["tool_calls"]:
                    render_tool_call(tool_call)
    
    # Show thinking indicator if model is active (persists across reruns)
    if st.session_state.is_thinking:
        with st.chat_message("assistant"):
            st.info(f"🤔 Thinking with {st.session_state.thinking_model}...")
    
    # Chat input
    if prompt := st.chat_input("Ask a question or request information..."):
        # Add user message to chat history
        user_message = {
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now()
        }
        st.session_state.messages.append(user_message)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Set thinking state and trigger rerun to show indicator
        st.session_state.is_thinking = True
        st.session_state.thinking_model = selected_model
        st.rerun()
    
    # Process pending response if we're in thinking state
    if st.session_state.is_thinking and len(st.session_state.messages) > 0:
        # Get the latest user message to process
        latest_message = st.session_state.messages[-1]
        if latest_message["role"] == "user":
            # Generate assistant response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                # Prepare message history for the model
                model_messages = []
                
                # Add system message with current date/time context
                current_datetime = datetime.now(timezone.utc)
                date_context = f"""Current date and time: {current_datetime.strftime('%A, %B %d, %Y at %H:%M UTC')}
Today is {current_datetime.strftime('%A')}. The current year is {current_datetime.year}.

You have access to web search tools for current information. When users ask about recent events, news, or anything time-sensitive, use the search tools to get up-to-date information."""
                
                model_messages.append({
                    "role": "system",
                    "content": date_context
                })
                
                # Add conversation history
                for msg in st.session_state.messages:
                    model_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                # Get response from model
                response = chat_interface.chat_with_model(
                    model=selected_model,
                    messages=model_messages,
                    enable_tools=enable_tools
                )
                
                # Clear thinking state
                st.session_state.is_thinking = False
                st.session_state.thinking_model = ""
                
                # Display the response
                if response["success"]:
                    # Parse thinking content from response
                    thinking_content, main_content = parse_thinking_content(response["content"])
                    
                    # Show thinking if enabled and present
                    if show_reasoning and thinking_content:
                        render_thinking_content(thinking_content)
                    
                    # Show main content
                    if main_content and main_content.strip():
                        message_placeholder.markdown(main_content)
                    elif response["content"] and response["content"].strip():
                        message_placeholder.markdown(response["content"])
                    else:
                        # Fallback for empty responses with tool calls
                        if response["tool_calls"]:
                            message_placeholder.markdown("*Used tools to retrieve information - see details below.*")
                        else:
                            message_placeholder.markdown("*No response generated.*")
                    
                    # Display tool calls if any
                    if response["tool_calls"]:
                        st.markdown("---")
                        for tool_call in response["tool_calls"]:
                            render_tool_call(tool_call)
                    
                    # Add assistant message to history
                    assistant_message = {
                        "role": "assistant",
                        "content": response["content"],
                        "timestamp": datetime.now(),
                        "model": selected_model,
                        "tool_calls": response["tool_calls"]
                    }
                    st.session_state.messages.append(assistant_message)
                    
                else:
                    message_placeholder.error(f"Error: {response.get('error', 'Unknown error')}")
    


if __name__ == "__main__":
    main()