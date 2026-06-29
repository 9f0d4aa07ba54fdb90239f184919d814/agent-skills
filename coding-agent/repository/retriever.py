"""
RETRIEVER — The retrieval engine that workers query instead of raw file access.

Architecture:
  Planner → Retriever → Knowledge Graph → Repository Cache → Context Builder → Worker

The Retriever provides:
  1. Structured queries ("Find login flow", "Find all API routes", "Find callers of X")
  2. Result ranking and filtering
  3. Integration with Knowledge Graph (semantic) and specialized caches (raw data)
  4. Query planning (breaking complex queries into sub-queries)
  5. Context assembly for worker consumption

Workers NEVER grep or read files directly. They ask the Retriever.
This isolates the worker from filesystem concerns and provides a semantic layer.
"""

import os, re, time
from typing import Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .kg_types import (
    NodeType, RelationType,
    KGNode, KGRelation,
)
from .knowledge_graph import KnowledgeGraph
from .intelligence import RepositoryIntelligence

# We import caches for direct file/symbol lookups when KG is insufficient
from .file_cache import FileCache
from .symbol_cache import SymbolCache


@dataclass
class QueryResult:
    """Result of a retrieval query."""
    query: str
    query_type: str
    results: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    execution_time_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    def is_empty(self) -> bool:
        return len(self.results) == 0

    def first(self) -> Optional[dict]:
        return self.results[0] if self.results else None


class Retriever:
    """Retrieval engine for worker queries.

    Workers interact with the codebase through this class.
    It combines Knowledge Graph understanding with cache lookups.

    Query types:
      - entity: Find entities by name/type
      - flow: Trace a call or data flow
      - impact: Impact analysis
      - architecture: Module/package structure
      - search: Full-text search through caches
      - context: Build rich context for a task
      - code: Get file contents with context
      - symbols: Find symbol definitions/usages
      - health: Module health assessment
      - custom: Composed query
    """

    def __init__(self, intelligence: RepositoryIntelligence,
                 file_cache: FileCache = None,
                 symbol_cache: SymbolCache = None):
        self.intel = intelligence
        self.kg = intelligence.kg
        self.files = file_cache or intelligence.files
        self.symbols = symbol_cache or intelligence.symbols

        self._stats = {
            "queries_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_time_ms": 0,
        }

    # ── Public API ──

    def query(self, query_text: str, query_type: str = "auto",
              params: dict = None) -> QueryResult:
        """Execute a retrieval query.

        This is the main entry point for workers.

        Args:
            query_text: Natural language query or entity name.
            query_type: Type of query ('auto', 'entity', 'flow', 'impact',
                       'architecture', 'search', 'context', 'code', 'symbols',
                       'health', 'custom').
            params: Additional parameters (file_path, limit, filters, etc.).

        Returns:
            QueryResult with matched entities and metadata.
        """
        start = time.time()
        self._stats["queries_executed"] += 1
        params = params or {}

        # Auto-detect query type if not specified
        if query_type == "auto":
            query_type = self._detect_query_type(query_text)

        try:
            result = self._dispatch(query_type, query_text, params)
        except Exception as e:
            result = QueryResult(
                query=query_text,
                query_type=query_type,
                error=str(e),
            )

        result.execution_time_ms = (time.time() - start) * 1000
        self._stats["total_time_ms"] += result.execution_time_ms
        return result

    def _dispatch(self, query_type: str, query_text: str,
                  params: dict) -> QueryResult:
        """Dispatch to the appropriate handler."""
        handlers = {
            "entity": self._query_entity,
            "flow": self._query_flow,
            "impact": self._query_impact,
            "architecture": self._query_architecture,
            "search": self._query_search,
            "context": self._query_context,
            "code": self._query_code,
            "symbols": self._query_symbols,
            "health": self._query_health,
            "custom": self._query_custom,
        }

        handler = handlers.get(query_type)
        if not handler:
            return QueryResult(query_text, query_type,
                               error=f"Unknown query type: {query_type}")

        return handler(query_text, params)

    def _detect_query_type(self, query_text: str) -> str:
        """Auto-detect query type from natural language."""
        q = query_text.lower().strip()

        # Entity queries
        if q.startswith(("find ", "get ", "show ", "search ")):
            target = q.split(" ", 1)[1] if " " in q else ""
            if target.startswith(("class", "function", "module", "interface",
                                  "all ")):
                return "entity"

        # Flow queries
        if any(word in q for word in
               ("trace", "flow", "call flow", "data flow", "call graph")):
            return "flow"

        # Impact queries
        if any(word in q for word in
               ("impact", "what breaks", "what if", "who calls",
                "who depends", "what uses")):
            return "impact"

        # Architecture queries
        if any(word in q for word in
               ("architecture", "structure", "module map", "package",
                "overview")):
            return "architecture"

        # Code queries
        if q.startswith("read ") or q.startswith("open ") or "file content" in q:
            return "code"

        # Health queries
        if "health" in q or "quality" in q or "metrics" in q:
            return "health"

        # Context queries (broad, task-oriented)
        if any(word in q for word in
               ("context", "understand", "build", "implement", "refactor")):
            return "context"

        # Symbol queries
        if any(word in q for word in
               ("symbol", "definition", "usage", "where is", "reference")):
            return "symbols"

        # Default to search
        return "search"

    # ── Query Handlers ──

    def _query_entity(self, query: str, params: dict) -> QueryResult:
        """Find entities by name, type, or file."""
        type_filter = params.get("type_filter")
        file_path = params.get("file_path")
        limit = params.get("limit", 30)

        results = []

        # Try type-specific queries
        if type_filter:
            nodes = self.intel.find_by_type(type_filter, file_path)
        else:
            # Extract entity name from natural language query
            search_term = params.get("name") or self._extract_target_name(query) or query
            nodes = self.intel.find(search_term, limit=limit)

        for node in nodes:
            entry = self._node_to_dict(node)

            # Add relation counts
            entry["relation_counts"] = self._get_relation_counts(node.id)
            results.append(entry)

        confidence = 0.9 if results else 0.0
        return QueryResult(
            query=query,
            query_type="entity",
            results=results,
            confidence=confidence,
            metadata={"total_found": len(nodes), "search_term": search_term},
        )

    def _query_flow(self, query: str, params: dict) -> QueryResult:
        """Trace a call or data flow."""
        target = params.get("target") or query
        flow_type = params.get("flow_type", "call")

        # Extract target name from query if not specified
        if not params.get("target"):
            target = self._extract_target_name(query) or target

        analysis = self.intel.trace_flow(target, flow_type)

        results = []
        for node in analysis.nodes:
            results.append(self._node_to_dict(node))

        return QueryResult(
            query=query,
            query_type="flow",
            results=results,
            confidence=0.8 if results else 0.0,
            metadata={
                "flow_type": flow_type,
                "suggestions": analysis.suggestions,
                "metrics": analysis.metrics,
            },
        )

    def _query_impact(self, query: str, params: dict) -> QueryResult:
        """Run impact analysis."""
        target = params.get("target") or query

        if not params.get("target"):
            target = self._extract_target_name(query) or target

        analysis = self.intel.what_breaks(target)

        results = []
        for node in analysis.nodes:
            results.append(self._node_to_dict(node))

        return QueryResult(
            query=query,
            query_type="impact",
            results=results,
            confidence=0.8 if results else 0.0,
            metadata={
                "summary": analysis.summary,
                "suggestions": analysis.suggestions,
                "metrics": analysis.metrics,
            },
        )

    def _query_architecture(self, query: str, params: dict) -> QueryResult:
        """Get architectural overview."""
        domain = params.get("domain")
        if not domain and len(query) > 15:
            # Extract domain from query
            for word in query.split():
                if word.lower() in ("auth", "payment", "user", "admin",
                                     "api", "database", "frontend", "backend"):
                    domain = word
                    break

        analysis = self.intel.find_architecture(domain)

        results = []
        for node in analysis.nodes:
            results.append(self._node_to_dict(node))

        return QueryResult(
            query=query,
            query_type="architecture",
            results=results,
            confidence=0.9,
            metadata={
                "total_modules": analysis.metrics.get("total_modules", 0),
                "total_packages": analysis.metrics.get("total_packages", 0),
                "summary": analysis.summary,
            },
        )

    def _query_search(self, query: str, params: dict) -> QueryResult:
        """Full-text search through caches and KG."""
        limit = params.get("limit", 20)
        search_in = params.get("search_in", "all")  # 'kg', 'files', 'symbols', 'all'

        results = []
        seen_ids = set()
        confidence = 0.0

        # Search knowledge graph
        if search_in in ("kg", "all"):
            nodes = self.intel.find(query, limit=limit)
            for node in nodes:
                if node.id not in seen_ids:
                    seen_ids.add(node.id)
                    entry = self._node_to_dict(node)

                    # Add code snippet if available
                    if self.files:
                        snippet = self._get_snippet(node.file_path, node.line)
                        if snippet:
                            entry["snippet"] = snippet

                    results.append(entry)
            confidence = 0.7 if results else 0.0

        # Search file cache
        if search_in in ("files", "all") and self.files:
            file_results = self.files.find(query) if hasattr(self.files, 'find') else []
            for entry in file_results[:limit]:
                fpath = getattr(entry, 'path', str(entry))
                if fpath not in seen_ids:
                    seen_ids.add(fpath)
                    results.append({
                        "type": "file",
                        "name": Path(fpath).name,
                        "path": fpath,
                        "size": getattr(entry, 'size', 0),
                    })
            confidence = max(confidence, 0.5)

        # Search symbols
        if search_in in ("symbols", "all") and self.symbols:
            symbol_results = self.symbols.find(query) if hasattr(self.symbols, 'find') else []
            for entry in symbol_results[:limit]:
                sym_id = getattr(entry, 'id', str(entry))
                if sym_id not in seen_ids:
                    seen_ids.add(sym_id)
                    results.append({
                        "type": "symbol",
                        "name": getattr(entry, 'name', str(entry)),
                        "path": getattr(entry, 'file_path', ''),
                        "symbol_type": getattr(entry, 'symbol_type', ''),
                    })
            confidence = max(confidence, 0.5)

        return QueryResult(
            query=query,
            query_type="search",
            results=results[:limit],
            confidence=confidence,
            metadata={"total_matches": len(results)},
        )

    def _query_context(self, query: str, params: dict) -> QueryResult:
        """Build rich context for a task."""
        task_files = params.get("files") or params.get("file_paths")
        max_nodes = params.get("max_nodes", 50)

        context = self.intel.build_context(
            task=query,
            task_files=task_files,
            max_nodes=max_nodes,
        )

        results = []
        for entity in context.get("entities", []):
            results.append(self._node_to_dict(entity))

        return QueryResult(
            query=query,
            query_type="context",
            results=results,
            confidence=0.8,
            metadata={
                "summary": context.get("summary", ""),
                "files": context.get("files", []),
                "total_entities": context.get("stats", {}).get("total_entities", 0),
                "total_relations": context.get("stats", {}).get("total_relations", 0),
                "impact_analyses": [
                    {
                        "summary": ia.summary,
                        "metric_count": len(ia.metrics),
                    }
                    for ia in context.get("impact_analyses", [])
                ],
            },
        )

    def _query_code(self, query: str, params: dict) -> QueryResult:
        """Get file contents with context."""
        file_path = params.get("file_path") or query
        # Extract file path if query looks like "read src/main.py"
        if not params.get("file_path"):
            for word in query.split():
                if "/" in word or "\\" in word or word.endswith((".py", ".js", ".ts")):
                    file_path = word
                    break

        results = []

        # Try file cache
        if self.files and file_path:
            entry = None
            if hasattr(self.files, 'get'):
                entry = self.files.get(file_path)
            if entry is None and hasattr(self.files, '_entries'):
                entry = self.files._entries.get(file_path)

            if entry:
                file_dict = {
                    "type": "file_contents",
                    "name": Path(file_path).name,
                    "path": file_path,
                }
                # Add content if available
                if hasattr(entry, 'content') and entry.content:
                    file_dict["content"] = self._truncate_content(
                        entry.content, params.get("max_lines", 100)
                    )
                elif hasattr(entry, 'size'):
                    file_dict["size"] = entry.size
                else:
                    file_dict["size_hint"] = "available in cache"
                results.append(file_dict)

        # If not in cache, read from disk
        if not results and file_path:
            abs_path = file_path if os.path.isabs(file_path) else \
                os.path.join(self.kg.repo_root, file_path)
            if os.path.isfile(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    results.append({
                        "type": "file_contents",
                        "name": Path(file_path).name,
                        "path": file_path,
                        "size": len(content),
                        "content": self._truncate_content(
                            content, params.get("max_lines", 100)
                        ),
                    })
                except (IOError, OSError) as e:
                    pass

        # If just a file path, also show entities from KG
        if file_path:
            entities = self.kg.find_in_file(file_path)
            for entity in entities[:10]:
                results.append(self._node_to_dict(entity))

        return QueryResult(
            query=query,
            query_type="code",
            results=results,
            confidence=0.8 if results else 0.0,
            metadata={"file_path": file_path},
        )

    def _query_symbols(self, query: str, params: dict) -> QueryResult:
        """Find symbol definitions and usages."""
        symbol_name = params.get("symbol") or query

        if not params.get("symbol"):
            symbol_name = self._extract_target_name(query) or symbol_name

        results = []

        # Search KG for symbols
        nodes = self.kg.find(symbol_name, exact=False)
        for node in nodes:
            if node.type in (NodeType.FUNCTION, NodeType.METHOD,
                             NodeType.CLASS, NodeType.VARIABLE,
                             NodeType.CONSTANT):
                entry = self._node_to_dict(node)

                # Find usages (incoming references)
                usages = []
                for r in self.kg.get_relations(node.id, direction="incoming"):
                    source = self.kg.get_node(r.source_id)
                    if source:
                        usages.append({
                            "type": r.type.name.lower(),
                            "from": source.name,
                            "from_type": source.type.name.lower(),
                            "file": r.file_path or source.file_path,
                            "line": r.line,
                        })
                entry["usages"] = usages
                entry["usage_count"] = len(usages)
                results.append(entry)

        # Also search symbol cache if available
        if self.symbols and not results:
            if hasattr(self.symbols, 'find'):
                sym_entries = self.symbols.find(symbol_name)
                for entry in sym_entries:
                    results.append({
                        "name": getattr(entry, 'name', str(entry)),
                        "type": "symbol",
                        "kind": getattr(entry, 'symbol_type', 'unknown'),
                        "file": getattr(entry, 'file_path', ''),
                        "line": getattr(entry, 'line', 0),
                    })

        return QueryResult(
            query=query,
            query_type="symbols",
            results=results,
            confidence=0.7 if results else 0.0,
            metadata={"symbol": symbol_name},
        )

    def _query_health(self, query: str, params: dict) -> QueryResult:
        """Module health assessment."""
        module_path = params.get("module_path") or query

        if not params.get("module_path"):
            for word in query.split():
                if "/" in word or "\\" in word:
                    module_path = word
                    break

        health = self.intel.module_health(module_path)

        return QueryResult(
            query=query,
            query_type="health",
            results=[health],
            confidence=0.9,
            metadata={
                "summary": health.get("summary", ""),
                "health_score": health.get("health_score", 0),
                "issues": health.get("issues", []),
            },
        )

    def _query_custom(self, query: str, params: dict) -> QueryResult:
        """Composed custom query — runs multiple sub-queries and combines results."""
        # Parse the query into sub-queries
        sub_queries = self._parse_sub_queries(query, params)
        combined_results = []
        metadata = {"sub_queries": len(sub_queries)}

        for sq in sub_queries:
            sq_result = self.query(
                query_text=sq.get("text", ""),
                query_type=sq.get("type", "search"),
                params=sq.get("params", {}),
            )
            combined_results.extend(sq_result.results)

        return QueryResult(
            query=query,
            query_type="custom",
            results=combined_results,
            confidence=0.6,
            metadata=metadata,
        )

    # ── Helpers ──

    def _node_to_dict(self, node: KGNode) -> dict:
        """Convert a KGNode to a dictionary for results."""
        return {
            "id": node.id,
            "name": node.name,
            "type": node.type.name.lower(),
            "file_path": node.file_path,
            "line": node.line,
            "signature": node.signature,
            "docstring": node.docstring[:300] if node.docstring else "",
            "visibility": node.visibility,
            "is_async": node.is_async,
        }

    def _get_relation_counts(self, node_id: str) -> dict:
        """Count incoming and outgoing relations by type."""
        counts = defaultdict(int)
        for r in self.kg.get_relations(node_id, direction="outgoing"):
            counts[f"out_{r.type.name.lower()}"] += 1
        for r in self.kg.get_relations(node_id, direction="incoming"):
            counts[f"in_{r.type.name.lower()}"] += 1
        return dict(counts)

    def _extract_target_name(self, query: str) -> Optional[str]:
        """Extract a target name from a natural language query."""
        q = query.strip()

        # "find login flow" -> "login"
        # "trace what happens when user registers" -> "register"
        # "impact of changing DatabaseClient" -> "DatabaseClient"

        # Capitalized words are likely entity names
        for word in q.split():
            word = word.strip(".,!?;:'\"()[]{}")
            if word and word[0].isupper() and len(word) > 1:
                return word

        # Try patterns
        patterns = [
            r'(?:find|trace|show|get|impact\s+of)\s+(\w+)',
            r'(?:who|what)\s+(?:calls|uses|depends on)\s+(\w+)',
            r'(?:what breaks if|what if)\s+(?:\w+\s+)+(\w+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, q, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _get_snippet(self, file_path: str, line: int,
                     context_lines: int = 5) -> Optional[str]:
        """Get a code snippet around a specific line."""
        if not file_path or not self.files:
            return None

        abs_path = file_path if os.path.isabs(file_path) else \
            os.path.join(self.kg.repo_root, file_path)

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except (IOError, OSError):
            return None

        if line < 1 or line > len(lines):
            return None

        start = max(0, line - 1 - context_lines)
        end = min(len(lines), line + context_lines)
        snippet = "".join(lines[start:end])

        # Line numbers for context
        numbered = []
        for i, l in enumerate(lines[start:end], start=start + 1):
            marker = "→" if i == line else " "
            numbered.append(f"{marker} {i}: {l}")

        return "".join(numbered)

    def _truncate_content(self, content: str, max_lines: int = 100) -> str:
        """Truncate content to max_lines."""
        lines = content.split("\n")
        if len(lines) <= max_lines:
            return content
        return "\n".join(lines[:max_lines]) + (
            f"\n# ... {len(lines) - max_lines} more lines ..."
        )

    def _parse_sub_queries(self, query: str, params: dict) -> list[dict]:
        """Parse a complex query into sub-queries."""
        sub_queries = []

        # Default: just run a search
        sub_queries.append({
            "text": query,
            "type": params.get("primary_type", "search"),
            "params": params,
        })

        # If there's a file context, also get code
        if params.get("file_path"):
            sub_queries.append({
                "text": f"read {params['file_path']}",
                "type": "code",
                "params": {"file_path": params["file_path"]},
            })

        # If there's a type filter, add a type-specific query
        if params.get("type_filter"):
            sub_queries.append({
                "text": f"find {params['type_filter']}",
                "type": "entity",
                "params": {"type_filter": params["type_filter"]},
            })

        return sub_queries

    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "name": "retriever",
            **self._stats,
            "avg_time_ms": (
                self._stats["total_time_ms"] / self._stats["queries_executed"]
                if self._stats["queries_executed"] > 0 else 0
            ),
        }
