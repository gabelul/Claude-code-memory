# Migration Guide: Claude Code Memory v2.8

## Overview

This guide helps you migrate from previous versions to Claude Code Memory v2.8, which includes major performance improvements and breaking changes.

## ⚡ What's New in v2.8

### Major Improvements
- **90% Token Reduction**: Revolutionary content deduplication system
- **165+ Languages**: Universal Tree-sitter language pack integration
- **Enhanced JavaScript/TypeScript**: Advanced variable extraction with destructuring patterns
- **Atomic Operations**: Race condition prevention with bulletproof reliability
- **Collision-Free Relations**: Fixed 41.3% chunk ID collision rate

### Breaking Changes
- Content deduplication now **enabled by default** (`use_unified_processor: true`)
- Enhanced JavaScript parsing with destructuring support
- Improved observation extractor with JSDoc and cross-language support
- Optimized file exclusion patterns (proper .git filtering)

## 🔄 Migration Steps

### Step 1: Update Dependencies

```bash
# Update to latest version
git pull origin main

# Update Python dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Verify tiktoken is installed for accurate token counting
pip install tiktoken
```

### Step 2: Update Configuration

The new default configuration enables content deduplication. If you have a custom configuration file, update it:

```json
{
  "use_unified_processor": true,
  "embedder_type": "openai",
  "openai_model": "text-embedding-3-small"
}
```

### Step 3: Re-index Your Projects

**Important**: Due to the architectural changes, you should re-index your projects to take advantage of the new features:

```bash
# Clear existing collection and re-index
claude-indexer index -p /path/to/your/project -c your-project-name --clear

# Or start fresh with new collection name
claude-indexer index -p /path/to/your/project -c your-project-v2
```

### Step 4: Update MCP Configuration

If you're using a custom MCP configuration, update it to use the new collection:

```bash
# Update MCP server configuration
claude-indexer add-mcp -c your-project-name -p /path/to/your/project
```

### Step 5: Update CLI Commands

Update your scripts and workflows to use the explicit `index` command:

```bash
# Old (still works but deprecated)
claude-indexer -p /path -c collection

# New (recommended)
claude-indexer index -p /path -c collection
```

## 🎯 Key Configuration Changes

### Content Deduplication (Default: Enabled)

```json
{
  "use_unified_processor": true
}
```

Benefits:
- 90% token reduction
- Faster embedding generation
- Reduced storage costs
- Better performance

### Enhanced JavaScript Parsing

New features automatically enabled:
- Destructuring pattern support
- Enhanced variable extraction
- JSDoc documentation parsing
- Cross-language relations

### File Exclusion Improvements

Better default patterns:
```json
{
  "exclude_patterns": [
    "*.pyc", "__pycache__", ".git/**", ".venv", "node_modules", 
    "dist", "build", "*.min.js", ".env", "*.log", ".mypy_cache",
    "qdrant_storage", "backups", "chat_reports", "*.egg-info",
    "settings.txt", ".claude-indexer"
  ]
}
```

## 🔧 Troubleshooting

### Token Limit Errors

If you encounter token limit errors with OpenAI embeddings:

```bash
# The system now uses accurate token counting with tiktoken
# This should resolve previous token limit issues automatically
```

### Performance Issues

```bash
# Clear and re-index with new deduplication system
claude-indexer index -p /path -c collection --clear-all

# Check that deduplication is enabled
claude-indexer show-config -p /path
```

### Missing Entities

```bash
# Enhanced parsers may extract different entities
# Re-index to get the latest entity extraction
claude-indexer index -p /path -c collection --clear
```

## 🎨 New Features You Can Use

### Entity-Specific Graph Filtering

```python
# Focus on specific entities instead of massive project graphs
mcp__your-project-memory__read_graph(entity="AuthService", mode="smart")
```

### Unified Search with Enhanced Filtering

```python
# 90% faster metadata search
mcp__your-project-memory__search_similar("pattern", entityTypes=["metadata"])

# Mixed search with OR logic
mcp__your-project-memory__search_similar("pattern", entityTypes=["function", "metadata"])
```

### Advanced Language Support

```bash
# Now supports 165+ languages automatically
claude-indexer index -p /any-language-project -c multi-lang
```

## 📦 Backwards Compatibility

### What Still Works
- All existing CLI commands
- Existing MCP configurations
- Previous project structures
- Manual memory entries

### What Changed
- Default configuration values
- Internal chunk structure (transparent to users)
- Enhanced parsing may extract different entities
- Better performance with same functionality

## 💡 Recommendations

### For New Projects
- Use the latest defaults (no configuration needed)
- Take advantage of enhanced language support
- Use entity-specific graph filtering for better performance

### For Existing Projects
- Re-index to get performance benefits
- Update CLI scripts to use explicit `index` command
- Consider using new filtering features for better debugging

### For Teams
- Document the migration in your project README
- Update CI/CD scripts to use new CLI format
- Share the migration guide with team members

## 🎯 Performance Improvements You'll See

- **90% Token Reduction**: Dramatically faster embedding generation
- **15x Faster Incremental Updates**: Smart change detection
- **3.99ms Search Response**: Blazing fast semantic search
- **Atomic Operations**: No more race conditions during indexing
- **Collision-Free Relations**: Reliable relationship tracking

## 🔄 Rolling Back (If Needed)

If you encounter issues, you can temporarily roll back:

```bash
# Disable deduplication in configuration
{
  "use_unified_processor": false
}

# Or use a specific older collection
claude-indexer index -p /path -c project-name-old
```

## 📞 Support

If you encounter issues during migration:

1. Check the [troubleshooting section](#troubleshooting)
2. Review your configuration with `claude-indexer show-config`
3. Try re-indexing with `--clear-all` flag
4. Report issues at [GitHub Issues](https://github.com/Durafen/Claude-code-memory/issues)

## 🚀 Next Steps

After successful migration:
1. Explore the new entity-specific graph filtering
2. Try the enhanced JavaScript/TypeScript parsing
3. Experiment with unified search filtering
4. Update your team's documentation
5. Consider optimizing your configuration for your specific use case

---

*This migration guide covers the major changes in v2.8. For detailed technical information, see [CLAUDE.md](CLAUDE.md).*