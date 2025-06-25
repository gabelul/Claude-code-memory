"""Configuration management with validation and environment variable support."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseSettings, Field, validator


class IndexerConfig(BaseSettings):
    """Configuration model with validation and environment variable support."""
    
    # API Keys
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    qdrant_api_key: str = Field(default="default-key", env="QDRANT_API_KEY")
    
    # URLs and Endpoints
    qdrant_url: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    
    # Indexing Behavior
    indexer_debug: bool = Field(default=False)
    indexer_verbose: bool = Field(default=True)
    debounce_seconds: float = Field(default=2.0, ge=0.1, le=30.0)
    
    # File Processing
    include_markdown: bool = Field(default=True)
    include_tests: bool = Field(default=False)
    max_file_size: int = Field(default=1048576, ge=1024)  # 1MB default, min 1KB
    
    # Performance Settings
    batch_size: int = Field(default=50, ge=1, le=1000)
    max_concurrent_files: int = Field(default=10, ge=1, le=100)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("openai_api_key")
    def validate_openai_key(cls, v):
        if v and not v.startswith("sk-"):
            raise ValueError("OpenAI API key must start with 'sk-'")
        return v
        
    @validator("qdrant_url")
    def validate_qdrant_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Qdrant URL must start with http:// or https://")
        return v


def load_legacy_settings(settings_file: Path) -> Dict[str, Any]:
    """Load configuration from legacy settings.txt format."""
    settings = {}
    
    if not settings_file.exists():
        return settings
        
    try:
        with open(settings_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Convert boolean values
                    if value.lower() in ('true', 'false'):
                        value = value.lower() == 'true'
                    # Convert numeric values
                    elif value.replace('.', '').replace('-', '').isdigit():
                        value = float(value) if '.' in value else int(value)
                    
                    settings[key] = value
    except Exception as e:
        print(f"Warning: Failed to load settings.txt: {e}")
    
    return settings


def load_config(settings_file: Optional[Path] = None, **overrides) -> IndexerConfig:
    """Load configuration from multiple sources with precedence:
    1. Explicit overrides (highest priority)
    2. Environment variables  
    3. settings.txt file
    4. Default values (lowest priority)
    """
    # Default settings file location
    if settings_file is None:
        settings_file = Path(__file__).parent.parent / "settings.txt"
    
    # Load legacy settings if available
    legacy_settings = load_legacy_settings(settings_file)
    
    # Merge with overrides (overrides take precedence)
    merged_settings = {**legacy_settings, **overrides}
    
    # Create config with merged settings
    try:
        config = IndexerConfig(**merged_settings)
    except Exception as e:
        print(f"Warning: Configuration validation failed: {e}")
        # Fall back to defaults if validation fails
        config = IndexerConfig(**overrides)
    
    return config


def create_default_settings_file(path: Path) -> None:
    """Create a default settings.txt file template."""
    template = """# Claude Indexer Configuration
# Lines starting with # are comments

# API Configuration
openai_api_key=your-openai-api-key-here
qdrant_api_key=your-qdrant-api-key
qdrant_url=http://localhost:6333

# Indexing Behavior  
indexer_debug=false
indexer_verbose=true
debounce_seconds=2.0

# File Processing
include_markdown=true
include_tests=false
max_file_size=1048576

# Performance Settings
batch_size=50
max_concurrent_files=10
"""
    
    try:
        with open(path, 'w') as f:
            f.write(template)
        print(f"Created default settings file: {path}")
    except Exception as e:
        print(f"Failed to create settings file: {e}")