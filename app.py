"""
MCP Playground - Simple Streamlit Chat App with Function Calling

A minimal, working chat application that integrates with Ollama for local AI
and includes web search, URL analysis, and arXiv paper search capabilities.

Author: MCP Arena Team
Version: 1.0.0
"""

import streamlit as st
import requests
from typing import List, Dict
from datetime import datetime

# Import our modules
from tools import get_function_schema, execute_function
from ui_config import STREAMLIT_STYLE, TOOLS_HELP_TEXT, get_system_prompt

# Page config - Minimalist setup
st.set_page_config(
    page_title="MCP Playground",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)


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
            current_date = datetime.now().strftime("%Y-%m-%d")
            system_message = {
                "role": "system",
                "content": get_system_prompt(current_date)
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


# Apply CSS styles
st.markdown(STREAMLIT_STYLE, unsafe_allow_html=True)

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
            st.markdown(TOOLS_HELP_TEXT)
    
    # Add some spacing at bottom
    st.empty()
    st.empty()