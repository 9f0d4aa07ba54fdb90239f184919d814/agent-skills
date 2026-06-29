"""
WORLD MODEL — Structured understanding of the project's state.
Tracks: architecture, technical debt, TODOs, known bugs, roadmap,
coding standards, feature requests, and design decisions.
The agent uses this to reason about the project like an engineer.
"""

import json, os, re, time, hashlib
from pathlib import Path
from typing import Optional, Any
from datetime import datetime


PROJECT_MODEL_DIR = Path.home() / ".coding-agent" / "world-models"


class WorldModel:
    """The agent's understanding of the project state.
    
    This is NOT just a file index. It's a structured model of:
    - Architecture (components, layers, patterns)
    - Technical debt (known issues, workarounds)
    - TODOs (incomplete features, planned work)
    - Known bugs (tracked issues)
    - Roadmap (planned features and milestones)
    - Coding standards (conventions, style guide)
    - Design decisions (rationale for past choices)
    - Feature requests (planned or requested features)
    """

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self._project_hash = hashlib.md5(self.workdir.encode()).hexdigest()[:12]
        self._model_file = PROJECT_MODEL_DIR / f"{self._project_hash}.json"
        PROJECT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    # ── Persistence ──

    def _load(self) -> dict:
        """Load the world model from disk."""
        if self._model_file.exists():
            try:
                return json.loads(self._model_file.read_text())
            except:
                pass
        return self._default()

    def _default(self) -> dict:
        return {
            "project_name": Path(self.workdir).name,
            "last_updated": datetime.now().isoformat(),
            "architecture": {
                "layers": [],
                "components": [],
                "patterns": [],
                "data_flow": [],
            },
            "technical_debt": [],
            "todos": [],
            "known_bugs": [],
            "roadmap": [],
            "coding_standards": [],
            "design_decisions": [],
            "feature_requests": [],
            "metrics": {
                "total_files": 0,
                "total_lines": 0,
                "languages": {},
            },
        }

    def save(self):
        """Persist the world model to disk."""
        self.data["last_updated"] = datetime.now().isoformat()
        self._model_file.write_text(json.dumps(self.data, indent=2))

    # ── Architecture Management ──

    def set_architecture(self, layers: list[dict], components: list[dict],
                         patterns: list[str], data_flow: list[dict]):
        """Set the architecture model."""
        self.data["architecture"] = {
            "layers": layers,
            "components": components,
            "patterns": patterns,
            "data_flow": data_flow,
        }
        self.save()

    def add_layer(self, name: str, description: str, technologies: list[str] = None):
        """Add an architectural layer."""
        layer = {
            "name": name,
            "description": description,
            "technologies": technologies or [],
            "added": datetime.now().isoformat(),
        }
        # Update if exists
        for i, l in enumerate(self.data["architecture"]["layers"]):
            if l["name"] == name:
                self.data["architecture"]["layers"][i] = layer
                self.save()
                return
        self.data["architecture"]["layers"].append(layer)
        self.save()

    def add_component(self, name: str, layer: str, description: str,
                      files: list[str] = None, dependencies: list[str] = None):
        """Add a component to the architecture."""
        component = {
            "name": name,
            "layer": layer,
            "description": description,
            "files": files or [],
            "dependencies": dependencies or [],
            "added": datetime.now().isoformat(),
        }
        for i, c in enumerate(self.data["architecture"]["components"]):
            if c["name"] == name:
                self.data["architecture"]["components"][i] = component
                self.save()
                return
        self.data["architecture"]["components"].append(component)
        self.save()

    def get_architecture_summary(self) -> str:
        """Return a human-readable architecture summary."""
        arch = self.data["architecture"]
        parts = ["## Architecture"]
        
        if arch["layers"]:
            parts.append("\n### Layers")
            for l in arch["layers"]:
                techs = f" ({', '.join(l['technologies'])})" if l.get('technologies') else ""
                parts.append(f"- **{l['name']}**{techs}: {l['description']}")
        
        if arch["components"]:
            parts.append(f"\n### Components ({len(arch['components'])})")
            for c in sorted(arch["components"], key=lambda x: x.get('layer', '')):
                deps = f" → {', '.join(c['dependencies'][:5])}" if c.get('dependencies') else ""
                parts.append(f"- **{c['name']}** [{c['layer']}]{deps}: {c['description'][:80]}")
        
        if arch["patterns"]:
            parts.append(f"\n### Patterns: {', '.join(arch['patterns'])}")
        
        return "\n".join(parts)

    # ── Technical Debt ──

    def add_debt(self, title: str, description: str, severity: str = "medium",
                 area: str = "", effort: str = ""):
        """Record technical debt."""
        entry = {
            "id": hashlib.md5(title.encode()).hexdigest()[:8],
            "title": title,
            "description": description,
            "severity": severity,
            "area": area,
            "effort": effort,
            "status": "open",
            "created": datetime.now().isoformat(),
        }
        self.data["technical_debt"].append(entry)
        self.save()
        return entry["id"]

    def resolve_debt(self, debt_id: str):
        """Mark technical debt as resolved."""
        for d in self.data["technical_debt"]:
            if d["id"] == debt_id:
                d["status"] = "resolved"
                d["resolved"] = datetime.now().isoformat()
                self.save()
                return True
        return False

    def get_debt_summary(self) -> str:
        """Return technical debt summary."""
        debts = [d for d in self.data["technical_debt"] if d["status"] == "open"]
        if not debts:
            return "No open technical debt items."
        lines = [f"### Technical Debt ({len(debts)} open)"]
        for d in sorted(debts, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 99)):
            area = f" [{d['area']}]" if d.get('area') else ""
            lines.append(f"- [{d['severity'].upper()}]{area} {d['title']} (effort: {d.get('effort', '?')})")
        return "\n".join(lines)

    # ── TODOs ──

    def add_todo(self, description: str, priority: str = "medium",
                 assignee: str = "", tags: list[str] = None):
        """Add a TODO item."""
        todo = {
            "id": hashlib.md5(description.encode()).hexdigest()[:8],
            "description": description,
            "priority": priority,
            "assignee": assignee,
            "tags": tags or [],
            "status": "open",
            "created": datetime.now().isoformat(),
        }
        self.data["todos"].append(todo)
        self.save()
        return todo["id"]

    def complete_todo(self, todo_id: str):
        """Mark a TODO as completed."""
        for t in self.data["todos"]:
            if t["id"] == todo_id:
                t["status"] = "completed"
                t["completed"] = datetime.now().isoformat()
                self.save()
                return True
        return False

    def get_todo_summary(self) -> str:
        """Return TODO summary."""
        todos = [t for t in self.data["todos"] if t["status"] == "open"]
        if not todos:
            return "No open TODOs."
        lines = [f"### TODOs ({len(todos)} open)"]
        for t in sorted(todos, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 99)):
            tags = f" ({', '.join(t['tags'])})" if t.get('tags') else ""
            lines.append(f"- [{t['priority'].upper()}]{tags} {t['description'][:100]}")
        return "\n".join(lines)

    # ── Known Bugs ──

    def add_bug(self, title: str, description: str, severity: str = "medium",
                component: str = "", workaround: str = ""):
        """Track a known bug."""
        bug = {
            "id": hashlib.md5(title.encode()).hexdigest()[:8],
            "title": title,
            "description": description,
            "severity": severity,
            "component": component,
            "workaround": workaround,
            "status": "open",
            "created": datetime.now().isoformat(),
        }
        self.data["known_bugs"].append(bug)
        self.save()
        return bug["id"]

    def fix_bug(self, bug_id: str):
        """Mark a bug as fixed."""
        for b in self.data["known_bugs"]:
            if b["id"] == bug_id:
                b["status"] = "fixed"
                b["fixed"] = datetime.now().isoformat()
                self.save()
                return True
        return False

    def get_bug_summary(self) -> str:
        """Return known bugs summary."""
        bugs = [b for b in self.data["known_bugs"] if b["status"] == "open"]
        if not bugs:
            return "No open bugs."
        lines = [f"### Known Bugs ({len(bugs)} open)"]
        for b in sorted(bugs, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 99)):
            comp = f" [{b['component']}]" if b.get('component') else ""
            lines.append(f"- [{b['severity'].upper()}]{comp} {b['title']}")
        return "\n".join(lines)

    # ── Design Decisions ──

    def add_decision(self, title: str, context: str, decision: str,
                     alternatives: list[str] = None, consequences: list[str] = None):
        """Record an architectural decision."""
        entry = {
            "id": hashlib.md5(title.encode()).hexdigest()[:8],
            "title": title,
            "context": context,
            "decision": decision,
            "alternatives": alternatives or [],
            "consequences": consequences or [],
            "created": datetime.now().isoformat(),
        }
        self.data["design_decisions"].append(entry)
        self.save()
        return entry["id"]

    def get_decision_summary(self) -> str:
        """Return design decisions summary."""
        decisions = self.data["design_decisions"]
        if not decisions:
            return "No design decisions recorded."
        lines = [f"### Design Decisions ({len(decisions)})"]
        for d in decisions[-5:]:
            lines.append(f"- **{d['title']}**: {d['decision'][:100]}")
        return "\n".join(lines)

    # ── Coding Standards ──

    def add_standard(self, rule: str, description: str, category: str = "style"):
        """Add a coding standard."""
        standard = {
            "rule": rule,
            "description": description,
            "category": category,
            "added": datetime.now().isoformat(),
        }
        self.data["coding_standards"].append(standard)
        self.save()

    def get_standards_summary(self) -> str:
        """Return coding standards summary."""
        standards = self.data["coding_standards"]
        if not standards:
            return "No coding standards recorded."
        by_category = {}
        for s in standards:
            by_category.setdefault(s["category"], []).append(s)
        lines = ["### Coding Standards"]
        for cat, items in by_category.items():
            lines.append(f"\n**{cat}:**")
            for i in items:
                lines.append(f"- {i['rule']}: {i['description'][:80]}")
        return "\n".join(lines)

    # ── Metrics ──

    def update_metrics(self, total_files: int = 0, total_lines: int = 0,
                       languages: dict = None):
        """Update project metrics."""
        self.data["metrics"]["total_files"] = total_files
        self.data["metrics"]["total_lines"] = total_lines
        if languages:
            self.data["metrics"]["languages"] = languages
        self.save()

    def get_metrics_summary(self) -> str:
        """Return metrics summary."""
        m = self.data["metrics"]
        langs = ", ".join(f"{lang}: {count}" for lang, count in list(m.get("languages", {}).items())[:5])
        return (f"Files: {m.get('total_files', '?')} | Lines: {m.get('total_lines', '?')} | "
                f"Languages: {langs or '?'}")

    # ── Complete World Model Snapshot ──

    def get_full_snapshot(self) -> str:
        """Return a complete snapshot of the world model for LLM context."""
        parts = [
            f"# World Model: {self.data['project_name']}",
            f"Last updated: {self.data['last_updated']}",
            "",
            self.get_metrics_summary(),
            "",
        ]
        
        arch = self.get_architecture_summary()
        if arch:
            parts.append(arch)
            parts.append("")
        
        debt = self.get_debt_summary()
        if debt and "No open" not in debt:
            parts.append(debt)
            parts.append("")
        
        bugs = self.get_bug_summary()
        if bugs and "No open" not in bugs:
            parts.append(bugs)
            parts.append("")
        
        todos = self.get_todo_summary()
        if todos and "No open" not in todos:
            parts.append(todos)
            parts.append("")
        
        decisions = self.get_decision_summary()
        if decisions and "No" not in decisions:
            parts.append(decisions)
            parts.append("")
        
        return "\n".join(parts)

    # ── Auto-extraction from repository ──

    def auto_extract(self, codebase_analyzer=None):
        """Automatically extract project knowledge from the codebase.
        Detects architecture layers, components, and patterns.
        """
        if codebase_analyzer is None:
            return
        
        try:
            idx = codebase_analyzer.index() if hasattr(codebase_analyzer, 'index') else {}
        except:
            return
        
        files = idx.get("files", {})
        all_paths = list(files.keys())
        all_paths_lower = [p.lower() for p in all_paths]
        
        # Detect layers from directory structure
        layers_found = set()
        for p in all_paths_lower:
            parts = p.split("/")
            for part in parts:
                if part in ("api", "routes", "controllers", "handlers"):
                    layers_found.add("API Layer")
                elif part in ("models", "entities", "schemas"):
                    layers_found.add("Data Layer")
                elif part in ("services", "usecases", "use_cases"):
                    layers_found.add("Service Layer")
                elif part in ("ui", "views", "pages", "components", "screens"):
                    layers_found.add("Presentation Layer")
                elif part in ("db", "database", "repositories", "repository"):
                    layers_found.add("Database Layer")
                elif part in ("middleware", "middlewares"):
                    layers_found.add("Middleware Layer")
                elif part in ("config", "configuration"):
                    layers_found.add("Configuration Layer")
                elif part in ("tests", "test", "__tests__"):
                    layers_found.add("Test Layer")
                elif part in ("utils", "helpers", "common", "shared"):
                    layers_found.add("Utility Layer")
                elif part in ("auth", "authentication"):
                    layers_found.add("Authentication Layer")
        
        # Detect technologies from config files
        technologies = {}
        for cfg in (idx.get("config_files", []) if hasattr(idx, 'get') else []):
            pass  # Could be enhanced
        
        # Add layers found
        for layer in sorted(layers_found):
            self.add_layer(layer, f"Auto-detected {layer}")
        
        # Detect components (top-level directories or key files)
        top_dirs = set()
        for p in all_paths:
            parts = p.split("/")
            if len(parts) >= 2:
                top_dirs.add(parts[0])
        for d in sorted(top_dirs):
            if d and not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git"):
                self.add_component(d, "Auto-detected", f"Top-level module: {d}",
                                  files=[f for f in all_paths if f.startswith(d)][:5])
        
        # Update metrics
        lang_counts = {}
        for p in all_paths:
            ext = Path(p).suffix.lower()
            if ext:
                lang_counts[ext] = lang_counts.get(ext, 0) + 1
        
        total_lines = sum(
            info.get("lines", 0) for info in files.values()
            if isinstance(info, dict)
        ) if files else 0
        
        self.update_metrics(
            total_files=len(all_paths),
            total_lines=total_lines,
            languages=lang_counts,
        )
        self.save()
