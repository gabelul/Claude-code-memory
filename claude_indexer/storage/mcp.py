"""MCP (Model Context Protocol) storage backend for generating manual commands."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from .base import VectorStore, StorageResult, VectorPoint


class MCPStore(VectorStore):
    """
    MCP storage backend that generates commands for manual execution instead of auto-loading.
    
    This recreates the --generate-commands functionality from the old indexer.py.
    """
    
    def __init__(self, auto_print: bool = False, output_dir: Optional[str] = None, 
                 collection_name: Optional[str] = None, **kwargs):
        """
        Initialize MCP command generator.
        
        Args:
            auto_print: Whether to print commands to console
            output_dir: Directory to save command files (defaults to project/mcp_output)
            collection_name: Collection name for file naming
        """
        self.auto_print = auto_print
        self.output_dir = output_dir
        self.collection_name = collection_name
        self.entities = []
        self.relations = []
        
    def create_collection(self, collection_name: str, vector_size: int, 
                         distance_metric: str = "cosine") -> StorageResult:
        """Create a collection (no-op for MCP, just track name)."""
        self.collection_name = collection_name
        return StorageResult(success=True, operation="create", items_processed=1)
        
    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists (always True for MCP)."""
        return True
        
    def delete_collection(self, collection_name: str) -> StorageResult:
        """Delete collection (clear stored data)."""
        self.entities = []
        self.relations = []
        return StorageResult(success=True, operation="delete", items_processed=1)
        
    def upsert_points(self, collection_name: str, points: List[VectorPoint]) -> StorageResult:
        """Store points for command generation.""" 
        try:
            # Convert VectorPoints to entities format
            entities = []
            for point in points:
                entity = {
                    "name": point.payload.get("name", f"entity_{point.id}"),
                    "entityType": point.payload.get("entityType", "unknown"),
                    "observations": point.payload.get("observations", [])
                }
                # Add other payload data as observations
                for key, value in point.payload.items():
                    if key not in ["name", "entityType", "observations"] and value:
                        entity["observations"].append(f"{key}: {value}")
                entities.append(entity)
            
            self.entities.extend(entities)
            
            # Generate and save commands if we have output directory
            if self.output_dir:
                self._save_commands_to_files()
            
            # Print commands if enabled
            if self.auto_print:
                commands = self._generate_entity_commands(entities)
                print("\n# Generated MCP Entity Commands:")
                print(commands)
            
            return StorageResult(success=True, operation="upsert", items_processed=len(points))
            
        except Exception as e:
            return StorageResult(success=False, operation="upsert", 
                               items_failed=len(points), errors=[str(e)])
    
    def delete_points(self, collection_name: str, point_ids: List[Union[str, int]]) -> StorageResult:
        """Delete points by their IDs (no-op for MCP)."""
        return StorageResult(success=True, operation="delete", items_processed=len(point_ids))
    
    def search_similar(self, collection_name: str, query_vector: List[float],
                      limit: int = 10, score_threshold: float = 0.0,
                      filter_conditions: Dict[str, Any] = None) -> StorageResult:
        """Search is not supported in MCP mode."""
        print("⚠️ Search not available in MCP command generation mode")
        return StorageResult(success=False, operation="search", 
                           errors=["Search not supported in MCP mode"])
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection."""
        return {
            "name": collection_name,
            "mode": "mcp_command_generation",
            "entities_count": len(self.entities),
            "relations_count": len(self.relations),
            "supports_search": False
        }
    
    def list_collections(self) -> List[str]:
        """List all collections (just current one for MCP)."""
        return [self.collection_name] if self.collection_name else []
        
    
    def _generate_entity_commands(self, entities: List[Dict[str, Any]]) -> str:
        """Generate MCP entity creation commands."""
        commands = []
        
        # Split entities into batches for readability
        batch_size = 10
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            entities_json = json.dumps(batch, indent=2)
            commands.append(f"# Entity batch {(i // batch_size) + 1}")
            commands.append(f"mcp__project-memory__create_entities({entities_json})")
            commands.append("")
        
        return "\n".join(commands)
    
    def _generate_relation_commands(self, relations: List[Dict[str, Any]]) -> str:
        """Generate MCP relation creation commands."""
        commands = []
        
        # Split relations into batches for readability  
        batch_size = 20
        for i in range(0, len(relations), batch_size):
            batch = relations[i:i + batch_size]
            relations_json = json.dumps(batch, indent=2)
            commands.append(f"# Relation batch {(i // batch_size) + 1}")
            commands.append(f"mcp__project-memory__create_relations({relations_json})")
            commands.append("")
        
        return "\n".join(commands)
    
    def _save_commands_to_files(self):
        """Save generated commands to files like the old system."""
        if not self.output_dir or not self.collection_name:
            return
            
        try:
            output_path = Path(self.output_dir)
            output_path.mkdir(exist_ok=True)
            
            # Save entity and relation JSON files (backup)
            if self.entities:
                entities_file = output_path / f"{self.collection_name}_entities.json"
                with open(entities_file, 'w') as f:
                    json.dump(self.entities, f, indent=2)
            
            if self.relations:
                relations_file = output_path / f"{self.collection_name}_relations.json"
                with open(relations_file, 'w') as f:
                    json.dump(self.relations, f, indent=2)
            
            # Generate combined MCP commands file
            commands_file = output_path / f"{self.collection_name}_mcp_commands.txt"
            with open(commands_file, 'w') as f:
                f.write("# MCP Commands for Claude Code\n")
                f.write(f"# Copy and paste these commands into Claude Code to load the knowledge graph\n")
                f.write(f"# Collection: {self.collection_name}\n\n")
                
                if self.entities:
                    f.write(self._generate_entity_commands(self.entities))
                    f.write("\n")
                
                if self.relations:
                    f.write(self._generate_relation_commands(self.relations))
            
            print(f"📋 Generated MCP commands in {commands_file}")
            print(f"💡 Copy and paste the commands from this file into Claude Code to load the knowledge graph")
            
        except Exception as e:
            print(f"❌ Failed to save MCP commands: {e}")


# Availability check
MCP_AVAILABLE = True  # Always available since it's just command generation