"""
MCP Arena - Local Development Entry Point

Simple wrapper for local MCP clients and development.
Uses the unified server architecture from src/server.py.
"""

# Export the server for MCP clients
from src.server import mcp, main

if __name__ == "__main__":
    main()