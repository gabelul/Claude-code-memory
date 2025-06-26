# Project-Level File Pattern Configuration Plan

## Overview
Enable per-project configuration of file types to watch and index, specifically adding support for JavaScript (.js) and text (.txt) files as requested. Each project can independently choose which file types to include, with all settings stored locally in `PROJECT_DIR/.claude-indexer/config.json` for complete project isolation and portability.

## Architecture: Project-Local Configuration

### New Architecture
- Project config: `PROJECT_DIR/.claude-indexer/config.json`
- State file: `PROJECT_DIR/.claude-indexer/state.json`
- Each project self-contained with its own settings
- No global configuration dependencies

### Benefits
1. **Version Control**: Configuration committed with code
2. **Team Collaboration**: Shared settings across team members
3. **Project Portability**: Move/copy projects with all settings intact
4. **Isolation**: No cross-project configuration conflicts
5. **Simplicity**: Settings next to code they configure
6. **Project Choice**: Each project independently decides which file types to index

## Current State Analysis

### Files to Update
1. **claude_indexer/config.py**
   - Remove hardcoded patterns
   - Remove global config references

2. **claude_indexer/watcher/handler.py**
   - Remove hardcoded watch patterns
   - Load from project config

3. **claude_indexer/service.py**
   - Remove global config path
   - Implement project discovery

4. **claude_indexer/indexer.py**
   - Change state file location
   - Remove centralized state management

5. **claude_indexer/analysis/parser.py**
   - Keep parser registry
   - Add new parsers

## Implementation Plan

### Phase 1: Project Configuration Structure

#### 1.1 Project Directory Structure
```
my-project/
├── src/                    # Project source code
├── tests/                  # Project tests
├── .claude-indexer/        # Claude indexer configuration
│   ├── config.json         # Project-specific settings
│   ├── state.json          # Indexing state
│   └── logs/               # Project-specific logs (optional)
└── README.md
```

#### 1.2 Project Configuration Schema
**Location**: `PROJECT_DIR/.claude-indexer/config.json`
```json
{
  "version": "2.0",
  "project": {
    "name": "my-project",
    "collection": "my-project-memory",
    "description": "Project description for context"
  },
  "indexing": {
    "enabled": true,
    "incremental": true,
    "file_patterns": {
      "include": ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.md", "*.txt"],
      "exclude": ["*.pyc", "__pycache__", "node_modules", ".git", "dist", "build", ".venv"]
    },
    "max_file_size": 1048576,
    "parser_config": {
      "javascript": {
        "ecma_version": "latest",
        "jsx": true,
        "typescript": true
      },
      "text": {
        "max_line_length": 1000,
        "encoding": "utf-8"
      }
    }
  },
  "watcher": {
    "enabled": true,
    "debounce_seconds": 2.0
  },
  "git_hooks": {
    "pre_commit": {
      "enabled": false,
      "fail_on_error": false
    }
  },
  "api_keys": {
    "use_global": true,  // Use settings.txt from project root
    "openai_api_key": null,  // Override if needed
    "qdrant_api_key": null,
    "qdrant_url": null
  }
}
```

#### 1.3 Example Project Configurations

**Python Project** (.claude-indexer/config.json):
```json
{
  "project": {
    "name": "my-python-app",
    "collection": "python-app-memory"
  },
  "indexing": {
    "file_patterns": {
      "include": ["*.py", "*.pyi", "*.md"],
      "exclude": ["*.pyc", "__pycache__", ".venv"]
    }
  }
}
```

**JavaScript Project** (.claude-indexer/config.json):
```json
{
  "project": {
    "name": "my-js-app",
    "collection": "js-app-memory"
  },
  "indexing": {
    "file_patterns": {
      "include": ["*.js", "*.jsx", "*.ts", "*.tsx", "*.json", "*.md"],
      "exclude": ["node_modules", "dist", "build", "*.min.js"]
    }
  }
}
```

**Mixed Project with Logs** (.claude-indexer/config.json):
```json
{
  "project": {
    "name": "full-stack-app",
    "collection": "fullstack-memory"
  },
  "indexing": {
    "file_patterns": {
      "include": ["*.py", "*.js", "*.txt", "*.log", "*.md", "*.yaml"],
      "exclude": ["*.pyc", "node_modules", "logs/archive", ".git"]
    }
  }
}
```

#### 1.4 Project Registry for Service
**Location**: `~/.claude-indexer/projects.json`
```json
{
  "version": "2.0",
  "projects": [
    {
      "path": "/absolute/path/to/project1",
      "name": "project1",
      "active": true
    },
    {
      "path": "/absolute/path/to/project2", 
      "name": "project2",
      "active": true
    }
  ]
}
```

### Phase 2: Core Components

#### 2.1 Project Configuration Manager
**File**: `claude_indexer/project_config.py`
```python
from pathlib import Path
import json
from typing import Dict, Any, Optional

class ProjectConfig:
    """Manages project-local configuration."""
    
    CONFIG_DIR = '.claude-indexer'
    CONFIG_FILE = 'config.json'
    STATE_FILE = 'state.json'
    
    def __init__(self, project_path: Path):
        self.project_path = Path(project_path).resolve()
        self.config_dir = self.project_path / self.CONFIG_DIR
        self.config_file = self.config_dir / self.CONFIG_FILE
        self.state_file = self.config_dir / self.STATE_FILE
        
    def exists(self) -> bool:
        """Check if project config exists."""
        return self.config_file.exists()
        
    def load(self) -> Dict[str, Any]:
        """Load project configuration."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"No config found at {self.config_file}")
            
        with open(self.config_file) as f:
            return json.load(f)
            
    def save(self, config: Dict[str, Any]) -> None:
        """Save project configuration."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
    def initialize(self, name: Optional[str] = None, 
                  collection: Optional[str] = None) -> None:
        """Initialize new project with config."""
        if self.config_file.exists():
            raise ValueError("Project already initialized")
            
        project_name = name or self.project_path.name
        collection_name = collection or f"{project_name}-memory"
        
        default_config = {
            "version": "2.0",
            "project": {
                "name": project_name,
                "collection": collection_name,
                "description": ""
            },
            "indexing": {
                "enabled": True,
                "incremental": True,
                "file_patterns": {
                    "include": ["*.py", "*.md"],
                    "exclude": ["*.pyc", "__pycache__", ".git", ".venv", "node_modules"]
                },
                "max_file_size": 1048576
            },
            "watcher": {
                "enabled": True,
                "debounce_seconds": 2.0
            },
            "api_keys": {
                "use_global": True
            }
        }
        
        self.save(default_config)
        
    def get_file_patterns(self) -> Dict[str, list]:
        """Get file patterns from config."""
        config = self.load()
        return config['indexing']['file_patterns']
        
    def get_parser_config(self, parser_type: str) -> Dict[str, Any]:
        """Get parser-specific configuration."""
        config = self.load()
        parser_configs = config['indexing'].get('parser_config', {})
        return parser_configs.get(parser_type, {})
```

#### 2.2 JavaScript Parser
**File**: `claude_indexer/analysis/javascript_parser.py`
```python
from pathlib import Path
from typing import List, Dict, Any
from tree_sitter import Parser, Node
import tree_sitter_javascript as tjs
from ..entities import Entity, Relation
from .base import BaseParser, ParsedFile

class JavaScriptParser(BaseParser):
    """Parse JavaScript/TypeScript files using tree-sitter."""
    
    SUPPORTED_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.parser = Parser()
        self.parser.set_language(tjs.language)
        
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        return file_path.suffix in self.SUPPORTED_EXTENSIONS
        
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return self.SUPPORTED_EXTENSIONS
        
    def parse(self, file_path: Path, content: str) -> ParsedFile:
        """Parse JavaScript/TypeScript file content."""
        tree = self.parser.parse(bytes(content, "utf8"))
        
        entities = []
        relations = []
        
        # Extract functions
        for node in self._find_nodes(tree.root_node, ['function_declaration', 
                                                      'arrow_function', 
                                                      'function_expression']):
            entity = self._create_function_entity(node, file_path)
            if entity:
                entities.append(entity)
                
        # Extract classes
        for node in self._find_nodes(tree.root_node, ['class_declaration']):
            entity = self._create_class_entity(node, file_path)
            if entity:
                entities.append(entity)
                
        # Extract imports
        for node in self._find_nodes(tree.root_node, ['import_statement']):
            relation = self._create_import_relation(node, file_path)
            if relation:
                relations.append(relation)
                
        return ParsedFile(
            file_path=file_path,
            entities=entities,
            relations=relations,
            language="javascript"
        )
        
    def _find_nodes(self, root: Node, node_types: List[str]) -> List[Node]:
        """Find all nodes of given types."""
        nodes = []
        
        def walk(node: Node):
            if node.type in node_types:
                nodes.append(node)
            for child in node.children:
                walk(child)
                
        walk(root)
        return nodes
        
    def _create_function_entity(self, node: Node, file_path: Path) -> Entity:
        """Create function entity from AST node."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
            
        return Entity(
            name=name_node.text.decode('utf8'),
            type='function',
            file_path=str(file_path),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            content=node.text.decode('utf8')[:200]
        )
```

#### 2.3 Text Parser
**File**: `claude_indexer/analysis/text_parser.py`
```python
from pathlib import Path
from typing import List, Dict, Any
from ..entities import Entity
from .base import BaseParser, ParsedFile

class TextParser(BaseParser):
    """Parse plain text files with configurable chunking."""
    
    SUPPORTED_EXTENSIONS = ['.txt', '.log', '.csv', '.dat', '.conf', '.ini']
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        return file_path.suffix in self.SUPPORTED_EXTENSIONS
        
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return self.SUPPORTED_EXTENSIONS
        
    def parse(self, file_path: Path, content: str) -> ParsedFile:
        """Parse text file into searchable chunks."""
        max_line_length = self.config.get('max_line_length', 500)
        chunk_size = self.config.get('chunk_size', 50)  # lines per chunk
        
        lines = content.splitlines()
        entities = []
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            chunk_text = '\n'.join(line[:max_line_length] for line in chunk_lines)
            
            if chunk_text.strip():
                entities.append(Entity(
                    name=f"{file_path.stem}_chunk_{i//chunk_size + 1}",
                    type="text_chunk",
                    file_path=str(file_path),
                    line_start=i + 1,
                    line_end=min(i + chunk_size, len(lines)),
                    content=chunk_text
                ))
                
        return ParsedFile(
            file_path=file_path,
            entities=entities,
            relations=[],
            language="text"
        )
```

### Phase 3: Update Core Services

#### 3.1 Update Indexer
**File**: `claude_indexer/indexer.py` (key changes)
```python
class Indexer:
    def __init__(self, project_path: str, *args, **kwargs):
        self.project_path = Path(project_path).resolve()
        self.project_config = ProjectConfig(self.project_path)
        
        if not self.project_config.exists():
            raise ValueError(f"Project not initialized. Run 'claude-indexer init' in {project_path}")
            
        self.config = self.project_config.load()
        self.collection = self.config['project']['collection']
        self.file_patterns = self.config['indexing']['file_patterns']
        
        # Initialize other components...
        
    def _get_state_file(self) -> Path:
        """Get project-local state file."""
        return self.project_config.state_file
        
    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file matches project patterns."""
        relative_path = file_path.relative_to(self.project_path)
        path_str = str(relative_path)
        
        # Check excludes first
        for pattern in self.file_patterns['exclude']:
            if fnmatch.fnmatch(path_str, pattern):
                return False
                
        # Check includes
        for pattern in self.file_patterns['include']:
            if fnmatch.fnmatch(path_str, pattern):
                return True
                
        return False
```

#### 3.2 Update Service
**File**: `claude_indexer/service.py` (key changes)
```python
class IndexingService:
    """Service to manage multiple project watchers."""
    
    PROJECTS_REGISTRY = Path.home() / '.claude-indexer' / 'projects.json'
    
    def __init__(self):
        self.projects = {}
        self.observers = {}
        
    def load_registry(self) -> Dict[str, Any]:
        """Load projects registry."""
        if not self.PROJECTS_REGISTRY.exists():
            return {"version": "2.0", "projects": []}
            
        with open(self.PROJECTS_REGISTRY) as f:
            return json.load(f)
            
    def save_registry(self, registry: Dict[str, Any]) -> None:
        """Save projects registry."""
        self.PROJECTS_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.PROJECTS_REGISTRY, 'w') as f:
            json.dump(registry, f, indent=2)
            
    def register_project(self, project_path: Path) -> None:
        """Register a project for service management."""
        registry = self.load_registry()
        
        project_entry = {
            "path": str(project_path.resolve()),
            "name": project_path.name,
            "active": True
        }
        
        # Check if already exists
        for i, proj in enumerate(registry['projects']):
            if proj['path'] == project_entry['path']:
                registry['projects'][i] = project_entry
                self.save_registry(registry)
                return
                
        registry['projects'].append(project_entry)
        self.save_registry(registry)
        
    def start_project_watcher(self, project_path: Path) -> None:
        """Start watching a specific project."""
        project_config = ProjectConfig(project_path)
        if not project_config.exists():
            logger.warning(f"Project {project_path} not initialized, skipping")
            return
            
        config = project_config.load()
        if not config['watcher']['enabled']:
            logger.info(f"Watcher disabled for {project_path}")
            return
            
        # Start file watcher for this project
        # Implementation continues...
```

#### 3.3 Update Parser Registry
**File**: `claude_indexer/analysis/parser.py` (additions)
```python
# Import new parsers
from .javascript_parser import JavaScriptParser
from .text_parser import TextParser

class ParserRegistry:
    """Registry for file parsers."""
    
    def __init__(self):
        self._parsers = []
        self._register_default_parsers()
        
    def _register_default_parsers(self):
        """Register all default parsers."""
        self.register(PythonParser())
        self.register(MarkdownParser())
        self.register(JavaScriptParser())
        self.register(TextParser())
        
    def register(self, parser: BaseParser):
        """Register a parser."""
        self._parsers.append(parser)
        
    def get_parser(self, file_path: Path, config: Dict[str, Any] = None) -> BaseParser:
        """Get appropriate parser for file."""
        for parser in self._parsers:
            if parser.can_parse(file_path):
                if config:
                    parser.config = config
                return parser
        return None
```

### Phase 4: CLI Commands

#### 4.1 Initialize Command
```python
@app.command()
def init(
    name: Optional[str] = typer.Option(None, help="Project name"),
    collection: Optional[str] = typer.Option(None, help="Collection name")
):
    """Initialize Claude indexer in current directory."""
    project_path = Path.cwd()
    project_config = ProjectConfig(project_path)
    
    if project_config.exists():
        typer.echo("Project already initialized")
        raise typer.Exit(1)
        
    project_config.initialize(name=name, collection=collection)
    typer.echo(f"✅ Initialized project at {project_config.config_file}")
```

#### 4.2 Index Command
```python
@app.command()
def index(
    project_path: Optional[str] = typer.Argument(None, help="Project path"),
    incremental: bool = typer.Option(True, help="Use incremental indexing"),
    clear: bool = typer.Option(False, help="Clear collection first")
):
    """Index project files."""
    path = Path(project_path) if project_path else Path.cwd()
    project_config = ProjectConfig(path)
    
    if not project_config.exists():
        typer.echo(f"Project not initialized. Run 'claude-indexer init' first")
        raise typer.Exit(1)
        
    indexer = Indexer(str(path))
    
    if clear:
        indexer.clear_collection()
        
    indexer.index_directory(incremental=incremental)
```

#### 4.3 Project Commands
```python
@project_app.command("register")
def register_project(project_path: str):
    """Register project with service."""
    path = Path(project_path).resolve()
    project_config = ProjectConfig(path)
    
    if not project_config.exists():
        typer.echo(f"Project not initialized at {path}")
        raise typer.Exit(1)
        
    service = IndexingService()
    service.register_project(path)
    typer.echo(f"✅ Registered project: {path}")

@project_app.command("set-patterns")
def set_patterns(
    include: str = typer.Option(None, help="Include patterns (comma-separated)"),
    exclude: str = typer.Option(None, help="Exclude patterns (comma-separated)"),
    project_path: Optional[str] = typer.Argument(None)
):
    """Update project file patterns."""
    path = Path(project_path) if project_path else Path.cwd()
    project_config = ProjectConfig(path)
    
    config = project_config.load()
    
    if include:
        config['indexing']['file_patterns']['include'] = include.split(',')
    if exclude:
        config['indexing']['file_patterns']['exclude'] = exclude.split(',')
        
    project_config.save(config)
    typer.echo("✅ Updated file patterns")
```

### Phase 5: Remove Legacy Code and Hardcoded Patterns

#### 5.1 Complete Removal of Hardcoded Patterns
**Audit all files for orphaned hardcoded settings:**

1. **claude_indexer/config.py**
   - Remove: `include_patterns = ['*.py', '*.md']`
   - Remove: `exclude_patterns = ['*.pyc', '__pycache__', '.git', '.venv', 'node_modules']`
   - Replace with dynamic loading from project config

2. **claude_indexer/watcher/handler.py**
   - Remove: Line 35 `self.watch_patterns = ["*.py", "*.md"]`
   - Remove: Line 340 fallback patterns
   - Remove: Line 457 constructor defaults
   - Replace with project config loading

3. **claude_indexer/service.py**
   - Remove: Line 24 `CONFIG_FILE = Path.home() / '.claude-indexer' / 'config.json'`
   - Remove: Lines 32-67 global config loading
   - Remove: Lines 68-81 global config saving
   - Replace with project registry only

4. **claude_indexer/indexer.py**
   - Remove: Line 97 centralized state directory
   - Remove: Line 339 hardcoded ignore patterns
   - Remove: Lines 102-141 centralized state management
   - Replace with project-local state

5. **Ensure NO orphaned patterns remain**
   - Search entire codebase for string literals: `"*.py"`, `"*.md"`, `"*.pyc"`
   - Replace ALL with configuration-driven patterns
   - No fallback patterns anywhere in code

#### 5.2 Simplified Config Loading
```python
# No fallbacks, no migrations, just clean project-local config
def load_project_config(project_path: Path) -> Dict[str, Any]:
    """Load project configuration."""
    project_config = ProjectConfig(project_path)
    if not project_config.exists():
        raise ValueError(f"Project not initialized at {project_path}")
    return project_config.load()
```

## Comprehensive Testing Strategy

### Unit Tests

1. **test_project_config.py**
   ```python
   def test_initialize_project():
       """Test project initialization creates correct structure."""
   def test_custom_file_patterns():
       """Test each project can set custom include/exclude patterns."""
   def test_js_txt_patterns():
       """Verify JS and TXT files are properly configured."""
   def test_no_hardcoded_defaults():
       """Ensure no hardcoded patterns exist in config."""
   ```

2. **test_javascript_parser.py**
   ```python
   def test_parse_js_functions():
       """Test parsing of JavaScript functions."""
   def test_parse_typescript_classes():
       """Test TypeScript class extraction."""
   def test_jsx_components():
       """Test React/JSX component parsing."""
   def test_import_export_relations():
       """Test ES6 import/export detection."""
   ```

3. **test_text_parser.py**
   ```python
   def test_text_file_chunking():
       """Test .txt file splitting into chunks."""
   def test_large_text_files():
       """Test handling of large text files."""
   def test_various_text_formats():
       """Test .log, .csv, .conf file parsing."""
   def test_encoding_handling():
       """Test UTF-8 and other encodings."""
   ```

### Integration Tests

1. **test_project_patterns_integration.py**
   ```python
   def test_project_specific_js_indexing():
       """Test project with JS files only."""
   def test_project_specific_txt_indexing():
       """Test project with TXT files only."""
   def test_mixed_file_types():
       """Test project with PY, JS, TXT files."""
   def test_pattern_exclusion():
       """Test exclude patterns work correctly."""
   ```

2. **test_no_hardcoded_patterns.py**
   ```python
   def test_no_fallback_patterns():
       """Verify no hardcoded patterns in any module."""
   def test_config_required():
       """Test that missing config raises error."""
   def test_dynamic_pattern_loading():
       """Test all patterns come from config."""
   ```

### End-to-End Tests

1. **test_js_txt_workflow.py**
   ```python
   def test_init_with_js_txt_patterns():
       """Test: init → add JS/TXT patterns → index → verify."""
   def test_change_patterns_reindex():
       """Test: change patterns → reindex → verify new files."""
   def test_per_project_isolation():
       """Test: two projects with different patterns."""
   ```

2. **test_cli_pattern_commands.py**
   ```python
   def test_set_patterns_command():
       """Test: claude-indexer project set-patterns --include "*.js,*.txt"."""
   def test_show_patterns():
       """Test: claude-indexer project show displays patterns."""
   def test_parser_list():
       """Test: claude-indexer parsers list shows JS/TXT."""
   ```

### Verification Tests

1. **test_complete_removal_hardcoded.py**
   ```python
   def test_grep_no_hardcoded_patterns():
       """Grep codebase for "*.py", "*.md" literals - should find none."""
   def test_all_patterns_configurable():
       """Verify every file pattern is configuration-driven."""
   ```

## Implementation Timeline

### Day 1: Core Infrastructure
1. Create `ProjectConfig` class
2. Update state management
3. Remove legacy code

### Day 2: Parser Development
1. Implement JavaScript parser
2. Implement text parser
3. Update parser registry

### Day 3: Service Updates
1. Update Indexer for project-local config
2. Update Service for project discovery
3. Update Watcher integration

### Day 4: CLI Implementation
1. Add init command
2. Update all commands for project-local
3. Add project management commands

### Day 5: Testing
1. Write all unit tests
2. Write integration tests
3. Fix any issues

### Day 6: Documentation
1. Update README
2. Update CLAUDE.md
3. Create examples

## Key Requirements Summary

### Core Requirements from Discussion
1. **Add JS and TXT file support** - Primary request
2. **Project-level settings** - Each project chooses its own file types
3. **Settings location** - PROJECT_DIR/.claude-indexer/config.json (NOT user directory)
4. **Clean implementation** - No dual mode, no legacy support
5. **Remove ALL hardcoded patterns** - No orphaned settings anywhere

### Implementation Verification Checklist
- [ ] JavaScript parser implemented with tree-sitter
- [ ] Text parser implemented with chunking
- [ ] All hardcoded patterns removed from codebase
- [ ] Project config in PROJECT_DIR/.claude-indexer/config.json
- [ ] Each project can independently configure file patterns
- [ ] State file moved to project-local directory
- [ ] No fallback patterns in any module
- [ ] Comprehensive tests for JS/TXT parsing
- [ ] CLI commands for pattern management
- [ ] Service supports multiple projects with different patterns

## Success Criteria

1. ✅ **JavaScript & Text Support**: Full parsing support for .js, .txt files as requested
2. ✅ **Project Independence**: Each project configures its own file patterns
3. ✅ **Clean Architecture**: No legacy code, dual modes, or hardcoded patterns
4. ✅ **Project-Local Everything**: Config and state in PROJECT_DIR/.claude-indexer/
5. ✅ **No Orphaned Settings**: Complete removal of all hardcoded file patterns
6. ✅ **Multi-Language Support**: Python, JS, TS, TXT, and extensible for more
7. ✅ **Simple CLI**: Intuitive commands (init, index, set-patterns)
8. ✅ **Service Compatible**: Multi-project watching with isolation
9. ✅ **Comprehensive Tests**: Full coverage of new functionality
10. ✅ **Documentation**: Clear examples and migration guide