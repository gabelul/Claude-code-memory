from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import time
from tree_sitter import Node
from .base_parsers import TreeSitterParser
from .parser import ParserResult
from .entities import Entity, Relation, EntityChunk, EntityType, RelationType, EntityFactory, RelationFactory


class JSONParser(TreeSitterParser):
    """Parse JSON with tree-sitter for structural relation extraction."""
    
    SUPPORTED_EXTENSIONS = ['.json']
    
    def __init__(self, config: Dict[str, Any] = None):
        import tree_sitter_json as tsjson
        super().__init__(tsjson, config)
        self.special_files = config.get('special_files', ['package.json', 'tsconfig.json', 'composer.json']) if config else ['package.json', 'tsconfig.json', 'composer.json']
        
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        return file_path.suffix in self.SUPPORTED_EXTENSIONS
    
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return self.SUPPORTED_EXTENSIONS
        
    def parse(self, file_path: Path) -> ParserResult:
        """Extract JSON structure as entities and relations."""
        start_time = time.time()
        result = ParserResult(file_path=file_path, entities=[], relations=[])
        
        try:
            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result.file_hash = self._get_file_hash(file_path)
            tree = self.parse_tree(content)
            
            # Check for syntax errors
            if self._has_syntax_errors(tree):
                result.errors.append(f"JSON syntax errors in {file_path.name}")
            
            entities = []
            relations = []
            chunks = []
            
            # Create file entity
            file_entity = self._create_file_entity(file_path, content_type="configuration")
            entities.append(file_entity)
            
            # Special handling for known JSON types
            if file_path.name in self.special_files:
                special_entities, special_relations = self._handle_special_json(
                    file_path, tree.root_node, content
                )
                entities.extend(special_entities)
                relations.extend(special_relations)
            else:
                # Generic JSON structure extraction
                root_obj = self._find_first_object(tree.root_node)
                if root_obj:
                    obj_entities, obj_relations = self._extract_object_structure(
                        root_obj, content, file_path, parent_path=""
                    )
                    entities.extend(obj_entities)
                    relations.extend(obj_relations)
            
            # Create chunks for searchability
            chunks = self._create_json_chunks(file_path, tree.root_node, content)
            
            result.entities = entities
            result.relations = relations
            result.implementation_chunks = chunks
            
        except Exception as e:
            result.errors.append(f"JSON parsing failed: {e}")
        
        result.parsing_time = time.time() - start_time
        return result
    
    def _find_first_object(self, node: Node) -> Optional[Node]:
        """Find the first object node in the tree."""
        if node.type == 'object':
            return node
        for child in node.children:
            obj = self._find_first_object(child)
            if obj:
                return obj
        return None
    
    def _extract_object_structure(self, node: Node, content: str, file_path: Path, 
                                parent_path: str) -> Tuple[List[Entity], List[Relation]]:
        """Extract entities and relations from JSON object structure."""
        entities = []
        relations = []
        
        # Process object pairs (key-value)
        for child in node.children:
            if child.type == 'pair':
                key_node = child.child_by_field_name('key')
                value_node = child.child_by_field_name('value')
                
                if key_node and value_node:
                    key = self.extract_node_text(key_node, content).strip('"')
                    current_path = f"{parent_path}.{key}" if parent_path else key
                    
                    # Create entity for this key
                    entity = Entity(
                        name=current_path,
                        entity_type=EntityType.DOCUMENTATION,  # JSON keys as documentation
                        observations=[f"JSON key: {key}"],
                        file_path=file_path,
                        line_number=key_node.start_point[0] + 1
                    )
                    entities.append(entity)
                    
                    # Create containment relation
                    parent = str(file_path) if not parent_path else parent_path
                    relation = RelationFactory.create_contains_relation(parent, current_path)
                    relations.append(relation)
                    
                    # Recursively process nested objects
                    if value_node.type == 'object':
                        nested_entities, nested_relations = self._extract_object_structure(
                            value_node, content, file_path, current_path
                        )
                        entities.extend(nested_entities)
                        relations.extend(nested_relations)
                    
                    # Process arrays
                    elif value_node.type == 'array':
                        # Create collection entity
                        array_entity = Entity(
                            name=f"{current_path}[]",
                            entity_type=EntityType.DOCUMENTATION,
                            observations=[f"JSON array: {key}"],
                            file_path=file_path,
                            line_number=value_node.start_point[0] + 1
                        )
                        entities.append(array_entity)
                        
                        # Array contains relation
                        relation = RelationFactory.create_contains_relation(
                            current_path, f"{current_path}[]"
                        )
                        relations.append(relation)
        
        return entities, relations
    
    def _handle_special_json(self, file_path: Path, root: Node, content: str) -> Tuple[List[Entity], List[Relation]]:
        """Special handling for known JSON file types."""
        entities = []
        relations = []
        
        if file_path.name == 'package.json':
            # Extract dependencies as import relations
            deps_entities, deps_relations = self._extract_package_dependencies(root, content, file_path)
            entities.extend(deps_entities)
            relations.extend(deps_relations)
            
        elif file_path.name == 'tsconfig.json':
            # Extract TypeScript configuration
            config_entities = self._extract_tsconfig_info(root, content, file_path)
            entities.extend(config_entities)
        
        return entities, relations
    
    def _extract_package_dependencies(self, root: Node, content: str, file_path: Path) -> Tuple[List[Entity], List[Relation]]:
        """Extract dependencies from package.json."""
        entities = []
        relations = []
        
        # Find dependencies and devDependencies objects
        for node in self._find_nodes_by_type(root, ['pair']):
            key_node = node.child_by_field_name('key')
            if key_node:
                key = self.extract_node_text(key_node, content).strip('"')
                if key in ['dependencies', 'devDependencies']:
                    value_node = node.child_by_field_name('value')
                    if value_node and value_node.type == 'object':
                        # Each dependency is an import relation
                        for pair in value_node.children:
                            if pair.type == 'pair':
                                dep_key = pair.child_by_field_name('key')
                                if dep_key:
                                    dep_name = self.extract_node_text(dep_key, content).strip('"')
                                    # Create import relation
                                    relation = RelationFactory.create_imports_relation(
                                        importer=str(file_path),
                                        imported=dep_name,
                                        import_type="npm_dependency"
                                    )
                                    relations.append(relation)
        
        return entities, relations
    
    def _extract_tsconfig_info(self, root: Node, content: str, file_path: Path) -> List[Entity]:
        """Extract TypeScript configuration info."""
        entities = []
        
        # Create entity for compiler options
        for node in self._find_nodes_by_type(root, ['pair']):
            key_node = node.child_by_field_name('key')
            if key_node:
                key = self.extract_node_text(key_node, content).strip('"')
                if key == 'compilerOptions':
                    entity = Entity(
                        name="TypeScript Compiler Options",
                        entity_type=EntityType.DOCUMENTATION,
                        observations=["TypeScript compiler configuration"],
                        file_path=file_path,
                        line_number=node.start_point[0] + 1
                    )
                    entities.append(entity)
        
        return entities
    
    def _create_json_chunks(self, file_path: Path, root: Node, content: str) -> List[EntityChunk]:
        """Create searchable chunks from JSON content."""
        chunks = []
        
        # For now, create a single chunk with the entire JSON
        # Future: Could chunk by top-level keys for large files
        chunks.append(EntityChunk(
            id=self._create_chunk_id(file_path, "content", "metadata"),
            entity_name=file_path.name,
            chunk_type="metadata",
            content=content[:1000],  # First 1000 chars for search
            metadata={
                "entity_type": "json_file",
                "file_path": str(file_path),
                "has_implementation": False
            }
        ))
        
        return chunks