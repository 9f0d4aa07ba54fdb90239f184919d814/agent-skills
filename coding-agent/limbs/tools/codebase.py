"""
LIMB: Codebase Understanding Tools
Index, analyze, and search the codebase intelligently.
"""

import json, os, re
from pathlib import Path
from collections import defaultdict


class CodebaseAnalyzer:
    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self._index = None

    def index(self, force: bool = False) -> dict:
        if self._index and not force:
            return self._index
        idx = {"files": {}, "imports": defaultdict(list), "classes": defaultdict(list), "functions": defaultdict(list), "total_lines": 0, "total_files": 0, "languages": defaultdict(int)}
        EXCLUDED_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".tox", ".eggs", "env", "venv", ".mypy_cache", ".pytest_cache"}
        EXCLUDED_EXTS = {".pyc", ".pyo", ".so", ".o", ".class", ".jar", ".dll", ".dylib"}
        for f in Path(self.workdir).rglob("*"):
            if any(p in f.parts for p in EXCLUDED_DIRS):
                continue
            if f.suffix.lower() in EXCLUDED_EXTS:
                continue
            if f.is_file() and f.stat().st_size < 500000:
                try:
                    rel = str(f.relative_to(self.workdir))
                    ext = f.suffix.lower()
                    idx["languages"][ext] += 1
                    content = f.read_text()
                    lines = content.split("\n")
                    idx["total_files"] += 1
                    idx["total_lines"] += len(lines)
                    info = {"path": rel, "lines": len(lines), "size": f.stat().st_size, "ext": ext, "imports": [], "classes": [], "functions": []}
                    for line in lines[:300]:
                        s = line.strip()
                        if ext in (".py",) and (s.startswith("import ") or s.startswith("from ")):
                            info["imports"].append(s)
                            idx["imports"][rel].append(s)
                        if "class " in s and ":" in s:
                            m = re.search(r'class\s+(\w+)', s)
                            if m:
                                info["classes"].append(m.group(1))
                                idx["classes"][m.group(1)].append(rel)
                        if "def " in s and ":" in s:
                            m = re.search(r'def\s+(\w+)', s)
                            if m:
                                info["functions"].append(m.group(1))
                                idx["functions"][m.group(1)].append(rel)
                    idx["files"][rel] = info
                except:
                    pass
        self._index = idx
        return idx

    def find_references(self, name: str) -> list[str]:
        idx = self.index()
        results = set()
        name_lower = name.lower()
        for fpath, finfo in idx["files"].items():
            try:
                content = Path(self.workdir, fpath).read_text()
                if name in content:
                    for i, line in enumerate(content.split("\n"), 1):
                        if name in line:
                            results.add(f"{fpath}:{i}: {line.strip()[:120]}")
            except:
                pass
        return sorted(results)[:30]

    def find_symbol(self, symbol: str) -> dict:
        idx = self.index()
        symbol_lower = symbol.lower()
        result = {"classes": [], "functions": [], "in_files": []}
        for cls, files in idx["classes"].items():
            if symbol_lower in cls.lower():
                result["classes"].append({"name": cls, "files": files})
        for func, files in idx["functions"].items():
            if symbol_lower in func.lower():
                result["functions"].append({"name": func, "files": files})
        return result

    def codebase_overview(self) -> dict:
        idx = self.index()
        return {
            "total_files": idx["total_files"],
            "total_lines": idx["total_lines"],
            "languages": dict(idx["languages"]),
            "top_imports": sorted(idx["imports"].items(), key=lambda x: len(x[1]), reverse=True)[:10],
            "top_classes": sorted(idx["classes"].items(), key=lambda x: len(x[1]), reverse=True)[:10],
        }

    def dependency_graph(self) -> dict:
        idx = self.index()
        deps = {}
        for fpath, imports in idx["imports"].items():
            local_deps = []
            for imp in imports:
                for other in idx["files"]:
                    mod = other.replace("/", ".").replace(".py", "")
                    if mod in imp or imp.split()[-1].split(".")[0] in other:
                        local_deps.append(other)
            if local_deps:
                deps[fpath] = list(set(local_deps))[:5]
        return deps

    def similar_files(self, path: str, top_n: int = 5) -> list[dict]:
        idx = self.index()
        target = idx["files"].get(path)
        if not target:
            return []
        target_imports = set(target["imports"])
        target_classes = set(target["classes"])
        scores = []
        for fpath, finfo in idx["files"].items():
            if fpath == path:
                continue
            score = 0
            fi = set(finfo["imports"])
            fc = set(finfo["classes"])
            score += len(target_imports & fi) * 2
            score += len(target_classes & fc) * 3
            if score > 0:
                scores.append({"path": fpath, "score": score, "lines": finfo["lines"]})
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_n]
