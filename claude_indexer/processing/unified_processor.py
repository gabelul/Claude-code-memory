"""Unified content processor that coordinates all processing phases."""

from typing import List, Set, TYPE_CHECKING
from .context import ProcessingContext
from .results import ProcessingResult
from .processors import EntityProcessor, RelationProcessor, ImplementationProcessor

if TYPE_CHECKING:
    from ..analysis.entities import Entity, Relation, EntityChunk


class UnifiedContentProcessor:
    """Orchestrates unified content processing pipeline."""
    
    def __init__(self, vector_store, embedder, logger=None):
        self.vector_store = vector_store
        self.embedder = embedder
        self.logger = logger
        
        # Initialize specialized processors
        self.entity_processor = EntityProcessor(vector_store, embedder, logger)
        self.relation_processor = RelationProcessor(vector_store, embedder, logger)
        self.impl_processor = ImplementationProcessor(vector_store, embedder, logger)
    
    def process_all_content(self, collection_name: str, entities: List['Entity'], 
                          relations: List['Relation'], implementation_chunks: List['EntityChunk'],
                          changed_entity_ids: Set[str]) -> ProcessingResult:
        """Single entry point replacing _store_vectors() logic."""
        
        # Create implementation chunk lookup for has_implementation flags
        implementation_entity_names = set()
        if implementation_chunks:
            implementation_entity_names = {chunk.entity_name for chunk in implementation_chunks}
        
        # Create processing context
        context = ProcessingContext(
            collection_name=collection_name,
            changed_entity_ids=changed_entity_ids,
            implementation_entity_names=implementation_entity_names
        )
        
        all_points = []
        combined_result = ProcessingResult.success_result()
        
        try:
            # Phase 1: Process entities
            if entities:
                if self.logger:
                    self.logger.debug(f"🔄 Phase 1: Processing {len(entities)} entities")
                
                entity_result = self.entity_processor.process_batch(entities, context)
                if not entity_result.success:
                    return entity_result
                combined_result = combined_result.combine_with(entity_result)
                all_points.extend(entity_result.points_created)
            
            # Phase 2: Process relations (with smart filtering based on changed entities)
            if relations:
                if self.logger:
                    self.logger.debug(f"🔄 Phase 2: Processing {len(relations)} relations")
                
                relation_result = self.relation_processor.process_batch(relations, context)
                if not relation_result.success:
                    return relation_result
                combined_result = combined_result.combine_with(relation_result)
                all_points.extend(relation_result.points_created)
            
            # Phase 3: Process implementation chunks
            if implementation_chunks:
                if self.logger:
                    self.logger.debug(f"🔄 Phase 3: Processing {len(implementation_chunks)} implementation chunks")
                
                impl_result = self.impl_processor.process_batch(implementation_chunks, context)
                if not impl_result.success:
                    return impl_result
                combined_result = combined_result.combine_with(impl_result)
                all_points.extend(impl_result.points_created)
            
            # Phase 4: Batch store all points
            if all_points:
                if self.logger:
                    self.logger.debug(f"🔄 Phase 4: Batch storing {len(all_points)} points")
                
                storage_result = self._batch_store_points(all_points, collection_name)
                if not storage_result:
                    return ProcessingResult.failure_result("Failed to store points in batch operation")
                
                # Phase 5: Enhanced orphan cleanup after successful storage
                try:
                    self._cleanup_orphaned_relations(collection_name)
                except Exception as cleanup_error:
                    if self.logger:
                        self.logger.warning(f"⚠️ Orphan cleanup failed but storage succeeded: {cleanup_error}")
            
            # Update combined result with final metrics
            combined_result.points_created = all_points
            
            # Log final summary
            if self.logger:
                self.logger.info(f"✅ Unified processing complete:")
                self.logger.info(f"   - Processed: {combined_result.items_processed}")
                self.logger.info(f"   - Skipped: {combined_result.items_skipped}")
                self.logger.info(f"   - Failed: {combined_result.items_failed}")
                self.logger.info(f"   - Points created: {len(all_points)}")
                if combined_result.cost_data:
                    self.logger.info(f"   - Tokens: {combined_result.cost_data.get('tokens', 0)}")
                    self.logger.info(f"   - Cost: ${combined_result.cost_data.get('cost', 0.0):.4f}")
            
            return combined_result
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in unified content processing: {e}")
            return ProcessingResult.failure_result(f"Processing failed: {e}")
    
    def _batch_store_points(self, all_points: List, collection_name: str) -> bool:
        """Store all points in batch with detailed logging."""
        if self.logger:
            self.logger.debug(f"💾 === FINAL STORAGE SUMMARY ===")
            self.logger.debug(f"   Collection: {collection_name}")
            self.logger.debug(f"   Total points to store: {len(all_points)}")
            
            # Count different types of points
            entity_points = sum(1 for p in all_points if self._get_point_payload(p).get('chunk_type') == 'metadata' and self._get_point_payload(p).get('entity_type') != 'relation')
            relation_points = sum(1 for p in all_points if self._get_point_payload(p).get('chunk_type') == 'relation')
            impl_points = sum(1 for p in all_points if self._get_point_payload(p).get('chunk_type') == 'implementation')
            
            self.logger.debug(f"   - Entity metadata: {entity_points}")
            self.logger.debug(f"   - Relations: {relation_points}")
            self.logger.debug(f"   - Implementations: {impl_points}")
        
        # Use vector store's batch upsert method
        result = self.vector_store.batch_upsert(collection_name, all_points)
        
        if self.logger:
            if result.success:
                self.logger.debug(f"✅ Successfully stored {result.items_processed} points (attempted: {len(all_points)})")
                if result.items_processed < len(all_points):
                    self.logger.warning(f"⚠️ Storage discrepancy: {len(all_points) - result.items_processed} points not stored")
            else:
                self.logger.error(f"❌ Failed to store points: {getattr(result, 'errors', 'Unknown error')}")
        
        return result.success
    
    def _get_point_payload(self, point) -> dict:
        """Get payload from point regardless of its structure."""
        if isinstance(point, dict):
            return point.get('payload', {})
        elif hasattr(point, 'payload'):
            return point.payload
        else:
            return {}
    
    def _cleanup_orphaned_relations(self, collection_name: str):
        """Clean up orphaned relations after successful storage."""
        if self.logger:
            self.logger.debug(f"🧹 Starting orphan cleanup after successful storage")
        
        # Try to use enhanced orphan cleanup if available
        try:
            from ..storage.diff_layers import EnhancedOrphanCleanup
            cleanup = EnhancedOrphanCleanup(self.vector_store.client)
            orphaned_count = cleanup.cleanup_hash_orphaned_relations(collection_name)
            
            if self.logger:
                if orphaned_count > 0:
                    self.logger.info(f"🧹 Cleaned {orphaned_count} orphaned relations after hash changes")
                else:
                    self.logger.debug(f"🧹 No orphaned relations found")
        except ImportError:
            if self.logger:
                self.logger.debug(f"🧹 Enhanced orphan cleanup not available, skipping")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"🧹 Orphan cleanup failed: {e}")