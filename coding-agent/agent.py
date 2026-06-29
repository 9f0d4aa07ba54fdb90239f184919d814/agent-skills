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
from brain.sub_agents.runner import run_parallel, summarize_parallel_results
from limbs.tools.runner import Tools
from limbs.memory.google_store import GoogleMemory
from limbs.memory.context import Context
from limbs.skills.loader import SkillsLoader
from config import Config


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
        self.tools = Tools(cfg.get("workdir", self.config.workdir), brain=self.brain)
        self.learn = LearningLoop(self.brain)
        self.skills = SkillsLoader()
        self.improver = SelfImprover()
        self._build_tool_map()
        self.errors_this_run = []
        self.project_memory: dict = {}
        self._load_project_memory()

    def _build_tool_map(self):
        self.tool_map = {}
        for name in dir(self.tools):
            if not name.startswith("_"):
                fn = getattr(self.tools, name)
                if callable(fn):
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
        print(f"\n{'='*60}")
        print(f"BRAIN: {self.brain.cfg.provider}/{self.brain.cfg.model}")
        print(f"TASK: {task}")
        mem_stats = self.memory.stats()
        skills_count = len(self.skills.get_all())
        print(f"MEMORY: {mem_stats['total']} entries | SKILLS: {skills_count}")
        print(f"TOOLS: {len(self.tool_map)}")
        print(f"{'='*60}\n")

        self.ctx.add("user", task)
        start_time = time.time()

        task = self._clarify_task(task)
        session_knowledge = self.improver.compact_knowledge()
        if session_knowledge:
            print(f"  [Session knowledge loaded]")

        # Load project-level memory
        project_ctx = self.project_memory.get("context", "")
        if project_ctx:
            print(f"  [Project memory: {len(project_ctx)}b]")

        # Phase 1: Deep thinking
        print(f"\n[Think] Analyzing task...")
        analysis = self.brain.deep_think(task, f"{session_knowledge}\n{project_ctx}".strip())
        if analysis:
            print(f"[Think] {analysis[:120]}...")
        all_actions = []
        all_results = []
        all_errors = []
        consecutive_failures = 0

        for i in range(1, max_iter + 1):
            progress = f"[{i}/{max_iter}]"
            print(f"\n{progress} ---")

            mem = self.memory.context(task)
            skills_prompt = self.skills.get_prompt_for(task)
            tools_hint = ""
            if skills_prompt:
                tools_hint = skills_prompt
            if session_knowledge:
                tools_hint += f"\n{session_knowledge}"
            if project_ctx:
                tools_hint += f"\nProject: {project_ctx[:200]}"

            if consecutive_failures >= 2:
                print(f"  Stuck, switching strategy...")
                task = f"{task}\n\nPrevious approach FAILED. Use DIFFERENT strategy."

            plan = self.brain.plan(task, mem, tools_hint, workdir=self.tools.workdir)
            if not plan:
                print("  No plan.")
                break

            print(f"  Plan: {len(plan)} step(s)")

            # Run steps in parallel batches using sub-agent runner
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
                        print(f"    -> {data}")
                else:
                    print(f"  [{status}] {desc}: {err[:80]}")
                    all_errors.append(f"{tool_name}: {err[:100]}")

                self.ctx.add("assistant", f"Step: {desc}\nResult: {str(result)[:300]}")

            elapsed = time.time() - start_time
            print(f"\n  {progress} {elapsed:.0f}s | {step_errors} error(s) | {summary['successful']}/{summary['total_steps']} ok")

            if step_errors > 0 and i < max_iter:
                consecutive_failures += 1
                self.learn.after_task(task, all_actions, all_results, all_errors)
                summary = self._summarize_errors(all_errors)
                failure_mode = self._analyze_failure(all_errors)
                task = f"FIX: {task[:100]}\nErrors: {summary}\nMode: {failure_mode}"
                all_errors = []
                continue

            consecutive_failures = 0
            self.learn.after_task(task, all_actions, all_results, all_errors)

            # Extract key findings for memory (prefer grep/CLI output, not full file reads)
            compact_results = []
            for r in all_results:
                if not r:
                    continue
                if len(r) < 200:
                    compact_results.append(r.strip()[:80])
                elif "class " in r[:300] or "def " in r[:300]:
                    lines = [l.strip() for l in r.split('\n') if l.strip() and (' class ' in l or ' def ' in l)][:2]
                    if lines:
                        compact_results.append("; ".join(l[:60] for l in lines))
                elif len(r) < 500:
                    compact_results.append(r.strip()[:80])
            result_summary = " | ".join(compact_results[:3]) if compact_results else f"Completed ({len(all_actions)} steps)"
            self._save_project_memory(task=task, result=result_summary)

            total_time = time.time() - start_time
            success = step_errors == 0
            self.improver.log_task(task, len(all_actions), len(all_errors), total_time, success, result=result_summary)

            print(f"\n{'='*60}")
            print(f"✓ COMPLETE ({len(all_actions)} steps, {total_time:.0f}s)")
            print(f"MEMORY: {self.memory.stats()['total']} | SKILLS: {len(self.skills.get_all())}")
            if success:
                print(f"Session: {self.improver.summarize_session()}")
            print(f"{'='*60}")
            return {"actions": len(all_actions), "errors": len(all_errors), "time": total_time, "success": success}

        total_time = time.time() - start_time
        self.improver.log_task(task, len(all_actions), len(all_errors), total_time, False)
        print(f"\n! Max iterations ({max_iter})")
        return {"actions": len(all_actions), "errors": len(all_errors), "time": total_time, "success": False}

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
