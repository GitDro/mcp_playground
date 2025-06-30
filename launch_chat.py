#!/usr/bin/env python3
"""
Launch Script for MCP Chat Interface

Simple launcher that validates prerequisites and starts the Streamlit chat interface.

Usage:
    python launch_chat.py

Author: MCP Arena
"""

import subprocess
import sys
import time
from pathlib import Path


def check_ollama() -> bool:
    """Check if Ollama is running and has models available."""
    try:
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Header + at least one model
                print("✅ Ollama is running with models available")
                return True
            else:
                print("❌ Ollama is running but no models found")
                print("💡 Install a model with: ollama pull llama3.2")
                return False
        else:
            print("❌ Ollama command failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Ollama command timed out")
        return False
    except FileNotFoundError:
        print("❌ Ollama not found. Please install Ollama first.")
        return False
    except Exception as e:
        print(f"❌ Error checking Ollama: {e}")
        return False


def check_mcp_server() -> bool:
    """Check if MCP server files exist."""
    server_file = Path("web_search_server.py")
    if server_file.exists():
        print("✅ MCP server file found")
        return True
    else:
        print("❌ MCP server file not found")
        return False


def launch_streamlit() -> None:
    """Launch the Streamlit chat interface."""
    try:
        print("🚀 Starting Streamlit chat interface...")
        print("📱 Opening browser...")
        
        # Start Streamlit
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", 
            "chat_interface.py", 
            "--server.headless", "false"
        ])
        
        # Wait a moment for Streamlit to start
        time.sleep(3)
        
        print("✅ Chat interface is running!")
        print("🌐 Open http://localhost:8501 in your browser")
        print("🛑 Press Ctrl+C to stop")
        
        # Wait for the process
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            process.terminate()
            process.wait()
            
    except Exception as e:
        print(f"❌ Failed to launch Streamlit: {e}")


def main():
    """Main launcher function."""
    print("🤖 MCP Chat Interface Launcher")
    print("=" * 40)
    
    # Check prerequisites
    if not check_ollama():
        print("\n💡 Please ensure Ollama is installed and running with models")
        sys.exit(1)
    
    if not check_mcp_server():
        print("\n💡 Please ensure web_search_server.py is in the current directory")
        sys.exit(1)
    
    print("\n🎉 All checks passed!")
    print("📋 Available features:")
    print("   • Multiple Ollama model selection")
    print("   • Web search integration")
    print("   • Beautiful tool call visualization")
    print("   • Real-time chat interface")
    
    print("\n" + "=" * 40)
    
    # Launch the interface
    launch_streamlit()


if __name__ == "__main__":
    main()