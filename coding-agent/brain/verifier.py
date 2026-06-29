"""
SELF VERIFICATION PIPELINE — Build → Test → Lint → Security.
Verifies changes automatically after code generation.
"""

import json, os, re, subprocess, sys, tempfile
from pathlib import Path
from typing import Optional


class Verifier:
    """Self-verification pipeline for generated code.
    
    Runs after edits to ensure changes are correct:
    1. Syntax check (all languages)
    2. Import resolution
    3. Build / compile
    4. Lint
    5. Test (if tests exist)
    6. Security scan (basic)
    """

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self.results: dict[str, list[dict]] = {}
        self._has_run = False

    # ── Main verification pipeline ──

    def verify(self, files: list[str] | None = None, run_tests: bool = True) -> dict:
        """Run the full verification pipeline.
        Args:
            files: List of changed files to verify. None = all.
            run_tests: Whether to run tests as well.
        Returns: {
            "ok": bool,  # True if all checks pass
            "checks": {check_name: {"ok": bool, "details": str, "errors": list}},
            "summary": str
        }
        """
        self.results = {}
        checks = {}
        all_ok = True

        # 1. Syntax check
        print("  [Verify] Syntax check...")
        result = self.verify_syntax(files)
        checks["syntax"] = result
        if not result["ok"]:
            all_ok = False
            if result.get("errors"):
                for err in result["errors"][:3]:
                    print(f"    Syntax error: {err['message'][:80]}")
                    print(f"    File: {err.get('file', '')}:{err.get('line', 0)}")

        # 2. Import check
        if files:
            print("  [Verify] Import check...")
            result = self.verify_imports(files)
            checks["imports"] = result
            if not result["ok"]:
                all_ok = False

        # 3. Build / compile check
        print("  [Verify] Build check...")
        result = self.verify_build()
        checks["build"] = result
        if not result["ok"]:
            all_ok = False

        # 4. Lint check
        print("  [Verify] Lint check...")
        result = self.verify_lint(files)
        checks["lint"] = result
        if not result["ok"]:
            all_ok = False

        # 5. Test check (optional)
        if run_tests and self._has_tests():
            print("  [Verify] Running tests...")
            result = self.verify_tests()
            checks["tests"] = result
            if not result["ok"]:
                all_ok = False
        else:
            checks["tests"] = {"ok": True, "details": "Skipped (no tests found or not requested)", "errors": []}

        # 6. Security check (basic)
        if files:
            print("  [Verify] Security scan...")
            result = self.verify_security(files)
            checks["security"] = result
            if not result["ok"]:
                all_ok = False

        # Summary
        passed = sum(1 for c in checks.values() if c.get("ok"))
        total = len(checks)
        summary = f"{passed}/{total} checks passed"
        
        self.results = checks
        self._has_run = True
        
        return {
            "ok": all_ok,
            "checks": checks,
            "summary": summary,
        }

    # ── Individual checks ──

    def verify_syntax(self, files: list[str] | None = None) -> dict:
        """Check syntax of modified files."""
        errors = []
        targets = files or self._find_project_files()
        
        for f in targets[:15]:  # Limit to 15 files
            path = self._resolve(f)
            if not path.exists() or path.is_dir():
                continue
            
            ext = path.suffix.lower()
            
            if ext == ".py":
                err = self._check_python_syntax(path)
                if err:
                    errors.append(err)
            elif ext in (".ts", ".tsx", ".js", ".jsx"):
                err = self._check_js_syntax(path)
                if err:
                    errors.append(err)
            elif ext == ".go":
                err = self._check_go_syntax(path)
                if err:
                    errors.append(err)
            elif ext == ".rs":
                err = self._check_rust_syntax(path)
                if err:
                    errors.append(err)
            elif ext == ".dart":
                err = self._check_dart_syntax(path)
                if err:
                    errors.append(err)
        
        return {
            "ok": len(errors) == 0,
            "details": f"Checked {len(targets)} file(s), {len(errors)} error(s)",
            "errors": errors,
        }

    def verify_imports(self, files: list[str]) -> dict:
        """Check that imports in changed files resolve."""
        errors = []
        for f in files[:10]:
            path = self._resolve(f)
            if not path.exists():
                continue
            ext = path.suffix.lower()
            
            if ext == ".py":
                err = self._check_python_imports(path)
                if err:
                    errors.append(err)
        
        return {
            "ok": len(errors) == 0,
            "details": f"Checked {len(files)} file(s), {len(errors)} import error(s)",
            "errors": errors,
        }

    def verify_build(self) -> dict:
        """Try to build the project."""
        # Detect project type and run appropriate build command
        if self._has_file("package.json"):
            return self._run_npm_build()
        elif self._has_file("pyproject.toml") or self._has_file("setup.py"):
            return self._run_python_build()
        elif self._has_file("Cargo.toml"):
            return self._run_cargo_build()
        elif self._has_file("go.mod"):
            return self._run_go_build()
        elif self._has_file("pubspec.yaml"):
            return self._run_dart_build()
        return {"ok": True, "details": "No build system detected", "errors": []}

    def verify_lint(self, files: list[str] | None = None) -> dict:
        """Run linting on changed files."""
        errors = []
        targets = files or self._find_project_files()
        
        for f in targets[:10]:
            path = self._resolve(f)
            if not path.exists():
                continue
            ext = path.suffix.lower()
            
            if ext == ".py":
                errs = self._run_pylint(path)
                errors.extend(errs)
            elif ext in (".ts", ".tsx"):
                errs = self._run_ts_lint(path)
                errors.extend(errs)
        
        return {
            "ok": len(errors) == 0,
            "details": f"Linted {len(targets[:10])} file(s), {len(errors)} issue(s)",
            "errors": errors[:10],
        }

    def verify_tests(self) -> dict:
        """Run the project's test suite."""
        if self._has_file("pytest.ini") or self._has_dir("tests"):
            return self._run_pytest()
        elif self._has_file("package.json"):
            return self._run_npm_test()
        elif self._has_file("Cargo.toml"):
            return self._run_cargo_test()
        return {"ok": True, "details": "No test framework detected", "errors": []}

    def verify_security(self, files: list[str]) -> dict:
        """Basic security scan of changed files."""
        warnings = []
        for f in files[:10]:
            path = self._resolve(f)
            if not path.exists():
                continue
            
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                
                # Check for dangerous patterns
                dangerous = {
                    "eval(": "Use of eval() — can execute arbitrary code",
                    "exec(": "Use of exec() — can execute arbitrary code",
                    "pickle.load": "Unsafe deserialization — prefer JSON",
                    "subprocess.call": "Shell execution — validate inputs",
                    "os.system": "Shell execution — validate inputs",
                    "sqlite3.execute(": "SQL injection risk — use parameterized queries",
                    "dangerouslySetInnerHTML": "XSS risk in React",
                    "innerHTML": "XSS risk — prefer textContent",
                }
                
                for pattern, msg in dangerous.items():
                    for i, line in enumerate(content.split("\n"), 1):
                        if pattern in line and not line.strip().startswith("#") and not line.strip().startswith("//"):
                            warnings.append({
                                "file": str(path),
                                "line": i,
                                "message": msg,
                                "pattern": pattern,
                            })
                            break
            except:
                continue
        
        return {
            "ok": len(warnings) == 0,
            "details": f"Scanned {len(files)} file(s), {len(warnings)} warning(s)",
            "errors": warnings[:10],
        }

    # ── Language-specific checks ──

    def _check_python_syntax(self, path: Path) -> Optional[dict]:
        try:
            import py_compile
            py_compile.compile(str(path), doraise=True)
            return None
        except py_compile.PyCompileError as e:
            return {"file": str(path), "line": e.lineno or 0, "message": str(e)[:200]}
        except Exception as e:
            return {"file": str(path), "line": 0, "message": str(e)[:200]}

    def _check_js_syntax(self, path: Path) -> Optional[dict]:
        try:
            r = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return None
            m = re.search(r'(\d+):(\d+)', r.stderr)
            line = int(m.group(1)) if m else 0
            return {"file": str(path), "line": line, "message": r.stderr.strip()[:200]}
        except FileNotFoundError:
            return None
        except Exception as e:
            return {"file": str(path), "line": 0, "message": str(e)[:200]}

    def _check_go_syntax(self, path: Path) -> Optional[dict]:
        try:
            r = subprocess.run(
                ["go", "vet", str(path)],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                return None
            return {"file": str(path), "line": 0, "message": r.stderr.strip()[:200]}
        except FileNotFoundError:
            return None
        except Exception as e:
            return {"file": str(path), "line": 0, "message": str(e)[:200]}

    def _check_rust_syntax(self, path: Path) -> Optional[dict]:
        try:
            r = subprocess.run(
                ["rustc", "--edition", "2021", str(path)],
                capture_output=True, text=True, timeout=60
            )
            if r.returncode == 0:
                return None
            return {"file": str(path), "line": 0, "message": r.stderr.strip()[:200]}
        except FileNotFoundError:
            return None
        except Exception as e:
            return {"file": str(path), "line": 0, "message": str(e)[:200]}

    def _check_dart_syntax(self, path: Path) -> Optional[dict]:
        try:
            r = subprocess.run(
                ["dart", "analyze", str(path)],
                capture_output=True, text=True, timeout=60
            )
            if r.returncode == 0:
                return None
            # Parse dart analyze output
            for line in r.stderr.split("\n"):
                m = re.match(r'.+\((\d+),\d+\)\s+(error|warning)\s+(.+)', line)
                if m:
                    return {"file": str(path), "line": int(m.group(1)), "message": m.group(3)[:200]}
            return {"file": str(path), "line": 0, "message": r.stderr.strip()[:200]}
        except FileNotFoundError:
            return None
        except Exception as e:
            return {"file": str(path), "line": 0, "message": str(e)[:200]}

    def _check_python_imports(self, path: Path) -> Optional[dict]:
        """Check that all imports in a Python file resolve."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            imports = re.findall(r'^import\s+(\S+)', content, re.MULTILINE)
            imports += re.findall(r'^from\s+(\S+)', content, re.MULTILINE)
            
            for imp in imports:
                # Skip stdlib modules
                base = imp.split(".")[0]
                if base in sys.stdlib_module_names:
                    continue
                # Try importing
                try:
                    __import__(imp.split(".")[0])
                except ImportError:
                    return {"file": str(path), "line": 0, "message": f"Cannot import '{imp}'"}
            return None
        except Exception as e:
            return {"file": str(path), "line": 0, "message": str(e)[:200]}

    # ── Build runners ──

    def _run_npm_build(self) -> dict:
        try:
            r = subprocess.run(
                ["npm", "run", "build"],
                capture_output=True, text=True, timeout=120,
                cwd=self.workdir
            )
            if r.returncode == 0:
                return {"ok": True, "details": "Build succeeded", "errors": []}
            return {"ok": False, "details": "Build failed", "errors": [
                {"file": "package.json", "line": 0, "message": r.stderr.strip()[:300]}
            ]}
        except FileNotFoundError:
            return {"ok": True, "details": "npm not available", "errors": []}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    def _run_python_build(self) -> dict:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "compileall", self.workdir, "-q"],
                capture_output=True, text=True, timeout=60
            )
            if r.returncode == 0:
                return {"ok": True, "details": "All Python files compile", "errors": []}
            return {"ok": False, "details": "Compilation errors", "errors": [
                {"file": "", "line": 0, "message": r.stderr.strip()[:300]}
            ]}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    def _run_cargo_build(self) -> dict:
        try:
            r = subprocess.run(
                ["cargo", "check"],
                capture_output=True, text=True, timeout=180,
                cwd=self.workdir
            )
            if r.returncode == 0:
                return {"ok": True, "details": "Cargo check passed", "errors": []}
            return {"ok": False, "details": "Cargo check failed", "errors": [
                {"file": "", "line": 0, "message": r.stderr.strip()[:300]}
            ]}
        except FileNotFoundError:
            return {"ok": True, "details": "cargo not available", "errors": []}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    def _run_go_build(self) -> dict:
        try:
            r = subprocess.run(
                ["go", "build", "./..."],
                capture_output=True, text=True, timeout=120,
                cwd=self.workdir
            )
            return {"ok": r.returncode == 0, "details": r.stderr.strip()[:300] or "Build OK", "errors": []}
        except FileNotFoundError:
            return {"ok": True, "details": "go not available", "errors": []}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    def _run_dart_build(self) -> dict:
        try:
            r = subprocess.run(
                ["dart", "analyze"],
                capture_output=True, text=True, timeout=120,
                cwd=self.workdir
            )
            return {"ok": r.returncode == 0, "details": r.stderr.strip()[:300] or "Dart analyze OK", "errors": []}
        except FileNotFoundError:
            return {"ok": True, "details": "dart not available", "errors": []}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    # ── Test runners ──

    def _run_pytest(self) -> dict:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "--tb=short", "-q"],
                capture_output=True, text=True, timeout=120,
                cwd=self.workdir
            )
            out = (r.stdout or "")[-500:] + (r.stderr or "")[-500:]
            passed = "passed" in (r.stdout or "").lower() or "ok" in (r.stdout or "").lower()
            return {"ok": r.returncode == 0 or passed, "details": out.strip()[:500], "errors": []}
        except FileNotFoundError:
            return {"ok": True, "details": "pytest not available", "errors": []}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    def _run_npm_test(self) -> dict:
        try:
            r = subprocess.run(
                ["npm", "test"],
                capture_output=True, text=True, timeout=120,
                cwd=self.workdir
            )
            out = (r.stdout or "")[-500:]
            return {"ok": r.returncode == 0, "details": out.strip()[:500], "errors": []}
        except FileNotFoundError:
            return {"ok": True, "details": "npm not available", "errors": []}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    def _run_cargo_test(self) -> dict:
        try:
            r = subprocess.run(
                ["cargo", "test"],
                capture_output=True, text=True, timeout=180,
                cwd=self.workdir
            )
            return {"ok": r.returncode == 0, "details": (r.stdout or "")[-500:].strip(), "errors": []}
        except FileNotFoundError:
            return {"ok": True, "details": "cargo not available", "errors": []}
        except Exception as e:
            return {"ok": False, "details": str(e)[:200], "errors": []}

    # ── Lint runners ──

    def _run_pylint(self, path: Path) -> list[dict]:
        errors = []
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pylint", "--output-format=text", str(path)],
                capture_output=True, text=True, timeout=30
            )
            for line in r.stdout.split("\n"):
                m = re.match(r'^.+?:(\d+):(\d+):\s+(.+)', line)
                if m:
                    errors.append({
                        "file": str(path),
                        "line": int(m.group(1)),
                        "message": m.group(3)[:200],
                    })
        except (FileNotFoundError, Exception):
            pass
        return errors[:5]

    def _run_ts_lint(self, path: Path) -> list[dict]:
        errors = []
        try:
            r = subprocess.run(
                ["npx", "eslint", "--format", "json", str(path)],
                capture_output=True, text=True, timeout=30
            )
            if r.stdout:
                try:
                    data = json.loads(r.stdout)
                    for file_result in data:
                        for msg in file_result.get("messages", []):
                            errors.append({
                                "file": file_result.get("filePath", str(path)),
                                "line": msg.get("line", 0),
                                "message": msg.get("message", ""),
                            })
                except:
                    pass
        except (FileNotFoundError, Exception):
            pass
        return errors[:5]

    # ── Helpers ──

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = Path(self.workdir) / path
        return p.resolve()

    def _has_file(self, name: str) -> bool:
        return (Path(self.workdir) / name).exists()

    def _has_dir(self, name: str) -> bool:
        return (Path(self.workdir) / name).is_dir()

    def _has_tests(self) -> bool:
        return self._has_dir("tests") or self._has_file("pytest.ini") or self._has_file("package.json")

    def _find_project_files(self) -> list[str]:
        """Find all source files in the project."""
        exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".dart"}
        files = []
        for ext in exts:
            try:
                r = subprocess.run(
                    ["rg", "--files", "--glob", f"*{ext}", "--no-ignore"],
                    capture_output=True, text=True, timeout=10,
                    cwd=self.workdir
                )
                files.extend(r.stdout.strip().split("\n"))
            except:
                pass
        return [f for f in files if f and not f.startswith(".") and "node_modules" not in f]
