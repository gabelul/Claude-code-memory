from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import time
from tree_sitter import Node
from .base_parsers import TreeSitterParser
from .parser import ParserResult
from .entities import Entity, Relation, EntityChunk, EntityType, RelationType, EntityFactory, RelationFactory


class JavaScriptParser(TreeSitterParser):
    """Parse JS/TS files with tree-sitter, optional TSServer for semantics."""
    
    SUPPORTED_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
    
    def __init__(self, config: Dict[str, Any] = None):
        import tree_sitter_javascript as tsjs
        super().__init__(tsjs, config)
        self.ts_server = self._init_ts_server() if config and config.get('use_ts_server') else None
        
        # Store language modules for TypeScript support
        try:
            import tree_sitter_typescript as tsts
            self.ts_language = tsts.language_typescript()
            self.tsx_language = tsts.language_tsx()
        except ImportError:
            self.ts_language = None
            self.tsx_language = None
        
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        return file_path.suffix in self.SUPPORTED_EXTENSIONS
    
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return self.SUPPORTED_EXTENSIONS
    
    def parse_tree(self, content: str, file_path: Path = None):
        """Parse content with appropriate language based on file extension."""
        if file_path and file_path.suffix in ['.ts'] and self.ts_language:
            # Use TypeScript grammar for .ts files
            from tree_sitter import Parser, Language
            parser = Parser(Language(self.ts_language))
            return parser.parse(bytes(content, "utf8"))
        elif file_path and file_path.suffix in ['.tsx'] and self.tsx_language:
            # Use TSX grammar for .tsx files
            from tree_sitter import Parser, Language
            parser = Parser(Language(self.tsx_language))
            return parser.parse(bytes(content, "utf8"))
        else:
            # Use JavaScript grammar for .js, .jsx, .mjs, .cjs files
            return super().parse_tree(content)
        
    def parse(self, file_path: Path) -> ParserResult:
        """Extract functions, classes, imports with progressive disclosure."""
        start_time = time.time()
        result = ParserResult(file_path=file_path, entities=[], relations=[])
        
        try:
            # Read file and calculate hash
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result.file_hash = self._get_file_hash(file_path)
            tree = self.parse_tree(content, file_path)
            
            # Check for syntax errors
            if self._has_syntax_errors(tree):
                result.errors.append(f"Syntax errors detected in {file_path.name}")
            
            # Extract entities and chunks
            entities = []
            chunks = []
            
            # Extract functions (including arrow functions)
            for node in self._find_nodes_by_type(tree.root_node, 
                ['function_declaration', 'arrow_function', 'function_expression', 'method_definition']):
                entity, entity_chunks = self._create_function_entity(node, file_path, content)
                if entity:
                    entities.append(entity)
                    chunks.extend(entity_chunks)
            
            # Extract classes
            for node in self._find_nodes_by_type(tree.root_node, ['class_declaration', 'class_expression']):
                entity, entity_chunks = self._create_class_entity(node, file_path, content)
                if entity:
                    entities.append(entity)
                    chunks.extend(entity_chunks)
            
            # Extract TypeScript interfaces
            for node in self._find_nodes_by_type(tree.root_node, ['interface_declaration']):
                entity, entity_chunks = self._create_interface_entity(node, file_path, content)
                if entity:
                    entities.append(entity)
                    chunks.extend(entity_chunks)
            
            # Extract imports
            relations = []
            for node in self._find_nodes_by_type(tree.root_node, ['import_statement', 'import_from']):
                relation = self._create_import_relation(node, file_path, content)
                if relation:
                    relations.append(relation)
            
            # Extract dynamic JSON/file loading patterns
            json_relations = self._extract_json_loading_patterns(tree.root_node, file_path, content)
            relations.extend(json_relations)
            
            # Create file entity
            file_entity = self._create_file_entity(file_path, len(entities), "javascript")
            entities.insert(0, file_entity)
            
            # Create containment relations
            file_name = str(file_path)
            for entity in entities[1:]:  # Skip file entity
                if entity.entity_type in [EntityType.FUNCTION, EntityType.CLASS]:
                    relation = RelationFactory.create_contains_relation(file_name, entity.name)
                    relations.append(relation)
            
            result.entities = entities
            result.relations = relations
            result.implementation_chunks = chunks
            
        except Exception as e:
            result.errors.append(f"JavaScript parsing failed: {e}")
        
        result.parsing_time = time.time() - start_time
        return result
        
    def _create_function_entity(self, node: Node, file_path: Path, content: str) -> Tuple[Optional[Entity], List[EntityChunk]]:
        """Create function entity with metadata and implementation chunks."""
        name = self._extract_function_name(node, content)
        if not name:
            return None, []
        
        # Create entity
        entity = EntityFactory.create_function_entity(
            name=name,
            file_path=file_path,
            line_number=node.start_point[0] + 1,
            metadata={
                "end_line": node.end_point[0] + 1,
                "source": "tree-sitter",
                "node_type": node.type
            }
        )
        
        # Create chunks
        chunks = []
        
        # Metadata chunk
        signature = self._extract_function_signature(node, content)
        chunks.append(EntityChunk(
            id=self._create_chunk_id(file_path, name, "metadata"),
            entity_name=name,
            chunk_type="metadata",
            content=signature,
            metadata={
                "entity_type": "function",
                "file_path": str(file_path),
                "line_number": node.start_point[0] + 1,
                "has_implementation": True
            }
        ))
        
        # Implementation chunk
        implementation = self.extract_node_text(node, content)
        chunks.append(EntityChunk(
            id=self._create_chunk_id(file_path, name, "implementation"),
            entity_name=name,
            chunk_type="implementation",
            content=implementation,
            metadata={
                "entity_type": "function",
                "file_path": str(file_path),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "semantic_metadata": {
                    "calls": self._extract_function_calls(implementation),
                    "complexity": self._calculate_complexity(implementation)
                }
            }
        ))
        
        return entity, chunks
    
    def _extract_function_name(self, node: Node, content: str) -> Optional[str]:
        """Extract function name from various function node types."""
        # Handle different function types
        if node.type == 'method_definition':
            # For class methods
            name_node = node.child_by_field_name('name')
            if name_node:
                return self.extract_node_text(name_node, content)
        
        # For regular functions
        name_node = node.child_by_field_name('name')
        if name_node:
            return self.extract_node_text(name_node, content)
        
        # For arrow functions assigned to variables
        if node.type == 'arrow_function' and node.parent:
            if node.parent.type == 'variable_declarator':
                id_node = node.parent.child_by_field_name('name')
                if id_node:
                    return self.extract_node_text(id_node, content)
        
        return None
    
    def _extract_function_signature(self, node: Node, content: str) -> str:
        """Extract function signature with parameters and return type."""
        name = self._extract_function_name(node, content) or 'anonymous'
        
        # Get parameters
        params_node = node.child_by_field_name('parameters')
        params = "()"
        if params_node:
            params = self.extract_node_text(params_node, content)
        
        # Get return type for TypeScript
        return_type = ""
        type_node = node.child_by_field_name('return_type')
        if type_node:
            return_type = f": {self.extract_node_text(type_node, content)}"
        
        # Handle different function types
        if node.type == 'arrow_function':
            return f"const {name} = {params} => {{...}}{return_type}"
        else:
            return f"function {name}{params}{return_type}"
    
    def _extract_function_calls(self, implementation: str) -> List[str]:
        """Extract function calls from implementation (simple heuristic)."""
        import re
        # Simple regex to find function calls
        call_pattern = r'(\w+)\s*\('
        calls = re.findall(call_pattern, implementation)
        # Filter out keywords
        keywords = {'if', 'for', 'while', 'switch', 'catch', 'function', 'class', 'return'}
        return list(set([call for call in calls if call not in keywords]))
    
    def _calculate_complexity(self, implementation: str) -> int:
        """Calculate cyclomatic complexity (simplified)."""
        complexity = 1
        complexity_keywords = ['if', 'else if', 'for', 'while', 'case', 'catch', '?', '&&', '||']
        for keyword in complexity_keywords:
            complexity += implementation.count(keyword)
        return complexity
    
    def _create_class_entity(self, node: Node, file_path: Path, content: str) -> Tuple[Optional[Entity], List[EntityChunk]]:
        """Create class entity with chunks."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None, []
        
        name = self.extract_node_text(name_node, content)
        
        # Create entity
        entity = EntityFactory.create_class_entity(
            name=name,
            file_path=file_path,
            line_number=node.start_point[0] + 1,
            metadata={
                "end_line": node.end_point[0] + 1,
                "source": "tree-sitter"
            }
        )
        
        # Create chunks
        chunks = []
        
        # Metadata chunk
        chunks.append(EntityChunk(
            id=self._create_chunk_id(file_path, name, "metadata"),
            entity_name=name,
            chunk_type="metadata",
            content=f"class {name}",
            metadata={
                "entity_type": "class",
                "file_path": str(file_path),
                "line_number": node.start_point[0] + 1,
                "has_implementation": True
            }
        ))
        
        # Implementation chunk
        chunks.append(EntityChunk(
            id=self._create_chunk_id(file_path, name, "implementation"),
            entity_name=name,
            chunk_type="implementation",
            content=self.extract_node_text(node, content),
            metadata={
                "entity_type": "class",
                "file_path": str(file_path),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1
            }
        ))
        
        return entity, chunks
    
    def _create_interface_entity(self, node: Node, file_path: Path, content: str) -> Tuple[Optional[Entity], List[EntityChunk]]:
        """Create TypeScript interface entity."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None, []
        
        name = self.extract_node_text(name_node, content)
        
        # Interfaces are like classes but for TypeScript
        entity = Entity(
            name=name,
            entity_type=EntityType.CLASS,  # Reuse class type for interfaces
            observations=[f"TypeScript interface: {name}"],
            file_path=file_path,
            line_number=node.start_point[0] + 1,
            end_line_number=node.end_point[0] + 1
        )
        
        # Create metadata chunk only (interfaces have no implementation)
        chunks = [EntityChunk(
            id=self._create_chunk_id(file_path, name, "metadata"),
            entity_name=name,
            chunk_type="metadata",
            content=self.extract_node_text(node, content),
            metadata={
                "entity_type": "interface",
                "file_path": str(file_path),
                "line_number": node.start_point[0] + 1,
                "has_implementation": False
            }
        )]
        
        return entity, chunks
    
    def _create_import_relation(self, node: Node, file_path: Path, content: str) -> Optional[Relation]:
        """Create import relation from import statement."""
        # Find the source/module being imported
        source_node = None
        
        # Handle different import statement structures
        for child in node.children:
            if child.type == 'string' and child.parent.type in ['import_statement', 'import_from']:
                source_node = child
                break
        
        if not source_node:
            return None
        
        # Extract module name, removing quotes
        module_name = self.extract_node_text(source_node, content).strip('"\'')
        
        return RelationFactory.create_imports_relation(
            importer=str(file_path),
            imported=module_name,
            import_type="module"
        )
    
    def _extract_json_loading_patterns(self, root: Node, file_path: Path, content: str) -> List[Relation]:
        """Extract dynamic JSON loading patterns like fetch(), require(), json.load()."""
        relations = []
        
        # Find all function calls
        for call in self._find_nodes_by_type(root, ['call_expression']):
            call_text = self.extract_node_text(call, content)
            
            # Pattern 1: fetch('config.json')
            if 'fetch(' in call_text:
                json_file = self._extract_string_from_call(call, content, 'fetch')
                if json_file and json_file.endswith('.json'):
                    relation = RelationFactory.create_imports_relation(
                        importer=str(file_path),
                        imported=json_file,
                        import_type="json_fetch"
                    )
                    relations.append(relation)
            
            # Pattern 2: require('./config.json')
            elif 'require(' in call_text:
                json_file = self._extract_string_from_call(call, content, 'require')
                if json_file and json_file.endswith('.json'):
                    relation = RelationFactory.create_imports_relation(
                        importer=str(file_path),
                        imported=json_file,
                        import_type="json_require"
                    )
                    relations.append(relation)
            
            # Pattern 3: JSON.parse() with file content
            elif 'JSON.parse(' in call_text:
                # Look for potential file references in the arguments
                for child in call.children:
                    if child.type == 'arguments':
                        arg_text = self.extract_node_text(child, content)
                        # Simple heuristic: if contains .json in string
                        if '.json' in arg_text:
                            import re
                            json_match = re.search(r'["\']([^"\']*\.json)["\']', arg_text)
                            if json_match:
                                json_file = json_match.group(1)
                                relation = RelationFactory.create_imports_relation(
                                    importer=str(file_path),
                                    imported=json_file,
                                    import_type="json_parse"
                                )
                                relations.append(relation)
        
        return relations
    
    def _extract_string_from_call(self, call_node: Node, content: str, function_name: str) -> Optional[str]:
        """Extract string argument from a function call."""
        # Find arguments node
        for child in call_node.children:
            if child.type == 'arguments':
                # Get first string argument
                for arg in child.children:
                    if arg.type == 'string':
                        string_value = self.extract_node_text(arg, content)
                        # Remove quotes
                        return string_value.strip('\'"')
        return None
    
    def _init_ts_server(self):
        """Initialize TypeScript language server (stub for future implementation)."""
        # Future: Could integrate with tsserver for advanced type inference
        return None