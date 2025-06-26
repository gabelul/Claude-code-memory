"""Data models for entities and relations extracted from code."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path


class EntityType(Enum):
    """Types of entities that can be extracted from code."""
    PROJECT = "project"
    DIRECTORY = "directory"
    FILE = "file" 
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    MODULE = "module"
    CONSTANT = "constant"
    DOCUMENTATION = "documentation"
    TEST = "test"


class RelationType(Enum):
    """Types of relationships between entities."""
    CONTAINS = "contains"
    IMPORTS = "imports"
    INHERITS = "inherits"
    CALLS = "calls"
    USES = "uses"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"
    DOCUMENTS = "documents"
    TESTS = "tests"
    REFERENCES = "references"


@dataclass(frozen=True)
class Entity:
    """Immutable entity representing a code component."""
    
    name: str
    entity_type: EntityType
    observations: List[str] = field(default_factory=list)
    
    # Optional metadata
    file_path: Optional[Path] = None
    line_number: Optional[int] = None
    end_line_number: Optional[int] = None
    docstring: Optional[str] = None
    signature: Optional[str] = None
    complexity_score: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate entity after creation."""
        if not self.name:
            raise ValueError("Entity name cannot be empty")
        if not self.observations:
            object.__setattr__(self, 'observations', [f"{self.entity_type.value.title()}: {self.name}"])
    
    @property
    def qualified_name(self) -> str:
        """Get fully qualified name including file path."""
        if self.file_path:
            return f"{self.file_path}:{self.name}"
        return self.name
    
    
    def add_observation(self, observation: str) -> 'Entity':
        """Create new entity with additional observation (immutable)."""
        new_observations = list(self.observations) + [observation]
        return Entity(
            name=self.name,
            entity_type=self.entity_type,
            observations=new_observations,
            file_path=self.file_path,
            line_number=self.line_number,
            end_line_number=self.end_line_number,
            docstring=self.docstring,
            signature=self.signature,
            complexity_score=self.complexity_score,
            metadata=self.metadata.copy()
        )


@dataclass(frozen=True)
class Relation:
    """Immutable relationship between two entities."""
    
    from_entity: str
    to_entity: str
    relation_type: RelationType
    
    # Optional metadata
    context: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate relation after creation."""
        if not self.from_entity or not self.to_entity:
            raise ValueError("Both from_entity and to_entity must be non-empty")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
    
    
    @property
    def is_bidirectional(self) -> bool:
        """Check if this relation type is naturally bidirectional."""
        bidirectional_types = {
            RelationType.REFERENCES,
            RelationType.USES,
        }
        return self.relation_type in bidirectional_types
    
    def reverse(self) -> 'Relation':
        """Create the reverse relation (if applicable)."""
        if not self.is_bidirectional:
            raise ValueError(f"Relation type {self.relation_type} is not bidirectional")
        
        return Relation(
            from_entity=self.to_entity,
            to_entity=self.from_entity,
            relation_type=self.relation_type,
            context=self.context,
            confidence=self.confidence,
            metadata=self.metadata.copy()
        )


class EntityFactory:
    """Factory for creating entities with consistent patterns."""
    
    @staticmethod
    def create_file_entity(file_path: Path, **metadata) -> Entity:
        """Create a file entity with standard observations."""
        observations = [
            f"File: {file_path.name}",
            f"Path: {file_path}",
            f"Extension: {file_path.suffix}",
        ]
        
        if file_path.stat().st_size:
            observations.append(f"Size: {file_path.stat().st_size} bytes")
        
        return Entity(
            name=str(file_path),
            entity_type=EntityType.FILE,
            observations=observations,
            file_path=file_path,
            metadata=metadata
        )
    
    @staticmethod  
    def create_function_entity(name: str, file_path: Path, line_number: int,
                             signature: str = None, docstring: str = None,
                             **metadata) -> Entity:
        """Create a function entity with standard observations."""
        observations = [
            f"Function: {name}",
            f"Defined in: {file_path}",
            f"Line: {line_number}",
        ]
        
        if signature:
            observations.append(f"Signature: {signature}")
        if docstring:
            observations.append(f"Description: {docstring}")
        
        return Entity(
            name=name,
            entity_type=EntityType.FUNCTION,
            observations=observations,
            file_path=file_path,
            line_number=line_number,
            signature=signature,
            docstring=docstring,
            metadata=metadata
        )
    
    @staticmethod
    def create_class_entity(name: str, file_path: Path, line_number: int,
                          docstring: str = None, base_classes: List[str] = None,
                          **metadata) -> Entity:
        """Create a class entity with standard observations."""
        observations = [
            f"Class: {name}",
            f"Defined in: {file_path}",
            f"Line: {line_number}",
        ]
        
        if base_classes:
            observations.append(f"Inherits from: {', '.join(base_classes)}")
        if docstring:
            observations.append(f"Description: {docstring}")
        
        return Entity(
            name=name,
            entity_type=EntityType.CLASS,
            observations=observations,
            file_path=file_path,
            line_number=line_number,
            docstring=docstring,
            metadata={**metadata, "base_classes": base_classes or []}
        )


class RelationFactory:
    """Factory for creating relations with consistent patterns."""
    
    @staticmethod
    def create_contains_relation(parent: str, child: str, context: str = None) -> Relation:
        """Create a 'contains' relationship."""
        return Relation(
            from_entity=parent,
            to_entity=child,
            relation_type=RelationType.CONTAINS,
            context=context or f"{parent} contains {child}"
        )
    
    @staticmethod
    def create_imports_relation(importer: str, imported: str, 
                              import_type: str = "module") -> Relation:
        """Create an 'imports' relationship."""
        return Relation(
            from_entity=importer,
            to_entity=imported,
            relation_type=RelationType.IMPORTS,
            context=f"Imports {import_type}",
            metadata={"import_type": import_type}
        )
    
    @staticmethod
    def create_calls_relation(caller: str, callee: str, context: str = None) -> Relation:
        """Create a 'calls' relationship."""
        return Relation(
            from_entity=caller,
            to_entity=callee,
            relation_type=RelationType.CALLS,
            context=context or f"{caller} calls {callee}"
        )