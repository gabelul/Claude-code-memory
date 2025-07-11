# Tree-Sitter Language Pack Overview

## What is tree-sitter-language-pack?

The `tree-sitter-language-pack` is a comprehensive Python package that provides **165+ pre-compiled language grammars** for tree-sitter parsing. Instead of installing individual packages like `tree-sitter-javascript`, `tree-sitter-python`, etc., you get all languages in a single dependency.

## Why We Migrated

### Before: Individual Packages
```python
# Old approach - multiple dependencies
pip install tree-sitter-javascript
pip install tree-sitter-typescript  
pip install tree-sitter-python
pip install tree-sitter-rust
# ... and so on for each language
```

### After: Language Pack
```python
# New approach - single dependency
pip install tree-sitter-language-pack

# Access any language
from tree_sitter_language_pack import get_language
js_lang = get_language("javascript")
ts_lang = get_language("typescript")
rust_lang = get_language("rust")
```

## Key Benefits

### 🎯 Unified Interface
- **Consistent API**: All languages use `get_language("name")`
- **No Version Conflicts**: Single package manages all language versions
- **Simplified Dependencies**: One line in requirements.txt

### 🚀 Comprehensive Coverage
- **165+ Languages**: From mainstream to niche languages
- **Always Up-to-Date**: Regular updates with latest grammar versions
- **Future-Proof**: New languages added automatically

### 🔧 Developer Experience
- **Easy Discovery**: See all available languages in one place
- **Reduced Setup**: No need to research individual package names
- **Better Testing**: Consistent behavior across all languages

## Architecture Integration

### Fallback Pattern
Our implementation uses a robust fallback pattern:

```python
def __init__(self, config=None):
    try:
        # Try language pack first (preferred)
        from tree_sitter_language_pack import get_language
        js_language = get_language("javascript")
        super().__init__(js_language, config)
    except ImportError:
        # Fallback to individual package
        import tree_sitter_javascript as tsjs
        super().__init__(tsjs, config)
```

### Language Detection
Languages are detected by **file extension**:

```python
SUPPORTED_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
```

### Parser Selection
The `ParserRegistry` automatically selects the appropriate parser based on file extension:

```
example.tsx → JavaScriptParser (with TSX grammar)
example.py  → PythonParser
example.rs  → RustParser (when implemented)
```

## Available Languages

The language pack includes support for:

### Web Technologies
- JavaScript, TypeScript, JSX, TSX
- HTML, CSS, SCSS, SASS
- JSON, YAML, TOML, XML

### Systems Programming
- Rust, Go, C, C++, Zig
- Java, C#, Kotlin, Swift

### Functional Languages
- Haskell, OCaml, Elixir, F#
- Clojure, Scheme, Racket

### Data & Query Languages
- SQL, GraphQL, Dockerfile
- Terraform, Jsonnet

### And Many More...
- Python, Ruby, PHP, Perl
- Lua, Julia, R, MATLAB
- Assembly languages, Shell scripts
- Documentation formats (Markdown, LaTeX, reStructuredText)

## Performance Characteristics

### Initialization Speed
- **Language Pack**: ~10ms for first language, ~1ms for subsequent
- **Individual Packages**: ~5ms each (but requires separate installs)

### Memory Usage
- **Language Pack**: ~50MB for all grammars (lazy-loaded)
- **Individual Packages**: ~2-5MB per grammar

### Parse Speed
- **Identical Performance**: No difference in actual parsing speed
- **Grammar Quality**: Same upstream grammars, same parse trees

## Migration Benefits

### For Users
- ✅ Simpler installation and setup
- ✅ Access to 165+ languages immediately
- ✅ Consistent behavior across languages
- ✅ Better error messages and debugging

### For Developers
- ✅ Easier to add new language support
- ✅ Reduced maintenance overhead
- ✅ Consistent patterns across parsers
- ✅ Better testing infrastructure

### For the Project
- ✅ Reduced dependency conflicts
- ✅ Easier distribution and packaging
- ✅ Better community contribution potential
- ✅ Future-proof architecture

## Next Steps

1. **[Current Support](./02-current-support.md)** - See what languages are available now
2. **[Adding Languages](./03-adding-languages.md)** - Learn how to extend support
3. **[Examples](./05-examples.md)** - See real implementations for popular languages

---

*The language pack is maintained by the tree-sitter community and updated regularly with new grammars and improvements.*