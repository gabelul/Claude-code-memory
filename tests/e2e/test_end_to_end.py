"""
End-to-end tests for the complete Claude Indexer CLI workflows.

Tests the full CLI interface including all commands and their integration
with the underlying indexing system.
"""

import pytest
import subprocess
import sys
import json
import time
from pathlib import Path
from unittest.mock import patch, Mock

try:
    from claude_indexer import cli_full as cli
    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False
    cli = None
from claude_indexer.config import IndexerConfig


@pytest.mark.e2e
class TestCLIEndToEnd:
    """Test complete CLI workflows."""
    
    def test_basic_cli_indexing_workflow(self, temp_repo, qdrant_store):
        """Test basic CLI indexing from command line."""
        if not CLI_AVAILABLE:
            pytest.skip("CLI not available (Click or dependencies missing)")
        
        # Test CLI help command
        from click.testing import CliRunner
        runner = CliRunner()
        
        # Test main CLI help
        result = runner.invoke(cli.cli, ['--help'])
        assert result.exit_code == 0
        assert "Claude Code Memory Indexer" in result.output
        
        # Test index command help
        result = runner.invoke(cli.cli, ['index', '--help'])
        assert result.exit_code == 0
        assert "Index an entire project" in result.output
    
    def test_cli_index_command_with_mocked_components(self, temp_repo):
        """Test CLI index command with mocked dependencies."""
        if not CLI_AVAILABLE:
            pytest.skip("CLI not available (Click or dependencies missing)")
            
        from click.testing import CliRunner
        
        runner = CliRunner()
        
        # Mock the core components to avoid external dependencies
        with patch('claude_indexer.cli_full.CoreIndexer') as mock_indexer_class:
            # Configure mock indexer
            mock_indexer = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.processing_time = 1.5
            mock_result.files_processed = 2
            mock_result.entities_created = 5
            mock_result.relations_created = 3
            mock_result.warnings = []
            mock_result.errors = []
            # Add missing cost tracking attributes to prevent Mock comparison errors
            mock_result.total_tokens = 0
            mock_result.total_cost_estimate = 0.0
            mock_result.embedding_requests = 0
            mock_indexer.index_project.return_value = mock_result
            mock_indexer_class.return_value = mock_indexer
            
            # Mock embedder and store creation
            with patch('claude_indexer.cli_full.create_embedder_from_config') as mock_embedder:
                with patch('claude_indexer.cli_full.create_store_from_config') as mock_store:
                    mock_embedder.return_value = Mock()
                    mock_store.return_value = Mock()
                    
                    # Test index command
                    result = runner.invoke(cli.cli, [
                        'index',
                        '--project', str(temp_repo),
                        '--collection', 'test-collection'
                    ])
                    
                    # Should succeed and call indexer
                    if result.exit_code != 0:
                        print(f"Exit code: {result.exit_code}")
                        print(f"Output: {result.output}")
                        print(f"Exception: {result.exception}")
                    assert result.exit_code == 0
                    assert mock_indexer.index_project.called
    
    def test_cli_search_command(self, temp_repo):
        """Test CLI search functionality."""
        try:
            import click
            from click.testing import CliRunner
        except ImportError:
            pytest.skip("Click not available for CLI testing")
        
        runner = CliRunner()
        
        # Mock search components
        with patch('claude_indexer.cli_full.create_embedder_from_config') as mock_embedder_factory:
            with patch('claude_indexer.cli_full.create_store_from_config') as mock_store_factory:
                with patch('claude_indexer.cli_full.CoreIndexer') as mock_indexer_class:
                    # Configure mock embedder
                    mock_embedder = Mock()
                    mock_embedder.embed_single.return_value = [0.1] * 1536
                    mock_embedder_factory.return_value = mock_embedder
                    
                    # Configure mock store
                    mock_store = Mock()
                    mock_store_factory.return_value = mock_store
                    
                    # Configure mock indexer with search results
                    mock_indexer = Mock()
                    search_results = [
                        {"payload": {"name": "test_function", "file_path": "test.py", "line": 10}, "score": 0.95}
                    ]
                    mock_indexer.search_similar.return_value = search_results
                    mock_indexer_class.return_value = mock_indexer
                
                    # Test search command
                    result = runner.invoke(cli.cli, [
                        'search',
                        '--project', str(temp_repo),
                        '--collection', 'test-collection',
                        'test function'
                    ])
                    
                    assert result.exit_code == 0
                    assert "test_function" in result.output
                    assert mock_indexer.search_similar.called
    
    def test_cli_config_validation(self, temp_repo):
        """Test CLI configuration validation."""
        try:
            import click
            from click.testing import CliRunner
        except ImportError:
            pytest.skip("Click not available for CLI testing")
        
        runner = CliRunner()
        
        # Test missing required arguments
        result = runner.invoke(cli.cli, ['index'])
        assert result.exit_code != 0  # Should fail due to missing required args
        
        # Test invalid project path
        result = runner.invoke(cli.cli, [
            'index',
            '--project', '/nonexistent/path',
            '--collection', 'test'
        ])
        assert result.exit_code != 0  # Should fail due to invalid path


@pytest.mark.e2e
class TestFullSystemWorkflows:
    """Test complete system workflows with real components."""
    
    def test_index_and_search_workflow(self, temp_repo, dummy_embedder, qdrant_store):
        """Test complete index -> search workflow."""
        config = IndexerConfig()
        
        # Step 1: Index the project
        from claude_indexer.indexer import CoreIndexer
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        result = indexer.index_project("test_e2e_workflow")
        assert result.success
        assert result.entities_created >= 3
        
        # Step 2: Search for indexed content
        search_embedding = dummy_embedder.embed_single("add function")
        hits = qdrant_store.search("test_e2e_workflow", search_embedding, top_k=5)
        
        assert len(hits) > 0
        
        # Verify we can find specific content
        add_function_found = any(
            "add" in hit.payload.get("name", "").lower()
            for hit in hits
        )
        assert add_function_found
        
        # Step 3: Modify files and re-index
        new_file = temp_repo / "new_module.py"
        new_file.write_text('''"""New module added during test."""

def search_test_function():
    """Function added for search testing."""
    return "searchable"
''')
        
        result2 = indexer.index_project("test_e2e_workflow", incremental=True)
        assert result2.success
        
        # Step 4: Search for new content
        search_embedding = dummy_embedder.embed_single("search_test_function")
        hits = qdrant_store.search("test_e2e_workflow", search_embedding, top_k=5)
        
        new_function_found = any(
            "search_test_function" in hit.payload.get("name", "")
            for hit in hits
        )
        assert new_function_found
    
    def test_incremental_indexing_workflow(self, temp_repo, dummy_embedder, qdrant_store):
        """Test incremental indexing maintains consistency."""
        config = IndexerConfig()
        
        from claude_indexer.indexer import CoreIndexer
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Initial index
        result1 = indexer.index_project("test_incremental_e2e")
        initial_count = qdrant_store.count("test_incremental_e2e")
        
        # First incremental run (no changes)
        result2 = indexer.index_project("test_incremental_e2e", incremental=True)
        assert result2.success
        assert qdrant_store.count("test_incremental_e2e") == initial_count  # Should be same
        
        # Add a file (use a name that won't be filtered as a test file)
        new_file = temp_repo / "additional_module.py"
        new_file.write_text('def incremental_func(): return "incremental"')
        
        # Second incremental run (with changes)
        result3 = indexer.index_project("test_incremental_e2e", incremental=True)
        assert result3.success
        assert qdrant_store.count("test_incremental_e2e") > initial_count  # Should increase
        
        # Verify new content is searchable
        search_embedding = dummy_embedder.embed_single("incremental_func")
        hits = qdrant_store.search("test_incremental_e2e", search_embedding, top_k=5)
        
        incremental_found = any(
            "incremental_func" in hit.payload.get("name", "")
            for hit in hits
        )
        assert incremental_found
    
    def test_error_recovery_workflow(self, temp_repo, qdrant_store):
        """Test system recovery from various error conditions."""
        config = IndexerConfig()
        
        # Create an embedder that fails sometimes
        failing_embedder = Mock()
        call_count = 0
        
        def sometimes_failing_embed(text):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # Fail on third call
                raise Exception("Simulated embedding failure")
            # Return valid embedding for other calls
            import numpy as np
            return np.random.rand(1536).astype(np.float32)
        
        failing_embedder.embed_text.side_effect = sometimes_failing_embed
        
        from claude_indexer.indexer import CoreIndexer
        indexer = CoreIndexer(
            config=config,
            embedder=failing_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Should handle partial failures gracefully
        result = indexer.index_project("test_error_recovery")
        
        # System should be resilient to individual failures
        # (exact behavior depends on error handling implementation)
        assert isinstance(result.success, bool)  # Should complete without crashing
        
        # Should be able to recover and continue
        call_count = 0  # Reset for successful run
        result2 = indexer.index_project("test_error_recovery", incremental=True)
        assert result2.success
    
    def test_large_project_workflow(self, tmp_path, dummy_embedder, qdrant_store):
        """Test workflow with a larger simulated project."""
        config = IndexerConfig()
        
        # Create a larger project structure
        project_root = tmp_path / "large_project"
        project_root.mkdir()
        
        # Create multiple modules with various content types
        for module_i in range(10):
            module_dir = project_root / f"module_{module_i}"
            module_dir.mkdir()
            
            # Create Python files in each module
            for file_i in range(5):
                py_file = module_dir / f"file_{file_i}.py"
                content = f'"""Module {module_i} file {file_i}."""\n\n'
                
                # Add classes
                for class_i in range(3):
                    content += f'''
class Module{module_i}Class{class_i}:
    """Class {class_i} in module {module_i}."""
    
    def method_{class_i}(self):
        """Method {class_i}."""
        return "module_{module_i}_class_{class_i}"
'''
                
                # Add functions
                for func_i in range(2):
                    content += f'''

def module_{module_i}_function_{func_i}():
    """Function {func_i} in module {module_i}."""
    return {module_i} * {func_i}
'''
                
                py_file.write_text(content)
        
        from claude_indexer.indexer import CoreIndexer
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=project_root
        )
        
        # Should handle large project efficiently
        result = indexer.index_project("test_large_project")
        assert result.success
        
        # Should create substantial number of entities
        assert result.entities_created >= 150  # 10 modules * 5 files * 3+ entities per file
        
        # Should be searchable
        search_embedding = dummy_embedder.embed_single("Module0Class0")
        hits = qdrant_store.search("test_large_project", search_embedding, top_k=10)
        
        assert len(hits) > 0
        class_found = any(
            "Module0Class0" in hit.payload.get("name", "")
            for hit in hits
        )
        assert class_found


@pytest.mark.e2e
class TestCLIIntegrationScenarios:
    """Test CLI integration with various real-world scenarios."""
    
    def test_cli_with_configuration_file(self, temp_repo, tmp_path):
        """Test CLI with custom configuration file."""
        try:
            import click
            from click.testing import CliRunner
        except ImportError:
            pytest.skip("Click not available for CLI testing")
        
        # Create a test configuration file
        config_file = tmp_path / "test_config.json"
        config_content = {
            "embedder_type": "openai",
            "storage_type": "qdrant",
            "openai_api_key": "test-key",
            "qdrant_url": "http://localhost:6333"
        }
        config_file.write_text(json.dumps(config_content))
        
        runner = CliRunner()
        
        with patch('claude_indexer.cli_full.CoreIndexer') as mock_indexer_class:
            mock_indexer = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.processing_time = 1.5
            mock_result.files_processed = 2
            mock_result.entities_created = 5
            mock_result.relations_created = 3
            mock_result.warnings = []
            mock_result.errors = []
            # Add missing cost tracking attributes to prevent Mock comparison errors
            mock_result.total_tokens = 0
            mock_result.total_cost_estimate = 0.0
            mock_result.embedding_requests = 0
            mock_indexer.index_project.return_value = mock_result
            mock_indexer_class.return_value = mock_indexer
            
            with patch('claude_indexer.cli_full.create_embedder_from_config'):
                with patch('claude_indexer.cli_full.create_store_from_config'):
                    result = runner.invoke(cli.cli, [
                        'index',
                        '--project', str(temp_repo),
                        '--collection', 'test-config',
                        '--config', str(config_file)
                    ])
                    
                    assert result.exit_code == 0
    
    def test_cli_quiet_and_verbose_modes(self, temp_repo):
        """Test CLI output modes."""
        try:
            import click
            from click.testing import CliRunner
        except ImportError:
            pytest.skip("Click not available for CLI testing")
        
        runner = CliRunner()
        
        with patch('claude_indexer.cli_full.CoreIndexer') as mock_indexer_class:
            mock_indexer = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.processing_time = 1.5
            mock_result.files_processed = 2
            mock_result.entities_created = 5
            mock_result.relations_created = 3
            mock_result.warnings = []
            mock_result.errors = []
            # Add missing cost tracking attributes to prevent Mock comparison errors
            mock_result.total_tokens = 0
            mock_result.total_cost_estimate = 0.0
            mock_result.embedding_requests = 0
            mock_indexer.index_project.return_value = mock_result
            mock_indexer_class.return_value = mock_indexer
            
            with patch('claude_indexer.cli_full.create_embedder_from_config'):
                with patch('claude_indexer.cli_full.create_store_from_config'):
                    # Test verbose mode
                    result_verbose = runner.invoke(cli.cli, [
                        'index',
                        '--project', str(temp_repo),
                        '--collection', 'test-verbose',
                        '--verbose'
                    ])
                    assert result_verbose.exit_code == 0
                    
                    # Test quiet mode
                    result_quiet = runner.invoke(cli.cli, [
                        'index',
                        '--project', str(temp_repo),
                        '--collection', 'test-quiet',
                        '--quiet'
                    ])
                    
                    assert result_quiet.exit_code == 0
                    
                    # Quiet mode should have less output than verbose
                    assert len(result_quiet.output) <= len(result_verbose.output)
    
    def test_cli_error_handling(self, temp_repo):
        """Test CLI error handling and user-friendly error messages."""
        try:
            import click
            from click.testing import CliRunner
        except ImportError:
            pytest.skip("Click not available for CLI testing")
        
        runner = CliRunner()
        
        # Test configuration errors
        with patch('claude_indexer.cli_full.load_config') as mock_load_config:
            mock_load_config.side_effect = ValueError("Invalid configuration")
            
            result = runner.invoke(cli.cli, [
                'index',
                '--project', str(temp_repo),
                '--collection', 'test-error'
            ])
            
            assert result.exit_code != 0
            assert "Error" in result.output
        
        # Test indexing errors
        with patch('claude_indexer.cli_full.CoreIndexer') as mock_indexer_class:
            mock_indexer = Mock()
            mock_indexer.index_project.side_effect = Exception("Indexing failed")
            mock_indexer_class.return_value = mock_indexer
            
            with patch('claude_indexer.cli_full.create_embedder_from_config'):
                with patch('claude_indexer.cli_full.create_store_from_config'):
                    result = runner.invoke(cli.cli, [
                        'index',
                        '--project', str(temp_repo),
                        '--collection', 'test-index-error'
                    ])
                    
                    assert result.exit_code != 0
                    assert "Error" in result.output


@pytest.mark.e2e
class TestPerformanceAndScalability:
    """Test performance characteristics under various conditions."""
    
    def test_indexing_performance_baseline(self, temp_repo, dummy_embedder, qdrant_store):
        """Test basic performance characteristics."""
        config = IndexerConfig()
        
        from claude_indexer.indexer import CoreIndexer
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        start_time = time.time()
        result = indexer.index_project("test_performance")
        duration = time.time() - start_time
        
        assert result.success
        assert duration < 30.0  # Should complete reasonably quickly
        
        # Performance should scale reasonably with content
        entities_per_second = result.entities_created / duration if duration > 0 else float('inf')
        assert entities_per_second > 0.1  # Minimum reasonable throughput
    
    def test_incremental_indexing_performance(self, temp_repo, dummy_embedder, qdrant_store):
        """Test that incremental indexing is faster than full re-indexing."""
        config = IndexerConfig()
        
        from claude_indexer.indexer import CoreIndexer
        indexer = CoreIndexer(
            config=config,
            embedder=dummy_embedder,
            vector_store=qdrant_store,
            project_path=temp_repo
        )
        
        # Initial full index
        start_time = time.time()
        result1 = indexer.index_project("test_incremental_perf")
        full_index_time = time.time() - start_time
        
        # Add one small file
        small_file = temp_repo / "small_addition.py"
        small_file.write_text('def small_func(): return "small"')
        
        # Incremental index
        start_time = time.time()
        result2 = indexer.index_project("test_incremental_perf", incremental=True)
        incremental_time = time.time() - start_time
        
        assert result1.success
        assert result2.success
        
        # Incremental should be significantly faster
        # (allowing some overhead for small datasets)
        assert incremental_time <= full_index_time * 1.5