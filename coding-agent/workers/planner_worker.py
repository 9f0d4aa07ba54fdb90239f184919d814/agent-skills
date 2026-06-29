"""
PLANNER WORKER — Decomposes tasks into execution steps.
Wraps ExecutionPlanner as an event-driven worker.
"""

import json
from kernel import BaseWorker, EventBus, Artifact, ArtifactType, ArtifactStore
from kernel.job import Job, JobStep


class PlannerWorker(BaseWorker):
    """Worker that creates execution plans.
    
    Takes a task and produces a structured plan with phases, steps, and risks.
    """

    def __init__(self, event_bus: EventBus, artifact_store: ArtifactStore,
                 execution_planner=None):
        super().__init__("planner", "PlannerWorker", event_bus, artifact_store)
        self.execution_planner = execution_planner  # Set externally

    def register(self):
        sub_id = self.event_bus.subscribe(
            "context.built", self._on_context_built, self.name
        )
        self._subscriptions.append(sub_id)

    def _on_context_built(self, event):
        """Optionally trigger planning when context is ready."""
        pass  # Planning is driven by the runtime step execution

    def can_handle(self, step: JobStep) -> bool:
        return step.worker_type == self.worker_type or step.worker_type == "planner"

    def handle(self, job: Job, step: JobStep) -> dict:
        """Create an execution plan for the job."""
        task = step.params.get("task", job.context.get("task", ""))
        task_type = step.params.get("task_type", "general")
        
        artifacts_created = []
        plan_data = {}
        
        # Use ExecutionPlanner if available
        if self.execution_planner:
            try:
                phases = self.execution_planner.plan(task, task_type)
                plan_text = self.execution_planner.to_text(phases)
                
                # Extract plan details
                plan_data = {
                    "task": task[:80],
                    "task_type": task_type,
                    "phases": [p.to_dict() for p in phases],
                    "total_phases": len(phases),
                    "total_tasks": sum(len(p.tasks) for p in phases),
                }
                
                # Store plan as artifact
                plan_artifact = Artifact(
                    "plan:created", ArtifactType.JSON,
                    content=plan_text,
                    data=plan_data,
                    source_job=job.id, source_step=step.id,
                    tags=["plan", task_type],
                )
                artifacts_created.append(plan_artifact)
                
                # Update job with plan
                job.update_context("plan", plan_data)
                job.update_context("plan_text", plan_text)
                
                self.log(f"Created plan: {len(phases)} phases, "
                         f"{plan_data['total_tasks']} tasks")
                
            except Exception as e:
                self.log(f"Planning error: {e}", "warning")
                plan_data = {"error": str(e)}
        
        # Always create a basic plan even without ExecutionPlanner
        if not plan_data:
            plan_data = {
                "task": task[:80],
                "phases": [
                    {"name": "Explore", "description": "Understand the code"},
                    {"name": "Execute", "description": "Make changes"},
                    {"name": "Verify", "description": "Confirm results"},
                ],
            }
        
        return {
            "status": "completed",
            "task": task[:80],
            "has_plan": bool(plan_data),
            "phases": len(plan_data.get("phases", [])),
            "plan_summary": json.dumps(plan_data)[:500],
        }
