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


class CoreIndexer:
    """Stateless core indexing service orchestrating all components."""
    
    def __init__(self, config: IndexerConfig, embedder: Embedder, 
                 vector_store: VectorStore, project_path: Path):
        self.config = config
        self.embedder = embedder
        self.vector_store = vector_store
        self.project_path = project_path
        
        # Initialize parser registry
        self.parser_registry = ParserRegistry(project_path)
        
        # State management - use collection-specific state file for consistency
        self.state_file = project_path / f".indexer_state_core.json"
    
    def index_project(self, collection_name: str, include_tests: bool = False,
                     incremental: bool = False, force: bool = False) -> IndexingResult:
        """Index an entire project."""
        start_time = time.time()
        result = IndexingResult(success=True, operation="incremental" if incremental else "full")
        
        try:
            # Find files to process
            if incremental and not force:
                files_to_process, deleted_files = self._find_changed_files(include_tests)
                
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
            
            # Process files in batches
            batch_size = self.config.batch_size
            all_entities = []
            all_relations = []
            
            for i in range(0, len(files_to_process), batch_size):
                batch = files_to_process[i:i + batch_size]
                batch_entities, batch_relations, batch_errors = self._process_file_batch(batch)
                
                all_entities.extend(batch_entities)
                all_relations.extend(batch_relations)
                result.errors.extend(batch_errors)
                
                # Update metrics
                result.files_processed += len([f for f in batch if f not in batch_errors])
                result.files_failed += len(batch_errors)
            
            # Store in vector database
            if all_entities or all_relations:
                storage_success = self._store_vectors(collection_name, all_entities, all_relations)
                if not storage_success:
                    result.success = False
                    result.errors.append("Failed to store vectors")
                else:
                    result.entities_created = len(all_entities)
                    result.relations_created = len(all_relations)
            
            # Update state file
            if result.success:
                self._save_state(files_to_process)
            
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
            
            # Generate embeddings and store
            entities_with_embeddings = []
            relations_with_embeddings = []
            
            # Process entities
            for entity in parse_result.entities:
                text = self._entity_to_text(entity)
                embedding_result = self.embedder.embed_text(text)
                
                if embedding_result.success:
                    point = self.vector_store.create_entity_point(
                        entity, embedding_result.embedding, collection_name
                    )
                    entities_with_embeddings.append(point)
                else:
                    result.warnings.append(f"Failed to embed entity: {entity.name}")
            
            # Process relations
            for relation in parse_result.relations:
                text = self._relation_to_text(relation)
                embedding_result = self.embedder.embed_text(text)
                
                if embedding_result.success:
                    point = self.vector_store.create_relation_point(
                        relation, embedding_result.embedding, collection_name
                    )
                    relations_with_embeddings.append(point)
                else:
                    result.warnings.append(f"Failed to embed relation: {relation.from_entity} -> {relation.to_entity}")
            
            # Store vectors
            all_points = entities_with_embeddings + relations_with_embeddings
            if all_points:
                storage_result = self.vector_store.upsert_points(collection_name, all_points)
                
                if storage_result.success:
                    result.files_processed = 1
                    result.entities_created = len(entities_with_embeddings)
                    result.relations_created = len(relations_with_embeddings)
                    result.processed_files = [str(file_path)]
                else:
                    result.success = False
                    result.files_failed = 1
                    result.errors.extend(storage_result.errors)
            
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
    
    def clear_collection(self, collection_name: str) -> bool:
        """Clear all data from collection and state file."""
        try:
            # Clear vector store
            result = self.vector_store.clear_collection(collection_name)
            
            # Clear state file
            if self.state_file.exists():
                self.state_file.unlink()
            
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
    
    def _get_files_needing_processing(self, include_tests: bool = False, force: bool = False) -> List[Path]:
        """Get files that need processing for incremental indexing."""
        if force:
            return self._find_all_files(include_tests)
        return self._find_changed_files(include_tests)[0]
    
    def _find_changed_files(self, include_tests: bool = False) -> Tuple[List[Path], List[str]]:
        """Find files that have changed since last indexing."""
        current_files = self._find_all_files(include_tests)
        current_state = self._get_current_state(current_files)
        previous_state = self._load_state()
        
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
                result = self.parser_registry.parse_file(file_path)
                
                if result.success:
                    all_entities.extend(result.entities)
                    all_relations.extend(result.relations)
                else:
                    errors.append(str(file_path))
                    
            except Exception as e:
                errors.append(str(file_path))
        
        return all_entities, all_relations, errors
    
    def _store_vectors(self, collection_name: str, entities: List[Entity], 
                      relations: List[Relation]) -> bool:
        """Store entities and relations in vector database."""
        try:
            all_points = []
            
            # Process entities
            for entity in entities:
                text = self._entity_to_text(entity)
                embedding_result = self.embedder.embed_text(text)
                
                if embedding_result.success:
                    point = self.vector_store.create_entity_point(
                        entity, embedding_result.embedding, collection_name
                    )
                    all_points.append(point)
            
            # Process relations
            for relation in relations:
                text = self._relation_to_text(relation)
                embedding_result = self.embedder.embed_text(text)
                
                if embedding_result.success:
                    point = self.vector_store.create_relation_point(
                        relation, embedding_result.embedding, collection_name
                    )
                    all_points.append(point)
            
            # Batch store
            if all_points:
                result = self.vector_store.batch_upsert(collection_name, all_points)
                return result.success
            
            return True
            
        except Exception as e:
            print(f"Storage failed: {e}")
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
    
    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        """Load previous indexing state."""
        try:
            if self.state_file.exists():
                import json
                with open(self.state_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_state(self, files: List[Path]):
        """Save current indexing state."""
        try:
            state = self._get_current_state(files)
            import json
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Failed to save state: {e}")
    
    def _handle_deleted_files(self, collection_name: str, deleted_files: List[str]):
        """Handle deleted files by removing their entities."""
        # TODO: Implement entity deletion based on file tracking
        # This requires maintaining entity-to-file mappings
        pass
    
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