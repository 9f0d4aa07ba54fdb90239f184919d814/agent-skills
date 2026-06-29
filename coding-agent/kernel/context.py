"""
IMMUTABLE CONTEXT — Versioned, immutable context snapshots.

Instead of one mutable context that every worker modifies, create
immutable versions. Each worker receives Version N and produces
Version N+1. Every decision is reproducible.

  Context V1 → Planner → Context V2 → Executor → Context V3 → ...
"""

from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
import hashlib, json, time


@dataclass
class ContextSnapshot:
    """An immutable snapshot of context at a point in time."""
    version: int
    created_by: str  # Worker that created this version
    data: dict = field(default_factory=dict)
    parent_version: Optional[int] = None
    created_at: float = 0.0
    hash: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute a content hash for this snapshot."""
        content = json.dumps(self.data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, key: str, default=None):
        """Get a value from context data."""
        return self.data.get(key, default)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "created_by": self.created_by,
            "data": self.data,
            "parent_version": self.parent_version,
            "created_at": self.created_at,
            "hash": self.hash,
        }

    def summary(self) -> str:
        """Short summary of this context version."""
        return f"Context V{self.version} by {self.created_by} [{self.hash[:8]}]"


class VersionedContext:
    """Immutable, versioned context that grows through the pipeline.
    
    Each worker receives a snapshot and produces a new snapshot.
    The full history is preserved for reproducibility.
    """

    def __init__(self, initial_data: dict = None):
        self._snapshots: list[ContextSnapshot] = []
        self._max_versions = 100
        if initial_data:
            self.create_snapshot("system", initial_data)

    @property
    def latest(self) -> Optional[ContextSnapshot]:
        """Get the latest context snapshot."""
        return self._snapshots[-1] if self._snapshots else None

    @property
    def version_count(self) -> int:
        return len(self._snapshots)

    @property
    def current_version(self) -> int:
        return len(self._snapshots)

    def create_snapshot(self, created_by: str, data: dict = None) -> ContextSnapshot:
        """Create a new immutable snapshot. Returns it."""
        parent = self._snapshots[-1] if self._snapshots else None
        merged_data = {}
        
        # Start with parent data
        if parent:
            merged_data.update(parent.data)
        
        # Apply new data
        if data:
            merged_data.update(data)
        
        version = len(self._snapshots) + 1
        snapshot = ContextSnapshot(
            version=version,
            created_by=created_by,
            data=merged_data,
            parent_version=parent.version if parent else None,
        )
        self._snapshots.append(snapshot)
        
        if len(self._snapshots) > self._max_versions:
            self._snapshots.pop(0)
        
        return snapshot

    def get_snapshot(self, version: int) -> Optional[ContextSnapshot]:
        """Get a specific version."""
        for s in self._snapshots:
            if s.version == version:
                return s
        return None

    def get_history(self) -> list[ContextSnapshot]:
        """Get all snapshots in order."""
        return list(self._snapshots)

    def get_diff(self, from_version: int, to_version: int) -> dict:
        """Get the difference between two context versions.
        
        Returns keys that were added, removed, or changed.
        """
        from_snap = self.get_snapshot(from_version)
        to_snap = self.get_snapshot(to_version)
        
        if not from_snap or not to_snap:
            return {}
        
        from_data = from_snap.data
        to_data = to_snap.data
        
        added = {k: v for k, v in to_data.items() if k not in from_data}
        removed = {k: v for k, v in from_data.items() if k not in to_data}
        changed = {k: {"from": from_data[k], "to": to_data[k]}
                  for k in from_data if k in to_data and from_data[k] != to_data[k]}
        
        return {
            "from_version": from_version,
            "to_version": to_version,
            "added": added,
            "removed": removed,
            "changed": changed,
            "hash_from": from_snap.hash,
            "hash_to": to_snap.hash,
        }

    def to_dict(self) -> dict:
        return {
            "version_count": self.version_count,
            "latest_version": self.latest.to_dict() if self.latest else None,
            "versions": [s.to_dict() for s in self._snapshots[-5:]],  # Last 5 only
        }
