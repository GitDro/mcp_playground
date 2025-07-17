#!/usr/bin/env python3
"""
Test script for simplified semantic RAG injection
"""

import asyncio
import sys
from fastmcp import Client

async def test_semantic_rag():
    """Test the pure semantic RAG injection system"""
    print("Testing Pure Semantic RAG Injection")
    print("=" * 40)
    
    try:
        # Import the FastMCP server instance
        from src import mcp
        
        # Create a client with in-memory transport
        async with Client(mcp) as client:
            print("✅ Connected to MCP server")
            
            # Store a test medication note
            print("\n📝 Creating test medication note...")
            await client.call_tool("store_note", {
                "title": "Daily Medication", 
                "content": "Take Lisinopril 10mg every morning with breakfast. Check blood pressure weekly.",
                "tags": ["health", "medication"]
            })
            
            print("\n🧪 Testing semantic similarity injection...")
            print("(You'll need to check debug output in the actual Streamlit app)")
            
            test_queries = [
                {
                    "query": "What's my daily medication schedule?",
                    "expected_relevance": ">85%",
                    "expected_injection": "Full context injection"
                },
                {
                    "query": "Tell me about my health routine",
                    "expected_relevance": "70-85%", 
                    "expected_injection": "Snippet injection"
                },
                {
                    "query": "What should I know about medicine?",
                    "expected_relevance": "30-70%",
                    "expected_injection": "No injection (too general)"
                },
                {
                    "query": "What's the weather today?",
                    "expected_relevance": "<30%",
                    "expected_injection": "No injection (tool query + low relevance)"
                }
            ]
            
            print(f"\n📋 Test scenarios:")
            for i, test in enumerate(test_queries, 1):
                print(f"{i}. '{test['query']}'")
                print(f"   Expected relevance: {test['expected_relevance']}")
                print(f"   Expected behavior: {test['expected_injection']}\n")
            
            print("🎯 Key Changes Made:")
            print("✅ Removed all keyword-based intent detection")
            print("✅ Pure semantic similarity thresholds:")
            print("   • >85% relevance → Full context injection")
            print("   • >70% relevance → Snippet injection")  
            print("   • <70% relevance → No injection")
            print("✅ Simple tool query detection (minimal keywords)")
            print("✅ Clean debug output with injection reasoning")
            
            print("\n💡 To test the live injection:")
            print("1. Run: uv run streamlit run app.py")
            print("2. Try the test queries above")
            print("3. Watch debug output for semantic injection details")
            print("4. Notice how embeddings naturally understand personal vs general queries")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def main():
    result = asyncio.run(test_semantic_rag())
    if result:
        print("\n✅ Semantic RAG system ready!")
        sys.exit(0)
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()