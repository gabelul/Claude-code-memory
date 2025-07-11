"""Main entry point for the Claude Code indexer."""

import sys
from pathlib import Path
from typing import Optional

from .config import load_config
from .indexer import CoreIndexer
from .embeddings.registry import create_embedder_from_config
from .storage.registry import create_store_from_config
from .indexer_logging import setup_logging


def _create_indexer_components(project_path: str, collection_name: str, quiet: bool = False, 
                              verbose: bool = False, config_file: Optional[str] = None):
    """Create indexer components using shared setup logic.
    
    This function eliminates 30+ lines of duplicated boilerplate code across 3 functions.
    Consolidates config loading, embedder creation, vector store creation with consistent
    error handling and logging.
    
    Args:
        project_path: Path to the project root
        collection_name: Name of the vector collection
        quiet: Suppress non-error output
        verbose: Enable verbose output
        config_file: Optional configuration file path
        
    Returns:
        tuple: (project_path, config, embedder, vector_store, logger) or None if failed
    """
    try:
        # Validate project path first
        project = Path(project_path).resolve()
        if not project.exists():
            print(f"❌ Project path does not exist: {project}")
            return None
        
        # Setup logging with project-specific file logging
        logger = setup_logging(quiet=quiet, verbose=verbose, collection_name=collection_name, project_path=project)
        
        # Load configuration
        if config_file:
            config_path = Path(config_file)
            config = load_config(config_path)
        else:
            # Use project path to load project-specific configuration
            config = load_config(project)
        
        # Create components using direct Qdrant integration
        # Get the appropriate API key based on provider
        provider = config.embedding_provider
        api_key = getattr(config, f'{provider}_api_key', None)
        model = config.voyage_model if provider == "voyage" else "text-embedding-3-small"
        
        if verbose:
            logger.debug(f"🔧 Config debug: provider='{provider}', model='{model}'")
            logger.debug(f"🔑 API key present: {api_key is not None}")
            logger.debug(f"⚙️  Voyage model: {getattr(config, 'voyage_model', 'NOT_SET')}")
        
        embedder = create_embedder_from_config({
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "enable_caching": True
        })
        
        vector_store = create_store_from_config({
            "backend": "qdrant",
            "url": config.qdrant_url,
            "api_key": config.qdrant_api_key,
            "enable_caching": True
        })
        
        if not quiet and verbose:
            provider_name = provider.title() if provider else "OpenAI"
            logger.debug(f"⚡ Using Qdrant + {provider_name} (direct mode)")
        
        return project, config, embedder, vector_store, logger
        
    except Exception as e:
        if not quiet:
            print(f"❌ Failed to create indexer components: {e}")
        return None


def run_indexing_with_shared_deletion(project_path: str, collection_name: str,
                                    deleted_file_path: str, quiet: bool = False, 
                                    verbose: bool = False, config_file: Optional[str] = None) -> bool:
    """Run deletion handling with shared deletion logic for a single file."""
    try:
        # Create indexer components using shared setup logic
        components = _create_indexer_components(project_path, collection_name, quiet, verbose, config_file)
        if components is None:
            return False
        
        project, config, embedder, vector_store, logger = components
        
        # Create indexer
        indexer = CoreIndexer(config, embedder, vector_store, project)
        
        # Convert absolute path to relative path for state consistency
        deleted_path = Path(deleted_file_path)
        relative_path = str(deleted_path.relative_to(project))
        
        # Load previous statistics for comparison
        from .indexer import format_change
        prev_stats = indexer._load_previous_statistics(collection_name)
        
        # Get database counts BEFORE deletion for accurate change tracking
        try:
            from qdrant_client.http import models
            
            # Access the underlying QdrantStore client (bypass CachingVectorStore wrapper)
            if hasattr(indexer.vector_store, 'backend'):
                qdrant_client = indexer.vector_store.backend.client
            else:
                qdrant_client = indexer.vector_store.client
            
            # Get counts before deletion
            metadata_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="metadata"))])
            implementation_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="implementation"))])
            relation_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="relation"))])
            
            before_metadata_count = qdrant_client.count(collection_name, count_filter=metadata_filter).count
            before_implementation_count = qdrant_client.count(collection_name, count_filter=implementation_filter).count
            before_relation_count = qdrant_client.count(collection_name, count_filter=relation_filter).count
            
        except Exception as e:
            if verbose:
                logger.warning(f"Failed to get database counts before deletion: {e}")
            # Set to 0 if we can't get counts - change tracking will show negative
            before_metadata_count = before_implementation_count = before_relation_count = 0

        # Use consolidated deletion function
        indexer._handle_deleted_files(collection_name, relative_path, verbose)
        
        # Update state file to remove deleted file entry
        indexer._update_state([], collection_name, verbose, full_rebuild=False, deleted_files=[relative_path])
        
        # Show deletion statistics if verbose
        if not quiet and verbose:
            # Get total tracked files from state (after deletion)
            state = indexer._load_state(collection_name)
            total_tracked = len([k for k in state.keys() if not k.startswith('_')])
            
            # Get actual database counts AFTER deletion
            try:
                metadata_count = qdrant_client.count(collection_name, count_filter=metadata_filter).count
                implementation_count = qdrant_client.count(collection_name, count_filter=implementation_filter).count
                relation_count = qdrant_client.count(collection_name, count_filter=relation_filter).count
                
            except Exception as e:
                if verbose:
                    logger.warning(f"Failed to get actual database counts after deletion: {e}")
                # Fall back to before counts (no change will be shown)
                metadata_count = before_metadata_count
                implementation_count = before_implementation_count
                relation_count = before_relation_count
            
            logger.info(f"✅ Deletion completed")
            logger.info(f"   Total Vectored Files:    {format_change(total_tracked, prev_stats.get('total_tracked', 0)):>6}")
            logger.info(f"   Total tracked files:     {format_change(total_tracked, prev_stats.get('total_tracked', 0)):>6}")
            logger.info(f"   📁 File Changes:")
            logger.info(f"      📋 Tracked (State JSON):")
            logger.info(f"         - {relative_path}")
            logger.info(f"      🗄️  Vectored (Database):")
            logger.info(f"         - {relative_path}")
            logger.info(f"   💻 Implementation:      {format_change(implementation_count, prev_stats.get('implementation_chunks_created', before_implementation_count)):>6}")
            logger.info(f"   🔗 Relation:         {format_change(relation_count, prev_stats.get('relations_created', before_relation_count)):>6}")
            logger.info(f"   📋 Metadata:          {format_change(metadata_count, prev_stats.get('entities_created', before_metadata_count)):>6}")
            
            # Save current statistics for next run
            import time
            state = indexer._load_state(collection_name)
            state['_statistics'] = {
                'files_processed': 0,  # Deletion doesn't process files, it removes them
                'total_tracked': total_tracked,
                'entities_created': metadata_count,
                'relations_created': relation_count,
                'implementation_chunks_created': implementation_count,
                'processing_time': 0.0,
                'timestamp': time.time()
            }
            
            # Save updated state
            state_file = indexer._get_state_file(collection_name)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = state_file.with_suffix('.tmp')
            import json
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            temp_file.rename(state_file)
            logger.info("-----------------------------------------")
        
        return True
        
    except Exception as e:
        if not quiet:
            logger.error(f"❌ Error in shared deletion: {e}")
        return False


def run_indexing_with_specific_files(project_path: str, collection_name: str,
                                    file_paths: list, quiet: bool = False, 
                                    verbose: bool = False,
                                    config_file: Optional[str] = None) -> bool:
    """Run indexing with specific file paths, bypassing file discovery.
    
    This function accepts specific files to process, eliminating the expensive
    file discovery step that scans the entire project.
    
    Args:
        project_path: Path to the project root
        collection_name: Name of the vector collection
        file_paths: List of Path objects to process
        quiet: Suppress non-error output
        verbose: Enable verbose output
        config_file: Optional configuration file path
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create indexer components using shared setup logic
        components = _create_indexer_components(project_path, collection_name, quiet, verbose, config_file)
        if components is None:
            return False
        
        project, config, embedder, vector_store, logger = components
        
        # Create indexer
        indexer = CoreIndexer(config, embedder, vector_store, project)
        
        # Convert file_paths to Path objects if needed
        paths_to_process = []
        for fp in file_paths:
            if isinstance(fp, str):
                paths_to_process.append(Path(fp))
            else:
                paths_to_process.append(fp)
        
        if not quiet and verbose:
            if not paths_to_process:
                logger.info("✅ No files to process, but proceeding to ensure collection and update statistics.")
            else:
                logger.info(f"🔄 Processing {len(paths_to_process)} specific files")
            logger.info(f"📦 Collection: {collection_name}")
        
        # Capture vectored files state BEFORE any processing for accurate comparison
        before_vectored_files = None
        state_file = indexer._get_state_file(collection_name)
        if state_file.exists():
            before_vectored_files = indexer._get_vectored_files(collection_name)
        
        # Clean up existing entities for each file BEFORE processing (prevents duplicates)
        # This ensures modified files get same cleanup treatment as deleted files
        for file_path in paths_to_process:
            try:
                relative_path = str(file_path.relative_to(project))
                if verbose:
                    logger.debug(f"🧹 Cleaning existing entities for: {relative_path}")
                indexer._handle_deleted_files(collection_name, relative_path, verbose)
            except Exception as e:
                if verbose:
                    logger.warning(f"⚠️ Failed to clean existing entities for {file_path}: {e}")
        
        # Process files directly using batch processing
        entities, relations, implementation_chunks, errors = indexer._process_file_batch(paths_to_process, collection_name, verbose)
        
        # Handle any processing errors
        if errors:
            if not quiet:
                logger.error(f"❌ Processing errors occurred:")
                for error in errors:
                    logger.error(f"   {error}")
        
        # Store vectors if we have entities or relations
        storage_success = True
        if entities or relations or implementation_chunks:
            storage_success = indexer._store_vectors(collection_name, entities, relations, implementation_chunks)
            if not storage_success:
                if not quiet:
                    logger.error("❌ Failed to store vectors in Qdrant")
                return False
        
        # Update state file with successfully processed files
        successfully_processed = [f for f in paths_to_process if str(f) not in errors]
        
        # Get file changes before updating state (for display purposes)
        file_changes_for_display = None
        vectored_changes_for_display = None
        incremental = False
        if successfully_processed:
            # Auto-detect incremental mode for state management
            state_file = indexer._get_state_file(collection_name)
            incremental = state_file.exists()
            
            # Get changes before state update for accurate display
            if incremental:
                file_changes_for_display = indexer._categorize_file_changes(False, collection_name)
                
                # We already captured before_vectored_files at the start
                # No need to capture it again here
                vectored_changes_for_display = None
            
            # Use incremental update to merge with existing state
            indexer._update_state(successfully_processed, collection_name, verbose, 
                                full_rebuild=False, deleted_files=None)
            
            # Clean up orphaned relations after processing
            if incremental and successfully_processed:
                if verbose:
                    logger.info(f"🔍 Cleaning up orphaned relations after processing {len(successfully_processed)} files")
                orphaned_deleted = vector_store._cleanup_orphaned_relations(collection_name, verbose)
                if verbose and orphaned_deleted > 0:
                    logger.info(f"✅ Cleanup complete: {orphaned_deleted} orphaned relations removed")
                elif verbose:
                    logger.info("✅ No orphaned relations found")
                
                # Now get the accurate vectored file changes after all operations
                if 'before_vectored_files' in locals():
                    vectored_changes_for_display = indexer._categorize_vectored_file_changes(
                        collection_name, before_vectored_files, set(successfully_processed)
                    )
                    if verbose:
                        logger.debug(f"DEBUG: Updated vectored_changes_for_display: {vectored_changes_for_display}")
        
        # Report results
        files_processed = len(successfully_processed)
        files_failed = len(errors)
        
        if not quiet:
            if verbose:
                logger.debug(f"DEBUG: successfully_processed={len(successfully_processed) if successfully_processed else 0}")
                logger.debug(f"DEBUG: incremental={incremental}")
                # Load previous statistics for comparison
                from .indexer import format_change
                prev_stats = indexer._load_previous_statistics(collection_name)
                
                # Get total tracked files from state (not just current run)
                state = indexer._load_state(collection_name)
                total_tracked = len([k for k in state.keys() if not k.startswith('_')])
                
                # Get actual database counts using direct Qdrant client  
                try:
                    from qdrant_client.http import models
                    
                    # Direct database count queries (proven to work)
                    metadata_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="metadata"))])
                    implementation_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="implementation"))])
                    relation_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="relation"))])
                    
                    # Access the underlying QdrantStore client (bypass CachingVectorStore wrapper)
                    if hasattr(indexer.vector_store, 'backend'):
                        qdrant_client = indexer.vector_store.backend.client
                    else:
                        qdrant_client = indexer.vector_store.client
                    
                    metadata_count = qdrant_client.count(collection_name, count_filter=metadata_filter).count
                    implementation_count = qdrant_client.count(collection_name, count_filter=implementation_filter).count
                    relation_count = qdrant_client.count(collection_name, count_filter=relation_filter).count
                    
                except Exception as e:
                    # Fallback to current run counts if database query fails
                    if verbose:
                        logger.warning(f"Failed to get actual database counts, using current run counts: {e}")
                    metadata_count = len(entities)
                    implementation_count = len(implementation_chunks)
                    relation_count = len(relations)
                
                logger.info(f"✅ Processing completed")
                logger.info(f"   Total Vectored Files:    {format_change(total_tracked, prev_stats.get('total_tracked', 0)):>6}")
                logger.info(f"   Total tracked files:     {format_change(total_tracked, prev_stats.get('total_tracked', 0)):>6}")
                
                # Show file changes if any
                has_tracked_changes = file_changes_for_display and any(file_changes_for_display)
                has_vectored_changes = vectored_changes_for_display and any(vectored_changes_for_display)
                
                if verbose:
                    logger.debug(f"DEBUG file_changes_for_display: {file_changes_for_display}")
                    logger.debug(f"DEBUG vectored_changes_for_display: {vectored_changes_for_display}")
                    logger.debug(f"DEBUG has_tracked_changes: {has_tracked_changes}")
                    logger.debug(f"DEBUG has_vectored_changes: {has_vectored_changes}")
                
                if has_tracked_changes or has_vectored_changes:
                    logger.info(f"   📁 File Changes:")
                    
                    # Show tracked file changes (from state JSON)
                    if has_tracked_changes:
                        new_files, modified_files, deleted_files = file_changes_for_display
                        if new_files or modified_files or deleted_files:
                            logger.info(f"      📋 Tracked (State JSON):")
                            for file_path in new_files:
                                rel_path = file_path.relative_to(indexer.project_path)
                                logger.info(f"         + {rel_path}")
                            for file_path in modified_files:
                                rel_path = file_path.relative_to(indexer.project_path)
                                logger.info(f"         = {rel_path}")
                            for deleted_file in deleted_files:
                                logger.info(f"         - {deleted_file}")
                    
                    # Show vectored file changes (from database)
                    if has_vectored_changes:
                        new_vectored, modified_vectored, deleted_vectored = vectored_changes_for_display
                        if new_vectored or modified_vectored or deleted_vectored:
                            logger.info(f"      🗄️  Vectored (Database):")
                            for rel_path in new_vectored:
                                logger.info(f"         + {rel_path}")
                            for rel_path in modified_vectored:
                                logger.info(f"         = {rel_path}")
                            for rel_path in deleted_vectored:
                                logger.info(f"         - {rel_path}")
                
                elif successfully_processed and not incremental:
                    # First run - show all processed files as new
                    logger.info(f"   📁 File Changes:")
                    logger.info(f"      📋 Tracked (State JSON):")
                    for file_path in successfully_processed:
                        rel_path = file_path.relative_to(indexer.project_path)
                        logger.info(f"         + {rel_path}")
                    logger.info(f"      🗄️  Vectored (Database):")
                    for file_path in successfully_processed:
                        rel_path = file_path.relative_to(indexer.project_path)
                        logger.info(f"         + {rel_path}")
                logger.info(f"   💻 Implementation:      {format_change(implementation_count, prev_stats.get('implementation_chunks_created', 0)):>6}")
                logger.info(f"   🔗 Relation:         {format_change(relation_count, prev_stats.get('relations_created', 0)):>6}")
                logger.info(f"   📋 Metadata:          {format_change(metadata_count, prev_stats.get('entities_created', 0)):>6}")
                logger.info(f"   Files failed: {files_failed}")
                
                # Save current statistics for next run (including total tracked count)
                from .indexer import IndexingResult
                result = IndexingResult(
                    success=True,
                    operation="manual",
                    files_processed=files_processed,
                    entities_created=len(entities),
                    relations_created=len(relations),
                    implementation_chunks_created=len(implementation_chunks)
                )
                
                # Save with total tracked count and actual database counts for future comparison
                import time
                state = indexer._load_state(collection_name)
                state['_statistics'] = {
                    'files_processed': files_processed,
                    'total_tracked': total_tracked,
                    'entities_created': metadata_count,
                    'relations_created': relation_count,
                    'implementation_chunks_created': implementation_count,
                    'processing_time': 0.0,
                    'timestamp': time.time()
                }
                
                # Save updated state
                state_file = indexer._get_state_file(collection_name)
                state_file.parent.mkdir(parents=True, exist_ok=True)
                temp_file = state_file.with_suffix('.tmp')
                import json
                with open(temp_file, 'w') as f:
                    json.dump(state, f, indent=2)
                temp_file.rename(state_file)
                
                # Show cost information if available
                if hasattr(indexer, '_session_cost_data'):
                    cost_data = indexer._session_cost_data
                    if cost_data.get('tokens', 0) > 0:
                        logger.info(f"   Tokens used: {cost_data['tokens']:,}")
                        logger.info(f"   Estimated cost: ${cost_data['cost']:.4f}")
                        logger.info(f"   API requests: {cost_data['requests']}")
            else:
                logger.info(f"✅ Processed {files_processed} files")
                if files_failed > 0:
                    logger.warning(f"⚠️  {files_failed} files failed")
        
        return storage_success and files_failed == 0
        
    except Exception as e:
        if not quiet:
            logger.error(f"❌ Error: {e}")
        return False


def run_indexing(project_path: str, collection_name: str, 
                quiet: bool = False, verbose: bool = False, 
                include_tests: bool = False,
                config_file: Optional[str] = None) -> bool:
    """Run indexing with the specified parameters.
    
    This function provides a programmatic interface for other modules.
    It discovers files and delegates to run_indexing_with_specific_files.
    """
    
    try:
        # Create indexer components using shared setup logic
        components = _create_indexer_components(project_path, collection_name, quiet, verbose, config_file)
        if components is None:
            return False
        
        project, config, embedder, vector_store, logger = components
        
        # Create indexer for file discovery
        indexer = CoreIndexer(config, embedder, vector_store, project)
        
        # Ensure collection exists before any operations
        logger.debug(f"Attempting to ensure collection '{collection_name}' exists via vector_store.ensure_collection...")
        if not vector_store.ensure_collection(collection_name):
            logger.error(f"❌ Failed to ensure collection '{collection_name}' exists. Aborting indexing.")
            return False
        
        if not quiet and verbose:
            logger.info(f"🔄 Indexing project: {project}")
            logger.info(f"📦 Collection: {collection_name}")
            logger.info(f"⚡ Mode: {'Incremental' if incremental else 'Full'} (auto-detected)")
        
        # Discover files to process
        if incremental:
            files_to_process, deleted_files = indexer._find_changed_files(include_tests, collection_name)
            
            # Handle deleted files first
            if deleted_files:
                # Show deletion statistics if this is a pure deletion operation (no files to process afterward)
                if not files_to_process and not quiet and verbose:
                    # Load previous statistics for comparison
                    from .indexer import format_change
                    prev_stats = indexer._load_previous_statistics(collection_name)
                    
                    # Get database counts BEFORE deletion for accurate change tracking
                    try:
                        from qdrant_client.http import models
                        
                        # Access the underlying QdrantStore client (bypass CachingVectorStore wrapper)
                        if hasattr(indexer.vector_store, 'backend'):
                            qdrant_client = indexer.vector_store.backend.client
                        else:
                            qdrant_client = indexer.vector_store.client
                        
                        # Get counts before deletion
                        metadata_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="metadata"))])
                        implementation_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="implementation"))])
                        relation_filter = models.Filter(must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="relation"))])
                        
                        before_metadata_count = qdrant_client.count(collection_name, count_filter=metadata_filter).count
                        before_implementation_count = qdrant_client.count(collection_name, count_filter=implementation_filter).count
                        before_relation_count = qdrant_client.count(collection_name, count_filter=relation_filter).count
                        
                    except Exception as e:
                        if verbose:
                            logger.warning(f"Failed to get database counts before deletion: {e}")
                        before_metadata_count = before_implementation_count = before_relation_count = 0
                
                indexer._handle_deleted_files(collection_name, deleted_files, verbose)
                
                # Show deletion statistics for pure deletion operations
                if not files_to_process and not quiet and verbose:
                    # Get total tracked files from state (after deletion)
                    state = indexer._load_state(collection_name)
                    total_tracked = len([k for k in state.keys() if not k.startswith('_')])
                    
                    # Get actual database counts AFTER deletion
                    try:
                        metadata_count = qdrant_client.count(collection_name, count_filter=metadata_filter).count
                        implementation_count = qdrant_client.count(collection_name, count_filter=implementation_filter).count
                        relation_count = qdrant_client.count(collection_name, count_filter=relation_filter).count
                        
                    except Exception as e:
                        if verbose:
                            logger.warning(f"Failed to get actual database counts after deletion: {e}")
                        metadata_count = before_metadata_count
                        implementation_count = before_implementation_count
                        relation_count = before_relation_count
                    
                    logger.info(f"✅ Deletion completed")
                    logger.info(f"   Total Vectored Files:    {format_change(total_tracked, prev_stats.get('total_tracked', 0)):>6}")
                    logger.info(f"   Total tracked files:     {format_change(total_tracked, prev_stats.get('total_tracked', 0)):>6}")
                    logger.info(f"   📁 File Changes:")
                    logger.info(f"      📋 Tracked (State JSON):")
                    for deleted_file in deleted_files:
                        logger.info(f"         - {deleted_file}")
                    logger.info(f"      🗄️  Vectored (Database):")
                    for deleted_file in deleted_files:
                        logger.info(f"         - {deleted_file}")
                    logger.info(f"   💻 Implementation:      {format_change(implementation_count, prev_stats.get('implementation_chunks_created', before_implementation_count)):>6}")
                    logger.info(f"   🔗 Relation:         {format_change(relation_count, prev_stats.get('relations_created', before_relation_count)):>6}")
                    logger.info(f"   📋 Metadata:          {format_change(metadata_count, prev_stats.get('entities_created', before_metadata_count)):>6}")
                    
                    # Save current statistics for next run
                    import time
                    state = indexer._load_state(collection_name)
                    state['_statistics'] = {
                        'files_processed': 0,  # Deletion doesn't process files, it removes them
                        'total_tracked': total_tracked,
                        'entities_created': metadata_count,
                        'relations_created': relation_count,
                        'implementation_chunks_created': implementation_count,
                        'processing_time': 0.0,
                        'timestamp': time.time()
                    }
                    
                    # Save updated state
                    state_file = indexer._get_state_file(collection_name)
                    state_file.parent.mkdir(parents=True, exist_ok=True)
                    temp_file = state_file.with_suffix('.tmp')
                    import json
                    with open(temp_file, 'w') as f:
                        json.dump(state, f, indent=2)
                    temp_file.rename(state_file)
                    logger.info("-----------------------------------------")
        else:
            files_to_process = indexer._find_all_files(include_tests)
            deleted_files = []
        
        # Delegate to the specific files function, even if no files to process.
        # This ensures the collection is properly handled and statistics are updated.
        return run_indexing_with_specific_files(
            project_path=project_path,
            collection_name=collection_name,
            file_paths=files_to_process, # This might be empty if only deletions were handled
            quiet=quiet,
            verbose=verbose,
            config_file=config_file
        )
        
    except Exception as e:
        if not quiet:
            logger.error(f"❌ Error: {e}")
        return False


def main():
    """Main entry point using Click CLI."""
    try:
        from .cli import cli
        cli()
    except ImportError:
        # Fallback to basic help if Click is not available - keep prints for CLI fallback
        print("Claude Code Memory Indexer")
        print()
        print("Click not available. Install with: pip install click")
        print("For basic indexing, use the run_indexing function directly.")
        sys.exit(1)


if __name__ == '__main__':
    main()
