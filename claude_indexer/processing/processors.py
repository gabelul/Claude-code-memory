"""Specialized content processors for different entity types."""

from typing import List, TYPE_CHECKING
from .content_processor import ContentProcessor
from .context import ProcessingContext
from .results import ProcessingResult

if TYPE_CHECKING:
    from ..analysis.entities import Entity, Relation, EntityChunk


class EntityProcessor(ContentProcessor):
    """Processor for entity metadata with deduplication."""
    
    def process_batch(self, entities: List['Entity'], context: ProcessingContext) -> ProcessingResult:
        """Process entity metadata batch with deduplication."""
        if not entities:
            return ProcessingResult.success_result()
        
        if self.logger:
            self.logger.debug(f"📋 Processing {len(entities)} entities for metadata")
        
        # Apply deduplication
        to_embed, to_skip = self.check_deduplication(entities, context.collection_name)
        
        if self.logger and to_skip:
            self.logger.debug(f"⚡ Skipping {len(to_skip)} unchanged entities")
        
        if not to_embed:
            return ProcessingResult.success_result(items_skipped=len(to_skip))
        
        # Process embeddings
        embedding_results, cost_data = self.process_embeddings(to_embed, "entity")
        
        # Create points
        points, failed_count = self.create_points(to_embed, embedding_results, context.collection_name, 'create_entity_point')
        
        # Update entities with has_implementation flags
        self._update_implementation_flags(to_embed, context)
        
        return ProcessingResult.success_result(
            items_processed=len(to_embed) - failed_count,
            items_skipped=len(to_skip),
            items_failed=failed_count,
            cost_data=cost_data,
            points_created=points
        )
    
    def _update_implementation_flags(self, entities: List['Entity'], context: ProcessingContext):
        """Update has_implementation flags for entities."""
        for entity in entities:
            if hasattr(entity, 'metadata') and entity.metadata:
                entity.metadata['has_implementation'] = context.entity_has_implementation(entity.name)


class RelationProcessor(ContentProcessor):
    """Processor for relations with smart filtering."""
    
    def process_batch(self, relations: List['Relation'], context: ProcessingContext) -> ProcessingResult:
        """Process relations batch with smart filtering based on changed entities."""
        if not relations:
            return ProcessingResult.success_result()
        
        if self.logger:
            self.logger.debug(f"🔗 Processing {len(relations)} relations")
        
        # Smart filter relations based on changed entities
        relevant_relations = self._filter_relevant_relations(relations, context)
        
        if self.logger and len(relevant_relations) < len(relations):
            skipped_count = len(relations) - len(relevant_relations)
            self.logger.debug(f"🔍 Filtered to {len(relevant_relations)} relevant relations (skipped {skipped_count} unchanged)")
        
        if not relevant_relations:
            return ProcessingResult.success_result(items_skipped=len(relations))
        
        # Apply deduplication
        to_embed, to_skip = self.check_deduplication(relevant_relations, context.collection_name)
        
        if self.logger and to_skip:
            self.logger.debug(f"⚡ Skipping {len(to_skip)} unchanged relations")
        
        if not to_embed:
            return ProcessingResult.success_result(items_skipped=len(to_skip))
        
        # Process embeddings
        embedding_results, cost_data = self.process_embeddings(to_embed, "relation")
        
        # Create points
        points, failed_count = self.create_points(to_embed, embedding_results, context.collection_name, 'create_relation_point')
        
        total_skipped = len(to_skip) + (len(relations) - len(relevant_relations))
        
        return ProcessingResult.success_result(
            items_processed=len(to_embed) - failed_count,
            items_skipped=total_skipped,
            items_failed=failed_count,
            cost_data=cost_data,
            points_created=points
        )
    
    def _filter_relevant_relations(self, relations: List['Relation'], context: ProcessingContext) -> List['Relation']:
        """Filter relations to only include those involving changed entities."""
        if not context.changed_entity_ids:
            return relations
        
        relevant_relations = []
        for relation in relations:
            # Include relation if either entity was changed
            if (relation.from_entity in context.changed_entity_ids or 
                relation.to_entity in context.changed_entity_ids):
                relevant_relations.append(relation)
        
        return relevant_relations


class ImplementationProcessor(ContentProcessor):
    """Processor for implementation chunks with deduplication."""
    
    def process_batch(self, implementation_chunks: List['EntityChunk'], context: ProcessingContext) -> ProcessingResult:
        """Process implementation chunks batch with deduplication."""
        if not implementation_chunks:
            return ProcessingResult.success_result()
        
        if self.logger:
            self.logger.debug(f"💻 Processing {len(implementation_chunks)} implementation chunks")
        
        # Apply deduplication
        to_embed, to_skip = self.check_deduplication(implementation_chunks, context.collection_name)
        
        if self.logger and to_skip:
            self.logger.debug(f"⚡ Skipping {len(to_skip)} unchanged implementation chunks")
        
        if not to_embed:
            return ProcessingResult.success_result(items_skipped=len(to_skip))
        
        # Process embeddings
        embedding_results, cost_data = self.process_embeddings(to_embed, "implementation")
        
        # Create points
        points, failed_count = self.create_points(to_embed, embedding_results, context.collection_name, 'create_chunk_point')
        
        return ProcessingResult.success_result(
            items_processed=len(to_embed) - failed_count,
            items_skipped=len(to_skip),
            items_failed=failed_count,
            cost_data=cost_data,
            points_created=points
        )