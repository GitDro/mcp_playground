#!/usr/bin/env python3
"""
Quick test script to test the list_saved tool directly
"""

import asyncio
from fastmcp import Client

async def test_list_saved():
    """Test the list_saved tool directly"""
    try:
        # Import the FastMCP server instance
        from src import mcp
        
        # Create a client with in-memory transport
        async with Client(mcp) as client:
            print("🧪 Testing list_saved tool...")
            
            # Call list_saved tool with no arguments
            result = await client.call_tool("list_saved", {})
            
            # Extract the content
            if hasattr(result, 'content') and result.content:
                content_item = result.content[0]
                if hasattr(content_item, 'text'):
                    response = content_item.text
                else:
                    response = str(content_item)
            else:
                response = str(result)
            
            print("📋 list_saved result:")
            print("=" * 50)
            print(response)
            print("=" * 50)
            
    except Exception as e:
        print(f"❌ Error testing list_saved: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_list_saved())