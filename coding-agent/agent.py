#!/usr/bin/env python3
"""
CODING AGENT - The complete agent.
Brain (core AI) + Limbs (tools, memory, skills) working together.
Self-learning, multi-provider, memory system, goal-driven execution.
"""

import sys, json, time, os, hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from brain.core import Brain, BrainConfig
from brain.learn import LearningLoop
from brain.improve import SelfImprover
from brain.context_engine import ContextEngine
from brain.router import ModelRouter, classify_task, estimate_complexity
from brain.verifier import Verifier
from brain.personalities import PersonalityManager
from brain.code_intel import CodeIntel
from brain.enterprise_memory import EnterpriseMemory
from brain.world_model import WorldModel
from brain.arch_graph import ArchitectureGraph
from brain.reviewer import EngineeringReviewer
from brain.benchmark import BenchmarkTracker
from brain.refactor_detector import RefactoringDetector
from brain.execution_planner import ExecutionPlanner
from brain.parallel_agents import ParallelOrchestrator, AgentTask
from brain.sub_agents.runner import run_parallel, summarize_parallel_results
from limbs.tools.runner import Tools
from limbs.tools.patch import PatchEditor
from limbs.memory.google_store import GoogleMemory
from limbs.memory.context import Context
from limbs.skills.loader import SkillsLoader
from config import Config

# Kernel-based architecture
from kernel import Kernel, Job, JobPriority, JobState, EventBus, Event
from kernel import EVT_TASK_CREATED, EVT_JOB_FINISHED, EVT_JOB_FAILED
from workers import ContextWorker, PlannerWorker, ExecutorWorker, VerifierWorker, ReviewerWorker, RepositoryWorker


TOOL_DESCRIPTIONS = {
    "run_bash": "Execute a bash command",
    "run_python": "Execute Python code",
    "read_file": "Read a file",
    "write_file": "Write/create a file",
    "edit_file": "Edit a file (find and replace text)",
    "search_files": "Find files by glob pattern",
    "grep": "Search text in files",
    "tree": "Show directory structure",
    "web_search": "Search the web",
    "web_fetch": "Fetch a URL",
    "install_deps": "Install Python packages",
    "run_tests": "Run tests",
    "ask_user": "Ask the user a question",
    "analyze_file": "Analyze a source file",
    "find_file": "Find a file by name",
    "codebase_overview": "Overview of entire codebase",
    "find_references": "Find all references to a symbol",
    "find_symbol": "Find classes/functions matching name",
    "dependency_graph": "Show file dependency graph",
    "similar_files": "Find files similar to given file",
    "generate_image_prompt": "Create a detailed image generation prompt",
    "generate_story": "Write a creative story",
    "analyze_dataframe": "Execute pandas analysis",
    "run_ml_experiment": "Run ML training/evaluation",
    "visualize_data": "Create data visualization",
    "git_status": "Show git status (changed files)",
    "git_diff": "Show git diff for working tree",
    "git_log": "Show recent git commit history",
    "read_directory": "List files and folders in a directory",
    "file_info": "Get file metadata (size, lines, type)",
    "run_command": "Run an arbitrary shell command",
    # Level 2 tools
    "go_to_definition": "Find where a symbol is defined (LSP-like)",
    "find_references_intel": "Find all references to a symbol across codebase",
    "get_type_info": "Get type information for an expression",
    "get_diagnostics": "Run diagnostics/linting on a file",
    "hover_info": "Get type signature and docstring for a symbol",
    "search_symbol": "Search for all occurrences of a symbol with context",
    "build_call_graph": "Build a call graph for a file",
    "generate_patch": "Generate a unified diff between current and new content",
    "apply_patch": "Apply a unified diff patch with backup and rollback",
    "preview_patch": "Preview what a patch would do (dry run)",
    "verify_changes": "Run full verification pipeline (build, test, lint, security)",
    "verify_syntax": "Check syntax of modified files",
    "verify_imports": "Check that imports resolve correctly",
    "router_info": "Show which model would be selected for a task",
    "personality_list": "List all available agent personalities",
    "personality_select": "Select a specific personality for the current task",
    # Level 3: AI Software Engineer tools
    "world_model_show": "Show the World Model (architecture, tech debt, TODOs, bugs)",
    "world_model_add_debt": "Record technical debt",
    "world_model_add_todo": "Add a TODO item",
    "world_model_add_bug": "Track a known bug",
    "arch_graph_show": "Show the Architecture Graph (concept-based understanding)",
    "arch_graph_impact": "Show what's impacted by changing a concept",
    "review_file": "Comprehensive code review (security, perf, style, docs)",
    "review_diff": "Review a git diff for issues",
    "benchmark_show": "Show performance benchmarks and success metrics",
    "refactor_scan": "Scan codebase for refactoring opportunities",
    "enterprise_search": "Search enterprise memory for relevant knowledge",
    "enterprise_store": "Store knowledge in enterprise memory",
    "plan_task": "Generate a structured execution plan with phases and risks",
    "parallel_execute": "Execute agents in parallel for a task",
    # Kernel tools
    "kernel_status": "Show kernel status, registered workers, and active jobs",
}


class Agent:
    def __init__(self, config: dict = None):
        cfg = config or {}
        self.config = Config()
        bc = BrainConfig(
            provider=cfg.get("provider", self.config.provider),
            model=cfg.get("model", self.config.model),
            api_key=cfg.get("api_key", self.config.api_key),
            temperature=cfg.get("temperature", self.config.temperature),
        )
        self.brain = Brain(bc)
        self.memory = GoogleMemory()
        self.ctx = Context()
        workdir = cfg.get("workdir", self.config.workdir)
        
        # Core subsystems
        self.tools = Tools(workdir, brain=self.brain)
        self.learn = LearningLoop(self.brain)
        self.skills = SkillsLoader()
        self.improver = SelfImprover()
        self.context_engine = ContextEngine(workdir)
        
        # Level 2: Professional AI subsystems
        self.code_intel = CodeIntel(workdir)
        self.model_router = ModelRouter()
        self.verifier = Verifier(workdir)
        self.patch_editor = PatchEditor(workdir)
        self.personalities = PersonalityManager()
        
        # Level 3: AI Software Engineer subsystems
        self.enterprise_memory = EnterpriseMemory(workdir)
        self.world_model = WorldModel(workdir)
        self.arch_graph = ArchitectureGraph(workdir)
        self.reviewer = EngineeringReviewer(workdir)
        self.benchmark = BenchmarkTracker()
        self.refactor_detector = RefactoringDetector(workdir)
        self.exec_planner = ExecutionPlanner()
        self.parallel_orchestrator = ParallelOrchestrator(max_workers=4)

        # ── Kernel Architecture (event-driven orchestrator) ──
        self.kernel = Kernel(workdir, max_workers=4)
        self._register_kernel_workers()
        self.kernel.initialize()
        self.use_kernel = cfg.get("use_kernel", True)  # Toggle kernel mode
        
        self._build_tool_map()
        self.errors_this_run = []
        self.project_memory: dict = {}
        self._load_project_memory()
        
        print(f"  [Agent] Initialized: {len(self.tool_map)} tools | "
              f"{len(self.personalities.list_personalities())} personalities | "
              f"Kernel={'on' if self.use_kernel else 'off'}")

    def _register_kernel_workers(self):
        """Register all subsystem workers with the kernel."""
        # Context worker
        ctx_worker = ContextWorker(self.kernel.event_bus, self.kernel.artifacts, self.context_engine)
        self.kernel.register_worker(ctx_worker)
        
        # Planner worker
        plan_worker = PlannerWorker(self.kernel.event_bus, self.kernel.artifacts, self.exec_planner)
        self.kernel.register_worker(plan_worker)
        
        # Executor worker
        exec_worker = ExecutorWorker(self.kernel.event_bus, self.kernel.artifacts, self.tools, self.code_intel, self.patch_editor)
        self.kernel.register_worker(exec_worker)
        
        # Verifier worker
        ver_worker = VerifierWorker(self.kernel.event_bus, self.kernel.artifacts, self.verifier)
        self.kernel.register_worker(ver_worker)
        
        # Reviewer worker
        rev_worker = ReviewerWorker(self.kernel.event_bus, self.kernel.artifacts, self.reviewer)
        self.kernel.register_worker(rev_worker)

        # Repository worker (cache)
        repo_worker = RepositoryWorker(
            self.kernel.event_bus, self.kernel.artifacts,
            repo_root=self.workdir
        )
        self.kernel.register_worker(repo_worker)

    def _build_tool_map(self):
        self.tool_map = {}
        # Add tools from Tools instance
        for name in dir(self.tools):
            if not name.startswith("_"):
                fn = getattr(self.tools, name)
                if callable(fn):
                    self.tool_map[name] = fn
        # Add Agent-level tools (code intel, patch, verify, router, personality)
        for name in ["go_to_definition", "find_references_intel", "get_type_info",
                      "get_diagnostics", "hover_info", "search_symbol",
                      "build_call_graph", "generate_patch", "apply_patch",
                      "preview_patch", "verify_changes", "verify_syntax",
                      "verify_imports", "router_info", "personality_list",
                      "personality_select",
                      # Level 3: AI Software Engineer tools
                      "world_model_show", "world_model_add_debt",
                      "world_model_add_todo", "world_model_add_bug",
                      "arch_graph_show", "arch_graph_impact",
                      "review_file", "review_diff",
                      "benchmark_show", "refactor_scan",
                      "enterprise_search", "enterprise_store",
                      "plan_task", "parallel_execute",
                      # Kernel tools
                      "kernel_status", "process_with_kernel"]:
            fn = getattr(self, name, None)
            if fn and callable(fn):
                self.tool_map[name] = fn

    def _load_project_memory(self):
        proj_path = Path(self.tools.workdir).resolve()
        proj_hash = hashlib.md5(str(proj_path).encode()).hexdigest()[:8]
        mem_file = Path.home() / ".coding-agent" / "projects" / f"{proj_hash}.json"
        if mem_file.exists():
            try:
                self.project_memory = json.loads(mem_file.read_text())
            except:
                self.project_memory = {}
        self._project_mem_file = mem_file

    def _save_project_memory(self, task: str = "", result: str = ""):
        self._project_mem_file.parent.mkdir(parents=True, exist_ok=True)
        if task and result:
            history = self.project_memory.get("history", [])
            history.append({"task": task[:80], "result": result[:200], "time": time.time()})
            self.project_memory["history"] = history[-5:]  # Keep last 5
            self.project_memory["last_task"] = task[:80]
            self.project_memory["last_result"] = result[:200]
        self._project_mem_file.write_text(json.dumps(self.project_memory, indent=2))

    def _clarify_task(self, task: str) -> str:
        VAGUE_PATTERNS = ["help me", "do something", "fix it", "make it work", "improve", "thing", "stuff"]
        task_lower = task.lower()
        is_vague = any(p in task_lower for p in VAGUE_PATTERNS) or len(task) < 20
        if not is_vague:
            return task
        print(f"\n[!] Task seems unclear: '{task[:60]}'")
        try:
            print("[?] What specifically should I do? ", end="", flush=True)
            answer = sys.stdin.readline().strip()
            if answer and answer != "continue":
                return f"{task}\n\nClarification: {answer}"
        except:
            pass
        return task

    def run(self, task: str, max_iter: int = 10):
        """Run the agent with the given task.
        
        If kernel mode is enabled, delegates to the event-driven kernel.
        Otherwise, uses the classic 6-phase pipeline.
        """
        if self.use_kernel:
            return self._run_via_kernel(task)
        
        print(f"\n{'='*60}")
        print(f"BRAIN: {self.brain.cfg.provider}/{self.brain.cfg.model}")
        print(f"TASK: {task}")
        mem_stats = self.memory.stats()
        skills_count = len(self.skills.get_all())
        print(f"MEMORY: {mem_stats['total']} entries | SKILLS: {skills_count}")
        print(f"TOOLS: {len(self.tool_map)} | KERNEL: {'on' if self.use_kernel else 'off'}")
        print(f"{'='*60}")

        self.ctx.add("user", task)
        start_time = time.time()
        task = self._clarify_task(task)

        # ── Phase 1: Load previous context ──
        session_knowledge = self.improver.compact_knowledge()
        project_ctx = self.project_memory.get("context", "")
        if session_knowledge:
            print(f"  [Session knowledge loaded]")
        if project_ctx:
            print(f"  [Project memory: {len(project_ctx)}b]")

        # ── Phase 2: Context Engine (NO LLM) ──
        print(f"\n[Context] Scanning repository and building context...")
        context = self.context_engine.build_llm_context(task, max_files=8)
        task_analysis = self.context_engine.analyze_task(task)
        plan_structure = self.context_engine.generate_plan_structure(task, task_analysis)
        print(f"  [Context] Project: {len(context)} chars | "
              f"Plan: {len(plan_structure)} phases")
        print(f"  [Context] Task type: {task_analysis.get('task_type', 'general')} | "
              f"Keywords: {', '.join(task_analysis.get('keywords', [])[:8])}")

        # ── Phase 3: Deep Thinking (LLM) ──
        print(f"\n[Think] Analyzing task with context...")
        think_context = f"Repository Context:\n{context[:2000]}\n\n"
        think_context += f"Session: {session_knowledge}\n" if session_knowledge else ""
        think_context += f"Project Memory: {project_ctx[:500]}\n" if project_ctx else ""
        analysis = self.brain.deep_think(task, think_context)
        if analysis:
            print(f"  [Think] {analysis[:150]}...")

        # ── Phase 4: Execute-Retreflect Loop ──
        all_actions = []
        all_results = []
        all_errors = []
        consecutive_failures = 0
        prior_context = context[:5000]
        plan_desc = "; ".join(p.get("desc", "") for p in plan_structure)

        for i in range(1, max_iter + 1):
            progress = f"[{i}/{max_iter}]"
            print(f"\n{progress} {'─'*40}")

            # Build comprehensive context for this iteration
            mem = self.memory.context(task)
            skills_prompt = self.skills.get_prompt_for(task)

            tools_hint = f"Plan structure: {plan_desc}\n"
            if skills_prompt:
                tools_hint += skills_prompt + "\n"
            if session_knowledge:
                tools_hint += session_knowledge + "\n"
            if project_ctx:
                tools_hint += f"Project: {project_ctx[:200]}\n"

            # If stuck, adapt strategy
            if consecutive_failures >= 2:
                print(f"  [*] Adapting strategy after {consecutive_failures} failures...")
                failure_mode = self._analyze_failure(all_errors)
                task = f"{task}\n\nADAPT: Previous attempt ({failure_mode}) failed. Try a completely different approach."

            # Generate detailed plan using context
            rich_context = f"Repository context:\n{prior_context[:3000]}\n\nMemory:\n{mem}"
            plan = self.brain.plan(task, rich_context, tools_hint,
                                   workdir=self.tools.workdir)
            if not plan:
                print("  [!] No plan generated.")
                break

            print(f"  Plan: {len(plan)} step(s)")

            # Execute steps in parallel
            parallel_results = list(run_parallel(plan, self.tools.workdir, brain=self.brain))
            summary = summarize_parallel_results(parallel_results)

            step_errors = summary["failed"]
            for pr in parallel_results:
                tool_name = pr.get("tool", "")
                desc = pr.get("desc", "")[:60]
                result = pr.get("result", {})
                ok = result.get("ok", False)
                data = result.get("data", "")
                err = result.get("error", "")
                step_time = pr.get("time", 0)

                all_actions.append({"tool": tool_name, "desc": desc})
                all_results.append(str(data)[:300])

                status = "✓" if ok else "x"
                if ok:
                    print(f"  [{status}] {desc} ({len(data)}b, {step_time:.0f}s)")
                    if data and len(data) < 200:
                        print(f"    -> {data[:120]}")
                else:
                    print(f"  [{status}] {desc}: {err[:80]}")
                    all_errors.append(f"{tool_name}: {err[:100]}")

                self.ctx.add("assistant", f"Step: {desc}\nResult: {str(result)[:300]}")

            elapsed = time.time() - start_time
            print(f"\n  {progress} {elapsed:.0f}s | {step_errors} error(s) | "
                  f"{summary['successful']}/{summary['total_steps']} ok")

            # ── Phase 5: Reflect ──
            if step_errors > 0 and i < max_iter:
                consecutive_failures += 1
                self.learn.after_task(task, all_actions, all_results, all_errors)

                # Build diagnosis from errors
                err_summary = self._summarize_errors(all_errors)
                failure_mode = self._analyze_failure(all_errors)

                # Update task with error context for retry
                task = (f"FIX ERRORS: {task[:80]}\n"
                        f"Errors: {err_summary}\n"
                        f"Mode: {failure_mode}\n"
                        f"Attempt: {consecutive_failures}")
                all_errors = []
                continue

            # ── Phase 6: Success — Learn ──
            consecutive_failures = 0
            self.learn.after_task(task, all_actions, all_results, all_errors)

            # Extract compact results for memory
            compact_results = []
            for r in all_results:
                if not r:
                    continue
                if len(r) < 200:
                    compact_results.append(r.strip()[:80])
                elif "class " in r[:300] or "def " in r[:300]:
                    lines = [l.strip() for l in r.split('\n')
                             if l.strip() and (' class ' in l or ' def ' in l)][:2]
                    if lines:
                        compact_results.append("; ".join(l[:60] for l in lines))
                elif len(r) < 500:
                    compact_results.append(r.strip()[:80])
            result_summary = (" | ".join(compact_results[:3])
                              if compact_results else f"Completed ({len(all_actions)} steps)")
            self._save_project_memory(task=task, result=result_summary)

            total_time = time.time() - start_time
            success = step_errors == 0
            self.improver.log_task(task, len(all_actions), len(all_errors),
                                   total_time, success, result=result_summary)

            print(f"\n{'='*60}")
            print(f"✓ COMPLETE ({len(all_actions)} steps, {total_time:.0f}s)")
            print(f"MEMORY: {self.memory.stats()['total']} | "
                  f"SKILLS: {len(self.skills.get_all())}")
            if success:
                print(f"Session: {self.improver.summarize_session()}")
            print(f"{'='*60}")
            return {"actions": len(all_actions), "errors": len(all_errors),
                    "time": total_time, "success": success}

        total_time = time.time() - start_time
        self.improver.log_task(task, len(all_actions), len(all_errors),
                               total_time, False)
        print(f"\n! Max iterations ({max_iter})")
        return {"actions": len(all_actions), "errors": len(all_errors),
                "time": total_time, "success": False}

    # ── Kernel-Based Execution ──

    def _run_via_kernel(self, task: str) -> dict:
        """Execute a task using the event-driven kernel."""
        print(f"\n{'='*60}")
        print(f"KERNEL MODE — Event-driven execution")
        print(f"TASK: {task}")
        print(f"WORKERS: {self.kernel.list_workers()}")
        print(f"{'='*60}")

        start_time = time.time()
        task = self._clarify_task(task)

        # Submit to kernel
        job_id = self.kernel.process_task_async(task)

        # Poll for completion
        result = self.kernel._wait_for_job(job_id)

        total_time = time.time() - start_time
        status = result.get("status", "unknown")

        print(f"\n{'='*60}")
        if status == "completed":
            print(f"✓ KERNEL COMPLETE ({total_time:.0f}s)")
            print(f"  Steps: {len(result.get('steps', []))}")
            step_artifacts = result.get("step_artifacts", [])
            for s in step_artifacts:
                print(f"  Artifact: {s}")
            print(f"  Metrics: {result.get('metrics', {})}")
        else:
            print(f"✗ KERNEL FAILED ({total_time:.0f}s)")
            print(f"  Status: {status}")
            if result.get("error"):
                print(f"  Error: {result['error']}")
        print(f"{'='*60}")

        return {
            "status": status,
            "duration": total_time,
            "job_id": job_id,
            "result": result,
        }

    def process_with_kernel(self, task: str, context: dict = None,
                             priority: str = "normal") -> dict:
        """Public method: process a task through the kernel.
        
        This creates a Job, submits it to the kernel runtime,
        and returns the result with all artifacts.
        """
        # Map priority string to enum
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "critical": JobPriority.CRITICAL,
        }
        job_priority = priority_map.get(priority.lower(), JobPriority.NORMAL)

        # Create and submit job
        job = Job(name=task[:80], description=task, priority=job_priority)
        job.source = "agent.process_with_kernel"
        job.context["task"] = task
        if context:
            job.context.update(context)

        # Add standard pipeline steps
        job.add_step("Discover Context", "context",
                     params={"task": task, "workdir": self.tools.workdir})
        job.add_step("Plan", "planner", params={"task": task})
        job.add_step("Execute", "executor", params={"task": task})
        job.add_step("Verify", "verifier", params={})

        # Submit
        job_id = self.kernel.runtime.submit(job)
        self.kernel._job_history.append(job)

        # Wait for completion
        result = self.kernel._wait_for_job(job_id)

        # Log to benchmark
        self.benchmark.log_task_complete(
            task, "kernel_job",
            success=result.get("status") == "completed",
            time_secs=result.get("duration", 0),
            steps=len(result.get("steps", [])),
            errors=1 if result.get("status") != "completed" else 0,
            tools_used=[],
            model="kernel",
            tokens=0,
        )

        return result

    # ── Kernel Status Tool ──

    def kernel_status(self) -> dict:
        """Show kernel status, workers, and active jobs."""
        try:
            snapshot = self.kernel.get_snapshot()
            lines = [
                f"Kernel: {'initialized' if self.kernel._initialized else 'stopped'}",
                f"Workers: {', '.join(self.kernel.list_workers()) or 'none'}",
                f"Active jobs: {len(snapshot.get('active_jobs', []))}",
                f"Queued jobs: {snapshot.get('queued_jobs', 0)}",
                f"Events published: {snapshot.get('kernel_stats', {}).get('event_bus', {}).get('published', 0)}",
                f"Jobs completed: {snapshot.get('kernel_stats', {}).get('kernel', {}).get('jobs_completed', 0)}",
                f"Jobs failed: {snapshot.get('kernel_stats', {}).get('kernel', {}).get('jobs_failed', 0)}",
            ]
            if snapshot.get("active_jobs"):
                lines.append("\nActive jobs:")
                for j in snapshot["active_jobs"]:
                    lines.append(f"  [{j['status']}] {j['name'][:40]} ({j['progress']:.0%})")
            return {"ok": True, "data": "\n".join(lines), "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def _call_tool(self, fn, tool_name: str, args_raw) -> dict:
        ARG_ALIASES = {
            "command":"cmd", "filePath":"path", "filename":"path",
            "file_pattern":"include", "search":"text", "dir":"workdir",
            "package":"packages", "packages":"packages",
        }
        if isinstance(args_raw, str):
            try:
                args_raw = json.loads(args_raw)
            except:
                return fn(args_raw)

        import inspect
        sig = inspect.signature(fn)
        norm = {}
        for k, v in args_raw.items():
            nk = ARG_ALIASES.get(k, k)
            if nk in sig.parameters:
                param = sig.parameters[nk]
                if param.annotation is int and isinstance(v, str):
                    try: v = int(v)
                    except: pass
            norm[nk] = v
        filtered = {k: v for k, v in norm.items() if k in sig.parameters}
        return fn(**filtered)

    def _summarize_errors(self, errors: list) -> str:
        unique = list(set(e[:100] for e in errors))
        return "; ".join(unique[:5])

    def _analyze_failure(self, errors: list) -> str:
        error_text = " ".join(errors).lower()
        if "not found" in error_text or "no such" in error_text:
            return "FILE_NOT_FOUND"
        if "timeout" in error_text:
            return "TIMEOUT"
        if "syntax" in error_text or "nameerror" in error_text or "typeerror" in error_text:
            return "CODE_ERROR"
        if "permission" in error_text or "denied" in error_text:
            return "PERMISSION"
        if "import" in error_text or "module" in error_text:
            return "MISSING_DEP"
        return "UNKNOWN"


    # ═══════════════════════════════════════════
    # Level 2 Tool Methods (auto-registered by _build_tool_map)
    # ═══════════════════════════════════════════

    # ── Code Intelligence Tools ──

    def go_to_definition(self, symbol: str, file_path: str) -> dict:
        """Find where a symbol is defined (LSP-like)."""
        try:
            results = self.code_intel.get_definition(symbol, file_path)
            if results:
                data = "\n".join(
                    f"{r['file']}:{r['line']} — {r.get('description', '')}"
                    for r in results[:5]
                )
                return {"ok": True, "data": data, "error": ""}
            return {"ok": True, "data": f"No definition found for '{symbol}'", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def find_references_intel(self, symbol: str, file_path: str = "") -> dict:
        """Find all references to a symbol across codebase."""
        try:
            results = self.code_intel.find_references(symbol, file_path)
            if results:
                data_lines = [f"{r['file']}:{r['line']}  {r.get('context', '')[:60]}"
                             for r in results[:20]]
                data = f"{len(results)} reference(s):\n" + "\n".join(data_lines)
                return {"ok": True, "data": data, "error": ""}
            return {"ok": True, "data": f"No references found for '{symbol}'", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def get_type_info(self, expression: str, file_path: str, line: int = 0) -> dict:
        """Get type information for an expression."""
        try:
            result = self.code_intel.get_type(expression, file_path, line)
            if result:
                return {"ok": True, "data": result[:500], "error": ""}
            return {"ok": True, "data": "No type information available", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def get_diagnostics(self, file_path: str) -> dict:
        """Run diagnostics/linting on a file."""
        try:
            results = self.code_intel.get_diagnostics(file_path)
            if results:
                data_lines = [
                    f"{r.get('severity','').upper()}:{r.get('line',0)}:{r.get('column',0)} {r.get('message','')[:100]}"
                    for r in results[:15]
                ]
                data = f"{len(results)} diagnostic(s):\n" + "\n".join(data_lines)
                return {"ok": True, "data": data, "error": ""}
            return {"ok": True, "data": "No diagnostics — file looks clean", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def hover_info(self, symbol: str, file_path: str) -> dict:
        """Get type signature and docstring for a symbol."""
        try:
            result = self.code_intel.hover_info(symbol, file_path)
            if result:
                return {"ok": True, "data": result[:500], "error": ""}
            return {"ok": True, "data": f"No info for '{symbol}'", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def search_symbol(self, name: str) -> dict:
        """Search for all occurrences of a symbol with context."""
        try:
            results = self.code_intel.search_symbol(name)
            if results:
                data_lines = []
                for r in results[:15]:
                    ctx = r.get('context', '')[:80].replace('\n', ' | ')
                    data_lines.append(f"{r['file']}:{r['line']}  {ctx}")
                data = f"{len(results)} occurrence(s):\n" + "\n".join(data_lines)
                return {"ok": True, "data": data, "error": ""}
            return {"ok": True, "data": f"No occurrences of '{name}' found", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def build_call_graph(self, file_path: str) -> dict:
        """Build a call graph for a file: who calls what."""
        try:
            graph = self.code_intel.build_call_graph(file_path)
            lines = []
            for func_name, info in graph.items():
                calls = ", ".join(str(l) for l in info.get("calls", []))
                called_by = ", ".join(info.get("called_by", []))
                if calls:
                    lines.append(f"{func_name} ({info['type']}) → calls at lines: {calls}")
                if called_by:
                    lines.append(f"{func_name} ← called by: {called_by}")
            if lines:
                return {"ok": True, "data": "\n".join(lines), "error": ""}
            return {"ok": True, "data": "No call graph data", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Patch Editing Tools ──

    def generate_patch(self, file_path: str, new_content: str) -> dict:
        """Generate a unified diff between current and new content."""
        try:
            patch = self.patch_editor.generate_patch(file_path, new_content)
            if patch.strip():
                return {"ok": True, "data": patch[:3000], "error": ""}
            return {"ok": True, "data": "No changes (files are identical)", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def apply_patch(self, file_path: str, patch: str) -> dict:
        """Apply a unified diff patch with backup and rollback."""
        try:
            result = self.patch_editor.apply_patch(file_path, patch)
            return result
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def preview_patch(self, file_path: str, patch: str) -> dict:
        """Preview what a patch would do (dry run)."""
        try:
            result = self.patch_editor.preview_patch(file_path, patch)
            return {"ok": True, "data": result[:2000], "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Verification Tools ──

    def verify_changes(self, files: str = "") -> dict:
        """Run full verification pipeline (build, test, lint, security)."""
        file_list = [f.strip() for f in files.split(",")] if files else None
        try:
            result = self.verifier.verify(file_list, run_tests=True)
            checks = result.get("checks", {})
            lines = []
            all_pass = True
            for name, check in checks.items():
                ok = check.get("ok", False)
                details = check.get("details", "")
                lines.append(f"  {'✓' if ok else '✗'} {name}: {details}")
                if not ok:
                    all_pass = False
                    for err in check.get("errors", [])[:2]:
                        lines.append(f"    - {err.get('message', '')[:100]}")
            data = "\n".join(lines)
            return {"ok": all_pass, "data": data, "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def verify_syntax(self, files: str = "") -> dict:
        """Check syntax of modified files."""
        file_list = [f.strip() for f in files.split(",")] if files else None
        try:
            result = self.verifier.verify_syntax(file_list)
            errors = result.get("errors", [])
            if errors:
                data = "\n".join(f"{e.get('file','')}:{e.get('line',0)} {e.get('message','')[:100]}"
                                for e in errors[:5])
                return {"ok": False, "data": data, "error": ""}
            return {"ok": True, "data": result.get("details", "Syntax OK"), "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def verify_imports(self, files: str = "") -> dict:
        """Check that imports resolve correctly."""
        file_list = [f.strip() for f in files.split(",")] if files else None
        if not file_list:
            return {"ok": True, "data": "No files specified", "error": ""}
        try:
            result = self.verifier.verify_imports(file_list)
            errors = result.get("errors", [])
            if errors:
                data = "\n".join(e.get("message", "")[:100] for e in errors[:5])
                return {"ok": False, "data": data, "error": ""}
            return {"ok": True, "data": result.get("details", "Imports OK"), "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Router & Personality Tools ──

    def router_info(self, task: str = "") -> dict:
        """Show which model would be selected for a task."""
        try:
            if not task:
                data = self.model_router.get_route_summary()
                return {"ok": True, "data": data or "No routing decisions yet", "error": ""}
            category, confidence = classify_task(task)
            complexity = estimate_complexity(task)
            model = self.model_router.route(task)
            data = (
                f"Task category: {category} (confidence: {confidence:.2f})\n"
                f"Complexity: {complexity:.2f}\n"
                f"Selected: {model.provider}/{model.name}\n"
                f"Quality: {model.quality:.2f} | Speed: {model.speed:.2f} | Cost: {model.cost:.2f}"
            )
            return {"ok": True, "data": data, "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def personality_list(self) -> dict:
        """List all available agent personalities."""
        try:
            personalities = self.personalities.list_personalities()
            lines = [f"  {p['name']:15s} — {p['role']} (strengths: {', '.join(p['strengths'])})"
                    for p in personalities]
            data = f"Available personalities:\n" + "\n".join(lines)
            data += f"\n\nCurrent: {self.personalities.current or 'not set'}"
            return {"ok": True, "data": data, "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def personality_select(self, name: str) -> dict:
        """Select a specific personality for the current task."""
        try:
            personality = self.personalities.get_personality(name)
            if not personality:
                available = [p['name'] for p in self.personalities.list_personalities()]
                return {"ok": False, "data": "", "error": f"Unknown personality: {name}. Available: {', '.join(available)}"}
            self.personalities.current = name
            return {"ok": True, "data": f"Selected personality: {name} ({personality.role})", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}


    # ═══════════════════════════════════════════
    # Level 3 Tool Methods (AI Software Engineer)
    # ═══════════════════════════════════════════

    # ── World Model Tools ──

    def world_model_show(self, section: str = "") -> dict:
        """Show the World Model (architecture, tech debt, TODOs, bugs)."""
        try:
            if section == "architecture":
                data = self.world_model.get_architecture_summary()
            elif section == "debt":
                data = self.world_model.get_debt_summary()
            elif section == "todos":
                data = self.world_model.get_todo_summary()
            elif section == "bugs":
                data = self.world_model.get_bug_summary()
            elif section == "decisions":
                data = self.world_model.get_decision_summary()
            elif section == "standards":
                data = self.world_model.get_standards_summary()
            elif section == "metrics":
                data = self.world_model.get_metrics_summary()
            elif section == "full":
                data = self.world_model.get_full_snapshot()
            else:
                data = self.world_model.get_full_snapshot()[:3000]
            return {"ok": True, "data": data[:5000], "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def world_model_add_debt(self, title: str, description: str,
                              severity: str = "medium", area: str = "general") -> dict:
        """Record technical debt."""
        try:
            self.world_model.add_debt(title, description, severity, area)
            return {"ok": True, "data": f"Debt recorded: {title}", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def world_model_add_todo(self, description: str, priority: str = "medium") -> dict:
        """Add a TODO item to the World Model."""
        try:
            self.world_model.add_todo(description, priority)
            return {"ok": True, "data": f"TODO added: {description[:60]}", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def world_model_add_bug(self, title: str, description: str,
                             severity: str = "medium", component: str = "") -> dict:
        """Track a known bug."""
        try:
            self.world_model.add_bug(title, description, severity, component)
            return {"ok": True, "data": f"Bug tracked: {title}", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Architecture Graph Tools ──

    def arch_graph_show(self, concept: str = "") -> dict:
        """Show the Architecture Graph (concept-based understanding)."""
        try:
            if concept:
                related = self.arch_graph.get_related(concept, max_depth=2)
                text = self.arch_graph.to_text()
                data = f"Related to '{concept}':\n"
                for r in related:
                    data += f"  {r.get('name', '?')} ({r.get('kind', '?')}) — {r.get('description', '')[:60]}\n"
                data += f"\nFull graph:\n{text}"
            else:
                data = self.arch_graph.to_text()
            return {"ok": True, "data": data[:5000], "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def arch_graph_impact(self, concept: str) -> dict:
        """Show what's impacted by changing a concept."""
        try:
            impacted = self.arch_graph.find_impacted(concept)
            if impacted:
                data = f"Changing '{concept}' may impact:\n"
                for item in impacted[:10]:
                    data += f"  - {item.get('name', '?')} ({item.get('kind', '?')})\n"
                return {"ok": True, "data": data, "error": ""}
            return {"ok": True, "data": f"No downstream impact found for '{concept}'", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Engineering Reviewer Tools ──

    def review_file(self, file_path: str) -> dict:
        """Comprehensive code review (security, perf, style, docs)."""
        try:
            content = Path(file_path).read_text() if Path(file_path).exists() else ""
            if not content:
                return {"ok": False, "data": "", "error": f"File not found: {file_path}"}
            result = self.reviewer.review_file(file_path, content)
            return {"ok": result.passed > 0, "data": result.to_text()[:5000], "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def review_diff(self, diff_text: str) -> dict:
        """Review a git diff for issues."""
        try:
            result = self.reviewer.review_diff(diff_text)
            return {"ok": result.passed > 0, "data": result.to_text()[:5000], "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Benchmark Tools ──

    def benchmark_show(self, metric: str = "", days: int = 7) -> dict:
        """Show performance benchmarks and success metrics."""
        try:
            session = self.benchmark.get_session_summary()
            report = self.benchmark.get_session_report()
            if metric:
                trend = self.benchmark.get_trend(metric, days)
                data = f"Trend for '{metric}' (last {days} days):\n"
                for point in trend[-10:]:
                    data += f"  {point.get('date', '?')}: {point.get('value', '?')}\n"
            else:
                data = report[:3000]
            return {"ok": True, "data": data, "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Refactoring Detector Tool ──

    def refactor_scan(self, full: bool = False) -> dict:
        """Scan codebase for refactoring opportunities."""
        try:
            issues = self.refactor_detector.scan(full=full)
            if issues:
                report = self.refactor_detector.get_report(issues)
                return {"ok": True, "data": report[:5000], "error": ""}
            return {"ok": True, "data": "No refactoring opportunities found — code looks clean", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Enterprise Memory Tools ──

    def enterprise_search(self, query: str) -> dict:
        """Search enterprise memory for relevant knowledge."""
        try:
            results = self.enterprise_memory.search(query, top_k=5)
            if results:
                lines = [f"  [{e.kind.upper()}] {e.title} ({e.created[:10]}) — {e.content[:120]}"
                        for e in results]
                data = f"Enterprise memory results for '{query}':\n" + "\n".join(lines)
                return {"ok": True, "data": data, "error": ""}
            return {"ok": True, "data": f"No results found for '{query}'", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def enterprise_store(self, kind: str, title: str, content: str,
                          tags: str = "") -> dict:
        """Store knowledge in enterprise memory."""
        try:
            tag_list = [t.strip() for t in tags.split(",")] if tags else []
            entry_id = self.enterprise_memory.store(kind, title, content, tag_list)
            return {"ok": True, "data": f"Stored as [{kind}] '{title}' (id: {entry_id})", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Execution Planner Tool ──

    def plan_task(self, task: str, task_type: str = "general") -> dict:
        """Generate a structured execution plan with phases and risks."""
        try:
            phases = self.exec_planner.plan(task, task_type)
            data = self.exec_planner.to_text(phases)
            return {"ok": True, "data": data[:5000], "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    # ── Parallel Agent Orchestration Tool ──

    def parallel_execute(self, task: str) -> dict:
        """Execute agents in parallel for a task."""
        try:
            tasks = self.parallel_orchestrator.create_plan(task)
            results = self.parallel_orchestrator.dispatch(tasks)
            merged = self.parallel_orchestrator.merge_results(results, task)
            output = self.parallel_orchestrator.format_output(merged)
            return {"ok": True, "data": output[:5000], "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}


def main():
    import argparse
    p = argparse.ArgumentParser(description="Coding Agent - AI-powered development assistant")
    p.add_argument("--task", required=True, help="Task description")
    p.add_argument("--dir", default="", help="Working directory")
    p.add_argument("--provider", default="", help="LLM provider (opencode, openai, anthropic, etc)")
    p.add_argument("--model", default="", help="Model name")
    p.add_argument("--iter", type=int, default=10, help="Max iterations")
    args = p.parse_args()

    cfg = {}
    if args.provider: cfg["provider"] = args.provider
    if args.model: cfg["model"] = args.model
    if args.dir: cfg["workdir"] = args.dir

    a = Agent(cfg)
    result = a.run(args.task, args.iter)
    if not result.get("success", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
