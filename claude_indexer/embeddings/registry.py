"""Registry for managing embedder instances and configurations."""

from typing import Dict, Any, Optional, Type
from .base import Embedder, CachingEmbedder, RetryableEmbedder
from .openai import OpenAIEmbedder, OPENAI_AVAILABLE
from .voyage import VoyageEmbedder, VOYAGE_AVAILABLE


class EmbedderRegistry:
    """Registry for creating and managing embedders."""
    
    def __init__(self):
        self._embedders: Dict[str, Type[Embedder]] = {}
        self._register_default_embedders()
    
    def _register_default_embedders(self):
        """Register default embedder implementations."""
        if OPENAI_AVAILABLE:
            self.register("openai", OpenAIEmbedder)
        if VOYAGE_AVAILABLE:
            self.register("voyage", VoyageEmbedder)
        
    
    def register(self, name: str, embedder_class: Type[Embedder]):
        """Register an embedder class."""
        self._embedders[name] = embedder_class
    
    def create_embedder(self, provider: str, config: Dict[str, Any], 
                       enable_caching: bool = True) -> Embedder:
        """Create an embedder instance from configuration."""
        if provider not in self._embedders:
            available = list(self._embedders.keys())
            raise ValueError(f"Unknown embedder provider: {provider}. Available: {available}")
        
        embedder_class = self._embedders[provider]
        
        try:
            # Create base embedder
            embedder = embedder_class(**config)
            
            # Wrap with caching if enabled
            if enable_caching:
                cache_size = config.get("cache_size", 10000)
                embedder = CachingEmbedder(embedder, max_cache_size=cache_size)
            
            return embedder
            
        except Exception as e:
            raise RuntimeError(f"Failed to create {provider} embedder: {e}")
    
    def get_available_providers(self) -> list[str]:
        """Get list of available embedder providers."""
        return list(self._embedders.keys())
    
    def get_provider_info(self, provider: str) -> Dict[str, Any]:
        """Get information about a specific provider."""
        if provider not in self._embedders:
            raise ValueError(f"Unknown provider: {provider}")
        
        embedder_class = self._embedders[provider]
        
        # Try to get model info without instantiating
        if hasattr(embedder_class, 'MODELS'):
            return {
                "provider": provider,
                "class": embedder_class.__name__,
                "available_models": list(embedder_class.MODELS.keys()),
                "supports_batch": True,
                "supports_retry": issubclass(embedder_class, RetryableEmbedder)
            }
        
        return {
            "provider": provider,
            "class": embedder_class.__name__,
            "available_models": ["unknown"],
            "supports_batch": hasattr(embedder_class, "embed_batch"),
            "supports_retry": False
        }


def create_embedder_from_config(config: Dict[str, Any]) -> Embedder:
    """Create embedder from configuration dictionary."""
    registry = EmbedderRegistry()
    
    provider = config.get("provider", "openai")
    enable_caching = config.get("enable_caching", True)
    
    # Extract provider-specific config
    provider_config = {k: v for k, v in config.items() 
                      if k not in ["provider", "enable_caching", "cache_size"]}
    
    return registry.create_embedder(provider, provider_config, enable_caching)


# For backward compatibility
def create_openai_embedder(api_key: str, model: str = "text-embedding-3-small",
                          enable_caching: bool = True, **kwargs) -> Embedder:
    """Create OpenAI embedder with default configuration."""
    config = {
        "provider": "openai",
        "api_key": api_key,
        "model": model,
        "enable_caching": enable_caching,
        **kwargs
    }
    return create_embedder_from_config(config)


def create_voyage_embedder(api_key: str, model: str = "voyage-3-lite",
                          enable_caching: bool = True, **kwargs) -> Embedder:
    """Create Voyage AI embedder with default configuration."""
    config = {
        "provider": "voyage",
        "api_key": api_key,
        "model": model,
        "enable_caching": enable_caching,
        **kwargs
    }
    return create_embedder_from_config(config)