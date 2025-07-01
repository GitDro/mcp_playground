// MCP Arena - Frontend JavaScript

class MCPArena {
    constructor() {
        this.websocket = null;
        this.sessionId = this.generateSessionId();
        this.isConnected = false;
        this.currentModel = null;
        this.isTyping = false;
        
        this.initializeElements();
        this.setupEventListeners();
        this.connect();
        this.loadModels();
        this.loadConversations();
    }
    
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now();
    }
    
    initializeElements() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.modelSelect = document.getElementById('model-select');
        this.conversationsList = document.getElementById('conversations-list');
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
            const response = await fetch('/api/models');
            const data = await response.json();
            
            console.log('Models API response:', data);
            
            this.modelSelect.innerHTML = '';
            
            if (data.models && Array.isArray(data.models)) {
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
            } else {
                throw new Error('Invalid models data received');
            }
            
        } catch (error) {
            console.error('Failed to load models:', error);
            this.modelSelect.innerHTML = '<option value="">Failed to load models - Check console</option>';
            
            // Add fallback models if API fails
            const fallbackModels = ['llama3.1:latest', 'llama3.2:latest', 'qwen3:4b'];
            fallbackModels.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model + ' (fallback)';
                this.modelSelect.appendChild(option);
            });
        }
    }
    
    async loadConversations() {
        try {
            console.log('Loading conversations...');
            const response = await fetch('/api/conversations');
            const data = await response.json();
            
            console.log('Conversations API response:', data);
            
            // For now, just show that conversations are loaded
            this.conversationsList.innerHTML = '<div class="conversations-summary">Conversations loaded</div>';
            
        } catch (error) {
            console.error('Failed to load conversations:', error);
            this.conversationsList.innerHTML = '<div class="error">Failed to load conversations</div>';
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
        messageDiv.className = 'message system';
        const icon = type === 'error' ? '❌' : 'ℹ️';
        messageDiv.innerHTML = `
            <div class="message-avatar">${icon}</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
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