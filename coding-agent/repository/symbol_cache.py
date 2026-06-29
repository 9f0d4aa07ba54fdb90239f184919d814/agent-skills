"""
SYMBOL CACHE — Index of symbols (functions, classes, variables) in the repository.

Maintains: symbol name, kind, file, line, signature, docstring, context.
Supports: search by name, kind, file, visibility.

Event-driven: subscribes to file.changed to re-index symbols.
"""

import os, time
from typing import Optional
from dataclasses import dataclass, field, asdict
from .base import BaseCache


@dataclass
class SymbolEntry:
    """A symbol defined in the repository."""
    name: str
    kind: str                           # function, class, method, variable, constant
    file_path: str
    line: int = 0
    column: int = 0
    parent: str = ""                    # Parent symbol (e.g., class name)
    signature: str = ""                 # Full signature
    docstring: str = ""                 # Documentation
    context: str = ""                   # Surrounding code (3-5 lines)
    visibility: str = "public"          # public, private, protected
    is_deprecated: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SymbolEntry":
        return cls(**d)


class SymbolCache(BaseCache):
    """Index of symbols across the repository.

    Enables fast answers to:
      "Where is function X defined?"
      "What classes are in module Y?"
      "Find all public functions in the codebase."
    """

    def __init__(self, repo_root: str, cache_dir: str):
        super().__init__("symbol_cache", cache_dir)
        self.repo_root = os.path.abspath(repo_root)
        self._symbols: dict[str, list[SymbolEntry]] = {}  # file -> [SymbolEntry]
        self._by_name: dict[str, list[SymbolEntry]] = {}  # name -> [SymbolEntry]
        self._by_kind: dict[str, list[SymbolEntry]] = {}  # kind -> [SymbolEntry]
        self.load()

    # ── Persistence ──

    def save(self):
        data = {
            "symbols": {f: [s.to_dict() for s in syms] for f, syms in self._symbols.items()},
        }
        self._save_json(data)

    def load(self):
        data = self._load_json()
        self._symbols = {f: [SymbolEntry.from_dict(s) for s in syms]
                        for f, syms in data.get("symbols", {}).items()}
        self._rebuild_indexes()

    def _rebuild_indexes(self):
        self._by_name.clear()
        self._by_kind.clear()
        for fpath, syms in self._symbols.items():
            for sym in syms:
                self._by_name.setdefault(sym.name, []).append(sym)
                self._by_kind.setdefault(sym.kind, []).append(sym)

    # ── Event Subscriptions ──

    def _subscribe_to_events(self):
        self._subscribe("file.changed", self._on_file_changed)
        self._subscribe("file.deleted", self._on_file_deleted)

    def _on_file_changed(self, event):
        # File changed — symbols for that file are stale
        # (re-indexing is done by whoever publishes the event)
        pass

    def _on_file_deleted(self, event):
        rel_path = event.data.get("path", "")
        self._symbols.pop(rel_path, None)
        self._rebuild_indexes()
        self.mark_dirty()

    # ── Indexing ──

    def index_file(self, rel_path: str, symbols: list[SymbolEntry]):
        """Store symbols for a file."""
        # Remove old symbols for this file
        old_syms = self._symbols.pop(rel_path, [])
        self._symbols[rel_path] = symbols
        self._rebuild_indexes()
        self.mark_dirty()

    def remove_file(self, rel_path: str):
        """Remove all symbols for a file."""
        self._symbols.pop(rel_path, None)
        self._rebuild_indexes()
        self.mark_dirty()

    # ── Queries ──

    def find(self, name: str, kind: str = None, file_path: str = None) -> list[SymbolEntry]:
        """Find symbols by name, optionally filtered by kind or file."""
        results = self._by_name.get(name, [])
        if not results:
            # Partial match
            results = [s for s_list in self._symbols.values() for s in s_list if name in s.name]
        if kind:
            results = [s for s in results if s.kind == kind]
        if file_path:
            results = [s for s in results if s.file_path == file_path]
        return results

    def by_kind(self, kind: str) -> list[SymbolEntry]:
        """Find all symbols of a given kind."""
        return list(self._by_kind.get(kind, []))

    def by_file(self, rel_path: str) -> list[SymbolEntry]:
        """Get all symbols defined in a file."""
        return list(self._symbols.get(rel_path, []))

    def search(self, query: str, max_results: int = 20) -> list[SymbolEntry]:
        """Search symbols by name substring."""
        q = query.lower()
        results = []
        for sym_list in self._symbols.values():
            for sym in sym_list:
                if q in sym.name.lower() or q in sym.signature.lower():
                    results.append(sym)
                    if len(results) >= max_results:
                        return results
        return results

    def count(self) -> int:
        return sum(len(s) for s in self._symbols.values())

    def count_by_kind(self) -> dict[str, int]:
        return {k: len(v) for k, v in self._by_kind.items()}

    # ── State ──

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "total_symbols": self.count(),
            "by_kind": self.count_by_kind(),
            "files_with_symbols": len(self._symbols),
        }

    def clear(self):
        self._symbols.clear()
        self._by_name.clear()
        self._by_kind.clear()
        self.mark_dirty()
