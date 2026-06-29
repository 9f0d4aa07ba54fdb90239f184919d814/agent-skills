"""
CONTEXT WORKER — Analyzes tasks and discovers relevant context.
Wraps ContextEngine as an event-driven worker.
"""

import json, time
from kernel import BaseWorker, EventBus, Event, EVT_CONTEXT_BUILT, \
    Artifact, ArtifactType, ArtifactStore
from kernel.job import Job, JobStep


class ContextWorker(BaseWorker):
    """Worker that builds context for a task.
    
    Subscribes to 'task.created' events and publishes 'context.built'.
    Uses the ContextEngine to analyze the codebase and find relevant files.
    """

    def __init__(self, event_bus: EventBus, artifact_store: ArtifactStore,
                 context_engine=None):
        super().__init__("context", "ContextWorker", event_bus, artifact_store)
        self.context_engine = context_engine  # Set externally after construction

    def register(self):
        sub_id = self.event_bus.subscribe(
            "step.started", self._on_step_started, self.name
        )
        self._subscriptions.append(sub_id)

    def _on_step_started(self, event: Event):
        """Listen for steps that need context building."""
        data = event.data
        if data.get("worker") != self.worker_type:
            return
        # Context building will be triggered by the runtime's execute loop

    def can_handle(self, step: JobStep) -> bool:
        return step.worker_type == self.worker_type or step.worker_type == "context"

    def handle(self, job: Job, step: JobStep) -> dict:
        """Build context for a task."""
        self.log(f"Building context for job: {job.name[:40]}")
        
        task = step.params.get("task", job.context.get("task", ""))
        workdir = step.params.get("workdir", ".")
        
        artifacts_created = []
        
        # Use ContextEngine if available
        if self.context_engine:
            try:
                ctx_result = self.context_engine.analyze_task(task)
                relevant_files = ctx_result.get("files", [])
                llm_context = ctx_result.get("context", "")
                
                # Store as artifact
                ctx_artifact = Artifact(
                    "context:analyzed", ArtifactType.JSON,
                    content=llm_context[:5000],
                    data={
                        "task": task,
                        "files_found": len(relevant_files),
                        "files": relevant_files[:20],
                        "raw_context_length": len(llm_context),
                    },
                    source_job=job.id, source_step=step.id,
                    tags=["context", "analysis"],
                )
                artifacts_created.append(ctx_artifact)
                
                # Update job context
                job.update_context("relevant_files", relevant_files)
                job.update_context("llm_context", llm_context[:5000])
                job.context["files"] = [str(f) for f in relevant_files]
                
                self.log(f"Found {len(relevant_files)} relevant files")
                
            except Exception as e:
                self.log(f"ContextEngine error: {e}", "warning")
        
        # Extract project knowledge
        project_knowledge = {}
        if self.context_engine and hasattr(self.context_engine, "extract_project_knowledge"):
            try:
                project_knowledge = self.context_engine.extract_project_knowledge()
                pk_artifact = Artifact(
                    "context:project-knowledge", ArtifactType.JSON,
                    data=project_knowledge,
                    source_job=job.id, source_step=step.id,
                    tags=["context", "project-knowledge"],
                )
                artifacts_created.append(pk_artifact)
                job.update_context("project_knowledge", project_knowledge)
            except Exception as e:
                self.log(f"Project knowledge extraction error: {e}", "warning")
        
        return {
            "status": "completed",
            "task": task[:80],
            "relevant_files": job.context.get("files", [])[:10],
            "has_project_knowledge": bool(project_knowledge),
            "artifacts": len(artifacts_created),
        }
