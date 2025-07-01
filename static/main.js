// MCP Arena - Frontend JavaScript

class MCPArena {
    constructor() {
        this.websocket = null;
        this.sessionId = this.generateSessionId();
        this.isConnected = false;
        this.currentModel = null;
        this.isTyping = false;
        this.modelsLoaded = false;
        
        this.initializeElements();
        this.setupEventListeners();
        this.connect();
        this.loadModels();
    }
    
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now();
    }
    
    initializeElements() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.modelSelect = document.getElementById('model-select');
    }
    
    setupEventListeners() {
        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enter key handling
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                if (e.ctrlKey || e.metaKey) {
                    this.sendMessage();
                } else if (!e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            }
        });
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });
        
        // Model selection
        this.modelSelect.addEventListener('change', (e) => {
            this.switchModel(e.target.value);
        });
    }
    
    autoResizeTextarea() {
        const textarea = this.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('Connected to MCP Arena');
            this.isConnected = true;
            this.updateConnectionStatus(true);
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.websocket.onclose = () => {
            console.log('Disconnected from MCP Arena');
            this.isConnected = false;
            this.updateConnectionStatus(false);
            
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                if (!this.isConnected) {
                    this.connect();
                }
            }, 3000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    updateConnectionStatus(connected) {
        const status = connected ? 'Connected' : 'Disconnected';
        document.title = `MCP Arena - ${status}`;
    }
    
    async loadModels() {
        try {
            console.log('Loading models...');
            this.modelSelect.innerHTML = '<option value="">Loading models...</option>';
            
            const response = await fetch('/api/models');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('Models API response:', data);
            
            this.modelSelect.innerHTML = '';
            
            if (data.status === 'error') {
                throw new Error(data.error || 'Failed to load models');
            }
            
            if (data.models && Array.isArray(data.models) && data.models.length > 0) {
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    if (model === data.current) {
                        option.selected = true;
                        this.currentModel = model;
                    }
                    this.modelSelect.appendChild(option);
                });
                
                console.log(`Loaded ${data.models.length} models, current: ${data.current}`);
                
                // Re-enable send button
                this.sendButton.disabled = false;
                this.sendButton.textContent = 'Send';
                
                // Only show success message if we haven't shown it before
                if (!this.modelsLoaded) {
                    this.addSystemMessage(`Models loaded successfully (${data.models.length} available)`, 'success');
                    this.modelsLoaded = true;
                }
            } else {
                throw new Error('No models available from Ollama');
            }
            
        } catch (error) {
            console.error('Failed to load models:', error);
            
            this.modelSelect.innerHTML = '<option value="">⚠️ No models available</option>';
            
            // Show specific error message
            const errorMsg = error.message.includes('Ollama') 
                ? error.message 
                : 'Unable to connect to Ollama. Please ensure Ollama is running on localhost:11434 with models installed.';
            
            this.addSystemMessage(errorMsg, 'error');
            
            // Disable send button when no models
            this.sendButton.disabled = true;
            this.sendButton.textContent = 'No Models';
        }
    }
    
    
    async switchModel(modelName) {
        if (!modelName || modelName === this.currentModel) return;
        
        try {
            const response = await fetch('/api/model/switch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    model: modelName,
                    session_id: this.sessionId
                })
            });
            
            if (response.ok) {
                this.currentModel = modelName;
                this.addSystemMessage(`Switched to model: ${modelName}`);
            } else {
                throw new Error('Failed to switch model');
            }
            
        } catch (error) {
            console.error('Failed to switch model:', error);
            this.addSystemMessage(`Failed to switch to model: ${modelName}`, 'error');
        }
    }
    
    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || !this.isConnected) return;
        
        // Check if we have a valid model selected
        if (!this.currentModel || this.sendButton.disabled) {
            this.addSystemMessage('Please wait for models to load or check that Ollama is running.', 'warning');
            return;
        }
        
        // Clear input
        this.messageInput.value = '';
        this.autoResizeTextarea();
        
        // Check for special commands
        if (message.startsWith('@')) {
            this.handleResourceCommand(message);
        } else if (message.startsWith('/')) {
            this.handlePromptCommand(message);
        } else {
            this.handleChatMessage(message);
        }
    }
    
    handleChatMessage(message) {
        this.websocket.send(JSON.stringify({
            type: 'chat',
            message: message,
            stream: true,
            use_tools: true
        }));
    }
    
    handleResourceCommand(command) {
        const resource = command.substring(1); // Remove @
        
        this.websocket.send(JSON.stringify({
            type: 'resource',
            resource: resource
        }));
        
        this.addUserMessage(command);
    }
    
    handlePromptCommand(command) {
        const parts = command.substring(1).split(' '); // Remove /
        const promptName = parts[0];
        const params = {};
        
        // Parse parameters (key=value format)
        for (let i = 1; i < parts.length; i++) {
            const part = parts[i];
            if (part.includes('=')) {
                const [key, value] = part.split('=', 2);
                params[key] = value;
            }
        }
        
        if (promptName === 'prompts') {
            // Show available prompts
            this.addUserMessage(command);
            this.addSystemMessage(`Available prompts:
• /prompt research_prompt topic=AI num_papers=5
• /prompt chat_starter style=casual|academic|creative

Example: /prompt research_prompt topic="machine learning" num_papers=3`);
            return;
        }
        
        this.websocket.send(JSON.stringify({
            type: 'prompt',
            prompt: promptName,
            params: params
        }));
        
        this.addUserMessage(command);
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'user_message':
                this.addUserMessage(data.content);
                break;
                
            case 'assistant_start':
                this.startAssistantMessage();
                break;
                
            case 'assistant_chunk':
                this.appendToAssistantMessage(data.content);
                break;
                
            case 'assistant_end':
                this.endAssistantMessage();
                break;
                
            case 'assistant_message':
                this.addAssistantMessage(data.content);
                break;
                
            case 'resource_result':
                this.addResourceResult(data.resource, data.content);
                break;
                
            case 'prompt_result':
                this.addPromptResult(data.prompt, data.content);
                break;
                
            case 'error':
                this.addSystemMessage(data.content, 'error');
                break;
                
            case 'conversation_loaded':
                this.handleConversationLoaded(data);
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    addUserMessage(content) {
        this.removeWelcomeMessage();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `
            <div class="message-avatar">U</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    startAssistantMessage() {
        this.removeWelcomeMessage();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-content"></div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.currentAssistantMessage = messageDiv.querySelector('.message-content');
        this.showTypingIndicator();
        this.scrollToBottom();
    }
    
    appendToAssistantMessage(content) {
        if (this.currentAssistantMessage) {
            this.hideTypingIndicator();
            this.currentAssistantMessage.innerHTML += this.escapeHtml(content);
            this.scrollToBottom();
        }
    }
    
    endAssistantMessage() {
        if (this.currentAssistantMessage) {
            // Convert markdown-like formatting to HTML
            const content = this.currentAssistantMessage.textContent;
            this.currentAssistantMessage.innerHTML = this.formatMarkdown(content);
            this.currentAssistantMessage = null;
            this.hideTypingIndicator();
            this.scrollToBottom();
        }
    }
    
    addAssistantMessage(content) {
        this.removeWelcomeMessage();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-content">${this.formatMarkdown(content)}</div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addResourceResult(resource, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `
            <div class="message-avatar">📁</div>
            <div class="message-content">
                <strong>Resource: @${resource}</strong><br><br>
                ${this.formatMarkdown(content)}
            </div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addPromptResult(prompt, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `
            <div class="message-avatar">⚡</div>
            <div class="message-content">
                <strong>Prompt: /${prompt}</strong><br><br>
                ${this.formatMarkdown(content)}
            </div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addSystemMessage(content, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message system ${type}`;
        const icons = {
            'error': '❌',
            'success': '✅',
            'info': 'ℹ️',
            'warning': '⚠️'
        };
        const icon = icons[type] || icons['info'];
        messageDiv.innerHTML = `
            <div class="message-avatar">${icon}</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        
        // Auto-remove success messages after 3 seconds
        if (type === 'success') {
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 3000);
        }
    }
    
    showTypingIndicator() {
        if (this.isTyping) return;
        
        this.isTyping = true;
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            AI is typing
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        
        this.messagesContainer.appendChild(indicator);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
        this.isTyping = false;
    }
    
    removeWelcomeMessage() {
        const welcome = document.querySelector('.welcome-message');
        if (welcome) {
            welcome.remove();
        }
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    formatMarkdown(text) {
        // Simple markdown formatting
        return text
            // Headers
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            // Bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Code blocks
            .replace(/```([\\s\\S]*?)```/g, '<pre><code>$1</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Links
            .replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank">$1</a>')
            // Line breaks
            .replace(/\\n/g, '<br>')
            // Lists (simple)
            .replace(/^- (.*$)/gm, '<li>$1</li>')
            .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    }
    
    handleConversationLoaded(data) {
        this.addSystemMessage(`Loaded conversation: ${data.conversation_id}`);
        // Additional logic to display conversation content would go here
    }
}

// Global functions for quick actions
window.sendCommand = function(command) {
    if (window.mcpArena) {
        window.mcpArena.messageInput.value = command;
        window.mcpArena.sendMessage();
    }
};

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.mcpArena = new MCPArena();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && window.mcpArena && !window.mcpArena.isConnected) {
        window.mcpArena.connect();
    }
});