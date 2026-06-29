"""
LSP CACHE — LSP/Pylance diagnostics per file.

Maintains: file-level diagnostics (errors, warnings, hints).
Supports: store, query, error/warning counts, filtering by severity.

Event-driven: subscribes to file.changed to clear stale diagnostics.
"""

import os, time
from typing import Optional
from dataclasses import dataclass, asdict
from .base import BaseCache


@dataclass
class DiagnosticEntry:
    """A diagnostic (error, warning, hint) for a file."""
    file_path: str
    line: int = 0
    column: int = 0
    message: str = ""
    severity: str = "error"            # error, warning, information, hint
    code: str = ""
    source: str = "pylance"
    rule: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DiagnosticEntry":
        return cls(**d)


class LspCache(BaseCache):
    """LSP/Pylance diagnostics cache.

    Stores diagnostics per file with severity, code, and message.
    Enables fast answers to:
      "What errors are in the codebase?"
      "How many warnings in module X?"
    """

    def __init__(self, repo_root: str, cache_dir: str):
        super().__init__("lsp_cache", cache_dir)
        self.repo_root = __import__('os').path.abspath(repo_root)
        self._diagnostics: dict[str, list[DiagnosticEntry]] = {}
        self.load()

    # ── Persistence ──

    def save(self):
        data = {f: [d.to_dict() for d in diags] for f, diags in self._diagnostics.items()}
        self._save_json({"diagnostics": data})

    def load(self):
        data = self._load_json()
        self._diagnostics = {f: [DiagnosticEntry.from_dict(d) for d in diags]
                            for f, diags in data.get("diagnostics", {}).items()}

    # ── Event Subscriptions ──

    def _subscribe_to_events(self):
        self._subscribe("file.changed", self._on_file_changed)
        self._subscribe("file.deleted", self._on_file_deleted)

    def _on_file_changed(self, event):
        rel_path = event.data.get("path", "")
        self._diagnostics.pop(rel_path, None)
        self.mark_dirty()

    def _on_file_deleted(self, event):
        rel_path = event.data.get("path", "")
        self._diagnostics.pop(rel_path, None)
        self.mark_dirty()

    # ── Indexing ──

    def store(self, rel_path: str, diagnostics: list[DiagnosticEntry]):
        """Store diagnostics for a file."""
        self._diagnostics[rel_path] = diagnostics
        self.mark_dirty()

    def remove(self, rel_path: str):
        """Remove diagnostics for a file."""
        self._diagnostics.pop(rel_path, None)
        self.mark_dirty()

    # ── Queries ──

    def get(self, rel_path: str = None) -> list[DiagnosticEntry]:
        """Get diagnostics for a file or all files."""
        if rel_path:
            return list(self._diagnostics.get(rel_path, []))
        results = []
        for diags in self._diagnostics.values():
            results.extend(diags)
        return results

    def by_severity(self, severity: str) -> list[DiagnosticEntry]:
        """Filter diagnostics by severity."""
        results = []
        for diags in self._diagnostics.values():
            results.extend(d for d in diags if d.severity == severity)
        return results

    def errors(self) -> list[DiagnosticEntry]:
        return self.by_severity("error")

    def warnings(self) -> list[DiagnosticEntry]:
        return self.by_severity("warning")

    def error_count(self) -> int:
        return len(self.errors())

    def warning_count(self) -> int:
        return len(self.warnings())

    def by_file(self, rel_path: str) -> list[DiagnosticEntry]:
        return list(self._diagnostics.get(rel_path, []))

    def count(self) -> int:
        return sum(len(d) for d in self._diagnostics.values())

    # ── State ──

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "files_with_diagnostics": len(self._diagnostics),
            "total_diagnostics": self.count(),
            "errors": self.error_count(),
            "warnings": self.warning_count(),
        }

    def clear(self):
        self._diagnostics.clear()
        self.mark_dirty()
