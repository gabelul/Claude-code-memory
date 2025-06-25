"""File system event handler for automatic indexing."""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Set
from .debounce import FileChangeCoalescer

try:
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Mock class for when watchdog is not available
    class FileSystemEventHandler:
        pass


class IndexingEventHandler(FileSystemEventHandler):
    """File system event handler with debouncing and batch processing."""
    
    def __init__(self, project_path: str, collection_name: str, 
                 debounce_seconds: float = 2.0, settings: Optional[Dict[str, Any]] = None):
        
        if not WATCHDOG_AVAILABLE:
            raise ImportError("Watchdog not available. Install with: pip install watchdog")
        
        super().__init__()
        
        self.project_path = Path(project_path)
        self.collection_name = collection_name
        self.debounce_seconds = debounce_seconds
        self.settings = settings or {}
        
        # File filtering
        self.watch_patterns = self.settings.get("watch_patterns", ["*.py", "*.md"])
        self.ignore_patterns = self.settings.get("ignore_patterns", [
            "*.pyc", "__pycache__", ".git", ".venv", "node_modules"
        ])
        self.max_file_size = self.settings.get("max_file_size", 1048576)  # 1MB
        
        # Change tracking
        self.coalescer = FileChangeCoalescer(delay=debounce_seconds)
        self.processed_files: Set[str] = set()
        
        # Stats
        self.events_received = 0
        self.events_processed = 0
        self.events_ignored = 0
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "modified")
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "created")
    
    def on_deleted(self, event):
        """Handle file deletion events."""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "deleted")
    
    def on_moved(self, event):
        """Handle file move events."""
        if not event.is_directory:
            # Treat as delete + create
            self._handle_file_event(event.src_path, "deleted")
            self._handle_file_event(event.dest_path, "created")
    
    def _handle_file_event(self, file_path: str, event_type: str):
        """Process a file system event."""
        self.events_received += 1
        
        try:
            path = Path(file_path)
            
            # Check if we should process this file
            if not self._should_process_file(path):
                self.events_ignored += 1
                return
            
            # Use coalescer to debounce rapid changes
            if event_type == "deleted":
                # Process deletions immediately
                self._process_file_deletion(path)
                self.events_processed += 1
            else:
                # Debounce modifications and creations
                if self.coalescer.add_change(file_path):
                    self._process_file_change(path, event_type)
                    self.events_processed += 1
        
        except Exception as e:
            print(f"❌ Error handling file event {file_path}: {e}")
    
    def _should_process_file(self, path: Path) -> bool:
        """Check if a file should be processed."""
        try:
            # Check if file is within project
            try:
                path.relative_to(self.project_path)
            except ValueError:
                return False
            
            # Check file extension
            if not self._matches_patterns(path.name, self.watch_patterns):
                return False
            
            # Check ignore patterns
            if self._matches_patterns(str(path), self.ignore_patterns):
                return False
            
            # Check file size (for existing files)
            if path.exists() and path.is_file():
                if path.stat().st_size > self.max_file_size:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _matches_patterns(self, text: str, patterns: list) -> bool:
        """Check if text matches any pattern."""
        import fnmatch
        
        for pattern in patterns:
            if fnmatch.fnmatch(text, pattern) or pattern in text:
                return True
        return False
    
    def _process_file_change(self, path: Path, event_type: str):
        """Process a file change or creation."""
        try:
            relative_path = path.relative_to(self.project_path)
            print(f"🔄 Auto-indexing ({event_type}): {relative_path}")
            
            # Create indexer and process file
            success = self._run_incremental_indexing()
            
            if success:
                self.processed_files.add(str(path))
                print(f"✅ Indexed: {relative_path}")
            else:
                print(f"❌ Failed to index: {relative_path}")
        
        except Exception as e:
            print(f"❌ Error processing file change {path}: {e}")
    
    def _process_file_deletion(self, path: Path):
        """Process a file deletion."""
        try:
            relative_path = path.relative_to(self.project_path)
            print(f"🗑️  File deleted: {relative_path}")
            
            # Remove from processed files
            self.processed_files.discard(str(path))
            
            # TODO: Implement entity deletion from vector store
            # This would require tracking which entities belong to which files
            
        except Exception as e:
            print(f"❌ Error processing file deletion {path}: {e}")
    
    def _run_incremental_indexing(self) -> bool:
        """Run incremental indexing for the project."""
        try:
            # Import here to avoid circular imports
            from ..main import run_indexing
            
            # Run indexing with minimal output
            return run_indexing(
                project_path=str(self.project_path),
                collection_name=self.collection_name,
                incremental=True,
                quiet=True,
                verbose=False
            )
            
        except Exception as e:
            print(f"❌ Indexing failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event handler statistics."""
        return {
            "project_path": str(self.project_path),
            "collection_name": self.collection_name,
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "events_ignored": self.events_ignored,
            "processed_files": len(self.processed_files),
            "debounce_seconds": self.debounce_seconds,
            "coalescer_stats": self.coalescer.get_stats() if hasattr(self.coalescer, 'get_stats') else {}
        }
    
    def cleanup(self):
        """Clean up resources and old entries."""
        # Clean up old coalescer entries
        self.coalescer.cleanup_old_entries()
        
        # Clean up processed files set if it gets too large
        if len(self.processed_files) > 10000:
            # Keep only the most recent 5000
            self.processed_files = set(list(self.processed_files)[-5000:])


class AsyncIndexingEventHandler:
    """Async version of the event handler using asyncio debouncer."""
    
    def __init__(self, project_path: str, collection_name: str,
                 debounce_seconds: float = 2.0, settings: Optional[Dict[str, Any]] = None):
        
        self.project_path = Path(project_path)
        self.collection_name = collection_name
        self.settings = settings or {}
        
        # Import here to avoid circular imports
        from .debounce import AsyncDebouncer
        
        self.debouncer = AsyncDebouncer(
            delay=debounce_seconds,
            max_batch_size=settings.get("max_batch_size", 50)
        )
        self.debouncer.set_callback(self._process_batch)
        
        # Stats
        self.batches_processed = 0
        self.files_processed = 0
        
    async def start(self):
        """Start the async event handler."""
        await self.debouncer.start()
    
    async def stop(self):
        """Stop the async event handler."""
        await self.debouncer.stop()
    
    async def handle_file_event(self, file_path: str, event_type: str):
        """Handle a file system event asynchronously."""
        await self.debouncer.add_file_event(file_path, event_type)
    
    async def _process_batch(self, batch_event: Dict[str, Any]):
        """Process a batch of file changes."""
        try:
            modified_files = batch_event.get("modified_files", [])
            deleted_files = batch_event.get("deleted_files", [])
            
            if modified_files:
                print(f"🔄 Batch indexing: {len(modified_files)} files")
                success = await self._run_batch_indexing(modified_files)
                
                if success:
                    self.files_processed += len(modified_files)
                    print(f"✅ Batch indexed: {len(modified_files)} files")
                else:
                    print(f"❌ Batch indexing failed")
            
            if deleted_files:
                print(f"🗑️  Processing {len(deleted_files)} deletions")
                await self._handle_batch_deletions(deleted_files)
            
            self.batches_processed += 1
            
        except Exception as e:
            print(f"❌ Error processing batch: {e}")
    
    async def _run_batch_indexing(self, file_paths: list) -> bool:
        """Run indexing for a batch of files."""
        try:
            # Run in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            
            def run_indexing():
                from ..main import run_indexing
                return run_indexing(
                    project_path=str(self.project_path),
                    collection_name=self.collection_name,
                    incremental=True,
                    quiet=True,
                    verbose=False
                )
            
            return await loop.run_in_executor(None, run_indexing)
            
        except Exception as e:
            print(f"❌ Batch indexing failed: {e}")
            return False
    
    async def _handle_batch_deletions(self, file_paths: list):
        """Handle batch file deletions."""
        try:
            # TODO: Implement batch entity deletion
            # This would require tracking entity-to-file mappings
            for file_path in file_paths:
                relative_path = Path(file_path).relative_to(self.project_path)
                print(f"   Deleted: {relative_path}")
        
        except Exception as e:
            print(f"❌ Error handling deletions: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get async handler statistics."""
        return {
            "project_path": str(self.project_path),
            "collection_name": self.collection_name,
            "batches_processed": self.batches_processed,
            "files_processed": self.files_processed,
            "debouncer_stats": self.debouncer.get_stats()
        }