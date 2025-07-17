#!/usr/bin/env python3
"""
Test script for document management functionality
"""

import asyncio
import sys
from fastmcp import Client

async def test_document_tools():
    """Test the document management tools"""
    print("Testing Document Management Tools")
    print("=" * 40)
    
    try:
        # Import the FastMCP server instance
        from src import mcp
        
        # Create a client with in-memory transport
        async with Client(mcp) as client:
            print("✅ Connected to MCP server")
            
            # Test storing a note
            print("\n🧪 Testing store_note...")
            store_result = await client.call_tool("store_note", {
                "title": "Test Note - House Measurements",
                "content": "Living room: 12x15 feet\nBedroom: 10x12 feet\nKitchen: 8x10 feet",
                "tags": ["home", "measurements"],
                "save_to_file": True
            })
            print(f"Store Result: {store_result.content[0].text}")
            
            # Test searching notes
            print("\n🧪 Testing search_notes...")
            search_result = await client.call_tool("search_notes", {
                "query": "room dimensions",
                "limit": 3
            })
            print(f"Search Result: {search_result.content[0].text}")
            
            # Test listing notes
            print("\n🧪 Testing list_notes...")
            list_result = await client.call_tool("list_notes", {
                "limit": 5
            })
            print(f"List Result: {list_result.content[0].text}")
            
            print("\n🎉 Document tools test completed successfully!")
            
    except Exception as e:
        print(f"❌ Error testing document tools: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    result = asyncio.run(test_document_tools())
    if result:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()