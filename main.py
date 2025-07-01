"""
MCP Arena - FastAPI Backend with WebSocket Support
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from mcp_server import (
    web_search, summarize_paper, save_conversation,
    research_prompt, chat_starter, mcp
)
from ollama_client import get_ollama_client, OllamaClient


# Initialize FastAPI app
app = FastAPI(title="MCP Arena", description="Elegant MCP-based chat application")

# Serve static files
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_sessions: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_sessions[session_id] = {
            'websocket': websocket,
            'conversation_id': None,
            'ollama_client': None
        }
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if session_id in self.user_sessions:
            del self.user_sessions[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.user_sessions:
            websocket = self.user_sessions[session_id]['websocket']
            await websocket.send_text(json.dumps(message))

manager = ConnectionManager()

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    session_id: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None
    use_tools: bool = True

class ModelSwitchRequest(BaseModel):
    model: str
    session_id: str

class ConversationRequest(BaseModel):
    conversation_id: str
    session_id: str

# Routes
@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the main application"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MCP Arena</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <div id="app">
            <header class="app-header">
                <h1>MCP Arena</h1>
                <div class="model-selector">
                    <select id="model-select">
                        <option value="">Loading models...</option>
                    </select>
                </div>
            </header>
            
            <div class="chat-container">
                <div class="sidebar">
                    <div class="sidebar-section">
                        <h3>Conversations</h3>
                        <div id="conversations-list">
                            <div class="loading">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="sidebar-section">
                        <h3>Quick Actions</h3>
                        <div class="quick-actions">
                            <button onclick="sendCommand('@conversations')">@conversations</button>
                            <button onclick="sendCommand('@search-history')">@search-history</button>
                            <button onclick="sendCommand('/prompts')">Show prompts</button>
                        </div>
                    </div>
                </div>
                
                <div class="chat-main">
                    <div class="messages-container" id="messages">
                        <div class="welcome-message">
                            <h2>Welcome to MCP Arena</h2>
                            <p>Your intelligent research assistant powered by MCP and Ollama.</p>
                            <div class="features">
                                <div class="feature">
                                    <strong>🔍 Web Search</strong>
                                    <p>Search the web with DuckDuckGo integration</p>
                                </div>
                                <div class="feature">
                                    <strong>📄 Paper Analysis</strong>
                                    <p>Summarize and analyze academic papers</p>
                                </div>
                                <div class="feature">
                                    <strong>💬 Smart Chat</strong>
                                    <p>Engage with local AI models via Ollama</p>
                                </div>
                            </div>
                            <p class="help-text">
                                Try asking me to search for something, or use commands like 
                                <code>@conversations</code> or <code>/prompt research_prompt topic=AI</code>
                            </p>
                        </div>
                    </div>
                    
                    <div class="input-container">
                        <div class="input-wrapper">
                            <textarea 
                                id="message-input" 
                                placeholder="Ask me anything, use @commands for resources, or /commands for prompts..."
                                rows="1"
                            ></textarea>
                            <button id="send-button">Send</button>
                        </div>
                        <div class="input-help">
                            <span class="help-item">@ - Access resources</span>
                            <span class="help-item">/ - Use prompts</span>
                            <span class="help-item">Ctrl+Enter - Send message</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="/static/main.js"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/models")
async def get_models():
    """Get available Ollama models"""
    try:
        client = await get_ollama_client()
        models = client.get_available_models()
        current_model = client.get_current_model()
        
        print(f"API: Returning models: {models}, current: {current_model}")
        
        return {
            'models': models,
            'current': current_model,
            'status': 'success'
        }
    except Exception as e:
        print(f"API Error getting models: {e}")
        # Return fallback response so frontend doesn't break
        import httpx
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [model['name'] for model in data.get('models', [])]
                    return {
                        'models': models,
                        'current': models[0] if models else 'llama3.1:latest',
                        'status': 'fallback'
                    }
        except:
            pass
        
        return {
            'models': ['llama3.1:latest', 'llama3.2:latest', 'qwen3:4b'],
            'current': 'llama3.1:latest',
            'status': 'error',
            'error': str(e)
        }

@app.post("/api/model/switch")
async def switch_model(request: ModelSwitchRequest):
    """Switch the active model for a session"""
    try:
        session = manager.user_sessions.get(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        client = session.get('ollama_client')
        if not client:
            client = await get_ollama_client()
            session['ollama_client'] = client
        
        success = client.set_model(request.model)
        if not success:
            raise HTTPException(status_code=400, detail="Model not available")
        
        return {'success': True, 'model': request.model}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations")
async def get_conversations():
    """Get list of saved conversations"""
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data/conversations.db")
        if not db_path.exists():
            return {
                'conversations': "# Conversations\n\nNo conversations found.",
                'status': 'success'
            }
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, model, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
        """)
        
        conversations = cursor.fetchall()
        conn.close()
        
        if not conversations:
            conversations_markdown = "# Conversations\n\nNo conversations found."
        else:
            conversations_markdown = "# Saved Conversations\n\n"
            for conv_id, title, model, created_at, updated_at in conversations:
                conversations_markdown += f"## {title}\n"
                conversations_markdown += f"- **ID**: {conv_id}\n"
                conversations_markdown += f"- **Model**: {model}\n"
                conversations_markdown += f"- **Created**: {created_at}\n"
                conversations_markdown += f"- **Updated**: {updated_at}\n\n"
                conversations_markdown += "---\n\n"
        
        print(f"API: Got {len(conversations)} conversations")
        
        return {
            'conversations': conversations_markdown,
            'status': 'success'
        }
    except Exception as e:
        print(f"API Error getting conversations: {e}")
        return {
            'conversations': "# Conversations\n\nNo conversations found.",
            'status': 'error',
            'error': str(e)
        }

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    await manager.connect(websocket, session_id)
    
    # Initialize Ollama client for this session
    client = await get_ollama_client()
    
    # Register MCP tools with the client
    client.register_tool('web_search', web_search, 'Search the web using DuckDuckGo')
    client.register_tool('summarize_paper', summarize_paper, 'Summarize academic papers from URLs')
    client.register_tool('save_conversation', save_conversation, 'Save conversation to database')
    
    manager.user_sessions[session_id]['ollama_client'] = client
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get('type')
            
            if message_type == 'chat':
                await handle_chat_message(session_id, message_data)
            elif message_type == 'resource':
                await handle_resource_request(session_id, message_data)
            elif message_type == 'prompt':
                await handle_prompt_request(session_id, message_data)
            elif message_type == 'load_conversation':
                await handle_load_conversation(session_id, message_data)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)

async def handle_chat_message(session_id: str, message_data: dict):
    """Handle regular chat messages"""
    try:
        session = manager.user_sessions[session_id]
        client: OllamaClient = session['ollama_client']
        
        message = message_data.get('message', '')
        use_tools = message_data.get('use_tools', True)
        stream = message_data.get('stream', True)
        
        # Send user message confirmation
        await manager.send_message(session_id, {
            'type': 'user_message',
            'content': message
        })
        
        if stream:
            # Handle streaming response
            await manager.send_message(session_id, {
                'type': 'assistant_start',
                'content': ''
            })
            
            async for chunk in client.chat(message, use_tools=use_tools, stream=True):
                await manager.send_message(session_id, {
                    'type': 'assistant_chunk',
                    'content': chunk
                })
            
            await manager.send_message(session_id, {
                'type': 'assistant_end',
                'content': ''
            })
        else:
            # Handle single response
            response = await client.chat(message, use_tools=use_tools, stream=False)
            await manager.send_message(session_id, {
                'type': 'assistant_message',
                'content': response
            })
            
    except Exception as e:
        await manager.send_message(session_id, {
            'type': 'error',
            'content': f'Error: {str(e)}'
        })

async def handle_resource_request(session_id: str, message_data: dict):
    """Handle resource requests (@commands)"""
    try:
        resource = message_data.get('resource', '')
        
        if resource == 'conversations':
            result = get_conversations_list()
        elif resource == 'search-history':
            result = get_search_history()
        elif resource.startswith('conversation:'):
            conv_id = resource.split(':', 1)[1]
            result = get_conversation_details(conv_id)
        else:
            result = f"Unknown resource: {resource}"
        
        await manager.send_message(session_id, {
            'type': 'resource_result',
            'resource': resource,
            'content': result
        })
        
    except Exception as e:
        await manager.send_message(session_id, {
            'type': 'error',
            'content': f'Resource error: {str(e)}'
        })

async def handle_prompt_request(session_id: str, message_data: dict):
    """Handle prompt requests (/commands)"""
    try:
        prompt_name = message_data.get('prompt', '')
        params = message_data.get('params', {})
        
        if prompt_name == 'research_prompt':
            topic = params.get('topic', 'AI')
            num_papers = int(params.get('num_papers', 5))
            result = research_prompt(topic, num_papers)
        elif prompt_name == 'chat_starter':
            style = params.get('style', 'casual')
            result = chat_starter(style)
        else:
            result = f"Unknown prompt: {prompt_name}"
        
        await manager.send_message(session_id, {
            'type': 'prompt_result',
            'prompt': prompt_name,
            'content': result
        })
        
    except Exception as e:
        await manager.send_message(session_id, {
            'type': 'error',
            'content': f'Prompt error: {str(e)}'
        })

async def handle_load_conversation(session_id: str, message_data: dict):
    """Handle loading a saved conversation"""
    try:
        conversation_id = message_data.get('conversation_id', '')
        session = manager.user_sessions[session_id]
        client: OllamaClient = session['ollama_client']
        
        # Get conversation details
        conversation_data = get_conversation_details(conversation_id)
        
        # TODO: Parse conversation data and load into client
        # This would require parsing the markdown format back to messages
        
        await manager.send_message(session_id, {
            'type': 'conversation_loaded',
            'conversation_id': conversation_id,
            'content': conversation_data
        })
        
    except Exception as e:
        await manager.send_message(session_id, {
            'type': 'error',
            'content': f'Load conversation error: {str(e)}'
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)