# Claude Code Memory Solution

**🚨 ACTIVE ISSUES: To check current active issues, use:** `mcp__claude-memory-test-memory__read_graph(entityTypes=["active_issue"], mode="entities", limit=20)` or search with `active_issue` category.

**🧪 TESTING: For running tests, use `test-relations-full-memory` MCP. Always use `mcp__test-relations-full-memory__` prefix for test operations.**

**🔧 MCP DEBUG: For debugging the MCP server used in Claude Code, use `mcp-debug-memory` MCP. Always use `mcp__mcp-debug-memory__` prefix for MCP server debugging operations (troubleshooting vectorization, MCP functionality issues).**

**⚠️ IMPORTANT: This project uses `claude-memory-test` as its memory collection/database. Always use `mcp__claude-memory-test-memory__` prefix for all memory operations (search, read_graph, etc.) when working on this project.**

## Current Version: v2.7.1 - Project-Local State Files ✅ PRODUCTION READY

Complete memory solution for Claude Code providing context-aware conversations with semantic search across **10+ programming languages** with universal Tree-sitter parsing, enhanced Python file operations, and project-level configuration.

→ **Use §m to search project memory for:** implementation details, performance results, migration guides

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

# 4. Index any multi-language project (use -p and -c shortcuts for faster typing)
claude-indexer -p /path/to/project -c project-name
```

## Core Usage

### Embedding Provider Configuration

**Voyage AI (Recommended - 85% cost reduction):**
```bash
# Add to settings.txt
VOYAGE_API_KEY=your_voyage_key
EMBEDDING_PROVIDER=voyage
EMBEDDING_MODEL=voyage-3-lite  # or voyage-3
```

**OpenAI (Default):**
```bash
# Add to settings.txt  
OPENAI_API_KEY=your_openai_key
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

### Direct Qdrant Integration

```bash
# Auto-detects: First run = Full mode, subsequent runs = Incremental mode (15x faster)
claude-indexer -p /path -c name

# Clear collection (preserves manually added memories)
claude-indexer -p /path -c name --clear

# Clear entire collection (deletes all memories including manual)
claude-indexer -p /path -c name --clear-all
```

### Essential Commands

#### MCP Server Setup  
```bash
# Add MCP server configuration with automatic Voyage AI integration
claude-indexer add-mcp -c project-name
claude-indexer add-mcp -c general  # for general memory
```

#### File Watching & Services
```bash
# Real-time file watching
claude-indexer watch start -p /path -c name --debounce 3.0

# Background service management
claude-indexer service start
claude-indexer service add-project /path/to/project project-collection-name
```

#### Search & Discovery
```bash
# Semantic search across indexed collections
claude-indexer search "authentication function" -p /path -c name
claude-indexer search "database connection" -p /path -c name --type entity
```

## Memory Integration

### Enhanced 8-Category System for Manual Entries

**Research-backed categorization with semantic content analysis:**

- **`debugging_pattern` (30% target)**: Error diagnosis, root cause analysis, troubleshooting
- **`implementation_pattern` (25% target)**: Coding solutions, algorithms, best practices  
- **`integration_pattern` (15% target)**: APIs, databases, authentication, pipelines
- **`configuration_pattern` (12% target)**: Environment setup, deployment, CI/CD
- **`architecture_pattern` (10% target)**: System design, component structure
- **`performance_pattern` (8% target)**: Optimization, caching, bottlenecks
- **`knowledge_insight`**: Research findings, lessons learned, methodology
- **`active_issue`**: Current bugs/problems requiring attention (delete when fixed)

**Classification Approach**: Analyze content semantics, not format. Identify 3 strongest indicators, then categorize based on actual problem domain rather than documentation style.

## MCP Server Setup

**Option 1: Built-in CLI Command (Recommended)**
```bash
# Add MCP server using integrated command - reads API keys from settings.txt
claude-indexer add-mcp -c project-name
claude-indexer add-mcp -c general  # for general memory
```

**Option 2: Manual Command Line**
```bash
# Add project-specific memory manually
claude mcp add project-memory -e OPENAI_API_KEY="YOUR_KEY" -e QDRANT_API_KEY="YOUR_KEY" -e QDRANT_URL="http://localhost:6333" -e QDRANT_COLLECTION_NAME="project-name" -- node "/path/to/memory/mcp-qdrant-memory/dist/index.js"
```

## Debug Testing Protocol

**Testing Database - watcher-test Collection:**
```bash
# Use dedicated test collection for all debugging (never use production DB)
claude-indexer index -p /path/to/test-files -c watcher-test --verbose
```

**Testing Best Practices:**
- Always use separate test collections (watcher-test, debug-test) for debugging
- Use 1-2 Python files only for cleaner debug output  
- Never contaminate production memory collections during testing
- Test indexing, relations, file processing, incremental updates, parser functionality
- MCP server already configured for watcher-test collection

## Manual Memory Backup & Restore

Protect your valuable manual memories (analysis notes, insights, patterns):

```bash
# Backup all manual entries from a collection
python utils/manual_memory_backup.py backup -c collection-name

# Generate MCP restore commands for manual entries
python utils/manual_memory_backup.py restore -f manual_entries_backup_collection-name.json

# Execute restore automatically via MCP (no manual steps)
python utils/manual_memory_backup.py restore -f manual_entries_backup_collection-name.json --execute

# Dry run to see what would be restored
python utils/manual_memory_backup.py restore -f backup.json --dry-run
```

## Logs and Debug Information

**Project File Organization:**
- **State files**: `{project_path}/.claude-indexer/{collection_name}.json` (tracks incremental indexing metadata)
- **Project logs**: `{project_path}/logs/{collection_name}.log`
- **Project config**: `{project_path}/.claude-indexer/config.json` (optional project-specific settings)
- **Service logs**: `~/.claude-indexer/logs/` (fallback when no project path)
- **Service config**: `~/.claude-indexer/config.json` (global service configuration)

**Debug Commands:**
```bash
# Enable verbose logging for troubleshooting
claude-indexer -p /path -c name --verbose

# Check service status with detailed logs
claude-indexer service status --verbose

# Monitor real-time logs during operation
tail -f {project_path}/logs/{collection_name}.log

# For testing relation formats and orphan cleanup - use small test directory
claude-indexer -p /path/to/small-test-dir -c debug-test --verbose
# Recommended: 1-2 Python files only for cleaner debug output
```

## 🎯 Entity-Specific Graph Filtering (NEW in v2.7)

**Focus on specific entities instead of browsing entire project graphs:**

```python
# Focus on specific function's dependencies and usage
read_graph(entity="AuthService", mode="smart")
# Returns: AI summary of AuthService's connections, dependencies, usage

# See all relationships for a specific entity  
read_graph(entity="process_login", mode="relationships") 
# Returns: Only relations involving process_login (incoming/outgoing)

# Get entities connected to a specific component
read_graph(entity="validate_token", mode="entities")
# Returns: All entities that connect to validate_token

# Raw data for a specific entity's network
read_graph(entity="DatabaseManager", mode="raw")
# Returns: Complete entities + relations for DatabaseManager's network
```

**Common Debugging Workflows:**
```python
# 1. Debug specific function
search_similar("authentication error")                    # Find problematic function
read_graph(entity="validate_token", mode="smart")         # See its context  
get_implementation("validate_token", scope="dependencies") # Get full code

# 2. Understand class architecture
read_graph(entity="UserService", mode="smart")
# Shows: inheritance, methods, dependencies, usage patterns

# 3. Trace error sources
read_graph(entity="handle_request", mode="relationships")
# Shows: what calls it, what it calls, error propagation paths
```

**Performance Benefits:**
- **10-20 focused relations** instead of 300+ scattered ones
- **Smart entity summaries** with key statistics and relationship breakdown  
- **Laser-focused debugging** without information overload
- **Backward compatible** - general graph still works without entity parameter

## Basic Troubleshooting

**Qdrant Connection Failed:**
- Ensure Qdrant is running on port 6333
- Check firewall settings
- Verify API key matches

**MCP Server Not Loading:**
- Restart Claude Code after config changes
- Check absolute paths in MCP configuration

**No Entities Created:**
- Verify target directory contains supported files (Python, JavaScript, TypeScript, JSON, HTML, CSS, YAML, etc.)
- Use `--verbose` flag for detailed error messages

## Multi-Language & Configuration Support

**Supported Languages:** Python, JavaScript/TypeScript, JSON, YAML, HTML, CSS, Text files (24 extensions total)

**Project Configuration:** Use `.claude-indexer/config.json` for project-specific settings

→ **Use §m to search project memory for:** technical specs, parser details, configuration examples

## Advanced Details → Use §m to search project memory for:

- **Multi-language support technical specs** and parser implementation details
- **Configuration system patterns** and hierarchy management
- **Version history and migration guides** (v2.4-v2.7)
- **Performance validation results** and optimization analysis
- **Architecture evolution notes** and component integration

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