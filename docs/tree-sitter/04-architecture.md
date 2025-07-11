# Tree-Sitter Architecture & Design Patterns

This document explains the architectural patterns and design decisions behind the tree-sitter language pack integration.

## Core Architecture

### Language Pack Integration Flow

```mermaid
graph TD
    A[File Detection] --> B{Extension Match?}
    B -->|Yes| C[Get Parser]
    B -->|No| D[Skip File]
    C --> E[Load Language]
    E --> F{Language Pack Available?}
    F -->|Yes| G[get_language("name")]
    F -->|No| H[Fallback to Individual Package]
    G --> I[Create Parser]
    H --> I
    I --> J[Parse File]
    J --> K[Extract Entities]
    K --> L[Store Results]
```

### Parser Registry Pattern

The `ParserRegistry` manages all available parsers and routes files to the appropriate parser:

```python
class ParserRegistry:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self._parsers: List[CodeParser] = []
        self._register_default_parsers()
    
    def get_parser_for_file(self, file_path: Path) -> Optional[CodeParser]:
        """Route file to appropriate parser based on extension."""
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return None
    
    def register(self, parser: CodeParser):
        """Register a new parser."""
        self._parsers.append(parser)
```

### Language Detection Strategy

#### 1. File Extension Mapping
Primary detection method using file extensions:

```python
EXTENSION_TO_LANGUAGE = {
    '.js': 'javascript',
    '.jsx': 'javascript', 
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.py': 'python',
    '.rs': 'rust',
    '.go': 'go',
    '.vue': 'vue',
    '.svelte': 'svelte'
}
```

#### 2. Content-Based Detection (Future)
For ambiguous cases or extensionless files:

```python
def detect_language_by_content(content: str) -> Optional[str]:
    """Detect language by analyzing file content."""
    # Shebang detection
    if content.startswith('#!/usr/bin/python'):
        return 'python'
    
    # Language-specific patterns
    if 'fn main()' in content and 'println!' in content:
        return 'rust'
    
    return None
```

### Parser Hierarchy

```
TreeSitterParser (Base)
├── JavaScriptParser
│   ├── Handles: .js, .jsx, .ts, .tsx
│   └── Languages: javascript, typescript, tsx
├── PythonParser  
│   ├── Handles: .py, .pyi
│   └── Language: python + Jedi integration
├── RustParser
│   ├── Handles: .rs
│   └── Language: rust
└── VueParser
    ├── Handles: .vue
    └── Language: vue + sub-parsers
```

## Design Patterns

### 1. Fallback Pattern

Every parser implements graceful degradation:

```python
class LanguageParser(TreeSitterParser):
    def __init__(self, config=None):
        try:
            # Try language pack first (preferred)
            from tree_sitter_language_pack import get_language
            lang = get_language("language_name")
            super().__init__(lang, config)
        except ImportError:
            # Fallback to individual package
            try:
                import tree_sitter_language as lang_module
                super().__init__(lang_module, config)
            except ImportError:
                # Final fallback or error
                raise ImportError("No language support available")
```

**Benefits:**
- Graceful degradation for different installation scenarios
- Backward compatibility with existing setups
- Clear error messages for missing dependencies

### 2. Progressive Disclosure Pattern

Each parser creates both metadata and implementation chunks:

```python
def _create_entity_with_chunks(self, node, file_path, content):
    """Create entity with progressive disclosure."""
    
    # Extract basic information
    name = self._extract_name(node, content)
    signature = self._extract_signature(node, content)
    
    # Create entity
    entity = Entity(
        name=name,
        entity_type=self._determine_type(node),
        observations=[f"Brief description: {signature}"],
        metadata={"has_implementation": True}
    )
    
    # Create chunks
    chunks = [
        # Fast metadata chunk (for search)
        EntityChunk(
            chunk_type="metadata",
            content=f"Name: {name}\nSignature: {signature}",
            metadata={"entity_type": "function", "has_implementation": True}
        ),
        # Detailed implementation chunk (on-demand)
        EntityChunk(
            chunk_type="implementation",
            content=self.extract_node_text(node, content),
            metadata={"entity_type": "function", "start_line": node.start_point[0]}
        )
    ]
    
    return entity, chunks
```

**Benefits:**
- Fast search through metadata chunks
- Detailed analysis through implementation chunks
- Reduced memory usage for large codebases
- Flexible query patterns

### 3. Language Object Management

Proper handling of Language objects from different sources:

```python
def _initialize_language(self, language_source):
    """Initialize parser with proper Language object handling."""
    
    if hasattr(language_source, 'language'):
        # Individual package (tree_sitter_python)
        language_capsule = language_source.language()
        language = Language(language_capsule)
        self.parser = Parser(language)
    elif hasattr(language_source, '_address'):
        # Language pack (already a Language object)
        self.parser = Parser(language_source)
    else:
        # Direct Language object
        self.parser = Parser(language_source)
```

**Handles:**
- Language pack Language objects
- Individual package language capsules  
- Direct Language object initialization
- Error cases with clear messages

### 4. Entity Factory Pattern

Consistent entity creation across all parsers:

```python
class EntityFactory:
    @staticmethod
    def create_function_entity(name: str, file_path: Path, **kwargs) -> Entity:
        """Create standardized function entity."""
        return Entity(
            name=name,
            entity_type=EntityType.FUNCTION,
            file_path=file_path,
            observations=kwargs.get('observations', []),
            metadata={
                "type": "function",
                "language": kwargs.get('language', 'unknown'),
                **kwargs.get('metadata', {})
            }
        )
    
    @staticmethod  
    def create_class_entity(name: str, file_path: Path, **kwargs) -> Entity:
        """Create standardized class entity."""
        return Entity(
            name=name,
            entity_type=EntityType.CLASS,
            file_path=file_path,
            observations=kwargs.get('observations', []),
            metadata={
                "type": "class",
                "language": kwargs.get('language', 'unknown'),
                **kwargs.get('metadata', {})
            }
        )
```

**Benefits:**
- Consistent metadata structure
- Standardized entity types
- Easy to extend with new entity types
- Type safety and validation

### 5. Error Handling Strategy

Lenient parsing with detailed error reporting:

```python
def parse(self, file_path: Path) -> ParserResult:
    """Parse with comprehensive error handling."""
    result = ParserResult(file_path=file_path, entities=[], relations=[])
    
    try:
        # Parse and extract
        tree = self.parse_tree(content, file_path)
        
        # Check for syntax errors
        if self._has_syntax_errors(tree):
            if self._is_lenient_file_type(file_path):
                # TSX, Vue, etc. - use warnings
                result.warnings.append(f"Minor syntax irregularities in {file_path.name}")
            else:
                # Strict languages - use errors
                result.errors.append(f"Syntax errors in {file_path.name}")
        
        # Extract entities even with minor errors
        entities = self._extract_entities(tree, content, file_path)
        result.entities = entities
        
    except Exception as e:
        # Capture actual error details
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Parse failed for {file_path}: {type(e).__name__}: {e}")
        result.errors.append(f"Parse failed: {e}")
    
    return result
```

**Strategy:**
- Continue parsing even with minor syntax errors
- Differentiate between lenient (TSX, Vue) and strict (Python) languages
- Provide detailed error information for debugging
- Never fail silently

## Performance Optimizations

### 1. Lazy Language Loading

Languages are loaded on-demand to reduce startup time:

```python
class CachedLanguageLoader:
    _language_cache = {}
    
    @classmethod
    def get_language(cls, name: str):
        """Get language with caching."""
        if name not in cls._language_cache:
            from tree_sitter_language_pack import get_language
            cls._language_cache[name] = get_language(name)
        return cls._language_cache[name]
```

### 2. Parser Instance Reuse

Parser instances are reused across files of the same type:

```python
class ParserRegistry:
    def __init__(self):
        self._parser_cache = {}
    
    def get_parser_for_file(self, file_path: Path) -> CodeParser:
        """Get cached parser instance."""
        ext = file_path.suffix
        if ext not in self._parser_cache:
            self._parser_cache[ext] = self._create_parser_for_extension(ext)
        return self._parser_cache[ext]
```

### 3. Incremental Parsing

Support for parsing only changed portions of files:

```python
def parse_incremental(self, file_path: Path, old_tree=None) -> ParserResult:
    """Parse with incremental updates."""
    if old_tree and self._can_use_incremental(file_path):
        # Use tree-sitter incremental parsing
        new_tree = self.parser.parse(
            bytes(content, "utf8"), 
            old_tree=old_tree
        )
    else:
        # Full parse
        new_tree = self.parser.parse(bytes(content, "utf8"))
    
    return self._extract_from_tree(new_tree, file_path)
```

### 4. Memory Management

Efficient memory usage for large codebases:

```python
def _optimize_memory_usage(self):
    """Optimize memory for large parsing operations."""
    # Clear parse tree after entity extraction
    del tree
    
    # Limit chunk sizes
    if len(content) > MAX_CHUNK_SIZE:
        content = content[:MAX_CHUNK_SIZE] + "..."
    
    # Use generators for large file sets
    def parse_files_generator(file_paths):
        for file_path in file_paths:
            yield self.parse(file_path)
            # Clear intermediate results
            gc.collect()
```

## Integration Points

### 1. Storage Layer Integration

Parsers work seamlessly with vector storage:

```python
class VectorStoreIntegration:
    def store_parse_results(self, results: List[ParserResult]):
        """Store parsing results in vector database."""
        
        # Batch entities and chunks
        all_entities = []
        all_chunks = []
        
        for result in results:
            all_entities.extend(result.entities)
            all_chunks.extend(result.implementation_chunks)
        
        # Generate embeddings
        embeddings = self.embedder.embed_batch([e.observations for e in all_entities])
        
        # Store in vector DB
        self.vector_store.store_entities(all_entities, embeddings)
        self.vector_store.store_chunks(all_chunks)
```

### 2. Configuration System

Language-specific configuration support:

```python
# Project config example
{
    "indexing": {
        "parser_config": {
            "javascript": {
                "include_jsx": true,
                "typescript_mode": "strict"
            },
            "python": {
                "include_docstrings": true,
                "jedi_enabled": true
            },
            "rust": {
                "extract_macros": true,
                "include_tests": false
            }
        }
    }
}
```

### 3. Plugin System

Extensible architecture for custom parsers:

```python
class PluginRegistry:
    def register_parser_plugin(self, parser_class: Type[CodeParser]):
        """Register external parser plugin."""
        self.parsers.append(parser_class)
    
    def load_plugins_from_config(self, config: Dict):
        """Load parsers from configuration."""
        for plugin_path in config.get('parser_plugins', []):
            module = importlib.import_module(plugin_path)
            self.register_parser_plugin(module.Parser)
```

## Testing Architecture

### 1. Parser Testing Framework

Standardized testing patterns for all parsers:

```python
class ParserTestBase:
    """Base class for parser tests."""
    
    def create_test_file(self, content: str, extension: str) -> Path:
        """Create temporary test file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=extension, delete=False
        ) as f:
            f.write(content)
            return Path(f.name)
    
    def assert_parse_success(self, result: ParserResult):
        """Assert successful parsing."""
        assert result.success, f"Parse failed: {result.errors}"
        assert len(result.entities) > 0, "No entities extracted"
    
    def assert_entity_extracted(self, result: ParserResult, name: str, entity_type: EntityType):
        """Assert specific entity was extracted."""
        entities = [e for e in result.entities if e.name == name]
        assert len(entities) > 0, f"Entity '{name}' not found"
        assert entities[0].entity_type == entity_type
```

### 2. Integration Testing

Test parser integration with the full system:

```python
def test_full_indexing_pipeline():
    """Test complete indexing pipeline."""
    
    # Create test project
    test_files = create_test_project([
        ("main.rs", rust_code),
        ("app.vue", vue_code),
        ("utils.ts", typescript_code)
    ])
    
    # Run indexing
    indexer = CoreIndexer(test_project_path)
    result = indexer.index_project("test-collection")
    
    # Verify results
    assert result.success
    assert result.files_processed == 3
    assert result.entities_created > 0
    
    # Verify language distribution
    rust_entities = count_entities_by_language(result, "rust")
    vue_entities = count_entities_by_language(result, "vue") 
    ts_entities = count_entities_by_language(result, "typescript")
    
    assert rust_entities > 0
    assert vue_entities > 0
    assert ts_entities > 0
```

## Future Architecture Considerations

### 1. Language Server Protocol Integration

Future support for LSP-based semantic analysis:

```python
class LSPEnhancedParser(TreeSitterParser):
    """Parser with LSP semantic enhancement."""
    
    def __init__(self, lsp_client=None):
        super().__init__()
        self.lsp_client = lsp_client
    
    def parse_with_semantics(self, file_path: Path):
        """Parse with LSP semantic information."""
        # Tree-sitter for structure
        syntax_result = super().parse(file_path)
        
        # LSP for semantics
        if self.lsp_client:
            semantic_info = self.lsp_client.get_semantic_tokens(file_path)
            self._enhance_with_semantics(syntax_result, semantic_info)
        
        return syntax_result
```

### 2. Streaming Parse Results

For very large codebases:

```python
def parse_streaming(self, file_paths: Iterator[Path]) -> Iterator[ParserResult]:
    """Stream parse results for memory efficiency."""
    for file_path in file_paths:
        result = self.parse(file_path)
        yield result
        # Clear intermediate state
        self._clear_cache()
```

### 3. Parallel Parsing

Multi-threaded parsing for performance:

```python
def parse_parallel(self, file_paths: List[Path], max_workers=4) -> List[ParserResult]:
    """Parse files in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(self.parse, fp) for fp in file_paths]
        return [future.result() for future in futures]
```

---

*This architecture provides a solid foundation for extensible, performant multi-language parsing with the tree-sitter language pack.*