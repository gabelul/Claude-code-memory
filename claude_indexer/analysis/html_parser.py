from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import time
from tree_sitter import Node
from .base_parsers import TreeSitterParser
from .parser import ParserResult
from .entities import Entity, Relation, EntityChunk, EntityType, RelationType, EntityFactory, RelationFactory


class HTMLParser(TreeSitterParser):
    """Parse HTML with tree-sitter for structure and components."""
    
    SUPPORTED_EXTENSIONS = ['.html', '.htm']
    
    def __init__(self, config: Dict[str, Any] = None):
        import tree_sitter_html as tshtml
        super().__init__(tshtml, config)
        
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        return file_path.suffix in self.SUPPORTED_EXTENSIONS
    
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return self.SUPPORTED_EXTENSIONS
        
    def parse(self, file_path: Path) -> ParserResult:
        """Extract HTML structure, IDs, classes, components."""
        start_time = time.time()
        result = ParserResult(file_path=file_path, entities=[], relations=[])
        
        try:
            # Read and parse HTML
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result.file_hash = self._get_file_hash(file_path)
            tree = self.parse_tree(content)
            
            # Check for syntax errors
            if self._has_syntax_errors(tree):
                result.errors.append(f"HTML syntax errors in {file_path.name}")
            
            entities = []
            relations = []
            chunks = []
            
            # Create file entity
            file_entity = self._create_file_entity(file_path, content_type="html")
            entities.append(file_entity)
            
            # Extract elements with IDs
            id_entities = self._extract_elements_with_ids(tree.root_node, content, file_path)
            entities.extend(id_entities)
            
            # Extract components (custom elements or component-like structures)
            component_entities = self._extract_components(tree.root_node, content, file_path)
            entities.extend(component_entities)
            
            # Extract links and form actions
            link_relations = self._extract_links(tree.root_node, content, file_path)
            relations.extend(link_relations)
            
            # Extract class references for CSS relations
            class_references = self._extract_class_references(tree.root_node, content, file_path)
            relations.extend(class_references)
            
            # Create containment relations
            file_name = str(file_path)
            for entity in entities[1:]:  # Skip file entity
                relation = RelationFactory.create_contains_relation(file_name, entity.name)
                relations.append(relation)
            
            # Create chunks for searchability
            chunks = self._create_html_chunks(file_path, tree.root_node, content)
            
            result.entities = entities
            result.relations = relations
            result.implementation_chunks = chunks
            
        except Exception as e:
            result.errors.append(f"HTML parsing failed: {e}")
        
        result.parsing_time = time.time() - start_time
        return result
    
    def _extract_elements_with_ids(self, root: Node, content: str, file_path: Path) -> List[Entity]:
        """Extract HTML elements that have id attributes."""
        entities = []
        
        for element in self._find_nodes_by_type(root, ['element']):
            # Find id attribute
            id_value = self._get_attribute_value(element, 'id', content)
            if id_value:
                tag_name = self._get_element_tag(element, content)
                entity_name = f"#{id_value}"
                
                entity = Entity(
                    name=entity_name,
                    entity_type=EntityType.DOCUMENTATION,  # HTML elements as documentation
                    observations=[
                        f"HTML element: {tag_name}#{id_value}",
                        f"Located in {file_path.name}"
                    ],
                    file_path=file_path,
                    line_number=element.start_point[0] + 1,
                    metadata={
                        "type": "html_element",
                        "tag": tag_name,
                        "id": id_value
                    }
                )
                entities.append(entity)
        
        return entities
    
    def _extract_components(self, root: Node, content: str, file_path: Path) -> List[Entity]:
        """Extract component-like structures (custom elements, elements with data attributes)."""
        entities = []
        
        for element in self._find_nodes_by_type(root, ['element']):
            tag_name = self._get_element_tag(element, content)
            
            # Check for custom elements (contain hyphen)
            if '-' in tag_name and tag_name not in ['input', 'meta', 'link']:
                entity = Entity(
                    name=f"<{tag_name}>",
                    entity_type=EntityType.CLASS,  # Components as classes
                    observations=[
                        f"Custom HTML component: {tag_name}",
                        f"Located in {file_path.name}"
                    ],
                    file_path=file_path,
                    line_number=element.start_point[0] + 1,
                    metadata={
                        "type": "html_component",
                        "tag": tag_name
                    }
                )
                entities.append(entity)
            
            # Check for elements with data-component attribute
            component_attr = self._get_attribute_value(element, 'data-component', content)
            if component_attr:
                entity = Entity(
                    name=f"Component:{component_attr}",
                    entity_type=EntityType.CLASS,
                    observations=[
                        f"Data component: {component_attr}",
                        f"Tag: {tag_name}",
                        f"Located in {file_path.name}"
                    ],
                    file_path=file_path,
                    line_number=element.start_point[0] + 1,
                    metadata={
                        "type": "data_component",
                        "tag": tag_name,
                        "component": component_attr
                    }
                )
                entities.append(entity)
        
        return entities
    
    def _extract_links(self, root: Node, content: str, file_path: Path) -> List[Relation]:
        """Extract link relations from href attributes and form actions."""
        relations = []
        
        # Extract links from regular elements
        for element in self._find_nodes_by_type(root, ['element']):
            tag_name = self._get_element_tag(element, content)
            
            if tag_name == 'a':
                href = self._get_attribute_value(element, 'href', content)
                if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                    relation = RelationFactory.create_imports_relation(
                        importer=str(file_path),
                        imported=href,
                        import_type="html_link"
                    )
                    relations.append(relation)
            
            elif tag_name == 'form':
                action = self._get_attribute_value(element, 'action', content)
                if action:
                    relation = RelationFactory.create_imports_relation(
                        importer=str(file_path),
                        imported=action,
                        import_type="form_action"
                    )
                    relations.append(relation)
            
            elif tag_name in ['script', 'link']:
                # Extract script src and link href
                src = self._get_attribute_value(element, 'src', content)
                href = self._get_attribute_value(element, 'href', content)
                resource = src or href
                
                if resource and not resource.startswith(('http:', 'https:', '//')):
                    relation = RelationFactory.create_imports_relation(
                        importer=str(file_path),
                        imported=resource,
                        import_type="html_resource"
                    )
                    relations.append(relation)
        
        # Handle script_element nodes separately (tree-sitter HTML specific)
        for script_element in self._find_nodes_by_type(root, ['script_element']):
            src = self._get_attribute_value(script_element, 'src', content)
            if src and not src.startswith(('http:', 'https:', '//')):
                relation = RelationFactory.create_imports_relation(
                    importer=str(file_path),
                    imported=src,
                    import_type="html_resource"
                )
                relations.append(relation)
        
        return relations
    
    def _extract_class_references(self, root: Node, content: str, file_path: Path) -> List[Relation]:
        """Extract class references for potential CSS relations."""
        relations = []
        
        for element in self._find_nodes_by_type(root, ['element']):
            class_value = self._get_attribute_value(element, 'class', content)
            if class_value:
                # Split multiple classes
                classes = class_value.split()
                for class_name in classes:
                    if class_name.strip():
                        relation = Relation(
                            from_entity=str(file_path),
                            to_entity=f".{class_name}",
                            relation_type=RelationType.USES,
                            context=f"HTML element uses CSS class",
                            metadata={"type": "css_class_reference"}
                        )
                        relations.append(relation)
        
        return relations
    
    def _get_element_tag(self, element: Node, content: str) -> str:
        """Get the tag name of an HTML element."""
        # Find start_tag child
        for child in element.children:
            if child.type == 'start_tag':
                # Look for tag_name child (second child after '<')
                for grandchild in child.children:
                    if grandchild.type == 'tag_name':
                        return self.extract_node_text(grandchild, content)
        return "unknown"
    
    def _get_attribute_value(self, element: Node, attr_name: str, content: str) -> Optional[str]:
        """Get the value of an attribute from an HTML element."""
        # Find start_tag
        start_tag = None
        for child in element.children:
            if child.type == 'start_tag':
                start_tag = child
                break
        
        if not start_tag:
            return None
        
        # Find attribute
        for child in start_tag.children:
            if child.type == 'attribute':
                # Check if this is the attribute we want
                attr_text = self.extract_node_text(child, content)
                if attr_text.startswith(f'{attr_name}='):
                    # Extract value from quotes
                    value_part = attr_text.split('=', 1)[1]
                    # Remove quotes
                    return value_part.strip('\'"')
        
        return None
    
    def _create_html_chunks(self, file_path: Path, root: Node, content: str) -> List[EntityChunk]:
        """Create searchable chunks from HTML content."""
        chunks = []
        
        # Create a chunk with the HTML content for search
        chunks.append(EntityChunk(
            id=self._create_chunk_id(file_path, "content", "metadata"),
            entity_name=file_path.name,
            chunk_type="metadata",
            content=content[:1000],  # First 1000 chars for search
            metadata={
                "entity_type": "html_file",
                "file_path": str(file_path),
                "has_implementation": False
            }
        ))
        
        return chunks