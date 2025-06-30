# Claude Code Memory Solution

## Current Version: v2.7 - Entity-Specific Graph Filtering ✅ PRODUCTION READY

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

## 🏗️ NEW in v2.6 - Project Configuration System

### Project-Level Configuration

Each project can now have its own `.claude-indexer/config.json` for custom settings:

```json
{
  "indexing": {
    "file_patterns": {
      "include": ["*.py", "*.js", "*.ts", "*.json", "*.yaml", "*.html", "*.css"],
      "exclude": ["node_modules", ".git", "dist", "build", "*.min.js"]
    },
    "parser_config": {
      "javascript": {
        "use_ts_server": false,
        "jsx": true,
        "typescript": true
      },
      "json": {
        "extract_schema": true,
        "special_files": ["package.json", "tsconfig.json"]
      },
      "text": {
        "chunk_size": 50,
        "max_line_length": 1000
      }
    }
  }
}
```

**Configuration Hierarchy (Priority Order):**
1. Project Config (`.claude-indexer/config.json`) - Highest priority
2. Environment Variables - Override specific values
3. Global Config (`settings.txt`) - Default values
4. System Defaults - Minimal fallback

### Enhanced Python File Operations v2.6

**20+ New File Operation Patterns:**

```python
# Pandas operations (auto-detected)
df = pd.read_csv('sales_data.csv')        # Creates pandas_csv_read relation
df.to_json('output/results.json')        # Creates pandas_json_write relation
data = pd.read_excel('inventory.xlsx')    # Creates pandas_excel_read relation

# Pathlib operations
config = Path('config.txt').read_text()   # Creates path_read_text relation
Path('output.txt').write_text('results')  # Creates path_write_text relation

# Requests/API operations
data = requests.get('api/data.json')      # Creates requests_get relation
response = requests.post('upload.json')   # Creates requests_post relation

# Configuration files
config = configparser.ConfigParser()
config.read('settings.ini')              # Creates config_ini_read relation
settings = toml.load('pyproject.toml')   # Creates toml_read relation
```

**Semantic Relation Types:** All file operations create semantic relations with specific `import_type` values for precise search and dependency tracking.

## 🚀 Multi-Language Support (v2.5)

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

- **v2.6 Project Configuration System** with .claude-indexer/config.json support and hierarchy management
- **v2.6 Enhanced Python File Operations** with 20+ new patterns (pandas, pathlib, requests, config files)
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