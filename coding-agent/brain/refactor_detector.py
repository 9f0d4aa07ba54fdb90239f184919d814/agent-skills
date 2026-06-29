"""
AUTOMATIC REFACTORING DETECTOR — Proactively detects code quality issues.
Detects: duplicate code, dead code, unused APIs, slow functions,
circular dependencies, large files, poor naming, and more.
"""

import json, os, re, subprocess, ast
from pathlib import Path
from typing import Optional
from collections import defaultdict


class RefactoringIssue:
    def __init__(self, issue_type: str, severity: str, message: str,
                 file: str = "", line: int = 0, suggestion: str = ""):
        self.issue_type = issue_type
        self.severity = severity
        self.message = message
        self.file = file
        self.line = line
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {
            "type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "suggestion": self.suggestion,
        }


class RefactoringDetector:
    """Periodically scans the codebase for refactoring opportunities."""

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())

    def scan(self, full: bool = True) -> list[RefactoringIssue]:
        """Run all detectors and return issues found."""
        issues = []
        
        issues.extend(self._find_large_files())
        issues.extend(self._find_dead_code())
        issues.extend(self._find_circular_deps())
        issues.extend(self._find_slow_patterns())
        issues.extend(self._find_poor_naming())
        issues.extend(self._find_duplicate_code())
        issues.extend(self._find_unused_imports())
        
        return sorted(issues, key=lambda x: 
                     {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.severity, 4))

    def _find_large_files(self) -> list[RefactoringIssue]:
        """Find files that are too large."""
        issues = []
        for ext in [".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".dart"]:
            try:
                r = subprocess.run(
                    ["rg", "--count", "-l", "", "--glob", f"*{ext}"],
                    capture_output=True, text=True, timeout=30,
                    cwd=self.workdir
                )
                for line in r.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        path = Path(self.workdir) / line
                        if path.exists():
                            content = path.read_text(encoding="utf-8", errors="replace")
                            lines = len(content.split("\n"))
                            if lines > 800:
                                issues.append(RefactoringIssue(
                                    "large_file", "medium",
                                    f"File has {lines} lines — consider splitting",
                                    line, 0, "Split into smaller modules by responsibility"
                                ))
                            elif lines > 400:
                                issues.append(RefactoringIssue(
                                    "large_file", "low",
                                    f"File has {lines} lines — could be split",
                                    line, 0, "Consider splitting if it handles multiple concerns"
                                ))
                    except:
                        continue
            except:
                continue
        return issues

    def _find_dead_code(self) -> list[RefactoringIssue]:
        """Find potentially dead/unused code."""
        issues = []
        
        # Find definitions that might not be used
        try:
            # Python: Find functions that start with underscore (private) and aren't called
            r = subprocess.run(
                ["rg", "-n", "--no-heading", r'^\s*def\s+\w+\s*\(', "--glob", "*.py"],
                capture_output=True, text=True, timeout=15,
                cwd=self.workdir
            )
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    file_path = parts[0]
                    func_line = parts[1] if len(parts) > 1 else "0"
                    func_name_match = re.search(r'def\s+(\w+)', line)
                    if func_name_match:
                        func_name = func_name_match.group(1)
                        # Skip dunder methods and test functions
                        if func_name.startswith("__") or func_name.startswith("test_"):
                            continue
                        # Check if function is referenced elsewhere
                        ref_count = self._count_references(func_name, file_path)
                        if ref_count <= 1:  # Only the definition
                            issues.append(RefactoringIssue(
                                "dead_code", "low",
                                f"Function '{func_name}' may be unused",
                                file_path, int(func_line),
                                "Remove if not needed, or add TODO if planned"
                            ))
        except:
            pass
        
        return issues

    def _find_circular_deps(self) -> list[RefactoringIssue]:
        """Find circular dependencies between files."""
        issues = []
        
        try:
            r = subprocess.run(
                ["rg", "-n", "^import |^from ", "--glob", "*.py"],
                capture_output=True, text=True, timeout=15,
                cwd=self.workdir
            )
            
            # Build import graph
            imports: dict[str, list[str]] = defaultdict(list)
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    file_path = parts[0]
                    import_line = parts[2] if len(parts) > 2 else ""
                    m = re.match(r'^(?:from\s+(\S+)\s+)?import\s+(\S+)', import_line)
                    if m:
                        module = m.group(1) or m.group(2)
                        imports[file_path].append(module)
            
            # Simple cycle detection
            for file1, deps in imports.items():
                for dep in deps:
                    dep_file = dep.replace(".", "/") + ".py"
                    if dep_file in imports and file1 in imports[dep_file]:
                        issues.append(RefactoringIssue(
                            "circular_dependency", "high",
                            f"Circular dependency between {file1} and {dep_file}",
                            file1, 0,
                            "Extract shared logic into a separate module"
                        ))
        except:
            pass
        
        return issues

    def _find_slow_patterns(self) -> list[RefactoringIssue]:
        """Find potentially slow code patterns."""
        issues = []
        
        patterns = [
            (r'for\s+\w+\s+in\s+range\(len\(', "C-style loop — use direct iteration", "low"),
            (r'\.\.\.\.', "Suspicious repeated dots — potential bug", "medium"),
            (r'\bprint\s*\(', "Debug print statement — remove before production", "low"),
            (r'except\s*:', "Bare except clause — catches all exceptions", "medium"),
            (r'except\s+Exception\s*:', "Generic except — may hide bugs", "low"),
            (r'\btry\s*:.*\n.*\n.*\bexcept\b', "Try block with single line — wrap minimal code", "info"),
            (r'\bpass\b', "Empty pass — incomplete implementation", "info"),
        ]
        
        for ext in [".py", ".ts", ".tsx", ".js", ".jsx"]:
            try:
                all_files = list(Path(self.workdir).rglob(f"*{ext}"))
                for pattern, message, severity in patterns:
                    for f in all_files[:50]:  # Limit scan
                        try:
                            content = f.read_text(encoding="utf-8", errors="replace")
                            for i, line in enumerate(content.split("\n"), 1):
                                if re.search(pattern, line):
                                    rel = str(f.relative_to(self.workdir))
                                    issues.append(RefactoringIssue(
                                        "slow_pattern", severity, message,
                                        rel, i, "Review and fix this pattern"
                                    ))
                                    break
                        except:
                            continue
            except:
                continue
        
        return issues

    def _find_poor_naming(self) -> list[RefactoringIssue]:
        """Find poorly named variables and functions."""
        issues = []
        
        # Python
        try:
            r = subprocess.run(
                ["rg", "-n", "--no-heading",
                 r'^\s*(def|class)\s+\w+\s*[\(:]',
                 "--glob", "*.py"],
                capture_output=True, text=True, timeout=15,
                cwd=self.workdir
            )
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    file_path = parts[0]
                    line_num = parts[1]
                    name_match = re.search(r'(def|class)\s+(\w+)', line)
                    if name_match:
                        name = name_match.group(2)
                        # Check for single-letter names (except common ones)
                        if len(name) == 1 and name not in ("i", "j", "k", "x", "y", "n", "e"):
                            issues.append(RefactoringIssue(
                                "poor_naming", "low",
                                f"Single-letter name '{name}' — use descriptive name",
                                file_path, int(line_num),
                                f"Rename '{name}' to a descriptive name"
                            ))
                        # Check for very long names
                        if len(name) > 40:
                            issues.append(RefactoringIssue(
                                "poor_naming", "info",
                                f"Very long name ({len(name)} chars) — consider shortening",
                                file_path, int(line_num),
                                "Shorten while keeping clarity"
                            ))
                        # Check for empty/placeholder names
                        if name.lower() in ("temp", "tmp", "foo", "bar", "baz", "data", "stuff", "thing"):
                            issues.append(RefactoringIssue(
                                "poor_naming", "low",
                                f"Placeholder name '{name}' — use descriptive name",
                                file_path, int(line_num),
                                f"Rename '{name}' to reflect its purpose"
                            ))
        except:
            pass
        
        return issues

    def _find_duplicate_code(self) -> list[RefactoringIssue]:
        """Find potentially duplicated code blocks."""
        issues = []
        
        # Simple approach: find similar blocks across files
        blocks_by_file = {}
        
        for ext in [".py", ".ts", ".tsx", ".js", ".jsx"]:
            try:
                for f in list(Path(self.workdir).rglob(f"*{ext}"))[:30]:
                    try:
                        content = f.read_text(encoding="utf-8", errors="replace")
                        lines = content.split("\n")
                        
                        # Extract function-sized blocks (5+ lines)
                        blocks = []
                        current_block = []
                        for i, line in enumerate(lines):
                            stripped = line.strip()
                            if ext == ".py" and (stripped.startswith("def ") or stripped.startswith("class ")):
                                if len(current_block) >= 5:
                                    blocks.append("\n".join(current_block))
                                current_block = [line]
                            elif ext in (".ts", ".tsx", ".js", ".jsx") and stripped.startswith(("function ", "export function ", "class ")):
                                if len(current_block) >= 5:
                                    blocks.append("\n".join(current_block))
                                current_block = [line]
                            else:
                                current_block.append(line)
                        if len(current_block) >= 5:
                            blocks.append("\n".join(current_block))
                        
                        if blocks:
                            rel = str(f.relative_to(self.workdir))
                            blocks_by_file[rel] = blocks
                    except:
                        continue
            except:
                continue
        
        # Compare blocks across files
        files_list = list(blocks_by_file.items())
        for i in range(len(files_list)):
            for j in range(i + 1, len(files_list)):
                file1, blocks1 = files_list[i]
                file2, blocks2 = files_list[j]
                
                for b1 in blocks1[:10]:
                    b1_lines = set(b1.split("\n"))
                    for b2 in blocks2[:10]:
                        b2_lines = set(b2.split("\n"))
                        if len(b1_lines) > 0 and len(b2_lines) > 0:
                            overlap = len(b1_lines & b2_lines) / max(len(b1_lines), len(b2_lines))
                            if overlap > 0.7 and len(b1_lines) >= 5:
                                issues.append(RefactoringIssue(
                                    "duplicate_code", "medium",
                                    f"Similar code block (~{overlap:.0%} match) in {file2}",
                                    file1, 0,
                                    f"Extract shared logic into a common module used by both {file1} and {file2}"
                                ))
                                break
                    if issues:
                        break
        
        return issues

    def _find_unused_imports(self) -> list[RefactoringIssue]:
        """Find unused imports in Python files."""
        issues = []
        
        try:
            for f in list(Path(self.workdir).rglob("*.py"))[:30]:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(content)
                    imports = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name.split(".")[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append("all")
                                for alias in node.names:
                                    if alias.name != "*":
                                        # Check if the name is used outside of the import
                                        pass
                    
                    # Simple check: find named imports and check if they're used
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            for alias in node.names:
                                if alias.name == "*":
                                    continue
                                name = alias.asname or alias.name
                                # Search for usage in file
                                usage_count = content.count(name)
                                # Count the import line itself
                                import_count = content.count(f"import {alias.name}") + content.count(f"import {name}")
                                if usage_count <= import_count:
                                    rel = str(f.relative_to(self.workdir))
                                    issues.append(RefactoringIssue(
                                        "unused_import", "low",
                                        f"Unused import: '{name}'",
                                        rel, 0, f"Remove 'from {node.module} import {alias.name}'"
                                    ))
                except (SyntaxError, Exception):
                    continue
        except:
            pass
        
        return issues

    def _count_references(self, name: str, exclude_file: str) -> int:
        """Count references to a symbol across the codebase, excluding a file."""
        try:
            r = subprocess.run(
                ["rg", "-c", rf'\b{re.escape(name)}\b', "--glob", "*.py"],
                capture_output=True, text=True, timeout=10,
                cwd=self.workdir
            )
            total = 0
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 1)
                if len(parts) >= 2 and parts[0] != exclude_file:
                    try:
                        total += int(parts[1])
                    except:
                        pass
            return total
        except:
            return 0

    def get_report(self, issues: list[RefactoringIssue] = None) -> str:
        """Generate a human-readable report from issues."""
        if issues is None:
            issues = self.scan()
        
        if not issues:
            return "## Refactoring Scan\n\nNo issues found — codebase looks healthy!"
        
        by_severity = defaultdict(list)
        for issue in issues:
            by_severity[issue.severity].append(issue)
        
        lines = ["## Refactoring Scan Report", f"Total issues: {len(issues)}"]
        
        for severity in ["critical", "high", "medium", "low", "info"]:
            items = by_severity.get(severity, [])
            if items:
                lines.append(f"\n### {severity.upper()} ({len(items)})")
                for issue in items[:10]:
                    file_info = f" {issue.file}:{issue.line}" if issue.file else ""
                    lines.append(f"- [{issue.issue_type}]{file_info}")
                    lines.append(f"  {issue.message[:100]}")
                    if issue.suggestion:
                        lines.append(f"  → {issue.suggestion[:80]}")
        
        return "\n".join(lines)
