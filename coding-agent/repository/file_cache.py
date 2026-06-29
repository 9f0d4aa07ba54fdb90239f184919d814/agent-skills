"""
FILE CACHE — File metadata index.

Maintains: path, size, modified_time, content_hash, language.
Supports: full scan, incremental refresh, language-based queries.

Event-driven: subscribes to file.changed, file.created, file.deleted.
"""

import os, time, hashlib, fnmatch
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from .base import BaseCache


@dataclass
class FileEntry:
    """Metadata about a file in the repository."""
    path: str
    size: int = 0
    modified_time: float = 0.0
    content_hash: str = ""
    language: str = ""
    last_indexed: float = 0.0
    error: str = ""

    def is_stale(self, current_mtime: float) -> bool:
        return abs(self.modified_time - current_mtime) > 0.01

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FileEntry":
        return cls(**d)


LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript-react", ".tsx": "typescript-react",
    ".java": "java", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".php": "php", ".c": "c", ".cpp": "cpp", ".h": "c-header",
    ".hpp": "cpp-header", ".cs": "csharp", ".swift": "swift",
    ".kt": "kotlin", ".scala": "scala",
    ".sh": "shell", ".bash": "shell", ".ps1": "powershell",
    ".md": "markdown", ".html": "html", ".css": "css",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".xml": "xml", ".toml": "toml", ".sql": "sql",
    ".txt": "text", ".env": "dotenv",
}


class FileCache(BaseCache):
    """Index of file metadata in the repository.

    Tracks every file: path, size, mtime, content hash, language.
    Enables fast answers to: "Which files changed?" "What's in this directory?"
    """

    def __init__(self, repo_root: str, cache_dir: str,
                 ignore_patterns: list[str] = None):
        super().__init__("file_cache", cache_dir)
        self.repo_root = os.path.abspath(repo_root)
        self._files: dict[str, FileEntry] = {}  # rel_path -> FileEntry
        self._ignore: list[str] = ignore_patterns or [
            ".git/", "__pycache__/", ".venv/", "venv/", "node_modules/",
            ".agent-cache/", "*.pyc", "*.pyo", ".env", ".gitignore",
        ]
        self.load()

    # ── Persistence ──

    def save(self):
        data = {p: e.to_dict() for p, e in self._files.items()}
        self._save_json({"files": data, "version": 1})

    def load(self):
        data = self._load_json()
        self._files = {p: FileEntry.from_dict(e) for p, e in data.get("files", {}).items()}

    # ── Event Subscriptions ──

    def _subscribe_to_events(self):
        self._subscribe("file.changed", self._on_file_changed)
        self._subscribe("file.created", self._on_file_created)
        self._subscribe("file.deleted", self._on_file_deleted)

    def _on_file_changed(self, event):
        rel_path = event.data.get("path", "")
        self.index_file(rel_path)

    def _on_file_created(self, event):
        rel_path = event.data.get("path", "")
        self.index_file(rel_path)

    def _on_file_deleted(self, event):
        rel_path = event.data.get("path", "")
        self._files.pop(rel_path, None)
        self.mark_dirty()

    # ── Ignore Patterns ──

    def _should_ignore(self, rel_path: str) -> bool:
        for pattern in self._ignore:
            if pattern.endswith("/"):
                if pattern in rel_path or rel_path.startswith(pattern):
                    return True
            elif fnmatch.fnmatch(rel_path, pattern):
                return True
            elif fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                return True
        return False

    # ── File Discovery ──

    def _list_files(self) -> list[str]:
        """Walk repo and return relative paths of all files."""
        results = []
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
            results.append(rel)
        return sorted(results)

    def _detect_language(self, filepath: str) -> str:
        ext = os.path.splitext(filepath)[1].lower()
        return LANGUAGE_MAP.get(ext, "unknown")

    def _hash_file(self, abs_path: str) -> str:
        try:
            with open(abs_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:32]
        except (IOError, OSError):
            return ""

    # ── Indexing ──

    def index_file(self, rel_path: str) -> Optional[FileEntry]:
        """Index a single file. Returns FileEntry or None."""
        abs_path = os.path.join(self.repo_root, rel_path)
        if not os.path.isfile(abs_path) or self._should_ignore(rel_path):
            return None
        try:
            stat = os.stat(abs_path)
            content_hash = self._hash_file(abs_path)
            existing = self._files.get(rel_path)
            if existing and not existing.is_stale(stat.st_mtime) and existing.content_hash == content_hash:
                existing.last_indexed = time.time()
                return existing
            entry = FileEntry(
                path=rel_path, size=stat.st_size,
                modified_time=stat.st_mtime, content_hash=content_hash,
                language=self._detect_language(rel_path),
                last_indexed=time.time(),
            )
            self._files[rel_path] = entry
            self.mark_dirty()
            return entry
        except (IOError, OSError) as e:
            self._files[rel_path] = FileEntry(path=rel_path, error=str(e), last_indexed=time.time())
            return None

    def index_all(self) -> int:
        """Index all files. Returns count."""
        count = 0
        for rel_path in self._list_files():
            if self.index_file(rel_path):
                count += 1
        return count

    def refresh(self) -> int:
        """Incremental refresh — only re-index changed/new files."""
        count = 0
        for rel_path, entry in list(self._files.items()):
            abs_path = os.path.join(self.repo_root, rel_path)
            if not os.path.isfile(abs_path):
                del self._files[rel_path]
                self.mark_dirty()
                continue
            if entry.is_stale(os.stat(abs_path).st_mtime):
                if self.index_file(rel_path):
                    count += 1
        indexed = set(self._files.keys())
        for rel_path in self._list_files():
            if rel_path not in indexed:
                if self.index_file(rel_path):
                    count += 1
        return count

    # ── Queries ──

    def get(self, rel_path: str) -> Optional[FileEntry]:
        return self._files.get(rel_path)

    def find(self, pattern: str = None, language: str = None) -> list[FileEntry]:
        results = []
        for entry in self._files.values():
            if pattern and not fnmatch.fnmatch(entry.path, pattern):
                continue
            if language and entry.language != language:
                continue
            results.append(entry)
        return results

    def all_paths(self) -> list[str]:
        return list(self._files.keys())

    def count(self) -> int:
        return len(self._files)

    def by_language(self, language: str) -> list[FileEntry]:
        return [e for e in self._files.values() if e.language == language]

    def get_changed_since(self, timestamp: float) -> list[FileEntry]:
        return [e for e in self._files.values() if e.modified_time > timestamp]

    # ── State ──

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "total_files": self.count(),
            "languages": list(set(e.language for e in self._files.values())),
        }

    def clear(self):
        self._files.clear()
        self.mark_dirty()
