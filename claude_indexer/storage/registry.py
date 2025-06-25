"""Registry for managing storage backend instances."""

from typing import Dict, Any, Type, List
from .base import VectorStore, CachingVectorStore
from .qdrant import QdrantStore, QDRANT_AVAILABLE
from .mcp import MCPStore, MCP_AVAILABLE


class StorageRegistry:
    """Registry for creating and managing vector store instances."""
    
    def __init__(self):
        self._stores: Dict[str, Type[VectorStore]] = {}
        self._register_default_stores()
    
    def _register_default_stores(self):
        """Register default storage implementations."""
        if QDRANT_AVAILABLE:
            self.register("qdrant", QdrantStore)
        if MCP_AVAILABLE:
            self.register("mcp", MCPStore)
    
    def register(self, name: str, store_class: Type[VectorStore]):
        """Register a storage backend."""
        self._stores[name] = store_class
    
    def create_store(self, backend: str, config: Dict[str, Any],
                    enable_caching: bool = True) -> VectorStore:
        """Create a vector store instance from configuration."""
        if backend not in self._stores:
            available = list(self._stores.keys())
            raise ValueError(f"Unknown storage backend: {backend}. Available: {available}")
        
        store_class = self._stores[backend]
        
        try:
            # Create base store
            store = store_class(**config)
            
            # Wrap with caching if enabled
            if enable_caching:
                cache_size = config.get("cache_size", 1000)
                store = CachingVectorStore(store, max_cache_size=cache_size)
            
            return store
            
        except Exception as e:
            raise RuntimeError(f"Failed to create {backend} store: {e}")
    
    def get_available_backends(self) -> List[str]:
        """Get list of available storage backends."""
        return list(self._stores.keys())


def create_store_from_config(config: Dict[str, Any]) -> VectorStore:
    """Create vector store from configuration dictionary."""
    registry = StorageRegistry()
    
    backend = config.get("backend", "qdrant")
    enable_caching = config.get("enable_caching", True)
    
    # Extract backend-specific config
    backend_config = {k: v for k, v in config.items() 
                     if k not in ["backend", "enable_caching", "cache_size"]}
    
    return registry.create_store(backend, backend_config, enable_caching)