#!/usr/bin/env python3
"""
Test script for simplified document management functionality
"""

import asyncio
import sys
import os
from fastmcp import Client

async def test_simplified_system():
    """Test the simplified document management system"""
    print("Testing Simplified Document System")
    print("=" * 40)
    
    try:
        # Import the FastMCP server instance
        from src import mcp
        
        # Create a client with in-memory transport
        async with Client(mcp) as client:
            print("✅ Connected to MCP server")
            
            # Test 1: Store a note
            print("\n🧪 Testing store_note...")
            store_result = await client.call_tool("store_note", {
                "title": "Medication Schedule",
                "content": "Take vitamin D: 1000 IU daily with breakfast\nTake omega-3: 2 capsules with dinner",
                "tags": ["health", "medication"],
                "save_to_file": True
            })
            print(f"Store Result: {store_result.content[0].text}")
            
            # Test 2: Search notes
            print("\n🧪 Testing search_notes...")
            search_result = await client.call_tool("search_notes", {
                "query": "daily supplements",
                "limit": 3
            })
            print(f"Search Result: {search_result.content[0].text}")
            
            # Test 3: List all notes
            print("\n🧪 Testing list_notes...")
            list_result = await client.call_tool("list_notes", {
                "limit": 5
            })
            print(f"List Result: {list_result.content[0].text}")
            
            # Test 4: Enhanced summarize_url (without saving)
            print("\n🧪 Testing summarize_url (basic)...")
            analyze_result = await client.call_tool("summarize_url", {
                "url": "https://httpbin.org/html",
                "save_content": False
            })
            print(f"Analyze Result: {analyze_result.content[0].text[:300]}...")
            
            print("\n🎉 Simplified document system test completed successfully!")
            
            # Show the simplified structure
            print("\n📁 Simplified Storage Structure:")
            docs_dir = os.path.expanduser('~/.cache/mcp_playground/documents')
            for root, dirs, files in os.walk(docs_dir):
                level = root.replace(docs_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 2 * (level + 1)
                for file in files:
                    print(f"{subindent}{file}")
            
    except Exception as e:
        print(f"❌ Error testing simplified system: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    result = asyncio.run(test_simplified_system())
    if result:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()