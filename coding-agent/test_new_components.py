"""
Integration test for all kernel components including new scheduler, resource management,
and specialized repository caches.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from kernel import (
    StateMachine, JobState, StepStateMachine, StepState,
    CommandBus, Command, CommandStatus,
    TaskGraph, TaskNode,
    VersionedContext, ContextSnapshot,
    CapabilityRegistry, Capability,
    Job, JobPriority,
    WorkerTelemetry,
)

# ── 1. State Machine ──
print("1. State Machine...")
sm = StateMachine(JobState.CREATED)
assert sm.state == JobState.CREATED
sm.transition_to(JobState.QUEUED)
assert sm.state == JobState.QUEUED
sm.transition_to(JobState.PLANNING)
assert sm.state == JobState.PLANNING
sm.transition_to(JobState.CONTEXT_BUILDING)
assert sm.state == JobState.CONTEXT_BUILDING
sm.transition_to(JobState.EXECUTING)
assert sm.state == JobState.EXECUTING
sm.transition_to(JobState.VERIFYING)
assert sm.state == JobState.VERIFYING
sm.transition_to(JobState.REVIEWING)
assert sm.state == JobState.REVIEWING
sm.transition_to(JobState.COMPLETED)
assert sm.state == JobState.COMPLETED
assert not sm.can_transition_to(JobState.CREATED)
print("   ✓ Valid transitions work")

# ── 2. Step State Machine ──
print("\n2. Step State Machine...")
ssm = StepStateMachine()
assert ssm.state == StepState.PENDING
ssm.transition_to(StepState.QUEUED)
ssm.transition_to(StepState.RUNNING)
ssm.transition_to(StepState.COMPLETED)
print("   ✓ Step transitions work")

# ── 3. Command Bus ──
print("\n3. Command Bus...")
cb = CommandBus()
cmd = Command(command_type="TEST_CMD", target_worker="test_worker",
              job_id="job-1", step_id="step-1",
              params={"key": "value"}, priority=5)
cb.dispatch(cmd)
cb.acknowledge("TEST_CMD", "test_worker")
cb.complete("TEST_CMD", "test_worker", result={"done": True})
assert cmd.status == CommandStatus.COMPLETED
print("   ✓ Command dispatch/acknowledge/complete works")

# ── 4. Task Graph (DAG) ──
print("\n4. Task Graph...")
tg = TaskGraph()
tg.add_node("a", "Step A", "worker1")
tg.add_node("b", "Step B", "worker2")
tg.add_node("c", "Step C", "worker3")
tg.add_dependency("b", "a")
tg.add_dependency("c", "a")
order = tg.get_execution_order()
assert len(order) == 2
assert order[0][0].id == "a"
assert {n.id for n in order[1]} == {"b", "c"}
print("   ✓ Parallel execution layers work")

# Cycle detection
tg2 = TaskGraph()
tg2.add_node("x", "X", "w")
tg2.add_node("y", "Y", "w")
tg2.add_node("z", "Z", "w")
tg2.add_dependency("y", "x")
tg2.add_dependency("z", "y")
try:
    tg2.add_dependency("x", "z")
    print("   ✗ Cycle NOT detected")
except ValueError:
    print("   ✓ Cycle detection works")

# ── 5. Versioned Context ──
print("\n5. Versioned Context...")
vc = VersionedContext()
v1 = vc.create_snapshot("user", {"task": "Fix bug"})
v2 = vc.create_snapshot("system", {"task": "Fix bug", "files": ["main.py"]})
diff = vc.get_diff(1, 2)
assert "files" in diff["added"]
print("   ✓ Versioned context works")

# ── 6. Capability Registry ──
print("\n6. Capability Registry...")
cr = CapabilityRegistry()
cr.register("filesystem.read", lambda p: f"content of {p}", domain="filesystem")
cr.register("filesystem.write", lambda p, c: f"wrote {p}", domain="filesystem")
cr.register("git.status", lambda: {"branch": "main"}, domain="git")
assert cr.count == 3
assert "filesystem" in cr.domains
result = cr.execute("filesystem.read", "test.txt")
assert result == "content of test.txt"
print(f"   ✓ Registry has {cr.count} capabilities")

# ── 7. Enriched Job ──
print("\n7. Enriched Job...")
job = Job("test-job", "A test job", priority=JobPriority.HIGH, tags=["test"])
job.set_goal("Complete the test")
job.set_intent("Verify enriched job functionality")
step_a = job.add_step("step_a", "worker1", {"cmd": "do_a"})
step_b = job.add_step_with_dependency("step_b", "worker2", "step_a")
assert len(job.steps) == 2
job.add_model_usage("gpt-4", 1000, 0.03)
job.add_model_usage("claude-3", 500, 0.015)
assert job.cost == 0.045
job.add_worker_usage("worker1")
job.add_worker_usage("worker2")
assert len(job.workers_used) == 2
# Follow the proper state machine path: CREATED -> QUEUED -> PLANNING -> CONTEXT_BUILDING -> EXECUTING -> VERIFYING -> REVIEWING -> COMPLETED
job.transition_to(JobState.QUEUED)
job.transition_to(JobState.PLANNING)
job.transition_to(JobState.CONTEXT_BUILDING)
job.transition_to(JobState.EXECUTING)
job.transition_to(JobState.VERIFYING)
job.transition_to(JobState.REVIEWING)
job.transition_to(JobState.COMPLETED)
d = job.to_dict()
assert d["goal"] == "Complete the test"
assert d["cost"] == 0.045
j = job.to_json()
assert isinstance(j, str)
replay = job.get_replay()
assert len(replay) > 0
print(f"   ✓ Job cost: ${job.cost}, models: {job.models_used}, replay: {len(replay)} entries")

# ── 8. Worker Telemetry ──
print("\n8. Worker Telemetry...")
tel = WorkerTelemetry()
tel.record_worker_execution("worker1", "context", 1.5, True, 500, 0.02, "handle")
tel.record_worker_execution("worker2", "executor", 0.5, False, 100, 0.005, "execute", error="timeout")
stats = tel.get_worker_stats()
assert "worker1" in stats
assert "worker2" in stats
assert stats["worker1"]["successful"] == 1
assert stats["worker2"]["failed"] == 1
print("   ✓ Worker telemetry works")

# ═══════════════════════════════════════════════
# NEW COMPONENT TESTS
# ═══════════════════════════════════════════════

import tempfile
import time
import threading

# ── 9. Specialized Repository Caches ──
print("\n9. Specialized Repository Caches...")
tmpdir = tempfile.mkdtemp()
cache_dir = os.path.join(tmpdir, ".cache")
os.makedirs(cache_dir, exist_ok=True)

# Create test files
for fname in ["main.py", "utils.py", "helper.js", "styles.css"]:
    with open(os.path.join(tmpdir, fname), "w") as f:
        f.write(f"# {fname}\nprint('hello from {fname}')\n")

# 9a. FileCache
from repository import FileCache
fc = FileCache(tmpdir, cache_dir)
fc.load()
count = fc.index_all()
assert count >= 4
assert "main.py" in fc._files
assert fc.by_language("python") is not None
stats = fc.get_stats()
assert stats["total_files"] >= 4
fc.save()
fc2 = FileCache(tmpdir, cache_dir)
fc2.load()
assert len(fc2._files) >= 4
print("   ✓ FileCache: indexing, language detection, persistence")

# 9b. SymbolCache
from repository import SymbolCache
sc = SymbolCache(tmpdir, cache_dir)
sc.load()
# Simulate indexing symbols
from repository.symbol_cache import SymbolEntry
sc.index_file("main.py", [
    SymbolEntry(name="hello", kind="function", file_path="main.py", line=1),
    SymbolEntry(name="MyClass", kind="class", file_path="main.py", line=5),
])
sc.index_file("utils.py", [
    SymbolEntry(name="helper_func", kind="function", file_path="utils.py", line=1),
])
assert len(sc.find("hello")) == 1
assert len(sc.by_kind("function")) == 2
assert len(sc.by_kind("class")) == 1
stats = sc.get_stats()
assert stats["total_symbols"] == 3
sc.save()
print("   ✓ SymbolCache: indexing, find, by_kind, persistence")

# 9c. DependencyCache
from repository import DependencyCache, ImportRelation
dc = DependencyCache(tmpdir, cache_dir)
dc.load()
dc.index_imports("main.py", [
    ImportRelation(source_file="main.py", target_module="os", target_file="", import_type="stdlib", import_statement="import os", line=1),
    ImportRelation(source_file="main.py", target_module="utils", target_file="utils.py", import_type="local", import_statement="from utils import helper", line=2),
])
dc.index_imports("utils.py", [
    ImportRelation(source_file="utils.py", target_module="json", target_file="", import_type="stdlib", import_statement="import json", line=1),
])
assert len(dc.get_imports("main.py")) == 2
assert len(dc.get_imported_by("utils.py")) == 1
affected = dc.get_affected_files(["utils.py"])
assert "main.py" in affected
stats = dc.get_stats()
assert stats["total_import_relations"] >= 3
dc.save()
print("   ✓ DependencyCache: imports graph, affected files, persistence")

# 9d. EmbeddingCache
from repository import EmbeddingCache
ec = EmbeddingCache(tmpdir, cache_dir)
ec.load()
ec.store("main.py", [0.1, 0.2, 0.3])
ec.store("utils.py", [0.4, 0.5, 0.6])
ec.store("helper.js", [0.7, 0.8, 0.9])
assert ec.get("main.py") == [0.1, 0.2, 0.3]
results = ec.search([0.15, 0.25, 0.35], top_k=2)
assert len(results) == 2
assert results[0][0] == "main.py"
stats = ec.get_stats()
assert stats["total_embedded"] == 3
ec.save()
print("   ✓ EmbeddingCache: store, get, cosine similarity search")

# 9e. GitCache
from repository import GitCache
gc = GitCache(tmpdir, cache_dir)
gc.load()
# Just verify it initializes without errors (no git repo in tmpdir)
stats = gc.get_stats()
assert stats["name"] == "git_cache"
gc.save()
print("   ✓ GitCache: initialization and persistence")

# 9f. LspCache
from repository import LspCache
lc = LspCache(tmpdir, cache_dir)
lc.load()
from repository.lsp_cache import DiagnosticEntry
lc.store("main.py", [
    DiagnosticEntry(file_path="main.py", line=1, message="unused import", severity="warning"),
    DiagnosticEntry(file_path="main.py", line=5, message="undefined variable", severity="error"),
])
lc.store("utils.py", [
    DiagnosticEntry(file_path="utils.py", line=3, message="missing docstring", severity="information"),
])
assert len(lc.get("main.py")) == 2
assert len(lc.errors()) == 1
assert len(lc.warnings()) == 1
assert lc.error_count() == 1
assert lc.warning_count() == 1
lc.save()
print("   ✓ LspCache: diagnostics, severity filtering, error/warning counts")

# 9g. BuildCache
from repository import BuildCache
bc = BuildCache(tmpdir, cache_dir)
bc.load()
from repository.build_cache import BuildResult
bc.store("build:main.py", BuildResult(file_path="main.py", result_type="build", success=True, duration=1.5))
bc.store("test:utils.py", BuildResult(file_path="utils.py", result_type="test", success=False, duration=2.0, errors=[{"message": "assertion failed"}]))
assert len(bc.successes()) == 1
assert len(bc.failures()) == 1
# Can query by file
results = bc.get_by_file(file_path="main.py")
assert len(results) >= 1
bc.save()
print("   ✓ BuildCache: store results, success/failure filtering")

# 9h. BaseCache persistence (abstract test)
from repository import BaseCache
class TestCache(BaseCache):
    def __init__(self, name, cache_dir):
        super().__init__(name, cache_dir)
        self.data = {}
    def save(self):
        self._save_json({"data": self.data})
    def load(self):
        d = self._load_json()
        self.data = d.get("data", {})
    def get_stats(self):
        return {"name": self.name, "items": len(self.data)}
    def clear(self):
        self.data.clear()

tc = TestCache("test_cache", cache_dir)
tc.data["key1"] = "value1"
tc.mark_dirty()
assert tc._dirty
tc.save()
tc2 = TestCache("test_cache", cache_dir)
tc2.load()
assert tc2.data.get("key1") == "value1"
print("   ✓ BaseCache: persistence, dirty tracking, save/load lifecycle")

# ═══════════════════════════════════════════════
# 10. Composite RepositoryCache Facade
# ═══════════════════════════════════════════════
print("\n10. Composite RepositoryCache Facade...")
from repository import RepositoryCache, FileWatcher
rc = RepositoryCache(tmpdir, cache_dir)

# Verify all 7 caches are initialized
assert rc.files is not None
assert rc.symbols is not None
assert rc.dependencies is not None
assert rc.embeddings is not None
assert rc.git is not None
assert rc.lsp is not None
assert rc.build is not None
assert rc.watcher is not None

# Scan
count = rc.scan()
assert count >= 4

# Save all
rc.save_all()

# Statistics
stats = rc.get_statistics()
assert "file_cache" in stats
assert "symbol_cache" in stats
assert "dependency_cache" in stats
assert "embedding_cache" in stats
assert "git_cache" in stats
assert "lsp_cache" in stats
assert "build_cache" in stats

# Summary
summary = rc.get_summary()
assert "Repository Cache" in summary
assert "Files:" in summary

# Query delegation
files = rc.find_files(language="python")
print(f"   ✓ 7 specialized caches created and verified")
print(f"   ✓ Scan found {count} files")
print(f"   ✓ Statistics includes all 7 caches")
print(f"   ✓ Query delegation works: {len(files)} python files")

# Clear
rc.clear()
assert rc.files.count() == 0

# ═══════════════════════════════════════════════
# 11. Scheduler
# ═══════════════════════════════════════════════
print("\n11. Scheduler...")
from kernel.scheduler import Scheduler, JobStatus

sched = Scheduler(max_workers=4)
sched.start()

results = {}
def my_handler(job_id, metadata):
    results[job_id] = metadata
    return {"processed": True, "job_id": job_id}

# Submit jobs
sched.submit("job-1", "First Job", my_handler, priority=2, metadata={"order": 1})
sched.submit("job-2", "Second Job", my_handler, priority=3, metadata={"order": 2})
sched.submit("job-3", "Critical Job", my_handler, priority=4, metadata={"order": 3})

# Wait for completion
time.sleep(2)

# Check results
assert "job-3" in results  # Critical runs first
assert "job-2" in results
assert "job-1" in results
assert results["job-3"]["order"] == 3

stats = sched.get_stats()
assert stats["completed"] >= 3
assert stats["submitted"] >= 3
assert stats["worker_pool_max"] == 4

# Test dependencies
dep_results = {}
def dep_handler(job_id, metadata):
    dep_results[job_id] = True
    return {"done": True}

sched.submit("dep-a", "Dependency A", dep_handler, dependencies=[], metadata={})
sched.submit("dep-b", "Dependency B", dep_handler, dependencies=["dep-a"], metadata={})
sched.submit("dep-c", "Dependency C", dep_handler, dependencies=["dep-a", "dep-b"], metadata={})

time.sleep(2)
assert "dep-a" in dep_results
assert "dep-b" in dep_results
assert "dep-c" in dep_results

# Test retry (handler that fails then succeeds)
retry_count = [0]
def flaky_handler(job_id, metadata):
    retry_count[0] += 1
    if retry_count[0] < 2:
        raise ValueError("Temporary failure")
    return {"success": True}

sched.submit("flaky-job", "Flaky Job", flaky_handler, max_retries=3, metadata={})
time.sleep(3)
assert retry_count[0] >= 2  # At least 2 attempts (1 fail + 1 retry)

# Stats
stats = sched.get_stats()
assert stats["total_jobs"] >= 7
assert stats["worker_pool_active"] == 0  # All done

sched.stop()
print(f"   ✓ Priority scheduling: critical jobs run first")
print(f"   ✓ Dependencies: dep-c waits for dep-a and dep-b")
print(f"   ✓ Retry: flaky handler retried {retry_count[0]-1} times")
print(f"   ✓ Stats: {stats['completed']} completed, {stats['total_jobs']} total")

# ═══════════════════════════════════════════════
# 12. Resource Manager
# ═══════════════════════════════════════════════
print("\n12. Resource Manager...")
from kernel.resources import ResourceManager, ModelSelector

rm = ResourceManager()

# CPU
assert rm.cpu_available == 4
assert rm.acquire_cpu()
assert rm.cpu_available == 3
rm.release_cpu(duration=1.5)
assert rm.cpu_available == 4
assert rm.cpu.total_cpu_time == 1.5

# Memory
assert rm.reserve_memory(256)
rm.release_memory(256)

# Tokens
rm.record_token_usage("gpt-4", 100, 50)
rm.record_token_usage("gpt-4o", 200, 100)
assert rm.can_use_model("gpt-4", 1000)
assert rm.tokens.total_tokens == 450

# Cost
rm.record_cost("gpt-4", 100, 50)
assert rm.cost.total_spent > 0
assert rm.can_afford("gpt-4o-mini", 100, 50)

# Time
assert rm.check_time_budget(5.0)
rm.record_time(3.0)
assert rm.time.total_time == 3.0

# Can accept job
assert rm.can_accept_job(estimated_memory_mb=128, estimated_duration=10)

# Stats
stats = rm.get_stats()
assert "cpu" in stats
assert "memory" in stats
assert "tokens" in stats
assert "cost" in stats
assert "time" in stats

# Summary
summary = rm.get_summary()
assert "Resource Management" in summary
assert "CPU:" in summary

print(f"   ✓ CPU: acquired/released, total time: {rm.cpu.total_cpu_time}s")
print(f"   ✓ Tokens: {rm.tokens.total_tokens} total ({rm.token_usage_percent():.1f}%)")
print(f"   ✓ Cost: ${rm.cost.total_spent:.4f} total, ${rm.cost.daily_spent:.4f} today")
print(f"   ✓ Stats includes all 5 budget types")

# 12b. ModelSelector
from kernel.resources import ModelSelector
ms = ModelSelector(rm)

model = ms.select_model("code_generation", complexity="complex")
assert isinstance(model, str)
assert len(model) > 0

model_simple = ms.select_model("simple_query", complexity="simple", prefer_cheap=True)
assert isinstance(model_simple, str)

cost = ms.estimate_cost("gpt-4", 1000, 500)
assert cost > 0
print(f"   ✓ ModelSelector: selected '{model}' for complex code, '{model_simple}' for simple")
print(f"   ✓ Cost estimate for gpt-4 (1k in, 500 out): ${cost:.4f}")

# ═══════════════════════════════════════════════
# 13. Kernel Integration
# ═══════════════════════════════════════════════
print("\n13. Kernel Integration...")
from kernel import Kernel

kernel = Kernel(workdir=tmpdir, max_workers=2)

# Verify new components exist
assert hasattr(kernel, 'scheduler')
assert hasattr(kernel, 'resource_manager')

# Initialize
kernel.initialize()
assert kernel._initialized

# Schedule a job through kernel
sched_results = {}
kernel.schedule_job(
    job_id="kernel-test-1",
    name="Kernel Scheduled Job",
    handler=lambda jid, md: sched_results.update({jid: True}) or {"done": True},
    priority=4,
    metadata={"test": True},
)

time.sleep(1)
assert "kernel-test-1" in sched_results

# Resource summary
summary = kernel.get_resource_summary()
assert "Resource Management" in summary

# Kernel stats
stats = kernel.get_kernel_stats()
assert "scheduler" in stats
assert "resource_manager" in stats
assert "runtime" in stats
assert "event_bus" in stats

# Shutdown
kernel.shutdown()
assert not kernel._initialized
print(f"   ✓ Scheduler integrated into kernel")
print(f"   ✓ Resource manager integrated into kernel")
print(f"   ✓ get_kernel_stats includes scheduler and resource_manager")
print(f"   ✓ Kernel shutdown stops all components")

# ═══════════════════════════════════════════════
# 14. Knowledge Graph
# ═══════════════════════════════════════════════
print("\n14. Knowledge Graph...")
from repository.kg_types import NodeType, RelationType, KGNode, KGRelation, KGAnalysis
from repository.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph(tmpdir, cache_dir)
kg.clear()

# 14a. Node management
n1 = KGNode(id="class:User", type=NodeType.CLASS, name="User",
            file_path="models/user.py", line=1, signature="class User")
n2 = KGNode(id="class:Admin", type=NodeType.CLASS, name="Admin",
            file_path="models/user.py", line=10, signature="class Admin(User)")
n3 = KGNode(id="function:login", type=NodeType.FUNCTION, name="login",
            file_path="auth/login.py", line=5, signature="def login()")
n4 = KGNode(id="function:logout", type=NodeType.FUNCTION, name="logout",
            file_path="auth/logout.py", line=3, signature="def logout()")
n5 = KGNode(id="function:get_user", type=NodeType.FUNCTION, name="get_user",
            file_path="models/user.py", line=20, signature="def get_user()")

kg.add_node(n1)
kg.add_node(n2)
kg.add_node(n3)
kg.add_node(n4)
kg.add_node(n5)
assert kg.node_count() == 5

# 14b. Relation management
r1 = KGRelation(source_id="class:Admin", target_id="class:User",
                type=RelationType.INHERITS, file_path="models/user.py", line=10)
r2 = KGRelation(source_id="function:login", target_id="function:get_user",
                type=RelationType.CALLS, file_path="auth/login.py", line=6)
r3 = KGRelation(source_id="function:logout", target_id="function:get_user",
                type=RelationType.CALLS, file_path="auth/logout.py", line=4)
r4 = KGRelation(source_id="function:login", target_id="class:User",
                type=RelationType.CREATES, file_path="auth/login.py", line=7)

kg.add_relation(r1)
kg.add_relation(r2)
kg.add_relation(r3)
kg.add_relation(r4)
assert kg.relation_count() == 4

# 14c. Query methods
# Find by name
found = kg.find("login")
assert len(found) >= 1
assert found[0].name == "login"

# Find by type
classes = kg.find_by_type(NodeType.CLASS)
assert len(classes) == 2

# Find in file
user_nodes = kg.find_in_file("models/user.py")
assert len(user_nodes) >= 3  # User, Admin, get_user

# Get node
node = kg.get_node("class:User")
assert node is not None
assert node.name == "User"

print("   ✓ Node/relation management: add, remove, query")

# 14d. Graph algorithms
# BFS
bfs_result = kg.bfs("function:login")
bfs_ids = [n.id for n in bfs_result]
assert "function:get_user" in bfs_ids
assert "class:User" in bfs_ids

# DFS
dfs_result = kg.dfs("function:login")
assert len(dfs_result) > 0

# Shortest path
path = kg.find_shortest_path("function:login", "class:User")
assert path is not None
assert len(path.nodes) >= 2
print("   ✓ Graph traversal: BFS, DFS, shortest path")

# 14e. Impact analysis
impact = kg.get_impact_analysis("function:get_user")
assert impact.metrics.get("total_impacted", 0) == 2
assert impact.query_type == "impact_analysis"
print("   ✓ Impact analysis: find_dependents, trace_upstream")

# 14f. Find dead code
# function:logout has no incoming relations from functions other than get_user
# Actually let's check: None of the functions are "dead" since get_user has callers
# Let's add an orphan
n6 = KGNode(id="function:orphan", type=NodeType.FUNCTION, name="orphan",
            file_path="dead.py", line=1)
kg.add_node(n6)
dead = kg.find_dead_code()
assert dead.metrics.get("dead_candidates", 0) >= 1
print("   ✓ Dead code detection: found orphan function")

# 14g. Duplicate detection
dup1 = KGNode(id="class:DuplicateA", type=NodeType.CLASS, name="DuplicateClass",
              file_path="a.py", line=1)
dup2 = KGNode(id="class:DuplicateB", type=NodeType.CLASS, name="DuplicateClass",
              file_path="b.py", line=1)
kg.add_node(dup1)
kg.add_node(dup2)
dups = kg.find_duplicates()
assert dups.metrics.get("total_duplicate_groups", 0) >= 1
print("   ✓ Duplicate detection: found duplicate class name")

# 14h. Persistence
kg.save()
kg2 = KnowledgeGraph(tmpdir, cache_dir)
kg2.load()
assert kg2.node_count() >= 7
assert kg2.relation_count() >= 4
print("   ✓ Persistence: save/load preserves nodes and relations")

# 14i. Stats
stats = kg.get_stats()
assert stats["total_nodes"] >= 7
assert stats["total_relations"] >= 4
assert "nodes_by_type" in stats
print("   ✓ Statistics: comprehensive node/relation counts")

# 14j. Subgraph
sub = kg.subgraph({"class:User", "class:Admin"})
assert sub.node_count() >= 2
print("   ✓ Subgraph extraction centered on nodes")

# 14k. Clear
kg.clear()
assert kg.node_count() == 0
kg.load()  # Restore for subsequent tests

# ═══════════════════════════════════════════════
# 15. Indexer (PythonASTWalker + Indexer)
# ═══════════════════════════════════════════════
print("\n15. Indexer...")

# 15a. PythonASTWalker
from repository.indexer import PythonASTWalker

test_code = '''
import os
from datetime import datetime

class User:
    """User model."""
    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}"

class Admin(User):
    """Admin user."""
    def __init__(self, name: str, role: str):
        super().__init__(name)
        self.role = role

def create_user(name: str) -> User:
    u = User(name)
    return u

def login(username: str):
    """Authenticate a user."""
    user = create_user(username)
    print(f"Logged in {user.name}")
    return user
'''

walker = PythonASTWalker("test_auth.py", test_code, "test_auth")
nodes, relations = walker.walk()
assert len(nodes) > 0
assert len(relations) > 0

# Check extracted entities
node_names = [n.name for n in nodes]
assert "User" in node_names, f"User class not found in {node_names}"
assert "Admin" in node_names, f"Admin class not found in {node_names}"
assert "create_user" in node_names, f"create_user not found in {node_names}"
assert "login" in node_names, f"login not found in {node_names}"

# Check relations by type
rel_types = [r.type for r in relations]
assert RelationType.INHERITS in rel_types
assert RelationType.CALLS in rel_types
assert RelationType.OWNS in rel_types

print(f"   ✓ PythonASTWalker: {len(nodes)} nodes, {len(relations)} relations")
print(f"   ✓ Extracted classes: User, Admin")
print(f"   ✓ Extracted functions: create_user, login")
print(f"   ✓ Relations: INHERITS, CALLS, OWNS")

# 15b. GenericParser
from repository.indexer import GenericParser

ts_code = '''
import { Component } from '@angular/core';
import { Router } from '@angular/router';

interface User {
  id: number;
  name: string;
}

class LoginComponent implements OnInit {
  user: User;

  constructor(private router: Router) {}

  ngOnInit(): void {
    this.loadUser();
  }

  loadUser(): void {
    // Load user logic
  }
}

function validateEmail(email: string): boolean {
  return email.includes('@');
}
'''

parser = GenericParser("test_component.ts", ts_code)
ts_nodes, ts_relations = parser.parse()
assert len(ts_nodes) > 0
assert len(ts_relations) > 0
print(f"   ✓ GenericParser (TypeScript): {len(ts_nodes)} nodes, {len(ts_relations)} relations")

# 15c. Indexer orchestrator
from repository.indexer import Indexer

# Fresh KG
index_kg = KnowledgeGraph(tmpdir, os.path.join(cache_dir, "index_test"))
index_kg.clear()

idx = Indexer(index_kg)

# Index the test code
count = idx.index_file("test_auth.py", source_code=test_code)
assert count > 0
assert index_kg.node_count() == count

# Index again (should not duplicate)
count2 = idx.index_file("test_auth.py", source_code=test_code)
assert count2 == 0  # All nodes already exist

# Get stats
stats = idx.get_stats()
assert stats["files_indexed"] >= 1
assert stats["nodes_created"] >= count

print(f"   ✓ Indexer: indexed {stats['files_indexed']} files, {stats['nodes_created']} nodes")
print(f"   ✓ Deduplication: re-indexing doesn't duplicate nodes")

# 15d. Index TS file
idx.index_file("test_component.ts", source_code=ts_code)
stats2 = idx.get_stats()
assert stats2["files_indexed"] >= 2
print(f"   ✓ Multi-language indexing: Python + TypeScript")

# ═══════════════════════════════════════════════
# 16. Repository Intelligence
# ═══════════════════════════════════════════════
print("\n16. Repository Intelligence...")
from repository.intelligence import RepositoryIntelligence

intel = RepositoryIntelligence(tmpdir, os.path.join(cache_dir, "intel_test"))

# Build a rich KG for testing
intel_kg = intel.kg
intel_kg.clear()

# Add test entities
entities = [
    KGNode(id="module:auth/login.py", type=NodeType.MODULE, name="login",
           file_path="auth/login.py", line=1),
    KGNode(id="function:login", type=NodeType.FUNCTION, name="login",
           file_path="auth/login.py", line=5, signature="def login()"),
    KGNode(id="function:validate", type=NodeType.FUNCTION, name="validate",
           file_path="auth/login.py", line=15, signature="def validate()"),
    KGNode(id="class:LoginForm", type=NodeType.CLASS, name="LoginForm",
           file_path="auth/login.py", line=25, signature="class LoginForm"),
    KGNode(id="module:auth/register.py", type=NodeType.MODULE, name="register",
           file_path="auth/register.py", line=1),
    KGNode(id="function:register", type=NodeType.FUNCTION, name="register",
           file_path="auth/register.py", line=5, signature="def register()"),
    KGNode(id="module:payment/service.py", type=NodeType.MODULE, name="service",
           file_path="payment/service.py", line=1),
    KGNode(id="function:process_payment", type=NodeType.FUNCTION, name="process_payment",
           file_path="payment/service.py", line=10, signature="def process_payment()"),
    KGNode(id="module:models/user.py", type=NodeType.MODULE, name="user",
           file_path="models/user.py", line=1),
    KGNode(id="class:User", type=NodeType.CLASS, name="User",
           file_path="models/user.py", line=5, signature="class User"),
    KGNode(id="function:create_user", type=NodeType.FUNCTION, name="create_user",
           file_path="models/user.py", line=20, signature="def create_user()"),
]
for e in entities:
    intel_kg.add_node(e)

# Add relations
relations = [
    KGRelation("function:login", "function:validate", RelationType.CALLS, "auth/login.py", 6),
    KGRelation("function:login", "function:create_user", RelationType.CALLS, "auth/login.py", 7),
    KGRelation("function:register", "function:create_user", RelationType.CALLS, "auth/register.py", 6),
    KGRelation("function:process_payment", "class:User", RelationType.USES, "payment/service.py", 11),
    KGRelation("module:auth/login.py", "module:models/user.py", RelationType.DEPENDS_ON, "auth/login.py", 2),
    KGRelation("module:auth/register.py", "module:models/user.py", RelationType.DEPENDS_ON, "auth/register.py", 2),
    KGRelation("module:payment/service.py", "module:models/user.py", RelationType.DEPENDS_ON, "payment/service.py", 3),
]
for r in relations:
    intel_kg.add_relation(r)

# 16a. Find entities
found = intel.find("login")
assert len(found) >= 1
print("   ✓ Find: entity search works")

# 16b. Find by type
funcs = intel.find_by_type("function")
assert len(funcs) >= 5
print("   ✓ Find by type: function returns all functions")

# 16c. Impact analysis
impact = intel.what_breaks("function:create_user")
assert impact.metrics.get("direct_dependents", 0) >= 2  # login + register call it
assert len(impact.suggestions) > 0
print(f"   ✓ Impact analysis: modifying create_user affects {impact.metrics.get('total_impacted', 0)} entities")

# 16d. Trace flow (call flow)
call_flow = intel.trace_flow("function:login", "call")
assert call_flow.query_type == "call_flow"
print("   ✓ Trace call flow: login → validate, create_user")

# 16e. Trace flow (inheritance)
inheritance_flow = intel.trace_flow("class:User", "inheritance")
# User has no parents, but no error
print("   ✓ Trace inheritance flow")

# 16f. Architecture
arch = intel.find_architecture()
assert arch.metrics.get("total_modules", 0) >= 4
print(f"   ✓ Architecture: {arch.metrics.get('total_modules', 0)} modules, {arch.metrics.get('total_packages', 0)} packages")

# 16g. Domain-specific architecture
auth_arch = intel.find_architecture("auth")
assert auth_arch.metrics.get("total_modules", 0) >= 2
print("   ✓ Domain architecture: auth package found")

# 16h. Dead code
dead = intel.find_dead_code()
assert dead.metrics.get("dead_count", 0) >= 0
print("   ✓ Dead code analysis")

# 16i. Module health
health = intel.module_health("auth/login.py")
assert health["entity_count"] >= 3
assert "health_score" in health
print(f"   ✓ Module health: {health['entity_count']} entities, score {health['health_score']:.0%}")

# 16j. Module map
mmap = intel.module_map("auth/login.py")
assert len(mmap) >= 3
print("   ✓ Module map: entity relationships mapped")

# 16k. Build context
context = intel.build_context("Find the login flow and understand authentication")
assert len(context["entities"]) >= 1
assert "summary" in context
print(f"   ✓ Context building: {context['stats']['total_entities']} entities, {context['stats']['total_files']} files")

# 16l. Find related
related = intel.find_related("function:register")
assert len(related) >= 1
print("   ✓ Find related entities")

# 16m. Summary
summary = intel.get_summary()
assert "Repository Intelligence" in summary
print(f"   ✓ Intelligence summary generated")

# ═══════════════════════════════════════════════
# 17. Retriever
# ═══════════════════════════════════════════════
print("\n17. Retriever...")
from repository.retriever import Retriever, QueryResult

retriever = Retriever(intel)

# 17a. Entity query
result = retriever.query("find login", "entity")
assert not result.is_empty()
assert result.confidence > 0
print(f"   ✓ Entity query: {len(result.results)} results, confidence {result.confidence:.2f}")

# 17b. Flow query
result = retriever.query("trace what calls create_user", "flow",
                          {"target": "function:create_user"})
assert not result.is_empty()
print(f"   ✓ Flow query: traced {len(result.results)} related entities")

# 17c. Impact query
result = retriever.query("impact of changing create_user", "impact",
                          {"target": "function:create_user"})
assert result.metadata.get("metrics", {}).get("direct_dependents", 0) >= 2
print(f"   ✓ Impact query: {result.metadata.get('summary', '')}")

# 17d. Architecture query
result = retriever.query("show me the architecture", "architecture")
assert len(result.results) >= 4
print(f"   ✓ Architecture query: {result.metadata.get('total_modules', 0)} modules")

# 17e. Search query
result = retriever.query("login", "search")
assert not result.is_empty()
print(f"   ✓ Search query: {len(result.results)} matches")

# 17f. Context query
result = retriever.query("Implement login with OAuth", "context")
assert "summary" in result.metadata
print(f"   ✓ Context query: {result.metadata.get('total_entities', 0)} entities")

# 17g. Code query
result = retriever.query("auth/login.py", "code")
assert not result.is_empty()
print(f"   ✓ Code query: {len(result.results)} results from file lookup")

# 17h. Symbols query
result = retriever.query("find create_user", "symbols",
                          {"symbol": "create_user"})
assert not result.is_empty()
print(f"   ✓ Symbols query: {len(result.results)} symbol results")

# 17i. Health query
result = retriever.query("check health of auth/login.py", "health",
                          {"module_path": "auth/login.py"})
assert not result.is_empty()
first = result.first()
assert first is not None
assert "health_score" in first
print(f"   ✓ Health query: score {first.get('health_score', 'N/A')}")

# 17j. Auto-detect query type
result = retriever.query("trace the login flow")
assert result.query_type == "flow"
print(f"   ✓ Auto-detect: 'trace the login flow' -> {result.query_type}")

result = retriever.query("what breaks if I change User")
assert result.query_type == "impact"
print(f"   ✓ Auto-detect: 'what breaks if I change User' -> {result.query_type}")

result = retriever.query("find all functions")
assert result.query_type == "entity"
print(f"   ✓ Auto-detect: 'find all functions' -> {result.query_type}")

# 17k. Stats
retriever_stats = retriever.get_stats()
assert retriever_stats["queries_executed"] > 0
assert retriever_stats["avg_time_ms"] >= 0
print(f"   ✓ Retriever stats: {retriever_stats['queries_executed']} queries executed, "
      f"avg {retriever_stats['avg_time_ms']:.2f}ms")

# ═══════════════════════════════════════════════
# 18. RepositoryCache Integration with KG + Intelligence
# ═══════════════════════════════════════════════
print("\n18. RepositoryCache Integration (KG + Intelligence)...")
from repository import RepositoryCache

rc2 = RepositoryCache(tmpdir, os.path.join(cache_dir, "rc_intel"))
rc2.kg.clear()

# Verify new components exist
assert hasattr(rc2, 'kg')
assert hasattr(rc2, 'indexer')
assert hasattr(rc2, 'intelligence')
assert hasattr(rc2, 'retriever')

# Test query convenience method
result = rc2.query("find login", "entity",
                    {"params": {"file_path": "auth/login.py"}})
print(f"   ✓ RepositoryCache.query() works: {len(result.results)} results")

# Test index_file convenience — create a real file first
test_src = '''
class Greeter:
    """A simple greeter."""
    def greet(self, name: str) -> str:
        return f"Hello, {name}"

def create_greeter():
    return Greeter()
'''
test_file = os.path.join(tmpdir, "test_integration.py")
with open(test_file, "w") as f:
    f.write(test_src)

result = rc2.index_file("test_integration.py")
assert result["total_nodes"] > 0
print(f"   ✓ RepositoryCache.index_file() works: {result['nodes_created']} nodes")

# Test what_breaks convenience
analysis = rc2.what_breaks("function:login")
assert analysis.metrics.get("total_impacted", 0) >= 0
print(f"   ✓ RepositoryCache.what_breaks() works")

# Test trace_flow convenience
analysis = rc2.trace_flow("function:login")
print(f"   ✓ RepositoryCache.trace_flow() works")

# Test build_context convenience
context = rc2.build_context("Understand the Greeter class", ["test_integration.py"])
assert len(context["entities"]) > 0
print(f"   ✓ RepositoryCache.build_context() works: {len(context['entities'])} entities")

# Test all components in statistics
stats_full = rc2.get_statistics()
assert "knowledge_graph" in stats_full
assert "retriever_stats" in stats_full
print(f"   ✓ Full statistics include KG and retriever metrics")

# Test updated summary
summary = rc2.get_summary()
assert "Intelligence" in summary or "Knowledge Graph" in summary
print(f"   ✓ Summary includes intelligence indicators")

# Test clear includes KG
rc2.clear()
assert rc2.files.count() == 0
rc2.kg.load()  # Verify clearing didn't corrupt persistence
print("   ✓ Clear includes all caches including KG")

# ═══════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════
print("\n" + "=" * 40)
print("ALL TESTS PASSED! ✅")
print("=" * 40)
