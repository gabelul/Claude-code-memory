#!/usr/bin/env python3
"""
Universal Semantic Indexer for Claude Code Memory
Builds knowledge graphs from Python codebases using Tree-sitter + Jedi
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
import traceback

# Import analysis libraries
import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python
import jedi
import requests

# Import Qdrant and OpenAI for direct automation
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import openai

# Import file watching and service functionality
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import signal
import threading
from threading import Timer

def load_settings() -> Dict[str, Any]:
    """Load configuration from settings.txt file"""
    settings = {}
    settings_file = Path(__file__).parent / "settings.txt"
    
    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            # Convert boolean values
                            if value.lower() in ('true', 'false'):
                                value = value.lower() == 'true'
                            # Convert numeric values
                            elif value.replace('.', '').isdigit():
                                value = float(value) if '.' in value else int(value)
                            
                            settings[key] = value
        except Exception as e:
            print(f"Warning: Failed to load settings.txt: {e}")
    
    # Set defaults for missing values
    defaults = {
        'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
        'qdrant_url': os.environ.get('QDRANT_URL', 'http://localhost:6333'),
        'qdrant_api_key': os.environ.get('QDRANT_API_KEY', 'default-key'),
        'indexer_debug': False,
        'indexer_verbose': True,
        'debounce_seconds': 2.0,
        'include_markdown': True,
        'include_tests': False,
        'max_file_size': 1048576,
    }
    
    for key, default_value in defaults.items():
        if key not in settings:
            settings[key] = default_value
    
    return settings

class UniversalIndexer:
    """Universal semantic indexer for Python codebases"""
    
    def __init__(self, project_path: str, collection_name: str, verbose: bool = False):
        self.project_path = Path(project_path).resolve()
        self.collection_name = collection_name
        self.verbose = verbose
        
        # Load settings
        self.settings = load_settings()
        if self.settings.get('indexer_verbose', True):
            self.verbose = True
        
        # Initialize Tree-sitter
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)
        
        # Initialize Jedi
        self.project = jedi.Project(str(self.project_path))
        
        # Storage for entities and relations
        self.entities = []
        self.relations = []
        
        # Tracking
        self.processed_files = set()
        self.errors = []
        
        # State file for incremental updates
        self.state_file = self.project_path / f".indexer_state_{collection_name}.json"
        self.previous_state = {}
        
        self.log(f"Initialized indexer for {self.project_path} -> {collection_name}")
        self.log(f"Settings loaded: {len(self.settings)} configuration values")

    def log(self, message: str, level: str = "INFO"):
        """Log messages with optional verbosity"""
        if self.verbose or level == "ERROR":
            print(f"[{level}] {message}")

    def get_file_hash(self, file_path: Path) -> str:
        """Get SHA256 hash of file contents for change detection"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            self.log(f"Failed to hash {file_path}: {e}", "ERROR")
            return ""

    def load_state_file(self) -> Dict[str, Any]:
        """Load previous indexing state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.log(f"Loaded state with {len(state.get('files', {}))} previously indexed files")
                    return state
        except Exception as e:
            self.log(f"Failed to load state file: {e}", "ERROR")
        
        return {"files": {}, "entities": {}, "timestamp": time.time()}

    def save_state_file(self, files_state: Dict[str, Dict[str, Any]]) -> bool:
        """Save current indexing state to disk"""
        try:
            state = {
                "files": files_state,
                "entities": {},  # Could store entity mappings for cleanup
                "timestamp": time.time(),
                "collection": self.collection_name
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            self.log(f"Saved state with {len(files_state)} files to {self.state_file}")
            return True
            
        except Exception as e:
            self.log(f"Failed to save state file: {e}", "ERROR")
            return False

    def get_changed_files(self, current_files: List[Path], incremental: bool = False, force: bool = False) -> Tuple[List[Path], List[str]]:
        """Detect which files have changed since last indexing"""
        if not incremental or force:
            return current_files, []  # Process all files in full mode or when forced
        
        self.previous_state = self.load_state_file()
        previous_files = self.previous_state.get("files", {})
        
        changed_files = []
        deleted_files = []
        
        # Check for new and modified files
        for file_path in current_files:
            relative_path = str(file_path.relative_to(self.project_path))
            current_hash = self.get_file_hash(file_path)
            
            if relative_path not in previous_files:
                # New file
                changed_files.append(file_path)
                self.log(f"New file: {relative_path}")
            elif previous_files[relative_path].get("hash") != current_hash:
                # Modified file
                changed_files.append(file_path)
                self.log(f"Modified file: {relative_path}")
        
        # Check for deleted files
        current_relative_paths = {str(f.relative_to(self.project_path)) for f in current_files}
        for prev_file in previous_files:
            if prev_file not in current_relative_paths:
                deleted_files.append(prev_file)
                self.log(f"Deleted file: {prev_file}")
        
        self.log(f"Incremental update: {len(changed_files)} changed, {len(deleted_files)} deleted")
        return changed_files, deleted_files

    def delete_entities_for_files(self, deleted_files: List[str]) -> bool:
        """Delete entities from MCP memory for removed files"""
        if not deleted_files:
            return True
            
        try:
            # For now, we'll just log what would be deleted
            # In a full implementation, this would call MCP delete operations
            entities_to_delete = []
            
            for file_path in deleted_files:
                # Add file entity
                entities_to_delete.append(file_path)
                
                # Add entities that were in this file
                # This would require tracking entity-to-file mappings in state
                self.log(f"Would delete entities for removed file: {file_path}")
            
            self.log(f"Would delete {len(entities_to_delete)} entities for {len(deleted_files)} removed files")
            return True
            
        except Exception as e:
            self.log(f"Error deleting entities for removed files: {e}", "ERROR")
            return False

    def find_source_files(self, include_tests: bool = False) -> List[Path]:
        """Find all source files in the project (Python and optionally Markdown)"""
        source_files = []
        
        # Find Python files
        for file_path in self.project_path.rglob("*.py"):
            # Skip virtual environments and hidden directories
            if any(part.startswith('.') for part in file_path.parts):
                continue
            if 'venv' in str(file_path) or '__pycache__' in str(file_path):
                continue
                
            # Skip test files unless explicitly included
            if not include_tests and ('test_' in file_path.name or '/tests/' in str(file_path)):
                continue
                
            source_files.append(file_path)
        
        # Find Markdown files if enabled
        if self.settings.get('include_markdown', True):
            for file_path in self.project_path.rglob("*.md"):
                # Skip hidden directories
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                if 'venv' in str(file_path) or '__pycache__' in str(file_path):
                    continue
                # Skip node_modules
                if 'node_modules' in str(file_path):
                    continue
                    
                source_files.append(file_path)
        
        python_count = len([f for f in source_files if f.suffix == '.py'])
        markdown_count = len([f for f in source_files if f.suffix == '.md'])
        self.log(f"Found {python_count} Python files and {markdown_count} Markdown files")
        return source_files

    def find_python_files(self, include_tests: bool = False) -> List[Path]:
        """Legacy method - use find_source_files instead"""
        return [f for f in self.find_source_files(include_tests) if f.suffix == '.py']

    def parse_with_tree_sitter(self, file_path: Path) -> Optional[tree_sitter.Tree]:
        """Parse file with Tree-sitter"""
        try:
            with open(file_path, 'rb') as f:
                source_code = f.read()
            
            tree = self.parser.parse(source_code)
            return tree
        except Exception as e:
            self.log(f"Tree-sitter parsing failed for {file_path}: {e}", "ERROR")
            self.errors.append(f"Parse error in {file_path}: {e}")
            return None

    def analyze_with_jedi(self, file_path: Path) -> Dict[str, Any]:
        """Analyze file with Jedi for semantic information"""
        try:
            script = jedi.Script(path=str(file_path), project=self.project)
            
            # Get names (functions, classes, variables)
            names = script.get_names(all_scopes=True, definitions=True)
            
            analysis = {
                'functions': [],
                'classes': [],
                'imports': [],
                'variables': []
            }
            
            for name in names:
                if name.type == 'function':
                    analysis['functions'].append({
                        'name': name.name,
                        'line': name.line,
                        'docstring': name.docstring() if hasattr(name, 'docstring') else None,
                        'full_name': name.full_name
                    })
                elif name.type == 'class':
                    analysis['classes'].append({
                        'name': name.name,
                        'line': name.line,
                        'docstring': name.docstring() if hasattr(name, 'docstring') else None,
                        'full_name': name.full_name
                    })
                elif name.type == 'module':
                    analysis['imports'].append({
                        'name': name.name,
                        'full_name': name.full_name
                    })
            
            return analysis
        except Exception as e:
            self.log(f"Jedi analysis failed for {file_path}: {e}", "ERROR")
            self.errors.append(f"Jedi error in {file_path}: {e}")
            return {'functions': [], 'classes': [], 'imports': [], 'variables': []}

    def extract_tree_sitter_entities(self, tree: tree_sitter.Tree, file_path: Path) -> List[Dict[str, Any]]:
        """Extract entities from Tree-sitter AST"""
        entities = []
        
        def traverse_node(node, depth=0):
            """Recursively traverse AST nodes"""
            if node.type == 'function_definition':
                func_name = None
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = child.text.decode('utf-8')
                        break
                
                if func_name:
                    entities.append({
                        'name': func_name,
                        'type': 'function',
                        'file': str(file_path.relative_to(self.project_path)),
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1,
                        'source': 'tree-sitter'
                    })
            
            elif node.type == 'class_definition':
                class_name = None
                for child in node.children:
                    if child.type == 'identifier':
                        class_name = child.text.decode('utf-8')
                        break
                
                if class_name:
                    entities.append({
                        'name': class_name,
                        'type': 'class',
                        'file': str(file_path.relative_to(self.project_path)),
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1,
                        'source': 'tree-sitter'
                    })
            
            elif node.type == 'import_statement' or node.type == 'import_from_statement':
                import_text = node.text.decode('utf-8').strip()
                entities.append({
                    'name': import_text,
                    'type': 'import',
                    'file': str(file_path.relative_to(self.project_path)),
                    'start_line': node.start_point[0] + 1,
                    'source': 'tree-sitter'
                })
            
            # Recursively process children
            for child in node.children:
                traverse_node(child, depth + 1)
        
        if tree.root_node:
            traverse_node(tree.root_node)
        
        return entities

    def create_mcp_entities(self, file_entities: List[Dict[str, Any]], jedi_analysis: Dict[str, Any], file_path: Path) -> List[Dict[str, Any]]:
        """Create MCP entities from extracted information"""
        mcp_entities = []
        
        # Create file entity
        relative_path = str(file_path.relative_to(self.project_path))
        file_entity = {
            'name': relative_path,
            'entityType': 'file',
            'observations': [
                f"Python source file in {self.collection_name} project",
                f"Located at {relative_path}",
                f"Contains {len([e for e in file_entities if e['type'] == 'function'])} functions",
                f"Contains {len([e for e in file_entities if e['type'] == 'class'])} classes",
                f"Has {len([e for e in file_entities if e['type'] == 'import'])} imports"
            ]
        }
        mcp_entities.append(file_entity)
        
        # Create entities for functions
        for func in file_entities:
            if func['type'] == 'function':
                jedi_func = next((f for f in jedi_analysis['functions'] if f['name'] == func['name']), None)
                observations = [
                    f"Function defined in {relative_path} at line {func['start_line']}",
                    f"Part of {self.collection_name} project"
                ]
                
                if jedi_func and jedi_func.get('docstring'):
                    observations.append(f"Documentation: {jedi_func['docstring'][:200]}...")
                
                if jedi_func and jedi_func.get('full_name'):
                    observations.append(f"Full name: {jedi_func['full_name']}")
                
                mcp_entities.append({
                    'name': f"{relative_path}:{func['name']}",
                    'entityType': 'function',
                    'observations': observations
                })
        
        # Create entities for classes
        for cls in file_entities:
            if cls['type'] == 'class':
                jedi_cls = next((c for c in jedi_analysis['classes'] if c['name'] == cls['name']), None)
                observations = [
                    f"Class defined in {relative_path} at line {cls['start_line']}",
                    f"Part of {self.collection_name} project"
                ]
                
                if jedi_cls and jedi_cls.get('docstring'):
                    observations.append(f"Documentation: {jedi_cls['docstring'][:200]}...")
                
                if jedi_cls and jedi_cls.get('full_name'):
                    observations.append(f"Full name: {jedi_cls['full_name']}")
                
                mcp_entities.append({
                    'name': f"{relative_path}:{cls['name']}",
                    'entityType': 'class',
                    'observations': observations
                })
        
        return mcp_entities

    def create_mcp_relations(self, file_path: Path, file_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create MCP relations between entities"""
        relations = []
        relative_path = str(file_path.relative_to(self.project_path))
        
        # File contains functions and classes
        for entity in file_entities:
            if entity['type'] in ['function', 'class']:
                relations.append({
                    'from': relative_path,
                    'to': f"{relative_path}:{entity['name']}",
                    'relationType': 'contains'
                })
        
        # Could add more sophisticated relations here:
        # - function calls
        # - class inheritance
        # - import dependencies
        
        return relations

    def send_to_mcp(self, entities: List[Dict[str, Any]], relations: List[Dict[str, Any]], use_mcp_api: bool = True) -> bool:
        """Send entities and relations to MCP memory server"""
        try:
            # First, save backup JSON files
            output_dir = self.project_path / 'mcp_output'
            output_dir.mkdir(exist_ok=True)
            
            entities_file = output_dir / f"{self.collection_name}_entities.json"
            with open(entities_file, 'w') as f:
                json.dump(entities, f, indent=2)
            
            relations_file = output_dir / f"{self.collection_name}_relations.json"
            with open(relations_file, 'w') as f:
                json.dump(relations, f, indent=2)
            
            self.log(f"Saved backup files to {output_dir}")
            
            if not use_mcp_api:
                self.log(f"MCP API integration disabled. Only saved JSON files.")
                return True
            
            # Send to MCP memory server via API calls
            success = self._send_entities_to_mcp(entities) and self._send_relations_to_mcp(relations)
            
            if success:
                self.log(f"Successfully sent {len(entities)} entities and {len(relations)} relations to MCP server")
            
            return success
            
        except Exception as e:
            self.log(f"Failed to send MCP data: {e}", "ERROR")
            return False

    def _send_entities_to_mcp(self, entities: List[Dict[str, Any]]) -> bool:
        """Send entities to MCP memory server in batches"""
        try:
            # Process entities in batches to avoid overwhelming the server
            batch_size = 50
            total_batches = (len(entities) + batch_size - 1) // batch_size
            
            for i in range(0, len(entities), batch_size):
                batch = entities[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                self.log(f"Sending entity batch {batch_num}/{total_batches} ({len(batch)} entities)")
                
                # Format for MCP API
                mcp_request = {
                    "entities": batch
                }
                
                # Make API call to MCP server
                if not self._call_mcp_api("create_entities", mcp_request):
                    self.log(f"Failed to send entity batch {batch_num}", "ERROR")
                    return False
            
            return True
            
        except Exception as e:
            self.log(f"Error sending entities to MCP: {e}", "ERROR")
            return False

    def _send_relations_to_mcp(self, relations: List[Dict[str, Any]]) -> bool:
        """Send relations to MCP memory server in batches"""
        try:
            if not relations:
                self.log("No relations to send")
                return True
                
            # Process relations in batches
            batch_size = 50
            total_batches = (len(relations) + batch_size - 1) // batch_size
            
            for i in range(0, len(relations), batch_size):
                batch = relations[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                self.log(f"Sending relation batch {batch_num}/{total_batches} ({len(batch)} relations)")
                
                # Format for MCP API
                mcp_request = {
                    "relations": batch
                }
                
                # Make API call to MCP server
                if not self._call_mcp_api("create_relations", mcp_request):
                    self.log(f"Failed to send relation batch {batch_num}", "ERROR")
                    return False
            
            return True
            
        except Exception as e:
            self.log(f"Error sending relations to MCP: {e}", "ERROR")
            return False

    def _call_mcp_api(self, method: str, params: Dict[str, Any]) -> bool:
        """Execute direct Qdrant operations for true automation"""
        try:
            self.log(f"Direct Qdrant call: {method} with {len(params.get('entities', params.get('relations', [])))} items")
            
            # Use settings for configuration
            qdrant_url = self.settings.get('qdrant_url', 'http://localhost:6333')
            qdrant_api_key = self.settings.get('qdrant_api_key', 'default-key')
            openai_api_key = self.settings.get('openai_api_key', '')
            
            if not openai_api_key:
                self.log("OpenAI API key not configured in settings.txt", "ERROR")
                return False
            
            # Initialize Qdrant client
            client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            
            # Initialize OpenAI client for embeddings
            openai_client = openai.OpenAI(api_key=openai_api_key)
            
            # Ensure collection exists
            collection_name = self.collection_name
            try:
                client.get_collection(collection_name)
                self.log(f"Using existing collection: {collection_name}")
            except Exception:
                # Create collection if it doesn't exist
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
                )
                self.log(f"Created new collection: {collection_name}")
            
            if method == "create_entities":
                return self._create_entities_direct(client, openai_client, collection_name, params["entities"])
            elif method == "create_relations":
                return self._create_relations_direct(client, openai_client, collection_name, params["relations"])
            else:
                self.log(f"Unknown method: {method}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Direct Qdrant call failed: {e}", "ERROR")
            return False

    def _create_entities_direct(self, client: QdrantClient, openai_client, collection_name: str, entities: List[Dict[str, Any]]) -> bool:
        """Create entities directly in Qdrant with embeddings"""
        try:
            points = []
            
            for i, entity in enumerate(entities):
                # Create text for embedding from entity data
                entity_text = f"{entity['name']} ({entity['entityType']}): {' '.join(entity['observations'])}"
                
                # Generate embedding
                response = openai_client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=entity_text
                )
                embedding = response.data[0].embedding
                
                # Create point for Qdrant  
                # Use deterministic hash for stable IDs across runs
                entity_id = int(hashlib.sha256(entity['name'].encode()).hexdigest()[:8], 16)
                point = PointStruct(
                    id=entity_id,  # Deterministic ID based on entity name
                    vector=embedding,
                    payload={
                        "name": entity['name'],
                        "entityType": entity['entityType'],
                        "observations": entity['observations'],
                        "collection": collection_name
                    }
                )
                points.append(point)
            
            # Batch upsert to Qdrant
            client.upsert(collection_name=collection_name, points=points)
            self.log(f"✅ Created {len(entities)} entities in Qdrant")
            return True
            
        except Exception as e:
            self.log(f"Failed to create entities: {e}", "ERROR")
            return False

    def clear_collection(self) -> bool:
        """Clear all data from the collection"""
        try:
            qdrant_url = self.settings.get('qdrant_url', 'http://localhost:6333')
            qdrant_api_key = self.settings.get('qdrant_api_key', 'default-key')
            
            # Initialize Qdrant client
            client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            
            # Check if collection exists
            try:
                client.get_collection(self.collection_name)
                # Delete the collection
                client.delete_collection(self.collection_name)
                self.log(f"✅ Deleted collection: {self.collection_name}")
                
                # Also clear the state file
                if self.state_file.exists():
                    self.state_file.unlink()
                    self.log(f"✅ Cleared state file: {self.state_file}")
                
                return True
                
            except Exception as e:
                if "doesn't exist" in str(e).lower():
                    self.log(f"ℹ️  Collection '{self.collection_name}' doesn't exist - nothing to clear")
                    # Still clear state file if it exists
                    if self.state_file.exists():
                        self.state_file.unlink()
                        self.log(f"✅ Cleared state file: {self.state_file}")
                    return True
                else:
                    raise e
                    
        except Exception as e:
            self.log(f"❌ Failed to clear collection: {e}", "ERROR")
            return False

    def _create_relations_direct(self, client: QdrantClient, openai_client, collection_name: str, relations: List[Dict[str, Any]]) -> bool:
        """Create relations directly in Qdrant as separate points"""
        try:
            points = []
            
            for i, relation in enumerate(relations):
                # Create text for embedding from relation data
                relation_text = f"Relation: {relation['from']} {relation['relationType']} {relation['to']}"
                
                # Generate embedding
                response = openai_client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=relation_text
                )
                embedding = response.data[0].embedding
                
                # Create point for Qdrant
                # Use deterministic hash for stable IDs across runs
                relation_key = f"{relation['from']}-{relation['relationType']}-{relation['to']}"
                relation_id = int(hashlib.sha256(relation_key.encode()).hexdigest()[:8], 16)
                point = PointStruct(
                    id=relation_id,
                    vector=embedding,
                    payload={
                        "from": relation['from'],
                        "to": relation['to'],
                        "relationType": relation['relationType'],
                        "collection": collection_name,
                        "type": "relation"  # Mark as relation for filtering
                    }
                )
                points.append(point)
            
            # Batch upsert to Qdrant
            client.upsert(collection_name=collection_name, points=points)
            self.log(f"✅ Created {len(relations)} relations in Qdrant")
            return True
            
        except Exception as e:
            self.log(f"Failed to create relations: {e}", "ERROR")
            return False

    def process_file(self, file_path: Path, include_tests: bool = False) -> bool:
        """Process a single source file (Python or Markdown)"""
        try:
            self.log(f"Processing {file_path.relative_to(self.project_path)}")
            
            if file_path.suffix == '.py':
                return self.process_python_file(file_path, include_tests)
            elif file_path.suffix == '.md':
                return self.process_markdown_file(file_path)
            else:
                self.log(f"Unsupported file type: {file_path.suffix}", "ERROR")
                return False
            
        except Exception as e:
            self.log(f"Error processing {file_path}: {e}", "ERROR")
            self.errors.append(f"Processing error in {file_path}: {e}")
            traceback.print_exc()
            return False

    def process_python_file(self, file_path: Path, include_tests: bool = False) -> bool:
        """Process a single Python file"""
        try:
            # Parse with Tree-sitter
            tree = self.parse_with_tree_sitter(file_path)
            if not tree:
                return False
            
            # Extract entities from Tree-sitter
            file_entities = self.extract_tree_sitter_entities(tree, file_path)
            
            # Analyze with Jedi
            jedi_analysis = self.analyze_with_jedi(file_path)
            
            # Create MCP entities
            mcp_entities = self.create_mcp_entities(file_entities, jedi_analysis, file_path)
            self.entities.extend(mcp_entities)
            
            # Create MCP relations
            mcp_relations = self.create_mcp_relations(file_path, file_entities)
            self.relations.extend(mcp_relations)
            
            self.processed_files.add(str(file_path))
            return True
            
        except Exception as e:
            self.log(f"Error processing Python file {file_path}: {e}", "ERROR")
            self.errors.append(f"Python processing error in {file_path}: {e}")
            return False

    def process_markdown_file(self, file_path: Path) -> bool:
        """Process a single Markdown file"""
        try:
            # Read markdown content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract markdown entities
            md_entities = self.extract_markdown_entities(content, file_path)
            
            # Create MCP entities for markdown
            mcp_entities = self.create_markdown_mcp_entities(md_entities, file_path)
            self.entities.extend(mcp_entities)
            
            # Create MCP relations for markdown
            mcp_relations = self.create_markdown_mcp_relations(file_path, md_entities)
            self.relations.extend(mcp_relations)
            
            self.processed_files.add(str(file_path))
            return True
            
        except Exception as e:
            self.log(f"Error processing Markdown file {file_path}: {e}", "ERROR")
            self.errors.append(f"Markdown processing error in {file_path}: {e}")
            return False

    def extract_markdown_entities(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract entities from Markdown content"""
        entities = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Extract headers
            if line.startswith('#'):
                header_level = len(line) - len(line.lstrip('#'))
                header_text = line.lstrip('#').strip()
                if header_text:
                    entities.append({
                        'name': header_text,
                        'type': 'header',
                        'level': header_level,
                        'file': str(file_path.relative_to(self.project_path)),
                        'line': line_num,
                        'source': 'markdown'
                    })
            
            # Extract links [text](url)
            import re
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            for match in re.finditer(link_pattern, line):
                link_text, link_url = match.groups()
                entities.append({
                    'name': f"Link: {link_text}",
                    'type': 'link',
                    'url': link_url,
                    'text': link_text,
                    'file': str(file_path.relative_to(self.project_path)),
                    'line': line_num,
                    'source': 'markdown'
                })
            
            # Extract code blocks
            if line.startswith('```'):
                language = line[3:].strip() if len(line) > 3 else 'unknown'
                entities.append({
                    'name': f"Code block ({language})",
                    'type': 'code_block',
                    'language': language,
                    'file': str(file_path.relative_to(self.project_path)),
                    'line': line_num,
                    'source': 'markdown'
                })
        
        return entities

    def create_markdown_mcp_entities(self, md_entities: List[Dict[str, Any]], file_path: Path) -> List[Dict[str, Any]]:
        """Create MCP entities from markdown content"""
        mcp_entities = []
        
        # Create file entity
        relative_path = str(file_path.relative_to(self.project_path))
        
        # Count entity types
        headers = [e for e in md_entities if e['type'] == 'header']
        links = [e for e in md_entities if e['type'] == 'link']
        code_blocks = [e for e in md_entities if e['type'] == 'code_block']
        
        file_entity = {
            'name': relative_path,
            'entityType': 'file',
            'observations': [
                f"Markdown documentation file in {self.collection_name} project",
                f"Located at {relative_path}",
                f"Contains {len(headers)} headers",
                f"Contains {len(links)} links",
                f"Contains {len(code_blocks)} code blocks"
            ]
        }
        mcp_entities.append(file_entity)
        
        # Create entities for headers
        for header in headers:
            observations = [
                f"Level {header['level']} header in {relative_path} at line {header['line']}",
                f"Part of {self.collection_name} project documentation"
            ]
            
            mcp_entities.append({
                'name': f"{relative_path}:{header['name']}",
                'entityType': 'section',
                'observations': observations
            })
        
        # Create entities for significant links (not too many to avoid noise)
        for link in links[:5]:  # Limit to first 5 links per file
            observations = [
                f"Link in {relative_path} at line {link['line']}",
                f"Links to: {link['url']}",
                f"Link text: {link['text']}"
            ]
            
            mcp_entities.append({
                'name': f"{relative_path}:Link:{link['text'][:50]}",
                'entityType': 'reference',
                'observations': observations
            })
        
        return mcp_entities

    def create_markdown_mcp_relations(self, file_path: Path, md_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create MCP relations for markdown content"""
        relations = []
        relative_path = str(file_path.relative_to(self.project_path))
        
        # File contains headers and links
        for entity in md_entities:
            if entity['type'] in ['header', 'link']:
                entity_name = entity['name']
                if entity['type'] == 'link':
                    entity_name = f"Link:{entity['text'][:50]}"
                
                relations.append({
                    'from': relative_path,
                    'to': f"{relative_path}:{entity_name}",
                    'relationType': 'contains'
                })
        
        return relations

    def index_project(self, include_tests: bool = False, incremental: bool = False, force: bool = False, generate_commands: bool = False) -> bool:
        """Index the entire project"""
        mode = "incremental" if incremental else "full"
        self.log(f"Starting {mode} indexing of {self.project_path}")
        
        # Find source files (Python + Markdown)
        all_source_files = self.find_source_files(include_tests)
        
        if not all_source_files:
            self.log("No source files found to index", "ERROR")
            return False
        
        # Determine which files to process
        files_to_process, deleted_files = self.get_changed_files(all_source_files, incremental, force)
        
        if incremental:
            if not files_to_process and not deleted_files:
                self.log("No changes detected - all files up to date")
                return True
            
            # Clean up entities for deleted files
            if deleted_files:
                self.delete_entities_for_files(deleted_files)
        
        # Process files (changed files only in incremental mode)
        successful = 0
        files_state = {}
        
        for file_path in files_to_process:
            if self.process_file(file_path, include_tests):
                successful += 1
                
                # Track file state for next incremental run
                relative_path = str(file_path.relative_to(self.project_path))
                files_state[relative_path] = {
                    "hash": self.get_file_hash(file_path),
                    "timestamp": time.time(),
                    "size": file_path.stat().st_size
                }
        
        # In incremental mode, also preserve state for unchanged files
        if incremental and self.previous_state:
            current_relative_paths = {str(f.relative_to(self.project_path)) for f in all_source_files}
            for prev_file, prev_state in self.previous_state.get("files", {}).items():
                if prev_file in current_relative_paths and prev_file not in files_state:
                    # File unchanged - preserve its state
                    files_state[prev_file] = prev_state
        
        # Save state for next incremental run
        if files_state:
            self.save_state_file(files_state)
        
        self.log(f"Successfully processed {successful}/{len(files_to_process)} files")
        
        if self.errors:
            self.log(f"Encountered {len(self.errors)} errors:")
            for error in self.errors[:5]:  # Show first 5 errors
                self.log(f"  {error}", "ERROR")
        
        # Send to MCP - auto-load by default unless generating commands
        if self.entities or self.relations:
            # Use auto-load mode unless --generate-commands was specified
            auto_load = not generate_commands
            return self.send_to_mcp(self.entities, self.relations, use_mcp_api=auto_load)
        
        return successful > 0 or (incremental and not files_to_process)

    def process_single_file_for_watching(self, file_path: str, collection_name: str) -> bool:
        """Process a single file for file watching (simplified interface)"""
        try:
            # Create a minimal indexer instance for this file
            if self.process_file(Path(file_path)):
                # Send to MCP if we have entities/relations
                if self.entities or self.relations:
                    return self.send_to_mcp(self.entities, self.relations, use_mcp_api=True)
            return False
        except Exception as e:
            self.log(f"Error processing file for watching: {e}", "ERROR")
            return False

    def create_mcp_commands(self) -> str:
        """Generate MCP commands that can be copy-pasted into Claude Code"""
        commands = []
        
        if self.entities:
            # Split entities into batches of 10 for readability
            batch_size = 10
            for i in range(0, len(self.entities), batch_size):
                batch = self.entities[i:i + batch_size]
                entities_json = json.dumps(batch, indent=2)
                commands.append(f"# Entity batch {(i // batch_size) + 1}")
                commands.append(f"mcp__github-utils-memory__create_entities({entities_json})")
                commands.append("")
        
        if self.relations:
            # Split relations into batches of 20 for readability  
            batch_size = 20
            for i in range(0, len(self.relations), batch_size):
                batch = self.relations[i:i + batch_size]
                relations_json = json.dumps(batch, indent=2)
                commands.append(f"# Relation batch {(i // batch_size) + 1}")
                commands.append(f"mcp__github-utils-memory__create_relations({relations_json})")
                commands.append("")
        
        return "\n".join(commands)


class IndexingEventHandler(FileSystemEventHandler):
    """File system event handler for automatic indexing"""
    
    def __init__(self, project_path: str, collection_name: str, debounce_seconds: float = 2.0):
        super().__init__()
        self.project_path = Path(project_path)
        self.collection_name = collection_name
        self.debounce_seconds = debounce_seconds
        self.pending_files = {}
        self.timers = {}
        
    def on_modified(self, event):
        if not event.is_directory and (event.src_path.endswith('.py') or event.src_path.endswith('.md')):
            self._debounced_index(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory and (event.src_path.endswith('.py') or event.src_path.endswith('.md')):
            self._debounced_index(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory and (event.src_path.endswith('.py') or event.src_path.endswith('.md')):
            self._handle_file_deletion(event.src_path)
    
    def _debounced_index(self, file_path):
        """Debounce file changes to avoid duplicate processing"""
        # Cancel existing timer for this file
        if file_path in self.timers:
            self.timers[file_path].cancel()
        
        # Start new timer
        self.timers[file_path] = Timer(
            self.debounce_seconds, 
            self._execute_indexing, 
            args=[file_path]
        )
        self.timers[file_path].start()
    
    def _execute_indexing(self, file_path):
        """Execute incremental indexing for single file"""
        try:
            print(f"🔄 Auto-indexing: {file_path}")
            
            # Create indexer instance for this file
            indexer = UniversalIndexer(
                project_path=str(self.project_path),
                collection_name=self.collection_name,
                verbose=False
            )
            
            # Process single file
            if indexer.process_file(Path(file_path)):
                # Send to MCP if we have entities/relations
                if indexer.entities or indexer.relations:
                    success = indexer.send_to_mcp(indexer.entities, indexer.relations, use_mcp_api=True)
                    if success:
                        print(f"✅ Auto-indexed: {Path(file_path).name}")
                    else:
                        print(f"❌ Auto-indexing failed: {Path(file_path).name}")
                
        except Exception as e:
            print(f"❌ Auto-indexing error for {file_path}: {e}")
        finally:
            # Cleanup timer reference
            if file_path in self.timers:
                del self.timers[file_path]
    
    def _handle_file_deletion(self, file_path):
        """Handle file deletion from knowledge graph"""
        try:
            print(f"🗑️ File deleted: {Path(file_path).name}")
            # TODO: Implement entity cleanup for deleted files
        except Exception as e:
            print(f"❌ Cleanup failed for {file_path}: {e}")


class IndexingService:
    """Background service for continuous file watching across multiple projects"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or str(Path.home() / '.claude-indexer' / 'config.json')
        self.observers = {}
        self.running = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def load_config(self) -> Dict[str, Any]:
        """Load service configuration from file"""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(config_path) as f:
                    return json.load(f)
            else:
                # Create default config
                default_config = {
                    "projects": [],
                    "settings": {
                        "debounce_seconds": 2.0,
                        "watch_patterns": ["*.py"],
                        "ignore_patterns": ["*.pyc", "__pycache__", ".git", ".venv", "node_modules"]
                    }
                }
                
                # Ensure config directory exists
                config_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                
                print(f"📝 Created default config at {config_path}")
                return default_config
                
        except Exception as e:
            print(f"❌ Failed to load config: {e}")
            return {"projects": [], "settings": {}}
    
    def save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"💾 Saved config to {config_path}")
            
        except Exception as e:
            print(f"❌ Failed to save config: {e}")
    
    def add_project(self, project_path: str, collection_name: str, watch_enabled: bool = True):
        """Add a project to the watch list"""
        config = self.load_config()
        
        # Check if project already exists
        for project in config["projects"]:
            if project["path"] == project_path:
                project["collection"] = collection_name
                project["watch_enabled"] = watch_enabled
                self.save_config(config)
                print(f"✅ Updated project: {project_path}")
                return
        
        # Add new project
        config["projects"].append({
            "path": project_path,
            "collection": collection_name,
            "watch_enabled": watch_enabled
        })
        
        self.save_config(config)
        print(f"✅ Added project: {project_path} -> {collection_name}")
    
    def start_project_watching(self, project_path: str, collection_name: str) -> Optional[Observer]:
        """Start watching a single project"""
        try:
            if not Path(project_path).exists():
                print(f"❌ Project path does not exist: {project_path}")
                return None
            
            event_handler = IndexingEventHandler(
                project_path=project_path,
                collection_name=collection_name,
                debounce_seconds=2.0
            )
            
            observer = Observer()
            observer.schedule(event_handler, project_path, recursive=True)
            observer.start()
            
            print(f"👁️  Started watching: {project_path} -> {collection_name}")
            return observer
            
        except Exception as e:
            print(f"❌ Failed to start watching {project_path}: {e}")
            return None
    
    def start_service(self):
        """Start the background indexing service"""
        config = self.load_config()
        
        if not config["projects"]:
            print("📝 No projects configured. Use --add-project to add projects to watch.")
            return
        
        print("🚀 Starting Claude Code Indexing Service")
        print("=" * 50)
        
        # Start watchers for enabled projects
        for project in config["projects"]:
            if project.get("watch_enabled", False):
                observer = self.start_project_watching(
                    project["path"], 
                    project["collection"]
                )
                if observer:
                    self.observers[project["path"]] = observer
        
        if not self.observers:
            print("⚠️  No projects enabled for watching")
            return
        
        self.running = True
        print(f"✅ Service started - watching {len(self.observers)} projects")
        print("💡 Press Ctrl+C to stop the service")
        print()
        
        # Keep service running
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()
    
    def stop_service(self):
        """Stop the service gracefully"""
        self.running = False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n🛑 Received signal {signum}, shutting down service...")
        self.running = False
    
    def _shutdown(self):
        """Graceful shutdown of all observers"""
        print("\n🛑 Stopping file watchers...")
        for path, observer in self.observers.items():
            try:
                observer.stop()
                observer.join(timeout=5)
                print(f"✅ Stopped watcher for {path}")
            except Exception as e:
                print(f"⚠️  Error stopping watcher for {path}: {e}")
        
        print("✅ All watchers stopped - service shutdown complete")


class GitHooksManager:
    """Manage git hooks for automatic indexing"""
    
    def __init__(self, project_path: str, collection_name: str):
        self.project_path = Path(project_path)
        self.collection_name = collection_name
        self.git_dir = self.project_path / '.git'
        
    def is_git_repository(self) -> bool:
        """Check if the project is a git repository"""
        return self.git_dir.exists() and self.git_dir.is_dir()
    
    def install_pre_commit_hook(self, indexer_path: str = None) -> bool:
        """Install pre-commit hook for automatic indexing"""
        if not self.is_git_repository():
            print("❌ Not a git repository - cannot install git hooks")
            return False
        
        try:
            hooks_dir = self.git_dir / 'hooks'
            hooks_dir.mkdir(exist_ok=True)
            
            pre_commit_path = hooks_dir / 'pre-commit'
            
            # Determine indexer path
            if not indexer_path:
                # Try to find indexer in PATH or use current script
                indexer_path = 'claude-indexer'
                
            # Create pre-commit hook script
            hook_content = f"""#!/bin/bash
# Claude Code Memory - Pre-commit Hook
# Automatically index changed Python files before commit

echo "🔄 Running Claude Code indexing..."

# Run incremental indexing
{indexer_path} --project "{self.project_path}" --collection "{self.collection_name}" --incremental --quiet

# Check if indexing succeeded
if [ $? -eq 0 ]; then
    echo "✅ Indexing complete"
else
    echo "⚠️  Indexing failed - proceeding with commit"
fi

# Always allow commit to proceed
exit 0
"""
            
            # Write hook file
            with open(pre_commit_path, 'w') as f:
                f.write(hook_content)
            
            # Make executable
            pre_commit_path.chmod(0o755)
            
            print(f"✅ Installed pre-commit hook: {pre_commit_path}")
            print(f"🔄 Will auto-index changed files before each commit")
            return True
            
        except Exception as e:
            print(f"❌ Failed to install pre-commit hook: {e}")
            return False
    
    def uninstall_pre_commit_hook(self) -> bool:
        """Remove the pre-commit hook"""
        if not self.is_git_repository():
            return False
        
        try:
            pre_commit_path = self.git_dir / 'hooks' / 'pre-commit'
            
            if pre_commit_path.exists():
                # Check if it's our hook
                content = pre_commit_path.read_text()
                if 'Claude Code Memory' in content:
                    pre_commit_path.unlink()
                    print(f"✅ Removed pre-commit hook")
                    return True
                else:
                    print("⚠️  Pre-commit hook exists but is not ours - not removing")
                    return False
            else:
                print("ℹ️  No pre-commit hook found")
                return True
                
        except Exception as e:
            print(f"❌ Failed to remove pre-commit hook: {e}")
            return False
    
    def status(self) -> Dict[str, Any]:
        """Get status of git hooks"""
        status = {
            "is_git_repo": self.is_git_repository(),
            "pre_commit_installed": False,
            "pre_commit_ours": False
        }
        
        if status["is_git_repo"]:
            pre_commit_path = self.git_dir / 'hooks' / 'pre-commit'
            if pre_commit_path.exists():
                status["pre_commit_installed"] = True
                try:
                    content = pre_commit_path.read_text()
                    status["pre_commit_ours"] = 'Claude Code Memory' in content
                except:
                    pass
        
        return status


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Universal Semantic Indexer for Claude Code Memory")
    
    # Basic indexing arguments
    parser.add_argument("--project", help="Path to Python project")
    parser.add_argument("--collection", help="MCP collection name")
    parser.add_argument("--include-tests", action="store_true", help="Include test files")
    parser.add_argument("--incremental", action="store_true", help="Only process changed files since last run")
    parser.add_argument("--force", action="store_true", help="Force reprocessing all files (overrides incremental hash checks)")
    parser.add_argument("--clear", action="store_true", help="Clear all data from the collection before indexing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--depth", choices=["basic", "full"], default="full", help="Analysis depth")
    parser.add_argument("--generate-commands", action="store_true", help="Generate MCP commands for manual execution instead of auto-loading")
    
    # File watching arguments
    parser.add_argument("--watch", action="store_true", help="Start file watching for real-time indexing")
    parser.add_argument("--debounce", type=float, default=2.0, help="Debounce delay in seconds for file watching")
    
    # Service management arguments
    parser.add_argument("--service-start", action="store_true", help="Start background indexing service")
    parser.add_argument("--service-stop", action="store_true", help="Stop background indexing service")
    parser.add_argument("--service-add-project", nargs=2, metavar=('PROJECT_PATH', 'COLLECTION'), help="Add project to service watch list")
    parser.add_argument("--service-status", action="store_true", help="Show service status")
    parser.add_argument("--service-config", help="Path to service config file")
    
    # Git hooks arguments
    parser.add_argument("--install-hooks", action="store_true", help="Install git pre-commit hooks")
    parser.add_argument("--uninstall-hooks", action="store_true", help="Uninstall git pre-commit hooks")
    parser.add_argument("--hooks-status", action="store_true", help="Show git hooks status")
    parser.add_argument("--indexer-path", help="Path to indexer executable for git hooks")
    
    args = parser.parse_args()
    
    # Handle service management commands
    if args.service_start or args.service_stop or args.service_add_project or args.service_status:
        service = IndexingService(args.service_config)
        
        if args.service_add_project:
            project_path, collection = args.service_add_project
            service.add_project(project_path, collection)
            return
        
        if args.service_status:
            config = service.load_config()
            print("🔧 Claude Code Indexing Service Status")
            print("=" * 40)
            print(f"📁 Config file: {service.config_file}")
            print(f"📋 Projects configured: {len(config.get('projects', []))}")
            for project in config.get('projects', []):
                status = "✅ enabled" if project.get('watch_enabled', False) else "❌ disabled"
                print(f"  • {project['path']} -> {project['collection']} ({status})")
            return
        
        if args.service_start:
            service.start_service()
            return
        
        if args.service_stop:
            # This would require process management in a real implementation
            print("⚠️  Service stop not implemented - use Ctrl+C to stop running service")
            return
    
    # Handle git hooks commands
    if args.install_hooks or args.uninstall_hooks or args.hooks_status:
        if not args.project or not args.collection:
            print("❌ --project and --collection are required for git hooks operations")
            sys.exit(1)
            
        hooks_manager = GitHooksManager(args.project, args.collection)
        
        if args.hooks_status:
            status = hooks_manager.status()
            print("🔧 Git Hooks Status")
            print("=" * 20)
            print(f"📁 Git repository: {'✅ yes' if status['is_git_repo'] else '❌ no'}")
            if status['is_git_repo']:
                print(f"🪝 Pre-commit hook: {'✅ installed' if status['pre_commit_installed'] else '❌ not installed'}")
                if status['pre_commit_installed']:
                    print(f"🏷️  Our hook: {'✅ yes' if status['pre_commit_ours'] else '❌ no (different hook)'}")
            return
        
        if args.install_hooks:
            hooks_manager.install_pre_commit_hook(args.indexer_path)
            return
        
        if args.uninstall_hooks:
            hooks_manager.uninstall_pre_commit_hook()
            return
    
    # Handle file watching mode
    if args.watch:
        if not args.project or not args.collection:
            print("❌ --project and --collection are required for file watching")
            sys.exit(1)
            
        project_path = Path(args.project).resolve()
        if not project_path.exists():
            print(f"❌ Project path does not exist: {project_path}")
            sys.exit(1)
        
        print(f"👁️  Starting file watching for {project_path} -> {args.collection}")
        print("💡 Press Ctrl+C to stop watching")
        
        event_handler = IndexingEventHandler(
            project_path=str(project_path),
            collection_name=args.collection,
            debounce_seconds=args.debounce
        )
        
        observer = Observer()
        observer.schedule(event_handler, str(project_path), recursive=True)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping file watcher...")
            observer.stop()
        
        observer.join()
        print("✅ File watching stopped")
        return
    
    # Handle basic indexing (default mode)
    if not args.project or not args.collection:
        print("❌ --project and --collection are required for indexing operations")
        parser.print_help()
        sys.exit(1)
    
    # Validate project path
    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"❌ Project path does not exist: {project_path}")
        sys.exit(1)
    
    if not project_path.is_dir():
        print(f"❌ Project path is not a directory: {project_path}")
        sys.exit(1)
    
    # Create and run indexer
    indexer = UniversalIndexer(
        project_path=str(project_path),
        collection_name=args.collection,
        verbose=args.verbose
    )
    
    # Handle clear collection command
    if args.clear:
        print(f"🗑️  Clearing collection '{args.collection}'...")
        clear_success = indexer.clear_collection()
        if clear_success:
            print(f"✅ Successfully cleared collection '{args.collection}'")
        else:
            print(f"❌ Failed to clear collection '{args.collection}'")
            sys.exit(1)
        return
    
    success = indexer.index_project(
        include_tests=args.include_tests,
        incremental=args.incremental,
        force=args.force,
        generate_commands=args.generate_commands
    )
    
    if success:
        print(f"✅ Successfully indexed {args.project} to collection '{args.collection}'")
        print(f"📊 Processed {len(indexer.processed_files)} files")
        print(f"📝 Created {len(indexer.entities)} entities and {len(indexer.relations)} relations")
        if indexer.errors:
            print(f"⚠️  {len(indexer.errors)} errors encountered")
        
        # Generate MCP commands if requested, otherwise auto-load
        if args.generate_commands:
            output_dir = project_path / 'mcp_output'
            output_dir.mkdir(exist_ok=True)
            commands_file = output_dir / f"{args.collection}_mcp_commands.txt"
            with open(commands_file, 'w') as f:
                f.write("# MCP Commands for Claude Code\n")
                f.write(f"# Copy and paste these commands into Claude Code to load the knowledge graph\n")
                f.write(f"# Collection: {args.collection}\n")
                f.write(f"# Project: {args.project}\n\n")
                f.write(indexer.create_mcp_commands())
            
            print(f"📋 Generated MCP commands in {commands_file}")
            print(f"💡 Copy and paste the commands from this file into Claude Code to load the knowledge graph")
        else:
            print(f"🚀 Directly loaded entities and relations into Qdrant vector database")
            print(f"💡 Knowledge graph stored in collection '{args.collection}' with semantic search enabled")
            print(f"🔍 Use semantic search: mcp__${args.collection}-memory__search_similar(\"query\")")
            
    else:
        print(f"❌ Failed to index {args.project}")
        sys.exit(1)

if __name__ == "__main__":
    main()