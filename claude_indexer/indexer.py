"""Core indexing orchestrator - stateless domain service."""

import time
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .config import IndexerConfig
from .analysis.parser import ParserRegistry, ParserResult
from .analysis.entities import Entity, Relation
from .embeddings.base import Embedder
from .storage.base import VectorStore
from .logging import get_logger

logger = get_logger()


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
        
    def _get_state_directory(self) -> Path:
        """Get state directory (configurable for test isolation)."""
        # Use configured state directory if provided (for tests)
        if self.config.state_directory is not None:
            state_dir = self.config.state_directory
        else:
            # Default to centralized state directory for production
            state_dir = Path.home() / '.claude-indexer' / 'state'
        
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir
    
    def _get_state_file(self, collection_name: str) -> Path:
        """Get collection-specific state file with atomic migration."""
        import hashlib
        
        # Create unique project identifier using path hash
        project_hash = hashlib.md5(str(self.project_path).encode()).hexdigest()[:8]
        filename = f"{project_hash}_{collection_name}.json"
        
        # Check for migration from legacy location
        legacy_state = self.project_path / f".indexer_state_{collection_name}.json"
        new_state = self._get_state_directory() / filename
        
        # Atomic migration with race condition protection
        if legacy_state.exists() and not new_state.exists():
            temp_file = None
            try:
                # Use atomic two-step rename to prevent race conditions
                temp_file = new_state.with_suffix('.tmp')
                legacy_state.rename(temp_file)  # Atomic move from legacy
                temp_file.rename(new_state)     # Atomic move to final location
                logger.info(f"Migrated state file: {legacy_state} -> {new_state}")
            except FileNotFoundError:
                # Another process already migrated it - this is expected
                # Clean up temp file if it exists (edge case handling)
                if temp_file and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors
            except Exception as e:
                # Clean up temp file if it exists
                if temp_file and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors
                logger.warning(f"Migration failed, using legacy location: {e}")
                return legacy_state  # Graceful fallback to legacy location
        
        return new_state
    
    @property
    def state_file(self) -> Path:
        """Default state file for backward compatibility with tests."""
        return self._get_state_file("default")
    
    def index_project(self, collection_name: str, include_tests: bool = False) -> IndexingResult:
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
                
                # Handle deleted files
                if deleted_files:
                    self._handle_deleted_files(collection_name, deleted_files)
                    result.warnings.append(f"Handled {len(deleted_files)} deleted files")
            else:
                files_to_process = self._find_all_files(include_tests)
                deleted_files = []
            
            if not files_to_process:
                result.warnings.append("No files to process")
                result.processing_time = time.time() - start_time
                return result
            
            self.logger.info(f"Found {len(files_to_process)} files to process")
            
            # Process files in batches
            batch_size = self.config.batch_size
            all_entities = []
            all_relations = []
            
            for i in range(0, len(files_to_process), batch_size):
                batch = files_to_process[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(files_to_process) + batch_size - 1) // batch_size
                self.logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
                
                batch_entities, batch_relations, batch_errors = self._process_file_batch(batch)
                
                all_entities.extend(batch_entities)
                all_relations.extend(batch_relations)
                result.errors.extend(batch_errors)
                
                # Update metrics
                result.files_processed += len([f for f in batch if f not in batch_errors])
                result.files_failed += len(batch_errors)
            
            # Store vectors using direct Qdrant automation
            if all_entities or all_relations:
                # Use direct Qdrant automation via existing _store_vectors method
                storage_success = self._store_vectors(collection_name, all_entities, all_relations)
                if not storage_success:
                    result.success = False
                    result.errors.append("Failed to store vectors in Qdrant")
                else:
                    result.entities_created = len(all_entities)
                    result.relations_created = len(all_relations)
            
            # Update state file
            if result.success:
                self._save_state(files_to_process, collection_name)
            
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
            # Parse file
            parse_result = self.parser_registry.parse_file(file_path)
            
            if not parse_result.success:
                result.success = False
                result.files_failed = 1
                result.errors.extend(parse_result.errors)
                return result
            
            # Use batch processing like the project indexer
            storage_success = self._store_vectors(collection_name, parse_result.entities, parse_result.relations)
            
            if storage_success:
                result.files_processed = 1
                result.entities_created = len(parse_result.entities)
                result.relations_created = len(parse_result.relations)
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
                print(f"Collection '{collection_name}' does not exist")
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
            print(f"Search failed: {e}")
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
            print(f"Failed to clear collection: {e}")
            return False
    
    
    
    def _find_all_files(self, include_tests: bool = False) -> List[Path]:
        """Find all source files in the project."""
        files = []
        
        for extension in self.parser_registry.get_supported_extensions():
            pattern = f"**/*{extension}"
            found = list(self.project_path.glob(pattern))
            files.extend(found)
        
        # Filter files
        filtered_files = []
        for file_path in files:
            # Skip hidden directories and files
            if any(part.startswith('.') for part in file_path.parts):
                continue
            
            # Skip common ignore patterns
            ignore_patterns = ['venv', '__pycache__', 'node_modules', '.git']
            if any(pattern in str(file_path) for pattern in ignore_patterns):
                continue
            
            # Skip test files unless included
            if not include_tests and self._is_test_file(file_path):
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
    
    def _process_file_batch(self, files: List[Path]) -> Tuple[List[Entity], List[Relation], List[str]]:
        """Process a batch of files."""
        all_entities = []
        all_relations = []
        errors = []
        
        for file_path in files:
            try:
                relative_path = file_path.relative_to(self.project_path)
                self.logger.debug(f"Processing file: {relative_path}")
                
                result = self.parser_registry.parse_file(file_path)
                
                if result.success:
                    all_entities.extend(result.entities)
                    all_relations.extend(result.relations)
                    self.logger.debug(f"  Found {len(result.entities)} entities, {len(result.relations)} relations")
                else:
                    errors.append(str(file_path))
                    self.logger.warning(f"  Failed to parse {relative_path}")
                    
            except Exception as e:
                errors.append(str(file_path))
                self.logger.error(f"  Error processing {file_path}: {e}")
        
        return all_entities, all_relations, errors
    
    def _store_vectors(self, collection_name: str, entities: List[Entity], 
                      relations: List[Relation]) -> bool:
        """Store entities and relations in vector database using batch processing."""
        try:
            all_points = []
            total_tokens = 0
            total_cost = 0.0
            total_requests = 0
            
            # Batch process entities
            if entities:
                entity_texts = [self._entity_to_text(entity) for entity in entities]
                embedding_results = self.embedder.embed_batch(entity_texts)
                
                # Collect cost data from embedding results
                for embedding_result in embedding_results:
                    if hasattr(embedding_result, 'token_count') and embedding_result.token_count:
                        total_tokens += embedding_result.token_count
                    if hasattr(embedding_result, 'cost_estimate') and embedding_result.cost_estimate:
                        total_cost += embedding_result.cost_estimate
                
                # Count successful requests (batch counts as requests based on actual API calls)
                if hasattr(self.embedder, 'get_usage_stats'):
                    # Get current stats to track requests made during this operation
                    stats_before = getattr(self, '_last_usage_stats', {'total_requests': 0})
                    current_stats = self.embedder.get_usage_stats()
                    total_requests += max(0, current_stats.get('total_requests', 0) - stats_before.get('total_requests', 0))
                    self._last_usage_stats = current_stats
                
                for entity, embedding_result in zip(entities, embedding_results):
                    if embedding_result.success:
                        point = self.vector_store.create_entity_point(
                            entity, embedding_result.embedding, collection_name
                        )
                        all_points.append(point)
            
            # Batch process relations
            if relations:
                relation_texts = [self._relation_to_text(relation) for relation in relations]
                embedding_results = self.embedder.embed_batch(relation_texts)
                
                # Collect cost data from embedding results
                for embedding_result in embedding_results:
                    if hasattr(embedding_result, 'token_count') and embedding_result.token_count:
                        total_tokens += embedding_result.token_count
                    if hasattr(embedding_result, 'cost_estimate') and embedding_result.cost_estimate:
                        total_cost += embedding_result.cost_estimate
                
                # Update request count
                if hasattr(self.embedder, 'get_usage_stats'):
                    stats_before = getattr(self, '_last_usage_stats', {'total_requests': 0})
                    current_stats = self.embedder.get_usage_stats()
                    total_requests += max(0, current_stats.get('total_requests', 0) - stats_before.get('total_requests', 0))
                    self._last_usage_stats = current_stats
                
                for relation, embedding_result in zip(relations, embedding_results):
                    if embedding_result.success:
                        point = self.vector_store.create_relation_point(
                            relation, embedding_result.embedding, collection_name
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
                result = self.vector_store.batch_upsert(collection_name, all_points)
                return result.success
            
            return True
            
        except Exception as e:
            print(f"Error in _store_vectors: {e}")
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
                import json
                with open(state_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_state(self, files: List[Path], collection_name: str):
        """Save current indexing state."""
        try:
            state = self._get_current_state(files)
            state_file = self._get_state_file(collection_name)
            import json
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Failed to save state: {e}")
    
    def _handle_deleted_files(self, collection_name: str, deleted_files: List[str]):
        """Handle deleted files by removing their entities."""
        if not deleted_files:
            return
        
        try:
            for deleted_file in deleted_files:
                print(f"   Removing entities from deleted file: {deleted_file}")
                
                # Convert relative path to absolute path for matching
                if not deleted_file.startswith('/'):
                    # This is a relative path from the state file
                    # Use resolve() to handle symlinks (e.g., /var -> /private/var on macOS)
                    full_path = str((self.project_path / deleted_file).resolve())
                else:
                    # Also resolve absolute paths to handle symlinks
                    full_path = str(Path(deleted_file).resolve())
                
                # Use a proper dummy vector for search
                dummy_vector = [0.1] * 1536  # Small non-zero values
                
                # First search: Find entities with file_path matching
                filter_conditions_path = {"file_path": full_path}
                search_result = self.vector_store.search_similar(
                    collection_name=collection_name,
                    query_vector=dummy_vector,
                    limit=1000,  # Get all matches for this file
                    score_threshold=0.0,  # Include all results
                    filter_conditions=filter_conditions_path
                )
                
                point_ids = []
                if search_result.success and search_result.results:
                    point_ids.extend([result["id"] for result in search_result.results])
                
                # Second search: Find File entities where name = full_path
                # This catches File entities that use path as their name
                filter_conditions_name = {"name": full_path}
                search_result_name = self.vector_store.search_similar(
                    collection_name=collection_name,
                    query_vector=dummy_vector,
                    limit=1000,
                    score_threshold=0.0,
                    filter_conditions=filter_conditions_name
                )
                
                if search_result_name.success and search_result_name.results:
                    point_ids.extend([result["id"] for result in search_result_name.results])
                
                # Remove duplicates and delete all found points
                point_ids = list(set(point_ids))
                if point_ids:
                    
                    # Delete the points
                    delete_result = self.vector_store.delete_points(collection_name, point_ids)
                    
                    if delete_result.success:
                        print(f"   Removed {len(point_ids)} entities from {deleted_file}")
                    else:
                        print(f"   Warning: Failed to remove entities from {deleted_file}: {delete_result.errors}")
                else:
                    print(f"   No entities found for {deleted_file}")
                        
        except Exception as e:
            print(f"Error handling deleted files: {e}")
    
    
    

    
    def _is_test_file(self, file_path: Path) -> bool:
        """Check if a file is a test file."""
        name = file_path.name.lower()
        path_str = str(file_path).lower()
        
        return (
            name.startswith('test_') or
            name.endswith('_test.py') or
            '/test/' in path_str or
            '/tests/' in path_str
        )