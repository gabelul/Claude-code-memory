"""Qdrant vector store implementation."""

import time
import warnings
from typing import List, Dict, Any, Optional, Union
from .base import VectorStore, StorageResult, VectorPoint, ManagedVectorStore

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, IsNullCondition, PayloadField
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    # Create mock classes for development
    class Distance:
        COSINE = "cosine"
        EUCLID = "euclidean" 
        DOT = "dot"
    
    class QdrantClient:
        pass
    
    class VectorParams:
        pass
    
    class PointStruct:
        pass
    
    class Filter:
        pass
    
    class FieldCondition:
        pass
    
    class MatchValue:
        pass
    
    class IsNullCondition:
        pass
    
    class PayloadField:
        pass


class QdrantStore(ManagedVectorStore):
    """Qdrant vector database implementation."""
    
    DISTANCE_METRICS = {
        "cosine": Distance.COSINE,
        "euclidean": Distance.EUCLID,
        "dot": Distance.DOT
    }
    
    def __init__(self, url: str = "http://localhost:6333", api_key: str = None,
                 timeout: float = 60.0, auto_create_collections: bool = True):
        
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant client not available. Install with: pip install qdrant-client")
        
        super().__init__(auto_create_collections=auto_create_collections)
        
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        
        # Initialize client
        try:
            # Suppress insecure connection warning for development
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")
                self.client = QdrantClient(
                    url=url,
                    api_key=api_key,
                    timeout=timeout
                )
            # Test connection
            self.client.get_collections()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Qdrant at {url}: {e}")
    
    def create_collection(self, collection_name: str, vector_size: int, 
                         distance_metric: str = "cosine") -> StorageResult:
        """Create a new Qdrant collection."""
        start_time = time.time()
        
        try:
            if distance_metric not in self.DISTANCE_METRICS:
                available = list(self.DISTANCE_METRICS.keys())
                return StorageResult(
                    success=False,
                    operation="create_collection",
                    processing_time=time.time() - start_time,
                    errors=[f"Invalid distance metric: {distance_metric}. Available: {available}"]
                )
            
            distance = self.DISTANCE_METRICS[distance_metric]
            
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=distance),
                optimizers_config={
                    "indexing_threshold": 1000
                }
            )
            
            return StorageResult(
                success=True,
                operation="create_collection",
                items_processed=1,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            return StorageResult(
                success=False,
                operation="create_collection",
                processing_time=time.time() - start_time,
                errors=[f"Failed to create collection {collection_name}: {e}"]
            )
    
    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        try:
            collections = self.client.get_collections()
            return any(col.name == collection_name for col in collections.collections)
        except Exception:
            return False
    
    def delete_collection(self, collection_name: str) -> StorageResult:
        """Delete a collection."""
        start_time = time.time()
        
        try:
            self.client.delete_collection(collection_name=collection_name)
            
            return StorageResult(
                success=True,
                operation="delete_collection",
                items_processed=1,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            return StorageResult(
                success=False,
                operation="delete_collection",
                processing_time=time.time() - start_time,
                errors=[f"Failed to delete collection {collection_name}: {e}"]
            )
    
    def upsert_points(self, collection_name: str, points: List[VectorPoint]) -> StorageResult:
        """Insert or update points in the collection."""
        start_time = time.time()
        
        if not points:
            return StorageResult(
                success=True,
                operation="upsert",
                items_processed=0,
                processing_time=time.time() - start_time
            )
        
        try:
            # Ensure collection exists
            if not self.ensure_collection(collection_name, len(points[0].vector)):
                return StorageResult(
                    success=False,
                    operation="upsert",
                    processing_time=time.time() - start_time,
                    errors=[f"Collection {collection_name} does not exist"]
                )
            
            # Convert to Qdrant points
            qdrant_points = []
            for point in points:
                qdrant_point = PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=point.payload
                )
                qdrant_points.append(qdrant_point)
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=collection_name,
                points=qdrant_points
            )
            
            return StorageResult(
                success=True,
                operation="upsert",
                items_processed=len(points),
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            return StorageResult(
                success=False,
                operation="upsert",
                items_failed=len(points),
                processing_time=time.time() - start_time,
                errors=[f"Failed to upsert points: {e}"]
            )
    
    def delete_points(self, collection_name: str, point_ids: List[Union[str, int]]) -> StorageResult:
        """Delete points by their IDs."""
        start_time = time.time()
        
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=point_ids
            )
            
            return StorageResult(
                success=True,
                operation="delete",
                items_processed=len(point_ids),
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            return StorageResult(
                success=False,
                operation="delete",
                items_failed=len(point_ids),
                processing_time=time.time() - start_time,
                errors=[f"Failed to delete points: {e}"]
            )
    
    def search_similar(self, collection_name: str, query_vector: List[float],
                      limit: int = 10, score_threshold: float = 0.0,
                      filter_conditions: Dict[str, Any] = None) -> StorageResult:
        """Search for similar vectors."""
        start_time = time.time()
        
        try:
            # Build filter if provided
            query_filter = None
            if filter_conditions:
                query_filter = self._build_filter(filter_conditions)
            
            # Perform search
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter
            )
            
            # Convert results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                })
            
            return StorageResult(
                success=True,
                operation="search",
                processing_time=time.time() - start_time,
                results=results,
                total_found=len(results)
            )
            
        except Exception as e:
            return StorageResult(
                success=False,
                operation="search",
                processing_time=time.time() - start_time,
                errors=[f"Search failed: {e}"]
            )
    
    def _build_filter(self, filter_conditions: Dict[str, Any]) -> Filter:
        """Build Qdrant filter from conditions."""
        conditions = []
        
        for field, value in filter_conditions.items():
            if isinstance(value, (str, int, float, bool)):
                condition = FieldCondition(
                    key=field,
                    match=MatchValue(value=value)
                )
                conditions.append(condition)
        
        return Filter(must=conditions) if conditions else None
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection."""
        try:
            collection_info = self.client.get_collection(collection_name)
            
            return {
                "name": collection_name,
                "status": collection_info.status.value,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.value,
                "points_count": collection_info.points_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "segments_count": collection_info.segments_count
            }
            
        except Exception as e:
            return {
                "name": collection_name,
                "error": str(e)
            }
    
    def count(self, collection_name: str) -> int:
        """Count total points in collection - test compatibility method."""
        try:
            collection_info = self.client.get_collection(collection_name)
            return collection_info.points_count
        except Exception:
            return 0
    
    def search(self, collection_name: str, query_vector, top_k: int = 10):
        """Legacy search interface for test compatibility."""
        try:
            if hasattr(query_vector, 'tolist'):
                query_vector = query_vector.tolist()
            elif isinstance(query_vector, list):
                pass
            else:
                query_vector = list(query_vector)
                
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k
            )
            
            # Return results in expected format for tests
            class SearchHit:
                def __init__(self, id, score, payload):
                    self.id = id
                    self.score = score
                    self.payload = payload
            
            return [SearchHit(result.id, result.score, result.payload) for result in search_results]
            
        except Exception as e:
            print(f"Search failed: {e}")
            return []
    
    def list_collections(self) -> List[str]:
        """List all collections."""
        try:
            collections = self.client.get_collections()
            return [col.name for col in collections.collections]
        except Exception:
            return []
    
    def clear_collection(self, collection_name: str, preserve_manual: bool = True) -> StorageResult:
        """Clear collection data. By default, preserves manually-added memories.
        
        Args:
            collection_name: Name of the collection
            preserve_manual: If True, only delete auto-generated memories (entities with file_path or relations with from/to/relationType)
        """
        start_time = time.time()
        
        try:
            # Check if collection exists
            if not self.collection_exists(collection_name):
                return StorageResult(
                    success=True,
                    operation="clear_collection",
                    processing_time=time.time() - start_time,
                    warnings=[f"Collection {collection_name} doesn't exist - nothing to clear"]
                )
            
            if preserve_manual:
                # Delete only auto-generated memories (entities with file_path or relations)
                from qdrant_client import models
                
                # Count points before deletion for reporting
                count_before = self.client.count(collection_name=collection_name).count
                
                # Get all points to identify auto-generated content
                # Use scroll to get all points, filter manually, then delete by IDs
                all_points = self.client.scroll(
                    collection_name=collection_name,
                    limit=10000,  # Get all points
                    with_payload=True
                )[0]
                
                # Find points that are auto-generated (code-indexed entities or relations)
                auto_generated_ids = []
                for point in all_points:
                    # Auto-generated entities have file_path
                    if 'file_path' in point.payload and point.payload['file_path']:
                        auto_generated_ids.append(point.id)
                    # Auto-generated relations have from/to/relationType structure
                    elif ('from' in point.payload and 'to' in point.payload and 
                          'relationType' in point.payload):
                        auto_generated_ids.append(point.id)
                
                # Delete auto-generated points by ID if any found
                if auto_generated_ids:
                    self.client.delete(
                        collection_name=collection_name,
                        points_selector=auto_generated_ids,
                        wait=True
                    )
                
                # Count points after deletion
                count_after = self.client.count(collection_name=collection_name).count
                deleted_count = count_before - count_after
                
                return StorageResult(
                    success=True,
                    operation="clear_collection",
                    items_processed=deleted_count,
                    processing_time=time.time() - start_time,
                    warnings=[f"Preserved {count_after} manual memories"]
                )
            else:
                # Delete the entire collection (old behavior)
                self.client.delete_collection(collection_name=collection_name)
                
                return StorageResult(
                    success=True,
                    operation="clear_collection",
                    items_processed=1,
                    processing_time=time.time() - start_time
                )
            
        except Exception as e:
            return StorageResult(
                success=False,
                operation="clear_collection",
                processing_time=time.time() - start_time,
                errors=[f"Failed to clear collection {collection_name}: {e}"]
            )
    
    def get_client_info(self) -> Dict[str, Any]:
        """Get Qdrant client information."""
        try:
            info = self.client.get_telemetry()
            return {
                "url": self.url,
                "version": getattr(info, 'version', 'unknown'),
                "status": "connected",
                "timeout": self.timeout,
                "has_api_key": self.api_key is not None
            }
        except Exception as e:
            return {
                "url": self.url,
                "status": "error",
                "error": str(e),
                "timeout": self.timeout,
                "has_api_key": self.api_key is not None
            }
    
    def create_entity_point(self, entity: 'Entity', embedding: List[float], 
                           collection_name: str) -> VectorPoint:
        """Create a vector point from an entity."""
        from ..analysis.entities import Entity
        
        # Generate deterministic ID using file path + entity name to prevent collisions
        entity_key = f"{entity.file_path}::{entity.name}" if entity.file_path else entity.name
        point_id = self.generate_deterministic_id(entity_key)
        
        # Create payload
        payload = {
            "name": entity.name,
            "entityType": entity.entity_type.value,
            "observations": entity.observations,
            "collection": collection_name,
            "type": "entity"
        }
        
        # Add optional metadata
        if entity.file_path:
            payload["file_path"] = str(entity.file_path)
        if entity.line_number:
            payload["line_number"] = entity.line_number
        if entity.docstring:
            payload["docstring"] = entity.docstring
        if entity.signature:
            payload["signature"] = entity.signature
        
        return VectorPoint(
            id=point_id,
            vector=embedding,
            payload=payload
        )
    
    def create_relation_point(self, relation: 'Relation', embedding: List[float],
                            collection_name: str) -> VectorPoint:
        """Create a vector point from a relation."""
        from ..analysis.entities import Relation
        
        # Generate deterministic ID
        relation_key = f"{relation.from_entity}-{relation.relation_type.value}-{relation.to_entity}"
        point_id = self.generate_deterministic_id(relation_key)
        
        # Create payload
        payload = {
            "from": relation.from_entity,
            "to": relation.to_entity,
            "relationType": relation.relation_type.value,
            "collection": collection_name,
            "type": "relation"
        }
        
        # Add optional metadata
        if relation.context:
            payload["context"] = relation.context
        if relation.confidence != 1.0:
            payload["confidence"] = relation.confidence
        
        return VectorPoint(
            id=point_id,
            vector=embedding,
            payload=payload
        )
    
    def _get_all_entity_names(self, collection_name: str) -> set:
        """Get all entity names from the collection.
        
        Returns:
            Set of entity names currently in the collection.
        """
        entity_names = set()
        
        try:
            # Check if collection exists
            if not self.collection_exists(collection_name):
                return entity_names
            
            # Use scroll to get all entities (type != "relation")
            from qdrant_client import models
            
            scroll_result = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must_not=[
                        models.FieldCondition(
                            key="type",
                            match=models.MatchValue(value="relation")
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False
            )
            
            for point in scroll_result[0]:
                name = point.payload.get('name', '')
                if name:
                    entity_names.add(name)
                    
        except Exception as e:
            # Log error but continue - empty set means no entities found
            pass
        
        return entity_names
    
    def _get_all_relations(self, collection_name: str) -> List:
        """Get all relations from the collection.
        
        Returns:
            List of relation points from the collection.
        """
        relations = []
        
        try:
            # Check if collection exists
            if not self.collection_exists(collection_name):
                return relations
            
            # Use scroll to get all relations (type = "relation")  
            from qdrant_client import models
            
            scroll_result = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="type",
                            match=models.MatchValue(value="relation")
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False
            )
            
            relations.extend(scroll_result[0])
            
        except Exception as e:
            # Log error but continue - empty list means no relations found
            pass
        
        return relations
    
    def _cleanup_orphaned_relations(self, collection_name: str, verbose: bool = False) -> int:
        """Clean up relations that reference non-existent entities.
        
        Args:
            collection_name: Name of the collection to clean
            verbose: Whether to log detailed information about orphaned relations
            
        Returns:
            Number of orphaned relations deleted
        """
        if verbose:
            print("🔍 Searching for orphaned relations...")
        
        try:
            # Step 1: Get all entity names currently in collection
            existing_entities = self._get_all_entity_names(collection_name)
            
            if not existing_entities:
                if verbose:
                    print("   No entities found in collection")
                return 0
            
            # Step 2: Find all relations
            all_relations = self._get_all_relations(collection_name)
            
            if not all_relations:
                if verbose:
                    print("   No relations found in collection")
                return 0
            
            # Step 3: Check each relation for orphaned references
            orphaned_relations = []
            for relation in all_relations:
                from_entity = relation.payload.get('from', '')
                to_entity = relation.payload.get('to', '')
                
                # Check if either end of the relation references a non-existent entity
                if from_entity not in existing_entities or to_entity not in existing_entities:
                    orphaned_relations.append(relation)
                    if verbose:
                        print(f"🔍 Found orphaned relation: {from_entity} -> {to_entity}")
            
            # Step 4: Batch delete orphaned relations
            if orphaned_relations:
                relation_ids = [r.id for r in orphaned_relations]
                delete_result = self.delete_points(collection_name, relation_ids)
                
                if delete_result.success:
                    if verbose:
                        print(f"🗑️  Deleted {len(orphaned_relations)} orphaned relations")
                    return len(orphaned_relations)
                else:
                    if verbose:
                        print(f"❌ Failed to delete orphaned relations: {delete_result.errors}")
                    return 0
            else:
                if verbose:
                    print("   No orphaned relations found")
                return 0
                
        except Exception as e:
            if verbose:
                print(f"❌ Error during orphaned relation cleanup: {e}")
            return 0