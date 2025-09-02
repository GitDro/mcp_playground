#!/usr/bin/env python3
"""
MCP Arena - Cloud Server Entrypoint

This is the cloud-specific entrypoint for FastMCP Cloud deployment.
It configures the server for HTTP transport and cloud-optimized settings.

Local development continues to use src/server.py with stdio transport.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables for cloud deployment
load_dotenv()

# Configure logging for cloud environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_cloud_config():
    """Get cloud-specific configuration"""
    return {
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", "8000")),
        "enable_cors": os.getenv("ENABLE_CORS", "true").lower() == "true",
        "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
        # Authentication is MANDATORY for cloud deployment - never disable
        "enable_auth": True,
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        # Disable memory features that require local Ollama
        "disable_vector_memory": os.getenv("DISABLE_VECTOR_MEMORY", "true").lower() == "true",
        "cloud_mode": True,
    }

def setup_cloud_environment():
    """Setup cloud-specific environment configurations"""
    config = get_cloud_config()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, config["log_level"]))
    
    # Log deployment configuration (without sensitive info)
    logger.info("=== MCP Arena Cloud Deployment ===")
    logger.info(f"Host: {config['host']}")
    logger.info(f"Port: {config['port']}")
    logger.info(f"CORS enabled: {config['enable_cors']}")
    logger.info(f"Auth enabled: {config['enable_auth']}")
    logger.info(f"Log level: {config['log_level']}")
    
    return config

def create_cloud_server():
    """Create FastMCP server configured for cloud deployment"""
    from src.server import setup_server, mcp
    
    config = setup_cloud_environment()
    
    # Setup the MCP server with all tools
    server = setup_server(enable_retry_middleware=True)
    
    # Authentication is MANDATORY for cloud deployment
    auth_token = os.getenv("AUTH_TOKEN")
    if auth_token:
        logger.info("🔒 Authentication enabled with provided token - FastMCP Cloud will validate")
    else:
        logger.info("🔒 Authentication enabled - FastMCP Cloud will provide and validate tokens")
        logger.info("⚠️  Server is secured - only authenticated clients can access")
    
    # Configure for cloud mode - disable features requiring local services
    if config.get("disable_vector_memory", True):
        logger.info("🔧 Vector memory disabled for cloud deployment (no local Ollama)")
        # Set environment variable to disable vector memory in tools
        os.environ["DISABLE_VECTOR_MEMORY"] = "true"
    
    if config.get("cloud_mode", True):
        logger.info("☁️  Cloud mode enabled - optimized for serverless deployment")
    
    # Add health check endpoint
    @mcp.tool(description="Health check endpoint for monitoring")
    def health_check() -> str:
        """Simple health check endpoint for cloud monitoring and load balancers"""
        return "MCP Arena server is healthy and running"
    
    logger.info("Cloud server setup complete - all tools registered")
    return server, config

def main():
    """Main function for cloud deployment"""
    try:
        server, config = create_cloud_server()
        
        # Start server in HTTP mode for cloud deployment
        logger.info(f"Starting MCP Arena server for cloud deployment...")
        logger.info(f"Server will be available at http://{config['host']}:{config['port']}")
        
        # FastMCP Cloud will handle the HTTP transport automatically
        # This serves as the entrypoint that FastMCP Cloud will call
        server.run(
            transport="http",
            host=config["host"], 
            port=config["port"]
        )
        
    except Exception as e:
        logger.error(f"Failed to start cloud server: {e}")
        raise

# Expose the server for FastMCP Cloud
# FastMCP Cloud looks for a FastMCP instance at module level
if __name__ == "__main__":
    # When run directly (for testing)
    main()
else:
    # When imported by FastMCP Cloud
    server, _ = create_cloud_server()
    # Export the server instance that FastMCP Cloud expects
    mcp = server