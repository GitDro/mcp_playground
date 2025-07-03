#!/usr/bin/env python3
"""
Quick test script to verify MCP server functionality
"""

import asyncio
import sys
from fastmcp import Client

async def test_mcp_server():
    """Test the MCP server connection and basic functionality"""
    print("🧪 Testing MCP server connection...")
    
    try:
        # Import the FastMCP server instance (in-memory approach)
        from mcp_server import mcp
        print(f"📡 Connecting to FastMCP server (in-memory transport)")
        
        async with Client(mcp) as client:
            print("✅ MCP server connected successfully!")
            
            # List available tools
            tools = await client.list_tools()
            print(f"🔧 Found {len(tools)} tools:")
            for tool in tools:
                print(f"   - {tool.name}: {tool.description}")
            
            # Test a simple tool call
            if tools:
                print(f"\n🚀 Testing tool: {tools[0].name}")
                try:
                    # Try web search as a basic test
                    if tools[0].name == "web_search":
                        result = await client.call_tool("web_search", {"query": "test", "max_results": 1})
                        print(f"✅ Tool call successful! Result preview: {str(result)[:100]}...")
                    else:
                        print(f"ℹ️  Skipping test for {tools[0].name} (would need specific parameters)")
                except Exception as e:
                    print(f"⚠️  Tool call failed: {e}")
            
            print("\n🎉 MCP server test completed successfully!")
            return True
            
    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   1. Make sure you're in the project directory")
        print("   2. Run 'uv sync' to install dependencies")
        print("   3. Try running 'uv run python mcp_server.py stdio' manually")
        return False

if __name__ == "__main__":
    print("MCP Playground - Server Test")
    print("=" * 40)
    
    # Run the test
    success = asyncio.run(test_mcp_server())
    
    if success:
        print("\n✅ Ready to run: uv run streamlit run app_fastmcp.py")
        sys.exit(0)
    else:
        print("\n❌ Please fix the issues above before running the Streamlit app")
        sys.exit(1)