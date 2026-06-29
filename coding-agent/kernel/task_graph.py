"""
TASK GRAPH — Directed Acyclic Graph (DAG) for parallel task execution.

Instead of linear Step 1 → Step 2 → Step 3, use a DAG where
independent tasks can run in parallel.

Example:
    Read Repository
           │
      ─────┼──────
      │           │
    Index     Read Docs
      │           │
      ─────┬──────
           │
    Build Context
           │
         Plan
           │
       Execute
"""

from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
import json


@dataclass
class TaskNode:
    """A single node in the task graph."""
    id: str
    name: str
    worker_type: str = ""
    description: str = ""
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: dict = field(default_factory=dict)
    error: str = ""
    duration: float = 0.0


class TaskGraph:
    """A DAG of tasks that can be executed in dependency order.
    
    Independent tasks (no dependencies between them) can run in parallel.
    """

    def __init__(self):
        self._nodes: dict[str, TaskNode] = {}
        self._dependencies: dict[str, set[str]] = defaultdict(set)  # node_id -> set of dependency node_ids
        self._dependents: dict[str, set[str]] = defaultdict(set)    # node_id -> set of dependent node_ids

    # ── Node Management ──

    def add_node(self, node_id: str, name: str, worker_type: str = "",
                 description: str = "", params: dict = None) -> TaskNode:
        """Add a task node."""
        node = TaskNode(
            id=node_id,
            name=name,
            worker_type=worker_type,
            description=description or name,
            params=params or {},
        )
        self._nodes[node_id] = node
        return node

    def add_dependency(self, node_id: str, depends_on: str):
        """Add a dependency: node_id depends on depends_on."""
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found")
        if depends_on not in self._nodes:
            raise ValueError(f"Dependency '{depends_on}' not found")
        if depends_on == node_id:
            raise ValueError("A node cannot depend on itself")
        
        # Check for cycles
        if self._would_create_cycle(node_id, depends_on):
            raise ValueError(f"Adding dependency '{depends_on}' -> '{node_id}' would create a cycle")
        
        self._dependencies[node_id].add(depends_on)
        self._dependents[depends_on].add(node_id)

    def _would_create_cycle(self, node_id: str, depends_on: str) -> bool:
        """Check if adding dependency would create a cycle."""
        # If depends_on already depends on node_id (transitively), it's a cycle
        visited = set()
        queue = list(self._dependents.get(node_id, set()))
        while queue:
            current = queue.pop(0)
            if current == depends_on:
                return True
            if current not in visited:
                visited.add(current)
                queue.extend(self._dependents.get(current, set()))
        return False

    # ── Execution Order ──

    def get_execution_order(self) -> list[list[TaskNode]]:
        """Get tasks in execution order as layers.
        
        Each layer is a list of tasks that can run in parallel.
        All tasks in layer N must complete before layer N+1 starts.
        """
        # Topological sort
        in_degree = {nid: len(deps) for nid, deps in self._dependencies.items()}
        for nid in self._nodes:
            if nid not in in_degree:
                in_degree[nid] = 0
        
        layers = []
        remaining = set(self._nodes.keys())
        
        while remaining:
            # Find nodes with no remaining dependencies
            ready = [nid for nid in remaining if in_degree.get(nid, 0) == 0]
            if not ready:
                # Cycle detected or unreachable nodes
                break
            
            layer = [self._nodes[nid] for nid in ready]
            layers.append(layer)
            
            # Update in-degrees
            for nid in ready:
                remaining.remove(nid)
                for dependent in self._dependents.get(nid, set()):
                    if dependent in in_degree:
                        in_degree[dependent] -= 1
        
        return layers

    def get_dependencies(self, node_id: str) -> list[TaskNode]:
        """Get all dependencies of a node (direct and indirect)."""
        result = []
        visited = set()
        queue = list(self._dependencies.get(node_id, set()))
        while queue:
            current = queue.pop(0)
            if current not in visited:
                visited.add(current)
                result.append(self._nodes[current])
                queue.extend(self._dependencies.get(current, set()))
        return result

    def get_dependents(self, node_id: str) -> list[TaskNode]:
        """Get all nodes that depend on this node (direct and indirect)."""
        result = []
        visited = set()
        queue = list(self._dependents.get(node_id, set()))
        while queue:
            current = queue.pop(0)
            if current not in visited:
                visited.add(current)
                result.append(self._nodes[current])
                queue.extend(self._dependents.get(current, set()))
        return result

    # ── Status ──

    @property
    def is_complete(self) -> bool:
        """Check if all nodes are completed or skipped."""
        if not self._nodes:
            return False
        return all(n.status in ("completed", "skipped", "failed") for n in self._nodes.values())

    def get_ready_nodes(self) -> list[TaskNode]:
        """Get nodes that are ready to execute (all dependencies met)."""
        ready = []
        for nid, node in self._nodes.items():
            if node.status != "pending":
                continue
            deps = self._dependencies.get(nid, set())
            if all(self._nodes[d].status == "completed" for d in deps):
                ready.append(node)
        return ready

    def get_progress(self) -> dict:
        """Get progress information."""
        total = len(self._nodes)
        completed = sum(1 for n in self._nodes.values() if n.status == "completed")
        running = sum(1 for n in self._nodes.values() if n.status == "running")
        failed = sum(1 for n in self._nodes.values() if n.status == "failed")
        return {
            "total": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "pending": total - completed - running - failed,
            "progress": completed / total if total > 0 else 0,
        }

    def to_text(self) -> str:
        """Render the graph as a text DAG."""
        layers = self.get_execution_order()
        lines = ["Task Graph:"]
        for i, layer in enumerate(layers):
            statuses = [f"{n.name} [{n.status}]" for n in layer]
            prefix = "  " * i + "  ├─ " if i > 0 else "  "
            lines.append(f"{prefix}{', '.join(statuses)}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: {"name": n.name, "worker_type": n.worker_type,
                            "status": n.status, "dependencies": list(self._dependencies.get(nid, set()))}
                     for nid, n in self._nodes.items()},
            "layers": [[n.id for n in layer] for layer in self.get_execution_order()],
            "progress": self.get_progress(),
        }
