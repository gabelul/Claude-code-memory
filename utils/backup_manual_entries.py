#!/usr/bin/env python3
"""
Generic backup utility to extract manual entries from any Qdrant collection.
Creates a JSON backup of all manual entries before clearing the collection.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Set
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_indexer.storage.qdrant import QdrantStore
from claude_indexer.config import IndexerConfig

def load_config():
    """Load configuration from settings.txt"""
    config_file = Path("settings.txt")
    if not config_file.exists():
        raise FileNotFoundError("settings.txt not found. Please create it with your API keys.")
    
    config_data = {}
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                config_data[key.strip()] = value.strip()
    
    return IndexerConfig(
        qdrant_url=config_data.get('qdrant_url', 'http://localhost:6333'),
        qdrant_api_key=config_data.get('qdrant_api_key'),
        openai_api_key=config_data.get('openai_api_key')
    )

def get_manual_entity_types() -> Set[str]:
    """Define manual entity types based on common patterns."""
    return {
        # Original manual types
        'optimization_pattern', 'milestone', 'solution', 'bug', 'performance-metric',
        'feature-verification', 'task-completion', 'technical-analysis', 'debugging-analysis',
        'project_milestone', 'verification_report', 'system_validation', 'completed_optimization',
        'performance_improvement', 'refactoring_project', 'design_patterns', 'architecture_pattern',
        'verification_plan', 'checklist', 'verification_result', 'technical_pattern',
        'solution_pattern', 'test', 'analysis-report', 'code-pattern', 'code-analysis',
        'infrastructure-analysis', 'critical-bug', 'debugging-report', 'bug-reproduction',
        'bug-analysis', 'workflow_pattern', 'configuration_pattern', 'best_practice',
        'implementation_note', 'decision_record', 'learning', 'insight',
        
        # GitHub-utils specific manual types (from memory search analysis)
        'code_analysis', 'debugging_solution', 'project_architecture', 'reference', 
        'research_summary', 'section',
        
        # Additional documentation and content types
        'documentation', 'manual_test', 'user_note', 'comment', 'annotation',
        'summary', 'guide', 'tutorial', 'example', 'template', 'specification',
        'requirement', 'design_document', 'meeting_notes', 'decision', 'changelog',
        'release_notes', 'troubleshooting', 'faq', 'howto', 'tips', 'tricks'
    }

def get_code_entity_types() -> Set[str]:
    """Define code-indexed entity types to exclude."""
    return {'file', 'function', 'class', 'variable', 'import', 'directory', 'project'}

def is_truly_manual_entry(payload: Dict[str, Any]) -> bool:
    """
    Strict detection for truly manual entries based on memory patterns.
    Manual entries have ONLY basic fields: name, entityType, observations.
    Auto entries have file_path field OR relation structure (from/to/relationType).
    """
    # PRIMARY PATTERN FROM MEMORY: Manual entries lack both automation patterns
    
    # Pattern 1: Auto entities have file_path field
    if 'file_path' in payload:
        return False
    
    # Pattern 2: Auto relations have from/to/relationType structure  
    if all(field in payload for field in ['from', 'to', 'relationType']):
        return False
    
    # Pattern 3: Auto entities have extended metadata fields
    automation_fields = {
        'line_number', 'ast_data', 'signature', 'docstring', 'full_name', 
        'ast_type', 'start_line', 'end_line', 'source_hash', 'parsed_at',
        'collection'  # Auto-indexed entries have collection field
    }
    if any(field in payload for field in automation_fields):
        return False
    
    # True manual entries have minimal fields: name, entityType, observations
    # And were created through MCP tools, not automated indexing
    required_manual_fields = {'name', 'entityType'}
    if not all(field in payload for field in required_manual_fields):
        return False
    
    # Additional check: Manual entries typically have meaningful observations
    observations = payload.get('observations', [])
    if not observations or not isinstance(observations, list) or len(observations) == 0:
        return False
    
    return True

def backup_manual_entries(collection_name: str, output_file: str = None):
    """Extract manual entries from any Qdrant collection and save to backup file."""
    
    print(f"🔍 Backing up manual entries from '{collection_name}' collection...")
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize Qdrant store
        store = QdrantStore(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key
        )
        
        # Get all points from collection
        print(f"📥 Retrieving all points from {collection_name}...")
        all_points = []
        
        # Use scroll to get all points
        scroll_result = store.client.scroll(
            collection_name=collection_name,
            limit=1000,  # Get in batches
            with_payload=True,
            with_vectors=False  # We don't need vectors for backup
        )
        
        points, next_page_offset = scroll_result
        all_points.extend(points)
        
        # Continue scrolling if there are more points
        while next_page_offset:
            scroll_result = store.client.scroll(
                collection_name=collection_name,
                limit=1000,
                offset=next_page_offset,
                with_payload=True,
                with_vectors=False
            )
            points, next_page_offset = scroll_result
            all_points.extend(points)
        
        print(f"📊 Found {len(all_points)} total points")
        
        # Get entity type definitions
        manual_entity_types = get_manual_entity_types()
        code_types = get_code_entity_types()
        
        # Filter manual entries with improved classification
        manual_entries = []
        code_entries = []
        relation_entries = []  # Track relations separately
        unknown_entries = []
        
        for point in all_points:
            payload = point.payload or {}
            entity_type = payload.get('entityType', 'unknown')
            point_type = payload.get('type', 'entity')  # Check if it's entity or relation
            
            # Check if this is a relation (not an entity)
            if point_type == 'relation' or ('from' in payload and 'to' in payload and 'relationType' in payload):
                relation_entries.append({
                    'id': str(point.id),
                    'type': 'relation',
                    'from': payload.get('from', 'unknown'),
                    'to': payload.get('to', 'unknown'),
                    'relationType': payload.get('relationType', 'unknown')
                })
            # Check if it's a manual entity type AND truly manual (strict check)
            elif entity_type in manual_entity_types and is_truly_manual_entry(payload):
                manual_entries.append({
                    'id': str(point.id),
                    'payload': payload
                })
            # Check if it's an automated code entity type
            elif entity_type in code_types:
                code_entries.append({
                    'id': str(point.id),
                    'entityType': entity_type,
                    'name': payload.get('name', 'unknown')
                })
            # Use strict detection for truly manual entries
            elif is_truly_manual_entry(payload):
                manual_entries.append({
                    'id': str(point.id),
                    'payload': payload
                })
            else:
                unknown_entries.append({
                    'id': str(point.id),
                    'entityType': entity_type,
                    'name': payload.get('name', 'unknown'),
                    'type': point_type
                })
        
        # Print statistics
        print(f"📝 Manual entries: {len(manual_entries)}")
        print(f"🤖 Code entries: {len(code_entries)}")
        print(f"🔗 Relation entries: {len(relation_entries)}")
        print(f"❓ Unknown entries: {len(unknown_entries)}")
        
        if unknown_entries:
            unknown_types = set(e['entityType'] for e in unknown_entries)
            print(f"❓ Unknown entity types found: {sorted(unknown_types)}")
        
        # Create backup data
        backup_data = {
            "collection_name": collection_name,
            "backup_timestamp": datetime.now().isoformat(),
            "total_points": len(all_points),
            "manual_entries_count": len(manual_entries),
            "code_entries_count": len(code_entries),
            "relation_entries_count": len(relation_entries),
            "unknown_entries_count": len(unknown_entries),
            "manual_entity_types": sorted(list(manual_entity_types)),
            "code_entity_types": sorted(list(code_types)),
            "manual_entries": manual_entries,
            "relation_entries": relation_entries,  # Include relations for completeness
            "unknown_entries": unknown_entries  # Include for review
        }
        
        # Save to file
        if not output_file:
            output_file = f"manual_entries_backup_{collection_name}.json"
        
        backup_file = Path(output_file)
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Manual entries backup saved to: {backup_file}")
        print(f"💾 Backup contains {len(manual_entries)} manual entries")
        
        # Create summary report
        summary_file = Path(f"backup_summary_{collection_name}.txt")
        with open(summary_file, 'w') as f:
            f.write(f"Backup Summary for {collection_name}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Backup timestamp: {backup_data['backup_timestamp']}\n")
            f.write(f"Total points in collection: {len(all_points)}\n")
            f.write(f"Manual entries backed up: {len(manual_entries)}\n")
            f.write(f"Code entries (not backed up): {len(code_entries)}\n")
            f.write(f"Relation entries (identified): {len(relation_entries)}\n")
            f.write(f"Unknown entries (included for review): {len(unknown_entries)}\n\n")
            
            if manual_entries:
                f.write("Manual Entry Types Found:\n")
                manual_types = set(e['payload'].get('entityType') for e in manual_entries)
                for et in sorted(manual_types):
                    count = sum(1 for e in manual_entries if e['payload'].get('entityType') == et)
                    f.write(f"  - {et}: {count} entries\n")
            
            if unknown_entries:
                f.write(f"\nUnknown Entry Types (review needed):\n")
                unknown_types = set(e['entityType'] for e in unknown_entries)
                for et in sorted(unknown_types):
                    count = sum(1 for e in unknown_entries if e['entityType'] == et)
                    f.write(f"  - {et}: {count} entries\n")
        
        print(f"📋 Summary report saved to: {summary_file}")
        
        return backup_file, len(manual_entries)
        
    except Exception as e:
        print(f"❌ Error during backup: {e}")
        raise

def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Generic backup utility for manual entries from any Qdrant collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backup_manual_entries.py -c github-utils
  python backup_manual_entries.py -c memory-project -o my_backup.json
  python backup_manual_entries.py --list-types
        """
    )
    
    parser.add_argument("--collection", "-c", required=True,
                       help="Collection name to backup")
    parser.add_argument("--output", "-o", 
                       help="Output file name (default: manual_entries_backup_{collection}.json)")
    parser.add_argument("--list-types", action="store_true",
                       help="List manual and code entity types and exit")
    
    args = parser.parse_args()
    
    if args.list_types:
        manual_types = get_manual_entity_types()
        code_types = get_code_entity_types()
        
        print("📝 Manual Entity Types (will be backed up):")
        for et in sorted(manual_types):
            print(f"  - {et}")
        
        print(f"\n🤖 Code Entity Types (will be excluded):")
        for et in sorted(code_types):
            print(f"  - {et}")
        
        return
    
    try:
        backup_file, count = backup_manual_entries(args.collection, args.output)
        print(f"\n🎉 Backup complete! {count} manual entries saved to {backup_file}")
    except Exception as e:
        print(f"\n❌ Backup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()