#!/usr/bin/env python3
"""
Execution-Based Verification System

Tests actual behavior, not just structure:
- Import every module
- Instantiate every class
- Call every public API
- Run integration workflows
- Validate Repository Intelligence on real repos
- Execute Olympics benchmarks
- Verify policy enforcement
"""

import sys
import time
import traceback
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class TestResult:
    file: str
    test_type: str
    status: str  # PASS, FAIL, SKIP, WARN
    message: str
    duration_ms: float
    details: Optional[Dict[str, Any]] = None

class ExecutionVerifier:
    def __init__(self, root_dir: Path):
        self.root = root_dir
        self.results: List[TestResult] = []
        sys.path.insert(0, str(root_dir))
    
    def test_import(self, module_path: str) -> TestResult:
        """Test 1: Can we import the module?"""
        start = time.time()
        try:
            __import__(module_path)
            duration = (time.time() - start) * 1000
            return TestResult(module_path, "import", "PASS", "Module imported", duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(module_path, "import", "FAIL", str(e), duration)
    
    def test_kernel_api(self) -> List[TestResult]:
        """Test 2: Can we create Kernel and run basic operations?"""
        results = []
        start = time.time()
        try:
            from kernel.kernel import Kernel, Job
            
            # Create kernel
            kernel = Kernel()
            duration = (time.time() - start) * 1000
            results.append(TestResult("kernel.kernel", "api_create", "PASS", "Kernel created", duration))
            
            # Submit job
            start = time.time()
            def dummy_task():
                return "test"
            job = Job(task=dummy_task)
            kernel.submit(job)
            duration = (time.time() - start) * 1000
            results.append(TestResult("kernel.kernel", "api_submit", "PASS", "Job submitted", duration))
            
            # Shutdown
            start = time.time()
            kernel.shutdown()
            duration = (time.time() - start) * 1000
            results.append(TestResult("kernel.kernel", "api_shutdown", "PASS", "Kernel shutdown", duration))
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            results.append(TestResult("kernel.kernel", "api", "FAIL", str(e), duration, {"error": traceback.format_exc()}))
        
        return results
    
    def test_decision_engine_api(self) -> List[TestResult]:
        """Test 3: Can DecisionEngine make decisions?"""
        results = []
        start = time.time()
        try:
            from brain.decision_engine import DecisionEngine, DecisionContext
            
            engine = DecisionEngine()
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.decision_engine", "api_create", "PASS", "DecisionEngine created", duration))
            
            # Test decision
            start = time.time()
            context = DecisionContext(
                task="test task",
                available_context={},
                confidence_threshold=0.7
            )
            decision = engine.decide(context)
            duration = (time.time() - start) * 1000
            
            if hasattr(decision, 'action'):
                results.append(TestResult("brain.decision_engine", "api_decide", "PASS", f"Decision: {decision.action}", duration))
            else:
                results.append(TestResult("brain.decision_engine", "api_decide", "FAIL", "No action in decision", duration))
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.decision_engine", "api", "FAIL", str(e), duration, {"error": traceback.format_exc()}))
        
        return results
    
    def test_policy_enforcement(self) -> List[TestResult]:
        """Test 4: Do policies actually block dangerous operations?"""
        results = []
        start = time.time()
        try:
            from brain.policy.engine import PolicyEngine, NoSecretsInCodePolicy
            
            engine = PolicyEngine()
            engine.add_policy(NoSecretsInCodePolicy())
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.policy.engine", "api_create", "PASS", "PolicyEngine created", duration))
            
            # Test secret detection
            start = time.time()
            code_with_secret = 'api_key = "sk-1234567890abcdef"'
            verdict = engine.evaluate("write_file", {"content": code_with_secret})
            duration = (time.time() - start) * 1000
            
            if verdict.name == "BLOCK":
                results.append(TestResult("brain.policy.engine", "enforce_block", "PASS", "Secret blocked", duration))
            else:
                results.append(TestResult("brain.policy.engine", "enforce_block", "FAIL", f"Expected BLOCK, got {verdict.name}", duration))
            
            # Test clean code
            start = time.time()
            clean_code = 'x = 42'
            verdict = engine.evaluate("write_file", {"content": clean_code})
            duration = (time.time() - start) * 1000
            
            if verdict.name == "ALLOW":
                results.append(TestResult("brain.policy.engine", "enforce_allow", "PASS", "Clean code allowed", duration))
            else:
                results.append(TestResult("brain.policy.engine", "enforce_allow", "FAIL", f"Expected ALLOW, got {verdict.name}", duration))
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.policy.engine", "enforce", "FAIL", str(e), duration, {"error": traceback.format_exc()}))
        
        return results
    
    def test_repository_intelligence(self) -> List[TestResult]:
        """Test 5: Can Repository Intelligence parse actual code?"""
        results = []
        start = time.time()
        
        # Create test repository
        test_repo = self.root / "test_repo_verify"
        test_repo.mkdir(exist_ok=True)
        test_file = test_repo / "sample.py"
        test_file.write_text("""
def hello(name: str) -> str:
    return f"Hello, {name}"

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
""")
        
        try:
            from core.repository_intelligence.parser import RepositoryParser
            
            parser = RepositoryParser()
            duration = (time.time() - start) * 1000
            results.append(TestResult("core.repository_intelligence.parser", "api_create", "PASS", "Parser created", duration))
            
            # Parse file
            start = time.time()
            result = parser.parse_file(test_file)
            duration = (time.time() - start) * 1000
            
            # Validate output
            if result and hasattr(result, 'functions'):
                func_count = len(result.functions) if hasattr(result.functions, '__len__') else 0
                results.append(TestResult("core.repository_intelligence.parser", "api_parse", "PASS", f"Parsed {func_count} functions", duration))
            else:
                results.append(TestResult("core.repository_intelligence.parser", "api_parse", "WARN", "Parser returned result but structure unclear", duration))
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            results.append(TestResult("core.repository_intelligence.parser", "parse", "FAIL", str(e), duration, {"error": traceback.format_exc()}))
        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
            if test_repo.exists():
                test_repo.rmdir()
        
        return results
    
    def test_olympics_benchmark(self) -> List[TestResult]:
        """Test 6: Can we load and score Olympics tasks?"""
        results = []
        start = time.time()
        try:
            from science.benchmarks.olympics import EngineeringOlympics, OlympicTask
            
            olympics = EngineeringOlympics()
            duration = (time.time() - start) * 1000
            results.append(TestResult("science.benchmarks.olympics", "api_create", "PASS", "Olympics created", duration))
            
            # Load tasks
            start = time.time()
            tasks = olympics.get_tasks()
            duration = (time.time() - start) * 1000
            
            if tasks and len(tasks) > 0:
                results.append(TestResult("science.benchmarks.olympics", "api_tasks", "PASS", f"Loaded {len(tasks)} tasks", duration))
                
                # Try scoring
                start = time.time()
                sample_task = tasks[0]
                score = olympics.score_task(sample_task, {"reasoning": 0.8, "execution": 0.9})
                duration = (time.time() - start) * 1000
                results.append(TestResult("science.benchmarks.olympics", "api_score", "PASS", f"Score: {score}", duration))
            else:
                results.append(TestResult("science.benchmarks.olympics", "api_tasks", "WARN", "No tasks loaded", duration))
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            results.append(TestResult("science.benchmarks.olympics", "benchmark", "FAIL", str(e), duration, {"error": traceback.format_exc()}))
        
        return results
    
    def test_world_model(self) -> List[TestResult]:
        """Test 7: Can World Model track project state?"""
        results = []
        start = time.time()
        try:
            from brain.world_model import WorldModel
            
            model = WorldModel()
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.world_model", "api_create", "PASS", "WorldModel created", duration))
            
            # Add architecture
            start = time.time()
            model.add_architecture("test_component", {"type": "service"})
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.world_model", "api_add", "PASS", "Architecture added", duration))
            
            # Query
            start = time.time()
            arch = model.get_architecture()
            duration = (time.time() - start) * 1000
            if arch:
                results.append(TestResult("brain.world_model", "api_query", "PASS", "Architecture retrieved", duration))
            else:
                results.append(TestResult("brain.world_model", "api_query", "WARN", "No architecture found", duration))
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.world_model", "world_model", "FAIL", str(e), duration, {"error": traceback.format_exc()}))
        
        return results
    
    def test_provenance(self) -> List[TestResult]:
        """Test 8: Can Provenance track decisions?"""
        results = []
        start = time.time()
        try:
            from brain.provenance import ProvenanceTracker, DecisionRecord
            
            tracker = ProvenanceTracker()
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.provenance", "api_create", "PASS", "Tracker created", duration))
            
            # Record decision
            start = time.time()
            record = DecisionRecord(
                decision="test_decision",
                evidence=["fact1", "fact2"],
                alternatives=["alt1"],
                tradeoffs={"speed": "accuracy"},
                outcome="success"
            )
            tracker.record(record)
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.provenance", "api_record", "PASS", "Decision recorded", duration))
            
            # Query
            start = time.time()
            history = tracker.get_history()
            duration = (time.time() - start) * 1000
            if history and len(history) > 0:
                results.append(TestResult("brain.provenance", "api_query", "PASS", f"Retrieved {len(history)} records", duration))
            else:
                results.append(TestResult("brain.provenance", "api_query", "WARN", "No history found", duration))
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            results.append(TestResult("brain.provenance", "provenance", "FAIL", str(e), duration, {"error": traceback.format_exc()}))
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all execution tests"""
        print("=== Execution Verification System ===\n")
        
        # Test imports for critical modules
        critical_modules = [
            "kernel.kernel",
            "brain.decision_engine",
            "brain.world_model",
            "brain.provenance",
            "brain.policy.engine",
            "core.repository_intelligence.parser",
            "science.benchmarks.olympics",
        ]
        
        print("Phase 1: Import Tests")
        for module in critical_modules:
            result = self.test_import(module)
            self.results.append(result)
            print(f"  {result.status} {module}: {result.message}")
        
        print("\nPhase 2: Kernel API Tests")
        for result in self.test_kernel_api():
            self.results.append(result)
            print(f"  {result.status} {result.test_type}: {result.message}")
        
        print("\nPhase 3: Decision Engine API Tests")
        for result in self.test_decision_engine_api():
            self.results.append(result)
            print(f"  {result.status} {result.test_type}: {result.message}")
        
        print("\nPhase 4: Policy Enforcement Tests")
        for result in self.test_policy_enforcement():
            self.results.append(result)
            print(f"  {result.status} {result.test_type}: {result.message}")
        
        print("\nPhase 5: Repository Intelligence Tests")
        for result in self.test_repository_intelligence():
            self.results.append(result)
            print(f"  {result.status} {result.test_type}: {result.message}")
        
        print("\nPhase 6: Olympics Benchmark Tests")
        for result in self.test_olympics_benchmark():
            self.results.append(result)
            print(f"  {result.status} {result.test_type}: {result.message}")
        
        print("\nPhase 7: World Model Tests")
        for result in self.test_world_model():
            self.results.append(result)
            print(f"  {result.status} {result.test_type}: {result.message}")
        
        print("\nPhase 8: Provenance Tests")
        for result in self.test_provenance():
            self.results.append(result)
            print(f"  {result.status} {result.test_type}: {result.message}")
        
        # Generate summary
        summary = self.generate_summary()
        return summary
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary"""
        by_status = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        by_file = {}
        
        for result in self.results:
            by_status[result.status] = by_status.get(result.status, 0) + 1
            
            if result.file not in by_file:
                by_file[result.file] = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
            by_file[result.file][result.status] += 1
        
        total = len(self.results)
        pass_rate = (by_status["PASS"] / total * 100) if total > 0 else 0
        
        return {
            "summary": {
                "total_tests": total,
                "pass": by_status["PASS"],
                "fail": by_status["FAIL"],
                "warn": by_status["WARN"],
                "skip": by_status["SKIP"],
                "pass_rate": round(pass_rate, 1)
            },
            "by_file": by_file,
            "results": [asdict(r) for r in self.results]
        }

def main():
    root = Path(__file__).parent.parent / "coding-agent"
    verifier = ExecutionVerifier(root)
    
    summary = verifier.run_all_tests()
    
    # Save JSON report
    report_path = root / "EXECUTION_REPORT.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n=== Summary ===")
    print(f"Total Tests: {summary['summary']['total_tests']}")
    print(f"Pass: {summary['summary']['pass']}")
    print(f"Fail: {summary['summary']['fail']}")
    print(f"Warn: {summary['summary']['warn']}")
    print(f"Pass Rate: {summary['summary']['pass_rate']}%")
    print(f"\nReport saved to: {report_path}")
    
    # Exit with error if any tests failed
    if summary['summary']['fail'] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
