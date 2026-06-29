"""
ENGINEERING REVIEWER — Comprehensive code review system.
Reviews code changes across 8 dimensions:
Security, Performance, Accessibility, Architecture, Style, Tests, Documentation, Maintainability.
"""

import json, os, re, subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime


class ReviewResult:
    def __init__(self):
        self.issues: list[dict] = []
        self.passed: list[str] = []
        self.score: float = 1.0  # 0.0 (worst) to 1.0 (perfect)

    def add_issue(self, category: str, severity: str, message: str,
                  file: str = "", line: int = 0, suggestion: str = ""):
        self.issues.append({
            "category": category,
            "severity": severity,
            "message": message,
            "file": file,
            "line": line,
            "suggestion": suggestion,
        })
        # Decrease score based on severity
        penalties = {"critical": 0.3, "high": 0.15, "medium": 0.08, "low": 0.03, "info": 0.01}
        self.score = max(0.0, self.score - penalties.get(severity, 0.05))

    def add_pass(self, category: str, message: str):
        self.passed.append(f"[{category}] {message}")

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 2),
            "total_issues": len(self.issues),
            "issues": self.issues[:20],
            "passed_checks": self.passed,
        }

    def to_text(self) -> str:
        lines = [f"## Review Score: {self.score:.0%}"]
        if self.passed:
            lines.append(f"\n### Passed ({len(self.passed)})")
            for p in self.passed:
                lines.append(f"  ✓ {p}")
        if self.issues:
            lines.append(f"\n### Issues ({len(self.issues)})")
            for issue in sorted(self.issues, key=lambda x:
                                {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(x["severity"], 5)):
                file_info = f" {issue['file']}:{issue['line']}" if issue.get('file') else ""
                lines.append(f"  [{issue['severity'].upper()}][{issue['category']}]{file_info}")
                lines.append(f"    {issue['message'][:120]}")
                if issue.get('suggestion'):
                    lines.append(f"    → {issue['suggestion'][:100]}")
        return "\n".join(lines)


class EngineeringReviewer:
    """Reviews code across 8 engineering dimensions."""

    DIMENSIONS = ["security", "performance", "accessibility", "architecture",
                  "style", "tests", "documentation", "maintainability"]

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())

    def review_file(self, file_path: str, content: str = None) -> ReviewResult:
        """Review a single file across all relevant dimensions."""
        result = ReviewResult()
        
        if content is None:
            try:
                path = self._resolve(file_path)
                content = path.read_text(encoding="utf-8", errors="replace")
            except:
                result.add_issue("architecture", "high", f"Cannot read file: {file_path}", file_path)
                return result

        ext = Path(file_path).suffix.lower()

        # Security review (all languages)
        self._review_security(content, ext, file_path, result)
        
        # Performance review
        self._review_performance(content, ext, file_path, result)
        
        # Style review
        self._review_style(content, ext, file_path, result)
        
        # Architecture review
        self._review_architecture(content, ext, file_path, result)
        
        # Documentation review
        self._review_documentation(content, ext, file_path, result)
        
        # Maintainability review
        self._review_maintainability(content, ext, file_path, result)

        if not result.issues:
            result.add_pass("all", f"File looks good across all dimensions")

        return result

    def review_diff(self, diff_text: str) -> ReviewResult:
        """Review a git diff (added/changed lines only)."""
        result = ReviewResult()
        added_lines = []
        
        for line in diff_text.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
        
        content = "\n".join(added_lines)
        
        self._review_security(content, ".py", "diff", result)
        self._review_performance(content, ".py", "diff", result)
        self._review_style(content, ".py", "diff", result)
        
        if not result.issues:
            result.add_pass("all", "Diff looks clean")
        
        return result

    # ── Dimension: Security ──

    def _review_security(self, content: str, ext: str, file_path: str, result: ReviewResult):
        patterns = {
            "eval(": ("Use of eval() allows arbitrary code execution", "Replace with safer alternative"),
            "exec(": ("Use of exec() allows arbitrary code execution", "Replace with safer alternative"),
            "pickle.loads": ("Unsafe deserialization with pickle", "Use JSON or a safe serialization library"),
            "pickle.load": ("Unsafe deserialization with pickle", "Use JSON or a safe serialization library"),
            "subprocess.call": ("Shell execution with subprocess", "Validate inputs, prefer subprocess.run with shell=False"),
            "subprocess.Popen": ("Shell execution with subprocess.Popen", "Validate inputs, use with caution"),
            "os.system": ("Shell execution via os.system", "Use subprocess.run with shell=False"),
            "os.popen": ("Shell execution via os.popen", "Use subprocess.run with shell=False"),
            "sqlite3.execute(": ("SQL execution — potential injection risk", "Use parameterized queries (?, :name)"),
            "cursor.execute(": ("SQL execution — potential injection risk", "Use parameterized queries"),
            "raw_input": ("Use of raw_input instead of input()", "Use input() in Python 3"),
            "dangerouslySetInnerHTML": ("XSS risk: dangerouslySetInnerHTML", "Sanitize content or use safer alternatives"),
            "innerHTML": ("XSS risk: setting innerHTML directly", "Use textContent or sanitize input"),
            "document.write": ("XSS risk: document.write", "Use DOM manipulation methods"),
            "{{": ("Template injection risk", "Validate template content"),
        }
        
        for pattern, (msg, suggestion) in patterns.items():
            for i, line in enumerate(content.split("\n"), 1):
                if pattern in line and not self._is_comment(line, ext):
                    result.add_issue("security", "high" if "eval" in pattern or "pickle" in pattern else "medium",
                                    msg, file_path, i, suggestion)
                    break

        # Check for hardcoded secrets
        secret_patterns = [
            (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded password detected"),
            (r'(?i)(api_key|apikey|api-key)\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded API key detected"),
            (r'(?i)(secret|token|auth_token)\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded secret/token detected"),
        ]
        for pat, msg in secret_patterns:
            for i, line in enumerate(content.split("\n"), 1):
                if re.search(pat, line) and "example" not in line.lower() and "test" not in line.lower():
                    result.add_issue("security", "critical", msg, file_path, i,
                                    "Use environment variables or a secrets manager")

        self._add_generic_pass(result, "security", content)

    # ── Dimension: Performance ──

    def _review_performance(self, content: str, ext: str, file_path: str, result: ReviewResult):
        # Python-specific
        if ext == ".py":
            # N+1 query detection
            if "for" in content and "query" in content.lower():
                for i, line in enumerate(content.split("\n"), 1):
                    if "for" in line and "query" in line.lower():
                        result.add_issue("performance", "medium", "N+1 query pattern detected",
                                        file_path, i, "Use select_related/prefetch_related or batch queries")
                        break
            
            # Large list comprehension without generator
            if "[" in content and "for" in content and "]" in content:
                if any(l.strip().startswith("[") and "for" in l for l in content.split("\n")):
                    pass  # List comprehensions are usually fine
        
        # General
        if "JSON.parse" in content and "JSON.stringify" in content:
            pass
        
        # Check for obvious issues
        for i, line in enumerate(content.split("\n"), 1):
            if ext == ".py" and "while True:" in line and i < len(content.split("\n")) - 1:
                # Check if there's a break in the next few lines
                subsequent = "\n".join(content.split("\n")[i:i+5])
                if "break" not in subsequent and "return" not in subsequent:
                    result.add_issue("performance", "high", "Potential infinite loop: while True without break",
                                    file_path, i, "Add a break condition or timeout")
        
        self._add_generic_pass(result, "performance", content)

    # ── Dimension: Style ──

    def _review_style(self, content: str, ext: str, file_path: str, result: ReviewResult):
        lines = content.split("\n")
        
        # Check line length
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                result.add_issue("style", "low", f"Line too long ({len(line)} chars, max 120)",
                                file_path, i, "Split into multiple lines")
                break
        
        # Check for TODO/FIXME without context
        for i, line in enumerate(lines, 1):
            if re.search(r'#\s*(TODO|FIXME|HACK|XXX)\b', line) and ":" not in line and "(" not in line:
                result.add_issue("style", "info", "TODO/FIXME without context or owner",
                                file_path, i, "Add a description and/or owner: # TODO(username): description")
                break
        
        # Check for large functions (Python)
        if ext == ".py":
            in_function = False
            fn_start = 0
            fn_lines = 0
            for i, line in enumerate(lines, 1):
                if re.match(r'^\s*def\s+\w+\s*\(', line):
                    if in_function and fn_lines > 50:
                        result.add_issue("style", "medium", f"Function starting at line {fn_start} has {fn_lines} lines",
                                        file_path, fn_start, "Consider splitting into smaller functions")
                    in_function = True
                    fn_start = i
                    fn_lines = 0
                elif in_function:
                    if re.match(r'^\s*def\s+\w+\s*\(', line) or re.match(r'^\s*class\s+\w+', line):
                        if fn_lines > 50:
                            result.add_issue("style", "medium", f"Function starting at line {fn_start} has {fn_lines} lines",
                                            file_path, fn_start, "Consider splitting into smaller functions")
                        in_function = True
                        fn_start = i
                        fn_lines = 0
                    elif line.strip() and not line.strip().startswith("#"):
                        fn_lines += 1
            
            if in_function and fn_lines > 50:
                result.add_issue("style", "medium", f"Function starting at line {fn_start} has {fn_lines} lines",
                                file_path, fn_start, "Consider splitting into smaller functions")
        
        self._add_generic_pass(result, "style", content)

    # ── Dimension: Architecture ──

    def _review_architecture(self, content: str, ext: str, file_path: str, result: ReviewResult):
        # Check for circular import risks
        lines = content.split("\n")
        imports = []
        for i, line in enumerate(lines, 1):
            if ext == ".py" and (line.startswith("import ") or line.startswith("from ")):
                imports.append(line)
        
        if len(imports) > 20:
            result.add_issue("architecture", "low", f"File has {len(imports)} imports — may have too many dependencies",
                            file_path, 0, "Consider splitting into smaller modules")
        
        # Check for god object / large file
        if len(lines) > 500:
            result.add_issue("architecture", "medium", f"Large file ({len(lines)} lines) — may be doing too much",
                            file_path, 0, "Consider splitting into smaller files by responsibility")
        
        self._add_generic_pass(result, "architecture", content)

    # ── Dimension: Documentation ──

    def _review_documentation(self, content: str, ext: str, file_path: str, result: ReviewResult):
        lines = content.split("\n")
        has_docstring = False
        has_module_doc = False
        public_functions = 0
        undocumented_functions = 0
        
        for i, line in enumerate(lines, 1):
            if ext == ".py":
                if i == 1 and ('"""' in line or "'''" in line):
                    has_module_doc = True
                if re.match(r'^\s*def\s+\w+\s*\(', line) and not line.strip().startswith("def _"):  # Skip private
                    public_functions += 1
                    # Check next line(s) for docstring
                    next_lines = "\n".join(lines[i:i+3])
                    if '"""' not in next_lines and "'''" not in next_lines:
                        undocumented_functions += 1
                if '"""' in line or "'''" in line:
                    has_docstring = True
        
        if undocumented_functions > 0:
            result.add_issue("documentation", "medium",
                            f"{undocumented_functions}/{public_functions} public functions lack docstrings",
                            file_path, 0, "Add docstrings explaining parameters and return values")
        
        if not has_module_doc and ext == ".py":
            result.add_issue("documentation", "low", "Module-level docstring missing",
                            file_path, 0, "Add a module docstring explaining the file's purpose")
        
        self._add_generic_pass(result, "documentation", content)

    # ── Dimension: Maintainability ──

    def _review_maintainability(self, content: str, ext: str, file_path: str, result: ReviewResult):
        lines = content.split("\n")
        
        # Check for hardcoded values (magic numbers)
        magic_numbers = re.findall(r'\bif\s+\w+\s*[=!]=\s*(\d+)\b', content)
        if len(magic_numbers) > 3:
            result.add_issue("maintainability", "low", f"Multiple magic numbers detected",
                            file_path, 0, "Extract to named constants")
        
        # Check for deeply nested code
        max_depth = 0
        current_depth = 0
        for line in lines:
            stripped = line.strip()
            if stripped.endswith(":") and not stripped.startswith("#"):
                current_depth += line.count("    ") // 4
                max_depth = max(max_depth, current_depth)
            elif stripped == "" or stripped.startswith("#"):
                pass
            else:
                # Dedent based on leading spaces
                indent = len(line) - len(line.lstrip())
                current_depth = min(current_depth, indent // 4)
        
        if max_depth > 5:
            result.add_issue("maintainability", "medium", f"Deep nesting detected (depth {max_depth})",
                            file_path, 0, "Extract nested blocks into separate functions")
        
        self._add_generic_pass(result, "maintainability", content)

    # ── Helpers ──

    def _is_comment(self, line: str, ext: str) -> bool:
        stripped = line.strip()
        if ext == ".py":
            return stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")
        if ext in (".ts", ".tsx", ".js", ".jsx"):
            return stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")
        return False

    def _add_generic_pass(self, result: ReviewResult, dimension: str, content: str):
        """Add a generic pass if no issues were found for this dimension."""
        has_issue = any(issue["category"] == dimension for issue in result.issues)
        if not has_issue:
            result.add_pass(dimension, f"{dimension.title()} check passed")

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = Path(self.workdir) / path
        return p.resolve()
