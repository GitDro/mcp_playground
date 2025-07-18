"""
MCP Playground - FastMCP Version
Simple Streamlit Chat App with FastMCP Integration

A modernized chat application that integrates with Ollama for local AI
and uses FastMCP for tool execution.

Author: MCP Arena Team
Version: 2.0.0 (FastMCP)
"""

import streamlit as st
import requests
import asyncio
from typing import List, Dict
from datetime import datetime

# Import our modules
from ui_config import STREAMLIT_STYLE, TOOLS_HELP_TEXT, get_system_prompt
from src.core.vector_memory import vector_memory_manager as memory_manager
import uuid

# Import FastMCP client
from fastmcp import Client

# Page config - Minimalist setup
st.set_page_config(
    page_title="MCP Playground",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

async def get_mcp_tools():
    """Get available tools from the FastMCP server using in-memory transport"""
    try:
        # Import the FastMCP server instance
        from src import mcp
        from fastmcp import Client
        
        # Create a client with in-memory transport (FastMCPTransport auto-inferred)
        async with Client(mcp) as client:
            tools_data = await client.list_tools()
            
            # Convert to the format expected by the app
            tools = []
            for tool in tools_data:
                tools.append({
                    "name": tool.name, 
                    "description": tool.description or f"Tool: {tool.name}",
                    "inputSchema": tool.inputSchema
                })
            
            return tools
    except Exception as e:
        st.error(f"Failed to get MCP tools: {e}")
        return []

async def call_mcp_tool(tool_name: str, arguments: dict):
    """Call a tool using the FastMCP client with in-memory transport"""
    try:
        # Import the FastMCP server instance
        from src import mcp
        from fastmcp import Client
        
        # Create a client with in-memory transport
        async with Client(mcp) as client:
            result = await client.call_tool(tool_name, arguments)
            
            # Extract the content from the result (updated for MCP 2.10.0+)
            if hasattr(result, 'content') and result.content:
                # Handle different content types
                content_item = result.content[0]
                if hasattr(content_item, 'text'):
                    return content_item.text
                else:
                    return str(content_item)
            elif hasattr(result, 'data'):
                # Structured output from the tool
                return str(result.data)
            else:
                return str(result)
    except Exception as e:
        return f"Error calling tool {tool_name}: {str(e)}"

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

async def chat_with_ollama_and_mcp(model: str, message: str, conversation_history: List[Dict], use_functions: bool = True) -> tuple[str, List[str]]:
    """
    Send chat message to Ollama with FastMCP function calling support.
    
    Args:
        model: Ollama model name to use
        message: User's message
        conversation_history: Previous messages in the conversation
        use_functions: Whether to enable function calling
        
    Returns:
        Tuple of (AI response string, list of tool names used)
    """
    try:
        # Get MCP tools if functions are enabled
        mcp_tools = []
        if use_functions:
            mcp_tools = await get_mcp_tools()
            if not mcp_tools:
                use_functions = False  # Disable if no tools available
        
        # Format conversation for Ollama with system guidance
        messages = []
        
        # Add simple system message 
        if use_functions:
            current_date = datetime.now().strftime("%Y-%m-%d")
            base_prompt = get_system_prompt(current_date)
            
            system_message = {
                "role": "system", 
                "content": base_prompt
            }
            messages.append(system_message)
        
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Simple Semantic RAG: Inject facts and documents based on pure similarity
        if use_functions:
            try:
                # Detect memory queries to inject ALL stored information
                memory_keywords = [
                    'what do you remember', 'what do you know about me', 'what do you recall',
                    'tell me about myself', 'about me', 'remember about me'
                ]
                
                # Skip memory injection for tool-focused queries (keep minimal list)
                tool_keywords = [
                    'stock', 'price', 'crypto', 'weather', 'youtube', 'arxiv', 
                    'crime', 'tide', 'search', 'url', 'analyze'
                ]
                
                query_lower = message.lower()
                is_tool_query = any(keyword in query_lower for keyword in tool_keywords)
                is_memory_query = any(keyword in query_lower for keyword in memory_keywords)
                
                if is_memory_query:
                    # For "what do you remember about me" queries, inject ALL stored information
                    all_facts = memory_manager.get_all_facts()
                    all_documents = memory_manager.get_all_documents()
                    
                    if all_facts or all_documents:
                        content_parts = []
                        if all_facts:
                            facts_content = "; ".join([fact.content for fact in all_facts])
                            content_parts.append(f"Facts: {facts_content}")
                        if all_documents:
                            docs_content = "; ".join([f"{doc['title']}: {doc['content'][:100]}..." for doc in all_documents[:3]])
                            content_parts.append(f"Notes: {docs_content}")
                        
                        messages.append({
                            "role": "user",
                            "content": f"Here's what I remember about you: {' | '.join(content_parts)}"
                        })
                        messages.append({
                            "role": "assistant",
                            "content": "Got it, I have that information."
                        })
                        print(f"DEBUG - Injected all stored information for memory query ({len(all_facts)} facts, {len(all_documents)} documents)")
                        
                elif not is_tool_query:
                    # Pure Semantic RAG: Simple threshold-based injection
                    injected_items = []
                    
                    # 1. Inject high-relevance facts (80%+ similarity) - unchanged
                    relevant_facts = memory_manager.retrieve_facts_semantic(message, limit=5)
                    high_relevance_facts = [fact for fact in relevant_facts if fact.relevance_score > 0.8]
                    
                    for fact in high_relevance_facts[:2]:
                        messages.append({
                            "role": "user",
                            "content": f"Just so you know, {fact.content.lower()}"
                        })
                        messages.append({
                            "role": "assistant", 
                            "content": "Got it, I'll keep that in mind!"
                        })
                        injected_items.append(f"fact: {fact.content} ({fact.relevance_score:.0%})")
                    
                    # 2. Pure semantic document injection - no keyword logic
                    relevant_documents = memory_manager.search_documents(message, limit=3, min_similarity=0.3)
                    
                    for doc in relevant_documents:
                        relevance = doc['relevance_score']
                        
                        # Simple threshold-based injection
                        if relevance > 0.85:
                            # High confidence - inject full context
                            doc_content = doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content']
                            
                            messages.append({
                                "role": "user",
                                "content": f"For context, from my notes '{doc['title']}': {doc_content}"
                            })
                            messages.append({
                                "role": "assistant",
                                "content": "I see that from your notes."
                            })
                            injected_items.append(f"document: {doc['title']} ({relevance:.0%}, high-conf)")
                            
                        elif relevance > 0.70:
                            # Medium confidence - inject shorter snippet
                            doc_snippet = doc['content'][:100] + "..." if len(doc['content']) > 100 else doc['content']
                            
                            messages.append({
                                "role": "user",
                                "content": f"From my notes '{doc['title']}': {doc_snippet}"
                            })
                            messages.append({
                                "role": "assistant",
                                "content": "Got it."
                            })
                            injected_items.append(f"document: {doc['title']} ({relevance:.0%}, med-conf)")
                        
                        # Below 70% - no injection to avoid noise
                        
                        # Limit total injections to prevent context overload
                        if len(injected_items) >= 3:
                            break
                    
                    # Debug output
                    if injected_items:
                        print(f"DEBUG - Semantic injection: {'; '.join(injected_items)}")
                
            except Exception as e:
                print(f"Enhanced memory injection failed: {e}")
        
        messages.append({"role": "user", "content": message})
        
        # Prepare request data
        request_data = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        # Add tools if function calling is enabled
        if use_functions and mcp_tools:
            request_data["tools"] = create_function_schema_from_mcp_tools(mcp_tools)
        
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
                        return data.get("message", {}).get("content", "No response"), []
                
                return f"Error {response.status_code}: {error_detail}", []
        except requests.exceptions.Timeout:
            return "Error: Request timed out. Ollama may be overloaded.", []
        except requests.exceptions.ConnectionError:
            return "Error: Could not connect to Ollama. Is it running on localhost:11434?", []
        
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
            # Execute function calls using FastMCP
            function_results = []
            function_names = []
            
            for tool_call in tool_calls:
                function_info = tool_call.get("function", {})
                function_name = function_info.get("name", "")
                arguments = function_info.get("arguments", {})
                
                # Execute the function using FastMCP
                result = await call_mcp_tool(function_name, arguments)
                function_results.append(result)
                function_names.append(function_name)
                
                # Track tool usage for memory - this will be handled by the sync wrapper
                
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
                    
                    # Format response with function results
                    # Only show function results for certain types of functions
                    # YouTube functions are meant to be processed by LLM, not shown to user
                    show_function_results = []
                    for i, (func_name, result) in enumerate(zip(function_names, function_results)):
                        if not func_name.startswith('analyze_youtube_url'):
                            show_function_results.append(result)
                    
                    if show_function_results:
                        if final_content.strip():
                            combined_response = final_content + "\n\n---\n\n"
                        else:
                            combined_response = ""
                        
                        # Add non-YouTube function results
                        for result in show_function_results:
                            combined_response += f"{result}\n\n"
                        
                        return combined_response, function_names
                    else:
                        # No function results to show (likely YouTube functions), just return LLM response
                        return final_content, function_names
                else:
                    error_detail = ""
                    try:
                        error_data = final_response.json()
                        error_detail = error_data.get("error", "Unknown error")
                    except:
                        error_detail = final_response.text or "No error details available"
                    return f"Error in final response {final_response.status_code}: {error_detail}", []
            except requests.exceptions.RequestException as e:
                return f"Error in final response: {str(e)}", []
        else:
            # No tool calls, return regular response
            return assistant_message.get("content", "No response"), []
            
    except Exception as e:
        return f"Error connecting to Ollama or MCP: {str(e)}", []

def chat_with_ollama_sync(*args, **kwargs):
    """Synchronous wrapper for the async chat function"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        response, tool_names = loop.run_until_complete(chat_with_ollama_and_mcp(*args, **kwargs))
        
        # Track tool usage in session state
        for tool_name in tool_names:
            update_tool_usage(tool_name)
        
        return response
    finally:
        loop.close()

def get_mcp_tools_sync():
    """Synchronous wrapper for getting MCP tools"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_mcp_tools())
    finally:
        loop.close()

def save_conversation_summary():
    """Save conversation summary to memory when session ends"""
    if st.session_state.messages and len(st.session_state.messages) > 2:
        try:
            memory_manager.save_conversation_summary(
                st.session_state.session_id,
                st.session_state.messages,
                st.session_state.tool_usage
            )
        except Exception as e:
            st.error(f"Failed to save conversation summary: {e}")

def update_tool_usage(tool_name: str):
    """Update tool usage tracking"""
    if tool_name in st.session_state.tool_usage:
        st.session_state.tool_usage[tool_name] += 1
    else:
        st.session_state.tool_usage[tool_name] = 1

def get_memory_context(user_message: str) -> str:
    """Get relevant memory context for the current conversation"""
    try:
        context = memory_manager.build_conversation_context(
            user_message,
            st.session_state.messages
        )
        return context
    except Exception as e:
        st.error(f"Failed to get memory context: {e}")
        return ""

# Apply CSS styles
st.markdown(STREAMLIT_STYLE, unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_model" not in st.session_state:
    st.session_state.selected_model = None

if "use_functions" not in st.session_state:
    st.session_state.use_functions = True

# Initialize memory-related session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "tool_usage" not in st.session_state:
    st.session_state.tool_usage = {}

if "memory_context" not in st.session_state:
    st.session_state.memory_context = ""

# Centered layout with breathing room
col1, col2, col3 = st.columns([1, 3, 1])

with col2:
    # Clean header
    st.markdown("# **MCP Playground**")
    
    # Status section with expandable hierarchy
    models = get_ollama_models()
    if models:
        mcp_tools = get_mcp_tools_sync() if st.session_state.get('use_functions', True) else []
        tool_count = len(mcp_tools)
        
        # Create expandable status hierarchy
        with st.expander(f"{len(models)} models available, {tool_count} tools available", expanded=False):
            # Models section
            st.markdown("**Models:**")
            for i, model in enumerate(models):
                # Clean up model names for display
                display_name = model.replace(':latest', '').replace('_', ' ')
                if len(display_name) > 40:
                    display_name = display_name[:37] + "..."
                
                # Add tree-like formatting
                if i == len(models) - 1:
                    st.markdown(f"<div style='font-family: monospace; font-size: 12px; color: #666;'>└── {display_name}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='font-family: monospace; font-size: 12px; color: #666;'>├── {display_name}</div>", unsafe_allow_html=True)
            
            st.markdown("")  # Add spacing
            
            # Tools section
            if st.session_state.get('use_functions', True):
                st.markdown("**Tools:**")
                for i, tool in enumerate(mcp_tools):
                    tool_name = tool['name']
                    
                    # Extract concise inline descriptions
                    if 'web_search' in tool_name:
                        purpose = "web search"
                    elif 'analyze_url' in tool_name:
                        purpose = "webpage summary"
                    elif 'analyze_url' in tool_name:  # Legacy fallback
                        purpose = "URL analysis"
                    elif 'arxiv_search' in tool_name:
                        purpose = "academic papers"
                    elif 'stock_price' in tool_name:
                        purpose = "stock prices"
                    elif 'stock_history' in tool_name:
                        purpose = "stock history"
                    elif 'crypto_price' in tool_name:
                        purpose = "crypto prices"
                    elif 'market_summary' in tool_name:
                        purpose = "market overview"
                    elif 'get_stock_overview' in tool_name:
                        purpose = "stock market data"
                    elif 'summarize_youtube' in tool_name:
                        purpose = "YouTube summaries"
                    elif 'query_youtube' in tool_name:
                        purpose = "YouTube Q&A"
                    elif 'analyze_youtube_url' in tool_name:
                        purpose = "video analysis"
                    elif 'get_weather' in tool_name:
                        purpose = "weather forecast"
                    elif 'remember' in tool_name:
                        purpose = "store user info"
                    elif 'recall' in tool_name:
                        purpose = "retrieve memories"
                    elif 'forget' in tool_name:
                        purpose = "remove memories"
                    elif 'store_note' in tool_name:
                        purpose = "save notes"
                    elif 'search_documents' in tool_name:
                        purpose = "search documents by keyword"
                    elif 'show_all_documents' in tool_name:
                        purpose = "show ALL saved documents"
                    elif 'get_tide_info' in tool_name:
                        purpose = "tide information"
                    elif 'get_toronto_crime' in tool_name:
                        purpose = "crime statistics"
                    elif 'analyze_canadian_economy' in tool_name:
                        purpose = "economic analysis"
                    elif 'save_link' in tool_name:
                        purpose = "save webpage content"
                    else:
                        purpose = "specialized tool"
                    
                    # Add tree-like formatting with inline descriptions
                    if i == len(mcp_tools) - 1:
                        st.markdown(f"<div style='font-family: monospace; font-size: 12px; color: #666;'>└── {tool_name} <span style='color: #888;'>({purpose})</span></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='font-family: monospace; font-size: 12px; color: #666;'>├── {tool_name} <span style='color: #888;'>({purpose})</span></div>", unsafe_allow_html=True)
            else:
                st.markdown("**Tools:** *Disabled*")
    else:
        st.markdown("<div style='color: #ff6b6b; font-size: 14px; margin-bottom: 1rem;'>Ollama disconnected</div>", unsafe_allow_html=True)
    
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
                    if 'llama3.2:latest' in model.lower():
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
                help="Enable tools for web search, URL analysis, arXiv papers, finance, YouTube, and weather"
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
                # Save conversation summary before clearing
                save_conversation_summary()
                
                # Clear session state
                st.session_state.messages = []
                st.session_state.tool_usage = {}
                st.session_state.session_id = str(uuid.uuid4())
                st.rerun()
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                content = message["content"]
                
                # Debug: Log message content to see where "Stored information about you" comes from
                if "stored information" in content.lower():
                    print(f"DEBUG - Found stored information in message: {content}")
                
                # Check if this is a response with function call results
                if "---\n\n" in content:
                    # Split the content into main response and function results
                    parts = content.split("---\n\n")
                    main_content = parts[0].strip()
                    function_results = parts[1].strip() if len(parts) > 1 else ""
                    
                    # Display main content prominently
                    if main_content:
                        st.markdown(main_content)
                    
                    # Display function results directly
                    if function_results:
                        st.markdown(function_results)
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
                    response = chat_with_ollama_sync(
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
        st.markdown("### Welcome to MCP Playground")
        st.markdown("Select a model above to start chatting with AI tools")
        
        # Subtle help section
        with st.expander("What can I do?"):
            st.markdown(TOOLS_HELP_TEXT)
    
    # Add some spacing at bottom
    st.empty()
    st.empty()