"""
DEPENDENCY CACHE — Import graph and dependency relationships.

Maintains: import relations, reverse import index, dependency graph.
Supports: get_imports, get_imported_by, get_dependencies, get_dependents,
          get_affected_files (transitive traversal).

Event-driven: subscribes to file.changed to rebuild dependency edges.
"""

import os
from typing import Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
from .base import BaseCache


@dataclass
class ImportRelation:
    """A relationship between two files via imports."""
    source_file: str
    target_module: str
    target_file: str = ""
    import_type: str = "local"         # local, third_party, stdlib, dynamic
    import_statement: str = ""
    is_type_only: bool = False
    line: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ImportRelation":
        return cls(**d)


class DependencyCache(BaseCache):
    """Import graph and dependency relationships.

    Tracks:
      - What each file imports
      - What imports each file
      - Transitive dependency chains
      - Affected-file analysis for change impact
    """

    def __init__(self, repo_root: str, cache_dir: str):
        super().__init__("dependency_cache", cache_dir)
        self.repo_root = os.path.abspath(repo_root)
        self._imports: dict[str, list[ImportRelation]] = {}  # file -> imports
        self._imported_by: dict[str, list[str]] = defaultdict(list)  # file -> importers
        self._dependencies: dict[str, list[str]] = {}  # file -> dependency files
        self._dependents: dict[str, list[str]] = {}  # file -> dependent files
        self.load()

    # ── Persistence ──

    def save(self):
        data = {
            "imports": {f: [i.to_dict() for i in imps] for f, imps in self._imports.items()},
            "dependencies": self._dependencies,
            "dependents": self._dependents,
        }
        self._save_json(data)

    def load(self):
        data = self._load_json()
        self._imports = {f: [ImportRelation.from_dict(i) for i in imps]
                        for f, imps in data.get("imports", {}).items()}
        self._dependencies = data.get("dependencies", {})
        self._dependents = data.get("dependents", {})
        self._rebuild_imported_by()

    def _rebuild_imported_by(self):
        self._imported_by.clear()
        for fpath, imps in self._imports.items():
            for imp in imps:
                if imp.target_file:
                    self._imported_by[imp.target_file].append(fpath)

    # ── Event Subscriptions ──

    def _subscribe_to_events(self):
        self._subscribe("file.changed", self._on_file_changed)
        self._subscribe("file.deleted", self._on_file_deleted)

    def _on_file_changed(self, event):
        rel_path = event.data.get("path", "")
        # Mark imports for this file as stale
        self._imports.pop(rel_path, None)

    def _on_file_deleted(self, event):
        rel_path = event.data.get("path", "")
        self._imports.pop(rel_path, None)
        self._dependencies.pop(rel_path, None)
        self._dependents.pop(rel_path, None)
        self._rebuild_imported_by()
        self.mark_dirty()

    # ── Indexing ──

    def index_imports(self, rel_path: str, imports: list[ImportRelation]):
        """Store import relations for a file."""
        self._imports[rel_path] = imports
        self._rebuild_imported_by()
        self._build_dependency_graph()
        self.mark_dirty()

    def remove_file(self, rel_path: str):
        """Remove a file from the import graph."""
        self._imports.pop(rel_path, None)
        self._dependencies.pop(rel_path, None)
        self._dependents.pop(rel_path, None)
        self._rebuild_imported_by()
        self.mark_dirty()

    def _build_dependency_graph(self):
        """Build dependency graph from import data."""
        deps: dict[str, set[str]] = {}
        for fpath, imps in self._imports.items():
            deps.setdefault(fpath, set())
            for imp in imps:
                if imp.target_file:
                    deps[fpath].add(imp.target_file)
        self._dependencies = {k: sorted(v) for k, v in deps.items()}
        # Build reverse
        self._dependents = {}
        for fpath, dep_list in self._dependencies.items():
            for dep in dep_list:
                self._dependents.setdefault(dep, []).append(fpath)

    # ── Queries ──

    def get_imports(self, rel_path: str) -> list[ImportRelation]:
        """Get all imports in a file."""
        return list(self._imports.get(rel_path, []))

    def get_imported_by(self, rel_path: str) -> list[str]:
        """Get all files that import this file."""
        return list(self._imported_by.get(rel_path, []))

    def get_dependencies(self, rel_path: str) -> list[str]:
        """Get files that this file depends on."""
        return list(self._dependencies.get(rel_path, []))

    def get_dependents(self, rel_path: str) -> list[str]:
        """Get files that depend on this file."""
        return list(self._dependents.get(rel_path, []))

    def get_affected_files(self, changed_files: list[str]) -> set[str]:
        """Get all files transitively affected by changes."""
        affected = set(changed_files)
        queue = list(changed_files)
        while queue:
            f = queue.pop(0)
            for dependent in self.get_dependents(f):
                if dependent not in affected:
                    affected.add(dependent)
                    queue.append(dependent)
        return affected

    def find_usage(self, module_name: str) -> list[dict]:
        """Find all files that import a given module."""
        results = []
        for fpath, imps in self._imports.items():
            for imp in imps:
                if module_name in imp.target_module:
                    results.append({
                        "file": fpath, "line": imp.line,
                        "statement": imp.import_statement,
                    })
        return results

    # ── State ──

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "files_with_imports": len(self._imports),
            "total_import_relations": sum(len(i) for i in self._imports.values()),
            "files_with_dependencies": len(self._dependencies),
        }

    def clear(self):
        self._imports.clear()
        self._imported_by.clear()
        self._dependencies.clear()
        self._dependents.clear()
        self.mark_dirty()
