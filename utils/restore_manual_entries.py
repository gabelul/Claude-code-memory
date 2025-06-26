#!/usr/bin/env python3
"""
Generic restore utility to reload manual entries from backup files.
Supports any collection and backup file format created by backup_manual_entries.py.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

def restore_manual_entries(backup_file: str, collection_name: str = None, batch_size: int = 10, dry_run: bool = False):
    """Restore manual entries from backup file to specified collection."""
    
    backup_path = Path(backup_file)
    
    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_path}")
        print("Please ensure the backup file exists")
        return False
    
    # Load the backup data
    try:
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading backup file: {e}")
        return False
    
    # Extract collection info and manual entries
    original_collection = backup_data.get("collection_name", "unknown")
    target_collection = collection_name or original_collection
    manual_entries = backup_data.get("manual_entries", [])
    backup_timestamp = backup_data.get("backup_timestamp", "unknown")
    
    if not manual_entries:
        print(f"📭 No manual entries found in backup file")
        print(f"Backup contained {backup_data.get('total_points', 0)} total points with {backup_data.get('manual_entries_count', 0)} manual entries")
        return True
    
    print(f"🔍 Restoring from backup: {backup_path}")
    print(f"📅 Backup timestamp: {backup_timestamp}")
    print(f"📦 Original collection: {original_collection}")
    print(f"🎯 Target collection: {target_collection}")
    print(f"📋 Found {len(manual_entries)} manual entries to restore")
    
    if dry_run:
        print(f"\n🔍 DRY RUN MODE - No actual restoration will occur")
    
    # Format entities for MCP restoration
    entities_for_mcp = []
    for entry in manual_entries:
        payload = entry.get("payload", {})
        mcp_entity = {
            "name": payload.get("name", f"restored_entry_{entry.get('id', 'unknown')}"),
            "entityType": payload.get("entityType", "unknown"),
            "observations": payload.get("observations", [])
        }
        entities_for_mcp.append(mcp_entity)
    
    if dry_run:
        print(f"\n📋 Would restore {len(entities_for_mcp)} entities:")
        entity_types = {}
        for entity in entities_for_mcp:
            et = entity["entityType"]
            entity_types[et] = entity_types.get(et, 0) + 1
        
        for et, count in sorted(entity_types.items()):
            print(f"  - {et}: {count} entries")
        return True
    
    # Generate the MCP commands
    print(f"\n🔧 Use these MCP commands to restore your manual entries:")
    print(f"Collection: {target_collection}")
    
    # Determine MCP server name based on collection
    if "memory-project" in target_collection or target_collection == "memory-project":
        mcp_server = "mcp__memory-project-memory__create_entities"
    elif "general" in target_collection:
        mcp_server = "mcp__general-memory__create_entities"
    elif "github-utils" in target_collection:
        mcp_server = "mcp__github-utils-memory__create_entities"
    else:
        # Default to project memory or suggest manual configuration
        mcp_server = f"mcp__{target_collection}-memory__create_entities"
        print(f"⚠️  Unknown collection pattern. You may need to adjust the MCP server name.")
    
    print(f"MCP Server: {mcp_server}")
    print("Parameters:")
    
    # Split into batches to avoid overwhelming the API
    total_batches = (len(entities_for_mcp) + batch_size - 1) // batch_size
    
    for i in range(0, len(entities_for_mcp), batch_size):
        batch = entities_for_mcp[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"\n📦 Batch {batch_num}/{total_batches} ({len(batch)} entities):")
        print(json.dumps({"entities": batch}, indent=2))
        
        if batch_num < total_batches:
            print(f"\n⏳ After running batch {batch_num}, continue with batch {batch_num + 1}...")
    
    print(f"\n✅ All {len(manual_entries)} manual entries ready for restoration")
    print("Run the MCP commands above to restore your manual memories")
    
    # Create restoration summary
    summary_file = Path(f"restore_summary_{target_collection}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(summary_file, 'w') as f:
        f.write(f"Restoration Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Backup file: {backup_path}\n")
        f.write(f"Backup timestamp: {backup_timestamp}\n")
        f.write(f"Target collection: {target_collection}\n")
        f.write(f"Restoration timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Entries to restore: {len(manual_entries)}\n")
        f.write(f"Batch size: {batch_size}\n")
        f.write(f"Total batches: {total_batches}\n\n")
        
        entity_types = {}
        for entity in entities_for_mcp:
            et = entity["entityType"]
            entity_types[et] = entity_types.get(et, 0) + 1
        
        f.write("Entity Types to Restore:\n")
        for et, count in sorted(entity_types.items()):
            f.write(f"  - {et}: {count} entries\n")
    
    print(f"📋 Restoration summary saved to: {summary_file}")
    return True

def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Generic restore utility for manual entries from backup files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python restore_manual_entries.py -f manual_entries_backup_github-utils.json
  python restore_manual_entries.py -f backup.json -c memory-project
  python restore_manual_entries.py -f backup.json --dry-run
  python restore_manual_entries.py -f backup.json --batch-size 5
        """
    )
    
    parser.add_argument("--file", "-f", required=True,
                       help="Path to backup file (JSON format)")
    parser.add_argument("--collection", "-c",
                       help="Target collection name (default: use original collection from backup)")
    parser.add_argument("--batch-size", type=int, default=10,
                       help="Number of entities per batch (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be restored without actually generating commands")
    
    args = parser.parse_args()
    
    try:
        success = restore_manual_entries(
            backup_file=args.file,
            collection_name=args.collection,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        
        if success:
            if args.dry_run:
                print(f"\n🔍 Dry run complete - use without --dry-run to generate restoration commands")
            else:
                print(f"\n🎉 Restoration commands generated successfully!")
        else:
            print(f"\n❌ Restoration failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Restoration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()