"""
Integration tests for file watching functionality.

Tests the real-time file monitoring and automatic re-indexing
when files change in the project.
"""

import asyncio
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

try:
    from claude_indexer.watcher.handler import Watcher
    WATCHER_AVAILABLE = True
except ImportError:
    WATCHER_AVAILABLE = False

from claude_indexer.config import IndexerConfig


@pytest.mark.skipif(not WATCHER_AVAILABLE, reason="Watcher components not available")
@pytest.mark.integration
@pytest.mark.asyncio
class TestWatcherFlow:
    """Test file watching integration."""
    
    async def test_basic_file_watch_flow(self, temp_repo, dummy_embedder, qdrant_store):
        """Test basic file watching and re-indexing."""
        config = IndexerConfig(
            collection_name="test_watcher",
            embedder_type="dummy",
            storage_type="qdrant",
            watch_debounce=0.1  # Short debounce for testing
        )
        
        watcher = Watcher(
            repo_path=temp_repo,
            config=config,
            embedder=dummy_embedder,
            store=qdrant_store
        )
        
        # Start watching
        watch_task = asyncio.create_task(watcher.start())
        
        try:
            # Wait for watcher to initialize
            await asyncio.sleep(0.2)
            
            # Get initial count
            initial_count = qdrant_store.count()
            
            # Modify a file
            modified_file = temp_repo / "foo.py"
            original_content = modified_file.read_text()
            modified_content = original_content + '\n\ndef new_watched_function():\n    """Added by watcher test."""\n    return "watched"\n'
            modified_file.write_text(modified_content)
            
            # Wait for watcher to process the change
            await asyncio.sleep(0.5)
            
            # Check that re-indexing occurred
            final_count = qdrant_store.count()
            assert final_count >= initial_count
            
            # Verify we can find the new function
            search_embedding = dummy_embedder.embed_single("new_watched_function")
            hits = qdrant_store.search(search_embedding, top_k=5)
            
            new_function_found = any(
                "new_watched_function" in hit.payload.get("name", "")
                for hit in hits
            )
            assert new_function_found
            
        finally:
            # Stop watcher
            await watcher.stop()
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
    
    async def test_multiple_file_changes(self, temp_repo, dummy_embedder, qdrant_store):
        """Test watching multiple file changes."""
        config = IndexerConfig(
            collection_name="test_multi_watch",
            embedder_type="dummy",
            storage_type="qdrant",
            watch_debounce=0.1
        )
        
        watcher = Watcher(
            repo_path=temp_repo,
            config=config,
            embedder=dummy_embedder,
            store=qdrant_store
        )
        
        watch_task = asyncio.create_task(watcher.start())
        
        try:
            await asyncio.sleep(0.2)
            
            # Modify multiple files simultaneously
            files_to_modify = [
                temp_repo / "foo.py",
                temp_repo / "bar.py",
                temp_repo / "utils" / "helpers.py"
            ]
            
            for i, file_path in enumerate(files_to_modify):
                content = file_path.read_text()
                content += f'\n\ndef batch_function_{i}():\n    """Batch test function {i}."""\n    return {i}\n'
                file_path.write_text(content)
            
            # Wait for debounced processing
            await asyncio.sleep(0.5)
            
            # Verify all changes were processed
            for i in range(len(files_to_modify)):
                search_embedding = dummy_embedder.embed_single(f"batch_function_{i}")
                hits = qdrant_store.search(search_embedding, top_k=5)
                
                function_found = any(
                    f"batch_function_{i}" in hit.payload.get("name", "")
                    for hit in hits
                )
                assert function_found, f"batch_function_{i} not found in search results"
        
        finally:
            await watcher.stop()
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
    
    async def test_new_file_creation(self, temp_repo, dummy_embedder, qdrant_store):
        """Test watching for new file creation."""
        config = IndexerConfig(
            collection_name="test_new_files",
            embedder_type="dummy",
            storage_type="qdrant",
            watch_debounce=0.1
        )
        
        watcher = Watcher(
            repo_path=temp_repo,
            config=config,
            embedder=dummy_embedder,
            store=qdrant_store
        )
        
        watch_task = asyncio.create_task(watcher.start())
        
        try:
            await asyncio.sleep(0.2)
            
            # Create a new file
            new_file = temp_repo / "new_module.py"
            new_file.write_text('''"""Newly created module."""

def fresh_function():
    """A function in a new file."""
    return "fresh"

class NewClass:
    """A new class."""
    pass
''')
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Verify new file was indexed
            search_embedding = dummy_embedder.embed_single("fresh_function")
            hits = qdrant_store.search(search_embedding, top_k=5)
            
            fresh_function_found = any(
                "fresh_function" in hit.payload.get("name", "")
                for hit in hits
            )
            assert fresh_function_found
            
            # Also check for the new class
            search_embedding = dummy_embedder.embed_single("NewClass")
            hits = qdrant_store.search(search_embedding, top_k=5)
            
            new_class_found = any(
                "NewClass" in hit.payload.get("name", "")
                for hit in hits
            )
            assert new_class_found
        
        finally:
            await watcher.stop()
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
    
    async def test_file_deletion_handling(self, temp_repo, dummy_embedder, qdrant_store):
        """Test watching for file deletion."""
        config = IndexerConfig(
            collection_name="test_deletions",
            embedder_type="dummy",
            storage_type="qdrant",
            watch_debounce=0.1
        )
        
        # First, create and index a file
        temp_file = temp_repo / "temporary.py"
        temp_file.write_text('''"""Temporary module."""

def temp_function():
    """Will be deleted."""
    return "temporary"
''')
        
        watcher = Watcher(
            repo_path=temp_repo,
            config=config,
            embedder=dummy_embedder,
            store=qdrant_store
        )
        
        watch_task = asyncio.create_task(watcher.start())
        
        try:
            await asyncio.sleep(0.3)  # Wait for initial indexing
            
            # Verify the function exists
            search_embedding = dummy_embedder.embed_single("temp_function")
            hits = qdrant_store.search(search_embedding, top_k=5)
            
            temp_function_found = any(
                "temp_function" in hit.payload.get("name", "")
                for hit in hits
            )
            assert temp_function_found, "Temporary function should be indexed initially"
            
            # Delete the file
            temp_file.unlink()
            
            # Wait for deletion processing
            await asyncio.sleep(0.5)
            
            # Verify the function is no longer findable or properly cleaned up
            search_embedding = dummy_embedder.embed_single("temp_function")
            hits = qdrant_store.search(search_embedding, top_k=5)
            
            # After deletion, either no hits for temp_function or hits don't reference the deleted file
            remaining_temp_hits = [
                hit for hit in hits 
                if "temp_function" in hit.payload.get("name", "") 
                and "temporary.py" in hit.payload.get("file_path", "")
            ]
            assert len(remaining_temp_hits) == 0, "Deleted file references should be cleaned up"
        
        finally:
            await watcher.stop()
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
    
    async def test_watcher_error_handling(self, temp_repo, dummy_embedder, qdrant_store):
        """Test watcher handles errors gracefully."""
        config = IndexerConfig(
            collection_name="test_error_handling",
            embedder_type="dummy",
            storage_type="qdrant",
            watch_debounce=0.1
        )
        
        # Mock the embedder to fail sometimes
        failing_embedder = Mock()
        failing_embedder.embed_single.side_effect = Exception("Mock embedding failure")
        
        watcher = Watcher(
            repo_path=temp_repo,
            config=config,
            embedder=failing_embedder,
            store=qdrant_store
        )
        
        watch_task = asyncio.create_task(watcher.start())
        
        try:
            await asyncio.sleep(0.2)
            
            # Modify a file (should trigger error)
            modified_file = temp_repo / "foo.py"
            content = modified_file.read_text()
            modified_file.write_text(content + '\n# Error test comment\n')
            
            # Wait for processing attempt
            await asyncio.sleep(0.5)
            
            # Watcher should still be running despite the error
            assert not watch_task.done(), "Watcher should continue running despite errors"
        
        finally:
            await watcher.stop()
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
    
    async def test_debouncing_behavior(self, temp_repo, dummy_embedder, qdrant_store):
        """Test that rapid file changes are properly debounced."""
        config = IndexerConfig(
            collection_name="test_debounce",
            embedder_type="dummy",
            storage_type="qdrant",
            watch_debounce=0.3  # Longer debounce for testing
        )
        
        # Track indexing calls
        index_calls = []
        original_index = qdrant_store.upsert
        
        def tracking_upsert(*args, **kwargs):
            index_calls.append(time.time())
            return original_index(*args, **kwargs)
        
        qdrant_store.upsert = tracking_upsert
        
        watcher = Watcher(
            repo_path=temp_repo,
            config=config,
            embedder=dummy_embedder,
            store=qdrant_store
        )
        
        watch_task = asyncio.create_task(watcher.start())
        
        try:
            await asyncio.sleep(0.2)
            
            # Make rapid changes to the same file
            test_file = temp_repo / "rapid_changes.py"
            for i in range(5):
                test_file.write_text(f'def rapid_function_{i}(): return {i}\n')
                await asyncio.sleep(0.05)  # Rapid changes within debounce window
            
            # Wait for debounced processing
            await asyncio.sleep(0.5)
            
            # Should have fewer indexing calls than file changes due to debouncing
            assert len(index_calls) < 5, f"Expected debouncing, but got {len(index_calls)} calls for 5 rapid changes"
        
        finally:
            await watcher.stop()
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass


@pytest.mark.integration
@pytest.mark.asyncio
class TestWatcherConfiguration:
    """Test watcher configuration options."""
    
    @pytest.mark.skipif(not WATCHER_AVAILABLE, reason="Watcher components not available")
    async def test_custom_file_patterns(self, temp_repo, dummy_embedder, qdrant_store):
        """Test watcher with custom include/exclude patterns."""
        config = IndexerConfig(
            collection_name="test_patterns",
            embedder_type="dummy",
            storage_type="qdrant",
            include_patterns=["*.py"],
            exclude_patterns=["*test*", "*temp*"],
            watch_debounce=0.1
        )
        
        watcher = Watcher(
            repo_path=temp_repo,
            config=config,
            embedder=dummy_embedder,
            store=qdrant_store
        )
        
        watch_task = asyncio.create_task(watcher.start())
        
        try:
            await asyncio.sleep(0.2)
            
            # Create files that should be ignored
            (temp_repo / "test_ignore.py").write_text("def test_func(): pass")
            (temp_repo / "temp_ignore.py").write_text("def temp_func(): pass")
            
            # Create file that should be indexed
            (temp_repo / "valid.py").write_text("def valid_func(): pass")
            
            await asyncio.sleep(0.5)
            
            # Check that only valid file was indexed
            search_embedding = dummy_embedder.embed_single("valid_func")
            hits = qdrant_store.search(search_embedding, top_k=10)
            
            valid_found = any(
                "valid_func" in hit.payload.get("name", "")
                for hit in hits
            )
            assert valid_found
            
            # Check that ignored files were not indexed
            for ignored_func in ["test_func", "temp_func"]:
                search_embedding = dummy_embedder.embed_single(ignored_func)
                hits = qdrant_store.search(search_embedding, top_k=10)
                
                ignored_found = any(
                    ignored_func in hit.payload.get("name", "")
                    for hit in hits
                )
                assert not ignored_found, f"{ignored_func} should have been ignored"
        
        finally:
            await watcher.stop()
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass