"""Dummy embedder for MCP command generation - no API calls."""

import time
from typing import List
from .base import Embedder, EmbeddingResult


class DummyEmbedder(Embedder):
    """Dummy embedder that returns zero vectors without API calls.
    
    Used with MCP command generator where embeddings aren't needed.
    """
    
    def __init__(self, dimension: int = 1536):
        """Initialize dummy embedder.
        
        Args:
            dimension: Size of dummy vectors to generate
        """
        self.dimension = dimension
    
    def embed_text(self, text: str) -> EmbeddingResult:
        """Generate dummy embedding without API calls."""
        start_time = time.time()
        
        # Create zero vector of specified dimension
        dummy_embedding = [0.0] * self.dimension
        
        return EmbeddingResult(
            text=text,
            embedding=dummy_embedding,
            model="dummy",
            token_count=len(text.split()),
            processing_time=time.time() - start_time,
            cost_estimate=0.0
        )
    
    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate dummy embeddings for multiple texts."""
        return [self.embed_text(text) for text in texts]
    
    def get_embedding_dimension(self) -> int:
        """Return embedding dimension."""
        return self.dimension
    
    def validate_config(self) -> bool:
        """Always valid - no API keys needed."""
        return True
    
    def get_max_tokens(self) -> int:
        """Return max tokens for dummy embedder."""
        return 999999  # Unlimited for dummy embedder
    
    def get_model_info(self) -> dict:
        """Return dummy model information."""
        return {
            "provider": "dummy",
            "model": "zero-vector",
            "dimension": self.dimension,
            "max_tokens": 999999,
            "cost_per_token": 0.0
        }