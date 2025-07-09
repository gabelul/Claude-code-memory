"""Configuration models for both global and project settings."""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, validator
from .config_schema import ProjectConfig
from ..indexer_logging import get_logger

logger = get_logger()


class IndexerConfig(BaseModel):
    """Global configuration model with validation."""
    
    # API Keys
    openai_api_key: str = Field(default="")
    voyage_api_key: str = Field(default="")
    qdrant_api_key: str = Field(default="default-key")
    
    # URLs and Endpoints
    qdrant_url: str = Field(default="http://localhost:6333")
    openai_base_url: Optional[str] = None
    
    # Collection Management
    collection_name: str = Field(default="default")
    
    # Component Types
    embedder_type: str = Field(default="openai")
    embedding_provider: str = Field(default="openai")  # For compatibility
    voyage_model: str = Field(default="voyage-3-lite")
    storage_type: str = Field(default="qdrant")
    
    # Indexing Behavior
    indexer_debug: bool = Field(default=False)
    indexer_verbose: bool = Field(default=True)
    debounce_seconds: float = Field(default=2.0)
    
    # Watcher Settings
    include_patterns: list = Field(default_factory=lambda: [
        '*.py', '*.pyi', '*.js', '*.jsx', '*.ts', '*.tsx', 
        '*.html', '*.htm', '*.css', '*.md', '*.txt', '*.json'
    ])
    exclude_patterns: list = Field(default_factory=lambda: [
        '*.pyc', '__pycache__', '.git', '.venv', 'node_modules', 
        'dist', 'build', '*.min.js', '.env', '*.log', '.mypy_cache',
        'qdrant_storage', 'backups', 'chat_reports', '*.egg-info',
        'settings.txt', '.claude-indexer'
    ])
    
    # File Processing
    include_markdown: bool = Field(default=True)
    include_tests: bool = Field(default=False)
    max_file_size: int = Field(default=1048576, ge=1024)  # 1MB default, min 1KB
    
    # Performance Settings
    batch_size: int = Field(default=50, ge=1, le=1000)
    max_concurrent_files: int = Field(default=10, ge=1, le=100)
    
    # State Management
    state_directory: Optional[Path] = Field(default=None)
    
    @classmethod
    def from_env(cls) -> 'IndexerConfig':
        """Create config with environment variable overrides."""
        return cls(
            openai_api_key=os.environ.get('OPENAI_API_KEY', ''),
            voyage_api_key=os.environ.get('VOYAGE_API_KEY', ''),
            qdrant_api_key=os.environ.get('QDRANT_API_KEY', 'default-key'),
            qdrant_url=os.environ.get('QDRANT_URL', 'http://localhost:6333'),
            openai_base_url=os.environ.get('OPENAI_BASE_URL'),
            embedding_provider=os.environ.get('EMBEDDING_PROVIDER', 'openai'),
            voyage_model=os.environ.get('VOYAGE_MODEL', 'voyage-3-lite'),
        )


# Project configuration models (existing ones)
class FilePatterns(BaseModel):
    """File patterns for include/exclude."""
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    
    @validator('include', 'exclude')
    def validate_patterns(cls, v):
        if not isinstance(v, list):
            raise ValueError("Patterns must be a list")
        for pattern in v:
            if not isinstance(pattern, str):
                raise ValueError("All patterns must be strings")
        return v


class JavaScriptParserConfig(BaseModel):
    """JavaScript parser specific configuration."""
    use_ts_server: bool = Field(default=False)
    jsx: bool = Field(default=True)
    include_node_modules: bool = Field(default=False)


class PythonParserConfig(BaseModel):
    """Python parser specific configuration."""
    include_docstrings: bool = Field(default=True)
    include_type_hints: bool = Field(default=True)
    jedi_environment: Optional[str] = Field(default=None)


class IndexingConfig(BaseModel):
    """Indexing behavior configuration."""
    file_patterns: Optional[FilePatterns] = Field(default=None)
    max_file_size: Optional[int] = Field(default=None)
    include_hidden: bool = Field(default=False)
    
    parser_config: Dict[str, Union[JavaScriptParserConfig, PythonParserConfig, Dict[str, Any]]] = Field(
        default_factory=dict
    )


class WatcherConfig(BaseModel):
    """File watcher configuration."""
    enabled: bool = Field(default=True)
    debounce_seconds: Optional[float] = Field(default=None)
    ignore_patterns: List[str] = Field(default_factory=lambda: [".git", "__pycache__", "node_modules"])


class ProjectInfo(BaseModel):
    """Project metadata."""
    name: str
    collection: str
    description: Optional[str] = Field(default="")
    created_at: Optional[str] = Field(default=None)
    
    @validator('name', 'collection')
    def validate_names(cls, v):
        if not v or not v.strip():
            raise ValueError("Name and collection cannot be empty")
        return v.strip()


# ProjectConfig is imported from config_schema to avoid duplication
