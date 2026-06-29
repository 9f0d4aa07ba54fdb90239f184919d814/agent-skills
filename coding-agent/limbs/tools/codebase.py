"""
LIMB: Codebase Understanding Engine
Repository scanner + Symbol index + Dependency graph + Fast search.
No LLM needed — pure deterministic code analysis.
"""

import json, os, re, subprocess, time
from pathlib import Path
from collections import defaultdict
from typing import Optional


# Language-specific definition patterns
DEFINITION_PATTERNS = {
    ".py": {
        "classes": r'^\s*class\s+(\w+)',
        "functions": r'^\s*(?:async\s+)?def\s+(\w+)',
        "imports": r'^(?:from\s+\S+\s+)?import\s+\S+',
    },
    ".js": {
        "classes": r'^\s*class\s+(\w+)',
        "functions": r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        "imports": r'^(?:import\s+)',
    },
    ".ts": {
        "classes": r'^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)',
        "functions": r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        "imports": r'^(?:import\s+)',
    },
    ".tsx": {
        "classes": r'^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)',
        "functions": r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        "imports": r'^(?:import\s+)',
    },
    ".jsx": {
        "classes": r'^\s*class\s+(\w+)',
        "functions": r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        "imports": r'^(?:import\s+)',
    },
    ".go": {
        "classes": r'^\s*type\s+(\w+)\s+struct',
        "functions": r'^\s*func\s+(?:\([^)]*\)\s+)?(\w+)',
        "imports": r'^\s*import',
    },
    ".rs": {
        "classes": r'^\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+(\w+)',
        "functions": r'^\s*(?:pub\s+)?(?:unsafe\s+)?fn\s+(\w+)',
        "imports": r'^\s*(?:use\s+|pub\s+use\s+)',
    },
    ".dart": {
        "classes": r'^\s*(?:class|abstract\s+class|mixin|enum)\s+(\w+)',
        "functions": r'^\s*(?:[A-Z]\w+\s+)?(\w+)\s*\([^)]*\)\s*\{',
        "imports": r'^\s*import\s+',
    },
}

EXCLUDED_DIRS = {
    "__pycache__", ".git", ".venv", "node_modules", ".tox", ".eggs",
    "env", "venv", ".mypy_cache", ".pytest_cache", ".next", "dist",
    "build", ".svelte-kit", ".dart_tool", ".packages", "coverage",
    ".vscode", ".idea", "target", "bin", "obj", ".gradle",
}
EXCLUDED_EXTS = {
    ".pyc", ".pyo", ".so", ".o", ".class", ".jar", ".dll", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".tar", ".gz", ".bz2",
    ".exe", ".dmg", ".pdb", ".lib", ".obj", ".ilk",
}


class Symbol:
    """A code symbol with location and metadata."""
    def __init__(self, name: str, kind: str, file_path: str, line: int,
                 parent: str = ""):
        self.name = name
        self.kind = kind
        self.file_path = file_path
        self.line = line
        self.parent = parent
        self.references = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name, "kind": self.kind,
            "file": self.file_path, "line": self.line,
            "parent": self.parent,
        }


class DependencyNode:
    """Represents a file's dependency relationships."""
    def __init__(self, path: str):
        self.path = path
        self.imports: list[str] = []
        self.imported_by: list[str] = []
        self.symbols: list[str] = []

    def to_dict(self) -> dict:
        return {
            "path": self.path, "imports": self.imports[:10],
            "imported_by": self.imported_by[:10],
            "symbols": self.symbols[:10],
        }


class CodebaseAnalyzer:
    """
    Intelligent codebase scanner and symbol indexer.
    Features:
    - Recursive file scanning with smart exclusions
    - Multi-language symbol extraction (classes, functions, imports)
    - Dependency graph construction
    - Fast text search (ripgrep if available, fallback to Python)
    - Context building for LLM prompts (selects only relevant files)
    """

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self._index: Optional[dict] = None
        self._symbols: list[Symbol] = []
        self._symbol_lookup: dict[str, list[Symbol]] = {}
        self._dep_graph: dict[str, DependencyNode] = {}
        self._last_scan_time = 0
        self._ripgrep_available = self._check_ripgrep()

    def _check_ripgrep(self) -> bool:
        try:
            r = subprocess.run(["rg", "--version"], capture_output=True, text=True, timeout=3)
            return r.returncode == 0
        except:
            return False

    # ── Phase 1: Repository Scan ──

    def scan(self, force: bool = False) -> dict:
        """Scan the repository and build a comprehensive file index."""
        if self._index and not force:
            return self._index

        idx = {
            "files": {}, "file_tree": [],
            "imports": defaultdict(list),
            "classes": defaultdict(list),
            "functions": defaultdict(list),
            "symbols": defaultdict(list),
            "total_lines": 0, "total_files": 0,
            "languages": defaultdict(int),
            "large_files": [], "config_files": [], "readme_files": [],
        }
        self._symbols = []

        for f in Path(self.workdir).rglob("*"):
            if any(p in f.parts for p in EXCLUDED_DIRS):
                continue
            if f.suffix.lower() in EXCLUDED_EXTS:
                continue
            if not f.is_file() or f.stat().st_size > 5_000_000:
                continue

            try:
                rel = str(f.relative_to(self.workdir))
                ext = f.suffix.lower()
                idx["languages"][ext] += 1
                idx["total_files"] += 1
                if self._is_binary(f):
                    continue

                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")
                idx["total_lines"] += len(lines)

                info = {
                    "path": rel, "lines": len(lines), "size": f.stat().st_size,
                    "ext": ext, "imports": [], "classes": [],
                    "functions": [], "summary": lines[0] if lines else "",
                }
                self._parse_file_symbols(rel, ext, lines, info, idx)
                idx["files"][rel] = info
                idx["file_tree"].append(rel)

                # Track special files
                bn = f.name.lower()
                if bn in ("readme.md", "readme.txt", "readme"):
                    idx["readme_files"].append(rel)
                if bn in ("package.json", "pubspec.yaml", "cargo.toml",
                          "pyproject.toml", "go.mod", "gemfile",
                          "requirements.txt", "setup.py", "composer.json"):
                    idx["config_files"].append(rel)
                if len(lines) > 2000:
                    idx["large_files"].append({"path": rel, "lines": len(lines)})
            except:
                continue

        self._index = idx
        self._last_scan_time = time.time()
        self._build_symbol_lookup()
        self._build_dependency_graph(idx)
        return idx

    def _is_binary(self, path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                return b"\0" in f.read(1024)
        except:
            return True

    def _parse_file_symbols(self, rel, ext, lines, info, idx):
        patterns = DEFINITION_PATTERNS.get(ext, {})
        class_pat = patterns.get("classes", "")
        func_pat = patterns.get("functions", "")
        imp_pat = patterns.get("imports", "")

        for i, raw in enumerate(lines[:2000]):
            sline = raw.strip()
            line_num = i + 1

            if class_pat:
                m = re.search(class_pat, sline)
                if m:
                    name = m.group(1)
                    info["classes"].append(name)
                    idx["classes"][name].append(rel)
                    idx["symbols"][rel].append({"name": name, "kind": "class", "line": line_num})
                    self._symbols.append(Symbol(name, "class", rel, line_num))

            if func_pat:
                m = re.search(func_pat, sline)
                if m:
                    name = m.group(1) or ""
                    if name and name not in ("if", "for", "while", "with"):
                        info["functions"].append(name)
                        idx["functions"][name].append(rel)
                        idx["symbols"][rel].append({"name": name, "kind": "function", "line": line_num})
                        self._symbols.append(Symbol(name, "function", rel, line_num))

            if imp_pat and re.search(imp_pat, sline):
                info["imports"].append(sline)
                idx["imports"][rel].append(sline)

    def _build_symbol_lookup(self):
        self._symbol_lookup = {}
        for sym in self._symbols:
            key = sym.name.lower()
            if key not in self._symbol_lookup:
                self._symbol_lookup[key] = []
            self._symbol_lookup[key].append(sym)

    def _build_dependency_graph(self, idx):
        deps = {}
        for rel in idx["files"]:
            deps[rel] = DependencyNode(rel)
        for fpath, imports in idx["imports"].items():
            for imp in imports:
                targets = self._resolve_import_targets(imp, fpath, idx)
                for t in targets:
                    if t in deps:
                        deps[fpath].imports.append(t)
                        deps[t].imported_by.append(fpath)
        for rel, syms in idx["symbols"].items():
            if rel in deps:
                deps[rel].symbols = [s["name"] for s in syms]
        self._dep_graph = deps

    def _resolve_import_targets(self, imp, source_path, idx):
        targets = []
        m = re.match(r'from\s+(\S+)\s+import', imp)
        if m:
            mod = m.group(1).replace(".", "/")
            for c in [f"{mod}.py", f"{mod}/__init__.py"]:
                for f in idx["files"]:
                    if f.endswith(c) or f == c:
                        targets.append(f)
            return targets[:3]
        m = re.match(r'import\s+(\S+)', imp)
        if m:
            mod = m.group(1).replace(".", "/")
            for f in idx["files"]:
                if f.endswith(f"{mod}.py") or f.endswith(f"{mod}/__init__.py"):
                    targets.append(f)
            return targets[:3]
        m = re.search(r"""['"](\.[^'"]+)['"]""", imp)
        if m:
            rel_path = m.group(1)
            src_dir = Path(source_path).parent
            full = (Path(self.workdir) / src_dir / rel_path).resolve()
            for ext in [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"]:
                candidate = str(full) + ext if not full.name.endswith(ext) else str(full)
                for f in idx["files"]:
                    if str(Path(self.workdir, f).resolve()) == candidate:
                        targets.append(f)
            return targets[:3]
        return targets

    # ── Phase 2: Fast Search ──

    def fast_search(self, query: str, file_pattern: str = "", max_results: int = 30) -> list[dict]:
        """Search codebase using ripgrep if available, with Python fallback."""
        if self._ripgrep_available:
            return self._ripgrep_search(query, file_pattern, max_results)
        return self._python_search(query, file_pattern, max_results)

    def _ripgrep_search(self, query, file_pattern, max_results):
        cmd = ["rg", "--json", "-n"]
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        cmd.extend([query, self.workdir])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            results = []
            for line in r.stdout.split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        d = data["data"]
                        results.append({
                            "file": d["path"]["text"],
                            "line": d["line_number"],
                            "content": d["lines"]["text"].strip()[:150],
                        })
                except:
                    continue
            return results[:max_results]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._ripgrep_available = False
            return self._python_search(query, file_pattern, max_results)

    def _python_search(self, query, file_pattern, max_results):
        results = []
        for f in Path(self.workdir).rglob(file_pattern or "*"):
            if any(p in f.parts for p in EXCLUDED_DIRS):
                continue
            if f.is_file() and f.stat().st_size < 500000:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(content.split("\n"), 1):
                        if query in line:
                            results.append({
                                "file": str(f.relative_to(self.workdir)),
                                "line": i,
                                "content": line.strip()[:150],
                            })
                            if len(results) >= max_results:
                                return results
                except:
                    continue
        return results[:max_results]

    # ── Phase 3: Context Building ──

    def get_context_for_task(self, task: str, max_files: int = 8) -> dict:
        """
        Build the minimal context for an LLM to work on a task.
        This is the core of context engineering — selects only relevant files.
        Called BEFORE the LLM, not by the LLM.
        """
        idx = self.index()
        keywords = self._extract_keywords(task)
        scored_files = self._score_files_for_task(keywords, idx)

        # Always include config files and README
        essential = set()
        for f in idx.get("config_files", []):
            essential.add(f)
        for f in idx.get("readme_files", []):
            essential.add(f)

        selected = list(essential)
        for f, score in scored_files:
            if f not in selected:
                selected.append(f)
            if len(selected) >= max_files:
                break

        file_contents = {}
        for f in selected:
            try:
                path = Path(self.workdir, f)
                if path.exists():
                    content = path.read_text(encoding="utf-8", errors="replace")
                    if len(content) > 10000:
                        content = content[:5000] + f"\n... (truncated, {len(content)} total bytes)"
                    file_contents[f] = content
            except:
                continue

        symbols = {}
        for kw in keywords:
            found = self.find_symbol(kw)
            for cls in found.get("classes", []):
                symbols[cls["name"]] = cls
            for func in found.get("functions", []):
                symbols[func["name"]] = func

        return {
            "project_overview": self._build_project_overview(idx),
            "task_keywords": keywords,
            "selected_files": selected,
            "file_contents": file_contents,
            "symbols": symbols,
            "dependency_context": self._build_dependency_context(selected),
        }

    def _extract_keywords(self, text: str) -> list[str]:
        STOP_WORDS = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "because",
            "and", "but", "or", "if", "while", "about", "up", "this",
            "that", "these", "those", "it", "its", "please", "make",
            "add", "change", "update", "fix", "remove", "create", "new",
        }
        words = re.findall(r'[A-Z][a-z]+|[a-z]+', text)
        syms = re.findall(r'(\w+(?:\.\w+)*(?:\(\))?)', text)
        keywords = []
        for w in words + syms:
            wl = w.lower().strip("()")
            if len(wl) > 2 and wl not in STOP_WORDS:
                keywords.append(wl)
        return list(set(keywords))

    def _score_files_for_task(self, keywords, idx):
        scores = []
        for rel, info in idx.get("files", {}).items():
            score = 0.0
            rl = rel.lower()
            for kw in keywords:
                if kw in rl:
                    score += 3.0
                for cls in info.get("classes", []):
                    if kw in cls.lower():
                        score += 2.0
                for func in info.get("functions", []):
                    if kw in func.lower():
                        score += 2.0
                for imp in info.get("imports", []):
                    if kw in imp.lower():
                        score += 1.0
            if score > 0:
                scores.append((rel, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:20]

    def _build_project_overview(self, idx):
        lines = [f"Project: {Path(self.workdir).name}",
                 f"  Files: {idx['total_files']} | Lines: {idx['total_lines']}"]
        langs = dict(sorted(idx["languages"].items(), key=lambda x: x[1], reverse=True)[:5])
        lang_str = ", ".join(f"{k}: {v}" for k, v in langs.items())
        lines.append(f"  Languages: {lang_str}")
        top_c = sorted(idx["classes"].items(), key=lambda x: len(x[1]), reverse=True)[:5]
        if top_c:
            lines.append(f"  Top classes: {', '.join(c for c, _ in top_c)}")
        return "\n".join(lines)

    def _build_dependency_context(self, selected_files):
        parts = []
        for f in selected_files:
            node = self._dep_graph.get(f)
            if node and (node.imports or node.imported_by):
                deps = []
                if node.imports:
                    deps.append(f"imports: {', '.join(node.imports[:5])}")
                if node.imported_by:
                    deps.append(f"used by: {', '.join(node.imported_by[:5])}")
                parts.append(f"  {f}\n    {', '.join(deps)}")
        if not parts:
            return ""
        return "Dependencies:\n" + "\n".join(parts[:20])

    # ── Public API ──

    def index(self, force: bool = False) -> dict:
        return self.scan(force)

    def find_references(self, name: str) -> list[str]:
        results = set()
        for fpath, finfo in self.index().get("files", {}).items():
            try:
                content = Path(self.workdir, fpath).read_text(encoding="utf-8", errors="replace")
                if name in content:
                    for i, line in enumerate(content.split("\n"), 1):
                        if name in line:
                            results.add(f"{fpath}:{i}: {line.strip()[:120]}")
            except:
                continue
        return sorted(results)[:30]

    def find_symbol(self, symbol: str) -> dict:
        idx = self.index()
        sl = symbol.lower()
        result = {"classes": [], "functions": [], "in_files": []}
        for cls, files in idx.get("classes", {}).items():
            if sl in cls.lower():
                result["classes"].append({"name": cls, "files": files})
        for func, files in idx.get("functions", {}).items():
            if sl in func.lower():
                result["functions"].append({"name": func, "files": files})
        for f in idx.get("files", {}):
            if sl in f.lower():
                result["in_files"].append(f)
        return result

    def codebase_overview(self) -> dict:
        idx = self.index()
        return {
            "total_files": idx["total_files"],
            "total_lines": idx["total_lines"],
            "languages": dict(idx["languages"]),
            "project_name": Path(self.workdir).name,
            "ripgrep_available": self._ripgrep_available,
            "file_tree_sample": idx["file_tree"][:20],
        }

    def dependency_graph(self) -> dict:
        self.index()
        return {f: n.to_dict() for f, n in self._dep_graph.items()}

    def similar_files(self, path: str, top_n: int = 5) -> list[dict]:
        idx = self.index()
        target = idx["files"].get(path)
        if not target:
            return []
        ti = set(target.get("imports", []))
        tc = set(target.get("classes", []))
        tf = set(target.get("functions", []))
        scores = []
        for fpath, fi in idx["files"].items():
            if fpath == path:
                continue
            score = 0
            si = set(fi.get("imports", []))
            sc = set(fi.get("classes", []))
            sf = set(fi.get("functions", []))
            score += len(ti & si) * 2 + len(tc & sc) * 3 + len(tf & sf) * 1
            if score > 0:
                scores.append({"path": fpath, "score": score, "lines": fi.get("lines", 0)})
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_n]

    def get_file_info(self, path: str) -> Optional[dict]:
        idx = self.index()
        info = idx["files"].get(path)
        if not info:
            return None
        node = self._dep_graph.get(path)
        return {
            **info,
            "dependencies": node.imports[:5] if node else [],
            "dependents": node.imported_by[:5] if node else [],
            "symbols": idx["symbols"].get(path, []),
        }

    def get_file_tree(self) -> list[str]:
        return self.index().get("file_tree", [])

    def get_config_files(self) -> list[dict]:
        configs = []
        for f in self.index().get("config_files", []):
            try:
                content = Path(self.workdir, f).read_text(encoding="utf-8", errors="replace")[:2000]
                configs.append({"path": f, "content": content})
            except:
                continue
        return configs

    def get_readme(self) -> Optional[str]:
        for f in self.index().get("readme_files", []):
            try:
                path = Path(self.workdir, f)
                if path.exists():
                    return path.read_text(encoding="utf-8", errors="replace")[:5000]
            except:
                continue
        return None
