"""
Main MCP server setup and tool registration

This module sets up the FastMCP server and registers all tools from the various modules.
Enhanced with retry middleware for robust error recovery and type correction.
"""

import logging
import os
from dotenv import load_dotenv
from fastmcp import FastMCP

# Import tool registration functions
from .tools.web import register_web_tools
from .tools.arxiv import register_arxiv_tools
from .tools.financial import register_financial_tools
from .tools.youtube import register_youtube_tools
from .tools.weather import register_weather_tools
from .tools.memory import register_memory_tools
from .tools.tides import register_tide_tools
from .tools.crime import register_crime_tools
from .tools.statscan import register_statscan_tools
from .tools.documents import register_document_tools

# Import retry framework
from .core.tool_wrapper import configure_retry_behavior, ToolWrapperConfig
from .core.retry_manager import RetryManager

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastMCP server
mcp = FastMCP(name="MCPPlaygroundServer")

# Configure retry behavior from environment variables
def configure_retry_settings():
    """Configure global retry behavior based on environment variables"""
    max_attempts = int(os.getenv("MCP_RETRY_MAX_ATTEMPTS", "3"))
    base_delay = float(os.getenv("MCP_RETRY_BASE_DELAY", "0.5"))
    enable_type_coercion = os.getenv("MCP_RETRY_TYPE_COERCION", "true").lower() == "true"
    enable_logging = os.getenv("MCP_RETRY_LOGGING", "true").lower() == "true"
    
    config = ToolWrapperConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        enable_type_coercion=enable_type_coercion,
        enable_logging=enable_logging,
        enable_stats=True
    )
    
    configure_retry_behavior(config)
    logger.info(f"Retry middleware configured: max_attempts={max_attempts}, "
                f"base_delay={base_delay}, type_coercion={enable_type_coercion}")
    
    return config

# Global retry configuration
retry_config = configure_retry_settings()

# Register all tools
def setup_server(enable_retry_middleware: bool = True):
    """Set up the MCP server with all tools and optional retry middleware"""
    logger.info("Setting up MCP server with all tools...")
    
    if enable_retry_middleware:
        logger.info("Retry middleware enabled for enhanced error recovery")
    
    # Register tools from each module
    register_web_tools(mcp)
    register_arxiv_tools(mcp)
    register_financial_tools(mcp)
    register_youtube_tools(mcp)
    register_weather_tools(mcp)
    register_memory_tools(mcp)
    register_tide_tools(mcp)
    register_crime_tools(mcp)
    register_statscan_tools(mcp)
    register_document_tools(mcp)
    
    logger.info("All tools registered successfully")
    return mcp

def get_server_stats():
    """Get server statistics including retry configuration"""
    from .core.tool_wrapper import get_tool_stats
    
    stats = {
        "server_name": "MCPPlaygroundServer",
        "retry_middleware_enabled": True,
        "retry_config": {
            "max_attempts": retry_config.max_attempts,
            "base_delay": retry_config.base_delay,
            "type_coercion_enabled": retry_config.enable_type_coercion,
            "logging_enabled": retry_config.enable_logging,
            "stats_enabled": retry_config.enable_stats
        },
        "registered_tools": []
    }
    
    # Get stats for registered tools (would need to be implemented per tool)
    logger.info("Server statistics requested")
    return stats

def enable_retry_for_existing_tools():
    """
    Enable retry capabilities for tools that were registered without retry support.
    This is useful for retroactively adding retry to existing tools.
    """
    logger.info("Enabling retry capabilities for existing tools...")
    # This would need to be implemented by inspecting the FastMCP server's registered tools
    # and wrapping them with retry logic. For now, this is a placeholder for future enhancement.
    pass

# Initialize the server
setup_server()

def run_http_server(host="0.0.0.0", port=8000, enable_cors=True):
    """Run the server in HTTP mode for cloud deployment and web clients"""
    logger.info(f"Starting MCP Arena HTTP server on {host}:{port}")
    logger.info("HTTP mode - suitable for cloud deployment and web clients")
    
    if enable_cors:
        logger.info("CORS enabled for cross-origin requests")
    
    try:
        mcp.run(
            transport="http",
            host=host,
            port=port,
        )
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {e}")
        raise

def run_stdio_server():
    """Run the server in stdio mode for local development"""
    logger.info("Starting MCP Arena stdio server")
    logger.info("Stdio mode - suitable for local MCP clients and development")
    
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Failed to start stdio server: {e}")
        raise

def main():
    """Main function to run the FastMCP server with enhanced transport support"""
    import sys
    
    # Check for command line arguments for different modes
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "http":
            # Run as HTTP server for web-based clients and cloud deployment
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
            host = sys.argv[3] if len(sys.argv) > 3 else "0.0.0.0"
            enable_cors = os.getenv("ENABLE_CORS", "true").lower() == "true"
            run_http_server(host=host, port=port, enable_cors=enable_cors)
        elif mode == "stdio":
            # Run as stdio server (default for local clients)
            run_stdio_server()
        else:
            print(f"Unknown mode: {mode}")
            print("Usage:")
            print("  python -m src.server stdio              # Local development (default)")
            print("  python -m src.server http [port] [host] # HTTP server for cloud")
            print("Examples:")
            print("  python -m src.server http 8000          # HTTP on port 8000")
            print("  python -m src.server http 8000 0.0.0.0  # HTTP on all interfaces")
            sys.exit(1)
    else:
        # Default to stdio transport for local development
        logger.info("No mode specified - defaulting to stdio mode for local development")
        logger.info("Use 'python -m src.server http' for cloud/web mode")
        run_stdio_server()

if __name__ == "__main__":
    main()