"""
KNOWLEDGE GRAPH — The heart of Repository Intelligence.

A directed, typed, multi-relational graph representing code entities
and their semantic relationships. Supports:
  - Graph traversal (BFS, DFS, topological sort)
  - Impact analysis (what breaks if I modify X)
  - Dead code detection (no incoming references)
  - Flow tracing (data flow, call flow, inheritance chains)
  - Shortest path between any two nodes
  - Duplicate detection (similar nodes by name/signature)
  - Subgraph extraction for context building
  - Persistence (JSON-based, inherits from BaseCache)

The Knowledge Graph is designed to answer questions like:
  - Who calls this function?
  - Which routes use this service?
  - What breaks if I modify this class?
  - Find dead code.
  - Find duplicated logic.
  - Show the authentication flow.
  - What tests cover this module?
"""

import os, json, time, hashlib, threading
from typing import Optional, Callable
from collections import defaultdict, deque
from dataclasses import asdict

from .base import BaseCache
from .kg_types import (
    NodeType, RelationType,
    KGNode, KGRelation, KGPath, KGAnalysis,
)


class KnowledgeGraph(BaseCache):
    """A typed, directed, multi-relational knowledge graph for code.

    The Knowledge Graph stores code entities as nodes and their
    semantic relationships as edges. It provides graph algorithms
    and analysis queries for repository intelligence.

    Usage:
        kg = KnowledgeGraph(repo_root, cache_dir)
        kg.add_node(KGNode(...))
        kg.add_relation(KGRelation(...))
        results = kg.find("DatabaseClient")
        impact = kg.get_impact_analysis("class:UserService")
    """

    def __init__(self, repo_root: str, cache_dir: str):
        super().__init__("knowledge_graph", cache_dir)
        self.repo_root = os.path.abspath(repo_root)

        # Core graph storage
        self._nodes: dict[str, KGNode] = {}            # node_id -> KGNode
        self._relations: list[KGRelation] = []          # All relations
        self._adjacency: dict[str, list[KGRelation]] = defaultdict(list)     # source -> outgoing
        self._reverse_adj: dict[str, list[KGRelation]] = defaultdict(list)   # target -> incoming

        # Indexes
        self._by_name: dict[str, list[str]] = defaultdict(list)    # name -> [node_ids]
        self._by_type: dict[str, list[str]] = defaultdict(list)    # type_name -> [node_ids]
        self._by_file: dict[str, list[str]] = defaultdict(list)    # file_path -> [node_ids]
        self._name_lookup: dict[str, list[str]] = defaultdict(list)  # lowercase name -> [node_ids]

        # Stats
        self._stats = {
            "nodes_added": 0,
            "relations_added": 0,
            "queries_executed": 0,
        }

        self.load()

    # ── Node Management ──

    def add_node(self, node: KGNode) -> str:
        """Add a node to the graph. Returns node ID.

        If a node with the same ID already exists, it is updated.
        """
        node_id = node.id
        existing = self._nodes.get(node_id)
        self._nodes[node_id] = node

        # Update indexes
        self._by_name[node.name].append(node_id)
        self._by_type[node.type.name.lower()].append(node_id)
        self._by_file[node.file_path].append(node_id)
        self._name_lookup[node.name.lower()].append(node_id)

        # Remove old indexes if updating
        if existing and existing.name != node.name:
            self._by_name[existing.name].remove(node_id)
            self._name_lookup[existing.name.lower()].remove(node_id)

        self._stats["nodes_added"] += 1
        self.mark_dirty()
        return node_id

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its relations. Returns True if removed."""
        node = self._nodes.pop(node_id, None)
        if not node:
            return False

        # Remove from indexes
        self._by_name[node.name] = [n for n in self._by_name[node.name] if n != node_id]
        self._by_type[node.type.name.lower()] = [n for n in self._by_type[node.type.name.lower()] if n != node_id]
        self._by_file[node.file_path] = [n for n in self._by_file[node.file_path] if n != node_id]
        self._name_lookup[node.name.lower()] = [n for n in self._name_lookup[node.name.lower()] if n != node_id]

        # Remove all relations involving this node
        self._relations = [r for r in self._relations
                          if r.source_id != node_id and r.target_id != node_id]
        self._adjacency.pop(node_id, None)
        self._reverse_adj.pop(node_id, None)

        # Clean reverse adjacency references
        for src_id in list(self._adjacency.keys()):
            self._adjacency[src_id] = [r for r in self._adjacency[src_id] if r.target_id != node_id]
        for tgt_id in list(self._reverse_adj.keys()):
            self._reverse_adj[tgt_id] = [r for r in self._reverse_adj[tgt_id] if r.source_id != node_id]

        self.mark_dirty()
        return True

    def get_node(self, node_id: str) -> Optional[KGNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def node_count(self) -> int:
        return len(self._nodes)

    # ── Relation Management ──

    def add_relation(self, relation: KGRelation) -> bool:
        """Add a relation between two nodes.

        Both nodes must exist in the graph. If a similar relation already
        exists, it is skipped (deduplication).

        Returns True if the relation was added.
        """
        if relation.source_id not in self._nodes:
            return False
        if relation.target_id not in self._nodes:
            return False

        # Deduplication: skip if same relation exists
        for existing in self._adjacency.get(relation.source_id, []):
            if (existing.target_id == relation.target_id and
                existing.type == relation.type):
                return False

        self._relations.append(relation)
        self._adjacency[relation.source_id].append(relation)
        self._reverse_adj[relation.target_id].append(relation)
        self._stats["relations_added"] += 1
        self.mark_dirty()
        return True

    def remove_relation(self, source_id: str, target_id: str,
                        relation_type: RelationType = None) -> bool:
        """Remove a relation. If relation_type is None, removes all between."""
        removed = False
        self._relations = [
            r for r in self._relations
            if not (r.source_id == source_id and r.target_id == target_id
                    and (relation_type is None or r.type == relation_type))
        ]
        if source_id in self._adjacency:
            self._adjacency[source_id] = [
                r for r in self._adjacency[source_id]
                if not (r.target_id == target_id
                        and (relation_type is None or r.type == relation_type))
            ]
            removed = True
        if target_id in self._reverse_adj:
            self._reverse_adj[target_id] = [
                r for r in self._reverse_adj[target_id]
                if not (r.source_id == source_id
                        and (relation_type is None or r.type == relation_type))
            ]
        if removed:
            self.mark_dirty()
        return removed

    def relation_count(self) -> int:
        return len(self._relations)

    # ── Query: Finding Nodes ──

    def find(self, name: str, type_filter: NodeType = None,
             file_path: str = None, exact: bool = True) -> list[KGNode]:
        """Find nodes by name.

        Args:
            name: Node name to search for.
            type_filter: Optional node type filter.
            file_path: Optional file path filter.
            exact: If True, exact match. If False, substring match.

        Returns:
            List of matching KGNode objects.
        """
        self._stats["queries_executed"] += 1

        if exact:
            candidates = self._by_name.get(name, [])
        else:
            # Substring search across name lookup
            name_lower = name.lower()
            candidates = []
            for key, ids in self._name_lookup.items():
                if name_lower in key:
                    candidates.extend(ids)

        results = []
        seen = set()
        for node_id in candidates:
            if node_id in seen:
                continue
            seen.add(node_id)
            node = self._nodes.get(node_id)
            if not node:
                continue
            if type_filter and node.type != type_filter:
                continue
            if file_path and node.file_path != file_path:
                continue
            results.append(node)

        return results

    def find_by_type(self, node_type: NodeType, file_path: str = None) -> list[KGNode]:
        """Find all nodes of a given type."""
        self._stats["queries_executed"] += 1
        node_ids = self._by_type.get(node_type.name.lower(), [])
        results = []
        for node_id in node_ids:
            node = self._nodes.get(node_id)
            if node and (not file_path or node.file_path == file_path):
                results.append(node)
        return results

    def find_in_file(self, file_path: str) -> list[KGNode]:
        """Find all nodes defined in a file."""
        self._stats["queries_executed"] += 1
        node_ids = self._by_file.get(file_path, [])
        return [self._nodes[nid] for nid in node_ids if nid in self._nodes]

    def find_exact(self, name: str, node_type: NodeType, file_path: str = None) -> Optional[KGNode]:
        """Find a single node by exact name and type."""
        node_ids = self._by_name.get(name, [])
        for node_id in node_ids:
            node = self._nodes.get(node_id)
            if node and node.type == node_type:
                if not file_path or node.file_path == file_path:
                    return node
        return None

    # ── Query: Traversal ──

    def get_relations(self, node_id: str, relation_type: RelationType = None,
                      direction: str = "outgoing") -> list[KGRelation]:
        """Get relations for a node.

        Args:
            node_id: The node to query.
            relation_type: Optional filter by relation type.
            direction: 'outgoing', 'incoming', or 'both'.

        Returns:
            List of KGRelation objects.
        """
        self._stats["queries_executed"] += 1
        results = []

        if direction in ("outgoing", "both"):
            for r in self._adjacency.get(node_id, []):
                if relation_type and r.type != relation_type:
                    continue
                results.append(r)

        if direction in ("incoming", "both"):
            for r in self._reverse_adj.get(node_id, []):
                if relation_type and r.type != relation_type:
                    continue
                results.append(r)

        return results

    def get_related_nodes(self, node_id: str, relation_type: RelationType = None,
                          direction: str = "outgoing",
                          max_depth: int = 1) -> dict[str, list[KGNode]]:
        """Get nodes related to a node, grouped by relation type.

        Args:
            node_id: The starting node.
            relation_type: Optional filter by relation type.
            direction: 'outgoing', 'incoming', or 'both'.
            max_depth: How many hops to traverse (1 = direct only).

        Returns:
            Dict mapping relation type names to lists of KGNode objects.
        """
        self._stats["queries_executed"] += 1
        results = defaultdict(list)
        visited = {node_id}

        queue = deque([(node_id, 0)])
        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            relations = self.get_relations(current_id, relation_type, direction)
            for r in relations:
                other_id = r.target_id if direction == "outgoing" else r.source_id
                if other_id == current_id and direction == "both":
                    other_id = r.target_id if r.source_id == current_id else r.source_id

                if other_id not in visited:
                    visited.add(other_id)
                    other_node = self._nodes.get(other_id)
                    if other_node:
                        results[r.type.name.lower()].append(other_node)
                    queue.append((other_id, depth + 1))

        return dict(results)

    # ── Graph Algorithms ──

    def bfs(self, start_id: str, max_depth: int = 10,
            node_filter: Callable = None) -> list[KGNode]:
        """Breadth-first traversal from a starting node.

        Args:
            start_id: Starting node ID.
            max_depth: Maximum traversal depth.
            node_filter: Optional function (KGNode) -> bool to filter nodes.

        Returns:
            List of visited KGNode objects in BFS order.
        """
        if start_id not in self._nodes:
            return []

        visited = {start_id}
        queue = deque([(start_id, 0)])
        result = [self._nodes[start_id]]

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for r in self._adjacency.get(current_id, []):
                if r.target_id not in visited:
                    visited.add(r.target_id)
                    node = self._nodes.get(r.target_id)
                    if node and (not node_filter or node_filter(node)):
                        result.append(node)
                        queue.append((r.target_id, depth + 1))

            for r in self._reverse_adj.get(current_id, []):
                if r.source_id not in visited:
                    visited.add(r.source_id)
                    node = self._nodes.get(r.source_id)
                    if node and (not node_filter or node_filter(node)):
                        result.append(node)
                        queue.append((r.source_id, depth + 1))

        return result

    def dfs(self, start_id: str, max_depth: int = 10,
            node_filter: Callable = None) -> list[KGNode]:
        """Depth-first traversal from a starting node."""
        if start_id not in self._nodes:
            return []

        visited = {start_id}
        result = [self._nodes[start_id]]

        def _dfs(current_id: str, depth: int):
            if depth >= max_depth:
                return
            for r in self._adjacency.get(current_id, []):
                if r.target_id not in visited:
                    visited.add(r.target_id)
                    node = self._nodes.get(r.target_id)
                    if node and (not node_filter or node_filter(node)):
                        result.append(node)
                        _dfs(r.target_id, depth + 1)

        _dfs(start_id, 0)
        return result

    def find_shortest_path(self, start_id: str, end_id: str) -> Optional[KGPath]:
        """Find the shortest path between two nodes using BFS.

        Returns:
            KGPath with the sequence of nodes and relations, or None if no path exists.
        """
        if start_id not in self._nodes or end_id not in self._nodes:
            return None

        visited = {start_id}
        queue = deque([(start_id, [start_id], [])])

        while queue:
            current_id, node_path, rel_path = queue.popleft()
            if current_id == end_id:
                return KGPath(
                    nodes=[self._nodes[nid] for nid in node_path],
                    relations=rel_path,
                    length=len(rel_path),
                )

            for r in self._adjacency.get(current_id, []):
                if r.target_id not in visited:
                    visited.add(r.target_id)
                    queue.append((
                        r.target_id,
                        node_path + [r.target_id],
                        rel_path + [r],
                    ))

        return None

    def find_all_paths(self, start_id: str, end_id: str,
                       max_depth: int = 5) -> list[KGPath]:
        """Find all paths between two nodes up to max_depth."""
        results = []

        def _dfs(current_id: str, end_id: str, depth: int,
                 visited: set, node_path: list[str], rel_path: list[KGRelation]):
            if depth > max_depth:
                return
            if current_id == end_id:
                results.append(KGPath(
                    nodes=[self._nodes[nid] for nid in node_path],
                    relations=list(rel_path),
                    length=len(rel_path),
                ))
                return

            for r in self._adjacency.get(current_id, []):
                if r.target_id not in visited:
                    visited.add(r.target_id)
                    _dfs(r.target_id, end_id, depth + 1,
                         visited, node_path + [r.target_id], rel_path + [r])
                    visited.remove(r.target_id)

        _dfs(start_id, end_id, 0, {start_id}, [start_id], [])
        return sorted(results, key=lambda p: p.length)

    def subgraph(self, node_ids: set[str], max_depth: int = 2) -> "KnowledgeGraph":
        """Extract a subgraph centered around the given nodes.

        Includes all nodes within max_depth hops of any of the given nodes.
        Returns a new KnowledgeGraph instance.
        """
        sub = KnowledgeGraph(self.repo_root, self.cache_dir)

        # Find all nodes within max_depth
        included = set(node_ids)
        for nid in node_ids:
            for node in self.bfs(nid, max_depth):
                included.add(node.id)

        # Add nodes
        for nid in included:
            node = self._nodes.get(nid)
            if node:
                sub.add_node(node)

        # Add relations between included nodes
        for r in self._relations:
            if r.source_id in included and r.target_id in included:
                sub.add_relation(r)

        return sub

    # ── Analysis Queries ──

    def get_impact_analysis(self, node_id: str) -> KGAnalysis:
        """Analyze what breaks if this node is modified or removed.

        Finds all nodes that would be impacted (directly or transitively).
        """
        analysis = KGAnalysis(query_type="impact_analysis")
        node = self._nodes.get(node_id)
        if not node:
            analysis.summary = f"Node {node_id} not found in knowledge graph."
            return analysis

        # Direct dependents (incoming references)
        direct_dependents = []
        for r in self._reverse_adj.get(node_id, []):
            src = self._nodes.get(r.source_id)
            if src:
                direct_dependents.append(src)
                analysis.relations.append(r)

        # Transitive dependents (BFS through reverse adjacency, skipping depth 0
        # which are the direct dependents already counted above)
        transitive = []
        visited = {node_id}
        # Seed queue with direct dependents' IDs at depth 1
        queue = deque()
        for dd in direct_dependents:
            visited.add(dd.id)
            queue.append((dd.id, 1))

        while queue:
            current_id, depth = queue.popleft()
            for r in self._reverse_adj.get(current_id, []):
                if r.source_id not in visited:
                    visited.add(r.source_id)
                    src = self._nodes.get(r.source_id)
                    if src:
                        transitive.append(src)
                        queue.append((r.source_id, depth + 1))
                        analysis.relations.append(r)

        analysis.nodes = direct_dependents + transitive
        analysis.metrics = {
            "direct_dependents": len(direct_dependents),
            "transitive_dependents": len(transitive),
            "total_impacted": len(direct_dependents) + len(transitive),
        }
        analysis.summary = (
            f"Modifying {node.type.name.lower()}:{node.name} "
            f"impacts {analysis.metrics['total_impacted']} entities "
            f"({analysis.metrics['direct_dependents']} direct, "
            f"{analysis.metrics['transitive_dependents']} transitive)."
        )
        return analysis

    def find_dead_code(self) -> KGAnalysis:
        """Find nodes with no incoming references (potential dead code).

        Skips entry points (modules, tests, routes, APIs) and public APIs.
        """
        analysis = KGAnalysis(query_type="dead_code")

        # Entry point types that are expected to have no incoming refs
        entry_types = {NodeType.MODULE, NodeType.PACKAGE, NodeType.ROUTE,
                       NodeType.API, NodeType.COMMAND, NodeType.TEST,
                       NodeType.FILE}

        for node_id, node in self._nodes.items():
            # Skip entry types
            if node.type in entry_types:
                continue

            # Check if anything references this node
            has_incoming = len(self._reverse_adj.get(node_id, [])) > 0

            if not has_incoming:
                analysis.nodes.append(node)

        analysis.metrics = {
            "dead_candidates": len(analysis.nodes),
            "total_nodes": len(self._nodes),
        }
        analysis.summary = (
            f"Found {len(analysis.nodes)} potential dead code entities "
            f"out of {len(self._nodes)} total."
        )
        return analysis

    def find_duplicates(self, threshold: float = 0.8) -> KGAnalysis:
        """Find potential duplicate code based on name similarity.

        Groups nodes with similar names (same type, same file or different).
        """
        analysis = KGAnalysis(query_type="duplicates")

        # Group by type and normalized name prefix
        from collections import Counter
        groups = defaultdict(list)
        for node in self._nodes.values():
            # Normalize: strip trailing digits/underscores
            base = node.name.rstrip("0123456789_")
            if base != node.name and len(base) > 2:
                groups[(node.type, base, node.file_path)].append(node)
            # Also check same name, different file
            key = (node.type, node.name)
            groups[key].append(node)

        for key, nodes in groups.items():
            if len(nodes) >= 2:
                analysis.nodes.extend(nodes)
                analysis.metrics[f"duplicate_group_{key[0].name}_{key[1]}"] = len(nodes)

        analysis.metrics["total_duplicate_groups"] = sum(
            1 for nodes in groups.values() if len(nodes) >= 2
        )
        analysis.summary = (
            f"Found {analysis.metrics['total_duplicate_groups']} potential "
            f"duplicate groups."
        )
        return analysis

    def trace_call_flow(self, function_name: str) -> KGAnalysis:
        """Trace the call flow starting from a function.

        Shows who calls this function, and what this function calls.
        """
        analysis = KGAnalysis(query_type="call_flow")
        nodes = self.find(function_name, type_filter=NodeType.FUNCTION)
        if not nodes:
            nodes = self.find(function_name, type_filter=NodeType.METHOD)
        if not nodes:
            nodes = self.find(function_name)
        if not nodes:
            analysis.summary = f"Function '{function_name}' not found."
            return analysis

        start_node = nodes[0]

        # Outgoing calls (what this function calls)
        for r in self._adjacency.get(start_node.id, []):
            if r.type in (RelationType.CALLS, RelationType.CREATES,
                          RelationType.USES):
                target = self._nodes.get(r.target_id)
                if target:
                    analysis.nodes.append(target)
                    analysis.relations.append(r)

        # Incoming calls (who calls this function)
        for r in self._reverse_adj.get(start_node.id, []):
            if r.type == RelationType.CALLS:
                source = self._nodes.get(r.source_id)
                if source:
                    analysis.nodes.append(source)
                    analysis.relations.append(r)

        analysis.metrics = {
            "outgoing_calls": sum(1 for r in self._adjacency.get(start_node.id, [])
                                 if r.type in (RelationType.CALLS, RelationType.CREATES)),
            "incoming_calls": sum(1 for r in self._reverse_adj.get(start_node.id, [])
                                 if r.type == RelationType.CALLS),
        }
        analysis.summary = (
            f"Call flow for {start_node.type.name.lower()}:{start_node.name}: "
            f"{analysis.metrics['incoming_calls']} callers, "
            f"{analysis.metrics['outgoing_calls']} callees."
        )
        return analysis

    def trace_inheritance(self, class_name: str) -> KGAnalysis:
        """Trace the inheritance chain for a class."""
        analysis = KGAnalysis(query_type="inheritance")
        nodes = self.find(class_name, type_filter=NodeType.CLASS)
        if not nodes:
            analysis.summary = f"Class '{class_name}' not found."
            return analysis

        start_node = nodes[0]
        analysis.nodes.append(start_node)

        # Walk up inheritance (parents)
        current = start_node
        visited = {current.id}
        while True:
            parents = [r for r in self._reverse_adj.get(current.id, [])
                      if r.type == RelationType.INHERITS]
            if not parents:
                break
            parent = self._nodes.get(parents[0].source_id)
            if not parent or parent.id in visited:
                break
            visited.add(parent.id)
            analysis.nodes.append(parent)
            analysis.relations.append(parents[0])
            current = parent

        # Walk down inheritance (children)
        current = start_node
        while True:
            children = [r for r in self._adjacency.get(current.id, [])
                       if r.type == RelationType.INHERITS]
            if not children:
                break
            child = self._nodes.get(children[0].target_id)
            if not child or child.id in visited:
                break
            visited.add(child.id)
            analysis.nodes.append(child)
            analysis.relations.append(children[0])
            current = child

        analysis.metrics = {
            "ancestors": len([n for n in analysis.nodes if n != start_node]),
            "descendants": 0,
        }
        analysis.summary = (
            f"Inheritance chain for {class_name}: "
            f"{analysis.metrics['ancestors']} ancestors found."
        )
        return analysis

    def find_related_tests(self, node_id: str) -> KGAnalysis:
        """Find tests related to a node."""
        analysis = KGAnalysis(query_type="related_tests")

        # Direct test relations
        for r in self._reverse_adj.get(node_id, []):
            if r.type == RelationType.TESTS:
                test_node = self._nodes.get(r.source_id)
                if test_node:
                    analysis.nodes.append(test_node)
                    analysis.relations.append(r)

        # Also find tests of related nodes (by name similarity)
        node = self._nodes.get(node_id)
        if node:
            base_name = node.name.split(".")[0]
            for nid, n in self._nodes.items():
                if n.type in (NodeType.TEST, NodeType.FUNCTION, NodeType.METHOD):
                    if base_name.lower() in n.name.lower() and n.id != node_id:
                        if n not in analysis.nodes:
                            analysis.nodes.append(n)

        analysis.metrics = {"related_tests": len(analysis.nodes)}
        analysis.summary = (
            f"Found {len(analysis.nodes)} tests related to '{node_id}'."
        )
        return analysis

    def get_module_summary(self, file_path: str) -> KGAnalysis:
        """Get a summary of everything defined in a module/file."""
        analysis = KGAnalysis(query_type="module_summary")
        nodes = self.find_in_file(file_path)

        analysis.nodes = nodes
        by_type = defaultdict(list)
        for n in nodes:
            by_type[n.type.name.lower()].append(n.name)

        analysis.metrics = {f"{t}s": len(names) for t, names in by_type.items()}
        analysis.metrics["total"] = len(nodes)

        type_counts = ", ".join(
            f"{count} {t}" for t, count in analysis.metrics.items()
            if t != "total" and count > 0
        )
        analysis.summary = (
            f"Module '{file_path}': {len(nodes)} entities ({type_counts})."
        )
        return analysis

    # ── Persistence ──

    def save(self):
        """Save the knowledge graph to disk."""
        data = {
            "version": 1,
            "nodes": {nid: self._node_to_dict(n) for nid, n in self._nodes.items()},
            "relations": [self._relation_to_dict(r) for r in self._relations],
            "stats": dict(self._stats),
        }
        self._save_json(data)

    def load(self):
        """Load the knowledge graph from disk."""
        data = self._load_json()
        if not data:
            return

        self._nodes.clear()
        self._relations.clear()
        self._adjacency.clear()
        self._reverse_adj.clear()
        self._by_name.clear()
        self._by_type.clear()
        self._by_file.clear()
        self._name_lookup.clear()

        for nid, ndata in data.get("nodes", {}).items():
            node = self._node_from_dict(ndata)
            self._nodes[nid] = node
            self._by_name[node.name].append(nid)
            self._by_type[node.type.name.lower()].append(nid)
            self._by_file[node.file_path].append(nid)
            self._name_lookup[node.name.lower()].append(nid)

        for rdata in data.get("relations", []):
            rel = self._relation_from_dict(rdata)
            self._relations.append(rel)
            self._adjacency[rel.source_id].append(rel)
            self._reverse_adj[rel.target_id].append(rel)

        self._stats.update(data.get("stats", {}))

    # ── Serialization Helpers ──

    def _node_to_dict(self, node: KGNode) -> dict:
        d = asdict(node)
        d["type"] = node.type.name
        return d

    def _node_from_dict(self, data: dict) -> KGNode:
        data = dict(data)
        data["type"] = NodeType[data["type"]]
        return KGNode(**data)

    def _relation_to_dict(self, rel: KGRelation) -> dict:
        d = asdict(rel)
        d["type"] = rel.type.name
        return d

    def _relation_from_dict(self, data: dict) -> KGRelation:
        data = dict(data)
        data["type"] = RelationType[data["type"]]
        return KGRelation(**data)

    # ── Statistics ──

    def get_stats(self) -> dict:
        type_counts = defaultdict(int)
        for node in self._nodes.values():
            type_counts[node.type.name.lower()] += 1

        relation_counts = defaultdict(int)
        for rel in self._relations:
            relation_counts[rel.type.name.lower()] += 1

        return {
            "name": self.name,
            "total_nodes": len(self._nodes),
            "total_relations": len(self._relations),
            "nodes_by_type": dict(type_counts),
            "relations_by_type": dict(relation_counts),
            "files_indexed": len(self._by_file),
            "unique_names": len(self._by_name),
            **self._stats,
        }

    def clear(self):
        self._nodes.clear()
        self._relations.clear()
        self._adjacency.clear()
        self._reverse_adj.clear()
        self._by_name.clear()
        self._by_type.clear()
        self._by_file.clear()
        self._name_lookup.clear()
        self._stats = {"nodes_added": 0, "relations_added": 0, "queries_executed": 0}
        self.mark_dirty()
