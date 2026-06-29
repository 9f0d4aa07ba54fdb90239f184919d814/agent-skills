"""
PARALLEL AGENT ORCHESTRATION — Run multiple agents simultaneously.
Coordinator dispatches work to specialized agents and merges results.
"""

import json, time, threading, queue
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentTask:
    """A task for a sub-agent."""
    id: str
    agent_type: str  # "planner", "researcher", "coder", "reviewer", "security", "tester"
    description: str
    context: str = ""
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: dict = field(default_factory=dict)
    error: str = ""
    started: Optional[str] = None
    completed: Optional[str] = None


class AgentWorker(threading.Thread):
    """A worker thread that runs an agent task."""

    def __init__(self, task: AgentTask, result_queue: queue.Queue):
        super().__init__()
        self.task = task
        self.result_queue = result_queue

    def run(self):
        self.task.status = "running"
        self.task.started = datetime.now().isoformat()
        try:
            # In a real implementation, this would use the Brain + tools
            # For now, we simulate the agent work and return a structured result
            result = self._execute()
            self.task.result = result
            self.task.status = "completed"
            self.task.error = ""
        except Exception as e:
            self.task.status = "failed"
            self.task.error = str(e)
        self.task.completed = datetime.now().isoformat()
        self.result_queue.put(self.task)

    def _execute(self) -> dict:
        """Execute the agent task. Override in subclasses."""
        # This should be replaced with actual Brain calls
        return {
            "agent_type": self.task.agent_type,
            "description": self.task.description[:50],
            "status": "simulated",
            "findings": f"Simulated execution of {self.task.agent_type} for: {self.task.description[:60]}",
        }


class ParallelOrchestrator:
    """Orchestrates multiple agent personalities working in parallel.
    
    Dispatches work to specialized agents and merges results.
    Supports: Planner, Researcher, Coder, Reviewer, Security, Tester.
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.result_queue = queue.Queue()
        self.workers: list[AgentWorker] = []
        self.agent_types = {
            "planner": "Strategic planning and task decomposition",
            "researcher": "Codebase exploration and discovery",
            "coder": "Implementation and code generation",
            "reviewer": "Code quality and correctness review",
            "security": "Security vulnerability assessment",
            "tester": "Test generation and execution",
        }

    # ── Execution ──

    def dispatch(self, tasks: list[AgentTask]) -> list[AgentTask]:
        """Run multiple agent tasks in parallel (up to max_workers at a time)."""
        self.workers = []
        self.results = []
        
        # Start tasks
        active = []
        remaining = list(tasks)
        
        while remaining or active:
            # Start new workers up to max_workers
            while len(active) < self.max_workers and remaining:
                task = remaining.pop(0)
                worker = AgentWorker(task, self.result_queue)
                worker.start()
                active.append(worker)
            
            # Wait for at least one to finish
            if active:
                # Poll for completion
                for worker in active[:]:
                    if not worker.is_alive():
                        worker.join()
                        active.remove(worker)
            
            # Collect results
            while not self.result_queue.empty():
                self.results.append(self.result_queue.get())
        
        return self.results

    def dispatch_parallel(self, tasks: list[AgentTask]) -> list[AgentTask]:
        """Run ALL tasks in parallel (up to max_workers)."""
        return self.dispatch(tasks)

    # ── Task Creation Helpers ──

    def create_task(self, agent_type: str, description: str,
                    context: str = "", params: dict = None) -> AgentTask:
        """Create a task for a specific agent type."""
        task_id = f"{agent_type}-{int(time.time() * 1000)}"
        return AgentTask(
            id=task_id,
            agent_type=agent_type,
            description=description,
            context=context,
            params=params or {},
        )

    def create_plan(self, task: str, context: str = "") -> list[AgentTask]:
        """Create a standard set of parallel agent tasks for a given user task."""
        agents = [
            ("planner", f"Decompose task: {task}"),
            ("researcher", f"Find relevant code for: {task}"),
        ]
        
        # Add security review for sensitive tasks
        sensitive_keywords = ["auth", "payment", "user data", "password", "api key", "login"]
        if any(kw in task.lower() for kw in sensitive_keywords):
            agents.append(("security", f"Security review for: {task}"))
        
        return [self.create_task(agent_type, desc, context) for agent_type, desc in agents]

    def create_review_plan(self, files: list[str], task: str = "") -> list[AgentTask]:
        """Create review tasks for the given files."""
        tasks = [
            self.create_task("reviewer", f"Review code quality in {len(files)} file(s)", task),
            self.create_task("security", f"Security scan of {len(files)} file(s)", task),
        ]
        if any(f.endswith(".py") for f in files):
            tasks.append(self.create_task("tester", f"Check test coverage for modified files", task))
        return tasks

    # ── Result Merging ──

    def merge_results(self, results: list[AgentTask], task: str = "") -> dict:
        """Merge results from multiple agents into a single response."""
        merged = {
            "summary": "",
            "findings": [],
            "issues": [],
            "suggestions": [],
            "agent_reports": {},
        }
        
        for r in results:
            merged["agent_reports"][r.agent_type] = {
                "status": r.status,
                "findings": r.result.get("findings", ""),
                "error": r.error,
            }
            if r.status == "completed":
                merged["findings"].append(f"[{r.agent_type}] {r.result.get('findings', '')[:200]}")
            else:
                merged["issues"].append(f"[{r.agent_type}] Failed: {r.error}")
        
        # Generate summary
        success_count = sum(1 for r in results if r.status == "completed")
        merged["summary"] = f"{success_count}/{len(results)} agents completed successfully"
        
        return merged

    def format_output(self, merged: dict) -> str:
        """Format merged results as human-readable text."""
        lines = ["## Parallel Agent Results"]
        lines.append(f"\n{merged['summary']}")
        
        for agent_type, report in merged.get("agent_reports", {}).items():
            status_symbol = "✓" if report.get("status") == "completed" else "✗"
            lines.append(f"\n### {status_symbol} {agent_type.title()}")
            if report.get("findings"):
                lines.append(f"  {report['findings'][:200]}")
            if report.get("error"):
                lines.append(f"  Error: {report['error']}")
        
        if merged.get("issues"):
            lines.append("\n### Issues")
            for issue in merged["issues"]:
                lines.append(f"  ⚠ {issue}")
        
        return "\n".join(lines)

    def list_agent_types(self) -> dict:
        """List available agent types."""
        return dict(self.agent_types)
