"""
Main MCP server setup and tool registration

This module sets up the FastMCP server and registers all tools from the various modules.
"""

import logging
from dotenv import load_dotenv
from fastmcp import FastMCP

# Import tool registration functions
from .tools.web import register_web_tools
from .tools.arxiv import register_arxiv_tools
from .tools.financial import register_financial_tools
from .tools.youtube import register_youtube_tools
from .tools.weather import register_weather_tools
from .tools.memory import register_memory_tools

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastMCP server
mcp = FastMCP(name="MCPPlaygroundServer")

# Register all tools
def setup_server():
    """Set up the MCP server with all tools"""
    logger.info("Setting up MCP server with all tools...")
    
    # Register tools from each module
    register_web_tools(mcp)
    register_arxiv_tools(mcp)
    register_financial_tools(mcp)
    register_youtube_tools(mcp)
    register_weather_tools(mcp)
    register_memory_tools(mcp)
    
    logger.info("All tools registered successfully")
    return mcp

# Initialize the server
setup_server()

def main():
    """Main function to run the FastMCP server"""
    import sys
    
    # Check for command line arguments for different modes
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "http":
            # Run as HTTP server for web-based clients
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
            host = sys.argv[3] if len(sys.argv) > 3 else "0.0.0.0"
            print(f"Starting FastMCP HTTP server on {host}:{port}")
            mcp.run(transport="http", host=host, port=port)
        elif mode == "stdio":
            # Run as stdio server (default for local clients)
            print("Starting FastMCP stdio server")
            mcp.run(transport="stdio")
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python mcp_server.py [stdio|http] [port] [host]")
            sys.exit(1)
    else:
        # Default to stdio transport for local development
        print("Starting FastMCP server in stdio mode (default)")
        print("Use 'python mcp_server.py http 8000' for web mode")
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()