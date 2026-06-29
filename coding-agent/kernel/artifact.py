"""
ARTIFACT SYSTEM — Everything produces artifacts.

Artifacts are immutable records of work done:
- Repository Scan → Artifact (graph)
- Code Review → Artifact (issues)
- Test Run → Artifact (results)
- LLM Response → Artifact (content)

Nothing is lost. Every artifact is stored and searchable.
"""

import json, time, hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
from enum import Enum


ARTIFACT_DIR = Path.home() / ".coding-agent" / "artifacts"


class ArtifactType(Enum):
    TEXT = "text"
    CODE = "code"
    JSON = "json"
    GRAPH = "graph"
    DIFF = "diff"
    REPORT = "report"
    METRICS = "metrics"
    IMAGE = "image"
    FILE = "file"
    LOG = "log"


class Artifact:
    """An immutable record of work done.
    
    Everything produces artifacts:
    - repository_scan → Artifact(type=GRAPH, name="Dependency Graph")
    - code_review → Artifact(type=REPORT, name="Review Report")
    - test_run → Artifact(type=METRICS, name="Test Results")
    - context_build → Artifact(type=JSON, name="Built Context")
    """

    def __init__(self, name: str, artifact_type: ArtifactType = ArtifactType.TEXT,
                 content: str = "", data: dict = None,
                 source_job: str = "", source_step: str = "",
                 tags: list[str] = None, metadata: dict = None):
        self.id = hashlib.md5(f"{name}:{time.time()}:{id(self)}".encode()).hexdigest()[:12]
        self.name = name
        self.artifact_type = artifact_type
        self.content = content
        self.data = data or {}
        self.source_job = source_job
        self.source_step = source_step
        self.tags = tags or []
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.datetime = datetime.now().isoformat()
        self.size = len(content) + len(json.dumps(data)) if data else len(content)
        self._persisted = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "artifact_type": self.artifact_type.value,
            "content": self.content[:1000],  # Truncate in dict view
            "data": self.data,
            "source_job": self.source_job,
            "source_step": self.source_step,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "datetime": self.datetime,
            "size": self.size,
            "persisted": self._persisted,
        }

    def summary(self, max_length: int = 200) -> str:
        """Short summary of this artifact."""
        type_str = self.artifact_type.value.upper()
        content_preview = self.content[:max_length].replace("\n", " ")[:max_length]
        return f"[{type_str}] {self.name} — {content_preview}"

    def persist(self, directory: Path = None) -> Path:
        """Save this artifact to disk."""
        dir_path = directory or ARTIFACT_DIR / self.source_job[:12]
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{self.id}.json"
        file_path.write_text(json.dumps(self.to_dict(), indent=2))
        # Also save full content separately if needed
        content_path = dir_path / f"{self.id}.content.txt"
        content_path.write_text(self.content)
        self._persisted = True
        return file_path


class ArtifactStore:
    """Stores and retrieves artifacts."""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else ARTIFACT_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Artifact] = {}

    def store(self, artifact: Artifact) -> str:
        """Store an artifact. Returns its ID."""
        self._cache[artifact.id] = artifact
        artifact.persist(self.base_dir)
        return artifact.id

    def get(self, artifact_id: str) -> Optional[Artifact]:
        """Retrieve an artifact by ID."""
        if artifact_id in self._cache:
            return self._cache[artifact_id]
        for file_path in self.base_dir.rglob(f"{artifact_id}.json"):
            try:
                data = json.loads(file_path.read_text())
                artifact = self._from_dict(data)
                self._cache[artifact_id] = artifact
                return artifact
            except:
                pass
        return None

    def get_by_job(self, job_id: str) -> list[Artifact]:
        """Get all artifacts for a job."""
        results = []
        job_dir = self.base_dir / job_id[:12]
        if job_dir.exists():
            for file_path in sorted(job_dir.glob("*.json")):
                try:
                    data = json.loads(file_path.read_text())
                    if data.get("source_job", "")[:12] == job_id[:12]:
                        artifact = self._from_dict(data)
                        self._cache[artifact.id] = artifact
                        results.append(artifact)
                except:
                    pass
        # Also check cache
        for artifact in self._cache.values():
            if artifact.source_job == job_id and artifact not in results:
                results.append(artifact)
        return sorted(results, key=lambda a: a.created_at)

    def search(self, query: str, limit: int = 20) -> list[Artifact]:
        """Search artifacts by name, type, or tags."""
        query_lower = query.lower()
        results = []
        for file_path in self.base_dir.rglob("*.json"):
            try:
                data = json.loads(file_path.read_text())
                if (query_lower in data.get("name", "").lower() or
                    query_lower in str(data.get("tags", [])) or
                    query_lower in data.get("artifact_type", "").lower()):
                    artifact = self._from_dict(data)
                    results.append(artifact)
                    if len(results) >= limit:
                        break
            except:
                pass
        return results

    def get_recent(self, limit: int = 20) -> list[Artifact]:
        """Get most recent artifacts."""
        all_files = []
        for file_path in self.base_dir.rglob("*.json"):
            all_files.append((file_path.stat().st_mtime, file_path))
        all_files.sort(reverse=True)
        results = []
        for _, file_path in all_files[:limit]:
            try:
                data = json.loads(file_path.read_text())
                results.append(self._from_dict(data))
            except:
                pass
        return results

    def _from_dict(self, data: dict) -> Artifact:
        """Reconstruct an Artifact from dict."""
        try:
            atype = ArtifactType(data.get("artifact_type", "text"))
        except:
            atype = ArtifactType.TEXT
        artifact = Artifact(
            name=data.get("name", "unknown"),
            artifact_type=atype,
            content=data.get("content", ""),
            data=data.get("data", {}),
            source_job=data.get("source_job", ""),
            source_step=data.get("source_step", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        artifact.id = data.get("id", artifact.id)
        artifact.created_at = data.get("created_at", artifact.created_at)
        artifact._persisted = True
        # Try to load full content
        content_path = self.base_dir / artifact.source_job[:12] / f"{artifact.id}.content.txt"
        if content_path.exists() and artifact.content == artifact.content[:1000]:
            artifact.content = content_path.read_text()
        return artifact
