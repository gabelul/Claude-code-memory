#!/usr/bin/env python3
"""
Quick MCP Server Setup Script for Claude Code Memory Solution

Usage: python add_mcp_project.py <project_name>
Example: python add_mcp_project.py my-awesome-project

This script:
1. Reads API keys from settings.txt
2. Automatically adds MCP server to Claude Code using `claude mcp add`
3. Uses project name as collection name
"""

import sys
import os
import subprocess
from pathlib import Path


def load_settings():
    """Load configuration from settings.txt"""
    settings_file = Path(__file__).parent / "settings.txt"
    
    if not settings_file.exists():
        print("❌ settings.txt not found!")
        print("Run: cp settings.template.txt settings.txt")
        print("Then edit settings.txt with your API keys")
        sys.exit(1)
    
    settings = {}
    with open(settings_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                settings[key.strip()] = value.strip()
    
    required_keys = ['openai_api_key', 'qdrant_api_key', 'qdrant_url']
    missing_keys = [key for key in required_keys if not settings.get(key) or settings[key] == f'your_{key}_here']
    
    if missing_keys:
        print(f"❌ Missing or placeholder values in settings.txt: {missing_keys}")
        print("Please edit settings.txt with your actual API keys")
        sys.exit(1)
    
    return settings


def get_script_directory():
    """Get the directory where this script is located"""
    return Path(__file__).parent.absolute()


def add_mcp_server(project_name, settings):
    """Add MCP server using claude mcp add command"""
    script_dir = get_script_directory()
    mcp_server_path = script_dir / "mcp-qdrant-memory" / "dist" / "index.js"
    
    if not mcp_server_path.exists():
        print(f"❌ MCP server not found at: {mcp_server_path}")
        print("Run the installation steps first:")
        print("git clone https://github.com/delorenj/mcp-qdrant-memory.git")
        print("cd mcp-qdrant-memory && npm install && npm run build")
        sys.exit(1)
    
    server_name = f"{project_name}-memory"
    
    cmd = [
        "claude", "mcp", "add", server_name,
        "-e", f"OPENAI_API_KEY={settings['openai_api_key']}",
        "-e", f"QDRANT_API_KEY={settings['qdrant_api_key']}",
        "-e", f"QDRANT_URL={settings['qdrant_url']}",
        "-e", f"QDRANT_COLLECTION_NAME={project_name}",
        "--",
        "node", str(mcp_server_path)
    ]
    
    print(f"🚀 Adding MCP server: {server_name}")
    print(f"📊 Collection name: {project_name}")
    print(f"🔗 Server path: {mcp_server_path}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ MCP server added successfully!")
            print(f"🎯 Server name: {server_name}")
            print(f"📁 Collection: {project_name}")
            print()
            print("Next steps:")
            print("1. Restart Claude Code")
            print(f"2. Index your project: claude-indexer --project /path/to/project --collection {project_name}")
            print(f"3. Test search: mcp__{server_name.replace('-', '_')}__search_similar('your query')")
        else:
            print("❌ Failed to add MCP server")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            sys.exit(1)
            
    except FileNotFoundError:
        print("❌ 'claude' command not found")
        print("Make sure Claude Code is installed and in your PATH")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running command: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) != 2:
        print("Usage: python add_mcp_project.py <project_name>")
        print("Example: python add_mcp_project.py my-awesome-project")
        sys.exit(1)
    
    project_name = sys.argv[1]
    
    # Validate project name
    if not project_name.replace('-', '').replace('_', '').isalnum():
        print("❌ Project name should only contain letters, numbers, hyphens, and underscores")
        sys.exit(1)
    
    print(f"🔧 Setting up MCP server for project: {project_name}")
    print()
    
    # Load settings
    settings = load_settings()
    print("✅ Settings loaded successfully")
    
    # Add MCP server
    add_mcp_server(project_name, settings)


if __name__ == "__main__":
    main()