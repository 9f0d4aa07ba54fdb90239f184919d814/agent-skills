"""
GIT CACHE — Git status snapshot.

Maintains: branch, commit hash, commit message, file status (modified/added/deleted/renamed/untracked).
Supports: status queries, diff tracking, dirty check.

Event-driven: subscribes to file.changed/deleted/created to update git status.
"""

import os, subprocess
from typing import Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict
from .base import BaseCache


@dataclass
class GitStatus:
    """Current git status snapshot."""
    branch: str = ""
    commit_hash: str = ""
    commit_message: str = ""
    modified_files: list[str] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    renamed_files: list[tuple[str, str]] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    total_commits: int = 0
    last_commit_time: float = 0.0
    is_dirty: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["renamed_files"] = [(a, b) for a, b in self.renamed_files]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "GitStatus":
        renamed = [tuple(r) if isinstance(r, list) else r for r in d.get("renamed_files", [])]
        d["renamed_files"] = renamed
        return cls(**d)


class GitCache(BaseCache):
    """Git status cache.

    Tracks current branch, commit, and file-level changes.
    Enables fast answers to: "What changed?" "Which branch are we on?"
    """

    def __init__(self, repo_root: str, cache_dir: str):
        super().__init__("git_cache", cache_dir)
        self.repo_root = os.path.abspath(repo_root)
        self._status: GitStatus = GitStatus()
        self.load()

    # ── Persistence ──

    def save(self):
        self._save_json({"git": self._status.to_dict()})

    def load(self):
        data = self._load_json()
        self._status = GitStatus.from_dict(data.get("git", {}))

    # ── Event Subscriptions ──

    def _subscribe_to_events(self):
        self._subscribe("file.changed", lambda e: self.refresh())
        self._subscribe("file.created", lambda e: self.refresh())
        self._subscribe("file.deleted", lambda e: self.refresh())

    # ── Git Operations ──

    def refresh(self):
        """Update git status snapshot by running git commands."""
        try:
            repo = Path(self.repo_root)

            # Branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, cwd=repo, timeout=10
            )
            branch = result.stdout.strip() if result.returncode == 0 else ""

            # Commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=repo, timeout=10
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else ""

            # Commit message
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                capture_output=True, text=True, cwd=repo, timeout=10
            )
            commit_message = result.stdout.strip() if result.returncode == 0 else ""

            # Total commits
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, cwd=repo, timeout=10
            )
            total_commits = int(result.stdout.strip()) if result.returncode == 0 else 0

            # Last commit time
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct"],
                capture_output=True, text=True, cwd=repo, timeout=10
            )
            last_commit_time = float(result.stdout.strip()) if result.returncode == 0 else 0.0

            # Status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=repo, timeout=10
            )
            modified, added, deleted, untracked = [], [], [], []
            renamed = []
            is_dirty = bool(result.stdout.strip())

            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                status = line[:2]
                filepath = line[3:]
                if status in ("M ", " M"):
                    modified.append(filepath)
                elif status == "A ":
                    added.append(filepath)
                elif status == "D ":
                    deleted.append(filepath)
                elif status in ("R ", "R"):
                    parts = filepath.split(" -> ")
                    if len(parts) == 2:
                        renamed.append((parts[0], parts[1]))
                elif status in ("??", " ?"):
                    untracked.append(filepath)

            self._status = GitStatus(
                branch=branch, commit_hash=commit_hash,
                commit_message=commit_message,
                modified_files=modified, added_files=added,
                deleted_files=deleted, renamed_files=renamed,
                untracked_files=untracked,
                total_commits=total_commits,
                last_commit_time=last_commit_time,
                is_dirty=is_dirty,
            )
            self.mark_dirty()
        except (subprocess.TimeoutExpired, FileNotFoundError,
                subprocess.CalledProcessError):
            pass

    # ── Queries ──

    @property
    def status(self) -> GitStatus:
        return self._status

    @property
    def is_dirty(self) -> bool:
        return self._status.is_dirty

    @property
    def branch(self) -> str:
        return self._status.branch

    @property
    def commit_hash(self) -> str:
        return self._status.commit_hash

    def get_changed_files(self) -> list[str]:
        """Get all files that have changed (modified + added + deleted)."""
        return (self._status.modified_files + self._status.added_files
                + self._status.deleted_files)

    def count_changes(self) -> int:
        return len(self._status.modified_files) + len(self._status.added_files) \
               + len(self._status.deleted_files) + len(self._status.renamed_files) \
               + len(self._status.untracked_files)

    # ── State ──

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "branch": self._status.branch,
            "dirty": self._status.is_dirty,
            "changes": self.count_changes(),
        }

    def clear(self):
        self._status = GitStatus()
        self.mark_dirty()
