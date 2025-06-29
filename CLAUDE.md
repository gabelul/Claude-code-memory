# Claude Code Memory Solution

## Current Version: v2.5 - Enhanced Multi-Language Support ✅ PRODUCTION READY

Complete memory solution for Claude Code providing context-aware conversations with semantic search across **10+ programming languages** with universal Tree-sitter parsing.

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
- Verify target directory contains supported files (Python, JavaScript, TypeScript, JSON, HTML, CSS, YAML, etc.)
- Use `--verbose` flag for detailed error messages

## 🚀 Multi-Language Support (v2.5) - NEW!

### Supported Languages & File Types

**Complete Web Stack Coverage (24 file extensions):**

- **JavaScript/TypeScript**: `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`
  - Functions, classes, interfaces, imports
  - Arrow functions, method definitions
  - Progressive disclosure with metadata/implementation chunks

- **Configuration Files**: `.json`, `.yaml`, `.yml`, `.ini`
  - JSON: Special handling for `package.json`, `tsconfig.json`
  - YAML: Smart type detection (GitHub workflows, Docker Compose, Kubernetes)
  - NPM dependency relations, workflow/job extraction

- **Web Technologies**: `.html`, `.css`
  - HTML: Components, elements with IDs, class references
  - CSS: Selectors, variables, @import relations
  - Cross-language HTML→CSS relations

- **Text & Data**: `.txt`, `.log`, `.csv`, `.md`
  - Configurable text chunking
  - CSV column detection, Markdown structure
  - Log file processing for debugging

- **Python**: `.py` (existing enhanced support)
  - Functions, classes, imports with Jedi semantic analysis
  - Full progressive disclosure architecture

### Basic Flows & Architecture

**1. Universal Parser Registry**
```python
# Automatic file-to-parser matching
ParserRegistry.get_parser(file_path) → appropriate TreeSitterParser
```

**2. Tree-sitter Foundation**
```python
# Unified AST parsing across all languages
TreeSitterParser.parse_tree(content) → consistent entity extraction
```

**3. Progressive Disclosure (Maintained)**
```python
# Metadata chunk (fast search)
EntityChunk(chunk_type="metadata", content=signature)
# Implementation chunk (on-demand)  
EntityChunk(chunk_type="implementation", content=full_code)
```

**4. Cross-Language Relations**
```python
# HTML file imports CSS
RelationFactory.create_imports_relation("style.css", import_type="stylesheet")
# JavaScript imports from package.json
RelationFactory.create_imports_relation("lodash", import_type="npm_dependency")
```

### Performance Results

**Validated Multi-Language Processing:**
- **7 test files** processed in **0.40 seconds**
- **49 entities** + **78 relations** extracted
- **100% parser detection** accuracy
- **Zero breaking changes** to existing Python/Markdown functionality

### Implementation Details

**Core Components:**
- `base_parsers.py`: TreeSitterParser foundation with unified language initialization
- `javascript_parser.py`: JS/TS with function/class/interface extraction
- `json_parser.py`: Configuration parsing with special file handling
- `html_parser.py`: Component detection and CSS relation extraction
- `css_parser.py`: Selector parsing with @import relation detection
- `yaml_parser.py`: Smart type detection for workflows/compose/k8s
- `text_parser.py`: Configurable chunking for text/CSV/INI files

**Key Benefits:**
- **Zero Configuration**: Automatic parser selection based on file extensions
- **Consistent Entity Models**: Same Entity/Relation/Chunk patterns across all languages
- **MCP Compatibility**: Full integration with existing MCP server and progressive disclosure
- **Extensible Architecture**: Easy addition of new languages via TreeSitterParser base class

## Advanced Details → Use §m to search project memory for:

- **v2.5 Enhanced Multi-Language Support** with Tree-sitter universal parsing and web stack coverage
- **Universal Parser Registry** implementation and extensible architecture patterns
- **Cross-Language Relations** detection and HTML→CSS, JS→JSON dependency tracking
- **Tree-sitter Integration** technical details and language initialization patterns
- **v2.4.1 Semantic Scope Enhancement** with contextual code retrieval implementation
- **v2.4 Progressive Disclosure Architecture** and performance validation results
- **Enhanced MCP Server Features** with automatic provider detection and scope control
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