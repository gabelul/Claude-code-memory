"""
Integration tests for the complete indexing workflow.

Tests the interaction between parser, embedder, and storage components
during the full indexing process.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from claude_indexer.indexer import CoreIndexer
from claude_indexer.config import IndexerConfig
from claude_indexer.analysis.entities import Entity, Relation


@pytest.mark.integration
class TestIndexerFlow:
    """Test complete indexing workflows."""
    
    def test_full_index_flow_with_real_files(self, temp_repo, dummy_embedder, qdrant_store):
        """Test complete indexing flow with real Python files."""
        # Create indexer with test components
        config = IndexerConfig(
            openai_api_key="test-key",
            qdrant_api_key="test-key",
            qdrant_url="http://localhost:6333"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Index the temporary repository
        result = indexer.index_project("test_integration")
        
        # Verify indexing succeeded
        assert result.success is True
        assert result.entities_created >= 3  # At least foo.py, bar.py, helpers.py
        assert result.relations_created >= 1  # At least one import relation
        
        # Verify vectors were stored
        count = qdrant_store.count("test_integration")
        assert count >= 3, f"Expected at least 3 vectors, got {count}"
        
        # Verify we can search for content
        search_embedding = dummy_embedder.embed_single("add function")
        hits = qdrant_store.search("test_integration", search_embedding, top_k=5)
        
        assert len(hits) > 0
        # Should find the add function from foo.py
        add_function_found = any(
            "add" in hit.payload.get("name", "").lower() 
            for hit in hits
        )
        assert add_function_found
    
    def test_incremental_indexing_flow(self, temp_repo, dummy_embedder, qdrant_store):
        """Test incremental indexing with file changes."""
        config = IndexerConfig(
            openai_api_key="test-key",
            qdrant_api_key="test-key",
            qdrant_url="http://localhost:6333"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Initial index
        result1 = indexer.index_project("test_incremental")
        initial_count = qdrant_store.count("test_incremental")
        
        # Modify a file
        modified_file = temp_repo / "foo.py"
        original_content = modified_file.read_text()
        modified_content = original_content + '\n\ndef subtract(x, y):\n    """Subtract two numbers."""\n    return x - y\n'
        modified_file.write_text(modified_content)
        
        # Second index (should auto-detect incremental mode)
        result2 = indexer.index_project("test_incremental")
        final_count = qdrant_store.count("test_incremental")
        
        # Verify incremental indexing worked
        assert result2.success is True
        assert final_count >= initial_count  # Should have same or more vectors
        
        # Verify we can find the new function
        search_embedding = dummy_embedder.embed_single("subtract function")
        hits = qdrant_store.search("test_incremental", search_embedding, top_k=5)
        
        subtract_found = any(
            "subtract" in hit.payload.get("name", "").lower()
            for hit in hits
        )
        assert subtract_found
    
    def test_error_handling_in_flow(self, temp_repo, dummy_embedder, qdrant_store):
        """Test error handling during indexing flow."""
        config = IndexerConfig(
            collection_name="test_errors",
            embedder_type="dummy", 
            storage_type="qdrant"
        )
        
        # Create a file with syntax errors
        bad_file = temp_repo / "bad_syntax.py"
        bad_file.write_text("def broken(\n    return 'invalid syntax'")
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Indexing should still succeed for valid files
        result = indexer.index_project("test_errors")
        
        # Should be successful overall despite individual file errors
        assert result.success is True
        assert result.entities_created >= 2  # Valid files still processed
        assert len(result.errors) >= 1  # Should track parsing errors
    
    def test_empty_project_indexing(self, empty_repo, dummy_embedder, qdrant_store):
        """Test indexing an empty project."""
        config = IndexerConfig(
            collection_name="test_empty",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=empty_repo
        )
        
        result = indexer.index_project("test_empty")
        
        # Should succeed with no entities
        assert result.success is True
        assert result.entities_created == 0
        assert result.relations_created == 0
        assert qdrant_store.count("test_empty") == 0
    
    def test_large_file_batching(self, tmp_path, dummy_embedder, qdrant_store):
        """Test indexing with many files to verify batching."""
        config = IndexerConfig(
            collection_name="test_batching",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        # Create many small Python files
        for i in range(20):
            py_file = tmp_path / f"module_{i}.py"
            py_file.write_text(f'''"""Module {i}."""

def function_{i}():
    """Function number {i}."""
    return {i}

CLASS_{i} = "constant_{i}"
''')
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=tmp_path
        )
        
        result = indexer.index_project("test_batching")
        
        # Should successfully process all files
        assert result.success is True
        assert result.entities_created >= 40  # At least 2 entities per file
        assert qdrant_store.count("test_batching") >= 40
    
    def test_duplicate_entity_handling(self, tmp_path, dummy_embedder, qdrant_store):
        """Test handling of duplicate entities across files."""
        config = IndexerConfig(
            collection_name="test_duplicates",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        # Create files with same function names
        file1 = tmp_path / "module1.py"
        file1.write_text('''
def common_function():
    """First implementation."""
    return 1
''')
        
        file2 = tmp_path / "module2.py"
        file2.write_text('''
def common_function():
    """Second implementation.""" 
    return 2
''')
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=tmp_path
        )
        
        result = indexer.index_project("test_duplicates")
        
        # Should handle duplicates gracefully
        assert result.success is True
        
        # Search should find both implementations
        search_embedding = dummy_embedder.embed_single("common_function")
        hits = qdrant_store.search("test_duplicates", search_embedding, top_k=10)
        
        # Should find function in both files
        file_paths = {hit.payload.get("file_path", "") for hit in hits}
        assert "module1.py" in str(file_paths)
        assert "module2.py" in str(file_paths)


@pytest.mark.integration
class TestIndexerConfiguration:
    """Test indexer configuration and initialization."""
    
    def test_indexer_with_different_embedders(self, temp_repo, qdrant_store):
        """Test indexer with different embedder configurations."""
        # Test with dummy embedder
        config = IndexerConfig(
            collection_name="test_embedders",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        with patch('claude_indexer.embeddings.registry.create_embedder_from_config') as mock_create:
            mock_embedder = Mock()
            mock_embedder.embed_single.return_value = np.random.rand(1536).astype(np.float32)
            mock_create.return_value = mock_embedder
            
            indexer = CoreIndexer(
                config=config,
                embedder=mock_embedder,
                vector_store=qdrant_store,
                project_path=temp_repo
            )
            
            result = indexer.index_project("test_embedders")
            assert result.success is True
            
            # Verify embedder was used
            assert mock_embedder.embed_single.called
    
    def test_indexer_with_custom_filters(self, temp_repo, dummy_embedder, qdrant_store):
        """Test indexer with custom file filters."""
        config = IndexerConfig(
            collection_name="test_filters",
            embedder_type="dummy",
            storage_type="qdrant",
            include_patterns=["*.py"],
            exclude_patterns=["test_*"]
        )
        
        # Add test files that should be excluded
        test_dir = temp_repo / "tests"
        test_dir.mkdir(exist_ok=True)
        (test_dir / "test_example.py").write_text("def test_something(): pass")
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        result = indexer.index_project("test_filters")
        
        # Should exclude test files
        assert result.success is True
        
        # Verify test files were not indexed
        search_embedding = dummy_embedder.embed_single("test_something")
        hits = qdrant_store.search("test_filters", search_embedding, top_k=10)
        
        test_files_found = any(
            "test_" in hit.payload.get("file_path", "")
            for hit in hits
        )
        assert not test_files_found


@pytest.mark.integration 
class TestIndexerPerformance:
    """Test indexer performance characteristics."""
    
    def test_indexing_performance_tracking(self, temp_repo, dummy_embedder, qdrant_store):
        """Test that indexing tracks performance metrics."""
        config = IndexerConfig(
            collection_name="test_performance",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        result = indexer.index_project("test_performance")
        
        # Should track timing information
        assert result.success is True
        assert hasattr(result, 'duration')
        assert result.duration >= 0
        
        # Should have file-level statistics
        assert result.files_processed >= 3
        assert result.entities_created >= 3
    
    def test_memory_efficient_processing(self, tmp_path, dummy_embedder, qdrant_store):
        """Test that large projects don't consume excessive memory."""
        config = IndexerConfig(
            collection_name="test_memory",
            embedder_type="dummy",
            storage_type="qdrant"
        )
        
        # Create larger files to test memory usage
        for i in range(5):
            large_file = tmp_path / f"large_{i}.py"
            content = f'"""Large module {i}."""\n\n'
            
            # Add many functions to create a larger file
            for j in range(50):
                content += f'''
def function_{i}_{j}(param_{j}):
    """Function {i}-{j} with parameter."""
    result = "processing_{i}_{j}"
    return result
'''
            large_file.write_text(content)
        
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=tmp_path
        )
        
        # Should process without memory issues
        result = indexer.index_project("test_memory")
        
        assert result.success is True
        assert result.entities_created >= 250  # 5 files * 50 functions each
        assert qdrant_store.count("test_memory") >= 250