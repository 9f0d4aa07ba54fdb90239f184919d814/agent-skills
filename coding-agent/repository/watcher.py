"""
FILE WATCHER — Watches the filesystem for changes and publishes events.

Instead of scan-then-build, the watcher:
  1. Polls the filesystem at intervals (or uses watchdog if available)
  2. Detects file creations, modifications, deletions
  3. Publishes events: file.created, file.changed, file.deleted
  4. Each cache subscribes and updates only what changed

This means the cache is always hot — no full rescans needed.
"""

import os, time, threading
from pathlib import Path
from typing import Optional, Callable


class FileWatcher:
    """Filesystem watcher that publishes change events.

    Uses polling by default (cross-platform, no extra dependencies).
    Can optionally use watchdog for instant notifications.

    Publishes events:
      - file.created: {path, is_dir}
      - file.changed: {path, is_dir}
      - file.deleted: {path, is_dir}
    """

    def __init__(self, repo_root: str, event_bus=None,
                 poll_interval: float = 2.0, ignore_patterns: list[str] = None):
        self.repo_root = os.path.abspath(repo_root)
        self.event_bus = event_bus
        self.poll_interval = poll_interval
        self._ignore = ignore_patterns or [
            ".git/", "__pycache__/", ".venv/", "venv/", "node_modules/",
            ".agent-cache/", "*.pyc", "*.pyo", ".gitignore",
        ]

        # State for change detection
        self._snapshots: dict[str, tuple[float, int]] = {}  # path -> (mtime, size)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Callbacks (for direct use without event bus)
        self._callbacks: dict[str, list[Callable]] = {
            "created": [], "changed": [], "deleted": [],
        }

    # ── Lifecycle ──

    def start(self):
        """Start the watcher in a background thread."""
        if self._running:
            return
        self._running = True
        self._take_snapshot()  # Initial state
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the watcher."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ── Event Publishing ──

    def on_created(self, callback: Callable):
        """Register callback for file creation events."""
        self._callbacks["created"].append(callback)

    def on_changed(self, callback: Callable):
        """Register callback for file modification events."""
        self._callbacks["changed"].append(callback)

    def on_deleted(self, callback: Callable):
        """Register callback for file deletion events."""
        self._callbacks["deleted"].append(callback)

    def _publish(self, event_type: str, data: dict):
        """Publish event to event bus and callbacks."""
        # Event bus
        if self.event_bus:
            self.event_bus.publish(
                f"file.{event_type}",
                source="file_watcher",
                data=data,
            )
        # Callbacks
        for cb in self._callbacks.get(event_type, []):
            try:
                cb(data)
            except Exception:
                pass

    # ── File Scanning ──

    def _should_ignore(self, rel_path: str) -> bool:
        import fnmatch
        for pattern in self._ignore:
            if pattern.endswith("/"):
                if pattern in rel_path or rel_path.startswith(pattern):
                    return True
            elif fnmatch.fnmatch(rel_path, pattern):
                return True
            elif fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                return True
        return False

    def _list_files(self) -> dict[str, tuple[float, int]]:
        """Get all files with their mtime and size."""
        snapshot = {}
        repo = Path(self.repo_root)
        for f in repo.rglob("*"):
            if not f.is_file():
                continue
            try:
                rel = str(f.relative_to(repo))
            except ValueError:
                continue
            if self._should_ignore(rel):
                continue
            try:
                stat = f.stat()
                snapshot[rel] = (stat.st_mtime, stat.st_size)
            except (IOError, OSError):
                pass
        return snapshot

    def _take_snapshot(self):
        """Take an initial snapshot of all files."""
        with self._lock:
            self._snapshots = self._list_files()

    def _detect_changes(self):
        """Detect file changes since last snapshot."""
        with self._lock:
            old_snapshots = dict(self._snapshots)
            current = self._list_files()
            self._snapshots = current

        old_paths = set(old_snapshots.keys())
        current_paths = set(current.keys())

        # Deleted files
        for path in old_paths - current_paths:
            self._publish("deleted", {"path": path, "is_dir": False})

        # Created files
        for path in current_paths - old_paths:
            self._publish("created", {"path": path, "is_dir": False})

        # Changed files
        for path in current_paths & old_paths:
            old_mtime, old_size = old_snapshots[path]
            cur_mtime, cur_size = current[path]
            if abs(cur_mtime - old_mtime) > 0.01 or cur_size != old_size:
                self._publish("changed", {"path": path, "is_dir": False})

    # ── Polling Loop ──

    def _poll_loop(self):
        """Background loop that periodically checks for changes."""
        while self._running:
            time.sleep(self.poll_interval)
            try:
                self._detect_changes()
            except Exception:
                pass

    # ── Public API ──

    def watch(self):
        """Alias for start()."""
        self.start()

    def unwatch(self):
        """Alias for stop()."""
        self.stop()

    @property
    def is_watching(self) -> bool:
        return self._running
