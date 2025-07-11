# Troubleshooting Tree-Sitter Language Pack Integration

This document provides solutions to common issues when working with tree-sitter-language-pack in claude-indexer.

## Installation Issues

### Problem: `tree-sitter-language-pack` not found

**Symptoms:**
```
ImportError: No module named 'tree_sitter_language_pack'
```

**Solutions:**

1. **Install the package:**
   ```bash
   pip install tree-sitter-language-pack
   ```

2. **Verify installation:**
   ```bash
   python -c "from tree_sitter_language_pack import get_language; print('OK')"
   ```

3. **Check virtual environment:**
   ```bash
   which python
   pip list | grep tree-sitter
   ```

4. **Upgrade if needed:**
   ```bash
   pip install --upgrade tree-sitter-language-pack
   ```

### Problem: Language not available in pack

**Symptoms:**
```
ValueError: Language 'your_language' is not available
```

**Solutions:**

1. **Check available languages:**
   ```python
   from tree_sitter_language_pack import get_language_list
   print(get_language_list())
   ```

2. **Verify language name:**
   ```python
   # Common name variations
   languages = ['javascript', 'typescript', 'python', 'rust', 'go', 'java']
   for lang in languages:
       try:
           from tree_sitter_language_pack import get_language
           get_language(lang)
           print(f"✓ {lang} available")
       except Exception as e:
           print(f"✗ {lang} error: {e}")
   ```

3. **Use fallback to individual packages:**
   ```python
   def get_language_with_fallback(lang_name):
       try:
           from tree_sitter_language_pack import get_language
           return get_language(lang_name)
       except ImportError:
           # Fallback to individual package
           if lang_name == 'rust':
               import tree_sitter_rust as lang_module
               return lang_module
           # Add other fallbacks as needed
   ```

## Parsing Issues

### Problem: "Parse failure" errors

**Symptoms:**
```
Parse failure: 'Language' object has no attribute 'language'
```

**Root Cause:** Language object handling mismatch between language pack and individual packages.

**Solutions:**

1. **Check Language object initialization:**
   ```python
   def _initialize_language_safely(self, language_source):
       if hasattr(language_source, 'language'):
           # Individual package (tree_sitter_python)
           language_capsule = language_source.language()
           from tree_sitter import Language
           language = Language(language_capsule)
           self.parser = Parser(language)
       elif hasattr(language_source, '_address'):
           # Language pack (already a Language object)
           self.parser = Parser(language_source)
       else:
           # Direct Language object
           self.parser = Parser(language_source)
   ```

2. **Debug Language object type:**
   ```python
   def debug_language_object(lang):
       print(f"Type: {type(lang)}")
       print(f"Has language attr: {hasattr(lang, 'language')}")
       print(f"Has _address attr: {hasattr(lang, '_address')}")
       print(f"Dir: {dir(lang)}")
   ```

3. **Use unified parser initialization:**
   ```python
   class SafeTreeSitterParser(TreeSitterParser):
       def __init__(self, language_source, config=None):
           try:
               # Try direct initialization first
               self.parser = Parser(language_source)
           except Exception as e:
               # Try with Language wrapper
               try:
                   if hasattr(language_source, 'language'):
                       language_capsule = language_source.language()
                       from tree_sitter import Language
                       language = Language(language_capsule)
                       self.parser = Parser(language)
                   else:
                       raise e
               except Exception as e2:
                   raise ImportError(f"Failed to initialize parser: {e}, {e2}")
   ```

### Problem: TSX/JSX parsing errors

**Symptoms:**
```
Parse failure for .tsx files
Minor syntax irregularities in Component.tsx
```

**Solutions:**

1. **Use lenient error handling:**
   ```python
   def _has_lenient_syntax_errors(self, tree, file_path):
       """Check for syntax errors with lenient handling for web frameworks."""
       if file_path.suffix in ['.tsx', '.jsx', '.vue', '.svelte']:
           # These formats often have mixed syntax
           return self._count_error_nodes(tree.root_node) > 5  # Higher threshold
       else:
           return self._has_syntax_errors(tree)
   
   def _count_error_nodes(self, node):
       """Count error nodes in parse tree."""
       error_count = 0
       if node.type == 'ERROR':
           error_count += 1
       for child in node.children:
           error_count += self._count_error_nodes(child)
       return error_count
   ```

2. **Test TSX parsing directly:**
   ```python
   def test_tsx_parsing():
       from tree_sitter_language_pack import get_language
       from tree_sitter import Parser
       
       tsx_language = get_language("tsx")
       parser = Parser(tsx_language)
       
       tsx_code = """
       import React from 'react';
       
       interface Props {
           name: string;
       }
       
       export const Component: React.FC<Props> = ({ name }) => {
           return <div>Hello, {name}!</div>;
       };
       """
       
       tree = parser.parse(bytes(tsx_code, "utf8"))
       print(f"Parse successful: {tree.root_node.type != 'ERROR'}")
       
       # Print parse tree
       def print_tree(node, depth=0):
           print("  " * depth + f"{node.type}")
           for child in node.children:
               print_tree(child, depth + 1)
       
       print_tree(tree.root_node)
   ```

3. **Handle mixed content gracefully:**
   ```python
   def parse_with_error_recovery(self, content, file_path):
       """Parse with error recovery for mixed-syntax files."""
       try:
           tree = self.parser.parse(bytes(content, "utf8"))
           
           # Check if parsing was successful
           if tree.root_node.type == 'ERROR':
               # Try alternate parsing strategies
               return self._parse_with_fallback(content, file_path)
           
           return tree
           
       except Exception as e:
           # Log error and try fallback
           self.logger.warning(f"Parse failed for {file_path}: {e}")
           return self._parse_with_fallback(content, file_path)
   ```

### Problem: No entities extracted

**Symptoms:**
```
Parse successful but no entities found
```

**Solutions:**

1. **Debug node types:**
   ```python
   def debug_parse_tree(self, content, language_name):
       """Debug parse tree structure."""
       from tree_sitter_language_pack import get_language
       from tree_sitter import Parser
       
       language = get_language(language_name)
       parser = Parser(language)
       tree = parser.parse(bytes(content, "utf8"))
       
       def collect_node_types(node, types=None):
           if types is None:
               types = set()
           types.add(node.type)
           for child in node.children:
               collect_node_types(child, types)
           return types
       
       node_types = collect_node_types(tree.root_node)
       print(f"Available node types: {sorted(node_types)}")
       
       # Print tree structure
       def print_tree(node, depth=0):
           if depth < 3:  # Limit depth
               print("  " * depth + f"{node.type}: {node.text.decode('utf8')[:50]}")
               for child in node.children:
                   print_tree(child, depth + 1)
       
       print_tree(tree.root_node)
   ```

2. **Check node type mapping:**
   ```python
   # Language-specific node types
   NODE_TYPE_MAPPING = {
       'rust': {
           'function': ['function_item'],
           'struct': ['struct_item'],
           'trait': ['trait_item'],
           'impl': ['impl_item']
       },
       'go': {
           'function': ['function_declaration'],
           'struct': ['type_declaration'],
           'interface': ['type_declaration']
       },
       'vue': {
           'template': ['template_element'],
           'script': ['script_element'],
           'style': ['style_element']
       }
   }
   
   def _find_nodes_by_language(self, root_node, language):
       """Find nodes based on language-specific mapping."""
       if language not in NODE_TYPE_MAPPING:
           return []
       
       node_types = NODE_TYPE_MAPPING[language]
       nodes = []
       
       for category, types in node_types.items():
           for node_type in types:
               nodes.extend(self._find_nodes_by_type(root_node, [node_type]))
       
       return nodes
   ```

3. **Verify file content:**
   ```python
   def verify_file_content(self, file_path):
       """Verify file can be read and has expected content."""
       try:
           with open(file_path, 'r', encoding='utf-8') as f:
               content = f.read()
           
           print(f"File size: {len(content)} characters")
           print(f"First 200 chars: {content[:200]}")
           
           # Check for common patterns
           patterns = ['function', 'class', 'struct', 'def', 'fn', 'pub', 'const', 'let', 'var']
           found_patterns = [p for p in patterns if p in content]
           print(f"Found patterns: {found_patterns}")
           
           return content
           
       except Exception as e:
           print(f"Error reading file: {e}")
           return None
   ```

## Performance Issues

### Problem: Slow parsing

**Symptoms:**
```
Parsing time: 45.23 seconds for large file
```

**Solutions:**

1. **Implement file size limits:**
   ```python
   MAX_FILE_SIZE = 1024 * 1024  # 1MB
   
   def parse_with_size_limit(self, file_path):
       """Parse with file size checking."""
       file_size = file_path.stat().st_size
       
       if file_size > MAX_FILE_SIZE:
           # Skip or use streaming for large files
           return self._parse_large_file(file_path)
       
       return self.parse(file_path)
   
   def _parse_large_file(self, file_path):
       """Handle large files with streaming."""
       result = ParserResult(file_path=file_path, entities=[], relations=[])
       result.warnings.append(f"Large file ({file_path.stat().st_size} bytes) - using streaming")
       
       # Implement streaming logic or skip
       return result
   ```

2. **Use incremental parsing:**
   ```python
   def parse_incremental(self, file_path, old_tree=None):
       """Parse with incremental updates."""
       if old_tree and self._should_use_incremental(file_path):
           # Use tree-sitter incremental parsing
           content = self._read_file(file_path)
           new_tree = self.parser.parse(
               bytes(content, "utf8"), 
               old_tree=old_tree
           )
           return self._extract_from_tree(new_tree, file_path)
       else:
           # Full parse
           return self.parse(file_path)
   ```

3. **Implement caching:**
   ```python
   from functools import lru_cache
   import hashlib
   
   @lru_cache(maxsize=100)
   def _cached_parse(self, file_path_str, file_hash):
       """Cache parse results by file hash."""
       return self.parse(Path(file_path_str))
   
   def parse_with_cache(self, file_path):
       """Parse with caching based on file hash."""
       file_hash = self._get_file_hash(file_path)
       return self._cached_parse(str(file_path), file_hash)
   ```

### Problem: Memory usage too high

**Symptoms:**
```
MemoryError: Unable to allocate array
```

**Solutions:**

1. **Implement memory limits:**
   ```python
   import psutil
   
   def check_memory_usage(self):
       """Check current memory usage."""
       process = psutil.Process()
       memory_mb = process.memory_info().rss / 1024 / 1024
       
       if memory_mb > 1000:  # 1GB limit
           # Clear caches
           self._clear_caches()
           import gc
           gc.collect()
   
   def _clear_caches(self):
       """Clear internal caches."""
       if hasattr(self, '_parser_cache'):
           self._parser_cache.clear()
       if hasattr(self, '_language_cache'):
           self._language_cache.clear()
   ```

2. **Use streaming for large batches:**
   ```python
   def parse_files_streaming(self, file_paths):
       """Parse files with streaming to control memory."""
       for file_path in file_paths:
           result = self.parse(file_path)
           yield result
           
           # Clear intermediate results
           del result
           self.check_memory_usage()
   ```

## Configuration Issues

### Problem: Parser not registered

**Symptoms:**
```
No parser found for file extension .rs
```

**Solutions:**

1. **Check parser registration:**
   ```python
   def debug_parser_registry(self):
       """Debug parser registry state."""
       print(f"Registered parsers: {len(self._parsers)}")
       for parser in self._parsers:
           print(f"  - {type(parser).__name__}: {parser.SUPPORTED_EXTENSIONS}")
   
   def verify_parser_registration(self, file_path):
       """Verify parser can handle file."""
       parser = self.get_parser_for_file(file_path)
       if parser:
           print(f"Parser found: {type(parser).__name__}")
           return parser
       else:
           print(f"No parser for {file_path.suffix}")
           return None
   ```

2. **Manual parser registration:**
   ```python
   def register_additional_parsers(self):
       """Register additional parsers manually."""
       try:
           from .rust_parser import RustParser
           self.register(RustParser())
           print("Rust parser registered")
       except ImportError as e:
           print(f"Could not register Rust parser: {e}")
       
       try:
           from .vue_parser import VueParser
           self.register(VueParser())
           print("Vue parser registered")
       except ImportError as e:
           print(f"Could not register Vue parser: {e}")
   ```

3. **Dynamic parser loading:**
   ```python
   def load_parser_dynamically(self, language_name):
       """Load parser dynamically based on language."""
       parser_map = {
           'rust': 'rust_parser.RustParser',
           'go': 'go_parser.GoParser',
           'vue': 'vue_parser.VueParser'
       }
       
       if language_name in parser_map:
           module_path = parser_map[language_name]
           try:
               module_name, class_name = module_path.rsplit('.', 1)
               module = __import__(f'claude_indexer.analysis.{module_name}', 
                                 fromlist=[class_name])
               parser_class = getattr(module, class_name)
               return parser_class()
           except Exception as e:
               print(f"Failed to load {language_name} parser: {e}")
       
       return None
   ```

## Debugging Tools

### Debug Script Template

```python
#!/usr/bin/env python3
"""Debug script for tree-sitter parsing issues."""

import sys
from pathlib import Path
from tree_sitter_language_pack import get_language, get_language_list
from tree_sitter import Parser


def debug_language_pack():
    """Debug language pack installation."""
    print("=== Language Pack Debug ===")
    try:
        languages = get_language_list()
        print(f"Available languages: {len(languages)}")
        print(f"Sample languages: {languages[:10]}")
        
        # Test common languages
        test_langs = ['javascript', 'typescript', 'python', 'rust', 'go']
        for lang in test_langs:
            try:
                get_language(lang)
                print(f"✓ {lang}")
            except Exception as e:
                print(f"✗ {lang}: {e}")
                
    except Exception as e:
        print(f"Language pack error: {e}")


def debug_parser_creation(language_name):
    """Debug parser creation for specific language."""
    print(f"\n=== Parser Debug: {language_name} ===")
    try:
        language = get_language(language_name)
        print(f"Language object: {type(language)}")
        print(f"Language attributes: {dir(language)}")
        
        parser = Parser(language)
        print(f"Parser created successfully")
        
        return parser
        
    except Exception as e:
        print(f"Parser creation failed: {e}")
        return None


def debug_file_parsing(file_path, language_name):
    """Debug parsing of specific file."""
    print(f"\n=== File Parse Debug: {file_path} ===")
    
    parser = debug_parser_creation(language_name)
    if not parser:
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"File size: {len(content)} characters")
        
        tree = parser.parse(bytes(content, "utf8"))
        print(f"Parse successful: {tree.root_node.type != 'ERROR'}")
        
        # Print parse tree (limited depth)
        def print_tree(node, depth=0):
            if depth < 3:
                print("  " * depth + f"{node.type}: {node.text.decode('utf8', errors='ignore')[:50]}")
                for child in node.children:
                    print_tree(child, depth + 1)
        
        print("\nParse tree:")
        print_tree(tree.root_node)
        
        # Collect node types
        def collect_node_types(node, types=None):
            if types is None:
                types = set()
            types.add(node.type)
            for child in node.children:
                collect_node_types(child, types)
            return types
        
        node_types = collect_node_types(tree.root_node)
        print(f"\nNode types found: {sorted(node_types)}")
        
    except Exception as e:
        print(f"File parsing failed: {e}")


def main():
    """Main debug function."""
    if len(sys.argv) < 2:
        print("Usage: debug_parser.py <language> [file_path]")
        print("Example: debug_parser.py rust test.rs")
        return
    
    language_name = sys.argv[1]
    file_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    debug_language_pack()
    debug_parser_creation(language_name)
    
    if file_path:
        debug_file_parsing(file_path, language_name)


if __name__ == "__main__":
    main()
```

### Usage Examples

```bash
# Debug language pack installation
python debug_parser.py rust

# Debug file parsing
python debug_parser.py rust src/main.rs

# Debug TSX parsing
python debug_parser.py tsx components/App.tsx

# Debug Vue parsing
python debug_parser.py vue components/HelloWorld.vue
```

## Common Error Messages

### Error Reference Table

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `ImportError: No module named 'tree_sitter_language_pack'` | Package not installed | `pip install tree-sitter-language-pack` |
| `ValueError: Language 'xyz' is not available` | Language not in pack | Check available languages, use fallback |
| `'Language' object has no attribute 'language'` | Language object mismatch | Fix Language object initialization |
| `Parse failure: an integer is required` | Double Language wrapping | Remove duplicate Language() calls |
| `No entities extracted` | Wrong node types | Debug parse tree, verify node types |
| `MemoryError: Unable to allocate` | File too large | Implement size limits, streaming |
| `No parser found for extension` | Parser not registered | Register parser in ParserRegistry |

### Quick Fixes

```bash
# Quick installation fix
pip install --upgrade tree-sitter tree-sitter-language-pack

# Quick parser test
python -c "
from tree_sitter_language_pack import get_language
from tree_sitter import Parser
lang = get_language('rust')
parser = Parser(lang)
tree = parser.parse(b'fn main() {}')
print('Success' if tree.root_node.type != 'ERROR' else 'Failed')
"

# Quick file test
python -c "
from claude_indexer.analysis.rust_parser import RustParser
from pathlib import Path
parser = RustParser()
result = parser.parse(Path('test.rs'))
print(f'Success: {result.success}, Entities: {len(result.entities)}')
"
```

---

*This troubleshooting guide covers the most common issues. For additional help, check the [GitHub Issues](https://github.com/your-repo/issues) or create a new issue with your specific problem.*