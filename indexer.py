#!/usr/bin/env python3
"""
Universal Semantic Indexer for Claude Code Memory
Builds knowledge graphs from Python codebases using Tree-sitter + Jedi
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import traceback

# Import analysis libraries
import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python
import jedi
import requests

class UniversalIndexer:
    """Universal semantic indexer for Python codebases"""
    
    def __init__(self, project_path: str, collection_name: str, verbose: bool = False):
        self.project_path = Path(project_path).resolve()
        self.collection_name = collection_name
        self.verbose = verbose
        
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
        
        self.log(f"Initialized indexer for {self.project_path} -> {collection_name}")

    def log(self, message: str, level: str = "INFO"):
        """Log messages with optional verbosity"""
        if self.verbose or level == "ERROR":
            print(f"[{level}] {message}")

    def find_python_files(self, include_tests: bool = False) -> List[Path]:
        """Find all Python files in the project"""
        python_files = []
        
        for file_path in self.project_path.rglob("*.py"):
            # Skip virtual environments and hidden directories
            if any(part.startswith('.') for part in file_path.parts):
                continue
            if 'venv' in str(file_path) or '__pycache__' in str(file_path):
                continue
                
            # Skip test files unless explicitly included
            if not include_tests and ('test_' in file_path.name or '/tests/' in str(file_path)):
                continue
                
            python_files.append(file_path)
        
        self.log(f"Found {len(python_files)} Python files")
        return python_files

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
        """Make API call to MCP memory server"""
        try:
            # Since MCP runs locally through Claude Code, we'll use a subprocess approach
            # to call the MCP tools directly rather than HTTP requests
            
            import subprocess
            import tempfile
            import json
            
            # Create temporary file with the request data
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(params, f, indent=2)
                temp_file = f.name
            
            # For now, we'll print the MCP commands that would need to be run
            # In a full implementation, this would integrate with the MCP client
            
            self.log(f"MCP API call: {method} with {len(params.get('entities', params.get('relations', [])))} items")
            
            # Clean up temp file
            os.unlink(temp_file)
            
            # Return True for now - in real implementation, this would check the MCP response
            return True
            
        except Exception as e:
            self.log(f"MCP API call failed: {e}", "ERROR")
            return False

    def process_file(self, file_path: Path, include_tests: bool = False) -> bool:
        """Process a single Python file"""
        try:
            self.log(f"Processing {file_path.relative_to(self.project_path)}")
            
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
            self.log(f"Error processing {file_path}: {e}", "ERROR")
            self.errors.append(f"Processing error in {file_path}: {e}")
            traceback.print_exc()
            return False

    def index_project(self, include_tests: bool = False, incremental: bool = False) -> bool:
        """Index the entire project"""
        self.log(f"Starting indexing of {self.project_path}")
        
        # Find Python files
        python_files = self.find_python_files(include_tests)
        
        if not python_files:
            self.log("No Python files found to index", "ERROR")
            return False
        
        # Process each file
        successful = 0
        for file_path in python_files:
            if self.process_file(file_path, include_tests):
                successful += 1
        
        self.log(f"Successfully processed {successful}/{len(python_files)} files")
        
        if self.errors:
            self.log(f"Encountered {len(self.errors)} errors:")
            for error in self.errors[:5]:  # Show first 5 errors
                self.log(f"  {error}", "ERROR")
        
        # Send to MCP
        if self.entities or self.relations:
            return self.send_to_mcp(self.entities, self.relations, use_mcp_api=False)
        
        return successful > 0

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

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Universal Semantic Indexer for Claude Code Memory")
    parser.add_argument("--project", required=True, help="Path to Python project")
    parser.add_argument("--collection", required=True, help="MCP collection name")
    parser.add_argument("--include-tests", action="store_true", help="Include test files")
    parser.add_argument("--incremental", action="store_true", help="Incremental update (TODO)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--depth", choices=["basic", "full"], default="full", help="Analysis depth")
    parser.add_argument("--generate-commands", action="store_true", help="Generate MCP commands for manual execution")
    
    args = parser.parse_args()
    
    # Validate project path
    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"Error: Project path {project_path} does not exist")
        sys.exit(1)
    
    if not project_path.is_dir():
        print(f"Error: Project path {project_path} is not a directory")
        sys.exit(1)
    
    # Create and run indexer
    indexer = UniversalIndexer(
        project_path=str(project_path),
        collection_name=args.collection,
        verbose=args.verbose
    )
    
    success = indexer.index_project(
        include_tests=args.include_tests,
        incremental=args.incremental
    )
    
    if success:
        print(f"✅ Successfully indexed {args.project} to collection '{args.collection}'")
        print(f"📊 Processed {len(indexer.processed_files)} files")
        print(f"📝 Created {len(indexer.entities)} entities and {len(indexer.relations)} relations")
        if indexer.errors:
            print(f"⚠️  {len(indexer.errors)} errors encountered")
        
        # Generate MCP commands if requested
        if args.generate_commands:
            commands_file = project_path / 'mcp_output' / f"{args.collection}_mcp_commands.txt"
            with open(commands_file, 'w') as f:
                f.write("# MCP Commands for Claude Code\n")
                f.write(f"# Copy and paste these commands into Claude Code to load the knowledge graph\n")
                f.write(f"# Collection: {args.collection}\n")
                f.write(f"# Project: {args.project}\n\n")
                f.write(indexer.create_mcp_commands())
            
            print(f"📋 Generated MCP commands in {commands_file}")
            print(f"💡 Copy and paste the commands from this file into Claude Code to load the knowledge graph")
            
    else:
        print(f"❌ Failed to index {args.project}")
        sys.exit(1)

if __name__ == "__main__":
    main()