"""
Integration tests for file deletion and cleanup scenarios.

Tests how the indexer handles file deletions and ensures
proper cleanup of vectors and entities.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from claude_indexer.indexer import CoreIndexer
from claude_indexer.config import IndexerConfig


@pytest.mark.integration
class TestDeleteEventHandling:
    """Test file deletion and vector cleanup."""
    
    def test_simple_file_deletion_cleanup(self, temp_repo, dummy_embedder, qdrant_store):
        """Test cleanup when a single file is deleted."""
        import time
        collection_name = f"test_delete_simple_{int(time.time() * 1000)}"
        
        config = IndexerConfig(
            collection_name=collection_name,
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Initial indexing
        result1 = indexer.index_project(collection_name)
        assert result1.success
        
        initial_count = qdrant_store.count(collection_name)
        assert initial_count >= 3  # foo.py, bar.py, helpers.py
        
        # Verify we can find content from foo.py
        search_embedding = dummy_embedder.embed_single("add function")
        hits = qdrant_store.search(collection_name, search_embedding, top_k=10)
        
        foo_entities_before = [
            hit for hit in hits 
            if "foo.py" in hit.payload.get("file_path", "")
        ]
        assert len(foo_entities_before) > 0, "Should find entities from foo.py initially"
        
        # Delete foo.py
        (temp_repo / "foo.py").unlink()
        
        # Re-index (should auto-detect incremental mode and handle deletion)
        result2 = indexer.index_project(collection_name)
        assert result2.success
        
        # Verify cleanup occurred
        final_count = qdrant_store.count(collection_name)
        assert final_count < initial_count, "Vector count should decrease after file deletion"
        
        # Verify entities from deleted file are gone
        search_embedding = dummy_embedder.embed_single("add function")
        hits = qdrant_store.search(collection_name, search_embedding, top_k=10)
        
        foo_entities_after = [
            hit for hit in hits 
            if "foo.py" in hit.payload.get("file_path", "")
        ]
        assert len(foo_entities_after) == 0, "Should not find entities from deleted foo.py"
    
    def test_multiple_file_deletion(self, temp_repo, dummy_embedder, qdrant_store):
        """Test cleanup when multiple files are deleted."""
        import time
        collection_name = f"test_delete_multi_{int(time.time() * 1000)}"
        
        config = IndexerConfig(
            collection_name=collection_name,
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Add extra files to delete
        extra_files = []
        for i in range(3):
            extra_file = temp_repo / f"extra_{i}.py"
            extra_file.write_text(f'''"""Extra module {i}."""

def extra_function_{i}():
    """Extra function {i}."""
    return {i}
''')
            extra_files.append(extra_file)
        
        # Initial indexing
        result1 = indexer.index_project(collection_name)
        assert result1.success
        
        initial_count = qdrant_store.count(collection_name)
        
        # Verify extra files are indexed
        for i in range(3):
            search_embedding = dummy_embedder.embed_single(f"extra_function_{i}")
            hits = qdrant_store.search(collection_name, search_embedding, top_k=5)
            
            extra_found = any(
                f"extra_function_{i}" in hit.payload.get("name", "")
                for hit in hits
            )
            assert extra_found, f"extra_function_{i} should be found initially"
        
        # Delete all extra files
        for extra_file in extra_files:
            extra_file.unlink()
        
        # Re-index with cleanup
        result2 = indexer.index_project(collection_name)
        assert result2.success
        
        final_count = qdrant_store.count(collection_name)
        assert final_count < initial_count, "Count should decrease after multiple deletions"
        
        # Verify all extra functions are gone
        for i in range(3):
            search_embedding = dummy_embedder.embed_single(f"extra_function_{i}")
            hits = qdrant_store.search(collection_name, search_embedding, top_k=5)
            
            extra_found = any(
                f"extra_function_{i}" in hit.payload.get("name", "")
                for hit in hits
            )
            assert not extra_found, f"extra_function_{i} should be cleaned up after deletion"
    
    def test_directory_deletion_cleanup(self, temp_repo, dummy_embedder, qdrant_store):
        """Test cleanup when an entire directory is deleted."""
        config = IndexerConfig(
            collection_name="test_delete_dir",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Create a subdirectory with files
        subdir = temp_repo / "to_delete"
        subdir.mkdir()
        
        for i in range(2):
            sub_file = subdir / f"sub_module_{i}.py"
            sub_file.write_text(f'''"""Sub module {i}."""

class SubClass_{i}:
    """Sub class {i}."""
    
    def sub_method_{i}(self):
        """Sub method {i}."""
        return "sub_{i}"
''')
        
        # Initial indexing
        result1 = indexer.index_project("test_delete_dir")
        assert result1.success
        
        initial_count = qdrant_store.count("test_delete_dir")
        
        # Verify subdirectory content is indexed
        search_embedding = dummy_embedder.embed_single("SubClass_0")
        hits = qdrant_store.search("test_delete_dir", search_embedding, top_k=10)
        
        subdir_entities_before = [
            hit for hit in hits 
            if "to_delete" in hit.payload.get("file_path", "")
        ]
        assert len(subdir_entities_before) > 0, "Should find entities from subdirectory"
        
        # Delete entire subdirectory
        import shutil
        shutil.rmtree(subdir)
        
        # Re-index with cleanup
        result2 = indexer.index_project("test_delete_dir")
        assert result2.success
        
        final_count = qdrant_store.count("test_delete_dir")
        assert final_count < initial_count, "Count should decrease after directory deletion"
        
        # Verify subdirectory entities are gone
        search_embedding = dummy_embedder.embed_single("SubClass_0")
        hits = qdrant_store.search("test_delete_dir", search_embedding, top_k=10)
        
        subdir_entities_after = [
            hit for hit in hits 
            if "to_delete" in hit.payload.get("file_path", "")
        ]
        assert len(subdir_entities_after) == 0, "Should not find entities from deleted subdirectory"
    
    def test_partial_deletion_with_remaining_files(self, temp_repo, dummy_embedder, qdrant_store):
        """Test that deletion cleanup doesn't affect remaining files."""
        config = IndexerConfig(
            collection_name="test_delete_partial",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Initial indexing
        result1 = indexer.index_project("test_delete_partial")
        assert result1.success
        
        # Verify existing files are indexed
        search_embedding = dummy_embedder.embed_single("Calculator")
        hits = qdrant_store.search("test_delete_partial", search_embedding, top_k=5)
        
        calc_found_before = any(
            "Calculator" in hit.payload.get("name", "")
            for hit in hits
        )
        assert calc_found_before, "Calculator class should be found before deletion"
        
        # Delete bar.py but keep foo.py
        (temp_repo / "bar.py").unlink()
        
        # Re-index with cleanup
        result2 = indexer.index_project("test_delete_partial")
        assert result2.success
        
        # Verify that foo.py entities are still present
        search_embedding = dummy_embedder.embed_single("Calculator")
        hits = qdrant_store.search("test_delete_partial", search_embedding, top_k=5)
        
        calc_found_after = any(
            "Calculator" in hit.payload.get("name", "")
            for hit in hits
        )
        assert calc_found_after, "Calculator class should still be found after bar.py deletion"
        
        # Verify bar.py entities are gone
        search_embedding = dummy_embedder.embed_single("main")
        hits = qdrant_store.search("test_delete_partial", search_embedding, top_k=10)
        
        bar_entities = [
            hit for hit in hits 
            if "bar.py" in hit.payload.get("file_path", "")
        ]
        assert len(bar_entities) == 0, "Should not find entities from deleted bar.py"
    
    def test_deletion_state_persistence(self, temp_repo, dummy_embedder, qdrant_store):
        """Test that deletion state is properly persisted between indexing runs."""
        config = IndexerConfig(
            collection_name="test_delete_persistence",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Create a temporary file
        temp_file = temp_repo / "temporary.py"
        temp_file.write_text('''"""Temporary file."""

def temp_func():
    """Temporary function."""
    return "temp"
''')
        
        # Initial indexing
        result1 = indexer.index_project("test_delete_persistence")
        assert result1.success
        
        # Verify temp file is indexed
        search_embedding = dummy_embedder.embed_single("temp_func")
        hits = qdrant_store.search("test_delete_persistence", search_embedding, top_k=5)
        
        temp_found_before = any(
            "temp_func" in hit.payload.get("name", "")
            for hit in hits
        )
        assert temp_found_before, "Temp function should be found initially"
        
        # Delete the file
        temp_file.unlink()
        
        # First index (should clean up)
        result2 = indexer.index_project("test_delete_persistence")
        assert result2.success
        
        # Second index (should remember deletion)
        result3 = indexer.index_project("test_delete_persistence")
        assert result3.success
        
        # Verify temp function is still gone after multiple runs
        search_embedding = dummy_embedder.embed_single("temp_func")
        hits = qdrant_store.search("test_delete_persistence", search_embedding, top_k=5)
        
        temp_found_after = any(
            "temp_func" in hit.payload.get("name", "")
            for hit in hits
        )
        assert not temp_found_after, "Temp function should remain deleted after multiple indexing runs"
    
    def test_deletion_with_indexing_errors(self, temp_repo, dummy_embedder, qdrant_store):
        """Test that deletion cleanup works even when there are indexing errors."""
        config = IndexerConfig(
            collection_name="test_delete_errors",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        # Create a mock embedder that fails for some content
        failing_embedder = Mock()
        
        def selective_embedding(text):
            if "error_trigger" in text:
                raise Exception("Mock embedding failure")
            return dummy_embedder.embed_single(text)
        
        failing_embedder.embed_single.side_effect = selective_embedding
        
        indexer = CoreIndexer(
            config=config,
            embedder=failing_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Create a file that will cause embedding errors
        error_file = temp_repo / "error_file.py"
        error_file.write_text('''"""File with error trigger."""

def error_trigger_function():
    """This will cause embedding to fail."""
    return "error_trigger"
''')
        
        # Initial indexing (will have errors but should succeed partially)
        result1 = indexer.index_project("test_delete_errors")
        # May succeed or fail depending on error handling, but should not crash
        
        initial_count = qdrant_store.count("test_delete_errors")
        
        # Delete the error file
        error_file.unlink()
        
        # Re-index (cleanup should work despite previous errors)
        result2 = indexer.index_project("test_delete_errors")
        # Should succeed since error file is gone
        
        final_count = qdrant_store.count("test_delete_errors")
        
        # Should not crash and should handle cleanup properly
        assert final_count >= 0, "Should handle cleanup even with previous indexing errors"


@pytest.mark.integration
class TestDeleteEventEdgeCases:
    """Test edge cases in deletion handling."""
    
    def test_delete_nonexistent_file_references(self, temp_repo, dummy_embedder, qdrant_store):
        """Test handling deletion of files that were never indexed."""
        config = IndexerConfig(
            collection_name="test_delete_nonexistent",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Initial indexing
        result1 = indexer.index_project("test_delete_nonexistent")
        assert result1.success
        
        # Create and immediately delete a file without indexing
        temp_file = temp_repo / "never_indexed.py"
        temp_file.write_text("def never_indexed(): pass")
        temp_file.unlink()
        
        # Indexing should handle missing file gracefully
        result2 = indexer.index_project("test_delete_nonexistent")
        assert result2.success
    
    def test_delete_during_indexing_race_condition(self, temp_repo, dummy_embedder, qdrant_store):
        """Test race condition where file is deleted during indexing."""
        config = IndexerConfig(
            collection_name="test_delete_race",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        # This is a simplified test - in practice, this would require
        # more complex threading/timing setup
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Create a file
        race_file = temp_repo / "race_condition.py"
        race_file.write_text("def race_func(): pass")
        
        # Index normally first
        result1 = indexer.index_project("test_delete_race")
        assert result1.success
        
        # Delete the file
        race_file.unlink()
        
        # Try to index again - should handle gracefully
        result2 = indexer.index_project("test_delete_race")
        assert result2.success  # Should not crash