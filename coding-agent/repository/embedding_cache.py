"""
EMBEDDING CACHE — File embedding vectors for semantic search.

Maintains: file-level embedding vectors.
Supports: store, retrieve, semantic search (cosine similarity).

Event-driven: subscribes to file.changed to regenerate embeddings.
"""

import math
from typing import Optional
from .base import BaseCache


class EmbeddingCache(BaseCache):
    """File embedding vectors for semantic search.

    Enables natural-language queries over the codebase:
      "Find files related to authentication"
      "What modules handle database operations?"
    """

    def __init__(self, repo_root: str, cache_dir: str):
        super().__init__("embedding_cache", cache_dir)
        self.repo_root = __import__('os').path.abspath(repo_root)
        self._embeddings: dict[str, list[float]] = {}  # file path -> embedding
        self.load()

    # ── Persistence ──

    def save(self):
        self._save_json({"embeddings": self._embeddings})

    def load(self):
        data = self._load_json()
        self._embeddings = data.get("embeddings", {})

    # ── Event Subscriptions ──

    def _subscribe_to_events(self):
        self._subscribe("file.changed", self._on_file_changed)
        self._subscribe("file.deleted", self._on_file_deleted)

    def _on_file_changed(self, event):
        rel_path = event.data.get("path", "")
        self._embeddings.pop(rel_path, None)
        self.mark_dirty()

    def _on_file_deleted(self, event):
        rel_path = event.data.get("path", "")
        self._embeddings.pop(rel_path, None)
        self.mark_dirty()

    # ── Indexing ──

    def store(self, rel_path: str, embedding: list[float]):
        """Store an embedding for a file."""
        self._embeddings[rel_path] = embedding
        self.mark_dirty()

    def remove(self, rel_path: str):
        """Remove embedding for a file."""
        self._embeddings.pop(rel_path, None)
        self.mark_dirty()

    # ── Queries ──

    def get(self, rel_path: str) -> Optional[list[float]]:
        """Get embedding for a file."""
        return self._embeddings.get(rel_path)

    def search(self, query_embedding: list[float], top_k: int = 10) -> list[tuple[str, float]]:
        """Find files with similar embeddings (cosine similarity).

        Args:
            query_embedding: Query vector.
            top_k: Max results.

        Returns:
            List of (file_path, similarity) tuples, highest first.
        """
        results: list[tuple[str, float]] = []
        query_norm = math.sqrt(sum(v * v for v in query_embedding))
        if query_norm == 0:
            return []

        for fpath, emb in self._embeddings.items():
            emb_norm = math.sqrt(sum(v * v for v in emb))
            if emb_norm == 0:
                continue
            dot = sum(a * b for a, b in zip(query_embedding, emb))
            similarity = dot / (query_norm * emb_norm)
            results.append((fpath, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def count(self) -> int:
        return len(self._embeddings)

    # ── State ──

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "total_embedded": self.count(),
        }

    def clear(self):
        self._embeddings.clear()
        self.mark_dirty()
