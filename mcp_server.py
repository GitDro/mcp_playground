"""
MCP Arena Server - FastMCP-based server with tools, resources, and prompts
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastmcp import FastMCP
from duckduckgo_search import DDGS
import httpx
from pydantic import BaseModel

# Initialize FastMCP server
mcp = FastMCP("MCP Arena")

# Database and storage paths
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "conversations.db"
PAPERS_DIR = DATA_DIR / "papers"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
PAPERS_DIR.mkdir(exist_ok=True)

# Initialize database
def init_database():
    """Initialize SQLite database for conversations"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            model TEXT NOT NULL,
            messages TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            results TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

# Pydantic models for data validation
class SearchResult(BaseModel):
    title: str
    href: str
    body: str

class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class Conversation(BaseModel):
    id: str
    title: str
    model: str
    messages: List[ConversationMessage]
    created_at: str
    updated_at: str

# TOOLS
@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return formatted results.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Formatted search results as markdown
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"No search results found for: {query}"
        
        # Store search in history
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO search_history (query, results) VALUES (?, ?)",
            (query, json.dumps(results))
        )
        conn.commit()
        conn.close()
        
        # Format results as markdown
        formatted_results = f"# Search Results for: {query}\n\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"## {i}. {result.get('title', 'No Title')}\n"
            formatted_results += f"**URL**: {result.get('href', 'No URL')}\n"
            formatted_results += f"**Summary**: {result.get('body', 'No description available')}\n\n"
            formatted_results += "---\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Error performing search: {str(e)}"

@mcp.tool()
def summarize_paper(url: str) -> str:
    """
    Fetch and summarize an academic paper from a URL.
    
    Args:
        url: URL of the paper (PDF or webpage)
    
    Returns:
        Summary of the paper content
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # For now, return basic info about the URL
            # In a full implementation, you'd parse PDF content or extract text
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content)
            
            summary = f"# Paper Summary\n\n"
            summary += f"**URL**: {url}\n"
            summary += f"**Content Type**: {content_type}\n"
            summary += f"**Content Length**: {content_length:,} bytes\n\n"
            
            if 'pdf' in content_type.lower():
                summary += "**Note**: PDF content parsing requires additional implementation.\n"
                summary += "This is a placeholder summary for PDF content.\n"
            else:
                # Basic text extraction for web pages
                text_content = response.text[:1000]  # First 1000 chars
                summary += f"**Preview**: {text_content}...\n"
            
            return summary
            
    except Exception as e:
        return f"Error summarizing paper: {str(e)}"

@mcp.tool()
def save_conversation(conversation_id: str, title: str, model: str, messages: List[Dict[str, Any]]) -> str:
    """
    Save a conversation to the database.
    
    Args:
        conversation_id: Unique identifier for the conversation
        title: Title of the conversation
        model: Model used for the conversation
        messages: List of message objects
    
    Returns:
        Confirmation message
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        messages_json = json.dumps(messages)
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO conversations 
            (id, title, model, messages, created_at, updated_at)
            VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM conversations WHERE id = ?), ?), ?)
        """, (conversation_id, title, model, messages_json, conversation_id, now, now))
        
        conn.commit()
        conn.close()
        
        return f"Conversation '{title}' saved successfully with ID: {conversation_id}"
        
    except Exception as e:
        return f"Error saving conversation: {str(e)}"

# RESOURCES
@mcp.resource("conversations://list")
def get_conversations_list() -> str:
    """
    List all saved conversations.
    
    Returns:
        Markdown formatted list of conversations
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, model, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
        """)
        
        conversations = cursor.fetchall()
        conn.close()
        
        if not conversations:
            return "# Conversations\n\nNo conversations found."
        
        content = "# Saved Conversations\n\n"
        for conv_id, title, model, created_at, updated_at in conversations:
            content += f"## {title}\n"
            content += f"- **ID**: {conv_id}\n"
            content += f"- **Model**: {model}\n"
            content += f"- **Created**: {created_at}\n"
            content += f"- **Updated**: {updated_at}\n\n"
            content += "---\n\n"
        
        return content
        
    except Exception as e:
        return f"Error retrieving conversations: {str(e)}"

@mcp.resource("conversations://{conversation_id}")
def get_conversation_details(conversation_id: str) -> str:
    """
    Get detailed information about a specific conversation.
    
    Args:
        conversation_id: The conversation ID to retrieve
    
    Returns:
        Detailed conversation information
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT title, model, messages, created_at, updated_at
            FROM conversations
            WHERE id = ?
        """, (conversation_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return f"# Conversation Not Found\n\nNo conversation found with ID: {conversation_id}"
        
        title, model, messages_json, created_at, updated_at = result
        messages = json.loads(messages_json)
        
        content = f"# {title}\n\n"
        content += f"**Model**: {model}\n"
        content += f"**Created**: {created_at}\n"
        content += f"**Updated**: {updated_at}\n"
        content += f"**Messages**: {len(messages)}\n\n"
        content += "## Messages\n\n"
        
        for msg in messages:
            role = msg.get('role', 'unknown')
            text = msg.get('content', '')
            timestamp = msg.get('timestamp', '')
            
            content += f"### {role.title()}\n"
            if timestamp:
                content += f"*{timestamp}*\n\n"
            content += f"{text}\n\n"
            content += "---\n\n"
        
        return content
        
    except Exception as e:
        return f"Error retrieving conversation: {str(e)}"

@mcp.resource("search://history")
def get_search_history() -> str:
    """
    Get recent search history.
    
    Returns:
        Markdown formatted search history
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT query, timestamp
            FROM search_history
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        searches = cursor.fetchall()
        conn.close()
        
        if not searches:
            return "# Search History\n\nNo searches found."
        
        content = "# Recent Searches\n\n"
        for query, timestamp in searches:
            content += f"- **{query}** *({timestamp})*\n"
        
        return content
        
    except Exception as e:
        return f"Error retrieving search history: {str(e)}"

# PROMPTS
@mcp.prompt()
def research_prompt(topic: str, num_papers: int = 5) -> str:
    """Generate a research prompt for finding and analyzing academic papers on a topic."""
    return f"""Research the topic '{topic}' by following these steps:

1. First, search for {num_papers} academic papers about '{topic}' using the web_search tool
2. For each relevant paper found, use the summarize_paper tool to get detailed information
3. Organize your findings with:
   - Paper titles and authors
   - Key findings and contributions
   - Methodologies used
   - Publication dates and venues
   - Relevance to '{topic}'

4. Provide a comprehensive analysis including:
   - Current state of research in '{topic}'
   - Common themes and trends
   - Research gaps and future directions
   - Most significant papers in this area

5. Present your findings in a clear, structured format with proper headings and citations.

Focus on providing both detailed information about individual papers and a high-level synthesis of the research landscape in {topic}."""

@mcp.prompt()
def chat_starter(style: str = "casual") -> str:
    """Generate conversation starter prompts based on style."""
    
    if style == "academic":
        return """I'm here to help with academic research and analysis. I can:
        
- Search for and summarize academic papers
- Help analyze research topics and trends
- Assist with literature reviews
- Provide insights on research methodologies

What academic topic would you like to explore today?"""
    
    elif style == "creative":
        return """I'm ready to help with creative and analytical tasks! I can:
        
- Research any topic using web search
- Summarize complex documents and papers
- Help brainstorm ideas and solutions
- Analyze trends and patterns

What creative challenge or research question can I help you with?"""
    
    else:  # casual
        return """Hi! I'm your research assistant. I can help you:
        
- Search the web for information
- Summarize papers and documents
- Save and organize our conversations
- Switch between different AI models

What would you like to learn about or discuss today?"""

if __name__ == "__main__":
    mcp.run()