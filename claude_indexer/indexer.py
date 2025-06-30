"""Core indexing orchestrator - stateless domain service."""

import time
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union, Set
from dataclasses import dataclass

from .config import IndexerConfig
from .analysis.parser import ParserRegistry, ParserResult
from .analysis.entities import Entity, Relation, EntityChunk, RelationChunk
from .embeddings.base import Embedder
from .storage.base import VectorStore
from .indexer_logging import get_logger

logger = get_logger()


def format_change(current: int, previous: int) -> str:
    """Format a change value with +/- indicator."""
    change = current - previous
    if change > 0:
        return f"{current} (+{change})"
    elif change < 0:
        return f"{current} ({change})"
    else:
        return f"{current} (+0)" if previous > 0 else str(current)


@dataclass
class IndexingResult:
    """Result of an indexing operation."""
    
    success: bool
    operation: str  # "full", "incremental", "single_file"
    
    # Metrics
    files_processed: int = 0
    files_failed: int = 0
    entities_created: int = 0
    relations_created: int = 0
    implementation_chunks_created: int = 0  # Progressive disclosure metric
    processing_time: float = 0.0
    
    # Cost tracking
    total_tokens: int = 0
    total_cost_estimate: float = 0.0
    embedding_requests: int = 0
    
    # File tracking
    processed_files: List[str] = None
    failed_files: List[str] = None
    
    # Errors and warnings
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.processed_files is None:
            self.processed_files = []
        if self.failed_files is None:
            self.failed_files = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    @property
    def total_items(self) -> int:
        """Total entities and relations created."""
        return self.entities_created + self.relations_created
    
    @property
    def success_rate(self) -> float:
        """File processing success rate."""
        total = self.files_processed + self.files_failed
        if total == 0:
            return 1.0
        return self.files_processed / total
     
    @property  
    def duration(self) -> float:
        """Alias for processing_time for backward compatibility."""
        return self.processing_time


class CoreIndexer:
    """Stateless core indexing service orchestrating all components."""
    
    def __init__(self, config: IndexerConfig, embedder: Embedder, 
                 vector_store: VectorStore, project_path: Path):
        self.config = config
        self.embedder = embedder
        self.vector_store = vector_store
        self.project_path = project_path
        self.logger = get_logger()
        
        # Initialize parser registry
        self.parser_registry = ParserRegistry(project_path)
        
        # Load project configuration if available
        from .config.config_loader import ConfigLoader
        self.config_loader = ConfigLoader(project_path)
        try:
            # Update config with project-specific settings
            self.config = self.config_loader.load()
        except Exception:
            # Continue with existing config if project config fails
            pass
        
        # Inject parser-specific configurations
        self._inject_parser_configs()
    
    def _inject_parser_configs(self):
        """Inject project-specific parser configurations."""
        for parser in self.parser_registry._parsers:
            parser_name = parser.__class__.__name__.lower().replace('parser', '')
            parser_config = self.config_loader.get_parser_config(parser_name)
            if parser_config and hasattr(parser, 'update_config'):
                parser.update_config(parser_config)
        
    def _get_state_directory(self) -> Path:
        """Get state directory (configurable for test isolation)."""
        # Use configured state directory if provided (for tests)
        if self.config.state_directory is not None:
            state_dir = self.config.state_directory
        else:
            # Default to project-local state directory
            state_dir = self.project_path / '.claude-indexer'
        
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir
    
    def _get_state_file(self, collection_name: str) -> Path:
        """Get collection-specific state file with simple naming."""
        # Simple, predictable naming: just use collection name
        filename = f"{collection_name}.json"
        new_state_file = self._get_state_directory() / filename
        
        # Auto-migrate from global state directory if exists
        if not new_state_file.exists():
            old_global_state_file = Path.home() / '.claude-indexer' / 'state' / filename
            if old_global_state_file.exists():
                try:
                    # Copy state file content to new location
                    with open(old_global_state_file, 'r') as old_f:
                        state_data = old_f.read()
                    with open(new_state_file, 'w') as new_f:
                        new_f.write(state_data)
                    
                    # Remove old state file
                    old_global_state_file.unlink()
                    self.logger.info(f"Migrated state file: {old_global_state_file} -> {new_state_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to migrate state file {old_global_state_file}: {e}")
        
        return new_state_file
    
    @property
    def state_file(self) -> Path:
        """Default state file for backward compatibility with tests."""
        return self._get_state_file("default")
    
    def index_project(self, collection_name: str, include_tests: bool = False, verbose: bool = False) -> IndexingResult:
        """Index an entire project with automatic incremental detection."""
        start_time = time.time()
        
        # Auto-detect incremental mode based on state file existence (like watcher pattern)
        state_file = self._get_state_file(collection_name)
        incremental = state_file.exists()
        
        result = IndexingResult(success=True, operation="incremental" if incremental else "full")
        
        try:
            # Find files to process
            if incremental:
                files_to_process, deleted_files = self._find_changed_files(include_tests, collection_name)
                
                # Handle deleted files using consolidated function
                if deleted_files:
                    self._handle_deleted_files(collection_name, deleted_files, verbose)
                    # State cleanup happens automatically in _update_state when no files_to_process
                    result.warnings.append(f"Handled {len(deleted_files)} deleted files")
            else:
                files_to_process = self._find_all_files(include_tests)
                deleted_files = []
            
            if not files_to_process:
                # Even if no files to process, update state to remove deleted files
                if incremental and deleted_files:
                    # Use incremental mode to preserve existing files while removing deleted ones
                    self._update_state([], collection_name, verbose, full_rebuild=False, deleted_files=deleted_files)
                result.warnings.append("No files to process")
                result.processing_time = time.time() - start_time
                return result
            
            self.logger.info(f"Found {len(files_to_process)} files to process")
            
            # Process files in batches with progressive disclosure support
            batch_size = self.config.batch_size
            all_entities = []
            all_relations = []
            all_implementation_chunks = []
            
            for i in range(0, len(files_to_process), batch_size):
                batch = files_to_process[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(files_to_process) + batch_size - 1) // batch_size
                self.logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
                
                batch_entities, batch_relations, batch_implementation_chunks, batch_errors = self._process_file_batch(batch, verbose)
                
                all_entities.extend(batch_entities)
                all_relations.extend(batch_relations)
                all_implementation_chunks.extend(batch_implementation_chunks)
                result.errors.extend(batch_errors)
                
                # Track failed files properly
                failed_files_in_batch = [str(f) for f in batch if str(f) in batch_errors]
                result.failed_files.extend(failed_files_in_batch)
                
                # Print specific file errors for debugging
                for error_msg in batch_errors:
                    for file_path in batch:
                        if str(file_path) in error_msg:
                            logger.error(f"❌ Error processing file: {file_path} - {error_msg}")
                            break
                
                # Update metrics
                result.files_processed += len([f for f in batch if str(f) not in batch_errors])
                result.files_failed += len(batch_errors)
            
            # Store vectors using direct Qdrant automation with progressive disclosure
            if all_entities or all_relations or all_implementation_chunks:
                # Use direct Qdrant automation via existing _store_vectors method
                storage_success = self._store_vectors(collection_name, all_entities, all_relations, all_implementation_chunks)
                if not storage_success:
                    result.success = False
                    result.errors.append("Failed to store vectors in Qdrant")
                else:
                    result.entities_created = len(all_entities)
                    result.relations_created = len(all_relations)
                    result.implementation_chunks_created = len(all_implementation_chunks)
            
            # Update state file - merge successfully processed files with existing state
            successfully_processed = [f for f in files_to_process if str(f) not in result.failed_files]
            if successfully_processed:
                self._update_state(successfully_processed, collection_name, verbose, deleted_files=deleted_files if incremental else None)
                # Store processed files in result for test verification
                result.processed_files = [str(f) for f in successfully_processed]
                
                # Clean up orphaned relations after processing modified files
                if incremental and successfully_processed:
                    if verbose:
                        logger.info(f"🔍 Cleaning up orphaned relations after processing {len(successfully_processed)} modified files")
                    orphaned_deleted = self.vector_store._cleanup_orphaned_relations(collection_name, verbose)
                    if verbose and orphaned_deleted > 0:
                        logger.info(f"✅ Cleanup complete: {orphaned_deleted} orphaned relations removed")
                    elif verbose:
                        logger.info("✅ No orphaned relations found")
            elif verbose:
                logger.warning(f"⚠️  No files to save state for (all {len(files_to_process)} files failed)")
            
            # Transfer cost data to result
            if hasattr(self, '_session_cost_data'):
                result.total_tokens = self._session_cost_data.get('tokens', 0)
                result.total_cost_estimate = self._session_cost_data.get('cost', 0.0)
                result.embedding_requests = self._session_cost_data.get('requests', 0)
                # Reset for next operation
                self._session_cost_data = {'tokens': 0, 'cost': 0.0, 'requests': 0}
            
        except Exception as e:
            result.success = False
            result.errors.append(f"Indexing failed: {e}")
        
        result.processing_time = time.time() - start_time
        return result
    
    def index_single_file(self, file_path: Path, collection_name: str) -> IndexingResult:
        """Index a single file."""
        start_time = time.time()
        result = IndexingResult(success=True, operation="single_file")
        
        try:
            # Clean up existing entities for this file BEFORE processing (prevents duplicates)
            # This ensures single file indexing gets same cleanup treatment as batch processing
            try:
                relative_path = str(file_path.relative_to(self.project_path))
                logger.info(f"🧹 DEBUG: Single file cleanup starting for: {relative_path}")
                
                # Check if collection exists first
                collection_exists = self.vector_store.collection_exists(collection_name)
                logger.info(f"🧹 DEBUG: Collection '{collection_name}' exists: {collection_exists}")
                
                if collection_exists:
                    # Try to find entities before deletion
                    full_path = str(file_path)
                    logger.info(f"🧹 DEBUG: Searching for entities with path: {full_path}")
                    found_entities = self.vector_store.find_entities_for_file(collection_name, full_path)
                    logger.info(f"🧹 DEBUG: Found {len(found_entities)} entities before cleanup")
                    
                    # Run cleanup
                    self._handle_deleted_files(collection_name, relative_path, verbose=True)
                    
                    # Check after cleanup
                    found_entities_after = self.vector_store.find_entities_for_file(collection_name, full_path)
                    logger.info(f"🧹 DEBUG: Found {len(found_entities_after)} entities after cleanup")
                else:
                    logger.info(f"🧹 DEBUG: Collection doesn't exist, skipping cleanup")
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to clean existing entities for {file_path}: {e}")
                import traceback
                logger.warning(f"⚠️ Traceback: {traceback.format_exc()}")
            
            # Parse file
            parse_result = self.parser_registry.parse_file(file_path)
            
            if not parse_result.success:
                result.success = False
                result.files_failed = 1
                result.errors.extend(parse_result.errors)
                return result
            
            # Use batch processing like the project indexer with progressive disclosure
            storage_success = self._store_vectors(collection_name, parse_result.entities, parse_result.relations, parse_result.implementation_chunks)
            
            if storage_success:
                result.files_processed = 1
                result.entities_created = len(parse_result.entities)
                result.relations_created = len(parse_result.relations)
                result.implementation_chunks_created = len(parse_result.implementation_chunks)
                result.processed_files = [str(file_path)]
            else:
                result.success = False
                result.files_failed = 1
                result.errors.append("Failed to store vectors")
            
        except Exception as e:
            result.success = False
            result.files_failed = 1
            result.errors.append(f"Failed to index {file_path}: {e}")
        
        result.processing_time = time.time() - start_time
        return result
    
    def search_similar(self, collection_name: str, query: str, 
                      limit: int = 10, filter_type: str = None) -> List[Dict[str, Any]]:
        """Search for similar entities/relations."""
        try:
            # Check if collection exists before searching
            if not self.vector_store.collection_exists(collection_name):
                logger.warning(f"Collection '{collection_name}' does not exist")
                return []
            
            # Generate query embedding
            embedding_result = self.embedder.embed_text(query)
            if not embedding_result.success:
                return []
            
            # Build filter
            filter_conditions = {}
            if filter_type:
                filter_conditions["type"] = filter_type
            
            # Search vector store
            search_result = self.vector_store.search_similar(
                collection_name=collection_name,
                query_vector=embedding_result.embedding,
                limit=limit,
                filter_conditions=filter_conditions
            )
            
            return search_result.results if search_result.success else []
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def clear_collection(self, collection_name: str, preserve_manual: bool = True) -> bool:
        """Clear collection data.
        
        Args:
            collection_name: Name of the collection
            preserve_manual: If True (default), preserve manually-added memories
        """
        try:
            # Clear vector store
            result = self.vector_store.clear_collection(collection_name, preserve_manual=preserve_manual)
            
            # Clear state file (only tracks code-indexed files)
            state_file = self._get_state_file(collection_name)
            if state_file.exists():
                state_file.unlink()
            
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False
    
    
    
    def _find_all_files(self, include_tests: bool = False) -> List[Path]:
        """Find all files matching project patterns."""
        files = []
        
        # Use project-specific patterns
        include_patterns = self.config.include_patterns
        exclude_patterns = self.config.exclude_patterns
        
        # No fallback patterns - use what's configured
        if not include_patterns:
            raise ValueError("No include patterns configured")
        
        # Find files matching include patterns
        for pattern in include_patterns:
            found = list(self.project_path.glob(f"**/{pattern}"))
            files.extend(found)
        
        # Filter files
        filtered_files = []
        for file_path in files:
            # Skip files matching exclude patterns
            relative_path = file_path.relative_to(self.project_path)
            if any(relative_path.match(pattern) for pattern in exclude_patterns):
                continue
            
            # Skip files in excluded directories
            path_str = str(relative_path)
            if any(excluded in path_str for excluded in exclude_patterns):
                continue
            
            # Check file size
            if file_path.stat().st_size > self.config.max_file_size:
                continue
            
            filtered_files.append(file_path)
        
        return filtered_files
    
    def _get_files_needing_processing(self, include_tests: bool = False, collection_name: str = None) -> List[Path]:
        """Get files that need processing for incremental indexing."""
        return self._find_changed_files(include_tests, collection_name)[0]
    
    def _find_changed_files(self, include_tests: bool = False, collection_name: str = None) -> Tuple[List[Path], List[str]]:
        """Find files that have changed since last indexing."""
        current_files = self._find_all_files(include_tests)
        current_state = self._get_current_state(current_files)
        previous_state = self._load_state(collection_name)
        
        changed_files = []
        deleted_files = []
        
        # Find new and modified files
        for file_path in current_files:
            file_key = str(file_path.relative_to(self.project_path))
            current_hash = current_state.get(file_key, {}).get("hash", "")
            previous_hash = previous_state.get(file_key, {}).get("hash", "")
            
            if current_hash != previous_hash:
                changed_files.append(file_path)
        
        # Find deleted files
        current_keys = set(current_state.keys())
        previous_keys = set(previous_state.keys())
        deleted_keys = previous_keys - current_keys
        deleted_files.extend(deleted_keys)
        
        return changed_files, deleted_files
    
    def _categorize_file_changes(self, include_tests: bool = False, collection_name: str = None) -> Tuple[List[Path], List[Path], List[str]]:
        """Categorize files into new, modified, and deleted."""
        current_files = self._find_all_files(include_tests)
        current_state = self._get_current_state(current_files)
        previous_state = self._load_state(collection_name)
        
        new_files = []
        modified_files = []
        deleted_files = []
        
        # Categorize changed files
        for file_path in current_files:
            file_key = str(file_path.relative_to(self.project_path))
            current_hash = current_state.get(file_key, {}).get("hash", "")
            previous_hash = previous_state.get(file_key, {}).get("hash", "")
            
            if current_hash != previous_hash:
                if previous_hash == "":  # Not in previous state = new file
                    new_files.append(file_path)
                else:  # In previous state but different hash = modified file
                    modified_files.append(file_path)
        
        # Find deleted files
        current_keys = set(current_state.keys())
        previous_keys = set(k for k in previous_state.keys() if not k.startswith('_'))  # Exclude metadata
        deleted_keys = previous_keys - current_keys
        deleted_files.extend(deleted_keys)
        
        return new_files, modified_files, deleted_files
    
    def _get_vectored_files(self, collection_name: str) -> Set[str]:
        """Get set of files that currently have entities in the vector database."""
        try:
            from qdrant_client.http import models
            
            # Access the underlying QdrantStore client (bypass CachingVectorStore wrapper)
            if hasattr(self.vector_store, 'backend'):
                qdrant_client = self.vector_store.backend.client
            else:
                qdrant_client = self.vector_store.client
            
            # Scroll through all points to get file paths
            file_paths = set()
            scroll_result = qdrant_client.scroll(
                collection_name=collection_name,
                limit=10000,  # Large batch size
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]  # First element is the points list
            next_page_offset = scroll_result[1]  # Second element is next page offset
            
            # Process first batch
            for point in points:
                payload = point.payload if hasattr(point, 'payload') else {}
                file_path = payload.get('file_path')
                if file_path:
                    # Convert to relative path for consistency
                    try:
                        rel_path = str(Path(file_path).relative_to(self.project_path))
                        file_paths.add(rel_path)
                    except ValueError:
                        # If relative_to fails, use the file_path as-is
                        file_paths.add(file_path)
            
            # Handle pagination if there are more points
            while next_page_offset is not None:
                scroll_result = qdrant_client.scroll(
                    collection_name=collection_name,
                    offset=next_page_offset,
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )
                
                points = scroll_result[0]
                next_page_offset = scroll_result[1]
                
                for point in points:
                    payload = point.payload if hasattr(point, 'payload') else {}
                    file_path = payload.get('file_path')
                    if file_path:
                        try:
                            rel_path = str(Path(file_path).relative_to(self.project_path))
                            file_paths.add(rel_path)
                        except ValueError:
                            file_paths.add(file_path)
            
            return file_paths
        except Exception as e:
            logger.warning(f"Failed to get vectored files: {e}")
            return set()
    
    def _categorize_vectored_file_changes(self, collection_name: str, before_vectored_files: Set[str] = None) -> Tuple[List[str], List[str], List[str]]:
        """Categorize vectored files (files with entities in database) into new, modified, and deleted."""
        current_vectored_files = self._get_vectored_files(collection_name)
        
        if before_vectored_files is None:
            # If no before state provided, assume all current files are existing
            return [], list(current_vectored_files), []
        
        new_vectored = list(current_vectored_files - before_vectored_files)
        deleted_vectored = list(before_vectored_files - current_vectored_files)
        
        # Files that exist in both are considered "modified" in the context of this operation
        # (they may have had entities added/removed/updated)
        common_files = current_vectored_files & before_vectored_files
        modified_vectored = list(common_files) if common_files else []
        
        return new_vectored, modified_vectored, deleted_vectored
    
    def _process_file_batch(self, files: List[Path], verbose: bool = False) -> Tuple[List[Entity], List[Relation], List[EntityChunk], List[str]]:
        """Process a batch of files with progressive disclosure support."""
        all_entities = []
        all_relations = []
        all_implementation_chunks = []
        errors = []
        
        for file_path in files:
            try:
                relative_path = file_path.relative_to(self.project_path)
                
                # Determine file status using existing changed files logic
                current_state = self._get_current_state([file_path])
                previous_state = self._load_state("memory-project")
                
                file_key = str(relative_path)
                if file_key not in previous_state:
                    file_status = "ADDED"
                else:
                    current_hash = current_state.get(file_key, {}).get("hash", "")
                    previous_hash = previous_state.get(file_key, {}).get("hash", "")
                    file_status = "MODIFIED" if current_hash != previous_hash else "UNCHANGED"
                
                self.logger.debug(f"Processing file [{file_status}]: {relative_path}")
                
                result = self.parser_registry.parse_file(file_path)
                
                if result.success:
                    all_entities.extend(result.entities)
                    all_relations.extend(result.relations)
                    all_implementation_chunks.extend(result.implementation_chunks)
                    self.logger.debug(f"  Found {len(result.entities)} entities, {len(result.relations)} relations, {len(result.implementation_chunks)} implementation chunks")
                else:
                    error_msg = f"Failed to parse {relative_path}"
                    errors.append(error_msg)
                    self.logger.warning(f"  {error_msg}")
                    logger.error(f"❌ Parse error in {file_path}: Parse failure")
                    
            except Exception as e:
                error_msg = f"Error processing {file_path}: {e}"
                errors.append(error_msg)
                self.logger.error(f"  {error_msg}")
                logger.error(f"❌ Processing error in {file_path}: {e}")
        
        return all_entities, all_relations, all_implementation_chunks, errors
    
    def _store_vectors(self, collection_name: str, entities: List[Entity], 
                      relations: List[Relation], implementation_chunks: List[EntityChunk] = None) -> bool:
        """Store entities, relations, and implementation chunks in vector database using batch processing."""
        if implementation_chunks is None:
            implementation_chunks = []
        
        logger = self.logger if hasattr(self, 'logger') else None
        if logger:
            logger.debug(f"🔄 Starting storage: {len(entities)} entities, {len(relations)} relations, {len(implementation_chunks)} chunks")
        
        try:
            all_points = []
            total_tokens = 0
            total_cost = 0.0
            total_requests = 0
            
            # Create implementation chunk lookup for has_implementation flags
            implementation_entity_names = set()
            if implementation_chunks:
                implementation_entity_names = {chunk.entity_name for chunk in implementation_chunks}
            
            # Batch process entities with progressive disclosure
            if entities:
                if logger:
                    logger.debug(f"🧠 Processing entities: {len(entities)} items")
                
                # Convert entities to metadata chunks for dual storage
                metadata_chunks = []
                for entity in entities:
                    has_implementation = entity.name in implementation_entity_names
                    metadata_chunk = EntityChunk.create_metadata_chunk(entity, has_implementation)
                    metadata_chunks.append(metadata_chunk)
                
                metadata_texts = [chunk.content for chunk in metadata_chunks]
                if logger:
                    logger.debug(f"🔤 Generating embeddings for {len(metadata_texts)} entity texts")
                
                embedding_results = self.embedder.embed_batch(metadata_texts)
                if logger:
                    logger.debug(f"✅ Entity embeddings completed: {sum(1 for r in embedding_results if r.success)}/{len(embedding_results)} successful")
                
                # Process embedding results for metadata chunks
                cost_data = self._collect_embedding_cost_data(embedding_results)
                total_tokens += cost_data['tokens']
                total_cost += cost_data['cost']
                total_requests += cost_data['requests']
                
                for chunk, embedding_result in zip(metadata_chunks, embedding_results):
                    if embedding_result.success:
                        point = self.vector_store.create_chunk_point(
                            chunk, embedding_result.embedding, collection_name
                        )
                        all_points.append(point)
            
            # Batch process relations
            if relations:
                if logger:
                    logger.debug(f"🔗 Processing relations: {len(relations)} items")
                
                # Deduplicate relations BEFORE embedding to save API costs
                seen_relation_keys = set()
                unique_relations = []
                duplicate_count = 0
                
                for relation in relations:
                    # Generate the same key that will be used for storage
                    relation_chunk = RelationChunk.from_relation(relation)
                    relation_key = relation_chunk.id
                    
                    if relation_key not in seen_relation_keys:
                        seen_relation_keys.add(relation_key)
                        unique_relations.append(relation)
                    else:
                        duplicate_count += 1
                
                if logger and duplicate_count > 0:
                    logger.debug(f"🔍 Deduplicated {duplicate_count} relations before embedding (saved {duplicate_count} API calls)")
                    
                relation_texts = [self._relation_to_text(relation) for relation in unique_relations]
                if logger:
                    logger.debug(f"🔤 Generating embeddings for {len(relation_texts)} unique relation texts")
                    
                embedding_results = self.embedder.embed_batch(relation_texts)
                if logger:
                    logger.debug(f"✅ Relation embeddings completed: {sum(1 for r in embedding_results if r.success)}/{len(embedding_results)} successful")
                
                # Process embedding results for relations
                cost_data = self._collect_embedding_cost_data(embedding_results)
                total_tokens += cost_data['tokens']
                total_cost += cost_data['cost']
                total_requests += cost_data['requests']
                
                for relation, embedding_result in zip(unique_relations, embedding_results):
                    if embedding_result.success:
                        # Convert relation to chunk for v2.4 pure architecture
                        relation_chunk = RelationChunk.from_relation(relation)
                        point = self.vector_store.create_relation_chunk_point(
                            relation_chunk, embedding_result.embedding, collection_name
                        )
                        all_points.append(point)
            
            # Batch process implementation chunks for progressive disclosure
            if implementation_chunks:
                if logger:
                    logger.debug(f"💻 Processing implementation chunks: {len(implementation_chunks)} items")
                    
                implementation_texts = [chunk.content for chunk in implementation_chunks]
                if logger:
                    logger.debug(f"🔤 Generating embeddings for {len(implementation_texts)} implementation texts")
                    
                embedding_results = self.embedder.embed_batch(implementation_texts)
                if logger:
                    logger.debug(f"✅ Implementation embeddings completed: {sum(1 for r in embedding_results if r.success)}/{len(embedding_results)} successful")
                
                # Process embedding results for implementation chunks
                cost_data = self._collect_embedding_cost_data(embedding_results)
                total_tokens += cost_data['tokens']
                total_cost += cost_data['cost']
                total_requests += cost_data['requests']
                
                for chunk, embedding_result in zip(implementation_chunks, embedding_results):
                    if embedding_result.success:
                        point = self.vector_store.create_chunk_point(
                            chunk, embedding_result.embedding, collection_name
                        )
                        all_points.append(point)
            
            # Store cost tracking data for result reporting
            if not hasattr(self, '_session_cost_data'):
                self._session_cost_data = {'tokens': 0, 'cost': 0.0, 'requests': 0}
            
            self._session_cost_data['tokens'] += total_tokens
            self._session_cost_data['cost'] += total_cost
            self._session_cost_data['requests'] += total_requests
            
            # Batch store all points
            if all_points:
                if logger:
                    logger.debug(f"💾 Storing {len(all_points)} points to Qdrant collection '{collection_name}'")
                
                result = self.vector_store.batch_upsert(collection_name, all_points)
                
                if logger:
                    if result.success:
                        logger.debug(f"✅ Successfully stored all {len(all_points)} points")
                    else:
                        logger.error(f"❌ Failed to store points: {getattr(result, 'errors', 'Unknown error')}")
                
                return result.success
            else:
                if logger:
                    logger.debug("ℹ️ No points to store")
                return True
            
        except Exception as e:
            logger.error(f"Error in _store_vectors: {e}")
            return False
    
    def _entity_to_text(self, entity: Entity) -> str:
        """Convert entity to text for embedding."""
        parts = [
            f"{entity.entity_type.value}: {entity.name}",
            " ".join(entity.observations)
        ]
        
        if entity.docstring:
            parts.append(f"Description: {entity.docstring}")
        
        if entity.signature:
            parts.append(f"Signature: {entity.signature}")
        
        return " | ".join(parts)
    
    def _relation_to_text(self, relation: Relation) -> str:
        """Convert relation to text for embedding."""
        text = f"Relation: {relation.from_entity} {relation.relation_type.value} {relation.to_entity}"
        
        if relation.context:
            text += f" | Context: {relation.context}"
        
        return text
    
    def _get_current_state(self, files: List[Path]) -> Dict[str, Dict[str, Any]]:
        """Get current state of files."""
        state = {}
        
        for file_path in files:
            try:
                relative_path = str(file_path.relative_to(self.project_path))
                file_hash = self._get_file_hash(file_path)
                
                state[relative_path] = {
                    "hash": file_hash,
                    "size": file_path.stat().st_size,
                    "mtime": file_path.stat().st_mtime
                }
            except Exception:
                continue
        
        return state
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get SHA256 hash of file contents."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _load_state(self, collection_name: str) -> Dict[str, Dict[str, Any]]:
        """Load previous indexing state."""
        try:
            state_file = self._get_state_file(collection_name)
            if state_file.exists():
                with open(state_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _load_previous_statistics(self, collection_name: str) -> Dict[str, int]:
        """Load previous run statistics from state file."""
        state = self._load_state(collection_name)
        return state.get('_statistics', {})
    
    def _save_statistics_to_state(self, collection_name: str, result: 'IndexingResult'):
        """Save current statistics to state file."""
        import time
        try:
            state = self._load_state(collection_name)
            state['_statistics'] = {
                'files_processed': result.files_processed,
                'entities_created': result.entities_created,
                'relations_created': result.relations_created,
                'implementation_chunks_created': result.implementation_chunks_created,
                'processing_time': result.processing_time,
                'timestamp': time.time()
            }
            
            # Save updated state
            state_file = self._get_state_file(collection_name)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            temp_file = state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            temp_file.rename(state_file)
            
        except Exception as e:
            logger.debug(f"Failed to save statistics to state: {e}")
    
    def _update_state(self, new_files: List[Path], collection_name: str, verbose: bool = False, full_rebuild: bool = False, deleted_files: List[str] = None):
        """Update state file by merging new files with existing state, or do full rebuild."""
        try:
            if full_rebuild:
                # Full rebuild: use only the new files as complete state
                final_state = self._get_current_state(new_files)
                operation_desc = "rebuilt"
                file_count_desc = f"{len(new_files)} files tracked"
            else:
                # Incremental update: merge new files with existing state
                existing_state = self._load_state(collection_name)
                new_state = self._get_current_state(new_files)
                final_state = existing_state.copy()
                final_state.update(new_state)
                operation_desc = "updated"
                file_count_desc = f"{len(new_files)} new files added, {len(final_state)} total files tracked"
            
            # Remove deleted files from final state
            if deleted_files:
                files_removed = 0
                for deleted_file in deleted_files:
                    logger.info(f"🗑️ DEBUG: About to check for deletion from JSON state: '{deleted_file}' (exists in state: {deleted_file in final_state})")
                    if deleted_file in final_state:
                        logger.info(f"🗑️ DEBUG: DELETING '{deleted_file}' from JSON state")
                        del final_state[deleted_file]
                        files_removed += 1
                        if verbose:
                            logger.debug(f"   Removed {deleted_file} from state")
                    else:
                        logger.info(f"⚠️ DEBUG: File '{deleted_file}' NOT FOUND in state for deletion")
                
                if files_removed > 0:
                    # Update description to reflect deletions
                    if operation_desc == "updated":
                        file_count_desc = f"{len(new_files)} new files added, {files_removed} files removed, {len(final_state)} total files tracked"
                    else:  # rebuilt
                        file_count_desc = f"{len(new_files)} files tracked, {files_removed} deleted files removed"
            
            # Save state atomically
            state_file = self._get_state_file(collection_name)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            temp_file = state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(final_state, f, indent=2)
            
            # Atomic rename
            temp_file.rename(state_file)
            
            # Verify saved state
            with open(state_file) as f:
                saved_state = json.load(f)
            
            if full_rebuild:
                if len(saved_state) != len(new_files):
                    raise ValueError(f"State validation failed: expected {len(new_files)} files, got {len(saved_state)}")
            # Note: For incremental updates, we cannot validate the final count
            # because it depends on both additions and deletions
                
            if verbose:
                logger.info(f"✅ State {operation_desc}: {file_count_desc}")
                
        except Exception as e:
            error_msg = f"❌ Failed to {'rebuild' if full_rebuild else 'update'} state: {e}"
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            # For incremental updates, fallback to full rebuild if update fails
            if not full_rebuild:
                logger.warning("🔄 Falling back to full state rebuild...")
                self._update_state(self._find_all_files(include_tests=False), collection_name, verbose, full_rebuild=True, deleted_files=None)
    
    def _rebuild_full_state(self, collection_name: str, verbose: bool = False):
        """Rebuild full state file from all current files."""
        try:
            if verbose:
                logger.info("🔄 Rebuilding complete state from all project files...")
            
            # Get all current files
            all_files = self._find_all_files(include_tests=False)
            
            # Use unified _update_state method with full_rebuild=True
            self._update_state(all_files, collection_name, verbose, full_rebuild=True, deleted_files=None)
                
        except Exception as e:
            error_msg = f"❌ Failed to rebuild state: {e}"
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
    
    def _collect_embedding_cost_data(self, embedding_results: List[Any]) -> Dict[str, Union[int, float]]:
        """Collect cost data from embedding results."""
        total_tokens = 0
        total_cost = 0.0
        total_requests = 0
        
        # Collect cost data from embedding results
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
    
    def _cleanup_temp_file(self, temp_file: Optional[Path]):
        """Safely clean up temporary file with exception handling."""
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors
    
    def _handle_deleted_files(self, collection_name: str, deleted_files: Union[str, List[str]], verbose: bool = False):
        """Handle deleted files by removing their entities and orphaned relations."""
        # Convert single path to list for unified handling
        if isinstance(deleted_files, str):
            deleted_files = [deleted_files]
            
        if not deleted_files:
            return
        
        total_entities_deleted = 0
        
        try:
            for deleted_file in deleted_files:
                logger.info(f"🗑️ Handling deleted file: {deleted_file}")
                
                # State file always stores relative paths, construct the full path
                # Note: deleted_file is always relative from state file (see _get_current_state)
                # Don't use .resolve() as it adds /private on macOS, but entities are stored without it
                full_path = str(self.project_path / deleted_file)
                
                if verbose:
                    logger.debug(f"   📁 Resolved to: {full_path}")
                
                # Use the vector store's find_entities_for_file method
                logger.debug(f"   🔍 Finding ALL entities for file: {full_path}")
                
                point_ids = []
                try:
                    # Use the elegant single-query method
                    found_entities = self.vector_store.find_entities_for_file(collection_name, full_path)
                    
                    if found_entities:
                        logger.debug(f"   ✅ Found {len(found_entities)} entities for file")
                        for entity in found_entities:
                            entity_name = entity.get('name', 'Unknown')
                            entity_type = entity.get('type', 'unknown')
                            entity_id = entity.get('id')
                            logger.debug(f"      🆔 ID: {entity_id}, name: '{entity_name}', type: {entity_type}")
                        
                        # Extract point IDs for deletion
                        point_ids = [entity['id'] for entity in found_entities]
                    else:
                        logger.debug(f"   ⚠️ No entities found for {deleted_file}")
                        
                except Exception as e:
                    logger.error(f"   ❌ Error finding entities: {e}")
                    point_ids = []
                
                # Remove duplicates and delete all found points
                point_ids = list(set(point_ids))
                logger.info(f"   🎯 Total unique point IDs to delete: {len(point_ids)}")
                if point_ids and verbose:
                    logger.debug(f"      🆔 Point IDs: {point_ids}")
                    
                if point_ids:
                    # Delete the points
                    logger.info(f"🗑️ DEBUG: About to DELETE from Qdrant - file: '{deleted_file}' resolved to: '{full_path}' with {len(point_ids)} points")
                    logger.info(f"   🗑️ Attempting to delete {len(point_ids)} points...")
                    delete_result = self.vector_store.delete_points(collection_name, point_ids)
                    
                    if delete_result.success:
                        entities_deleted = len(point_ids)
                        total_entities_deleted += entities_deleted
                        logger.info(f"   ✅ Successfully removed {entities_deleted} entities from {deleted_file}")
                    else:
                        logger.error(f"   ❌ Failed to remove entities from {deleted_file}: {delete_result.errors}")
                else:
                    logger.warning(f"   ⚠️ No entities found for {deleted_file} - nothing to delete")
            
            # NEW: Clean up orphaned relations after entity deletion
            if total_entities_deleted > 0:
                if verbose:
                    logger.info(f"🔍 Starting orphan cleanup after deleting {total_entities_deleted} entities from {len(deleted_files)} files:")
                    for df in deleted_files:
                        logger.info(f"   📁 {df}")
                
                orphaned_deleted = self.vector_store._cleanup_orphaned_relations(collection_name, verbose)
                if verbose and orphaned_deleted > 0:
                    logger.info(f"✅ Cleanup complete: {total_entities_deleted} entities, {orphaned_deleted} orphaned relations removed")
                elif verbose:
                    logger.info(f"✅ Cleanup complete: {total_entities_deleted} entities removed, no orphaned relations found")
                        
        except Exception as e:
            logger.error(f"Error handling deleted files: {e}")
    
    
    

    
    def _is_test_file(self, file_path: Path) -> bool:
        """Check if a file is a test file - DISABLED."""
        return False