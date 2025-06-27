# Claude Code Memory Solution

## Current Version: v2.2 - Layer 2 Orphaned Relation Cleanup

Complete memory solution for Claude Code providing context-aware conversations with semantic search across Python codebases.

- 🧹 Automatic orphaned relation cleanup after entity deletion
- 📊 158/158 tests passing, production-ready
- ⚡ 15x faster incremental mode (auto-detected)
- ✨ Smart token management (<25k tokens vs 393k overflow)

→ **Use §m to search project memory for:** version history, breaking changes, detailed changelogs

## Quick Start

```bash
# 1. Setup environment
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure settings.txt with API keys
cp settings.template.txt settings.txt
# Edit with your OpenAI and Qdrant API keys

# 3. Install global wrapper
./install.sh

# 4. Index any Python project (use -p and -c shortcuts for faster typing)
claude-indexer -p /path/to/project -c project-name
```

## Core Usage

### Direct Qdrant Integration

```bash
# Auto-detects: First run = Full mode, subsequent runs = Incremental mode (15x faster)
claude-indexer -p /path -c name

# Clear collection (preserves manually added memories)
claude-indexer -p /path -c name --clear

# Clear entire collection (deletes all memories including manual)
claude-indexer -p /path -c name --clear-all
```

### Advanced Automation Features

#### Real-time File Watching
```bash
# Single project file watching with custom debounce
claude-indexer watch start -p /path -c name --debounce 3.0
```

#### Background Service Management
```bash
# Start multi-project background service
claude-indexer service start

# Add projects to service watch list
claude-indexer service add-project /path/to/project project-collection-name

# Check service status and active watchers
claude-indexer service status
```

#### Git Hooks Integration
```bash
# Install pre-commit automatic indexing
claude-indexer hooks install -p /path -c name

# Check hook status
claude-indexer hooks status -p /path -c name
```

#### Search and Discovery
```bash
# Semantic search across indexed collections
claude-indexer search "authentication function" -p /path -c name

# Filter by entity type
claude-indexer search "database connection" -p /path -c name --type entity
```

## Memory Integration

### Enhanced 7-Category System for Manual Entries

**Research-backed categorization with semantic content analysis:**

- **`debugging_pattern` (30% target)**: Error diagnosis, root cause analysis, troubleshooting
  - *Indicators*: "error", "exception", "memory leak", "root cause", "debug", "traceback", "stack trace"
  - *Content*: Error messages, troubleshooting steps, performance issues, exception handling

- **`implementation_pattern` (25% target)**: Coding solutions, algorithms, best practices  
  - *Indicators*: "class", "function", "algorithm", "pattern", "best practice", "code", "solution"
  - *Content*: Code examples, design patterns, development techniques, testing strategies

- **`integration_pattern` (15% target)**: APIs, services, data pipelines, external systems
  - *Indicators*: "API", "service", "integration", "database", "authentication", "pipeline" 
  - *Content*: External service connections, data flows, authentication patterns

- **`configuration_pattern` (12% target)**: Environment setup, deployment, tooling
  - *Indicators*: "config", "environment", "deploy", "setup", "docker", "CI/CD", "install"
  - *Content*: Environment configuration, deployment workflows, tool setup

- **`architecture_pattern` (10% target)**: System design, structural decisions
  - *Indicators*: "architecture", "design", "structure", "component", "system", "module"
  - *Content*: High-level design decisions, component organization, system structure

- **`performance_pattern` (8% target)**: Optimization techniques, scalability
  - *Indicators*: "performance", "optimization", "scalability", "memory", "speed", "bottleneck"
  - *Content*: Performance tuning, resource optimization, scalability patterns

- **`knowledge_insight`**: Research findings, consolidated learnings, cross-cutting concerns
  - *Content*: Strategic insights, lessons learned, research findings, methodology improvements

**Classification Approach**: Analyze content semantics, not format. Identify 3 strongest indicators, then categorize based on actual problem domain rather than documentation style.

## MCP Server Setup

**Option 1: Automated Script (Easiest)**
```bash
# Quick setup using your settings.txt - reads API keys automatically
python add_mcp_project.py project-name
python add_mcp_project.py general  # for general memory
```

**Option 2: Command Line**
```bash
# Add project-specific memory
claude mcp add project-memory -e OPENAI_API_KEY="YOUR_KEY" -e QDRANT_API_KEY="YOUR_KEY" -e QDRANT_URL="http://localhost:6333" -e QDRANT_COLLECTION_NAME="project-name" -- node "/path/to/memory/mcp-qdrant-memory/dist/index.js"
```

**Option 3: Manual JSON Configuration (`~/.claude/claude_desktop_config.json`)**
→ See full JSON example in project memory (search: "MCP JSON configuration")

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Code   │◄──►│  MCP Server      │◄──►│   Qdrant DB     │
│                 │    │  (delorenj)      │    │   (Vectors)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        ▲
                       ┌────────────────┐               │
                       │ Universal      │               │ Direct
                       │ Indexer        │───────────────┘ Automation
                       │ (claude_indexer)│
                       └────────────────┘
                                │
                       ┌────────▼────────┐
                       │  Tree-sitter +  │
                       │      Jedi       │
                       │  (Code Analysis)│
                       └─────────────────┘
```

## Key Features

- 🏗️ Modular `claude_indexer` package architecture
- 📊 Knowledge graph with entities & relations
- ⚡ Tree-sitter + Jedi parsing (36x faster)
- 🔄 Direct Qdrant integration (zero manual steps)
- 📁 Project-specific collections for isolation
- 🛡️ Smart clearing: --clear vs --clear-all
- 💾 Manual Memory Protection system

## Service Configuration

### Configuration Hierarchy
1. Runtime CLI overrides (highest priority)
2. Service configuration file (~/.claude-indexer/config.json)
3. Project settings (settings.txt)
4. Built-in defaults (lowest priority)

### Service Configuration Example
```json
{
  "projects": [
    {
      "path": "/home/dev/project",
      "collection": "project-memory",
      "watch_enabled": true
    }
  ],
  "settings": {
    "debounce_seconds": 2.5,
    "watch_patterns": ["*.py", "*.md", "*.js"],
    "ignore_patterns": ["*.pyc", "__pycache__", "node_modules"],
    "max_file_size": 2097152,
    "enable_logging": true
  }
}
```

## Basic Troubleshooting

**Qdrant Connection Failed:**
- Ensure Qdrant is running on port 6333
- Check firewall settings
- Verify API key matches

**MCP Server Not Loading:**
- Restart Claude Code after config changes
- Check absolute paths in MCP configuration

**No Entities Created:**
- Verify target directory contains Python files
- Use `--verbose` flag for detailed error messages

## Advanced Details → Use §m to search project memory for:

- **Performance benchmarks** and optimization results
- **Test suite architecture** and coverage details
- **Orphaned relation cleanup** algorithm implementation
- **Manual memory backup/restore** system details
- **Detailed troubleshooting** scenarios
- **Success metrics** and validation results
- **Implementation patterns** and architecture decisions

## Benefits Summary

- **Automatic Context**: Claude knows your entire project structure
- **Semantic Search**: Find code by intent, not just keywords
- **Cross-Session Memory**: Persistent understanding across sessions
- **True Automation**: Zero manual intervention required
- **Pattern Recognition**: Learns coding patterns and preferences
- **Dependency Tracking**: Understands impact of changes

## Prerequisites

- Python 3.12+ installed
- Node.js 18+ for MCP server
- Git for version control
- Claude Code installed and configured
- Qdrant running (Docker or local)

---

The combination of delorenj/mcp-qdrant-memory + Tree-sitter + Jedi + advanced automation provides enterprise-grade memory capabilities for Claude Code while remaining accessible for individual developers and teams.