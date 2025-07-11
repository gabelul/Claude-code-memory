"""Processing context for content processing operations."""

from typing import Set
from dataclasses import dataclass


@dataclass
class ProcessingContext:
    """Context object for content processing operations."""
    
    collection_name: str
    changed_entity_ids: Set[str]
    implementation_entity_names: Set[str]
    
    def __post_init__(self):
        """Ensure sets are initialized."""
        if self.changed_entity_ids is None:
            self.changed_entity_ids = set()
        if self.implementation_entity_names is None:
            self.implementation_entity_names = set()
    
    def entity_has_implementation(self, entity_name: str) -> bool:
        """Check if entity has implementation chunks."""
        return entity_name in self.implementation_entity_names
    
    def entity_changed(self, entity_name: str) -> bool:
        """Check if entity was changed in this indexing run."""
        return entity_name in self.changed_entity_ids