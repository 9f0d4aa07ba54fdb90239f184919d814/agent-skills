"""
CONTEXT ENGINE — The pre-LLM intelligence layer.
Gathers project context, builds symbol index, resolves dependencies,
selects relevant files, and formats context for the LLM.
No LLM calls here — pure deterministic engineering.
"""

import json, os, re, time, hashlib, subprocess
from pathlib import Path
from typing import Optional
from collections import defaultdict


class ContextEngine:
    """
    Gathers relevant context from the repository BEFORE any LLM call.
    
    Pipeline:
    1. Scan repo → index files, symbols, dependencies
    2. Parse task → extract keywords, symbols, file references
    3. Find relevant files → score by keyword/symbol match
    4. Build context package → selected files, configs, README, deps
    5. Format → compact Markdown for LLM consumption
    
    The LLM is NOT called here. This is all deterministic code.
    """

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self._codebase = None  # Lazy import to avoid circular deps
        self._cache = {}
        self._scan_time = 0

    def _get_codebase(self):
        if self._codebase is None:
            from limbs.tools.codebase import CodebaseAnalyzer
            self._codebase = CodebaseAnalyzer(self.workdir)
        return self._codebase

    # ── Pipeline Step 1: Analyze Task ──

    def analyze_task(self, task: str) -> dict:
        """
        Break down a task into its components.
        Identifies: file paths, symbol names, action verbs, technologies.
        """
        STOP_WORDS = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "shall", "can", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "out", "off", "over", "under", "again", "then",
            "once", "here", "there", "when", "where", "why", "how", "all",
            "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "because", "and", "but",
            "or", "if", "while", "about", "up", "this", "that", "these",
            "those", "it", "its", "please", "make", "add", "change",
            "update", "fix", "remove", "create", "new", "implement",
            "need", "want", "like", "work", "things", "stuff",
        }

        # Extract potential file paths
        file_paths = re.findall(r'(?:`)?([\w./\\]+\.\w+)(?:`)?', task)
        file_paths = [p for p in file_paths if len(p) > 3]

        # Extract symbol names (CamelCase, snake_case)
        camel_case = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', task)
        snake_case = re.findall(r'\b[a-z]+_[a-z_0-9]+\b', task)

        # Extract action verbs
        actions = re.findall(r'\b(add|update|fix|remove|create|change|delete|'
                            r'implement|refactor|optimize|test|debug|build|'
                            r'deploy|migrate|rename|move|copy|merge|split)\b',
                            task, re.IGNORECASE)

        # Extract keywords
        words = re.findall(r'[A-Z][a-z]+|[a-z]+|[A-Z]+', task)
        symbols_in_task = re.findall(r'(\w+(?:\.\w+)*(?:\(\))?)', task)

        keywords = []
        for w in words + symbols_in_task:
            wl = w.lower().strip("()")
            if len(wl) > 2 and wl not in STOP_WORDS:
                keywords.append(wl)

        return {
            "keywords": list(set(keywords)),
            "file_paths": list(set(file_paths)),
            "symbol_names": list(set(camel_case + snake_case)),
            "actions": list(set(a.lower() for a in actions)),
            "task_type": self._classify_task(keywords, actions),
        }

    def _classify_task(self, keywords: list[str], actions: list[str]) -> str:
        kw_set = set(kw.lower() for kw in keywords)
        act_set = set(a.lower() for a in actions)

        if "test" in kw_set or "test" in act_set:
            return "testing"
        if "debug" in act_set or "fix" in act_set or "error" in kw_set:
            return "debugging"
        if "refactor" in act_set or "optimize" in act_set:
            return "refactoring"
        if "deploy" in act_set:
            return "deployment"
        if "add" in act_set or "create" in act_set or "implement" in act_set:
            return "feature_addition"
        if "update" in act_set or "change" in act_set or "modify" in act_set:
            return "modification"
        return "general"

    # ── Pipeline Step 2: Find Relevant Files ──

    def find_relevant_files(self, task_analysis: dict, max_files: int = 8) -> dict:
        """
        Find the most relevant files for a task.
        Matches by: keywords, symbol names, file paths, dependency proximity.
        """
        cb = self._get_codebase()
        idx = cb.index()
        keywords = task_analysis.get("keywords", [])
        symbol_names = task_analysis.get("symbol_names", [])
        file_paths_hint = task_analysis.get("file_paths", [])

        all_terms = list(set(keywords + [s.lower() for s in symbol_names]))
        scored_files = self._score_files(all_terms, idx)

        # Essential files always included
        essential = set()
        for f in idx.get("config_files", []):
            essential.add(f)
        for f in idx.get("readme_files", []):
            essential.add(f)

        # Add explicitly mentioned files
        for hint in file_paths_hint:
            normalized = hint.replace("\\", "/")
            for f in idx.get("files", {}):
                if normalized in f or f.endswith(normalized):
                    essential.add(f)

        # Select top files
        selected = list(essential)
        for f, score in scored_files:
            if f not in selected:
                selected.append(f)
            if len(selected) >= max_files:
                break

        # Read file contents
        contents = {}
        for f in selected:
            try:
                path = Path(self.workdir, f)
                if path.exists():
                    content = path.read_text(encoding="utf-8", errors="replace")
                    if len(content) > 10000:
                        content = content[:5000] + f"\n... (truncated from {len(content)} bytes)"
                    contents[f] = content
            except:
                continue

        # Find symbol locations
        symbols = {}
        for term in all_terms:
            found = cb.find_symbol(term)
            for cls in found.get("classes", []):
                symbols[cls["name"]] = {"kind": "class", "files": cls["files"]}
            for func in found.get("functions", []):
                symbols[func["name"]] = {"kind": "function", "files": func["files"]}

        # Build dependency context
        deps = {}
        for f in selected:
            node = cb._dep_graph.get(f) if hasattr(cb, '_dep_graph') else None
            if node:
                deps[f] = {
                    "imports": node.imports[:5],
                    "imported_by": node.imported_by[:5],
                }

        return {
            "selected": selected,
            "contents": contents,
            "symbols": symbols,
            "dependencies": deps,
            "total_project_files": idx.get("total_files", 0),
            "total_project_lines": idx.get("total_lines", 0),
            "project_languages": dict(idx.get("languages", {})),
        }

    def _score_files(self, terms: list[str], idx: dict) -> list[tuple[str, float]]:
        """Score files by relevance to search terms."""
        scores = []
        for rel, info in idx.get("files", {}).items():
            score = 0.0
            rl = rel.lower()
            for term in terms:
                if term in rl:
                    score += 3.0
                for cls in info.get("classes", []):
                    if term in cls.lower():
                        score += 2.0
                for func in info.get("functions", []):
                    if term in func.lower():
                        score += 2.0
                for imp in info.get("imports", []):
                    if term in imp.lower():
                        score += 1.0
            if score > 0:
                scores.append((rel, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:20]

    # ── Pipeline Step 3: Build Context for LLM ──

    def build_llm_context(self, task: str, max_files: int = 8) -> str:
        """
        Build a complete context package for the LLM.
        This is the main entry point — returns a formatted string.
        
        What's included:
        1. Project overview (name, languages, size)
        2. Config files (package.json, README, etc.)
        3. Relevant source files (selected by task keywords)
        4. Symbol definitions found in the task
        5. Dependency subgraph of relevant files
        6. Previous task context (if any)
        
        The result is compact and focused — NOT the entire codebase.
        """
        start = time.time()

        # Step 1: Analyze task
        task_info = self.analyze_task(task)
        keywords = task_info.get("keywords", [])

        # Step 2: Find relevant files
        file_info = self.find_relevant_files(task_info, max_files=max_files)
        selected = file_info.get("selected", [])
        contents = file_info.get("contents", {})
        symbols = file_info.get("symbols", {})
        deps = file_info.get("dependencies", {})
        config_files = self._get_config_summary()

        # Step 3: Format everything
        parts = []

        # ── Project Header ──
        parts.append(f"# Project: {Path(self.workdir).name}")
        parts.append(f"Task: {task}")
        parts.append(f"Task Type: {task_info.get('task_type', 'general')}")
        parts.append(f"Keywords: {', '.join(keywords[:10])}")
        parts.append(f"Files in project: {file_info.get('total_project_files', '?')} "
                     f"| Lines: {file_info.get('total_project_lines', '?')}")
        parts.append("")

        # ── Config Files ──
        if config_files:
            parts.append("## Configuration")
            for cf in config_files[:3]:
                parts.append(f"### {cf['path']}")
                parts.append(f"```\n{cf['content'][:1000]}\n```")
            parts.append("")

        # ── Relevant Files ──
        parts.append(f"## Relevant Files ({len(selected)} selected from "
                     f"{file_info.get('total_project_files', '?')} total)")
        parts.append(f"Selection: {', '.join(selected[:10])}")
        parts.append("")

        for fpath in selected[:max_files]:
            content = contents.get(fpath, "")
            if not content:
                continue
            parts.append(f"### {fpath}")
            # Show file overview (first 30 lines and last 10 lines)
            lines = content.split("\n")
            if len(lines) > 40:
                preview = lines[:25] + ["... (skipping middle)"] + lines[-5:]
            else:
                preview = lines
            lang = Path(fpath).suffix.lstrip(".") or "text"
            parts.append(f"```{lang}")
            parts.extend(preview[:35])
            parts.append("```")
            parts.append("")

        # ── Symbols Found ──
        if symbols:
            parts.append(f"## Symbols Referenced in Task")
            for sym_name, sym_info in list(symbols.items())[:10]:
                files_str = ", ".join(sym_info.get("files", [])[:3])
                parts.append(f"- `{sym_name}` ({sym_info.get('kind', '?')}) → {files_str}")
            parts.append("")

        # ── Dependency Context ──
        if deps:
            parts.append("## Dependency Relationships")
            for fpath, dep_info in deps.items():
                rel_info = []
                if dep_info.get("imports"):
                    rel_info.append(f"imports: {', '.join(dep_info['imports'][:3])}")
                if dep_info.get("imported_by"):
                    rel_info.append(f"used by: {', '.join(dep_info['imported_by'][:3])}")
                if rel_info:
                    parts.append(f"- {fpath}: {'; '.join(rel_info)}")
            parts.append("")

        elapsed = time.time() - start
        parts.append(f"--- Context built in {elapsed:.1f}s | "
                     f"{len(selected)} files | {len(symbols)} symbols ---")

        context = "\n".join(parts)

        # Keep context manageable — truncate if too large
        if len(context) > 30000:
            context = context[:25000] + "\n\n... (context truncated to 25K chars) ..."

        return context

    def _get_config_summary(self) -> list[dict]:
        """Get config files with short content preview."""
        cb = self._get_codebase()
        return cb.get_config_files()

    # ── Pipeline Step 4: Generate Plan ──

    def generate_plan_structure(self, task: str, task_info: dict = None) -> list[dict]:
        """
        Generate a structured task plan WITHOUT calling the LLM.
        Uses deterministic rules based on task type and keywords.
        The LLM will fill in the details, but the structure is pre-built.
        """
        if task_info is None:
            task_info = self.analyze_task(task)

        task_type = task_info.get("task_type", "general")
        keywords = task_info.get("keywords", [])
        actions = task_info.get("actions", [])
        symbols = task_info.get("symbol_names", [])

        plan = []

        if task_type == "testing":
            plan = [
                {"step": 1, "action": "find_test_files", "desc": "Locate existing test files"},
                {"step": 2, "action": "identify_test_framework", "desc": "Detect test framework (pytest, jest, etc.)"},
                {"step": 3, "action": "run_tests", "desc": "Run existing tests to check current state"},
                {"step": 4, "action": "implement_changes", "desc": "Add/modify tests as needed"},
                {"step": 5, "action": "verify", "desc": "Run tests again and fix any failures"},
            ]

        elif task_type == "debugging":
            plan = [
                {"step": 1, "action": "read_error", "desc": "Understand the error/bug"},
                {"step": 2, "action": "find_relevant_code", "desc": "Locate the source of the bug"},
                {"step": 3, "action": "diagnose", "desc": "Analyze root cause"},
                {"step": 4, "action": "fix", "desc": "Apply the fix"},
                {"step": 5, "action": "verify", "desc": "Run tests/build to confirm fix"},
            ]

        elif task_type == "refactoring":
            plan = [
                {"step": 1, "action": "understand_code", "desc": "Read current implementation"},
                {"step": 2, "action": "plan_changes", "desc": "Design the new structure"},
                {"step": 3, "action": "refactor", "desc": "Apply changes incrementally"},
                {"step": 4, "action": "update_tests", "desc": "Update tests for new structure"},
                {"step": 5, "action": "verify", "desc": "Run tests and fix issues"},
            ]

        elif task_type == "feature_addition":
            plan = [
                {"step": 1, "action": "find_integration_points", "desc": "Find where to add the feature"},
                {"step": 2, "action": "read_dependencies", "desc": "Understand existing APIs and contracts"},
                {"step": 3, "action": "implement", "desc": "Add the new feature"},
                {"step": 4, "action": "integrate", "desc": "Connect with existing code"},
                {"step": 5, "action": "verify", "desc": "Test the new feature"},
            ]

        else:
            # Generic plan
            plan = [
                {"step": 1, "action": "explore", "desc": "Scan relevant files"},
                {"step": 2, "action": "understand", "desc": "Analyze existing code structure"},
                {"step": 3, "action": "implement", "desc": "Make the required changes"},
                {"step": 4, "action": "verify", "desc": "Validate the changes"},
            ]

        return plan

    # ── Incremental Context Builder ──

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self._codebase = None
        self._cache = {}
        self._scan_time = 0
        self._file_mtimes: dict[str, float] = {}  # Track file modification times
        self._context_snapshot: Optional[str] = None  # Last built context
        self._snapshot_key: str = ""  # Task hash that produced the snapshot
        self._changed_files: list[str] = []

    def invalidate_cache(self):
        """Force re-scan on next context build."""
        self._scan_time = 0
        self._file_mtimes = {}
        self._context_snapshot = None
        if self._codebase:
            self._codebase._index = None

    def get_changed_files(self) -> list[str]:
        """Return files that have changed since last scan."""
        return self._changed_files

    def _check_file_changes(self) -> list[str]:
        """Check which files have been modified since last scan.
        Returns a list of changed file paths.
        """
        changed = []
        try:
            # Use git if available for efficient change detection
            r = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=self.workdir
            )
            if r.returncode == 0 and r.stdout.strip():
                changed = [f for f in r.stdout.strip().split("\n") if f]
                self._changed_files = changed
                return changed
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: check mtimes
        changed = []
        for fpath in list(self._file_mtimes.keys()):
            p = Path(self.workdir, fpath)
            if p.exists():
                mtime = p.stat().st_mtime
                if mtime > self._file_mtimes.get(fpath, 0):
                    changed.append(fpath)
            else:
                changed.append(fpath)

        # Scan for new files
        if self._file_mtimes:
            for ext in [".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".dart"]:
                for p in Path(self.workdir).rglob(f"*{ext}"):
                    rel = str(p.relative_to(self.workdir))
                    if rel not in self._file_mtimes:
                        changed.append(rel)

        self._changed_files = changed
        return changed

    def _update_mtime_cache(self):
        """Update the mtime cache with current files."""
        cb = self._get_codebase()
        try:
            idx = cb.scan() if hasattr(cb, 'scan') else cb.index()
        except:
            return
        for fpath in idx.get("files", {}):
            p = Path(self.workdir, fpath)
            if p.exists():
                self._file_mtimes[fpath] = p.stat().st_mtime

    def build_incremental_context(self, task: str, max_files: int = 8) -> dict:
        """Build context incrementally — only re-index changed files.
        
        Returns:
            {"context": str, "incremental": bool, "changed_files": list,
             "full_context": str, "delta": str}
        """
        task_hash = hashlib.md5(task.encode()).hexdigest()[:12]
        changed = self._check_file_changes()
        
        is_incremental = bool(self._context_snapshot and not changed)
        
        if not changed and self._context_snapshot and self._snapshot_key == task_hash:
            # No changes — return cached context
            return {
                "context": self._context_snapshot,
                "incremental": True,
                "changed_files": [],
                "delta": "(cached, no changes)",
            }
        
        # Build full context
        context = self.build_llm_context(task, max_files=max_files)
        
        # Compute delta if we had a previous snapshot
        delta = ""
        if changed:
            delta = f"Changed files: {', '.join(changed[:10])}\n"
        elif self._context_snapshot:
            delta = "(no file changes, only task differs)"
        
        # Cache the result
        self._context_snapshot = context
        self._snapshot_key = task_hash
        self._update_mtime_cache()
        
        return {
            "context": context,
            "incremental": is_incremental,
            "changed_files": changed,
            "delta": delta,
        }

    def extract_project_knowledge(self) -> dict:
        """Extract structured knowledge about the project.
        Returns frameworks, patterns, conventions detected.
        """
        knowledge = {
            "frameworks": [],
            "languages": [],
            "patterns": [],
            "key_files": [],
            "dependencies": [],
        }

        cb = self._get_codebase()
        idx = cb.index() if hasattr(cb, 'index') else {}

        # Detect languages
        knowledge["languages"] = list(idx.get("languages", {}).keys())

        # Detect frameworks from config files
        for cfg in self._get_config_summary():
            content = cfg.get("content", "")
            path = cfg.get("path", "")

            if "package.json" in path:
                if '"react"' in content:
                    knowledge["frameworks"].append("React")
                if '"vue"' in content:
                    knowledge["frameworks"].append("Vue")
                if '"angular"' in content:
                    knowledge["frameworks"].append("Angular")
                if '"next"' in content or '"next.js"' in content.lower():
                    knowledge["frameworks"].append("Next.js")
                if '"express"' in content:
                    knowledge["frameworks"].append("Express")
                if '"jest"' in content or '"vitest"' in content:
                    knowledge["frameworks"].append("Jest/Vitest")

            elif "requirements.txt" in path or "pyproject.toml" in path:
                if "django" in content:
                    knowledge["frameworks"].append("Django")
                if "flask" in content:
                    knowledge["frameworks"].append("Flask")
                if "fastapi" in content:
                    knowledge["frameworks"].append("FastAPI")
                if "pytest" in content:
                    knowledge["frameworks"].append("pytest")
                if "sqlalchemy" in content:
                    knowledge["frameworks"].append("SQLAlchemy")
                if "torch" in content or "tensorflow" in content:
                    knowledge["frameworks"].append("PyTorch/TensorFlow")

            elif "Cargo.toml" in path:
                knowledge["frameworks"].append("Cargo/Rust")

            elif "go.mod" in path:
                knowledge["frameworks"].append("Go Modules")

            elif "pubspec.yaml" in path:
                knowledge["frameworks"].append("Flutter/Dart")

        # Detect architecture patterns
        all_files = idx.get("files", {})
        file_paths = list(all_files.keys())
        all_content = " ".join(file_paths).lower()

        if any("controller" in f for f in file_paths):
            knowledge["patterns"].append("MVC (Controllers detected)")
        if any("service" in f for f in file_paths):
            knowledge["patterns"].append("Service Layer")
        if any("repository" in f for f in file_paths):
            knowledge["patterns"].append("Repository Pattern")
        if any("provider" in f for f in file_paths):
            knowledge["patterns"].append("Provider Pattern")
        if any("hook" in f for f in file_paths) or any("use" in f and f.endswith(".ts") for f in file_paths):
            knowledge["patterns"].append("React Hooks")
        if any("middleware" in f for f in file_paths):
            knowledge["patterns"].append("Middleware Pattern")
        if "redux" in all_content or "zustand" in all_content:
            knowledge["patterns"].append("State Management")

        # Key files
        for f in file_paths:
            if any(kw in f.lower() for kw in ["main.", "app.", "index.", "router", "routes", "config"]):
                knowledge["key_files"].append(f)

        # De-duplicate
        knowledge["frameworks"] = list(set(knowledge["frameworks"]))
        knowledge["patterns"] = list(set(knowledge["patterns"]))
        knowledge["key_files"] = knowledge["key_files"][:10]

        return knowledge
