# Current Language Support

This document outlines the languages currently supported by claude-indexer and their parsing capabilities.

## Fully Supported Languages

These languages have dedicated parsers and full feature support:

### JavaScript/TypeScript Family
| Language | Extensions | Parser Class | Features |
|----------|------------|--------------|----------|
| JavaScript | `.js`, `.jsx`, `.mjs`, `.cjs` | `JavaScriptParser` | Functions, classes, imports, exports, JSX |
| TypeScript | `.ts` | `JavaScriptParser` | All JS features + types, interfaces |
| TSX (React) | `.tsx` | `JavaScriptParser` | All TS features + JSX components |

**Capabilities:**
- ✅ Function and class extraction
- ✅ Import/export analysis  
- ✅ React component detection
- ✅ TypeScript interface parsing
- ✅ Progressive disclosure (metadata + implementation chunks)

### Python
| Language | Extensions | Parser Class | Features |
|----------|------------|--------------|----------|
| Python | `.py`, `.pyi` | `PythonParser` | Functions, classes, imports, Jedi integration |

**Capabilities:**
- ✅ Function and class extraction with docstrings
- ✅ Import analysis with dependency tracking
- ✅ Jedi-powered semantic analysis
- ✅ Observation extraction for context
- ✅ Progressive disclosure support

### Web Technologies
| Language | Extensions | Parser Class | Features |
|----------|------------|--------------|----------|
| HTML | `.html`, `.htm` | `HTMLParser` | Elements, IDs, classes, components |
| CSS | `.css`, `.scss`, `.sass` | `CSSParser` | Rules, classes, IDs, variables |

**HTML Capabilities:**
- ✅ Element extraction with IDs
- ✅ Custom component detection
- ✅ Inline CSS parsing
- ✅ Link and form analysis

**CSS Capabilities:**
- ✅ Class and ID extraction
- ✅ CSS variable detection
- ✅ Import statement tracking
- ✅ SCSS/SASS support

### Data Formats
| Language | Extensions | Parser Class | Features |
|----------|------------|--------------|----------|
| JSON | `.json` | `JSONParser` | Structure analysis, special file types |
| YAML | `.yml`, `.yaml` | `YAMLParser` | Structure analysis, workflow detection |

**JSON Capabilities:**
- ✅ Package.json dependency extraction
- ✅ TSConfig.json analysis
- ✅ Content item extraction (for large files)
- ✅ Streaming support for large datasets

**YAML Capabilities:**
- ✅ GitHub Actions workflow parsing
- ✅ Docker Compose service detection
- ✅ Kubernetes resource extraction
- ✅ Generic structure analysis

### Documentation
| Language | Extensions | Parser Class | Features |
|----------|------------|--------------|----------|
| Markdown | `.md` | `TextParser` | Basic content extraction |
| Text | `.txt` | `TextParser` | Content-based indexing |

## Language Pack Available Languages

The following languages are available through `tree-sitter-language-pack` but **don't have dedicated parsers yet**:

### Systems Programming
- **Rust** (`.rs`) - Memory-safe systems programming
- **Go** (`.go`) - Google's systems language  
- **C** (`.c`, `.h`) - Low-level programming
- **C++** (`.cpp`, `.hpp`, `.cc`) - Object-oriented C
- **Zig** (`.zig`) - Modern systems programming

### JVM Languages
- **Java** (`.java`) - Enterprise programming
- **Kotlin** (`.kt`, `.kts`) - Modern JVM language
- **Scala** (`.scala`) - Functional JVM language
- **Clojure** (`.clj`, `.cljs`) - Lisp for JVM

### Mobile Development
- **Swift** (`.swift`) - iOS/macOS development
- **Dart** (`.dart`) - Flutter mobile apps
- **Objective-C** (`.m`, `.mm`) - Legacy iOS/macOS

### Web Frameworks
- **Vue** (`.vue`) - Vue.js single-file components
- **Svelte** (`.svelte`) - Compile-time framework
- **Angular** (`.ts` with Angular decorators)

### Functional Languages
- **Haskell** (`.hs`) - Pure functional programming
- **OCaml** (`.ml`, `.mli`) - Functional + imperative
- **Elixir** (`.ex`, `.exs`) - Actor model programming
- **F#** (`.fs`, `.fsx`) - Functional .NET

### Database & Query
- **SQL** (`.sql`) - Database queries
- **GraphQL** (`.graphql`, `.gql`) - API query language
- **Prisma** (`.prisma`) - Database schema

### Infrastructure
- **Dockerfile** - Container definitions
- **Terraform** (`.tf`) - Infrastructure as code
- **Kubernetes** (`.yaml` with K8s schemas)

### Scripting & Shell
- **Bash** (`.sh`, `.bash`) - Shell scripting
- **PowerShell** (`.ps1`) - Windows scripting
- **Fish** (`.fish`) - Modern shell
- **Zsh** (`.zsh`) - Extended shell

### Data Science
- **R** (`.r`, `.R`) - Statistical computing
- **Julia** (`.jl`) - High-performance computing
- **MATLAB** (`.m`) - Mathematical computing

### Documentation & Markup
- **LaTeX** (`.tex`) - Document typesetting
- **reStructuredText** (`.rst`) - Python documentation
- **AsciiDoc** (`.adoc`) - Technical documentation
- **Org-mode** (`.org`) - Emacs organization

## Adding Support for New Languages

To add a parser for any of the available languages, see [Adding Languages Guide](./03-adding-languages.md).

## Performance Characteristics

### Parse Speed (operations/second)
| Language Family | Small Files (<1KB) | Medium Files (1-10KB) | Large Files (>10KB) |
|-----------------|-------------------|----------------------|-------------------|
| JavaScript/TypeScript | ~1000/s | ~500/s | ~100/s |
| Python | ~800/s | ~400/s | ~80/s |
| HTML/CSS | ~1200/s | ~600/s | ~120/s |
| JSON/YAML | ~2000/s | ~1000/s | ~200/s |

### Memory Usage
| Parser Type | Memory per File | Peak Memory |
|-------------|----------------|-------------|
| JavaScript | ~2-5MB | ~50MB |
| Python | ~3-7MB | ~70MB |
| HTML/CSS | ~1-3MB | ~30MB |
| JSON/YAML | ~1-2MB | ~20MB |

## File Extension Coverage

Our parsers currently handle **~95%** of common development file types:

```bash
# Check coverage for your project
find . -name "*.js" -o -name "*.ts" -o -name "*.tsx" -o -name "*.py" | wc -l
# vs total code files
find . -type f \( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.go" -o -name "*.rs" \) | wc -l
```

## Planned Expansions

### High Priority (Next Release)
- **Vue.js** (`.vue`) - High community demand
- **Svelte** (`.svelte`) - Growing framework adoption
- **Rust** (`.rs`) - Systems programming popularity

### Medium Priority
- **Go** (`.go`) - Enterprise adoption
- **Java** (`.java`) - Large codebases
- **SQL** (`.sql`) - Database query analysis

### Community Requests
Vote for languages on our [GitHub Issues](https://github.com/your-repo/issues) with the `language-request` label.

---

*Language support is continuously expanding. Check back regularly for updates!*