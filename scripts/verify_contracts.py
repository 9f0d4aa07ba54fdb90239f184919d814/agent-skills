#!/usr/bin/env python3
"""
Contract-Based Verification System

This is the Definition of Done.
Every component must satisfy its contract or the build fails.

For every failure, this generates:
- Issue ID
- Severity
- Suggested fix
- Required tests
- Work estimation
"""

import sys
import time
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

# ============================================================================
# CONTRACTS - The Ground Truth
# ============================================================================

KERNEL_CONTRACT = {
    "module": "kernel.kernel",
    "classes": ["Kernel", "Job"],
    "kernel_methods": [
        "initialize",
        "shutdown",
        "process_task",
        "process_task_async",
        "get_job_result",
        "register_worker",
        "get_worker",
        "list_workers",
        "get_kernel_stats"
    ],
    "job_init_params": ["name", "description"],  # Expected parameters
}

DECISION_ENGINE_CONTRACT = {
    "module": "brain.decision_engine",
    "classes": ["DecisionEngine", "Decision", "DecisionType"],
    "decision_engine_methods": ["decide", "get_decision_history", "analyze_decision_quality"],
}

WORLD_MODEL_CONTRACT = {
    "module": "brain.world_model",
    "classes": ["WorldModel"],
    "world_model_methods": [
        "save",
        "set_architecture",
        "add_layer",
        "add_component",
        "get_architecture_summary",
        "add_debt",
        "get_debt_summary",
        "get_full_snapshot"
    ],
}

POLICY_CONTRACT = {
    "module": "brain.policy.engine",
    "classes": ["PolicyEngine", "PolicyVerdict", "BasePolicy"],
    "policy_engine_methods": ["register_policy", "evaluate", "get_active_policies"],
}

PROVENANCE_CONTRACT = {
    "module": "brain.provenance",
    "classes": ["DecisionRecord", "DecisionProvenanceStore"],
    "provenance_store_methods": ["record_decision", "get_decision", "query", "get_statistics"],
}

REPOSITORY_INTELLIGENCE_CONTRACT = {
    "module": "core.repository_intelligence.parser",
    "classes": ["RepositoryParser", "ParseResult"],
    "parser_methods": ["parse_file", "parse_directory", "get_symbols"],
}

OLYMPICS_CONTRACT = {
    "module": "science.benchmarks.olympics",
    "classes": ["EngineeringOlympics", "OlympicTask", "BenchmarkResult"],
    "olympics_methods": ["load_tasks", "run_task", "score_task", "get_leaderboard"],
}

ALL_CONTRACTS = [
    KERNEL_CONTRACT,
    DECISION_ENGINE_CONTRACT,
    WORLD_MODEL_CONTRACT,
    POLICY_CONTRACT,
    PROVENANCE_CONTRACT,
    REPOSITORY_INTELLIGENCE_CONTRACT,
    OLYMPICS_CONTRACT,
]

# ============================================================================
# Issue Generation
# ============================================================================

class Severity(Enum):
    CRITICAL = "critical"  # P0 - blocks everything
    HIGH = "high"          # P1 - blocks major features
    MEDIUM = "medium"      # P2 - reduces quality
    LOW = "low"            # P3 - nice to have

@dataclass
class Issue:
    issue_id: str
    component: str
    failure: str
    severity: Severity
    suggested_fix: str
    tests_required: List[str]
    estimated_effort: str  # "1h", "4h", "1d", "3d", "1w"
    status: str = "open"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "component": self.component,
            "failure": self.failure,
            "severity": self.severity.value,
            "suggested_fix": self.suggested_fix,
            "tests_required": self.tests_required,
            "estimated_effort": self.estimated_effort,
            "status": self.status
        }
    
    def to_markdown(self) -> str:
        return f"""## Issue {self.issue_id}

**Component:** `{self.component}`

**Failure:**
```
{self.failure}
```

**Severity:** {self.severity.value.upper()}

**Suggested Fix:**
{self.suggested_fix}

**Tests Required:**
{chr(10).join(f'- {t}' for t in self.tests_required)}

**Estimated Effort:** {self.estimated_effort}

**Status:** {self.status}

---
"""

# ============================================================================
# Contract Verifier
# ============================================================================

@dataclass
class ContractResult:
    contract_name: str
    test_type: str
    status: str  # PASS, FAIL, SKIP
    message: str
    duration_ms: float
    issue: Optional[Issue] = None

class ContractVerifier:
    def __init__(self, root_dir: Path):
        self.root = root_dir
        self.results: List[ContractResult] = []
        self.issues: List[Issue] = []
        sys.path.insert(0, str(root_dir))
    
    def verify_all_contracts(self):
        """Verify all contracts"""
        print("=== Contract Verification System ===\n")
        
        for contract in ALL_CONTRACTS:
            print(f"Verifying {contract['module']}...")
            self._verify_contract(contract)
        
        print(f"\n=== Summary ===")
        print(f"Total Tests: {len(self.results)}")
        print(f"Pass: {sum(1 for r in self.results if r.status == 'PASS')}")
        print(f"Fail: {sum(1 for r in self.results if r.status == 'FAIL')}")
        print(f"Issues Generated: {len(self.issues)}")
    
    def _verify_contract(self, contract: Dict[str, Any]):
        """Verify a single contract"""
        module_name = contract["module"]
        
        # Test 1: Import
        start = time.time()
        try:
            module = __import__(module_name, fromlist=['*'])
            duration = (time.time() - start) * 1000
            self.results.append(ContractResult(
                module_name, "import", "PASS",
                f"Module imported", duration
            ))
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.results.append(ContractResult(
                module_name, "import", "FAIL",
                f"Import failed: {e}", duration
            ))
            
            # Generate issue
            issue = self._create_import_issue(module_name, str(e))
            self.issues.append(issue)
            return  # Can't continue without import
        
        # Test 2: Classes exist
        for class_name in contract.get("classes", []):
            start = time.time()
            if hasattr(module, class_name):
                duration = (time.time() - start) * 1000
                self.results.append(ContractResult(
                    module_name, "class_exists", "PASS",
                    f"Class {class_name} exists", duration
                ))
            else:
                duration = (time.time() - start) * 1000
                self.results.append(ContractResult(
                    module_name, "class_exists", "FAIL",
                    f"Class {class_name} missing", duration
                ))
                issue = self._create_class_missing_issue(module_name, class_name)
                self.issues.append(issue)
        
        # Test 3: Methods exist
        for class_name in contract.get("classes", []):
            if not hasattr(module, class_name):
                continue
            
            cls = getattr(module, class_name)
            method_key = f"{class_name.lower()}_methods"
            
            for method_name in contract.get(method_key, []):
                start = time.time()
                if hasattr(cls, method_name):
                    duration = (time.time() - start) * 1000
                    self.results.append(ContractResult(
                        module_name, "method_exists", "PASS",
                        f"{class_name}.{method_name} exists", duration
                    ))
                else:
                    duration = (time.time() - start) * 1000
                    self.results.append(ContractResult(
                        module_name, "method_exists", "FAIL",
                        f"{class_name}.{method_name} missing", duration
                    ))
                    issue = self._create_method_missing_issue(
                        module_name, class_name, method_name
                    )
                    self.issues.append(issue)
    
    def _create_import_issue(self, module: str, error: str) -> Issue:
        """Generate issue for import failure"""
        issue_id = f"IMP-{hashlib.md5(module.encode()).hexdigest()[:6].upper()}"
        
        # Determine severity
        if "core.repository_intelligence" in module:
            severity = Severity.CRITICAL  # P0 blocker
            effort = "1w"
        else:
            severity = Severity.HIGH
            effort = "3d"
        
        return Issue(
            issue_id=issue_id,
            component=module,
            failure=f"Module import failed: {error}",
            severity=severity,
            suggested_fix=f"Create {module.replace('.', '/')} with required classes and methods. Check if __init__.py files exist in parent directories.",
            tests_required=[
                f"tests/test_{module.split('.')[-1]}_import.py",
                f"tests/test_{module.split('.')[-1]}_api.py"
            ],
            estimated_effort=effort
        )
    
    def _create_class_missing_issue(self, module: str, class_name: str) -> Issue:
        """Generate issue for missing class"""
        issue_id = f"CLS-{hashlib.md5(f'{module}.{class_name}'.encode()).hexdigest()[:6].upper()}"
        
        return Issue(
            issue_id=issue_id,
            component=f"{module}.{class_name}",
            failure=f"Class {class_name} not found in {module}",
            severity=Severity.HIGH,
            suggested_fix=f"Implement class {class_name} in {module} or update contract if class was renamed/removed.",
            tests_required=[
                f"tests/test_{class_name.lower()}.py"
            ],
            estimated_effort="1d"
        )
    
    def _create_method_missing_issue(self, module: str, class_name: str, method: str) -> Issue:
        """Generate issue for missing method"""
        issue_id = f"API-{hashlib.md5(f'{module}.{class_name}.{method}'.encode()).hexdigest()[:6].upper()}"
        
        return Issue(
            issue_id=issue_id,
            component=f"{module}.{class_name}.{method}",
            failure=f"Method {method}() not found in {class_name}",
            severity=Severity.MEDIUM,
            suggested_fix=f"Implement {class_name}.{method}() method or update contract if API changed.",
            tests_required=[
                f"tests/test_{class_name.lower()}_api.py"
            ],
            estimated_effort="4h"
        )
    
    def generate_reports(self, output_dir: Path):
        """Generate all reports"""
        output_dir.mkdir(exist_ok=True)
        
        # JSON report
        json_report = {
            "summary": {
                "total_tests": len(self.results),
                "pass": sum(1 for r in self.results if r.status == "PASS"),
                "fail": sum(1 for r in self.results if r.status == "FAIL"),
                "issues_generated": len(self.issues)
            },
            "results": [asdict(r) for r in self.results],
            "issues": [i.to_dict() for i in self.issues]
        }
        
        json_path = output_dir / "CONTRACT_VERIFICATION.json"
        with open(json_path, 'w') as f:
            json.dump(json_report, f, indent=2)
        print(f"\nJSON report: {json_path}")
        
        # Issues markdown
        md_path = output_dir / "GENERATED_ISSUES.md"
        with open(md_path, 'w') as f:
            f.write("# Auto-Generated Issues\n\n")
            f.write("These issues were automatically generated by contract verification.\n")
            f.write(f"Total Issues: {len(self.issues)}\n\n")
            
            # Group by severity
            by_severity = {
                Severity.CRITICAL: [],
                Severity.HIGH: [],
                Severity.MEDIUM: [],
                Severity.LOW: []
            }
            for issue in self.issues:
                by_severity[issue.severity].append(issue)
            
            for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
                issues = by_severity[severity]
                if issues:
                    f.write(f"## {severity.value.upper()} Priority ({len(issues)} issues)\n\n")
                    for issue in issues:
                        f.write(issue.to_markdown())
        
        print(f"Issues report: {md_path}")
        
        # Matrix report
        matrix_path = output_dir / "VERIFICATION_MATRIX.md"
        with open(matrix_path, 'w', encoding='utf-8') as f:
            f.write("# Verification Matrix\n\n")
            f.write("| Component | Import | Classes | Methods | Status | Completion |\n")
            f.write("|-----------|--------|---------|---------|--------|------------|\n")
            
            for contract in ALL_CONTRACTS:
                module = contract["module"]
                module_results = [r for r in self.results if r.contract_name == module]
                
                import_pass = any(r.status == "PASS" and r.test_type == "import" for r in module_results)
                class_pass = sum(1 for r in module_results if r.status == "PASS" and r.test_type == "class_exists")
                class_total = len(contract.get("classes", []))
                method_pass = sum(1 for r in module_results if r.status == "PASS" and r.test_type == "method_exists")
                method_total = sum(len(contract.get(f"{c.lower()}_methods", [])) for c in contract.get("classes", []))
                
                total_tests = 1 + class_total + method_total  # import + classes + methods
                passed_tests = (1 if import_pass else 0) + class_pass + method_pass
                completion = int((passed_tests / total_tests * 100) if total_tests > 0 else 0)
                
                status = "✅" if completion == 100 else "⚠️" if completion >= 50 else "❌"
                
                f.write(f"| {module} | {'✅' if import_pass else '❌'} | {class_pass}/{class_total} | {method_pass}/{method_total} | {status} | {completion}% |\n")
        
        print(f"Matrix report: {matrix_path}")

def main():
    root = Path(__file__).parent.parent / "coding-agent"
    verifier = ContractVerifier(root)
    
    verifier.verify_all_contracts()
    verifier.generate_reports(root)
    
    # Exit with error if issues found
    if len(verifier.issues) > 0:
        print(f"\nVerification FAILED: {len(verifier.issues)} issues found")
        sys.exit(1)
    else:
        print(f"\nVerification PASSED: All contracts satisfied")
        sys.exit(0)

if __name__ == "__main__":
    main()
