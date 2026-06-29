"""
EXECUTOR WORKER — Executes tool operations (read, write, edit, search).
The primary worker that makes changes to the codebase.
"""

import json, time, traceback
from pathlib import Path
from kernel import BaseWorker, EventBus, Artifact, ArtifactType, ArtifactStore
from kernel.job import Job, JobStep


class ExecutorWorker(BaseWorker):
    """Worker that executes tool operations.
    
    Handles: read_file, write_file, edit_file, grep, search, run_command.
    Each operation produces artifacts.
    """

    def __init__(self, event_bus: EventBus, artifact_store: ArtifactStore,
                 tools=None, code_intel=None, patch_editor=None):
        super().__init__("executor", "ExecutorWorker", event_bus, artifact_store)
        self.tools = tools  # Tools instance
        self.code_intel = code_intel  # CodeIntel instance
        self.patch_editor = patch_editor  # PatchEditor instance

    def register(self):
        sub_id = self.event_bus.subscribe(
            "plan.created", self._on_plan_created, self.name
        )
        self._subscriptions.append(sub_id)

    def _on_plan_created(self, event):
        """Trigger execution when plan is ready."""
        pass

    def can_handle(self, step: JobStep) -> bool:
        return step.worker_type == self.worker_type or step.worker_type == "executor"

    def handle(self, job: Job, step: JobStep) -> dict:
        """Execute a step's operations."""
        task = step.params.get("task", job.context.get("task", ""))
        
        self.log(f"Executing: {step.name}")
        
        artifacts_created = []
        operations = []
        
        # Determine what to execute based on the step and job context
        if "plan" in job.context:
            plan = job.context.get("plan", {})
            phases = plan.get("phases", [])
            current_phase_idx = self._get_current_phase_idx(job, step)
            if current_phase_idx is not None and current_phase_idx < len(phases):
                phase = phases[current_phase_idx]
                phase_tasks = phase.get("tasks", [])
                for task_item in phase_tasks:
                    result = self._execute_tool_task(task_item, job)
                    if result:
                        operations.append(result)
                        if result.get("artifact"):
                            artifacts_created.append(result["artifact"])
        
        # If no plan-based tasks, execute the step params
        if not operations:
            for key, value in step.params.items():
                if key == "task":
                    continue
                result = self._execute_param_operation(key, value, job)
                if result:
                    operations.append(result)
        
        return {
            "status": "completed",
            "step": step.name,
            "operations": len(operations),
            "artifacts_created": len(artifacts_created),
            "operation_summaries": [o.get("summary", "") for o in operations[:5]],
        }

    def _get_current_phase_idx(self, job: Job, step: JobStep) -> int:
        """Find the current phase index based on completed steps."""
        completed = sum(1 for s in job.steps if s.status.value == "completed")
        return completed

    def _execute_tool_task(self, task_item: dict, job: Job) -> dict:
        """Execute a single tool task from the plan."""
        tool = task_item.get("tool", "")
        args = task_item.get("args", {})
        desc = task_item.get("desc", "")
        
        if tool == "read_file":
            path = args.get("path", "")
            if path and self.tools and hasattr(self.tools, "read_file"):
                try:
                    content = self.tools.read_file(path)
                    art = Artifact(f"file:read:{Path(path).name}", ArtifactType.CODE,
                                   content=str(content)[:5000],
                                   source_job=job.id,
                                   tags=["file", "read", Path(path).suffix.lstrip(".")])
                    return {"summary": f"Read {path}", "artifact": art, "tool": tool}
                except Exception as e:
                    return {"summary": f"Error reading {path}: {e}", "tool": tool}
        
        elif tool == "grep":
            text = args.get("text", "")
            include = args.get("include", "")
            if text and self.tools and hasattr(self.tools, "grep"):
                try:
                    result = self.tools.grep(text, include)
                    art = Artifact(f"search:{text[:30]}", ArtifactType.TEXT,
                                   content=str(result)[:5000],
                                   source_job=job.id,
                                   tags=["search", "grep"])
                    return {"summary": f"Searched for '{text[:30]}'", "artifact": art, "tool": tool}
                except Exception as e:
                    return {"summary": f"Search error: {e}", "tool": tool}
        
        elif tool == "tree":
            depth = args.get("depth", 2)
            if self.tools and hasattr(self.tools, "tree"):
                try:
                    result = self.tools.tree(depth)
                    art = Artifact("directory:tree", ArtifactType.TEXT,
                                   content=str(result)[:5000],
                                   source_job=job.id,
                                   tags=["directory", "structure"])
                    return {"summary": f"Directory tree (depth={depth})", "artifact": art, "tool": tool}
                except Exception as e:
                    return {"summary": f"Tree error: {e}", "tool": tool}
        
        return {"summary": f"Unknown/unsupported tool: {tool}", "tool": tool}

    def _execute_param_operation(self, key: str, value, job: Job) -> dict:
        """Execute an operation from step params."""
        return {"summary": f"Param {key} = {str(value)[:50]}", "tool": "param"}
