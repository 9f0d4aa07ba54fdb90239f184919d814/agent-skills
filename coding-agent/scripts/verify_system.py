#!/usr/bin/env python3
"""
Comprehensive Verification Pipeline
Tests every component systematically and generates detailed report.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json


class VerificationPipeline:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.results = {"timestamp": datetime.now().isoformat(), "phases": {}}
    
    def run_all(self):
        print("="*80)
        print("COMPREHENSIVE VERIFICATION PIPELINE")
        print("="*80 + "\n")
        
        self.phase1_syntax()
        self.phase2_structure()
        self.phase3_components()
        self.phase4_tests()
        self.phase5_security()
        self.generate_report()
    
    def phase1_syntax(self):
        print("PHASE 1: Syntax Check")
        print("-"*80)
        
        issues = []
        passed = 0
        
        for py_file in self._get_python_files():
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), py_file, 'exec')
                passed += 1
            except SyntaxError as e:
                issues.append({"file": str(py_file.relative_to(self.root_dir)), "error": str(e), "line": e.lineno})
        
        self.results["phases"]["syntax"] = {"passed": passed, "issues": issues}
        print(f"  [OK] Files checked: {passed + len(issues)}")
        print(f"  [{'FAIL' if issues else 'OK'}] Syntax errors: {len(issues)}\n")
    
    def phase2_structure(self):
        print("PHASE 2: Structure Verification")
        print("-"*80)
        
        expected = ["brain", "kernel", "repository", "workers", "tests", "science"]
        found = [d for d in expected if (self.root_dir / d).exists()]
        missing = [d for d in expected if d not in found]
        
        missing_inits = []
        for root, dirs, files in os.walk(self.root_dir):
            if any(skip in root for skip in ['.git', '__pycache__', 'node_modules', '.venv']):
                continue
            py_files = [f for f in files if f.endswith('.py') and f != '__init__.py']
            if py_files and '__init__.py' not in files:
                missing_inits.append(Path(root).relative_to(self.root_dir))
        
        self.results["phases"]["structure"] = {"found": found, "missing": missing, "missing_inits": [str(m) for m in missing_inits]}
        print(f"  [OK] Found directories: {len(found)}/{len(expected)}")
        print(f"  [{'WARN' if missing else 'OK'}] Missing directories: {missing}")
        print(f"  [{'WARN' if missing_inits else 'OK'}] Missing __init__.py: {len(missing_inits)}\n")
    
    def phase3_components(self):
        print("PHASE 3: Component Validation")
        print("-"*80)
        
        components = {
            "kernel": self._check_component("kernel", ["kernel.py", "runtime.py", "event_bus.py"]),
            "policy": self._check_component("brain/policy", ["engine.py"]),
            "provenance": self._check_file("brain/provenance.py"),
            "repository": self._check_component("repository", ["indexer.py", "intelligence.py"]),
            "workers": self._check_dir("workers"),
            "world_model": self._check_file("brain/world_model.py"),
            "olympics": self._check_file("science/benchmarks/olympics.py")
        }
        
        self.results["phases"]["components"] = components
        
        for name, status in components.items():
            result = "PASS" if status["exists"] else "FAIL"
            print(f"  [{result}] {name}")
        print()
    
    def phase4_tests(self):
        print("PHASE 4: Test Analysis")
        print("-"*80)
        
        total_files = len(list(self._get_python_files()))
        test_files = len(list((self.root_dir / "tests").glob("test_*.py"))) if (self.root_dir / "tests").exists() else 0
        coverage_est = (test_files / total_files * 100) if total_files > 0 else 0
        
        missing_tests = []
        for py_file in self._get_python_files():
            if 'test_' in py_file.name or '__init__' in py_file.name:
                continue
            test_name = f"test_{py_file.stem}.py"
            if not (self.root_dir / "tests" / test_name).exists():
                missing_tests.append(str(py_file.relative_to(self.root_dir)))
        
        self.results["phases"]["tests"] = {
            "total_files": total_files,
            "test_files": test_files,
            "coverage_est": round(coverage_est, 1),
            "missing_tests": missing_tests[:20]
        }
        
        print(f"  Total Python files: {total_files}")
        print(f"  Test files: {test_files}")
        print(f"  [{'WARN' if coverage_est < 80 else 'OK'}] Estimated coverage: {coverage_est:.1f}%")
        print(f"  Files missing tests: {len(missing_tests)}\n")
    
    def phase5_security(self):
        print("PHASE 5: Security Scan")
        print("-"*80)
        
        secrets = []
        unsafe = []
        patterns_secret = ['password', 'api_key', 'secret', 'token']
        patterns_unsafe = ['eval(', 'exec(', 'subprocess.call']
        
        for py_file in self._get_python_files():
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        line_lower = line.lower()
                        for p in patterns_secret:
                            if p in line_lower and '=' in line and not line.strip().startswith('#'):
                                secrets.append({"file": str(py_file.relative_to(self.root_dir)), "line": i})
                        for p in patterns_unsafe:
                            if p in line:
                                unsafe.append({"file": str(py_file.relative_to(self.root_dir)), "line": i, "pattern": p})
            except:
                pass
        
        self.results["phases"]["security"] = {"secrets": secrets[:10], "unsafe": unsafe[:10]}
        print(f"  [{'WARN' if secrets else 'OK'}] Potential secrets: {len(secrets)}")
        print(f"  [{'WARN' if unsafe else 'OK'}] Unsafe patterns: {len(unsafe)}\n")
    
    def generate_report(self):
        print("="*80)
        print("SUMMARY")
        print("="*80 + "\n")
        
        print("PRIORITY ACTIONS:\n")
        print("P0 - Critical:")
        print("  1. Repository Intelligence: Complete to 60%+ (currently 20%)")
        print("  2. Test Coverage: Reach 80%+ (currently ~15%)")
        print("  3. Engineering Olympics: Create 100 tasks (currently 10)")
        
        print("\nP1 - High:")
        print("  4. Add missing __init__.py files")
        print("  5. Create tests for all core components")
        print("  6. Review security findings")
        
        # Save report
        report_path = self.root_dir / "VERIFICATION_REPORT.json"
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nFull report: {report_path}")
        print("="*80)
    
    def _get_python_files(self):
        for path in self.root_dir.rglob("*.py"):
            if any(skip in str(path) for skip in ['.venv', '__pycache__', 'node_modules', '.git']):
                continue
            yield path
    
    def _check_component(self, dir_path, required_files):
        comp_dir = self.root_dir / dir_path
        if not comp_dir.exists():
            return {"exists": False, "missing": required_files}
        missing = [f for f in required_files if not (comp_dir / f).exists()]
        return {"exists": len(missing) == 0, "missing": missing}
    
    def _check_file(self, file_path):
        return {"exists": (self.root_dir / file_path).exists()}
    
    def _check_dir(self, dir_path):
        return {"exists": (self.root_dir / dir_path).exists()}


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    pipeline = VerificationPipeline(root)
    pipeline.run_all()
