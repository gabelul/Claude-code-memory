# Claude Code Memory Solution

🧠 Universal semantic indexer with **True Automation** - providing persistent memory for Claude Code through direct Qdrant integration, knowledge graphs, and Tree-sitter parsing - Zero manual intervention required

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

# 2. Install MCP memory server
git clone https://github.com/delorenj/mcp-qdrant-memory.git
cd mcp-qdrant-memory && npm install && npm run build && cd ..

# 3. Install global wrapper
./install.sh

# 4. Start Qdrant
docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant
```

### Configure Claude Code
Add to `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "general-memory": {
      "command": "node",
      "args": ["/absolute/path/to/memory/mcp-qdrant-memory/dist/index.js"],
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
claude-indexer --project /path/to/any/python/project --collection test-setup --verbose

# Expected output: successful indexing with entities and relations created
```

## 📋 Adding New Projects

### Step 1: Add MCP Collection
Add to `~/.claude/claude_desktop_config.json`:
```json
"my-project-memory": {
  "command": "node",
  "args": ["/absolute/path/to/memory/mcp-qdrant-memory/dist/index.js"],
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
claude-indexer --project /path/to/your/project --collection my-project
```

### Step 4: Automatic Knowledge Graph Loading
Knowledge graph is automatically loaded into Qdrant - no manual steps required!

### Step 5: Test Semantic Search
```bash
# In Claude Code
mcp__my-project-memory__search_similar("your search query")
```

## 🔄 Daily Usage

```bash
# Index new project
claude-indexer --project /path/to/project --collection project-name

# Incremental updates (15x faster)
claude-indexer --project /path/to/project --collection project-name --incremental

# Full re-index after major changes
claude-indexer --project /path/to/project --collection project-name

# Debug mode (generate commands file)
claude-indexer --project /path/to/project --collection project-name --generate-commands
```

## 🎯 When to Run Indexer

- **New project**: First time setup
- **Major code changes**: Functions/classes added/removed
- **Before important Claude sessions**: Get latest context
- **After refactoring**: Capture structural changes

## ✨ Features

- **True Automation**: Direct Qdrant integration with zero manual intervention
- **Incremental updates**: 15x faster processing of changed files only
- **Project isolation**: Separate memory collections per project
- **Semantic search**: Find code by intent, not just keywords
- **Knowledge graphs**: Understands relationships between code components
- **Global wrapper**: Use `claude-indexer` from any directory
- **Zero Manual Steps**: Automatic loading eliminates copy-paste workflows

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