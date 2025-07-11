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
        
        # Convert entities to metadata chunks
        metadata_chunks = []
        for entity in entities:
            # Update entity with has_implementation flag before creating chunk
            has_implementation = context.entity_has_implementation(entity.name)
            metadata_chunk = self._create_metadata_chunk(entity, has_implementation)
            metadata_chunks.append(metadata_chunk)
        
        # Apply deduplication
        to_embed, to_skip = self.check_deduplication(metadata_chunks, context.collection_name)
        
        if self.logger and to_skip:
            self.logger.debug(f"⚡ Skipping {len(to_skip)} unchanged entities")
        
        if not to_embed:
            return ProcessingResult.success_result(items_skipped=len(to_skip))
        
        # Process embeddings
        embedding_results, cost_data = self.process_embeddings(to_embed, "entity")
        
        # Create points
        points, failed_count = self.create_points(to_embed, embedding_results, context.collection_name, 'create_chunk_point')
        
        return ProcessingResult.success_result(
            items_processed=len(to_embed) - failed_count,
            items_skipped=len(to_skip),
            items_failed=failed_count,
            cost_data=cost_data,
            points_created=points
        )
    
    def _create_metadata_chunk(self, entity: 'Entity', has_implementation: bool) -> 'EntityChunk':
        """Create metadata chunk from entity with token validation."""
        from ..analysis.entities import EntityChunk
        
        # Create the chunk first
        chunk = EntityChunk.create_metadata_chunk(entity, has_implementation)
        
        # Validate and truncate content if needed
        if hasattr(self.embedder, 'get_accurate_token_count'):
            token_count = self.embedder.get_accurate_token_count(chunk.content)
            max_tokens = self.embedder.get_max_tokens() - 400  # Conservative buffer
            
            if token_count > max_tokens:
                if self.logger:
                    self.logger.warning(f"📏 Truncating entity metadata chunk '{entity.name}': {token_count} → {max_tokens} tokens")
                
                # Truncate content using embedder's method
                truncated_content = self.embedder.truncate_text(chunk.content, max_tokens + 400)  # Account for buffer
                
                # Create new chunk with truncated content
                chunk = EntityChunk(
                    id=chunk.id,
                    entity_name=chunk.entity_name,
                    chunk_type=chunk.chunk_type,
                    content=truncated_content,
                    metadata=chunk.metadata
                )
        
        return chunk


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
        
        # Convert relations to relation chunks
        relation_chunks = []
        for relation in relevant_relations:
            relation_chunk = self._create_relation_chunk(relation)
            relation_chunks.append(relation_chunk)
        
        # Apply deduplication
        to_embed, to_skip = self.check_deduplication(relation_chunks, context.collection_name)
        
        if self.logger and to_skip:
            self.logger.debug(f"⚡ Skipping {len(to_skip)} unchanged relations")
        
        if not to_embed:
            return ProcessingResult.success_result(items_skipped=len(to_skip))
        
        # Process embeddings
        embedding_results, cost_data = self.process_embeddings(to_embed, "relation")
        
        # Create points
        points, failed_count = self.create_points(to_embed, embedding_results, context.collection_name, 'create_chunk_point')
        
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
    
    def _create_relation_chunk(self, relation: 'Relation') -> 'RelationChunk':
        """Create relation chunk from relation with token validation."""
        from ..analysis.entities import RelationChunk
        
        # Create the chunk first
        chunk = RelationChunk.from_relation(relation)
        
        # Validate and truncate content if needed
        if hasattr(self.embedder, 'get_accurate_token_count'):
            token_count = self.embedder.get_accurate_token_count(chunk.content)
            max_tokens = self.embedder.get_max_tokens() - 400  # Conservative buffer
            
            if token_count > max_tokens:
                if self.logger:
                    self.logger.warning(f"📏 Truncating relation chunk '{chunk.id}': {token_count} → {max_tokens} tokens")
                
                # Truncate content using embedder's method
                truncated_content = self.embedder.truncate_text(chunk.content, max_tokens + 400)  # Account for buffer
                
                # Create new chunk with truncated content
                chunk = RelationChunk(
                    id=chunk.id,
                    from_entity=chunk.from_entity,
                    to_entity=chunk.to_entity,
                    relation_type=chunk.relation_type,
                    content=truncated_content,
                    context=chunk.context,
                    confidence=chunk.confidence,
                    metadata=chunk.metadata
                )
        
        return chunk


class ImplementationProcessor(ContentProcessor):
    """Processor for implementation chunks with deduplication."""
    
    def process_batch(self, implementation_chunks: List['EntityChunk'], context: ProcessingContext) -> ProcessingResult:
        """Process implementation chunks batch with deduplication and token validation."""
        if not implementation_chunks:
            return ProcessingResult.success_result()
        
        if self.logger:
            self.logger.debug(f"💻 Processing {len(implementation_chunks)} implementation chunks")
        
        # Validate and truncate chunks if needed
        validated_chunks = []
        for chunk in implementation_chunks:
            validated_chunk = self._validate_chunk_tokens(chunk)
            validated_chunks.append(validated_chunk)
        
        # Apply deduplication
        to_embed, to_skip = self.check_deduplication(validated_chunks, context.collection_name)
        
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
    
    def _validate_chunk_tokens(self, chunk: 'EntityChunk') -> 'EntityChunk':
        """Validate and truncate chunk content if it exceeds token limits."""
        if hasattr(self.embedder, 'get_accurate_token_count'):
            token_count = self.embedder.get_accurate_token_count(chunk.content)
            max_tokens = self.embedder.get_max_tokens() - 400  # Conservative buffer
            
            if token_count > max_tokens:
                if self.logger:
                    self.logger.warning(f"📏 Truncating implementation chunk '{chunk.entity_name}': {token_count} → {max_tokens} tokens")
                
                # Truncate content using embedder's method
                truncated_content = self.embedder.truncate_text(chunk.content, max_tokens + 400)  # Account for buffer
                
                # Create new chunk with truncated content
                from ..analysis.entities import EntityChunk
                chunk = EntityChunk(
                    id=chunk.id,
                    entity_name=chunk.entity_name,
                    chunk_type=chunk.chunk_type,
                    content=truncated_content,
                    metadata=chunk.metadata
                )
        
        return chunk