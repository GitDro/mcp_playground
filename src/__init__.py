"""
MCP Playground Source Package

This package contains the modularized MCP server implementation.
"""

# Import and expose the main MCP server instance
from .server import mcp

# Make the server instance available when importing the package
__all__ = ['mcp']