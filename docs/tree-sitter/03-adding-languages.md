# Adding New Language Parsers

This guide shows you how to add support for new languages using the tree-sitter language pack.

## Quick Start Example: Rust Parser

Let's create a Rust parser as a complete example:

### 1. Create the Parser Class

```python
# claude_indexer/analysis/rust_parser.py
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import time
from tree_sitter import Node
from .base_parsers import TreeSitterParser
from .parser import ParserResult
from .entities import Entity, Relation, EntityChunk, EntityType, RelationType, EntityFactory, RelationFactory


class RustParser(TreeSitterParser):
    """Parse Rust files with tree-sitter."""
    
    SUPPORTED_EXTENSIONS = ['.rs']
    
    def __init__(self, config: Dict[str, Any] = None):
        # Use tree-sitter-language-pack for comprehensive language support
        try:
            from tree_sitter_language_pack import get_language
            rust_language = get_language("rust")
            super().__init__(rust_language, config)
        except ImportError:
            # Fallback to individual package (if available)
            try:
                import tree_sitter_rust as tsrust
                super().__init__(tsrust, config)
            except ImportError:
                raise ImportError("No Rust tree-sitter support available. Install tree-sitter-language-pack.")
    
    def parse(self, file_path: Path, batch_callback=None, global_entity_names=None) -> ParserResult:
        """Extract Rust functions, structs, traits, and modules."""
        start_time = time.time()
        result = ParserResult(file_path=file_path, entities=[], relations=[])
        
        try:
            # Read and parse Rust code
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result.file_hash = self._get_file_hash(file_path)
            tree = self.parse_tree(content)
            
            # Check for syntax errors (lenient for Rust)
            if self._has_syntax_errors(tree):
                result.warnings.append(f"Minor syntax irregularities in {file_path.name}")
            
            entities = []
            relations = []
            chunks = []
            
            # Create file entity
            file_entity = self._create_file_entity(file_path, content_type="rust")
            entities.append(file_entity)
            
            # Extract functions
            for node in self._find_nodes_by_type(tree.root_node, ['function_item']):
                entity, entity_chunks = self._create_function_entity(node, file_path, content)
                if entity:
                    entities.append(entity)
                    chunks.extend(entity_chunks)
            
            # Extract structs
            for node in self._find_nodes_by_type(tree.root_node, ['struct_item']):
                entity, entity_chunks = self._create_struct_entity(node, file_path, content)
                if entity:
                    entities.append(entity)
                    chunks.extend(entity_chunks)
            
            # Extract traits
            for node in self._find_nodes_by_type(tree.root_node, ['trait_item']):
                entity, entity_chunks = self._create_trait_entity(node, file_path, content)
                if entity:
                    entities.append(entity)
                    chunks.extend(entity_chunks)
            
            # Extract use statements (imports)
            import_relations = self._extract_imports(tree.root_node, content, file_path)
            relations.extend(import_relations)
            
            # Create containment relations
            file_name = str(file_path)
            for entity in entities[1:]:  # Skip file entity
                relation = RelationFactory.create_contains_relation(file_name, entity.name)
                relations.append(relation)
            
            result.entities = entities
            result.relations = relations
            result.implementation_chunks = chunks
            
        except Exception as e:
            result.errors.append(f"Rust parsing failed: {e}")
        
        result.parsing_time = time.time() - start_time
        return result
    
    def _create_function_entity(self, node: Node, file_path: Path, content: str) -> Tuple[Optional[Entity], List[EntityChunk]]:
        """Create entity for Rust function."""
        # Extract function name
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None, []
        
        func_name = self.extract_node_text(name_node, content)
        
        # Extract function signature and body
        signature = self.extract_node_text(node, content).split('{')[0].strip()
        
        # Create entity
        entity = Entity(
            name=func_name,
            entity_type=EntityType.FUNCTION,
            observations=[
                f"Rust function: {func_name}",
                f"Signature: {signature}",
                f"Located in {file_path.name}"
            ],
            file_path=file_path,
            line_number=node.start_point[0] + 1,
            metadata={
                "type": "rust_function",
                "signature": signature,
                "language": "rust"
            }
        )
        
        # Create implementation chunk
        chunk = EntityChunk(
            id=self._create_chunk_id(file_path, func_name, "implementation"),
            entity_name=func_name,
            chunk_type="implementation",
            content=self.extract_node_text(node, content),
            metadata={
                "entity_type": "rust_function",
                "file_path": str(file_path),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1
            }
        )
        
        return entity, [chunk]
    
    def _create_struct_entity(self, node: Node, file_path: Path, content: str) -> Tuple[Optional[Entity], List[EntityChunk]]:
        """Create entity for Rust struct."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None, []
        
        struct_name = self.extract_node_text(name_node, content)
        
        entity = Entity(
            name=struct_name,
            entity_type=EntityType.CLASS,
            observations=[
                f"Rust struct: {struct_name}",
                f"Located in {file_path.name}"
            ],
            file_path=file_path,
            line_number=node.start_point[0] + 1,
            metadata={
                "type": "rust_struct",
                "language": "rust"
            }
        )
        
        chunk = EntityChunk(
            id=self._create_chunk_id(file_path, struct_name, "implementation"),
            entity_name=struct_name,
            chunk_type="implementation",
            content=self.extract_node_text(node, content),
            metadata={
                "entity_type": "rust_struct",
                "file_path": str(file_path),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1
            }
        )
        
        return entity, [chunk]
    
    def _create_trait_entity(self, node: Node, file_path: Path, content: str) -> Tuple[Optional[Entity], List[EntityChunk]]:
        """Create entity for Rust trait."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None, []
        
        trait_name = self.extract_node_text(name_node, content)
        
        entity = Entity(
            name=trait_name,
            entity_type=EntityType.CLASS,
            observations=[
                f"Rust trait: {trait_name}",
                f"Located in {file_path.name}"
            ],
            file_path=file_path,
            line_number=node.start_point[0] + 1,
            metadata={
                "type": "rust_trait",
                "language": "rust"
            }
        )
        
        chunk = EntityChunk(
            id=self._create_chunk_id(file_path, trait_name, "implementation"),
            entity_name=trait_name,
            chunk_type="implementation",
            content=self.extract_node_text(node, content),
            metadata={
                "entity_type": "rust_trait",
                "file_path": str(file_path),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1
            }
        )
        
        return entity, [chunk]
    
    def _extract_imports(self, root: Node, content: str, file_path: Path) -> List[Relation]:
        """Extract use statements as import relations."""
        relations = []
        
        for use_node in self._find_nodes_by_type(root, ['use_declaration']):
            use_text = self.extract_node_text(use_node, content)
            
            # Extract the imported module/crate
            # use std::collections::HashMap -> std::collections::HashMap
            if '::' in use_text:
                import_path = use_text.replace('use ', '').replace(';', '').strip()
                
                relation = RelationFactory.create_imports_relation(
                    importer=str(file_path),
                    imported=import_path,
                    import_type="rust_use"
                )
                relations.append(relation)
        
        return relations
```

### 2. Register the Parser

Add the Rust parser to the parser registry:

```python
# claude_indexer/analysis/parser.py (in _register_default_parsers method)

def _register_default_parsers(self):
    """Register default parsers."""
    from .javascript_parser import JavaScriptParser
    from .json_parser import JSONParser
    from .html_parser import HTMLParser
    from .css_parser import CSSParser
    from .yaml_parser import YAMLParser
    from .rust_parser import RustParser  # Add this import
    from .text_parser import TextParser, CSVParser, INIParser
    
    # Core language parsers
    self.register(PythonParser(self.project_path))
    self.register(JavaScriptParser())
    self.register(RustParser())  # Add this line
    
    # ... rest of the method
```

### 3. Test the Parser

```python
# Test script
from claude_indexer.analysis.rust_parser import RustParser
from pathlib import Path
import tempfile

# Create test Rust code
rust_code = '''
use std::collections::HashMap;

#[derive(Debug)]
pub struct User {
    name: String,
    age: u32,
}

impl User {
    pub fn new(name: String, age: u32) -> Self {
        User { name, age }
    }
    
    pub fn greet(&self) -> String {
        format!("Hello, I'm {}", self.name)
    }
}

trait Displayable {
    fn display(&self) -> String;
}

pub fn main() {
    let user = User::new("Alice".to_string(), 30);
    println!("{}", user.greet());
}
'''

# Test parsing
with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as f:
    f.write(rust_code)
    temp_file = f.name

try:
    parser = RustParser()
    result = parser.parse(Path(temp_file))
    
    print(f"Parse successful: {result.success}")
    print(f"Entities found: {len(result.entities)}")
    for entity in result.entities:
        print(f"  - {entity.name} ({entity.entity_type})")
    
    print(f"Relations found: {len(result.relations)}")
    for relation in result.relations:
        print(f"  - {relation.from_entity} -> {relation.to_entity}")
        
finally:
    import os
    os.unlink(temp_file)
```

## Step-by-Step Process

### 1. Research the Language Grammar

```python
# Test if the language is available
from tree_sitter_language_pack import get_language
try:
    lang = get_language("your_language")
    print(f"Language available: {lang}")
except Exception as e:
    print(f"Language not available: {e}")
```

**Available languages**: See [Grammar List](https://github.com/grantjenks/py-tree-sitter-language-pack#languages)

### 2. Understand the Parse Tree Structure

Use the tree-sitter playground or create a test script:

```python
from tree_sitter_language_pack import get_language
from tree_sitter import Parser

# Create parser
language = get_language("rust")  # or your target language
parser = Parser(language)

# Parse sample code
code = '''
fn hello() {
    println!("Hello, world!");
}
'''

tree = parser.parse(bytes(code, "utf8"))

def print_tree(node, depth=0):
    print("  " * depth + f"{node.type}: {node.text.decode('utf8')[:50]}")
    for child in node.children:
        print_tree(child, depth + 1)

print_tree(tree.root_node)
```

### 3. Identify Key Node Types

For each language, identify the important node types:

| Language | Functions | Classes/Structs | Imports | Variables |
|----------|-----------|-----------------|---------|-----------|
| Rust | `function_item` | `struct_item`, `trait_item` | `use_declaration` | `let_declaration` |
| Go | `function_declaration` | `type_declaration` | `import_declaration` | `var_declaration` |
| Vue | `script_element` | `template_element` | `import_statement` | `variable_declaration` |

### 4. Follow the Parser Template

Use this template for any new language:

```python
class YourLanguageParser(TreeSitterParser):
    """Parse YourLanguage files with tree-sitter."""
    
    SUPPORTED_EXTENSIONS = ['.ext1', '.ext2']
    
    def __init__(self, config: Dict[str, Any] = None):
        # Language pack integration with fallback
        try:
            from tree_sitter_language_pack import get_language
            lang = get_language("your_language")
            super().__init__(lang, config)
        except ImportError:
            raise ImportError("No YourLanguage tree-sitter support available.")
    
    def parse(self, file_path: Path, batch_callback=None, global_entity_names=None) -> ParserResult:
        """Extract language-specific constructs."""
        # Standard parsing pattern
        start_time = time.time()
        result = ParserResult(file_path=file_path, entities=[], relations=[])
        
        try:
            # Read file and create parse tree
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result.file_hash = self._get_file_hash(file_path)
            tree = self.parse_tree(content)
            
            # Error handling
            if self._has_syntax_errors(tree):
                result.warnings.append(f"Minor syntax irregularities in {file_path.name}")
            
            entities = []
            relations = []
            chunks = []
            
            # File entity
            file_entity = self._create_file_entity(file_path, content_type="your_language")
            entities.append(file_entity)
            
            # Extract constructs
            # TODO: Add extraction methods for your language
            
            # Build result
            result.entities = entities
            result.relations = relations
            result.implementation_chunks = chunks
            
        except Exception as e:
            result.errors.append(f"YourLanguage parsing failed: {e}")
        
        result.parsing_time = time.time() - start_time
        return result
```

## Language-Specific Examples

### Vue.js Single File Components

```python
class VueParser(TreeSitterParser):
    """Parse Vue.js single file components."""
    
    SUPPORTED_EXTENSIONS = ['.vue']
    
    def __init__(self, config=None):
        from tree_sitter_language_pack import get_language
        vue_language = get_language("vue")
        super().__init__(vue_language, config)
    
    def parse(self, file_path: Path, batch_callback=None, global_entity_names=None) -> ParserResult:
        # Extract <template>, <script>, <style> sections
        # Parse each section with appropriate sub-parser
        pass
```

### Go Language

```python
class GoParser(TreeSitterParser):
    """Parse Go source files."""
    
    SUPPORTED_EXTENSIONS = ['.go']
    
    def __init__(self, config=None):
        from tree_sitter_language_pack import get_language
        go_language = get_language("go")
        super().__init__(go_language, config)
    
    def _extract_functions(self, root: Node, content: str, file_path: Path):
        """Extract Go functions and methods."""
        entities = []
        for node in self._find_nodes_by_type(root, ['function_declaration', 'method_declaration']):
            # Extract function name, parameters, return types
            pass
        return entities
```

### SQL Parser

```python
class SQLParser(TreeSitterParser):
    """Parse SQL query files."""
    
    SUPPORTED_EXTENSIONS = ['.sql']
    
    def __init__(self, config=None):
        from tree_sitter_language_pack import get_language
        sql_language = get_language("sql")
        super().__init__(sql_language, config)
    
    def _extract_statements(self, root: Node, content: str, file_path: Path):
        """Extract SQL statements, tables, functions."""
        # Extract CREATE TABLE, CREATE FUNCTION, etc.
        pass
```

## Testing Your Parser

### Unit Tests

```python
# tests/test_rust_parser.py
import pytest
from pathlib import Path
import tempfile
from claude_indexer.analysis.rust_parser import RustParser

def test_rust_function_extraction():
    rust_code = '''
    fn hello_world() {
        println!("Hello, world!");
    }
    '''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as f:
        f.write(rust_code)
        temp_file = f.name
    
    try:
        parser = RustParser()
        result = parser.parse(Path(temp_file))
        
        assert result.success
        assert len(result.entities) >= 2  # File + function
        
        # Find the function entity
        func_entity = next(e for e in result.entities if e.name == "hello_world")
        assert func_entity.entity_type == EntityType.FUNCTION
        
    finally:
        import os
        os.unlink(temp_file)
```

### Integration Tests

```python
# Test with real project files
def test_real_rust_project():
    # Point to actual Rust files
    rust_files = list(Path("./test_projects/rust_project").glob("**/*.rs"))
    
    parser = RustParser()
    for rust_file in rust_files:
        result = parser.parse(rust_file)
        assert result.success, f"Failed to parse {rust_file}"
        assert len(result.entities) > 0, f"No entities in {rust_file}"
```

## Best Practices

### 1. Error Handling
- Always use try/catch blocks
- Provide meaningful error messages
- Use warnings for minor syntax issues

### 2. Performance
- Lazy-load heavy dependencies
- Cache language objects when possible
- Use progressive disclosure for large entities

### 3. Entity Types
- Functions → `EntityType.FUNCTION`
- Classes/Structs → `EntityType.CLASS`  
- Modules/Namespaces → `EntityType.DOCUMENTATION`
- Files → `EntityType.FILE`

### 4. Metadata
Include rich metadata for filtering and analysis:

```python
metadata = {
    "type": "rust_function",
    "language": "rust", 
    "visibility": "pub",
    "is_async": False,
    "parameters": ["param1", "param2"],
    "return_type": "Result<String, Error>"
}
```

### 5. Progressive Disclosure
Always create both metadata and implementation chunks:

```python
# Metadata chunk (fast search)
metadata_chunk = EntityChunk(
    chunk_type="metadata",
    content=f"Function: {name}\nSignature: {signature}",
    metadata={"has_implementation": True}
)

# Implementation chunk (full code)
impl_chunk = EntityChunk(
    chunk_type="implementation", 
    content=full_function_code,
    metadata={"entity_type": "function"}
)
```

## Troubleshooting

### Common Issues

1. **Language not found**: Check available languages with `get_language_list()`
2. **Parse errors**: Use lenient error handling like TSX parser
3. **Missing entities**: Verify node types with tree-sitter playground
4. **Performance issues**: Implement chunking for large files

### Debug Tools

```python
# Debug parse tree structure
def debug_parse_tree(content, language_name):
    from tree_sitter_language_pack import get_language
    from tree_sitter import Parser
    
    language = get_language(language_name)
    parser = Parser(language)
    tree = parser.parse(bytes(content, "utf8"))
    
    def print_nodes(node, depth=0):
        print("  " * depth + f"{node.type}")
        for child in node.children:
            print_nodes(child, depth + 1)
    
    print_nodes(tree.root_node)
```

---

*For more examples and advanced patterns, see the [Examples](./05-examples.md) documentation.*