"""Main entry point for the Claude Code indexer."""

import sys
from pathlib import Path
from typing import Optional

from .config import load_config
from .indexer import CoreIndexer
from .embeddings.registry import create_embedder_from_config
from .storage.registry import create_store_from_config
from .logging import setup_logging


def run_indexing_with_shared_deletion(project_path: str, collection_name: str,
                                    deleted_file_path: str, quiet: bool = False, 
                                    verbose: bool = False, config_file: Optional[str] = None) -> bool:
    """Run deletion handling with shared deletion logic for a single file."""
    try:
        # Setup logging with collection-specific file logging
        logger = setup_logging(quiet=quiet, verbose=verbose, collection_name=collection_name)
        
        # Load configuration
        config_path = Path(config_file) if config_file else None
        config = load_config(config_path)
        
        # Validate project path
        project = Path(project_path).resolve()
        if not project.exists():
            if not quiet:
                print(f"❌ Project path does not exist: {project}")
            return False
        
        # Create components using direct Qdrant integration
        embedder = create_embedder_from_config({
            "provider": "openai",
            "api_key": config.openai_api_key,
            "model": "text-embedding-3-small",
            "enable_caching": True
        })
        
        vector_store = create_store_from_config({
            "backend": "qdrant",
            "url": config.qdrant_url,
            "api_key": config.qdrant_api_key,
            "enable_caching": True
        })
        
        # Create indexer
        indexer = CoreIndexer(config, embedder, vector_store, project)
        
        # Convert absolute path to relative path for state consistency
        deleted_path = Path(deleted_file_path)
        relative_path = str(deleted_path.relative_to(project))
        
        # Use consolidated deletion function
        indexer._handle_deleted_files(collection_name, relative_path, verbose)
        
        return True
        
    except Exception as e:
        if not quiet:
            print(f"❌ Error in shared deletion: {e}")
        return False


def run_indexing(project_path: str, collection_name: str, 
                quiet: bool = False, verbose: bool = False, 
                include_tests: bool = False,
                config_file: Optional[str] = None) -> bool:
    """Run indexing with the specified parameters.
    
    This function provides a programmatic interface for other modules.
    """
    
    try:
        # Setup logging with collection-specific file logging
        logger = setup_logging(quiet=quiet, verbose=verbose, collection_name=collection_name)
        
        # Load configuration
        config_path = Path(config_file) if config_file else None
        config = load_config(config_path)
        
        # Validate project path
        project = Path(project_path).resolve()
        if not project.exists():
            if not quiet:
                print(f"❌ Project path does not exist: {project}")
            return False
        
        # Create components using direct Qdrant integration
        embedder = create_embedder_from_config({
            "provider": "openai",
            "api_key": config.openai_api_key,
            "model": "text-embedding-3-small",
            "enable_caching": True
        })
        
        vector_store = create_store_from_config({
            "backend": "qdrant",
            "url": config.qdrant_url,
            "api_key": config.qdrant_api_key,
            "enable_caching": True
        })
        
        if not quiet:
            print("⚡ Using Qdrant + OpenAI (direct mode)")
        
        # Create indexer
        indexer = CoreIndexer(config, embedder, vector_store, project)
        
        # Auto-detect incremental mode and run indexing
        state_file = indexer._get_state_file(collection_name)
        incremental = state_file.exists()
        
        if not quiet and verbose:
            print(f"🔄 Indexing project: {project}")
            print(f"📦 Collection: {collection_name}")
            print(f"⚡ Mode: {'Incremental' if incremental else 'Full'} (auto-detected)")
        
        result = indexer.index_project(
            collection_name=collection_name,
            include_tests=include_tests
        )
        
        # Report results
        if result.success:
            if not quiet:
                if verbose:
                    print(f"✅ Indexing completed in {result.processing_time:.1f}s")
                    print(f"   Files processed: {result.files_processed}")
                    print(f"   Entities created: {result.entities_created}")
                    print(f"   Relations created: {result.relations_created}")
                else:
                    print(f"✅ Indexed {result.files_processed} files")
        else:
            if not quiet:
                print("❌ Indexing failed")
                for error in result.errors:
                    print(f"   {error}")
            return False
        
        return True
        
    except Exception as e:
        if not quiet:
            print(f"❌ Error: {e}")
        return False


def main():
    """Main entry point using Click CLI."""
    try:
        from .cli import cli
        cli()
    except ImportError:
        # Fallback to basic help if Click is not available
        print("Claude Code Memory Indexer")
        print()
        print("Click not available. Install with: pip install click")
        print("For basic indexing, use the run_indexing function directly.")
        sys.exit(1)


if __name__ == '__main__':
    main()