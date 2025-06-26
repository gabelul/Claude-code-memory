"""Main entry point for the Claude Code indexer."""

import sys
from pathlib import Path
from typing import Optional

from .config import load_config
from .indexer import CoreIndexer
from .embeddings.registry import create_embedder_from_config
from .storage.registry import create_store_from_config
from .logging import setup_logging


def run_indexing(project_path: str, collection_name: str, 
                incremental: bool = False, quiet: bool = False, 
                verbose: bool = False, include_tests: bool = False,
                config_file: Optional[str] = None) -> bool:
    """Run indexing with the specified parameters.
    
    This function provides a programmatic interface for other modules.
    """
    
    try:
        # Setup logging
        logger = setup_logging(quiet=quiet, verbose=verbose)
        
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
        
        # Run indexing
        if not quiet and verbose:
            print(f"🔄 Indexing project: {project}")
            print(f"📦 Collection: {collection_name}")
            print(f"⚡ Mode: {'Incremental' if incremental else 'Full'}")
        
        result = indexer.index_project(
            collection_name=collection_name,
            include_tests=include_tests,
            incremental=incremental
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