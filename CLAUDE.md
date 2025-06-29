# Claude Code Memory Solution

## Current Version: v2.4 - Progressive Disclosure Architecture ✅ PRODUCTION READY

Complete memory solution for Claude Code providing context-aware conversations with semantic search across Python codebases.

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

# 4. Index any Python project (use -p and -c shortcuts for faster typing)
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

### Enhanced 7-Category System for Manual Entries

**Research-backed categorization with semantic content analysis:**

- **`debugging_pattern` (30% target)**: Error diagnosis, root cause analysis, troubleshooting
- **`implementation_pattern` (25% target)**: Coding solutions, algorithms, best practices  
- **`integration_pattern` (15% target)**: APIs, services, data pipelines, external systems
- **`configuration_pattern` (12% target)**: Environment setup, deployment, tooling
- **`architecture_pattern` (10% target)**: System design, structural decisions
- **`performance_pattern` (8% target)**: Optimization techniques, scalability
- **`knowledge_insight`**: Research findings, consolidated learnings, cross-cutting concerns

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

**Application Logs Location:**
- Project logs: `{project_path}/logs/{collection_name}.log`
- Service logs: `~/.claude-indexer/logs/` (fallback when no project path)

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

- **v2.4 Progressive Disclosure Architecture** and performance validation results
- **Enhanced MCP Server Features** with automatic provider detection
- **Voyage AI Integration** and cost optimization analysis
- **Advanced Automation Features** including file watching and service management  
- **Chat History Processing** with GPT-4.1-mini integration
- **Service Configuration** hierarchy and management patterns
- **Manual Memory Backup/Restore** system architecture
- **Debug Testing Protocol** with dedicated collections
- **Architecture Overview** and component integration
- **Logs and Debug Information** management system
- **Complete troubleshooting guides** for production deployment

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