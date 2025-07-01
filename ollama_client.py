"""
Ollama Client Wrapper with Function Calling Support
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
from datetime import datetime

import ollama
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]


class OllamaClient:
    """Enhanced Ollama client with function calling and conversation management"""
    
    def __init__(self):
        self.client = ollama.Client()
        self.available_models: List[str] = []
        self.current_model: str = "llama3.1"
        self.conversation_history: List[ChatMessage] = []
        self.available_tools: Dict[str, Callable] = {}
        
    async def initialize(self):
        """Initialize the client and fetch available models"""
        try:
            # Use HTTP client directly for better async support
            import httpx
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    self.available_models = [model['name'] for model in data.get('models', [])]
                    
                    # Set default model if available
                    if self.available_models:
                        if 'llama3.1:latest' in self.available_models:
                            self.current_model = 'llama3.1:latest'
                        elif 'llama3.1' in self.available_models:
                            self.current_model = 'llama3.1'
                        elif 'llama3.2:latest' in self.available_models:
                            self.current_model = 'llama3.2:latest'
                        elif any('llama3' in model for model in self.available_models):
                            self.current_model = next(model for model in self.available_models if 'llama3' in model)
                        else:
                            self.current_model = self.available_models[0]
                    
                    print(f"Initialized Ollama client with models: {self.available_models}")
                    print(f"Default model: {self.current_model}")
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
        except Exception as e:
            print(f"Error: Could not fetch models from Ollama: {e}")
            # Last resort fallback
            self.available_models = ['llama3.1:latest', 'llama3.2:latest', 'qwen3:4b']
            self.current_model = 'llama3.1:latest'
            print(f"Using fallback models: {self.available_models}")
    
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return self.available_models
    
    def set_model(self, model_name: str) -> bool:
        """Set the current model"""
        if model_name in self.available_models:
            self.current_model = model_name
            return True
        return False
    
    def get_current_model(self) -> str:
        """Get current model name"""
        return self.current_model
    
    def register_tool(self, name: str, func: Callable, description: str = None):
        """Register a tool function for use in conversations"""
        self.available_tools[name] = {
            'function': func,
            'description': description or f"Tool: {name}"
        }
    
    def _format_messages_for_ollama(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        """Convert our message format to Ollama's expected format"""
        return [{'role': msg.role, 'content': msg.content} for msg in messages]
    
    def _create_tool_schema(self, tool_name: str, tool_info: Dict) -> Dict[str, Any]:
        """Create tool schema for Ollama function calling"""
        # This is a simplified schema - in practice, you'd want to extract
        # parameter information from the function signature
        return {
            'type': 'function',
            'function': {
                'name': tool_name,
                'description': tool_info['description'],
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            }
        }
    
    async def chat(
        self, 
        message: str, 
        use_tools: bool = True,
        stream: bool = False
    ) -> AsyncGenerator[str, None] | str:
        """
        Send a chat message and get response, with optional tool use
        
        Args:
            message: The user message
            use_tools: Whether to enable tool calling
            stream: Whether to stream the response
            
        Returns:
            Response string or async generator for streaming
        """
        # Add user message to history
        user_message = ChatMessage(
            role='user',
            content=message,
            timestamp=datetime.now().isoformat()
        )
        self.conversation_history.append(user_message)
        
        # Prepare messages for Ollama
        messages = self._format_messages_for_ollama(self.conversation_history)
        
        # Prepare tools if enabled
        tools = None
        if use_tools and self.available_tools:
            tools = [
                self._create_tool_schema(name, info)
                for name, info in self.available_tools.items()
            ]
        
        try:
            if stream:
                return self._stream_chat(messages, tools)
            else:
                return await self._single_chat(messages, tools)
                
        except Exception as e:
            error_message = f"Error communicating with Ollama: {str(e)}"
            return error_message
    
    async def _single_chat(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict]] = None
    ) -> str:
        """Handle single (non-streaming) chat response"""
        
        response = self.client.chat(
            model=self.current_model,
            messages=messages,
            tools=tools if tools else None
        )
        
        # Handle tool calls if present
        if response.get('message', {}).get('tool_calls'):
            tool_results = await self._handle_tool_calls(response['message']['tool_calls'])
            
            # Add tool call results to conversation and get final response
            messages.append({
                'role': 'assistant',
                'content': response['message'].get('content', ''),
                'tool_calls': response['message']['tool_calls']
            })
            
            # Add tool results
            for tool_call, result in zip(response['message']['tool_calls'], tool_results):
                messages.append({
                    'role': 'tool',
                    'content': result,
                    'tool_call_id': tool_call.get('id', 'unknown')
                })
            
            # Get final response with tool results
            final_response = self.client.chat(
                model=self.current_model,
                messages=messages
            )
            
            assistant_content = final_response['message']['content']
        else:
            assistant_content = response['message']['content']
        
        # Add assistant response to history
        assistant_message = ChatMessage(
            role='assistant',
            content=assistant_content,
            timestamp=datetime.now().isoformat()
        )
        self.conversation_history.append(assistant_message)
        
        return assistant_content
    
    async def _stream_chat(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict]] = None
    ) -> AsyncGenerator[str, None]:
        """Handle streaming chat response"""
        
        response_stream = self.client.chat(
            model=self.current_model,
            messages=messages,
            tools=tools if tools else None,
            stream=True
        )
        
        full_response = ""
        tool_calls = []
        
        for chunk in response_stream:
            if chunk.get('message'):
                content = chunk['message'].get('content', '')
                if content:
                    full_response += content
                    yield content
                
                # Collect tool calls
                if chunk['message'].get('tool_calls'):
                    tool_calls.extend(chunk['message']['tool_calls'])
        
        # Handle tool calls after streaming completes
        if tool_calls:
            tool_results = await self._handle_tool_calls(tool_calls)
            
            # Add tool results to messages and get final response
            messages.append({
                'role': 'assistant',
                'content': full_response,
                'tool_calls': tool_calls
            })
            
            for tool_call, result in zip(tool_calls, tool_results):
                messages.append({
                    'role': 'tool',
                    'content': result,
                    'tool_call_id': tool_call.get('id', 'unknown')
                })
            
            # Stream final response
            final_stream = self.client.chat(
                model=self.current_model,
                messages=messages,
                stream=True
            )
            
            yield "\n\n**Tool Results:**\n"
            final_content = ""
            for chunk in final_stream:
                if chunk.get('message', {}).get('content'):
                    content = chunk['message']['content']
                    final_content += content
                    yield content
            
            # Update conversation history with final response
            assistant_message = ChatMessage(
                role='assistant',
                content=full_response + "\n\n" + final_content,
                timestamp=datetime.now().isoformat()
            )
            self.conversation_history.append(assistant_message)
        else:
            # No tool calls, just add the response to history
            assistant_message = ChatMessage(
                role='assistant',
                content=full_response,
                timestamp=datetime.now().isoformat()
            )
            self.conversation_history.append(assistant_message)
    
    async def _handle_tool_calls(self, tool_calls: List[Dict]) -> List[str]:
        """Execute tool calls and return results"""
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call.get('function', {}).get('name')
            arguments = tool_call.get('function', {}).get('arguments', {})
            
            if function_name in self.available_tools:
                try:
                    tool_func = self.available_tools[function_name]['function']
                    
                    # Execute the tool function
                    if asyncio.iscoroutinefunction(tool_func):
                        result = await tool_func(**arguments)
                    else:
                        result = tool_func(**arguments)
                    
                    results.append(str(result))
                    
                except Exception as e:
                    results.append(f"Error executing {function_name}: {str(e)}")
            else:
                results.append(f"Unknown function: {function_name}")
        
        return results
    
    def clear_conversation(self):
        """Clear the conversation history"""
        self.conversation_history = []
    
    def get_conversation_history(self) -> List[ChatMessage]:
        """Get the current conversation history"""
        return self.conversation_history.copy()
    
    def load_conversation(self, messages: List[Dict[str, Any]]):
        """Load a conversation from saved messages"""
        self.conversation_history = [
            ChatMessage(**msg) for msg in messages
        ]
    
    def export_conversation(self) -> List[Dict[str, Any]]:
        """Export conversation for saving"""
        return [msg.model_dump() for msg in self.conversation_history]


# Singleton instance
ollama_client = OllamaClient()


async def get_ollama_client() -> OllamaClient:
    """Get initialized Ollama client"""
    if not ollama_client.available_models:
        await ollama_client.initialize()
    return ollama_client