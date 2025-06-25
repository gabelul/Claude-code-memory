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
        
        # State file will be set per collection
        self._state_file_base = project_path
        
    def _get_state_file(self, collection_name: str) -> Path:
        """Get collection-specific state file path."""
        return self._state_file_base / f".indexer_state_{collection_name}.json"
    
    def index_project(self, collection_name: str, include_tests: bool = False,
                     incremental: bool = False, force: bool = False) -> IndexingResult:
        """Index an entire project."""
        start_time = time.time()
        result = IndexingResult(success=True, operation="incremental" if incremental else "full")
        
        try:
            # Find files to process
            if incremental and not force:
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
            
            # Choose storage method based on vector store type
            if all_entities or all_relations:
                # Check for Qdrant backend (direct or cached) for direct automation
                is_qdrant_backend = (
                    hasattr(self.vector_store, 'client') or  # Direct QdrantStore
                    (hasattr(self.vector_store, 'backend') and hasattr(self.vector_store.backend, 'client'))  # CachingVectorStore wrapping QdrantStore
                )
                
                if is_qdrant_backend:
                    # Use direct Qdrant automation via existing _store_vectors method
                    storage_success = self._store_vectors(collection_name, all_entities, all_relations)
                    if not storage_success:
                        result.success = False
                        result.errors.append("Failed to store vectors in Qdrant")
                    else:
                        result.entities_created = len(all_entities)
                        result.relations_created = len(all_relations)
                else:
                    # Fall back to MCP command generation (for MCP backend)
                    mcp_success = self._send_to_mcp(all_entities, all_relations)
                    if not mcp_success:
                        result.success = False
                        result.errors.append("Failed to generate MCP commands")
                    else:
                        result.entities_created = len(all_entities)
                        result.relations_created = len(all_relations)
            
            # Finalize storage (important for MCP command generator)
            self._finalize_storage(collection_name)
            
            # Update state file
            if result.success:
                self._save_state(files_to_process, collection_name)
            
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
    
    def generate_mcp_commands(self, entities: List[Entity], relations: List[Relation],
                             collection_name: str) -> str:
        """Generate MCP commands for manual execution."""
        commands = []
        
        if entities:
            # Convert entities to MCP format
            entity_dicts = [entity.to_mcp_dict() for entity in entities]
            
            # Split into batches of 10 for readability
            batch_size = 10
            for i in range(0, len(entity_dicts), batch_size):
                batch = entity_dicts[i:i + batch_size]
                entities_json = json.dumps(batch, indent=2)
                commands.append(f"# Entity batch {(i // batch_size) + 1}")
                commands.append(f"mcp__{collection_name}-memory__create_entities({entities_json})")
                commands.append("")
        
        if relations:
            # Convert relations to MCP format
            relation_dicts = [relation.to_mcp_dict() for relation in relations]
            
            # Split into batches of 20 for readability
            batch_size = 20
            for i in range(0, len(relation_dicts), batch_size):
                batch = relation_dicts[i:i + batch_size]
                relations_json = json.dumps(batch, indent=2)
                commands.append(f"# Relation batch {(i // batch_size) + 1}")
                commands.append(f"mcp__{collection_name}-memory__create_relations({relations_json})")
                commands.append("")
        
        return "\n".join(commands)
    
    def save_mcp_commands_to_file(self, entities: List[Entity], relations: List[Relation],
                                  collection_name: str) -> Path:
        """Save MCP commands to file for manual execution."""
        output_dir = self.project_path / 'mcp_output'
        output_dir.mkdir(exist_ok=True)
        
        commands = self.generate_mcp_commands(entities, relations, collection_name)
        commands_file = output_dir / f"{collection_name}_mcp_commands.txt"
        
        with open(commands_file, 'w') as f:
            f.write(commands)
        
        return commands_file
    
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
    
    def _get_files_needing_processing(self, include_tests: bool = False, force: bool = False, collection_name: str = None) -> List[Path]:
        """Get files that need processing for incremental indexing."""
        if force:
            return self._find_all_files(include_tests)
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
            
            # Batch process entities
            if entities:
                entity_texts = [self._entity_to_text(entity) for entity in entities]
                embedding_results = self.embedder.embed_batch(entity_texts)
                
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
                
                for relation, embedding_result in zip(relations, embedding_results):
                    if embedding_result.success:
                        point = self.vector_store.create_relation_point(
                            relation, embedding_result.embedding, collection_name
                        )
                        all_points.append(point)
            
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
    
    def _send_to_mcp(self, entities: List[Entity], relations: List[Relation]) -> bool:
        """Send to MCP (auto-printing like old indexer.py)."""
        try:
            success = True
            
            # Convert entities to MCP format
            if entities:
                mcp_entities = []
                for entity in entities:
                    mcp_entity = {
                        "name": entity.name,
                        "entityType": entity.entity_type.value,
                        "observations": entity.observations
                    }
                    mcp_entities.append(mcp_entity)
                
                success &= self._call_mcp_api("create_entities", {"entities": mcp_entities})
            
            # Convert relations to MCP format  
            if relations:
                mcp_relations = []
                for relation in relations:
                    mcp_relation = {
                        "from": relation.from_entity,
                        "to": relation.to_entity, 
                        "relationType": relation.relation_type.value
                    }
                    mcp_relations.append(mcp_relation)
                
                success &= self._call_mcp_api("create_relations", {"relations": mcp_relations})
            
            return success
            
        except Exception as e:
            print(f"❌ MCP send failed: {e}")
            return False
    
    def _call_mcp_api(self, method: str, params: Dict[str, Any]) -> bool:
        """Execute MCP commands automatically - call functions directly from globals."""
        try:
            print(f"🚀 Executing MCP {method} automatically with {len(params.get('entities', params.get('relations', [])))} items")
            
            # Execute MCP commands directly - we have access to these functions in this environment
            if method == "create_entities":
                result = mcp__memory_project_memory__create_entities(params)
                print(f"✅ Entities created successfully: {result}")
                return True
                
            elif method == "create_relations":
                result = mcp__memory_project_memory__create_relations(params)
                print(f"✅ Relations created successfully: {result}")
                return True
                
            else:
                print(f"❌ Unknown MCP method: {method}")
                return False
            
        except NameError as e:
            # MCP functions not available in this environment - fall back to printing
            print(f"🔧 MCP functions not available ({e}), printing commands for manual execution:")
            return self._fallback_print_commands(method, params)
            
        except Exception as e:
            print(f"❌ MCP execution failed: {e}")
            # Fallback to printing commands for manual execution
            return self._fallback_print_commands(method, params)
    
    def _fallback_print_commands(self, method: str, params: Dict[str, Any]) -> bool:
        """Fallback to printing commands for manual execution."""
        collection_memory = f"memory-project-memory"
        mcp_command = f"mcp__{collection_memory}__{method}"
        params_json = json.dumps(params, indent=2)
        print(f"{mcp_command}({params_json})")
        print(f"✅ MCP {method} command printed for execution")
        return True

    def _finalize_storage(self, collection_name: str):
        """Finalize storage operations (important for MCP command generator)."""
        try:
            # Check if vector store has finalize method (e.g., MCPCommandGenerator)
            if hasattr(self.vector_store, 'finalize_commands'):
                result = self.vector_store.finalize_commands(collection_name)
        except Exception as e:
            print(f"Error finalizing storage: {e}")
    
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