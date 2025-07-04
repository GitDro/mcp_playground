"""
FastMCP Server for MCP Playground

Main entry point for the MCP server. This file maintains compatibility with 
external MCP clients like Windsurf while using the new modularized structure.

The actual server implementation is now in src/server.py with tools organized
in separate modules for better maintainability.
"""

# Import the server from the new modularized structure
from src import mcp
from src.server import main

# Export the mcp server for compatibility with external clients
__all__ = ['mcp', 'main']

if __name__ == "__main__":
    main()