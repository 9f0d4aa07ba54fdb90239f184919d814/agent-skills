"""
REPOSITORY WORKER — Continuously maintains the repository cache.

Uses the event-driven specialized caches:
  - FileCache: file metadata (path, size, mtime, hash, language)
  - SymbolCache: symbols (functions, classes, variables)
  - DependencyCache: imports and dependency graph
  - EmbeddingCache: file embeddings for semantic search
  - GitCache: git status, branch, commit, changes
  - LspCache: LSP/Pylance diagnostics per file
  - BuildCache: build/test/lint results

Handles commands:
  - CMD_SCAN_REPOSITORY: Full scan of the repository
  - CMD_REFRESH_CACHE: Incremental refresh of changed files (event-driven)
  - CMD_QUERY_CACHE: Query any cache (files, symbols, imports, etc.)

Listens to events:
  - task.created: Trigger initial scan via RepositoryCache.initialize()
  - step.completed: Check if cache needs updating
"""

import json, time, os, threading
from typing import Optional
from pathlib import Path

from kernel import BaseWorker, EventBus, Event, Artifact, ArtifactType, ArtifactStore
from kernel.job import Job, JobStep
from kernel.commands import CommandBus, Command, CommandStatus
from kernel.state_machine import JobState, StepState
from repository import RepositoryCache, SymbolEntry, ImportRelation, DiagnosticEntry, \
    FileEntry, GitStatus, BuildResult


class RepositoryWorker(BaseWorker):
    """Worker that maintains the repository cache continuously.

    Runs cache maintenance in a background thread.
    Responds to cache-related commands (scan, refresh, query).
    Uses the event-driven specialized caches.
    """

    def __init__(self, event_bus: EventBus, artifact_store: ArtifactStore,
                 command_bus: CommandBus = None,
                 repo_root: str = None, cache_dir: str = None):
        super().__init__("repository", "RepositoryWorker", event_bus, artifact_store)
        self.command_bus = command_bus
        self.repo_root = repo_root or os.getcwd()
        self.cache = RepositoryCache(self.repo_root, cache_dir)

        # Background maintenance
        self._maintenance_thread: Optional[threading.Thread] = None
        self._running = False
        self._maintenance_interval = 30  # seconds between incremental refreshes

    def register(self):
        """Register event subscriptions and command handlers."""
        # Subscribe to events
        sub_id = self.event_bus.subscribe(
            "task.created", self._on_task_created, self.name
        )
        self._subscriptions.append(sub_id)

        sub_id = self.event_bus.subscribe(
            "step.completed", self._on_step_completed, self.name
        )
        self._subscriptions.append(sub_id)

        # Register command handlers if command_bus is available
        if self.command_bus:
            self.command_bus.register_handler(
                "CMD_SCAN_REPOSITORY", self._handle_scan_command
            )
            self.command_bus.register_handler(
                "CMD_REFRESH_CACHE", self._handle_refresh_command
            )
            self.command_bus.register_handler(
                "CMD_QUERY_CACHE", self._handle_query_command
            )

    def unregister(self):
        """Stop background maintenance and unsubscribe."""
        self._running = False
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            self._maintenance_thread.join(timeout=5)
        self.cache.shutdown()
        super().unregister()

    # ── Event Handlers ──

    def _on_task_created(self, event: Event):
        """Trigger initial scan when a task is created."""
        if self.cache.files.count() == 0:
            self.log("Task created — initializing repository cache...")
            self.cache.initialize(event_bus=self.event_bus)
            self.cache.git.refresh()
            self.cache.save_all()
            s = self.cache.get_statistics()
            self.log(f"Repository cache initialized: "
                     f"{s.get('file_cache', {}).get('total_files', 0)} files")

    def _on_step_completed(self, event: Event):
        """Check if cache maintenance is needed after steps complete."""
        if not self._running:
            self._start_background_maintenance()

    # ── Command Handlers ──

    def _handle_scan_command(self, command: Command) -> dict:
        """Handle full repository scan command."""
        job = command.params.get("job")
        step = command.params.get("step")

        self.log("Starting full repository scan...")
        start = time.time()

        # Use the new event-driven scan: initialize connects caches to event bus
        self.cache.initialize(event_bus=self.event_bus)
        count = self.cache.scan()

        # Update git status
        self.cache.git.refresh()

        # Save all caches
        self.cache.save_all()

        duration = time.time() - start
        self.log(f"Repository scan complete: {count} files in {duration:.1f}s")

        # Create artifact with results
        stats = self.cache.get_statistics()
        artifact = Artifact(
            name=f"repo-scan:{job.id if job else 'unknown'}",
            artifact_type=ArtifactType.METRIC,
            content=json.dumps({
                "files_indexed": count,
                "duration": duration,
                "total_files": stats.get("file_cache", {}).get("total_files", 0),
                "total_symbols": stats.get("symbol_cache", {}).get("total_symbols", 0),
            }),
            source_job=job.id if job else "",
            source_step=step.id if step else "",
            tags=["repository", "scan"],
        )
        self.artifacts.store(artifact)

        return {
            "status": "success",
            "files_indexed": count,
            "duration": duration,
            "cache_stats": stats,
        }

    def _handle_refresh_command(self, command: Command) -> dict:
        """Handle incremental cache refresh command."""
        self.log("Starting incremental cache refresh...")
        start = time.time()

        # Event-driven: FileCache.refresh() detects changed files
        changed = self.cache.refresh()

        # Update git status
        self.cache.git.refresh()

        # Save dirty caches only
        self.cache.save_all()

        duration = time.time() - start
        self.log(f"Cache refresh: {changed} files changed in {duration:.1f}s")

        return {
            "status": "success",
            "files_changed": changed,
            "duration": duration,
            "cache_stats": self.cache.get_statistics(),
        }

    def _handle_query_command(self, command: Command) -> dict:
        """Handle cache query command."""
        query_type = command.params.get("query_type", "")
        query_params = command.params.get("params", {})

        if query_type == "find_files":
            results = self.cache.files.find(
                pattern=query_params.get("pattern"),
                language=query_params.get("language"),
            )
            return {"status": "success", "results": [r.to_dict() for r in results]}

        elif query_type == "find_symbol":
            results = self.cache.symbols.find(
                name=query_params.get("name", ""),
                kind=query_params.get("kind"),
                file_path=query_params.get("file_path"),
            )
            return {"status": "success", "results": [r.to_dict() for r in results]}

        elif query_type == "get_imports":
            results = self.cache.dependencies.get_imports(
                query_params.get("file", "")
            )
            return {"status": "success", "results": [r.to_dict() for r in results]}

        elif query_type == "get_dependents":
            results = self.cache.dependencies.get_dependents(
                query_params.get("file", "")
            )
            return {"status": "success", "results": results}

        elif query_type == "get_statistics":
            return {"status": "success", "results": self.cache.get_statistics()}

        elif query_type == "get_summary":
            return {"status": "success", "results": self.cache.get_summary()}

        elif query_type == "get_git_status":
            return {"status": "success", "results": self.cache.git.to_dict()}

        elif query_type == "get_affected_files":
            results = self.cache.dependencies.get_affected_files(
                query_params.get("files", [])
            )
            return {"status": "success", "results": list(results)}

        elif query_type == "get_diagnostics":
            results = self.cache.lsp.get(
                file_path=query_params.get("file")
            )
            return {"status": "success", "results": [r.to_dict() for r in results]}

        elif query_type == "get_build_results":
            results = self.cache.build.get(
                file_path=query_params.get("file")
            )
            return {"status": "success", "results": [r.to_dict() for r in results]}

        return {
            "status": "error",
            "error": f"Unknown query type: {query_type}",
            "available": ["find_files", "find_symbol", "get_imports",
                          "get_dependents", "get_statistics", "get_summary",
                          "get_git_status", "get_affected_files",
                          "get_diagnostics", "get_build_results"],
        }

    # ── Background Maintenance ──

    def _start_background_maintenance(self):
        """Start background thread for periodic cache maintenance."""
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            return
        self._running = True
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop, daemon=True
        )
        self._maintenance_thread.start()
        self.log("Background cache maintenance started")

    def _maintenance_loop(self):
        """Periodically refresh the cache using event-driven updates."""
        while self._running:
            time.sleep(self._maintenance_interval)
            try:
                # Event-driven refresh — only changed files are re-indexed
                changed = self.cache.refresh()
                if changed > 0:
                    self.cache.git.refresh()
                    self.cache.save_all()
                    self.log(f"Background refresh: {changed} files updated")
            except Exception as e:
                self.log(f"Background maintenance error: {e}")

    # ── Worker Interface ──

    def can_handle(self, step: JobStep) -> bool:
        return step.worker_type == self.worker_type or step.worker_type == "repository"

    def handle(self, job: Job, step: JobStep) -> dict:
        """Handle a repository-related step."""
        action = step.params.get("action", "scan")

        if action == "scan":
            return self._handle_scan_command(
                Command(command_type="CMD_SCAN_REPOSITORY", job_id=job.id,
                        step_id=step.id, params={"job": job, "step": step})
            )
        elif action == "refresh":
            return self._handle_refresh_command(
                Command(command_type="CMD_REFRESH_CACHE", job_id=job.id,
                        step_id=step.id, params={"job": job, "step": step})
            )
        elif action == "query":
            return self._handle_query_command(
                Command(command_type="CMD_QUERY_CACHE", job_id=job.id,
                        step_id=step.id, params=step.params.get("query_params", {}))
            )
        else:
            return {"status": "error", "error": f"Unknown action: {action}"}

    # ── Public API ──

    def scan_repository(self, job: Job = None, step: JobStep = None) -> dict:
        """Trigger a full repository scan."""
        return self._handle_scan_command(
            Command(command_type="CMD_SCAN_REPOSITORY",
                    job_id=job.id if job else "",
                    step_id=step.id if step else "",
                    params={"job": job, "step": step})
        )

    def refresh_cache(self) -> dict:
        """Trigger an incremental cache refresh."""
        return self._handle_refresh_command(
            Command(command_type="CMD_REFRESH_CACHE", params={})
        )

    def query(self, query_type: str, **params) -> dict:
        """Query the cache."""
        return self._handle_query_command(
            Command(command_type="CMD_QUERY_CACHE",
                    params={"query_type": query_type, "params": params})
        )

    def log(self, message: str):
        """Log a message with worker prefix."""
        print(f"[RepositoryWorker] {message}")

    def get_cache_summary(self) -> str:
        """Get a human-readable cache summary."""
        return self.cache.get_summary()
