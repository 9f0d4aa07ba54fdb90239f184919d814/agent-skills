"""
BUILD CACHE — Build, test, and lint results.

Maintains: per-key build results (success, errors, warnings, duration).
Supports: store, retrieve, status queries.
"""

import os, time
from typing import Optional
from dataclasses import dataclass, field, asdict
from .base import BaseCache


@dataclass
class BuildResult:
    """Result of a build, test, or lint run."""
    file_path: str = ""
    result_type: str = "build"          # build, test, lint, format
    success: bool = True
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    duration: float = 0.0
    timestamp: float = 0.0
    output: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BuildResult":
        return cls(**d)


class BuildCache(BaseCache):
    """Build/test/lint results cache.

    Stores results keyed by file path or build key.
    Enables fast answers to: "Did the build pass?" "What were the test results?"
    """

    def __init__(self, repo_root: str, cache_dir: str):
        super().__init__("build_cache", cache_dir)
        self.repo_root = __import__('os').path.abspath(repo_root)
        self._results: dict[str, BuildResult] = {}
        self.load()

    # ── Persistence ──

    def save(self):
        data = {k: r.to_dict() for k, r in self._results.items()}
        self._save_json({"build_results": data})

    def load(self):
        data = self._load_json()
        self._results = {k: BuildResult.from_dict(r) for k, r in data.get("build_results", {}).items()}

    # ── Indexing ──

    def store(self, key: str, result: BuildResult):
        """Store a build result."""
        self._results[key] = result
        self.mark_dirty()

    def remove(self, key: str):
        """Remove a build result."""
        self._results.pop(key, None)
        self.mark_dirty()

    # ── Queries ──

    def get(self, key: str) -> Optional[BuildResult]:
        """Get a build result by key."""
        return self._results.get(key)

    def get_by_file(self, file_path: str) -> list[tuple[str, BuildResult]]:
        """Get all build results for a file."""
        return [(k, r) for k, r in self._results.items() if r.file_path == file_path]

    def count(self) -> int:
        return len(self._results)

    def successes(self) -> list[BuildResult]:
        return [r for r in self._results.values() if r.success]

    def failures(self) -> list[BuildResult]:
        return [r for r in self._results.values() if not r.success]

    # ── State ──

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "total_results": self.count(),
            "successes": len(self.successes()),
            "failures": len(self.failures()),
        }

    def clear(self):
        self._results.clear()
        self.mark_dirty()
