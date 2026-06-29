"""
ARCHITECTURE GRAPH — Concept-based understanding of the codebase.
Moves from "which files exist?" to "how are concepts connected?"
Understands: authentication, data flow, business logic, API endpoints.
"""

import json, os, re, hashlib
from pathlib import Path
from typing import Optional, Any
from collections import defaultdict
from datetime import datetime


class ConceptNode:
    """A concept in the architecture graph (e.g., 'Authentication', 'User Model')."""
    def __init__(self, name: str, kind: str = "concept", description: str = ""):
        self.name = name
        self.kind = kind  # "concept", "layer", "component", "module", "endpoint", "data_flow"
        self.description = description
        self.files: list[str] = []
        self.related_concepts: list[str] = []
        self.parent: Optional[str] = None
        self.children: list[str] = []
        self.tags: list[str] = []


class ArchitectureGraph:
    """Graph of concepts and their relationships in the codebase.
    
    Instead of: login.ts, auth.ts, db.ts
    Understands: Authentication → OAuth → Session → JWT → Database → Users
    """

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self._nodes: dict[str, ConceptNode] = {}
        self._edges: list[dict] = []  # {"source": str, "target": str, "type": str}
        self._project_hash = hashlib.md5(self.workdir.encode()).hexdigest()[:12]
        self._graph_file = Path.home() / ".coding-agent" / "arch-graphs" / f"{self._project_hash}.json"
        self._load()

    # ── Persistence ──

    def _load(self):
        """Load graph from disk."""
        try:
            if self._graph_file.exists():
                data = json.loads(self._graph_file.read_text())
                for node_data in data.get("nodes", []):
                    node = ConceptNode(node_data["name"], node_data.get("kind", "concept"),
                                      node_data.get("description", ""))
                    node.files = node_data.get("files", [])
                    node.related_concepts = node_data.get("related_concepts", [])
                    node.parent = node_data.get("parent")
                    node.children = node_data.get("children", [])
                    node.tags = node_data.get("tags", [])
                    self._nodes[node.name] = node
                self._edges = data.get("edges", [])
        except:
            pass

    def _save(self):
        """Persist graph to disk."""
        self._graph_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": [
                {"name": n.name, "kind": n.kind, "description": n.description,
                 "files": n.files, "related_concepts": n.related_concepts,
                 "parent": n.parent, "children": n.children, "tags": n.tags}
                for n in self._nodes.values()
            ],
            "edges": self._edges,
        }
        self._graph_file.write_text(json.dumps(data, indent=2))

    # ── Node Management ──

    def add_concept(self, name: str, kind: str = "concept", description: str = "",
                    parent: str = None) -> ConceptNode:
        """Add or update a concept node."""
        if name not in self._nodes:
            self._nodes[name] = ConceptNode(name, kind, description)
        
        node = self._nodes[name]
        node.kind = kind
        if description:
            node.description = description
        if parent:
            node.parent = parent
            if parent in self._nodes and name not in self._nodes[parent].children:
                self._nodes[parent].children.append(name)
        
        self._save()
        return node

    def add_file_to_concept(self, concept: str, file_path: str):
        """Associate a file with a concept."""
        if concept in self._nodes:
            if file_path not in self._nodes[concept].files:
                self._nodes[concept].files.append(file_path)
                self._save()

    def relate_concepts(self, source: str, target: str, rel_type: str = "depends_on"):
        """Create a relationship between two concepts."""
        self._edges.append({
            "source": source, "target": target,
            "type": rel_type, "created": datetime.now().isoformat(),
        })
        # Also update related_concepts on both nodes
        if source in self._nodes and target not in self._nodes[source].related_concepts:
            self._nodes[source].related_concepts.append(target)
        if target in self._nodes and source not in self._nodes[target].related_concepts:
            self._nodes[target].related_concepts.append(source)
        self._save()

    def get_concept(self, name: str) -> Optional[ConceptNode]:
        return self._nodes.get(name)

    def find_concept_by_file(self, file_path: str) -> list[str]:
        """Find which concepts a file belongs to."""
        return [name for name, node in self._nodes.items() if file_path in node.files]

    # ── Query ──

    def get_related(self, concept: str, max_depth: int = 2) -> dict:
        """Get the subgraph of related concepts up to max_depth."""
        if concept not in self._nodes:
            return {}
        
        visited = set()
        result = {"nodes": {}, "edges": []}
        
        def dfs(name: str, depth: int):
            if name in visited or depth > max_depth:
                return
            visited.add(name)
            if name in self._nodes:
                result["nodes"][name] = {
                    "kind": self._nodes[name].kind,
                    "description": self._nodes[name].description[:100],
                    "files": self._nodes[name].files[:3],
                }
            for edge in self._edges:
                if edge["source"] == name:
                    result["edges"].append(edge)
                    dfs(edge["target"], depth + 1)
                elif edge["target"] == name:
                    result["edges"].append(edge)
                    dfs(edge["source"], depth + 1)
        
        dfs(concept, 0)
        return result

    def get_upstream(self, concept: str) -> list[str]:
        """Get concepts that this concept depends on."""
        return [
            edge["source"] for edge in self._edges
            if edge["target"] == concept and edge["type"] == "depends_on"
        ]

    def get_downstream(self, concept: str) -> list[str]:
        """Get concepts that depend on this concept."""
        return [
            edge["target"] for edge in self._edges
            if edge["source"] == concept and edge["type"] == "depends_on"
        ]

    def find_impacted(self, concept: str) -> list[str]:
        """Find all concepts impacted by changing this one."""
        impacted = set()
        def walk(name: str):
            for downstream in self.get_downstream(name):
                if downstream not in impacted:
                    impacted.add(downstream)
                    walk(downstream)
        walk(concept)
        return list(impacted)

    # ── Visualization ──

    def to_text(self) -> str:
        """Render the graph as text."""
        lines = ["# Architecture Graph"]
        
        # Group by kind
        by_kind = defaultdict(list)
        for node in self._nodes.values():
            by_kind[node.kind].append(node)
        
        for kind, nodes in by_kind.items():
            lines.append(f"\n## {kind.title()}s ({len(nodes)})")
            for node in sorted(nodes, key=lambda n: n.name):
                files_info = f" ({len(node.files)} files)" if node.files else ""
                deps = self.get_upstream(node.name)
                dep_info = f" ← {', '.join(deps[:5])}" if deps else ""
                impact = self.get_downstream(node.name)
                impact_info = f" → {', '.join(impact[:5])}" if impact else ""
                lines.append(f"- **{node.name}**{files_info}{dep_info}{impact_info}")
                if node.description:
                    lines.append(f"  {node.description[:100]}")
        
        return "\n".join(lines)

    def get_impact_summary(self, concept: str) -> str:
        """Return a summary of what's impacted by changing a concept."""
        impacted = self.find_impacted(concept)
        if not impacted:
            return f"Changing '{concept}' has no downstream impact."
        return (f"Changing **{concept}** impacts {len(impacted)} concept(s):\n"
                + "\n".join(f"- {c}" for c in impacted))

    # ── Auto-discovery from codebase ──

    def auto_discover(self, codebase_analyzer=None):
        """Automatically discover concepts from the codebase structure."""
        if codebase_analyzer is None:
            return
        
        try:
            idx = codebase_analyzer.index() if hasattr(codebase_analyzer, 'index') else {}
        except:
            return
        
        files = idx.get("files", {})
        all_paths = list(files.keys())
        
        # Auto-detect concepts from directory names
        concept_dirs = {
            "auth": "Authentication",
            "authentication": "Authentication",
            "login": "Authentication",
            "user": "User Management",
            "users": "User Management",
            "api": "API Layer",
            "routes": "API Layer",
            "database": "Database",
            "db": "Database",
            "models": "Data Models",
            "model": "Data Models",
            "services": "Services",
            "service": "Services",
            "middleware": "Middleware",
            "middlewares": "Middleware",
            "config": "Configuration",
            "configuration": "Configuration",
            "payment": "Payments",
            "payments": "Payments",
            "email": "Email Service",
            "notifications": "Notifications",
            "notification": "Notifications",
            "cache": "Caching",
            "logging": "Logging",
            "analytics": "Analytics",
            "search": "Search",
            "admin": "Admin Panel",
            "testing": "Testing",
            "tests": "Testing",
            "deployment": "Deployment",
            "docker": "Deployment",
            "ci": "CI/CD",
        }
        
        # Map files to concepts
        file_to_concept = {}
        for path in all_paths:
            parts = path.lower().split("/")
            for part in parts:
                if part in concept_dirs:
                    concept = concept_dirs[part]
                    file_to_concept.setdefault(concept, []).append(path)
        
        # Create concept nodes
        for concept, concept_files in file_to_concept.items():
            self.add_concept(concept, "concept", f"Auto-discovered from directory structure")
            for f in concept_files[:10]:
                self.add_file_to_concept(concept, f)
        
        # Auto-discover relationships from imports
        for path, info in files.items():
            if isinstance(info, dict) and "imports" in info:
                for imp in info["imports"]:
                    # Find which concept this import belongs to
                    for concept, concept_files in file_to_concept.items():
                        imp_clean = imp.replace(".", "/").split("/")[0]
                        if any(imp_clean in cf for cf in concept_files):
                            # Relate source file's concept to import's concept
                            src_concepts = self.find_concept_by_file(path)
                            for src in src_concepts:
                                if src != concept:
                                    self.relate_concepts(src, concept, "depends_on")
        
        self._save()
