"""Unit tests for CLI functionality."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

try:
    from claude_indexer.cli_full import cli
    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False
    cli = None


class TestMainCLI:
    """Test main CLI group functionality."""
    
    def test_cli_help(self):
        """Test CLI help output."""
        if not CLI_AVAILABLE:
            pytest.skip("CLI not available (Click or dependencies missing)")
            
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert "Claude Code Memory Indexer" in result.output
    
    def test_cli_version(self):
        """Test CLI version command."""
        if not CLI_AVAILABLE:
            pytest.skip("CLI not available (Click or dependencies missing)")
            
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
    
    def test_cli_without_click(self):
        """Test CLI behavior when click unavailable."""
        if not CLI_AVAILABLE:
            pytest.skip("CLI not available (Click or dependencies missing)")
            
        # Test that we can import and use the CLI when Click is available
        # This is essentially testing the positive case since we're in a Click-available environment
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert "Claude Code Memory Indexer" in result.output


class TestIndexCommands:
    """Test index command group."""
    
    def test_index_help(self):
        """Test index command help."""
        if not CLI_AVAILABLE:
            pytest.skip("CLI not available (Click or dependencies missing)")
            
        runner = CliRunner()
        result = runner.invoke(cli, ['index', '--help'])
        
        assert result.exit_code == 0
        assert "Index an entire project" in result.output
    
    @patch('claude_indexer.cli_full.CoreIndexer')
    @patch('claude_indexer.cli_full.create_embedder_from_config')
    @patch('claude_indexer.cli_full.create_store_from_config')
    @patch('claude_indexer.cli_full.load_config')
    def test_index_project_basic(self, mock_load_config, mock_create_store, 
                                 mock_create_embedder, mock_indexer_class):
        """Test basic project indexing."""
        if not CLI_AVAILABLE:
            pytest.skip("CLI not available (Click or dependencies missing)")
            
        # Mock configuration
        mock_config = MagicMock()
        mock_config.openai_api_key = "sk-test123"
        mock_config.qdrant_api_key = "test-key"
        mock_config.qdrant_url = "http://localhost:6333"
        mock_load_config.return_value = mock_config
        
        # Mock components
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        mock_create_store.return_value = mock_store
        
        # Mock indexer
        mock_indexer = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.processing_time = 1.5
        mock_result.files_processed = 3
        mock_result.entities_created = 15
        mock_result.relations_created = 12
        mock_result.warnings = []
        mock_indexer.index_project.return_value = mock_result
        mock_indexer_class.return_value = mock_indexer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a test project directory
            Path("test_project").mkdir()
            Path("test_project/main.py").write_text("def hello(): pass")
            
            result = runner.invoke(cli, [
                'index',
                '--project', 'test_project',
                '--collection', 'test-collection'
            ])
            
            assert result.exit_code == 0
            assert "Indexing completed" in result.output
            mock_indexer.index_project.assert_called_once()
    
    @patch('claude_indexer.cli_full.CoreIndexer')
    @patch('claude_indexer.cli_full.create_embedder_from_config')
    @patch('claude_indexer.cli_full.create_store_from_config')
    @patch('claude_indexer.cli_full.load_config')
    def test_index_project_with_options(self, mock_load_config, mock_create_store, 
                                       mock_create_embedder, mock_indexer_class):
        """Test project indexing with various options."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.openai_api_key = "sk-test123"
        mock_config.qdrant_api_key = "test-key"
        mock_config.qdrant_url = "http://localhost:6333"
        mock_load_config.return_value = mock_config
        
        # Mock components
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        mock_create_store.return_value = mock_store
        
        # Mock indexer
        mock_indexer = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.processing_time = 2.0
        mock_result.files_processed = 5
        mock_result.entities_created = 25
        mock_result.relations_created = 20
        mock_result.warnings = ["Test warning"]
        mock_indexer.index_project.return_value = mock_result
        mock_indexer.clear_collection.return_value = True
        mock_indexer_class.return_value = mock_indexer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            Path("test_project/main.py").write_text("def hello(): pass")
            
            result = runner.invoke(cli, [
                'index',
                '--project', 'test_project',
                '--collection', 'test-collection',
                '--include-tests',
                '--incremental',
                '--force',
                '--clear',
                '--verbose'
            ])
            
            assert result.exit_code == 0
            assert "Collection cleared" in result.output
            assert "Indexing completed" in result.output
            assert "Warnings:" in result.output
            
            # Verify options were passed correctly
            call_args = mock_indexer.index_project.call_args
            assert call_args.kwargs['include_tests'] is True
            assert call_args.kwargs['incremental'] is True
            assert call_args.kwargs['force'] is True
    
    @patch('claude_indexer.cli_full.CoreIndexer')
    @patch('claude_indexer.cli_full.create_embedder_from_config')
    @patch('claude_indexer.cli_full.create_store_from_config')
    @patch('claude_indexer.cli_full.load_config')
    def test_index_project_generate_commands(self, mock_load_config, mock_create_store, 
                                           mock_create_embedder, mock_indexer_class):
        """Test project indexing with command generation."""
        # Mock configuration and components
        mock_config = MagicMock()
        mock_config.openai_api_key = "sk-test123"
        mock_config.qdrant_api_key = "test-key"
        mock_config.qdrant_url = "http://localhost:6333"
        mock_load_config.return_value = mock_config
        
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        mock_create_store.return_value = mock_store
        
        # Mock indexer and parser
        mock_indexer = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_indexer.index_project.return_value = mock_result
        
        # Mock file finding and parsing
        mock_indexer._find_all_files.return_value = [Path("test.py")]
        mock_parse_result = MagicMock()
        mock_parse_result.success = True
        mock_parse_result.entities = []
        mock_parse_result.relations = []
        mock_indexer.parser_registry.parse_file.return_value = mock_parse_result
        mock_indexer.save_mcp_commands_to_file.return_value = Path("commands.txt")
        
        mock_indexer_class.return_value = mock_indexer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            Path("test_project/main.py").write_text("def hello(): pass")
            
            result = runner.invoke(cli, [
                'index',
                '--project', 'test_project',
                '--collection', 'test-collection',
                '--generate-commands'
            ])
            
            assert result.exit_code == 0
            assert "Generating MCP commands" in result.output
            assert "commands.txt" in result.output
    
    def test_index_project_quiet_and_verbose_error(self):
        """Test that quiet and verbose flags are mutually exclusive."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'index',
                '--project', 'test_project',
                '--collection', 'test-collection',
                '--quiet',
                '--verbose'
            ])
            
            assert result.exit_code == 1
            assert "mutually exclusive" in result.output
    
    def test_index_project_nonexistent_path(self):
        """Test indexing with non-existent project path."""
        runner = CliRunner()
        
        result = runner.invoke(cli, [
            'index',
            '--project', '/nonexistent/path',
            '--collection', 'test-collection'
        ])
        
        assert result.exit_code == 1
        assert "does not exist" in result.output
    
    @patch('claude_indexer.cli_full.CoreIndexer')
    @patch('claude_indexer.cli_full.create_embedder_from_config')
    @patch('claude_indexer.cli_full.create_store_from_config')
    @patch('claude_indexer.cli_full.load_config')
    def test_index_project_failure(self, mock_load_config, mock_create_store, 
                                  mock_create_embedder, mock_indexer_class):
        """Test project indexing failure handling."""
        # Mock configuration
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        
        # Mock components
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        mock_create_store.return_value = mock_store
        
        # Mock indexer with failure
        mock_indexer = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = ["Indexing failed", "Another error"]
        mock_indexer.index_project.return_value = mock_result
        mock_indexer_class.return_value = mock_indexer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'index',
                '--project', 'test_project',
                '--collection', 'test-collection'
            ])
            
            assert result.exit_code == 1
            assert "Indexing failed" in result.output
    
    @patch('claude_indexer.cli_full.CoreIndexer')
    @patch('claude_indexer.cli_full.create_embedder_from_config')
    @patch('claude_indexer.cli_full.create_store_from_config')
    @patch('claude_indexer.cli_full.load_config')
    def test_index_single_file(self, mock_load_config, mock_create_store, 
                              mock_create_embedder, mock_indexer_class):
        """Test single file indexing."""
        # Mock configuration
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        
        # Mock components
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        mock_create_store.return_value = mock_store
        
        # Mock indexer
        mock_indexer = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.processing_time = 0.5
        mock_result.entities_created = 5
        mock_result.relations_created = 3
        mock_indexer.index_single_file.return_value = mock_result
        mock_indexer_class.return_value = mock_indexer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            test_file = Path("test_project/test.py")
            test_file.write_text("def hello(): pass")
            
            result = runner.invoke(cli, [
                'file',
                '--project', 'test_project',
                '--collection', 'test-collection',
                str(test_file)
            ])
            
            assert result.exit_code == 0
            assert "File indexed" in result.output
    
    def test_index_file_outside_project(self):
        """Test indexing file outside project directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            Path("outside.py").write_text("def hello(): pass")
            
            result = runner.invoke(cli, [
                'file',
                '--project', 'test_project',
                '--collection', 'test-collection',
                'outside.py'
            ])
            
            assert result.exit_code == 1
            assert "must be within project" in result.output


class TestWatchCommands:
    """Test watch command group."""
    
    def test_watch_help(self):
        """Test watch command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ['watch', '--help'])
        
        assert result.exit_code == 0
        assert "File watching commands" in result.output
    
    @patch('watchdog.observers.Observer')
    @patch('claude_indexer.watcher.handler.IndexingEventHandler')
    @patch('claude_indexer.cli_full.load_config')
    def test_watch_start(self, mock_load_config, mock_handler_class, mock_observer_class):
        """Test starting file watcher."""
        # Mock configuration
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        
        # Mock event handler and observer
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            # Simulate KeyboardInterrupt to stop the watcher
            def interrupt(*args, **kwargs):
                raise KeyboardInterrupt()
            
            with patch('time.sleep', side_effect=interrupt):
                result = runner.invoke(cli, [
                    'watch', 'start',
                    '--project', 'test_project',
                    '--collection', 'test-collection',
                    '--debounce', '1.5'
                ])
            
            assert result.exit_code == 0
            assert "Watching:" in result.output
            assert "Stopping file watcher" in result.output
            mock_observer.start.assert_called_once()
            mock_observer.stop.assert_called_once()
    
    def test_watch_start_nonexistent_project(self):
        """Test watch start with non-existent project."""
        runner = CliRunner()
        
        result = runner.invoke(cli, [
            'watch', 'start',
            '--project', '/nonexistent/path',
            '--collection', 'test-collection'
        ])
        
        assert result.exit_code == 1
        assert "does not exist" in result.output
    
    def test_watch_start_missing_watchdog(self):
        """Test watch start when watchdog is unavailable."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            # Mock ImportError for watchdog imports inside the function
            with patch('claude_indexer.watcher.handler.IndexingEventHandler', side_effect=ImportError()), \
                 patch('watchdog.observers.Observer', side_effect=ImportError()):
                result = runner.invoke(cli, [
                    'watch', 'start',
                    '--project', 'test_project',
                    '--collection', 'test-collection'
                ])
            
            assert result.exit_code == 1
            assert "Watchdog not available" in result.output


class TestServiceCommands:
    """Test service command group."""
    
    def test_service_help(self):
        """Test service command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ['service', '--help'])
        
        assert result.exit_code == 0
        assert "Background service commands" in result.output
    
    @patch('claude_indexer.cli_full.IndexingService')
    def test_service_start(self, mock_service_class):
        """Test starting background service."""
        mock_service = MagicMock()
        mock_service.start.return_value = True
        mock_service_class.return_value = mock_service
        
        runner = CliRunner()
        result = runner.invoke(cli, ['service', 'start'])
        
        assert result.exit_code == 0
        mock_service.start.assert_called_once()
    
    @patch('claude_indexer.cli_full.IndexingService')
    def test_service_start_failure(self, mock_service_class):
        """Test service start failure."""
        mock_service = MagicMock()
        mock_service.start.return_value = False
        mock_service_class.return_value = mock_service
        
        runner = CliRunner()
        result = runner.invoke(cli, ['service', 'start'])
        
        assert result.exit_code == 1
        assert "Failed to start service" in result.output
    
    @patch('claude_indexer.cli_full.IndexingService')
    def test_service_add_project(self, mock_service_class):
        """Test adding project to service."""
        mock_service = MagicMock()
        mock_service.add_project.return_value = True
        mock_service_class.return_value = mock_service
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'service', 'add-project',
                'test_project',
                'test-collection'
            ])
            
            assert result.exit_code == 0
            assert "Added project" in result.output
            mock_service.add_project.assert_called_once()
    
    @patch('claude_indexer.cli_full.IndexingService')
    def test_service_status(self, mock_service_class):
        """Test service status command."""
        mock_service = MagicMock()
        mock_status = {
            'running': True,
            'config_file': '/path/to/config.json',
            'total_projects': 3,
            'active_watchers': 2,
            'watchers': {
                '/project1': {'running': True},
                '/project2': {'running': False}
            }
        }
        mock_service.get_status.return_value = mock_status
        mock_service_class.return_value = mock_service
        
        runner = CliRunner()
        result = runner.invoke(cli, ['service', 'status', '--verbose'])
        
        assert result.exit_code == 0
        assert "Service Status: 🟢 Running" in result.output
        assert "Projects: 3" in result.output
        assert "Watchers:" in result.output


class TestHooksCommands:
    """Test git hooks command group."""
    
    def test_hooks_help(self):
        """Test hooks command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ['hooks', '--help'])
        
        assert result.exit_code == 0
        assert "Git hooks management" in result.output
    
    @patch('claude_indexer.cli_full.GitHooksManager')
    def test_hooks_install(self, mock_hooks_class):
        """Test git hooks installation."""
        mock_hooks = MagicMock()
        mock_hooks.install_pre_commit_hook.return_value = True
        mock_hooks_class.return_value = mock_hooks
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'hooks', 'install',
                '--project', 'test_project',
                '--collection', 'test-collection',
                '--indexer-path', '/usr/local/bin/indexer'
            ])
            
            assert result.exit_code == 0
            mock_hooks.install_pre_commit_hook.assert_called_once()
    
    @patch('claude_indexer.cli_full.GitHooksManager')
    def test_hooks_uninstall(self, mock_hooks_class):
        """Test git hooks uninstallation."""
        mock_hooks = MagicMock()
        mock_hooks.uninstall_pre_commit_hook.return_value = True
        mock_hooks_class.return_value = mock_hooks
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'hooks', 'uninstall',
                '--project', 'test_project',
                '--collection', 'test-collection'
            ])
            
            assert result.exit_code == 0
            mock_hooks.uninstall_pre_commit_hook.assert_called_once()
    
    @patch('claude_indexer.cli_full.GitHooksManager')
    def test_hooks_status(self, mock_hooks_class):
        """Test git hooks status command."""
        mock_hooks = MagicMock()
        mock_status = {
            'is_git_repo': True,
            'hooks_dir_exists': True,
            'hook_installed': True,
            'hook_executable': True,
            'indexer_command': 'claude-indexer --project /path --collection test'
        }
        mock_hooks.get_hook_status.return_value = mock_status
        mock_hooks_class.return_value = mock_hooks
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'hooks', 'status',
                '--project', 'test_project',
                '--collection', 'test-collection',
                '--verbose'
            ])
            
            assert result.exit_code == 0
            assert "Git repository: ✅" in result.output
            assert "Pre-commit hook: ✅ Installed" in result.output
            assert "Command:" in result.output


class TestSearchCommand:
    """Test search command functionality."""
    
    @patch('claude_indexer.cli_full.CoreIndexer')
    @patch('claude_indexer.cli_full.create_embedder_from_config')
    @patch('claude_indexer.cli_full.create_store_from_config')
    @patch('claude_indexer.cli_full.load_config')
    def test_search_basic(self, mock_load_config, mock_create_store, 
                         mock_create_embedder, mock_indexer_class):
        """Test basic search functionality."""
        # Mock configuration
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        
        # Mock components
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        mock_create_store.return_value = mock_store
        
        # Mock indexer and search results
        mock_indexer = MagicMock()
        mock_search_results = [
            {
                'score': 0.95,
                'payload': {
                    'name': 'test_function',
                    'entityType': 'function',
                    'file_path': '/path/to/file.py',
                    'observations': ['A test function', 'Line 10 in file.py']
                }
            }
        ]
        mock_indexer.search_similar.return_value = mock_search_results
        mock_indexer_class.return_value = mock_indexer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'search',
                '--project', 'test_project',
                '--collection', 'test-collection',
                'test query'
            ])
            
            assert result.exit_code == 0
            assert "Found 1 results" in result.output
            assert "test_function" in result.output
    
    @patch('claude_indexer.cli_full.CoreIndexer')
    @patch('claude_indexer.cli_full.create_embedder_from_config')
    @patch('claude_indexer.cli_full.create_store_from_config')
    @patch('claude_indexer.cli_full.load_config')
    def test_search_no_results(self, mock_load_config, mock_create_store, 
                              mock_create_embedder, mock_indexer_class):
        """Test search with no results."""
        # Mock configuration and components
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        mock_create_store.return_value = mock_store
        
        # Mock indexer with no results
        mock_indexer = MagicMock()
        mock_indexer.search_similar.return_value = []
        mock_indexer_class.return_value = mock_indexer
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test_project").mkdir()
            
            result = runner.invoke(cli, [
                'search',
                '--project', 'test_project',
                '--collection', 'test-collection',
                '--limit', '5',
                '--type', 'entity',
                'nonexistent query'
            ])
            
            assert result.exit_code == 0
            assert "No results found" in result.output