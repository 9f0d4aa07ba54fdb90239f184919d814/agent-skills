"""
REPOSITORY INTELLIGENCE ENGINE

This is the brain that understands the repository at a conceptual level.
Instead of just knowing files and symbols, it understands:
- Architecture patterns (MVC, microservices, etc.)
- Business concepts (Authentication, Payment, User Management)
- Code relationships (what calls what, what depends on what)
- Framework conventions (Django, React, FastAPI, etc.)

This is the missing piece that makes an agent truly intelligent.
"""

import json, re, time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Concept:
    """A high-level concept in the codebase (e.g., Authentication, Payment)."""
    name: str
    type: str  # "feature", "module", "service", "component"
    description: str = ""
    files: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)  # classes, functions
    related_concepts: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0-1.0


@dataclass
class Architecture:
    """High-level architecture understanding."""
    pattern: str  # "monolith", "microservices", "mvc", "layered"
    layers: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)  # lang -> file count
    entry_points: list[str] = field(default_factory=list)


class RepositoryIntelligence:
    """
    Understands the repository at a conceptual level.
    
    This goes beyond file parsing - it understands:
    - What the code does (concepts)
    - How it's organized (architecture)
    - What frameworks it uses
    - How components relate to each other
    """
    
    def __init__(self, workdir: str):
        self.workdir = Path(workdir).resolve()
        self.concepts: dict[str, Concept] = {}
        self.architecture: Optional[Architecture] = None
        self._cache = {}
        self._last_scan = 0
    
    def analyze(self, full: bool = True):
        """Run full repository analysis."""
        print("[RepoIntel] Analyzing repository...")
        start = time.time()
        
        # 1. Detect architecture and frameworks
        self.architecture = self._detect_architecture()
        print(f"  Architecture: {self.architecture.pattern}")
        print(f"  Frameworks: {', '.join(self.architecture.frameworks)}")
        
        # 2. Extract concepts
        self._extract_concepts()
        print(f"  Concepts found: {len(self.concepts)}")
        
        # 3. Build relationships
        self._build_concept_relationships()
        
        duration = time.time() - start
        print(f"[RepoIntel] Analysis complete ({duration:.1f}s)")
        self._last_scan = time.time()
    
    def _detect_architecture(self) -> Architecture:
        """Detect high-level architecture pattern."""
        arch = Architecture(pattern="unknown")
        
        # Detect frameworks
        if (self.workdir / "manage.py").exists():
            arch.frameworks.append("Django")
            arch.pattern = "mvc"
        
        if (self.workdir / "package.json").exists():
            pkg = json.loads((self.workdir / "package.json").read_text())
            deps = pkg.get("dependencies", {})
            if "react" in deps:
                arch.frameworks.append("React")
            if "next" in deps:
                arch.frameworks.append("Next.js")
            if "vue" in deps:
                arch.frameworks.append("Vue")
            if "express" in deps:
                arch.frameworks.append("Express")
        
        if (self.workdir / "requirements.txt").exists():
            reqs = (self.workdir / "requirements.txt").read_text()
            if "fastapi" in reqs.lower():
                arch.frameworks.append("FastAPI")
                arch.pattern = "api"
            if "flask" in reqs.lower():
                arch.frameworks.append("Flask")
                arch.pattern = "api"
        
        if (self.workdir / "Cargo.toml").exists():
            arch.frameworks.append("Rust")
            arch.languages["Rust"] = 1
        
        if (self.workdir / "go.mod").exists():
            arch.frameworks.append("Go")
            arch.languages["Go"] = 1
        
        # Count languages
        for ext, lang in [(".py", "Python"), (".ts", "TypeScript"), 
                          (".js", "JavaScript"), (".go", "Go"), (".rs", "Rust")]:
            count = len(list(self.workdir.rglob(f"*{ext}")))
            if count > 0:
                arch.languages[lang] = count
        
        # Detect layers
        common_dirs = ["api", "models", "views", "controllers", "services", 
                       "routes", "middleware", "utils", "core", "domain"]
        for dir_name in common_dirs:
            if (self.workdir / dir_name).is_dir():
                arch.layers.append(dir_name)
        
        # Detect microservices
        service_indicators = ["docker-compose.yml", "kubernetes"]
        if any((self.workdir / ind).exists() for ind in service_indicators):
            services = [d.name for d in self.workdir.iterdir() 
                       if d.is_dir() and (d / "Dockerfile").exists()]
            if len(services) > 1:
                arch.pattern = "microservices"
                arch.services = services
        
        return arch
    
    def _extract_concepts(self):
        """Extract high-level concepts from code."""
        # Common concept patterns
        concept_patterns = {
            "auth": ["Authentication", "feature"],
            "login": ["Authentication", "feature"],
            "user": ["User Management", "feature"],
            "payment": ["Payment", "feature"],
            "order": ["Order Management", "feature"],
            "product": ["Product", "feature"],
            "cart": ["Shopping Cart", "feature"],
            "admin": ["Admin Panel", "feature"],
            "dashboard": ["Dashboard", "feature"],
            "api": ["API Layer", "layer"],
            "db": ["Database", "layer"],
            "cache": ["Caching", "service"],
            "queue": ["Message Queue", "service"],
            "email": ["Email Service", "service"],
            "notification": ["Notifications", "service"],
        }
        
        # Scan directories and files
        for path in self.workdir.rglob("*.py"):
            if "test" in str(path) or "__pycache__" in str(path):
                continue
            
            rel_path = path.relative_to(self.workdir)
            path_str = str(rel_path).lower()
            
            # Match patterns
            for pattern, (concept_name, concept_type) in concept_patterns.items():
                if pattern in path_str:
                    if concept_name not in self.concepts:
                        self.concepts[concept_name] = Concept(
                            name=concept_name,
                            type=concept_type,
                            confidence=0.7
                        )
                    self.concepts[concept_name].files.append(str(rel_path))
            
            # Extract classes and functions
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                classes = re.findall(r'class\s+(\w+)', content)
                functions = re.findall(r'def\s+(\w+)', content)
                
                for cls in classes:
                    # Try to infer concept from class name
                    cls_lower = cls.lower()
                    for pattern, (concept_name, concept_type) in concept_patterns.items():
                        if pattern in cls_lower:
                            if concept_name not in self.concepts:
                                self.concepts[concept_name] = Concept(
                                    name=concept_name,
                                    type=concept_type,
                                    confidence=0.8
                                )
                            self.concepts[concept_name].symbols.append(cls)
            except:
                continue
    
    def _build_concept_relationships(self):
        """Build relationships between concepts."""
        # For each concept, find related concepts based on:
        # 1. Shared files
        # 2. Import relationships
        # 3. Naming patterns
        
        for concept_name, concept in self.concepts.items():
            related = set()
            
            # Find concepts that share files
            for other_name, other in self.concepts.items():
                if other_name == concept_name:
                    continue
                
                shared_files = set(concept.files) & set(other.files)
                if shared_files:
                    related.add(other_name)
            
            concept.related_concepts = list(related)
    
    def get_concept(self, name: str) -> Optional[Concept]:
        """Get a concept by name."""
        return self.concepts.get(name)
    
    def find_concepts_for_task(self, task: str) -> list[Concept]:
        """Find relevant concepts for a task."""
        task_lower = task.lower()
        relevant = []
        
        for concept in self.concepts.values():
            score = 0.0
            
            # Name match
            if concept.name.lower() in task_lower:
                score += 1.0
            
            # Keyword match
            for word in concept.name.split():
                if word.lower() in task_lower:
                    score += 0.5
            
            # Type match
            if "auth" in task_lower and "auth" in concept.name.lower():
                score += 1.0
            
            if score > 0:
                relevant.append((concept, score))
        
        # Sort by score
        relevant.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in relevant[:5]]
    
    def get_architecture_summary(self) -> str:
        """Get human-readable architecture summary."""
        if not self.architecture:
            return "Architecture not analyzed yet"
        
        lines = [
            f"Architecture Pattern: {self.architecture.pattern}",
            f"Frameworks: {', '.join(self.architecture.frameworks) or 'None detected'}",
            f"Languages: {', '.join(f'{lang} ({count} files)' for lang, count in self.architecture.languages.items())}",
        ]
        
        if self.architecture.layers:
            lines.append(f"Layers: {', '.join(self.architecture.layers)}")
        
        if self.architecture.services:
            lines.append(f"Services: {', '.join(self.architecture.services)}")
        
        lines.append(f"\nConcepts found: {len(self.concepts)}")
        for concept in list(self.concepts.values())[:10]:
            lines.append(f"  - {concept.name} ({concept.type}): {len(concept.files)} files")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "architecture": {
                "pattern": self.architecture.pattern if self.architecture else "unknown",
                "frameworks": self.architecture.frameworks if self.architecture else [],
                "languages": self.architecture.languages if self.architecture else {},
            },
            "concepts": {
                name: {
                    "type": c.type,
                    "files": c.files,
                    "symbols": c.symbols,
                    "related": c.related_concepts,
                    "confidence": c.confidence,
                }
                for name, c in self.concepts.items()
            },
            "last_scan": self._last_scan,
        }
