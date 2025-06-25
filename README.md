# Claude Code Memory Solution

🧠 **Refactored Universal Semantic Indexer** - Modular, production-ready package providing persistent memory for Claude Code through direct Qdrant integration, knowledge graphs, and Tree-sitter parsing

## ✨ What's New in v2.0

🎯 **Complete Refactor**: Transformed from 2000+ LOC monolith to clean modular package  
🔧 **Improved CLI**: Command-based interface with `python -m claude_indexer`  
🏗️ **Plugin Architecture**: Extensible embedders, storage backends, and parsers  
📦 **Python Standards**: Proper package structure and imports  
⚡ **Same Performance**: All optimizations preserved (15x incremental updates)  

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+  
- Claude Code installed
- Qdrant running (Docker recommended)

### Installation
```bash
# 1. Clone and setup
git clone https://github.com/Durafen/Claude-code-memory.git memory
cd memory
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure settings (copy template and add your API keys)
cp settings.template.txt settings.txt
# Edit settings.txt with your OpenAI API key and Qdrant settings

# 3. Install MCP memory server
git clone https://github.com/delorenj/mcp-qdrant-memory.git
cd mcp-qdrant-memory && npm install && npm run build && cd ..

# 4. Install global wrapper (creates claude-indexer command)
./install.sh

# 5. Start Qdrant
docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant
```

### Configure Claude Code

**Option 1: Automated Script (Easiest)**
```bash
# Quick setup using your settings.txt
python add_mcp_project.py your-project-name
```

**Option 2: Command Line**
```bash
claude mcp add your-project-memory -e OPENAI_API_KEY="YOUR_OPENAI_KEY" -e QDRANT_API_KEY="YOUR_QDRANT_KEY" -e QDRANT_URL="http://localhost:6333" -e QDRANT_COLLECTION_NAME="your-project-name" -- node "/path/to/memory/mcp-qdrant-memory/dist/index.js"
```

**Option 3: Manual JSON Configuration**
Add to `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "general-memory": {
      "command": "node",
      "args": ["/path/to/memory/mcp-qdrant-memory/dist/index.js"],
      "env": {
        "OPENAI_API_KEY": "sk-your-key-here",
        "QDRANT_API_KEY": "your-secret-key",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_COLLECTION_NAME": "general"
      }
    }
  }
}
```

### Initial Setup Test
```bash
# Test the installation
claude-indexer -p /path/to/any/python/project -c test-setup --verbose

# Expected output: successful indexing with entities and relations created
```

### Quick Help
```bash
# Show comprehensive help with all options and commands
claude-indexer

# Show version information
claude-indexer --version
```

## 📋 Adding New Projects

### Step 1: Add MCP Collection

**Option 1: Automated Script (Easiest)**
```bash
# Quick setup using your settings.txt
python add_mcp_project.py my-project
```

**Option 2: Command Line**
```bash
claude mcp add my-project-memory -e OPENAI_API_KEY="YOUR_OPENAI_KEY" -e QDRANT_API_KEY="YOUR_QDRANT_KEY" -e QDRANT_URL="http://localhost:6333" -e QDRANT_COLLECTION_NAME="my-project" -- node "/path/to/memory/mcp-qdrant-memory/dist/index.js"
```

**Option 3: Manual JSON Configuration**
Add to `~/.claude/claude_desktop_config.json`:
```json
"my-project-memory": {
  "command": "node",
  "args": ["/path/to/memory/mcp-qdrant-memory/dist/index.js"],
  "env": {
    "OPENAI_API_KEY": "sk-your-key-here",
    "QDRANT_API_KEY": "your-secret-key", 
    "QDRANT_URL": "http://localhost:6333",
    "QDRANT_COLLECTION_NAME": "my-project"
  }
}
```

### Step 2: Restart Claude Code

### Step 3: Index Your Project
```bash
# Basic indexing (auto-loads to Qdrant)
claude-indexer -p /path/to/your/project -c my-project

# With verbose output to see detailed progress
claude-indexer -p /path/to/your/project -c my-project --verbose
```

### Step 4: Automatic Knowledge Graph Loading
Knowledge graph is automatically loaded into Qdrant - no manual steps required!

### Step 5: Test Semantic Search
```bash
# In Claude Code
mcp__my-project-memory__search_similar("your search query")
```

## 🔄 Dual-Mode Operation

### Auto-Loading Mode (Default)
Direct Qdrant integration with zero manual steps:
```bash
# Index new project (auto-loads to Qdrant)
claude-indexer -p /path/to/project -c project-name

# Incremental updates (15x faster)
claude-indexer -p /path/to/project -c project-name --incremental

# Full reprocess (default behavior without --incremental)
claude-indexer -p /path/to/project -c project-name

# Clear collection (preserves manually added memories)
claude-indexer -p /path/to/project -c project-name --clear

# Clear entire collection (deletes all memories including manual)
claude-indexer -p /path/to/project -c project-name --clear-all
```

### Manual Command Mode
Generate MCP commands for manual execution:
```bash
# Generate commands without API calls (uses dummy embedder)
claude-indexer -p /path/to/project -c project-name --generate-commands

# Commands saved to: mcp_output/project-name_mcp_commands.txt
# Copy and paste commands into Claude Code for manual execution
```

### CLI Help
```bash
# Get comprehensive help (shows all options + commands)
claude-indexer
```

### Advanced Commands
```bash
# File watching - real-time indexing
claude-indexer watch start -p /path/to/project -c project-name

# Background service for multiple projects  
claude-indexer service add-project /path/to project project-name
claude-indexer service start
claude-indexer service status

# Git hooks integration
claude-indexer hooks install -p /path/to/project -c project-name
claude-indexer hooks status -p /path/to/project -c project-name
claude-indexer hooks uninstall -p /path/to/project -c project-name

# Search existing collections
claude-indexer search "function authentication" -p /path -c project-name

# Index single file
claude-indexer file /path/to/file.py -p /path/to/project -c project-name

# Help shows both indexing options AND available commands
claude-indexer --help
claude-indexer --version
```

## ⚙️ Service Configuration

The background service uses `~/.claude-indexer/config.json` for persistent configuration across multiple projects and file watching behavior.

### Default Configuration
```json
{
  "projects": [
    {
      "path": "/Users/username/Python-Projects/memory",
      "collection": "memory",
      "watch_enabled": true
    }
  ],
  "settings": {
    "debounce_seconds": 2.0,
    "watch_patterns": ["*.py", "*.md"],
    "ignore_patterns": [
      "*.pyc", "__pycache__", ".git", ".venv", 
      "node_modules", ".env", "*.log"
    ],
    "max_file_size": 1048576,
    "enable_logging": true
  }
}
```

### Configuration Options

- **`debounce_seconds`**: Delay before processing file changes (prevents rapid re-indexing during active editing)
- **`watch_patterns`**: File extensions to monitor for changes (supports glob patterns)
- **`ignore_patterns`**: Files/directories to skip during watching (performance optimization)
- **`max_file_size`**: Maximum file size in bytes for processing (default 1MB)
- **`enable_logging`**: Enable/disable detailed service logging

### Customizing Service Behavior

**Edit Configuration File:**
```bash
# Create or edit service configuration
vi ~/.claude-indexer/config.json

# Or let service create default config on first run
claude-indexer service start
```

**Add Projects to Service:**
```bash
# Add project to background watching
claude-indexer service add-project /path/to/project project-collection-name

# Start background service (watches all configured projects)
claude-indexer service start

# Check service status
claude-indexer service status
```

**Performance Tuning:**
- **Increase `debounce_seconds`** (3.0-5.0) for large projects with frequent changes
- **Reduce `watch_patterns`** to only essential file types for better performance
- **Add specific paths** to `ignore_patterns` for directories with many temporary files
- **Adjust `max_file_size`** based on your largest source files

### Multi-Project Configuration Example
```json
{
  "projects": [
    {
      "path": "/home/dev/web-app",
      "collection": "webapp-memory",
      "watch_enabled": true
    },
    {
      "path": "/home/dev/api-service", 
      "collection": "api-memory",
      "watch_enabled": true
    }
  ],
  "settings": {
    "debounce_seconds": 3.0,
    "watch_patterns": ["*.py", "*.js", "*.ts", "*.md"],
    "ignore_patterns": ["*.pyc", "__pycache__", ".git", ".venv", "node_modules", "dist", "build"]
  }
}
```

## 🎯 When to Use Each Mode

- **Basic Indexing**: New projects, major refactoring, scheduled updates (just `claude-indexer -p X -c Y`)
- **File Watching**: Active development sessions, real-time feedback (`claude-indexer watch start`)
- **Background Service**: Multiple projects, continuous development (`claude-indexer service start`)
- **Git Hooks**: Team workflows, automated CI/CD integration (`claude-indexer hooks install`)

### CLI Interface Improvements

**Simplified Basic Usage:**
- No need for `index` command - basic usage is `claude-indexer -p X -c Y`
- Use `-p` and `-c` shortcuts instead of `--project` and `--collection` for faster typing
- Running `claude-indexer` with no arguments shows comprehensive help
- Help displays both indexing options and available commands in one view

**Smart Command Routing:**
- Basic indexing options work directly with main command
- Advanced features available through subcommands (hooks, watch, service, search, file)
- Backward compatibility maintained - all existing functionality preserved
- Cleaner interface while keeping full feature set

## 🛠️ Technology Stack

- **Vector Database**: Qdrant for high-performance semantic search
- **Knowledge Graph**: delorenj/mcp-qdrant-memory for entities & relations
- **Code Analysis**: Tree-sitter (36x faster parsing) + Jedi (semantic analysis)
- **Embeddings**: OpenAI text-embedding-3-small for semantic similarity
- **File Processing**: Python + Markdown with node_modules filtering
- **Automation**: Python watchdog, git hooks, background services
- **Integration**: MCP (Model Context Protocol) for Claude Code

## ✨ Features

- **True Automation**: Direct Qdrant integration with zero manual intervention
- **Incremental updates**: 15x faster processing of changed files only
- **Real-time file watching**: Automatic indexing on code changes
- **Multi-project service**: Background watching for multiple projects
- **Git hooks integration**: Pre-commit automatic indexing
- **Project isolation**: Separate memory collections per project
- **Semantic search**: Find code by intent, not just keywords
- **Knowledge graphs**: Understands relationships between code components
- **Global wrapper**: Use `claude-indexer` from any directory
- **Zero Manual Steps**: Automatic loading eliminates copy-paste workflows
- **Smart Memory Clearing**: --clear preserves manual memories, --clear-all removes everything

## 🧪 Testing

**Run All Tests:**
```bash
# Complete test suite with coverage
python -m pytest --cov=claude_indexer --cov-report=term-missing -v

# Fast unit tests only
python -m pytest tests/unit/ -v

# Test by category
python -m pytest -m "unit" -v
python -m pytest -m "integration" -v  
python -m pytest -m "e2e" -v
```

**Test Architecture:**
- **Unit Tests**: Individual component testing (config, parser, embeddings, storage)
- **Integration Tests**: Component interaction workflows
- **End-to-End Tests**: Complete CLI and system validation
- **Coverage**: 90%+ target with detailed reporting
- **CI/CD**: Automated testing with GitHub Actions

## 📚 Full Documentation

See [CLAUDE.md](CLAUDE.md) for comprehensive architecture, setup instructions, and advanced usage.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Code   │◄──►│  MCP Server      │◄──►│   Qdrant DB     │
│                 │    │  (delorenj)      │    │   (Vectors)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        ▲
                       ┌────────────────┐               │
                       │ Universal      │               │ Direct
                       │ Indexer        │───────────────┘ Automation
                       │ (indexer.py)   │
                       └────────────────┘
                                │
                       ┌────────▼────────┐
                       │  Tree-sitter +  │
                       │      Jedi       │
                       │  (Code Analysis)│
                       └─────────────────┘
```

## 🎉 Proven Results

✅ **218 entities** + **201 relations** indexed from 17-file project  
✅ **100% success rate** on file processing  
✅ **Sub-second semantic search** across indexed codebases  
✅ **15x performance improvement** with incremental updates  
✅ **Enterprise-grade accuracy** with Tree-sitter + Jedi analysis  
✅ **True Automation** - Zero manual copy-paste steps eliminated  
✅ **Direct Qdrant Integration** - Instant knowledge graph loading  
✅ **Real-time file watching** - 2-second debounced indexing  
✅ **Multi-project service** - Background automation for teams  
✅ **Git hooks integration** - Pre-commit automatic updates
✅ **Comprehensive Test Suite** - 90%+ coverage with CI/CD automation
✅ **Modular Architecture** - Clean, pluggable components for enterprise scale
