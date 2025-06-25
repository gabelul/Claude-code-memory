"""Click-based CLI interface for the Claude Code indexer."""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

from .config import load_config, IndexerConfig
from .indexer import CoreIndexer
from .embeddings.registry import create_embedder_from_config
from .storage.registry import create_store_from_config

# Only import these if they're available
try:
    from .service import IndexingService
    from .git_hooks import GitHooksManager
    SERVICE_AVAILABLE = True
except ImportError:
    SERVICE_AVAILABLE = False

try:
    import click
    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False

# Minimal CLI function for when Click is not available
def cli():
    """Claude Code Memory Indexer - Universal semantic indexing for codebases."""
    if not CLICK_AVAILABLE:
        print("Click not available. Install with: pip install click")
        sys.exit(1)

# Skip Click decorators and complex CLI setup when Click is not available
if not CLICK_AVAILABLE:
    # Early exit to prevent decorator errors during import
    import sys
    # Don't process the rest of the file to avoid decorator errors
    sys.modules[__name__].__dict__.update(locals())
    if __name__ == '__main__':
        cli()
        sys.exit(1)
else:
    # Only define Click-based CLI when Click is available

    # Common options as decorators
    def common_options(f):
        """Common options for indexing commands."""
        f = click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')(f)
        f = click.option('--quiet', '-q', is_flag=True, help='Suppress non-error output')(f)
        f = click.option('--config', type=click.Path(exists=True), help='Configuration file path')(f)
        return f


    def project_options(f):
        """Project-specific options."""
        f = click.option('--project', '-p', type=click.Path(), required=True, 
                        help='Project directory path')(f)
        f = click.option('--collection', '-c', required=True, 
                        help='Collection name for vector storage')(f)
        return f


    # Check for main help before defining CLI
    if len(sys.argv) >= 2 and sys.argv[1] in ['--help', '-h']:
        print("""Usage: python -m claude_indexer [OPTIONS]

  Claude Code Memory Indexer - Universal semantic indexing for codebases.

Options:
  -c, --collection TEXT  Collection name for vector storage  [required]
  -p, --project PATH     Project directory path  [required]
  --config PATH          Configuration file path
  -q, --quiet            Suppress non-error output
  -v, --verbose          Enable verbose output
  --include-tests        Include test files in indexing
  --incremental          Only process changed files
  --force                Force reprocessing of all files
  --clear                Clear collection before indexing
  --generate-commands    Generate MCP commands instead of auto-loading
  --depth [basic|full]   Analysis depth
  --version              Show the version and exit.
  --help                 Show this message and exit.

Commands:
  hooks    Git hooks management.
  search   Search for similar entities and relations.
  service  Background service commands.
  watch    File watching commands.
  file     Index a single file.""")
        sys.exit(0)

    @click.group(invoke_without_command=True)
    @click.version_option(version="1.0.0")
    @click.pass_context
    def cli(ctx):
        """Claude Code Memory Indexer - Universal semantic indexing for codebases."""
        # If no subcommand, this will be handled by the default routing in wrapper
        pass

    @cli.command()
    @project_options
    @common_options
    @click.option('--include-tests', is_flag=True, help='Include test files in indexing')
    @click.option('--incremental', is_flag=True, help='Only process changed files')
    @click.option('--force', is_flag=True, help='Force reprocessing of all files')
    @click.option('--clear', is_flag=True, help='Clear collection before indexing')
    @click.option('--generate-commands', is_flag=True, help='Generate MCP commands instead of auto-loading')
    @click.option('--depth', type=click.Choice(['basic', 'full']), default='full',
                  help='Analysis depth')
    def index(project, collection, verbose, quiet, config, include_tests, 
            incremental, force, clear, generate_commands, depth):
        """Index an entire project."""
        
        if quiet and verbose:
            click.echo("Error: --quiet and --verbose are mutually exclusive", err=True)
            sys.exit(1)
        
        try:
            # Load configuration
            config_obj = load_config(Path(config) if config else None)
        
            # Validate project path
            project_path = Path(project).resolve()
            if not project_path.exists():
                click.echo(f"Error: Project path does not exist: {project_path}", err=True)
                sys.exit(1)
            
            # Create components
            embedder = create_embedder_from_config({
                "provider": "openai",
                "api_key": config_obj.openai_api_key,
                "model": "text-embedding-3-small"
            })
            
            vector_store = create_store_from_config({
                "backend": "qdrant",
                "url": config_obj.qdrant_url,
                "api_key": config_obj.qdrant_api_key
            })
            
            # Create indexer
            indexer = CoreIndexer(config_obj, embedder, vector_store, project_path)
            
            # Clear collection if requested
            if clear:
                if not quiet:
                    click.echo(f"🗑️ Clearing collection: {collection}")
                success = indexer.clear_collection(collection)
                if not success:
                    click.echo("❌ Failed to clear collection", err=True)
                    sys.exit(1)
                elif not quiet:
                    click.echo("✅ Collection cleared")
        
            # Run indexing
            if not quiet:
                click.echo(f"🔄 Indexing project: {project_path}")
                click.echo(f"📦 Collection: {collection}")
                if incremental:
                    click.echo("⚡ Mode: Incremental")
                else:
                    click.echo("🔄 Mode: Full")
                if generate_commands:
                    click.echo("📝 Mode: Generate MCP commands")
            
            result = indexer.index_project(
                collection_name=collection,
                include_tests=include_tests,
                incremental=incremental,
                force=force
            )
        
            # Generate commands if requested
            if generate_commands and result.success:
                # Get entities and relations from the result
                # For now, we'll process files again to get the data for command generation
                if not quiet:
                    click.echo("📝 Generating MCP commands...")
                
                # Process files to get entities/relations for command generation
                files_to_process = indexer._find_all_files(include_tests)
                all_entities = []
                all_relations = []
                
                for file_path in files_to_process:
                    parse_result = indexer.parser_registry.parse_file(file_path)
                    if parse_result.success:
                        all_entities.extend(parse_result.entities)
                        all_relations.extend(parse_result.relations)
                
                # Save commands to file
                commands_file = indexer.save_mcp_commands_to_file(all_entities, all_relations, collection)
                
                if not quiet:
                    click.echo(f"📄 MCP commands saved to: {commands_file}")
                    click.echo(f"   Copy and paste commands from this file into Claude Code")
                    click.echo(f"   Total entities: {len(all_entities)}")
                    click.echo(f"   Total relations: {len(all_relations)}")
                
                return  # Don't auto-load when generating commands
        
            # Report results
            if result.success:
                if not quiet:
                    click.echo(f"✅ Indexing completed in {result.processing_time:.1f}s")
                    click.echo(f"   Files processed: {result.files_processed}")
                    click.echo(f"   Entities created: {result.entities_created}")
                    click.echo(f"   Relations created: {result.relations_created}")
                    
                    if result.warnings and verbose:
                        click.echo("⚠️  Warnings:")
                        for warning in result.warnings:
                            click.echo(f"   {warning}")
            else:
                click.echo("❌ Indexing failed", err=True)
                for error in result.errors:
                    click.echo(f"   {error}", err=True)
                sys.exit(1)
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            if verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)


    @cli.command()
    @project_options
    @common_options
    @click.argument('file_path', type=click.Path(exists=True))
    def file(project, collection, file_path, verbose, quiet, config):
        """Index a single file."""
        
        try:
            # Load configuration
            config_obj = load_config(Path(config) if config else None)
            
            # Validate paths
            project_path = Path(project).resolve()
            target_file = Path(file_path).resolve()
            
            # Ensure file is within project
            try:
                target_file.relative_to(project_path)
            except ValueError:
                click.echo(f"Error: File must be within project directory", err=True)
                sys.exit(1)
            
            # Create components
            embedder = create_embedder_from_config({
                "provider": "openai",
                "api_key": config_obj.openai_api_key,
                "model": "text-embedding-3-small"
            })
            
            vector_store = create_store_from_config({
                "backend": "qdrant",
                "url": config_obj.qdrant_url,
                "api_key": config_obj.qdrant_api_key
            })
            
            # Create indexer and process file
            indexer = CoreIndexer(config_obj, embedder, vector_store, project_path)
            
            if not quiet:
                click.echo(f"🔄 Indexing file: {target_file.relative_to(project_path)}")
            
            result = indexer.index_single_file(target_file, collection)
            
            # Report results
            if result.success:
                if not quiet:
                    click.echo(f"✅ File indexed in {result.processing_time:.1f}s")
                    click.echo(f"   Entities: {result.entities_created}")
                    click.echo(f"   Relations: {result.relations_created}")
            else:
                click.echo("❌ File indexing failed", err=True)
                for error in result.errors:
                    click.echo(f"   {error}", err=True)
                sys.exit(1)
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @cli.group()
    def watch():
        """File watching commands."""
        pass


    @watch.command()
    @project_options
    @common_options
    @click.option('--debounce', type=float, default=2.0, 
                  help='Debounce delay in seconds (default: 2.0)')
    def start(project, collection, verbose, quiet, config, debounce):
        """Start file watching for real-time indexing."""
        
        try:
            from .watcher.handler import IndexingEventHandler
            from watchdog.observers import Observer
            
            # Validate project path
            project_path = Path(project).resolve()
            if not project_path.exists():
                click.echo(f"Error: Project path does not exist: {project_path}", err=True)
                sys.exit(1)
            
            # Load configuration
            config_obj = load_config(Path(config) if config else None)
            
            # Create event handler
            settings = {
                "debounce_seconds": debounce,
                "watch_patterns": ["*.py", "*.md"],
                "ignore_patterns": ["*.pyc", "__pycache__", ".git", ".venv"]
            }
            
            event_handler = IndexingEventHandler(
                project_path=str(project_path),
                collection_name=collection,
                debounce_seconds=debounce,
                settings=settings
            )
            
            # Start observer
            observer = Observer()
            observer.schedule(event_handler, str(project_path), recursive=True)
            observer.start()
            
            if not quiet:
                click.echo(f"👁️  Watching: {project_path}")
                click.echo(f"📦 Collection: {collection}")
                click.echo(f"⏱️  Debounce: {debounce}s")
                click.echo("Press Ctrl+C to stop")
            
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
                if not quiet:
                    click.echo("\n🛑 Stopping file watcher...")
            
            observer.join()
            
            if not quiet:
                click.echo("✅ File watcher stopped")
        
        except ImportError:
            click.echo("Error: Watchdog not available. Install with: pip install watchdog", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @cli.group()
    def service():
        """Background service commands."""
        pass


    @service.command()
    @common_options
    @click.option('--config-file', type=click.Path(), 
                  help='Service configuration file path')
    def start(verbose, quiet, config, config_file):
        """Start the background indexing service."""
        
        try:
            svc = IndexingService(config_file)
            
            if not quiet:
                click.echo("🚀 Starting background indexing service...")
            
            success = svc.start()
            
            if not success:
                click.echo("❌ Failed to start service", err=True)
                sys.exit(1)
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @service.command('add-project')
    @click.argument('project_path', type=click.Path(exists=True))
    @click.argument('collection_name')
    @common_options
    @click.option('--config-file', type=click.Path(), 
                  help='Service configuration file path')
    def add_project(project_path, collection_name, verbose, quiet, config, config_file):
        """Add a project to the service watch list."""
        
        try:
            svc = IndexingService(config_file)
            project_path = str(Path(project_path).resolve())
            
            success = svc.add_project(project_path, collection_name)
            
            if success:
                if not quiet:
                    click.echo(f"✅ Added project: {project_path} -> {collection_name}")
            else:
                click.echo("❌ Failed to add project", err=True)
                sys.exit(1)
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @service.command()
    @common_options
    @click.option('--config-file', type=click.Path(), 
                  help='Service configuration file path')
    def status(verbose, quiet, config, config_file):
        """Show service status."""
        
        try:
            svc = IndexingService(config_file)
            status_info = svc.get_status()
            
            click.echo(f"Service Status: {'🟢 Running' if status_info['running'] else '🔴 Stopped'}")
            click.echo(f"Config file: {status_info['config_file']}")
            click.echo(f"Projects: {status_info['total_projects']}")
            click.echo(f"Active watchers: {status_info['active_watchers']}")
            
            if verbose and status_info['watchers']:
                click.echo("\nWatchers:")
                for project, info in status_info['watchers'].items():
                    status = "🟢 Running" if info['running'] else "🔴 Stopped"
                    click.echo(f"  {project}: {status}")
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @cli.group()
    def hooks():
        """Git hooks management."""
        pass


    @hooks.command()
    @project_options
    @common_options
    @click.option('--indexer-path', help='Path to indexer executable')
    def install(project, collection, verbose, quiet, config, indexer_path):
        """Install git pre-commit hook."""
        
        try:
            project_path = Path(project).resolve()
            hooks_manager = GitHooksManager(str(project_path), collection)
            
            success = hooks_manager.install_pre_commit_hook(indexer_path, quiet=quiet)
            
            if not success:
                sys.exit(1)
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @hooks.command()
    @project_options
    @common_options
    def uninstall(project, collection, verbose, quiet, config):
        """Uninstall git pre-commit hook."""
        
        try:
            project_path = Path(project).resolve()
            hooks_manager = GitHooksManager(str(project_path), collection)
            
            success = hooks_manager.uninstall_pre_commit_hook(quiet=quiet)
            
            if not success:
                sys.exit(1)
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @hooks.command()
    @project_options
    @common_options
    def status(project, collection, verbose, quiet, config):
        """Show git hooks status."""
        
        try:
            project_path = Path(project).resolve()
            hooks_manager = GitHooksManager(str(project_path), collection)
            
            status_info = hooks_manager.get_hook_status()
            
            click.echo(f"Git repository: {'✅' if status_info['is_git_repo'] else '❌'}")
            click.echo(f"Hooks directory: {'✅' if status_info['hooks_dir_exists'] else '❌'}")
            click.echo(f"Pre-commit hook: {'✅ Installed' if status_info['hook_installed'] else '❌ Not installed'}")
            
            if status_info['hook_installed']:
                click.echo(f"Hook executable: {'✅' if status_info['hook_executable'] else '❌'}")
                if verbose and 'indexer_command' in status_info:
                    click.echo(f"Command: {status_info['indexer_command']}")
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)


    @cli.command()
    @project_options
    @click.argument('query')
    @click.option('--limit', type=int, default=10, help='Maximum results')
    @click.option('--type', 'result_type', type=click.Choice(['entity', 'relation']), 
                  help='Filter by result type')
    @common_options
    def search(project, collection, query, limit, result_type, verbose, quiet, config):
        """Search for similar entities and relations."""
        
        try:
            # Load configuration
            config_obj = load_config(Path(config) if config else None)
            
            # Create components
            embedder = create_embedder_from_config({
                "provider": "openai",
                "api_key": config_obj.openai_api_key,
                "model": "text-embedding-3-small"
            })
            
            vector_store = create_store_from_config({
                "backend": "qdrant",
                "url": config_obj.qdrant_url,
                "api_key": config_obj.qdrant_api_key
            })
            
            # Create indexer and search
            project_path = Path(project).resolve()
            indexer = CoreIndexer(config_obj, embedder, vector_store, project_path)
            
            results = indexer.search_similar(collection, query, limit, result_type)
            
            if results:
                if not quiet:
                    click.echo(f"🔍 Found {len(results)} results for: {query}")
                    click.echo()
                
                for i, result in enumerate(results, 1):
                    score = result.get('score', 0)
                    payload = result.get('payload', {})
                    
                    click.echo(f"{i}. {payload.get('name', 'Unknown')} (score: {score:.3f})")
                    
                    if verbose:
                        entity_type = payload.get('entityType', payload.get('type', 'unknown'))
                        click.echo(f"   Type: {entity_type}")
                        
                        if 'file_path' in payload:
                            click.echo(f"   File: {payload['file_path']}")
                        
                        if 'observations' in payload:
                            obs = payload['observations'][:2]  # First 2 observations
                            for ob in obs:
                                click.echo(f"   📝 {ob}")
                        
                        click.echo()
            else:
                if not quiet:
                    click.echo(f"🔍 No results found for: {query}")
        
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)

    # End of Click-available conditional block

if __name__ == '__main__':
    cli()