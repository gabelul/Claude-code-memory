# Tree-Sitter Language Pack Documentation

Welcome to the comprehensive documentation for tree-sitter language pack integration in claude-indexer.

## 📚 Documentation Structure

| Document | Description |
|----------|-------------|
| [Overview](./01-overview.md) | Introduction to tree-sitter-language-pack and its benefits |
| [Current Support](./02-current-support.md) | Languages and parsers currently supported |
| [Adding Languages](./03-adding-languages.md) | Step-by-step guide to add new language parsers |
| [Architecture](./04-architecture.md) | Design patterns and technical architecture |
| [Examples](./05-examples.md) | Practical examples for popular languages |
| [Troubleshooting](./06-troubleshooting.md) | Common issues and solutions |

## 🚀 Quick Start

```bash
# Install the language pack
pip install tree-sitter-language-pack

# Test language support
python -c "from tree_sitter_language_pack import get_language; print(get_language('tsx'))"
```

## 🎯 Key Benefits

- **165+ Languages**: Single package provides comprehensive language support
- **Unified API**: Consistent `get_language("name")` interface for all languages
- **Easy Expansion**: Add new languages with minimal code
- **Better Maintenance**: One dependency instead of dozens of individual packages

## 📖 What You'll Learn

1. **How It Works**: Understanding the language pack architecture
2. **Current Capabilities**: What languages are supported out-of-the-box
3. **Extension Guide**: How to add support for new languages (Vue, Svelte, Go, Rust, etc.)
4. **Best Practices**: Design patterns and troubleshooting techniques
5. **Real Examples**: Working code for popular language integrations

## 🔗 External Resources

- [Tree-sitter Language Pack Repository](https://github.com/grantjenks/py-tree-sitter-language-pack)
- [Tree-sitter Official Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Available Language Grammars](https://tree-sitter.github.io/tree-sitter/#available-parsers)

---

*This documentation is automatically updated with each release. Last updated: $(date)*