"""Base content processor classes."""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Set, Any, TYPE_CHECKING
import hashlib
from .context import ProcessingContext
from .results import ProcessingResult

if TYPE_CHECKING:
    from ..analysis.entities import EntityChunk, RelationChunk


class ContentHashMixin:
    """Mixin for content-addressable storage functionality"""
    
    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Generate SHA256 hash of content"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def check_content_exists(self, collection_name: str, content_hash: str) -> bool:
        """Check if content hash already exists in storage"""
        try:
            # Check if collection exists first
            if not self.vector_store.collection_exists(collection_name):
                return False
                
            # Use vector store's content checking method if available
            if hasattr(self.vector_store, 'check_content_exists'):
                return self.vector_store.check_content_exists(collection_name, content_hash)
            
            # Fallback: assume content doesn't exist if no checking method available
            return False
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.debug(f"Error checking content hash existence: {e}")
            # On connection errors, fall back to processing (safer than skipping)
            return False


class ContentProcessor(ContentHashMixin, ABC):
    """Base class for content processing with deduplication."""
    
    def __init__(self, vector_store, embedder, logger=None):
        self.vector_store = vector_store
        self.embedder = embedder  
        self.logger = logger
    
    @abstractmethod
    def process_batch(self, items: List, context: ProcessingContext) -> ProcessingResult:
        """Process a batch of content items."""
        pass
    
    def check_deduplication(self, items: List, collection_name: str) -> Tuple[List, List]:
        """Universal deduplication logic using content hashes."""
        to_embed = []
        to_skip = []
        
        for item in items:
            # Get content hash from item
            content_hash = self._get_content_hash(item)
            
            if content_hash and self.check_content_exists(collection_name, content_hash):
                to_skip.append(item)
                if self.logger:
                    item_name = getattr(item, 'entity_name', getattr(item, 'name', str(item)))
                    self.logger.debug(f"⚡ Skipping unchanged item: {item_name}")
            else:
                to_embed.append(item)
        
        return to_embed, to_skip    
    
    def _get_content_hash(self, item) -> str:
        """Get content hash from item."""
        # Try to get content hash from vector payload
        if hasattr(item, 'to_vector_payload'):
            payload = item.to_vector_payload()
            if 'content_hash' in payload:
                return payload['content_hash']
        
        # Try to get content directly and compute hash
        if hasattr(item, 'content'):
            return self.compute_content_hash(item.content)
        
        # Try to get observations and compute hash
        if hasattr(item, 'observations') and item.observations:
            content = '\n'.join(item.observations)
            return self.compute_content_hash(content)
        
        # Fallback to empty hash
        return ""
    
    def process_embeddings(self, items: List, item_name: str) -> Tuple[List, Dict]:
        """Generate embeddings with error handling and cost tracking."""
        if not items:
            return [], {'tokens': 0, 'cost': 0.0, 'requests': 0}
        
        # Extract content for embedding
        texts = []
        for item in items:
            if hasattr(item, 'content'):
                texts.append(item.content)
            elif hasattr(item, 'observations') and item.observations:
                texts.append('\n'.join(item.observations))
            else:
                texts.append(str(item))
        
        if self.logger:
            self.logger.debug(f"🔤 Generating embeddings for {len(texts)} {item_name} texts")
        
        # Generate embeddings
        embedding_results = self.embedder.embed_batch(texts)
        
        if self.logger:
            successful = sum(1 for r in embedding_results if r.success)
            self.logger.debug(f"✅ {item_name.title()} embeddings completed: {successful}/{len(embedding_results)} successful")
        
        # Collect cost data
        cost_data = self._collect_embedding_cost_data(embedding_results)
        
        return embedding_results, cost_data    
    
    def create_points(self, items: List, embedding_results: List, collection_name: str, 
                     point_creation_method: str = 'create_chunk_point') -> Tuple[List, int]:
        """Create vector points from items and embeddings."""
        points = []
        failed_count = 0
        
        for item, embedding_result in zip(items, embedding_results):
            if embedding_result.success:
                # Get the appropriate point creation method
                if hasattr(self.vector_store, point_creation_method):
                    point_creator = getattr(self.vector_store, point_creation_method)
                    point = point_creator(item, embedding_result.embedding, collection_name)
                    points.append(point)
                else:
                    # Fallback to default chunk point creation
                    if hasattr(self.vector_store, 'create_chunk_point'):
                        point = self.vector_store.create_chunk_point(item, embedding_result.embedding, collection_name)
                        points.append(point)
                    else:
                        # Final fallback - try to create a basic point
                        point = self._create_basic_point(item, embedding_result.embedding, collection_name)
                        points.append(point)
            else:
                failed_count += 1
                if self.logger:
                    error_msg = getattr(embedding_result, 'error', 'Unknown error')
                    item_name = getattr(item, 'entity_name', getattr(item, 'name', str(item)))
                    self.logger.warning(f"❌ Embedding failed: {item_name} - {error_msg}")
        
        return points, failed_count
    
    def _create_basic_point(self, item, embedding, collection_name):
        """Create a basic vector point as fallback."""
        # This is a basic implementation - should be overridden by vector store specific logic
        payload = item.to_vector_payload() if hasattr(item, 'to_vector_payload') else {'content': str(item)}
        
        # Generate a simple ID
        import uuid
        point_id = str(uuid.uuid4())
        
        return {
            'id': point_id,
            'vector': embedding,
            'payload': payload
        }
    
    def _collect_embedding_cost_data(self, embedding_results: List[Any]) -> Dict[str, Any]:
        """Collect cost data from embedding results."""
        total_tokens = 0
        total_cost = 0.0
        total_requests = 0
        
        for embedding_result in embedding_results:
            if hasattr(embedding_result, 'token_count') and embedding_result.token_count:
                total_tokens += embedding_result.token_count
            if hasattr(embedding_result, 'cost_estimate') and embedding_result.cost_estimate:
                total_cost += embedding_result.cost_estimate
        
        # Count successful requests
        if hasattr(self.embedder, 'get_usage_stats'):
            stats_before = getattr(self, '_last_usage_stats', {'total_requests': 0})
            current_stats = self.embedder.get_usage_stats()
            total_requests += max(0, current_stats.get('total_requests', 0) - stats_before.get('total_requests', 0))
            self._last_usage_stats = current_stats
        
        return {'tokens': total_tokens, 'cost': total_cost, 'requests': total_requests}