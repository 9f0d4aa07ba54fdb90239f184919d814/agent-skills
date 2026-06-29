"""
ENTERPRISE MEMORY — Persistent, searchable knowledge store.
Stores: bugs, fixes, code reviews, architecture decisions, meeting notes,
design documents, and project-specific knowledge.
Retrieves relevant context automatically when needed.
"""

import json, os, re, time, hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
from collections import defaultdict


ENTERPRISE_MEMORY_DIR = Path.home() / ".coding-agent" / "enterprise-memory"


class KnowledgeEntry:
    """A single entry in enterprise memory."""
    def __init__(self, kind: str, title: str, content: str,
                 tags: list[str] = None, source: str = ""):
        self.id = hashlib.md5(f"{kind}:{title}:{time.time()}".encode()).hexdigest()[:12]
        self.kind = kind  # "bug", "fix", "review", "decision", "note", "meeting", "docs"
        self.title = title
        self.content = content
        self.tags = tags or []
        self.source = source
        self.created = datetime.now().isoformat()
        self.access_count = 0
        self.relevance_score = 0.5  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "title": self.title,
            "content": self.content, "tags": self.tags, "source": self.source,
            "created": self.created, "access_count": self.access_count,
            "relevance_score": self.relevance_score,
        }


class EnterpriseMemory:
    """Persistent, searchable knowledge base for the agent.
    
    Automatically stores:
    - Bugs encountered and their fixes
    - Code review outcomes
    - Architecture decisions
    - Project-specific conventions
    - Previous task solutions
    """

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self._project_hash = hashlib.md5(self.workdir.encode()).hexdigest()[:12]
        self._mem_file = ENTERPRISE_MEMORY_DIR / f"{self._project_hash}.json"
        ENTERPRISE_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._entries: list[KnowledgeEntry] = []
        self._load()
        self._build_index()

    # ── Persistence ──

    def _load(self):
        """Load entries from disk."""
        if self._mem_file.exists():
            try:
                data = json.loads(self._mem_file.read_text())
                for entry_data in data.get("entries", []):
                    entry = KnowledgeEntry(
                        entry_data.get("kind", "note"),
                        entry_data.get("title", ""),
                        entry_data.get("content", ""),
                        entry_data.get("tags", []),
                        entry_data.get("source", ""),
                    )
                    entry.id = entry_data.get("id", entry.id)
                    entry.created = entry_data.get("created", entry.created)
                    entry.access_count = entry_data.get("access_count", 0)
                    entry.relevance_score = entry_data.get("relevance_score", 0.5)
                    self._entries.append(entry)
            except:
                self._entries = []

    def _save(self):
        """Persist entries to disk."""
        self._mem_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "project_hash": self._project_hash,
            "total_entries": len(self._entries),
            "entries": [e.to_dict() for e in self._entries],
        }
        self._mem_file.write_text(json.dumps(data, indent=2))

    def _build_index(self):
        """Build a simple keyword index for fast retrieval."""
        self._index: dict[str, list[str]] = defaultdict(list)  # keyword -> [entry_ids]
        for entry in self._entries:
            words = set(re.findall(r'\b[a-zA-Z_]\w{2,}\b', entry.title + " " + entry.content))
            for word in words:
                self._index[word.lower()].append(entry.id)

    # ── Store ──

    def store(self, kind: str, title: str, content: str,
              tags: list[str] = None, source: str = "") -> str:
        """Store a knowledge entry. Returns entry ID."""
        entry = KnowledgeEntry(kind, title, content, tags, source)
        self._entries.append(entry)
        self._rebuild_index()
        self._save()
        return entry.id

    def store_bug_fix(self, bug_title: str, error: str, solution: str,
                      files_changed: list[str] = None) -> str:
        """Convenience: store a bug and its fix."""
        content = f"Error: {error}\nSolution: {solution}\nFiles: {', '.join(files_changed or [])}"
        return self.store("fix", bug_title, content,
                         tags=["bug", "fix"] + (files_changed or []))

    def store_review(self, file_path: str, score: float, findings: list[str]) -> str:
        """Store a code review result."""
        content = f"Score: {score}\nFindings:\n" + "\n".join(f"- {f}" for f in findings)
        return self.store("review", f"Review: {file_path}", content,
                         tags=["review", Path(file_path).suffix.lstrip(".")])

    def store_decision(self, title: str, context: str, decision: str) -> str:
        """Store an architecture decision."""
        content = f"Context: {context}\nDecision: {decision}"
        return self.store("decision", title, content, tags=["decision"])

    # ── Retrieve ──

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeEntry]:
        """Search enterprise memory by keyword relevance."""
        query_words = set(re.findall(r'\b[a-zA-Z_]\w{2,}\b', query.lower()))
        if not query_words or not self._entries:
            return []
        
        scored = []
        for entry in self._entries:
            score = 0.0
            entry_lower = (entry.title + " " + entry.content).lower()
            for word in query_words:
                if word in entry_lower:
                    score += 0.2
                if word in entry.title.lower():
                    score += 0.3  # Title matches are more relevant
                if word in entry.tags:
                    score += 0.4  # Tag matches are most relevant
            
            if score > 0:
                scored.append((-score, entry))
        
        scored.sort()
        results = [entry for _, entry in scored[:top_k]]
        
        # Update access counts
        for entry in results:
            entry.access_count += 1
        self._save()
        
        return results

    def get_by_kind(self, kind: str, limit: int = 10) -> list[KnowledgeEntry]:
        """Get entries by kind."""
        return [e for e in self._entries if e.kind == kind][:limit]

    def get_recent(self, limit: int = 10) -> list[KnowledgeEntry]:
        """Get most recent entries."""
        sorted_entries = sorted(self._entries, key=lambda e: e.created, reverse=True)
        return sorted_entries[:limit]

    def get_by_tag(self, tag: str, limit: int = 10) -> list[KnowledgeEntry]:
        """Get entries by tag."""
        return [e for e in self._entries if tag in e.tags][:limit]

    def get_stats(self) -> dict:
        """Get memory statistics."""
        kinds = defaultdict(int)
        for e in self._entries:
            kinds[e.kind] += 1
        return {
            "total": len(self._entries),
            "by_kind": dict(kinds),
            "top_tags": self._get_top_tags(5),
        }

    def get_context_for_task(self, task: str) -> str:
        """Get relevant context from enterprise memory for a task."""
        results = self.search(task, top_k=5)
        if not results:
            return ""
        
        parts = ["## Enterprise Memory (relevant context)"]
        for entry in results:
            parts.append(f"\n### [{entry.kind.upper()}] {entry.title}")
            parts.append(f"({entry.created[:10]})")
            parts.append(entry.content[:300])
        return "\n".join(parts)

    def _rebuild_index(self):
        """Rebuild the keyword index."""
        self._index = defaultdict(list)
        for entry in self._entries:
            words = set(re.findall(r'\b[a-zA-Z_]\w{2,}\b', entry.title + " " + entry.content))
            for word in words:
                self._index[word.lower()].append(entry.id)

    def _get_top_tags(self, n: int) -> list[tuple[str, int]]:
        """Get the most common tags."""
        tag_counts = defaultdict(int)
        for e in self._entries:
            for tag in e.tags:
                tag_counts[tag] += 1
        return sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:n]
