#!/usr/bin/env python3
"""
MCP Arena - Cloud Server Entrypoint

Simplified cloud deployment entrypoint that uses the unified server architecture.
This file configures cloud-specific settings and exposes the server for FastMCP Cloud.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging for cloud environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_cloud_environment():
    """Setup cloud-specific environment and logging"""
    # Set logging level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # Log deployment info
    logger.info("=== MCP Arena Cloud Deployment ===")
    logger.info(f"Host: {os.getenv('HOST', '0.0.0.0')}")
    logger.info(f"Port: {os.getenv('PORT', '8000')}")
    logger.info("🔒 Authentication: MANDATORY (managed by FastMCP Cloud)")
    logger.info("☁️  Cloud mode: Enabled")

def main():
    """Main function for direct cloud deployment testing"""
    setup_cloud_environment()
    
    # Import and run the unified server in HTTP mode  
    from src.server import run_http_server
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    logger.info("Starting MCP Arena server for cloud deployment...")
    run_http_server(host=host, port=port)

# For FastMCP Cloud import
if __name__ == "__main__":
    # Direct execution for testing
    main()
else:
    # FastMCP Cloud import mode
    setup_cloud_environment()
    
    # Import the configured server instance
    from src.server import mcp
    
    # Add cloud-specific health check
    @mcp.tool(description="Health check endpoint for monitoring")
    def health_check() -> str:
        """Simple health check endpoint for cloud monitoring and load balancers"""
        return "MCP Arena server is healthy and running"
    
    logger.info("MCP Arena server ready for FastMCP Cloud")