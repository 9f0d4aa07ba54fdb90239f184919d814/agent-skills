"""
REPOSITORY INTELLIGENCE — The layer that understands architecture, not just files.

Combines Knowledge Graph + specialized caches to provide:
  - Architectural understanding (classes, relationships, data flow)
  - High-level queries ("find login flow", "what breaks if I modify X")
  - Context building for workers
  - Code analysis (dead code, duplicates, complexity)
  - Architecture diagrams and summaries

This is the layer that separates an "LLM + tools" implementation from
a true software engineering agent that understands the codebase architecturally.
"""

import os, fnmatch
from typing import Optional, Any
from collections import defaultdict

from .kg_types import (
    NodeType, RelationType,
    KGNode, KGRelation, KGPath, KGAnalysis,
)
from .knowledge_graph import KnowledgeGraph
from .indexer import Indexer
from .file_cache import FileCache
from .dependency_cache import DependencyCache
from .symbol_cache import SymbolCache


class RepositoryIntelligence:
    """High-level repository understanding built on Knowledge Graph + caches.

    Provides:
      - Architectural queries (impact analysis, flow tracing)
      - Context building (what does a worker need to understand a task)
      - Code analysis (dead code, duplicates, module health)
      - Natural queries ("find login flow", "show auth architecture")

    Usage:
        ri = RepositoryIntelligence(repo_root, cache_dir)
        ri.initialize(knowledge_graph, file_cache, symbol_cache, dep_cache)

        # High-level queries
        impact = ri.what_breaks("class:DatabaseClient")
        flow = ri.trace_flow("function:login")
        context = ri.build_context("Add OAuth authentication")
        health = ri.module_health("src/auth/")
    """

    def __init__(self, repo_root: str, cache_dir: str = None):
        self.repo_root = os.path.abspath(repo_root)
        self.cache_dir = cache_dir or os.path.join(self.repo_root, ".agent-cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        # Core components
        self.kg = KnowledgeGraph(self.repo_root, self.cache_dir)
        self.indexer = Indexer(self.kg)

        # Optional cache references (set via initialize)
        self.files: Optional[FileCache] = None
        self.symbols: Optional[SymbolCache] = None
        self.dependencies: Optional[DependencyCache] = None

        # State
        self._initialized = False
        self._stats = {
            "queries_served": 0,
            "contexts_built": 0,
        }

    def initialize(self, file_cache: FileCache = None,
                   symbol_cache: SymbolCache = None,
                   dep_cache: DependencyCache = None):
        """Connect to specialized caches."""
        self.files = file_cache
        self.symbols = symbol_cache
        self.dependencies = dep_cache
        self._initialized = True

    # ── Indexing ──

    def index_file(self, file_path: str) -> dict:
        """Index a file: parse AST, populate KG, update caches.

        Args:
            file_path: Relative or absolute path to the file.

        Returns:
            Dict with stats about what was indexed.
        """
        start = len(self.kg._nodes)
        nodes_created = self.indexer.index_file(file_path)
        total_nodes = len(self.kg._nodes)

        return {
            "file": file_path,
            "nodes_created": nodes_created,
            "total_nodes": total_nodes,
            "total_relations": self.kg.relation_count(),
        }

    def index_all(self) -> dict:
        """Index all discoverable files in the repository.

        Returns:
            Dict with overall indexing stats.
        """
        start_nodes = len(self.kg._nodes)
        self.indexer.index_all()
        end_nodes = len(self.kg._nodes)

        stats = self.indexer.get_stats()
        return {
            "files_indexed": stats["indexed_files"],
            "nodes_created": end_nodes - start_nodes,
            "total_nodes": end_nodes,
            "total_relations": self.kg.relation_count(),
        }

    # ── Core Queries ──

    def find(self, query: str, type_filter: str = None, limit: int = 20) -> list[KGNode]:
        """Search for entities by name.

        Args:
            query: Name or partial name to search for.
            type_filter: Optional node type filter (e.g., 'class', 'function').
            limit: Maximum results.

        Returns:
            List of matching KGNode objects.
        """
        self._stats["queries_served"] += 1

        ntype = None
        if type_filter:
            try:
                ntype = NodeType[type_filter.upper()]
            except KeyError:
                pass

        # Try exact match first, then substring
        results = self.kg.find(query, ntype, exact=True)
        if not results:
            results = self.kg.find(query, ntype, exact=False)

        return results[:limit]

    def find_by_type(self, node_type: str, file_path: str = None) -> list[KGNode]:
        """Find all nodes of a given type."""
        self._stats["queries_served"] += 1
        try:
            ntype = NodeType[node_type.upper()]
        except KeyError:
            return []
        return self.kg.find_by_type(ntype, file_path)

    # ── Architectural Queries ──

    def what_breaks(self, target: str) -> KGAnalysis:
        """Impact analysis: what breaks if I modify this entity?

        Args:
            target: Entity name or node ID to analyze.

        Returns:
            KGAnalysis with impacted nodes and suggestions.
        """
        self._stats["queries_served"] += 1
        node = self._resolve_target(target)
        if not node:
            return KGAnalysis(
                query_type="impact_analysis",
                summary=f"Entity '{target}' not found in knowledge graph.",
            )

        analysis = self.kg.get_impact_analysis(node.id)

        # Add suggestions based on analysis
        if analysis.metrics.get("total_impacted", 0) > 0:
            analysis.suggestions.append(
                f"Run tests for {analysis.metrics['direct_dependents']} "
                f"directly impacted files."
            )
            analysis.suggestions.append(
                f"Review {analysis.metrics['transitive_dependents']} "
                f"transitively impacted files for side effects."
            )

        # Add file-level impact from dependency cache
        if self.dependencies and node.file_path:
            affected = self.dependencies.get_affected_files([node.file_path])
            if affected:
                analysis.metrics["affected_files"] = len(affected)
                analysis.suggestions.append(
                    f"Also check dependency graph: {len(affected)} files "
                    f"may be affected transitively."
                )

        return analysis

    def trace_flow(self, target: str, flow_type: str = "call") -> KGAnalysis:
        """Trace a flow through the codebase.

        Args:
            target: Entity name or node ID.
            flow_type: 'call' (call flow), 'data' (data flow),
                      'inheritance' (class hierarchy), 'all'

        Returns:
            KGAnalysis with the flow path.
        """
        self._stats["queries_served"] += 1
        node = self._resolve_target(target)
        if not node:
            return KGAnalysis(
                query_type=f"{flow_type}_flow",
                summary=f"Entity '{target}' not found.",
            )

        if flow_type == "call":
            return self.kg.trace_call_flow(node.name)
        elif flow_type == "inheritance":
            return self.kg.trace_inheritance(node.name)
        elif flow_type == "data":
            return self._trace_data_flow(node)
        else:
            return self.kg.trace_call_flow(node.name)

    def _trace_data_flow(self, node: KGNode) -> KGAnalysis:
        """Trace data flow: what this function reads/writes/returns."""
        analysis = KGAnalysis(query_type="data_flow")
        analysis.nodes.append(node)

        # Find READS, WRITES, RETURNS relations
        for r in self.kg.get_relations(node.id, direction="outgoing"):
            if r.type in (RelationType.READS, RelationType.WRITES,
                          RelationType.RETURNS, RelationType.CREATES,
                          RelationType.ASSIGNS):
                target = self.kg.get_node(r.target_id)
                if target:
                    analysis.nodes.append(target)
                    analysis.relations.append(r)

        analysis.metrics = {
            "reads": sum(1 for r in analysis.relations if r.type == RelationType.READS),
            "writes": sum(1 for r in analysis.relations if r.type == RelationType.WRITES),
            "returns": sum(1 for r in analysis.relations if r.type == RelationType.RETURNS),
        }
        analysis.summary = (
            f"Data flow for {node.type.name.lower()}:{node.name}: "
            f"{analysis.metrics['reads']} reads, {analysis.metrics['writes']} writes."
        )
        return analysis

    def find_architecture(self, domain: str = None) -> KGAnalysis:
        """Find the architectural structure of the codebase.

        Args:
            domain: Optional domain to focus on (e.g., 'auth', 'payment').

        Returns:
            KGAnalysis with module and package hierarchy.
        """
        self._stats["queries_served"] += 1
        analysis = KGAnalysis(query_type="architecture")

        # Get all modules
        modules = self.kg.find_by_type(NodeType.MODULE)
        if domain:
            modules = [m for m in modules if domain.lower() in m.name.lower() or
                       domain.lower() in m.file_path.lower()]

        # Build hierarchy
        hierarchy = defaultdict(list)
        for module in modules:
            parts = module.file_path.replace("\\", "/").split("/")
            if len(parts) >= 2:
                pkg = parts[0]
                hierarchy[pkg].append(module)

        for pkg, mods in sorted(hierarchy.items()):
            analysis.metrics[f"package:{pkg}"] = len(mods)

        analysis.metrics["total_modules"] = len(modules)
        analysis.metrics["total_packages"] = len(hierarchy)
        analysis.nodes = modules

        analysis.summary = (
            f"Architecture: {len(modules)} modules across "
            f"{len(hierarchy)} packages."
        )
        return analysis

    def find_dead_code(self) -> KGAnalysis:
        """Find potential dead code across the repository."""
        self._stats["queries_served"] += 1
        return self.kg.find_dead_code()

    def find_duplicates(self) -> KGAnalysis:
        """Find potential duplicate code."""
        self._stats["queries_served"] += 1
        return self.kg.find_duplicates()

    # ── Context Building ──

    def build_context(self, task: str, task_files: list[str] = None,
                      max_nodes: int = 50) -> dict:
        """Build a rich context for a task.

        This is the primary interface workers use to understand a task.
        Instead of grepping and reading files, they ask for context.

        Args:
            task: Natural language description of the task.
            task_files: Optional list of files already relevant to the task.
            max_nodes: Maximum number of knowledge graph nodes to include.

        Returns:
            Dict with:
              - summary: High-level context summary
              - entities: Relevant entities from the knowledge graph
              - relations: Relevant relationships
              - files: Relevant file paths
              - impact: Impact analysis for the main entities
        """
        self._stats["contexts_built"] += 1

        # Extract key terms from the task
        key_terms = self._extract_key_terms(task)
        relevant_nodes = []
        relevant_files = set(task_files or [])
        relations = []
        impacts = []

        # Find entities matching key terms
        for term in key_terms:
            nodes = self.kg.find(term, exact=False)
            relevant_nodes.extend(nodes)
            for n in nodes:
                relevant_files.add(n.file_path)

                # Get impact analysis for important entities
                if n.type in (NodeType.CLASS, NodeType.FUNCTION,
                              NodeType.MODULE, NodeType.INTERFACE):
                    ri = self.kg.get_impact_analysis(n.id)
                    impacts.append(ri)

        # Limit nodes
        relevant_nodes = relevant_nodes[:max_nodes]

        # Get relations between relevant nodes
        node_ids = {n.id for n in relevant_nodes}
        for nid in node_ids:
            for r in self.kg.get_relations(nid, direction="outgoing"):
                if r.target_id in node_ids:
                    relations.append(r)

        # File metadata from cache if available
        file_entries = {}
        if self.files and task_files:
            for f in task_files:
                entry = self.files.get(f)
                if entry:
                    file_entries[f] = {
                        "path": entry.path,
                        "language": entry.language,
                        "size": entry.size,
                    }

        # Build summary
        entity_types = defaultdict(list)
        for n in relevant_nodes:
            entity_types[n.type.name.lower()].append(n.name)

        type_desc = "; ".join(
            f"{len(names)} {t}" for t, names in entity_types.items()
        )

        return {
            "task": task,
            "summary": f"Context includes {len(relevant_nodes)} entities "
                       f"({type_desc}) across {len(relevant_files)} files. "
                       f"{len(relations)} relationships identified.",
            "entities": relevant_nodes,
            "relations": relations,
            "files": list(relevant_files),
            "file_metadata": file_entries,
            "impact_analyses": impacts[:5],
            "stats": {
                "total_entities": len(relevant_nodes),
                "total_files": len(relevant_files),
                "total_relations": len(relations),
            },
        }

    def _extract_key_terms(self, task: str) -> list[str]:
        """Extract key search terms from a natural language task.

        Uses simple heuristics: extracts capitalized words, quoted terms,
        and common code-related patterns.
        """
        terms = set()

        # Capitalized words (likely class/entity names)
        for word in task.split():
            word = word.strip(".,!?;:'\"()[]{}")
            if word and word[0].isupper() and len(word) > 1:
                terms.add(word)

        # Quoted terms
        import re
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', task)
        for q in quoted:
            for part in q:
                if part:
                    terms.add(part.strip())

        # Common patterns
        patterns = [
            r'(?:find|show|trace|get|locate)\s+(\w+(?:\s+\w+)?)',
            r'(?:modify|change|update|edit|refactor)\s+(\w+(?:\s+\w+)?)',
            r'(?:flow|process|pipeline|workflow)\s+(\w+)',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, task, re.IGNORECASE):
                term = match.group(1).strip()
                if term:
                    terms.add(term)

        # Also add base words that might be file/module names
        for word in task.lower().split():
            word = word.strip(".,!?;:'\"()[]{}")
            if word in ("auth", "login", "user", "api", "database", "payment",
                        "service", "model", "view", "controller", "route",
                        "test", "config", "middleware"):
                terms.add(word)

        return list(terms)

    def find_related(self, node_id: str, relation_type: str = None,
                     max_depth: int = 2) -> list[KGNode]:
        """Find all entities related to a given entity.

        Args:
            node_id: The starting node ID.
            relation_type: Optional relation type filter.
            max_depth: How many hops to traverse.

        Returns:
            List of related KGNode objects.
        """
        self._stats["queries_served"] += 1

        rtype = None
        if relation_type:
            try:
                rtype = RelationType[relation_type.upper()]
            except KeyError:
                pass

        related = self.kg.get_related_nodes(node_id, rtype, "both", max_depth)
        results = []
        for nodes_list in related.values():
            results.extend(nodes_list)
        return results

    # ── Module-Level Queries ──

    def module_health(self, module_path: str) -> dict:
        """Assess the health of a module.

        Args:
            module_path: Path to a file or directory.

        Returns:
            Dict with health metrics:
              - entity_count: Number of entities
              - complexity: Average complexity indicators
              - test_coverage: Related tests found
              - dependency_count: How many dependencies
              - dependent_count: How many dependents
              - dead_code: Potential dead code entities
              - issues: List of identified issues
        """
        self._stats["queries_served"] += 1

        nodes = self.kg.find_in_file(module_path)
        if not nodes:
            nodes = self.kg.find(module_path)
        if not nodes:
            for nid, node in list(self.kg._nodes.items())[:1000]:
                if module_path.lower() in node.file_path.lower():
                    nodes.append(node)

        # Count by type
        type_counts = defaultdict(int)
        for n in nodes:
            type_counts[n.type.name.lower()] += 1

        # Count dependencies
        dep_count = 0
        for n in nodes:
            for r in self.kg.get_relations(n.id, RelationType.DEPENDS_ON, "outgoing"):
                dep_count += 1

        # Count dependents
        dep_by_count = 0
        for n in nodes:
            for r in self.kg.get_relations(n.id, RelationType.DEPENDS_ON, "incoming"):
                dep_by_count += 1

        # Find dead code candidates
        dead = []
        for n in nodes:
            incoming = self.kg.get_relations(n.id, direction="incoming")
            if not incoming and n.type not in (NodeType.MODULE, NodeType.TEST,
                                                NodeType.IMPORT, NodeType.FILE):
                dead.append(n)

        # Find related tests
        tests = []
        for n in nodes:
            test_analysis = self.kg.find_related_tests(n.id)
            tests.extend(test_analysis.nodes)

        health_score = 1.0
        issues = []

        if len(dead) > 2:
            health_score -= 0.1 * min(len(dead), 5)
            issues.append(f"{len(dead)} potential dead code entities found.")

        if type_counts.get("function", 0) > 20:
            health_score -= 0.1
            issues.append("Module has many functions; consider splitting.")

        if dep_count > 15:
            health_score -= 0.1
            issues.append(f"Module has {dep_count} dependencies; high coupling.")

        if not tests:
            health_score -= 0.1
            issues.append("No related tests found.")

        return {
            "module": module_path,
            "health_score": max(0.0, health_score),
            "entity_count": len(nodes),
            "entities_by_type": dict(type_counts),
            "dependency_count": dep_count,
            "dependent_count": dep_by_count,
            "dead_code_candidates": [n.name for n in dead],
            "related_tests": list(set(t.name for t in tests)),
            "issues": issues,
            "summary": (
                f"Module '{module_path}': {len(nodes)} entities, "
                f"health score {max(0.0, health_score):.0%}. "
                f"{len(issues)} issues found."
            ),
        }

    def module_map(self, module_path: str) -> list[dict]:
        """Generate a structured map of a module's entities and relationships.

        Returns a list of entity dicts with their outgoing relations.
        """
        self._stats["queries_served"] += 1

        nodes = self.kg.find_in_file(module_path)
        if not nodes:
            return []

        result = []
        for node in nodes:
            relations = []
            for r in self.kg.get_relations(node.id, direction="outgoing"):
                target = self.kg.get_node(r.target_id)
                if target:
                    relations.append({
                        "type": r.type.name.lower(),
                        "target": target.name,
                        "target_type": target.type.name.lower(),
                        "line": r.line,
                    })

            result.append({
                "id": node.id,
                "name": node.name,
                "type": node.type.name.lower(),
                "line": node.line,
                "docstring": node.docstring[:200] if node.docstring else "",
                "relations": relations,
            })

        return result

    # ── Helpers ──

    def _resolve_target(self, target: str) -> Optional[KGNode]:
        """Resolve a user query to a knowledge graph node.

        Tries: exact node ID -> name match -> substring match -> file path match.
        """
        # Try as node ID first
        node = self.kg.get_node(target)
        if node:
            return node

        # Try as name (exact)
        nodes = self.kg.find(target, exact=True)
        if nodes:
            return nodes[0]

        # Try as name (substring)
        nodes = self.kg.find(target, exact=False)
        if nodes:
            return nodes[0]

        # Try as file path
        file_nodes = self.kg.find_in_file(target)
        if file_nodes:
            return file_nodes[0]

        return None

    def get_stats(self) -> dict:
        """Get comprehensive intelligence statistics."""
        kg_stats = self.kg.get_stats()
        indexer_stats = self.indexer.get_stats()
        return {
            "name": "repository_intelligence",
            "knowledge_graph": kg_stats,
            "indexer": indexer_stats,
            **self._stats,
        }

    def get_summary(self) -> str:
        """Human-readable summary."""
        s = self.get_stats()
        kg = s.get("knowledge_graph", {})
        lines = [
            "🧠 Repository Intelligence Summary",
            f"  📊 Knowledge Graph: {kg.get('total_nodes', 0)} nodes, "
                f"{kg.get('total_relations', 0)} relations",
            f"  📁 Files Indexed: {kg.get('files_indexed', 0)}",
            f"  🔤 Unique Names: {kg.get('unique_names', 0)}",
            f"  🔎 Queries Served: {s.get('queries_served', 0)}",
            f"  📝 Contexts Built: {s.get('contexts_built', 0)}",
            f"  📄 Indexer: {s.get('indexer', {}).get('indexed_files', 0)} files, "
                f"{s.get('indexer', {}).get('nodes_created', 0)} nodes",
        ]
        if "nodes_by_type" in kg:
            by_type = kg["nodes_by_type"]
            type_str = ", ".join(
                f"{count} {t}" for t, count in
                sorted(by_type.items(), key=lambda x: -x[1])[:5]
            )
            lines.append(f"  🏷️  Top Types: {type_str}")
        return "\n".join(lines)
