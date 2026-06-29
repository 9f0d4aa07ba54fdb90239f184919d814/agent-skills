"""
LIMB: Tools - Execution tools that plug into the brain.
All tools accept and return the same format: {"ok": bool, "data": str, "error": str}
"""

import subprocess, sys, os, tempfile, json, time, shutil, importlib, re, functools
from pathlib import Path
from typing import Optional
from .codebase import CodebaseAnalyzer


def safe_tool(func):
    """Decorator that wraps tool methods to standardize error handling.
    Catches exceptions and returns the standard {"ok": bool, "data": str, "error": str} format.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PermissionError as e:
            return {"ok": False, "data": "", "error": f"Permission denied: {e}"}
        except FileNotFoundError as e:
            return {"ok": False, "data": "", "error": f"File not found: {e}"}
        except Exception as e:
            return {"ok": False, "data": "", "error": f"{type(e).__name__}: {e}"[:300]}
    return wrapper


class Tools:
    def __init__(self, workdir: str = ".", brain=None):
        self.workdir = str(Path(workdir).resolve())
        self.codebase = CodebaseAnalyzer(self.workdir)
        self._brain = brain

    def _run(self, cmd: list, timeout: int = 30, env: dict = None) -> dict:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=self.workdir, env={**os.environ, **(env or {})})
            out = (r.stdout or "")[-5000:] or (r.stderr or "")[-1000:]
            return {"ok": r.returncode == 0, "data": out, "error": r.stderr[:500] if r.returncode else ""}
        except subprocess.TimeoutExpired:
            return {"ok": False, "data": "", "error": "timeout after {}s".format(timeout)}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def _safe_path(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = Path(self.workdir) / path
        p = p.resolve()
        # Only block actual traversal (.. component), not all absolute paths
        if ".." in path.split("/"):
            if not str(p).startswith(str(Path(self.workdir).resolve())):
                raise PermissionError(f"Path traversal blocked: {path}")
        return p

    # --- Core File Tools ---

    def run_bash(self, cmd: str) -> dict:
        return self._run(["bash", "-c", cmd], timeout=60)

    def run_python(self, code: str) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code); fpath = f.name
        result = self._run([sys.executable, fpath])
        os.unlink(fpath)
        return result

    @safe_tool
    def read_file(self, path: str, offset: int = 0, limit: int = 0) -> dict:
        p = self._safe_path(path)
        if not p.exists():
            return {"ok": False, "data": "", "error": f"not found: {path}"}
        content = p.read_text()
        if offset > 0 or limit > 0:
            lines = content.split("\n")
            start = max(0, offset - 1)
            end = start + limit if limit > 0 else len(lines)
            content = "\n".join(lines[start:end])
        return {"ok": True, "data": content, "error": ""}

    @safe_tool
    def write_file(self, path: str, content: str) -> dict:
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"ok": True, "data": f"written {path} ({len(content)}b)", "error": ""}

    @safe_tool
    def edit_file(self, path: str, old: str, new: str) -> dict:
        p = self._safe_path(path)
        if not p.exists():
            return {"ok": False, "data": "", "error": f"not found: {path}"}
        content = p.read_text()
        if old not in content:
            return {"ok": False, "data": "", "error": f"text not found in {path}"}
        p.write_text(content.replace(old, new, 1))
        return {"ok": True, "data": f"edited {path} (1 replacement)", "error": ""}

    def search_files(self, pattern: str) -> dict:
        clean = pattern.removeprefix("**/")
        results = list(Path(self.workdir).rglob(clean))
        return {"ok": True, "data": "\n".join(str(r.relative_to(self.workdir)) for r in results[:50]), "error": ""}

    def grep(self, text: str = "", pattern: str = "*.py", include: str = "", path: str = "") -> dict:
        search_text = text or pattern
        file_pat = include or (pattern if not text else "*.py")
        base = Path(self.workdir) / path if path else Path(self.workdir)
        is_regex = bool(re.search(r'[.*+?^${}()|\[\]\\]', search_text))
        lines = []
        for f in base.rglob(file_pat):
            if f.is_file() and f.stat().st_size < 500000:
                try:
                    for i, line in enumerate(f.read_text().split("\n"), 1):
                        if is_regex:
                            if re.search(search_text, line):
                                lines.append(f"{f.relative_to(self.workdir)}:{i}: {line.strip()[:150]}")
                        else:
                            if search_text in line:
                                lines.append(f"{f.relative_to(self.workdir)}:{i}: {line.strip()[:150]}")
                        if len(lines) >= 50:
                            break
                except: pass
            if len(lines) >= 50:
                break
        return {"ok": True, "data": "\n".join(lines[:50]), "error": ""}

    def tree(self, depth: int = 3) -> dict:
        result = []
        for dirpath, dirs, files in os.walk(self.workdir):
            rel = Path(dirpath).relative_to(self.workdir)
            if len(rel.parts) > depth: continue
            indent = "  " * len(rel.parts)
            dirs[:] = sorted(dirs)
            result.append(f"{indent}{rel.parts[-1] if rel.parts else '.'}/")
            for f in sorted(files)[:10]:
                fpath = Path(dirpath) / f
                size = fpath.stat().st_size
                size_str = f"{size/1024:.0f}K" if size > 1024 else f"{size}B"
                result.append(f"{indent}  {f} ({size_str})")
        return {"ok": True, "data": "\n".join(result[:100]), "error": ""}

    # --- Codebase Understanding ---

    @safe_tool
    def analyze_file(self, path: str) -> dict:
        p = self._safe_path(path)
        if not p.exists():
            return {"ok": False, "data": "", "error": f"not found: {path}"}
        content = p.read_text()
        lines = content.split("\n")
        info = {
            "path": path, "lines": len(lines), "size": len(content),
            "type": p.suffix,
            "imports": [],
            "classes": [],
            "functions": [],
            "summary": content[:2000]
        }
        for line in lines[:200]:
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                info["imports"].append(s)
            if "class " in s and ":" in s:
                info["classes"].append(s)
            if "def " in s and ":" in s:
                info["functions"].append(s)
        return {"ok": True, "data": json.dumps(info, indent=2), "error": ""}

    def find_file(self, name: str, path: str = "") -> dict:
        search_dir = Path(self.workdir) / path if path else Path(self.workdir)
        results = []
        for f in search_dir.rglob(name):
            if f.is_file():
                try:
                    rel = f.relative_to(self.workdir)
                    size = f.stat().st_size
                    results.append(f"{rel} ({size}b)")
                except: pass
        return {"ok": True, "data": "\n".join(results[:30]) if results else f"no files matching '{name}'", "error": ""}

    # --- Web Tools ---

    def web_search(self, query: str) -> dict:
        errors = []
        for attempt in range(2):
            try:
                import httpx
                from bs4 import BeautifulSoup
                import urllib.parse
                r = httpx.get(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
                              headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}, timeout=10, follow_redirects=True)
                soup = BeautifulSoup(r.text, "html.parser")
                results = []
                for a in soup.select("a.result__a")[:5]:
                    href = a.get("href", "")
                    if href and a.text.strip():
                        results.append(f"{a.text.strip()[:100]}: {href}")
                if results:
                    return {"ok": True, "data": "\n".join(results), "error": ""}
                errors.append("no results found")
                time.sleep(1)
            except Exception as e:
                errors.append(str(e)[:100])
                time.sleep(1)
        return {"ok": False, "data": "", "error": "; ".join(errors)}

    def web_fetch(self, url: str) -> dict:
        for attempt in range(2):
            try:
                import httpx
                from bs4 import BeautifulSoup
                r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}, timeout=15, follow_redirects=True)
                soup = BeautifulSoup(r.text, "html.parser")
                for t in soup(["script","style","nav","footer","header","aside"]): t.decompose()
                text = soup.get_text(separator="\n", strip=True)[:5000]
                return {"ok": True, "data": text, "error": ""}
            except Exception as e:
                if attempt < 1:
                    time.sleep(1)
                    continue
                return {"ok": False, "data": "", "error": str(e)[:200]}
        return {"ok": False, "data": "", "error": "failed to fetch"}

    # --- Development Tools ---

    def install_deps(self, packages: str) -> dict:
        return self._run(["pip3", "install"] + packages.split(), timeout=120)

    def run_tests(self, cmd: str = "", path: str = "") -> dict:
        if cmd:
            return self._run(["bash", "-c", cmd], timeout=120)
        test_dirs = ["tests", "test", "spec"]
        for td in test_dirs:
            tp = Path(self.workdir) / td
            if tp.is_dir():
                pytest = shutil.which("pytest")
                if pytest:
                    return self._run([pytest, str(tp)], timeout=120)
                return self._run(["python3", "-m", "unittest", "discover", str(tp)], timeout=120)
        return {"ok": False, "data": "", "error": "no test directory found"}

    # --- Interaction Tools ---

    @safe_tool
    def ask_user(self, question: str) -> dict:
        print(f"\n[AGENT] Question: {question}")
        print("[AGENT] (Type your answer, or press Enter for 'continue'): ", end="", flush=True)
        answer = sys.stdin.readline().strip()
        if not answer:
            answer = "continue"
        return {"ok": True, "data": answer, "error": ""}

    # --- Codebase Understanding ---

    @safe_tool
    def codebase_overview(self) -> dict:
        overview = self.codebase.codebase_overview()
        return {"ok": True, "data": json.dumps(overview, indent=2), "error": ""}

    @safe_tool
    def find_references(self, name: str) -> dict:
        refs = self.codebase.find_references(name)
        return {"ok": True, "data": "\n".join(refs[:30]) if refs else f"no references to '{name}'", "error": ""}

    @safe_tool
    def find_symbol(self, symbol: str) -> dict:
        result = self.codebase.find_symbol(symbol)
        parts = []
        for c in result["classes"]:
            parts.append(f"class {c['name']}: {', '.join(c['files'][:3])}")
        for f in result["functions"]:
            parts.append(f"function {f['name']}: {', '.join(f['files'][:3])}")
        return {"ok": True, "data": "\n".join(parts[:20]) if parts else f"no symbol '{symbol}' found", "error": ""}

    @safe_tool
    def dependency_graph(self) -> dict:
        deps = self.codebase.dependency_graph()
        if not deps:
            return {"ok": True, "data": "no dependencies found", "error": ""}
        lines = [f"{f} depends on:" for f, d in deps.items()]
        for f, d in list(deps.items())[:15]:
            for dep in d[:3]:
                lines.append(f"  -> {dep}")
        return {"ok": True, "data": "\n".join(lines[:50]), "error": ""}

    @safe_tool
    def similar_files(self, path: str) -> dict:
        sim = self.codebase.similar_files(path)
        if not sim:
            return {"ok": True, "data": f"no similar files to '{path}'", "error": ""}
        lines = [f"{s['path']} (score: {s['score']}, {s['lines']} lines)" for s in sim]
        return {"ok": True, "data": "\n".join(lines), "error": ""}

    # --- Creative / Image Tools ---

    def generate_image_prompt(self, concept: str) -> dict:
        try:
            brain = self._brain
            if brain is None:
                from brain.core import Brain
                brain = Brain()
            prompt = f"""Create a detailed image generation prompt for: {concept}
Include: subject, style, lighting, colors, composition, mood, medium.
Return ONLY the prompt text, 1-2 paragraphs."""
            result = brain.think(prompt, "You are an expert prompt engineer for AI image generation.")
            return {"ok": True, "data": result or f"A detailed visualization of {concept}", "error": ""}
        except Exception as e:
            return {"ok": False, "data": f"A visualization of {concept}", "error": str(e)}

    def generate_story(self, topic: str) -> dict:
        try:
            brain = self._brain
            if brain is None:
                from brain.core import Brain
                brain = Brain()
            prompt = f"Write a short creative story about: {topic}. Keep it under 300 words."
            result = brain.think(prompt, "You are a creative writer.")
            return {"ok": True, "data": result or f"Story about {topic}", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # --- Data Science / ML Tools ---

    def analyze_dataframe(self, code: str) -> dict:
        imports = "import pandas as pd\nimport numpy as np\nimport json\n"
        wrapped = f"{imports}\n{code}\nprint('===RESULT===')\nprint(json.dumps(result, default=str))"
        return self.run_python(wrapped)

    def run_ml_experiment(self, code: str) -> dict:
        imports = "import numpy as np\nimport json\n"
        try:
            import sklearn
            imports += "from sklearn import *\n"
        except:
            pass
        wrapped = f"{imports}\n{code}\nprint('===RESULT===')"
        return self.run_python(wrapped)

    def visualize_data(self, code: str, output_path: str = "vis_output.png") -> dict:
        viz_code = f"""import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
{code}
plt.savefig('{output_path}', dpi=100, bbox_inches='tight')
plt.close()
print('Saved to {output_path}')
"""
        result = self.run_python(viz_code)
        out_path = Path(self.workdir) / output_path
        if out_path.exists():
            return {"ok": True, "data": f"Visualization saved to {output_path}", "error": ""}
        return result

    # --- Git Tools ---

    @safe_tool
    def git_status(self) -> dict:
        """Show git status of the working directory."""
        r = subprocess.run(["git", "status", "--short"],
                          capture_output=True, text=True, timeout=10,
                          cwd=self.workdir)
        if r.returncode != 0:
            return {"ok": False, "data": "", "error": r.stderr[:200] or "not a git repo"}
        out = r.stdout.strip()
        if not out:
            return {"ok": True, "data": "Working tree clean — no changes", "error": ""}
        lines = out.split("\n")
        summary = f"{sum(1 for l in lines if l.startswith('M') or l.startswith('?') or l.startswith('A'))} file(s) changed\n"
        return {"ok": True, "data": summary + out[:2000], "error": ""}

    @safe_tool
    def git_diff(self, path: str = "") -> dict:
        """Show git diff for working tree changes."""
        cmd = ["git", "diff"]
        if path:
            cmd.append(path)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=self.workdir)
        if r.returncode != 0:
            return {"ok": False, "data": "", "error": r.stderr[:200]}
        out = r.stdout.strip()
        if not out:
            return {"ok": True, "data": "No changes to show", "error": ""}
        return {"ok": True, "data": out[:4000], "error": ""}

    @safe_tool
    def git_log(self, count: int = 10) -> dict:
        """Show recent git commit history."""
        r = subprocess.run(["git", "log", f"--max-count={count}",
                           "--oneline", "--decorate"],
                          capture_output=True, text=True, timeout=10,
                          cwd=self.workdir)
        if r.returncode != 0:
            return {"ok": False, "data": "", "error": r.stderr[:200]}
        return {"ok": True, "data": r.stdout.strip()[:2000], "error": ""}

    # --- Directory Tools ---

    @safe_tool
    def read_directory(self, path: str = ".") -> dict:
        """List all files and folders in a directory, one per line."""
        target = Path(self.workdir) / path if not Path(path).is_absolute() else Path(path)
        if not target.exists():
            return {"ok": False, "data": "", "error": f"directory not found: {path}"}
        if not target.is_dir():
            return {"ok": False, "data": "", "error": f"not a directory: {path}"}
        items = []
        for f in sorted(target.iterdir()):
            suffix = "/" if f.is_dir() else ""
            items.append(f"{f.name}{suffix}")
        return {"ok": True, "data": "\n".join(items[:100]), "error": ""}

    @safe_tool
    def file_info(self, path: str) -> dict:
        """Get metadata about a file (size, lines, type)."""
        p = self._safe_path(path)
        if not p.exists():
            return {"ok": False, "data": "", "error": f"not found: {path}"}
        import datetime
        stat = p.stat()
        info = {
            "path": path, "size": stat.st_size,
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "type": p.suffix or "(no extension)",
        }
        if p.is_file() and stat.st_size < 500000:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                info["lines"] = len(content.split("\n"))
            except:
                info["lines"] = 0
        return {"ok": True, "data": json.dumps(info, indent=2), "error": ""}

    @safe_tool
    def run_command(self, cmd: str, timeout: int = 30) -> dict:
        """Run an arbitrary shell command on the host system."""
        return self._run(["bash", "-c", cmd], timeout=timeout)

    # --- Utility ---

    def list(self) -> dict:
        return {"ok": True, "data": "\n".join(sorted(self.__class__.__dict__.keys())), "error": ""}
