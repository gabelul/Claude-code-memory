# Claude Code Memory Solution

🧠 **Refactored Universal Semantic Indexer** - Modular, production-ready package providing persistent memory for Claude Code through direct Qdrant integration, knowledge graphs, and Tree-sitter parsing

## ✨ What's New in v2.2 - Layer 2 Orphaned Relation Cleanup

🧹 **NEW**: Automatic orphaned relation cleanup after entity deletion  
🔍 **Smart Detection**: Search-based orphan detection using Qdrant scroll API  
🗑️ **Comprehensive Coverage**: All three deletion triggers (incremental, watcher, service)  
✅ **Full Integration**: Automatic cleanup in `_handle_deleted_files()` method  
🔧 **Robust Implementation**: Efficient batch deletion with verbose logging  
📊 **Complete Testing**: 35+ new tests covering orphan scenarios  

## ✨ Previous Updates

**v2.1 - Auto-Detection**
- ⚡ Automatic incremental detection - no `--incremental` flag needed
- 🎯 Smart defaults and 15x performance optimization
- ✅ 157/158 tests passing with auto-detection

**v2.0 - Breaking Changes**
- 🚨 **BREAKING**: Removed MCP storage backend entirely - **Direct Qdrant integration only**  
- 🎯 **Simplified Architecture**: Single backend design eliminates dual-mode complexity  
- ❌ **Removed**: `--generate-commands` flag and manual command mode  
- 🔧 **Streamlined CLI**: Cleaner interface with direct automation only  
- 🏗️ **Code Reduction**: Removed ~445 lines across multiple files  
- ✅ **All Tests Passing**: 158/158 tests now pass with simplified architecture  
- ⚡ **Same Performance**: All optimizations preserved (15x incremental updates)

### Migration from v1.x
**v1.x users upgrading to v2.0:**
- Remove any `--generate-commands` flags from your scripts
- The MCP storage backend is no longer available - use direct Qdrant only
- All existing functionality preserved except manual command generation mode
- No changes needed to MCP server configuration or API usage  

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

# 3. Install enhanced MCP memory server
git clone https://github.com/Durafen/mcp-qdrant-memory.git
cd mcp-qdrant-memory && npm install && npm run build && cd ..

# 4. Install global wrapper (creates claude-indexer command)
./install.sh

# 5. Start Qdrant
docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant
```

### Configure Claude Code

**Option 1: Built-in CLI Command (Recommended)**
```bash
# Add MCP server using integrated command - reads API keys from settings.txt
claude-indexer add-mcp -c your-project-name
```

**Option 2: Legacy Script (deprecated)**
```bash
# Legacy method - use CLI command instead
# python add_mcp_project.py your-project-name  # REMOVED
# Use: claude-indexer add-mcp -c your-project-name
```

**Option 3: Manual Command Line**
```bash
claude mcp add your-project-memory -e OPENAI_API_KEY="YOUR_OPENAI_KEY" -e QDRANT_API_KEY="YOUR_QDRANT_KEY" -e QDRANT_URL="http://localhost:6333" -e QDRANT_COLLECTION_NAME="your-project-name" -- node "/path/to/memory/mcp-qdrant-memory/dist/index.js"
```

**Option 4: Manual JSON Configuration**
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

**Option 1: Built-in CLI Command (Recommended)**
```bash
# Add MCP server using integrated command
claude-indexer add-mcp -c my-project
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
# First run: Full mode (auto-detected), subsequent runs: Incremental mode (auto-detected)
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

## 🔄 Direct Qdrant Integration

Direct Qdrant integration with zero manual steps:
```bash
# Index new project (auto-loads to Qdrant)
claude-indexer -p /path/to/project -c project-name

# Auto-detection: First run = Full mode, subsequent runs = Incremental mode (15x faster)
# No flags needed - automatically uses optimal mode based on state file existence

# Clear collection (preserves manually added memories)
claude-indexer -p /path/to/project -c project-name --clear

# Clear entire collection (deletes all memories including manual)
claude-indexer -p /path/to/project -c project-name --clear-all
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

# Manual memory backup/restore
python utils/manual_memory_backup.py backup -c collection-name
python utils/manual_memory_backup.py restore -f backup-file.json
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

- **Basic Indexing**: Auto-detects Full/Incremental mode - no flags needed (just `claude-indexer -p X -c Y`)
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

- **Simplified Architecture**: Direct Qdrant integration only (v2.0 removed MCP backend)
- **Automatic incremental updates**: 15x faster processing of changed files (auto-detected)
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

## 📋 Memory Management & Backup

### Manual Memory Backup & Restore
Protect your valuable manual memories (analysis notes, insights, patterns) with automated backup/restore:

```bash
# Backup all manual entries from a collection
python utils/backup_manual_entries.py backup -c memory-project

# Generate MCP restore commands for manual entries
python utils/backup_manual_entries.py restore -f manual_entries_backup_memory-project.json

# Dry run to see what would be restored
python utils/backup_manual_entries.py restore -f backup.json --dry-run

# List supported manual entry types
python utils/backup_manual_entries.py --list-types
```

**Smart Classification:**
- **97 manual entries** correctly identified vs **1,838 auto-indexed** entries
- **Automation detection** via `file_path`, `collection`, `line_number` fields  
- **Manual structure** only: `type`, `name`, `entityType`, `observations`
- **Relevant relations**: Only backs up 2 relations connected to manual entries (vs 1,867 total)

**Use Cases:**
- **Pre-clearing**: Backup manual memories before `--clear-all` operations
- **Project migration**: Move manual insights between collections
- **Team sharing**: Export/import manual analysis and patterns
- **Disaster recovery**: Restore valuable manual entries after data loss

## 🎉 Proven Results

✅ **218 entities** + **201 relations** indexed from 17-file project  
✅ **100% success rate** on file processing  
✅ **Sub-second semantic search** across indexed codebases  
✅ **15x performance improvement** with automatic incremental updates  
✅ **Enterprise-grade accuracy** with Tree-sitter + Jedi analysis  
✅ **True Automation** - Zero manual copy-paste steps eliminated  
✅ **Direct Qdrant Integration** - Instant knowledge graph loading  
✅ **Real-time file watching** - 2-second debounced indexing  
✅ **Multi-project service** - Background automation for teams  
✅ **Git hooks integration** - Pre-commit automatic updates
✅ **Comprehensive Test Suite** - 90%+ coverage with CI/CD automation
✅ **Modular Architecture** - Clean, pluggable components for enterprise scale
✅ **Manual Memory Protection** - Smart backup/restore for valuable insights
✅ **Layer 2 Orphaned Relation Cleanup** - Automatic cleanup of broken relationships after entity deletion
# Test comment added at Thu Jun 26 21:34:06 CEST 2025
