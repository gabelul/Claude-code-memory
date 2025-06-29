"""Unified configuration package."""

# Main configuration exports
from .models import IndexerConfig
from .config_loader import ConfigLoader, load_config
from .legacy import load_legacy_settings, create_default_settings_file

# Project configuration exports
from .config_schema import (
    ProjectConfig, 
    ProjectInfo, 
    IndexingConfig, 
    WatcherConfig, 
    FilePatterns,
    ParserConfig,
    JavaScriptParserConfig,
    JSONParserConfig,
    TextParserConfig,
    YAMLParserConfig,
    MarkdownParserConfig
)
from .project_config import ProjectConfigManager

__all__ = [
    # Main configuration
    "IndexerConfig",
    "load_config",
    "load_legacy_settings",
    "create_default_settings_file",
    "ConfigLoader",
    
    # Project configuration  
    "ProjectConfig",
    "ProjectInfo", 
    "IndexingConfig",
    "WatcherConfig",
    "FilePatterns",
    "ParserConfig",
    "JavaScriptParserConfig",
    "JSONParserConfig", 
    "TextParserConfig",
    "YAMLParserConfig",
    "MarkdownParserConfig",
    "ProjectConfigManager",
]