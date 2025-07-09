"""Base classes and interfaces for text embedding generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import time
import logging


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    
    text: str
    embedding: List[float]
    
    # Metadata
    model: str = ""
    token_count: int = 0
    processing_time: float = 0.0
    cost_estimate: float = 0.0
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        """Check if embedding generation was successful."""
        return self.error is None and len(self.embedding) > 0
    
    @property
    def dimension(self) -> int:
        """Get the dimensionality of the embedding vector."""
        return len(self.embedding)


class Embedder(ABC):
    """Abstract base class for text embedding generators."""
    
    @abstractmethod
    def embed_text(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        pass
    
    @abstractmethod
    def get_max_tokens(self) -> int:
        """Get maximum token limit for input text."""
        pass
    
    def truncate_text(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate text to fit within token limits."""
        if max_tokens is None:
            max_tokens = self.get_max_tokens()
        
        # Simple approximation: ~4 characters per token for English
        max_chars = max_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        # Truncate at word boundary when possible
        truncated = text[:max_chars]
        last_space = truncated.rfind(' ')
        
        if last_space > max_chars * 0.8:  # Don't lose too much content
            truncated = truncated[:last_space]
        
        return truncated + "..."


class RetryableEmbedder(Embedder):
    """Base class for embedders that support retry logic."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff with jitter."""
        import random
        
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.1, 0.3) * delay
        return delay + jitter
    
    def _should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if an error should trigger a retry."""
        if attempt >= self.max_retries:
            return False
        
        # Retry on common transient errors
        error_str = str(error).lower()
        transient_errors = [
            "rate limit",
            "timeout", 
            "connection",
            "temporary",
            "503",
            "502",
            "429"
        ]
        
        return any(err in error_str for err in transient_errors)
    
    def _embed_with_retry(self, operation_func, *args, **kwargs) -> Any:
        """Execute embedding operation with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return operation_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if not self._should_retry(e, attempt):
                    break
                
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    print(f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
        
        # If we get here, all retries failed
        raise last_error


class CachingEmbedder(Embedder):
    """Wrapper that adds caching to any embedder."""
    
    def __init__(self, embedder: Embedder, max_cache_size: int = 10000):
        self.embedder = embedder
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, EmbeddingResult] = {}
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        import hashlib
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    def _add_to_cache(self, text: str, result: EmbeddingResult):
        """Add result to cache with size management."""
        if len(self._cache) >= self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(self._cache.keys())[:len(self._cache) // 2]
            for key in keys_to_remove:
                del self._cache[key]
        
        cache_key = self._get_cache_key(text)
        self._cache[cache_key] = result
    
    def embed_text(self, text: str) -> EmbeddingResult:
        """Embed text with caching."""
        cache_key = self._get_cache_key(text)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = self.embedder.embed_text(text)
        
        if result.success:
            self._add_to_cache(text, result)
        
        return result
    
    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Embed batch with caching."""
        results = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache for each text
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                results.append(self._cache[cache_key])
            else:
                results.append(None)  # Placeholder
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # Embed uncached texts
        if uncached_texts:
            uncached_results = self.embedder.embed_batch(uncached_texts)
            
            # Fill in results and update cache
            for i, result in enumerate(uncached_results):
                original_index = uncached_indices[i]
                results[original_index] = result
                
                if result.success:
                    self._add_to_cache(uncached_texts[i], result)
        
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model info from wrapped embedder."""
        info = self.embedder.get_model_info()
        info["caching_enabled"] = True
        info["cache_size"] = len(self._cache)
        info["max_cache_size"] = self.max_cache_size
        return info
    
    def get_max_tokens(self) -> int:
        """Get max tokens from wrapped embedder."""
        return self.embedder.get_max_tokens()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.max_cache_size,
            "cache_hit_ratio": getattr(self, '_hit_count', 0) / max(getattr(self, '_total_requests', 1), 1)
        }
