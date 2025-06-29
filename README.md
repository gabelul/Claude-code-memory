# Claude Code Memory Solution

🧠 **Refactored Universal Semantic Indexer** - Modular, production-ready package providing persistent memory for Claude Code through direct Qdrant integration, knowledge graphs, and Tree-sitter parsing

## ✅ v2.5 - Enhanced Multi-Language Support - COMPLETE & PRODUCTION READY

🎉 **NEW**: Extended from Python-only to **10+ file types** with tree-sitter universal parsing  
✅ **Multi-Language**: JavaScript/TypeScript, JSON, HTML, CSS, YAML, Text, CSV, INI support  
✅ **24 File Extensions**: Comprehensive web stack coverage (.js, .ts, .json, .html, .css, .yml, etc.)  
✅ **Progressive Disclosure**: Maintained across all languages with metadata/implementation chunks  
✅ **Smart Detection**: Automatic parser assignment based on file extensions  
✅ **Performance**: 7 multi-language files processed in 0.40s (49 entities, 78 relations)  
✅ **Zero Breaking Changes**: All existing Python/Markdown functionality preserved  
✅ **TreeSitter Foundation**: Unified AST parsing for consistent entity extraction  
✅ **Production Tested**: Complete integration with CoreIndexer and MCP server  

## ✨ Previous Updates

**v2.4 - Progressive Disclosure Architecture**
- 🚀 3.99ms metadata search (90% faster validated)
- 📊 Pure v2.4 Format with unified `"type": "chunk"` architecture
- 🔍 MCP get_implementation with on-demand detailed code access
- ⚡ 3.63ms full MCP workflow (sub-4ms achieved)
- 🎯 Voyage AI Integration with automatic provider detection
- ✅ All tests passing with 100% v2.4 format compliance

**v2.2 - Layer 2 Orphaned Relation Cleanup**
- 🧹 Automatic orphaned relation cleanup after entity deletion
- 🔍 Search-based orphan detection using Qdrant scroll API
- 🗑️ Comprehensive coverage for all deletion triggers
- 📊 35+ new tests covering orphan scenarios

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
# Edit settings.txt with your API keys and choose embedding provider

# 3. Install enhanced MCP memory server
git clone https://github.com/Durafen/mcp-qdrant-memory.git
cd mcp-qdrant-memory && npm install && npm run build && cd ..

# 4. Install global wrapper (creates claude-indexer command)
./install.sh

# 5. Start Qdrant
docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant
```

## ⚙️ Embedding Provider Configuration

### Voyage AI (Recommended - 85% Cost Reduction)
```bash
# Add to settings.txt
VOYAGE_API_KEY=your_voyage_key
EMBEDDING_PROVIDER=voyage
EMBEDDING_MODEL=voyage-3-lite  # or voyage-3
```

**Benefits:**
- 85% cost reduction vs OpenAI text-embedding-3-small
- Smaller vector size (512-dim vs 1536-dim) = 3x storage efficiency
- Similar semantic search quality

### OpenAI (Default)
```bash
# Add to settings.txt  
OPENAI_API_KEY=your_openai_key
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

### Chat Summarization Options
```bash
# GPT-4.1-mini (Recommended - 78% cost reduction)
OPENAI_API_KEY=your_openai_key
CHAT_MODEL=gpt-4.1-mini

# GPT-3.5-turbo (Legacy)  
CHAT_MODEL=gpt-3.5-turbo
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

**Enhanced MCP Server Features (v2.4.1):**
- **Progressive Disclosure**: `search_similar` returns metadata-first for 90% faster queries
- **Semantic Scope Implementation**: `get_implementation(entityName, scope?)` with contextual code retrieval
  - `minimal`: Just the entity implementation (default)
  - `logical`: Entity + helper functions/classes from same file
  - `dependencies`: Entity + imported modules and called functions
- **Smart Token Management**: Configurable limits per scope (20 logical, 30 dependencies)
- **Automatic Provider Detection**: Reads embedding provider from environment variables
- **Voyage AI Integration**: Built-in support for voyage-3-lite with cost optimization
- **Backward Compatibility**: Seamlessly handles both v2.3 and v2.4 chunk formats

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
# Add MCP server using integrated command with v2.4 progressive disclosure
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

### Step 5: Test Progressive Disclosure Search
```bash
# In Claude Code - 90% faster metadata-first search
mcp__my-project-memory__search_similar("your search query")

# Enhanced semantic scope implementation access (v2.4.1)
mcp__my-project-memory__get_implementation("entityName")  # minimal scope (default)
mcp__my-project-memory__get_implementation("entityName", "logical")  # same-file helpers  
mcp__my-project-memory__get_implementation("entityName", "dependencies")  # imports/calls
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

# Chat history processing with GPT-4.1-mini summarization
claude-indexer chat-index -p /path/to/project -c project-name --chat-file conversation.md
claude-indexer chat-search "debugging patterns" -p /path -c project-name

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

- **Multi-Language Parsing**: Tree-sitter universal AST parsing (10+ languages, 24 file extensions)
- **Vector Database**: Qdrant for high-performance semantic search
- **Knowledge Graph**: delorenj/mcp-qdrant-memory for entities & relations
- **Code Analysis**: Tree-sitter (36x faster parsing) + Jedi (semantic analysis)
- **Language Support**: JavaScript/TypeScript, JSON, HTML, CSS, YAML, Python, Markdown, Text, CSV, INI
- **Embeddings**: Dual provider architecture (OpenAI + Voyage AI) with 85% cost reduction
- **Chat Processing**: GPT-4.1-mini summarization with 78% cost savings
- **File Processing**: Universal parser registry with automatic file-to-parser matching
- **Automation**: Python watchdog, git hooks, background services
- **Integration**: MCP (Model Context Protocol) for Claude Code

## ✨ Features

- **Multi-Language Support**: 10+ programming languages with 24 file extensions (v2.5)
- **Universal AST Parsing**: Tree-sitter foundation for consistent entity extraction across languages (v2.5)
- **Web Stack Coverage**: Complete JavaScript/TypeScript, HTML, CSS, JSON, YAML support (v2.5)
- **Smart Parser Registry**: Automatic file-to-parser matching with extensible architecture (v2.5)
- **Cross-Language Relations**: HTML→CSS, JavaScript→JSON dependency tracking (v2.5)
- **Semantic Scope Implementation**: Contextual code retrieval with logical and dependencies scopes (v2.4.1)
- **Progressive Disclosure Architecture**: 90% faster metadata-first search with on-demand implementation access (v2.4)
- **Pure v2.4 Chunk Format**: Unified `"type": "chunk"` with `chunk_type` for metadata/implementation/relation (v2.4)
- **Smart Token Management**: Configurable scope limits and intelligent deduplication (v2.4.1)
- **Voyage AI MCP Integration**: Automatic provider detection with 85% cost reduction (v2.4)
- **Dual Embedding Providers**: OpenAI + Voyage AI with cost optimization (v2.3)
- **Chat History Processing**: GPT-4.1-mini summarization with 78% cost savings (v2.3)
- **Simplified Architecture**: Direct Qdrant integration only (v2.0 removed MCP backend)
- **Automatic incremental updates**: 15x faster processing of changed files (auto-detected)
- **Complete Orphaned Relation Cleanup**: Automatic cleanup for modified files in incremental mode
- **Real-time file watching**: Automatic indexing on code changes
- **Multi-project service**: Background watching for multiple projects
- **Git hooks integration**: Pre-commit automatic indexing
- **Project isolation**: Separate memory collections per project
- **Semantic search**: Find code by intent, not just keywords with progressive disclosure
- **Knowledge graphs**: Understands relationships between code components
- **Global wrapper**: Use `claude-indexer` from any directory
- **Zero Manual Steps**: Automatic loading eliminates copy-paste workflows
- **Smart Memory Clearing**: --clear preserves manual memories, --clear-all removes everything
- **Advanced Token Management**: Progressive disclosure with smart response sizing

## 🐛 Debugging Protocol

### Memory-First Debugging Workflow

**Step 1: Search Similar Patterns**
```bash
# Search project memory for similar error patterns
mcp__project-memory__search_similar("error pattern or symptom")

# Check logs and store new patterns discovered
claude-indexer --verbose  # Check application logs for errors/warnings
```

**Step 2: Understand Problem Context**
```bash
# Read project relationships to understand connections
mcp__project-memory__read_graph(mode="relationships", limit=300)

# Get entity overview for context
mcp__project-memory__read_graph(mode="smart", limit=100)

# Focus on specific entities
mcp__project-memory__read_graph(mode="entities", entityTypes=["class","function"], limit=200)
```

**Step 3: Semantic Scope Analysis**
```bash
# Find relevant entities first
mcp__project-memory__search_similar("authentication function")

# Get minimal implementation
mcp__project-memory__get_implementation("EntityName", "minimal")

# Get local context with helper functions
mcp__project-memory__get_implementation("EntityName", "logical")

# Trace cross-file dependencies and imports
mcp__project-memory__get_implementation("EntityName", "dependencies")
```

**Step 4: Root Cause Analysis**
- **Problem-focused approach**: Understand the exact error/problem with same parameters and context
- **Replicate first**: Ensure you can reproduce the issue before proposing fixes
- **Deep investigation**: Continue searching deeper until root cause is identified
- **Validation**: Don't fix until certain the solution addresses the exact problem

**Step 5: Solution Implementation**
- **Check for duplicates**: Verify no existing functions solve the problem ($dup)
- **Test implementation**: Run tests to ensure the specific problem is solved
- **Store solution patterns**: Add insights to project memory for future reference

### Debug Commands Reference

**Log Analysis:**
```bash
# Application logs location
{project_path}/logs/{collection_name}.log

# Monitor real-time logs
tail -f {project_path}/logs/{collection_name}.log

# Check service logs with verbose output
claude-indexer service status --verbose
```

**Memory Graph Functions:**
```bash
# Full relations view
read_graph(mode="relationships", limit=300)

# AI-optimized overview  
read_graph(mode="smart", limit=100)

# Entity-focused view
read_graph(mode="entities", entityTypes=["class","function"], limit=200)

# Raw data dump
read_graph(mode="raw", limit=50)
```

**Implementation Access:**
```bash
# Just the entity (default)
get_implementation("ClassName", "minimal")

# Entity + same-file helpers
get_implementation("ClassName", "logical") 

# Entity + imports/calls
get_implementation("ClassName", "dependencies")

# Find related entities
search_similar("pattern", limit=10)
```

**Debugging Best Practices:**
- Use separate test collections (watcher-test, debug-test) for debugging
- Test with 1-2 Python files only for cleaner debug output
- Never contaminate production memory collections during testing
- Store solution patterns and insights, not just bug information
- Use memory categorization: debugging_pattern, implementation_pattern, integration_pattern

> **💡 Tip for End Users**: Add this debugging protocol to your project's `CLAUDE.md` file so Claude automatically follows these steps during debugging sessions. This ensures consistent memory-first debugging across all your projects.

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

# Execute restore automatically via MCP (no manual steps)
python utils/backup_manual_entries.py restore -f manual_entries_backup_memory-project.json --execute

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
✅ **Comprehensive Test Suite** - 158/158 tests passing with 90%+ coverage
✅ **Modular Architecture** - Clean, pluggable components for enterprise scale
✅ **Manual Memory Protection** - Smart backup/restore for valuable insights
✅ **Dual Embedding Architecture** - 85% cost reduction with Voyage AI integration
✅ **Chat History Processing** - GPT-4.1-mini with 78% cost savings vs legacy models
✅ **Layer 2 Orphaned Relation Cleanup** - Automatic cleanup of broken relationships after entity deletion
# Test comment added at Thu Jun 26 21:34:06 CEST 2025
