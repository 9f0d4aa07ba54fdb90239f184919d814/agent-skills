"""
REPOSITORY — Specialized caches for repository intelligence.

Split into independent caches, each updating independently:
  - FileCache: file metadata (path, size, mtime, hash, language)
  - SymbolCache: symbols (functions, classes, variables)
  - DependencyCache: imports, dependency graph, affected files
  - EmbeddingCache: file embeddings for semantic search
  - GitCache: git status, branch, commit, changes
  - LspCache: LSP/Pylance diagnostics per file
  - BuildCache: build/test/lint results

Event-driven: FileWatcher publishes file.created/changed/deleted events.
Each cache subscribes and updates only what changed — no full rescans.
"""

import os

from .base import BaseCache
from .file_cache import FileCache, FileEntry, LANGUAGE_MAP
from .symbol_cache import SymbolCache, SymbolEntry
from .dependency_cache import DependencyCache, ImportRelation
from .embedding_cache import EmbeddingCache
from .git_cache import GitCache, GitStatus
from .lsp_cache import LspCache, DiagnosticEntry
from .build_cache import BuildCache, BuildResult
from .watcher import FileWatcher

# Knowledge Graph + Intelligence (new generation)
from .kg_types import (
    NodeType, RelationType,
    KGNode, KGRelation, KGPath, KGAnalysis,
)
from .knowledge_graph import KnowledgeGraph
from .indexer import Indexer, PythonASTWalker, GenericParser
from .intelligence import RepositoryIntelligence
from .retriever import Retriever, QueryResult


class RepositoryCache:
    """Composite facade over all specialized caches.

    Coordinates initialization, persistence, and top-level queries.
    Each specialized cache operates independently and can be
    used directly for fine-grained access.
    """

    def __init__(self, repo_root: str, cache_dir: str = None):
        self.repo_root = os.path.abspath(repo_root)
        self.cache_dir = cache_dir or os.path.join(self.repo_root, ".agent-cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        # Specialized caches
        self.files = FileCache(self.repo_root, self.cache_dir)
        self.symbols = SymbolCache(self.repo_root, self.cache_dir)
        self.dependencies = DependencyCache(self.repo_root, self.cache_dir)
        self.embeddings = EmbeddingCache(self.repo_root, self.cache_dir)
        self.git = GitCache(self.repo_root, self.cache_dir)
        self.lsp = LspCache(self.repo_root, self.cache_dir)
        self.build = BuildCache(self.repo_root, self.cache_dir)

        # File watcher (for event-driven updates)
        self.watcher = FileWatcher(self.repo_root)

        # Knowledge Graph + Intelligence (new generation)
        self.kg = KnowledgeGraph(self.repo_root, self.cache_dir)
        self.indexer = Indexer(self.kg)
        self.intelligence = RepositoryIntelligence(self.repo_root, self.cache_dir)
        self.retriever = Retriever(self.intelligence, self.files, self.symbols)

        # State
        self._initialized = False

    # ── Initialization ──

    def initialize(self, event_bus=None):
        """Initialize caches and start file watcher.

        Args:
            event_bus: If provided, all caches subscribe to file events.
        """
        if self._initialized:
            return

        # Connect caches to event bus for event-driven updates
        if event_bus:
            self.files.connect_event_bus(event_bus)
            self.symbols.connect_event_bus(event_bus)
            self.dependencies.connect_event_bus(event_bus)
            self.embeddings.connect_event_bus(event_bus)
            self.git.connect_event_bus(event_bus)
            self.lsp.connect_event_bus(event_bus)
            self.build.connect_event_bus(event_bus)
            self.watcher.event_bus = event_bus

        # Start file watcher
        self.watcher.start()

        # Initialize intelligence layer
        self.intelligence.initialize(self.files, self.symbols, self.dependencies)

        # Wire retriever to the same caches
        self.retriever = Retriever(self.intelligence, self.files, self.symbols)

        self._initialized = True

        # Do initial scan if empty
        if self.files.count() == 0:
            self.scan()

    def shutdown(self):
        """Stop watcher and save all caches."""
        self.watcher.stop()
        self.kg.save()
        self.save_all()

    def save_all(self):
        """Save all caches to disk."""
        self.files.save_if_dirty()
        self.symbols.save_if_dirty()
        self.dependencies.save_if_dirty()
        self.embeddings.save_if_dirty()
        self.git.save_if_dirty()
        self.lsp.save_if_dirty()
        self.build.save_if_dirty()
        self.kg.save_if_dirty()

    # ─── Scanning ──

    def scan(self) -> int:
        """Full repository scan. Returns file count."""
        count = self.files.index_all()
        return count

    def refresh(self) -> int:
        """Incremental refresh of changed files."""
        return self.files.refresh()

    # ── Query Delegation ──

    def find_files(self, pattern: str = None, language: str = None):
        return self.files.find(pattern, language)

    def find_symbol(self, name: str, kind: str = None, file_path: str = None):
        return self.symbols.find(name, kind, file_path)

    def get_imports(self, rel_path: str):
        return self.dependencies.get_imports(rel_path)

    def get_imported_by(self, rel_path: str):
        return self.dependencies.get_imported_by(rel_path)

    def get_dependents(self, rel_path: str):
        return self.dependencies.get_dependents(rel_path)

    def get_affected_files(self, changed_files: list[str]):
        return self.dependencies.get_affected_files(changed_files)

    def semantic_search(self, query_embedding: list[float], top_k: int = 10):
        return self.embeddings.search(query_embedding, top_k)

    # ── Knowledge Graph + Intelligence Queries ──

    def query(self, query_text: str, query_type: str = "auto",
              params: dict = None) -> "QueryResult":
        """Query repository intelligence using the retriever.

        This is the preferred way for workers to interact with the codebase.

        Args:
            query_text: Natural language query.
            query_type: Type of query ('auto', 'entity', 'flow', 'impact',
                       'architecture', 'search', 'context', 'code',
                       'symbols', 'health', 'custom').
            params: Additional parameters.

        Returns:
            QueryResult with matched entities and metadata.
        """
        return self.retriever.query(query_text, query_type, params or {})

    def index_file(self, file_path: str) -> dict:
        """Index a file into the knowledge graph.

        Args:
            file_path: Path to the file to index.

        Returns:
            Dict with indexing stats.
        """
        return self.intelligence.index_file(file_path)

    def index_all_code(self) -> dict:
        """Index all discoverable code files into the knowledge graph.

        Returns:
            Dict with overall indexing stats.
        """
        return self.intelligence.index_all()

    def what_breaks(self, target: str) -> KGAnalysis:
        """Impact analysis: what breaks if I modify this entity?"""
        return self.intelligence.what_breaks(target)

    def trace_flow(self, target: str, flow_type: str = "call") -> KGAnalysis:
        """Trace a call or data flow through the codebase."""
        return self.intelligence.trace_flow(target, flow_type)

    def build_context(self, task: str, task_files: list[str] = None,
                      max_nodes: int = 50) -> dict:
        """Build rich context for a worker task."""
        return self.intelligence.build_context(task, task_files, max_nodes)

    # ── Statistics ──

    def get_statistics(self) -> dict:
        """Get aggregated cache statistics."""
        stats = {}
        for cache in [self.files, self.symbols, self.dependencies,
                      self.embeddings, self.git, self.lsp, self.build]:
            s = cache.get_stats()
            stats[s["name"]] = s
        stats["repo_root"] = self.repo_root
        stats["cache_dir"] = self.cache_dir
        stats["watcher_running"] = self.watcher.is_watching

        # Add intelligence stats
        intel_stats = self.intelligence.get_stats()
        stats["knowledge_graph"] = intel_stats.get("knowledge_graph", {})
        stats["intelligence_stats"] = {
            "queries_served": intel_stats.get("queries_served", 0),
            "contexts_built": intel_stats.get("contexts_built", 0),
        }
        retriever_stats = self.retriever.get_stats()
        stats["retriever_stats"] = retriever_stats

        return stats

    def get_summary(self) -> str:
        """Human-readable summary."""
        s = self.get_statistics()
        kg = s.get("knowledge_graph", {})
        lines = [
            "📦 Repository Cache + Intelligence Summary",
            f"  📁 Files: {s.get('file_cache', {}).get('total_files', 0)}",
            f"  🔣 Symbols: {s.get('symbol_cache', {}).get('total_symbols', 0)}",
            f"  🔗 Dependencies: {s.get('dependency_cache', {}).get('files_with_dependencies', 0)}",
            f"  🩺 Diagnostics: {s.get('lsp_cache', {}).get('total_diagnostics', 0)} "
                f"({s.get('lsp_cache', {}).get('errors', 0)} errors, "
                f"{s.get('lsp_cache', {}).get('warnings', 0)} warnings)",
            f"  🧠 Embedded: {s.get('embedding_cache', {}).get('total_embedded', 0)}",
            f"  🏗️  Build: {s.get('build_cache', {}).get('total_results', 0)}",
            f"  🌿 Git: {s.get('git_cache', {}).get('branch', '?')} "
                f"({'dirty' if s.get('git_cache', {}).get('dirty') else 'clean'})",
            f"  👀 Watcher: {'running' if s.get('watcher_running') else 'stopped'}",
            f"  🧠 Knowledge Graph: {kg.get('total_nodes', 0)} nodes, "
                f"{kg.get('total_relations', 0)} relations",
            f"  🔎 Intelligence Queries: {s.get('intelligence_stats', {}).get('queries_served', 0)}",
        ]
        return "\n".join(lines)

    def clear(self):
        """Clear all caches."""
        self.files.clear()
        self.symbols.clear()
        self.dependencies.clear()
        self.embeddings.clear()
        self.git.clear()
        self.lsp.clear()
        self.build.clear()
        self.kg.clear()


__all__ = [
    "BaseCache",
    "FileCache", "FileEntry", "LANGUAGE_MAP",
    "SymbolCache", "SymbolEntry",
    "DependencyCache", "ImportRelation",
    "EmbeddingCache",
    "GitCache", "GitStatus",
    "LspCache", "DiagnosticEntry",
    "BuildCache", "BuildResult",
    "FileWatcher",
    "RepositoryCache",
    # Knowledge Graph + Intelligence
    "NodeType", "RelationType",
    "KGNode", "KGRelation", "KGPath", "KGAnalysis",
    "KnowledgeGraph",
    "Indexer", "PythonASTWalker", "GenericParser",
    "RepositoryIntelligence",
    "Retriever", "QueryResult",
]
