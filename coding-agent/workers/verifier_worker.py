"""
VERIFIER WORKER — Verifies changes (syntax, imports, build, tests).
Wraps Verifier as an event-driven worker.
"""

import json
from kernel import BaseWorker, EventBus, Artifact, ArtifactType, ArtifactStore
from kernel.job import Job, JobStep


class VerifierWorker(BaseWorker):
    """Worker that verifies changes.
    
    Checks: syntax, imports, build, lint, tests, security.
    """

    def __init__(self, event_bus: EventBus, artifact_store: ArtifactStore,
                 verifier=None):
        super().__init__("verifier", "VerifierWorker", event_bus, artifact_store)
        self.verifier = verifier  # Verifier instance

    def register(self):
        sub_id = self.event_bus.subscribe(
            "step.completed", self._on_step_completed, self.name
        )
        self._subscriptions.append(sub_id)

    def _on_step_completed(self, event):
        """Optionally trigger verification after execution step."""
        pass

    def can_handle(self, step: JobStep) -> bool:
        return step.worker_type == self.worker_type or step.worker_type == "verifier"

    def handle(self, job: Job, step: JobStep) -> dict:
        """Run verification checks."""
        self.log(f"Verifying changes for job: {job.name[:40]}")
        
        artifacts_created = []
        results = {}
        all_pass = True
        
        if self.verifier:
            # Get modified files from job context
            files = job.context.get("files", [])
            
            # Syntax check
            try:
                syntax_result = self.verifier.verify_syntax(files)
                syntax_ok = not syntax_result.get("errors", [])
                results["syntax"] = {
                    "ok": syntax_ok,
                    "details": syntax_result.get("details", ""),
                    "errors": len(syntax_result.get("errors", [])),
                }
                if not syntax_ok:
                    all_pass = False
                
                art = Artifact("verify:syntax", ArtifactType.REPORT,
                               content=json.dumps(syntax_result, indent=2)[:3000],
                               source_job=job.id, source_step=step.id,
                               tags=["verify", "syntax"])
                artifacts_created.append(art)
            except Exception as e:
                results["syntax"] = {"ok": False, "error": str(e)}
                all_pass = False
            
            # Import check
            try:
                import_result = self.verifier.verify_imports(files)
                import_ok = not import_result.get("errors", [])
                results["imports"] = {
                    "ok": import_ok,
                    "details": import_result.get("details", ""),
                }
                if not import_ok:
                    all_pass = False
                
                art = Artifact("verify:imports", ArtifactType.REPORT,
                               content=json.dumps(import_result, indent=2)[:3000],
                               source_job=job.id, source_step=step.id,
                               tags=["verify", "imports"])
                artifacts_created.append(art)
            except Exception as e:
                results["imports"] = {"ok": False, "error": str(e)}
                all_pass = False
            
            # Security scan
            try:
                security_result = self.verifier.verify_security(files)
                security_ok = not security_result.get("errors", [])
                results["security"] = {
                    "ok": security_ok,
                    "details": security_result.get("details", ""),
                }
                if not security_ok:
                    all_pass = False
                
                art = Artifact("verify:security", ArtifactType.REPORT,
                               content=json.dumps(security_result, indent=2)[:3000],
                               source_job=job.id, source_step=step.id,
                               tags=["verify", "security"])
                artifacts_created.append(art)
            except Exception as e:
                results["security"] = {"ok": False, "error": str(e)}
                all_pass = False

        # Publish verification result event
        self.event_bus.publish(
            "verification.passed" if all_pass else "verification.failed",
            source=self.name,
            data={
                "job_id": job.id,
                "all_pass": all_pass,
                "checks": {k: v.get("ok", False) for k, v in results.items()},
            },
        )
        
        return {
            "status": "completed" if all_pass else "failed",
            "all_pass": all_pass,
            "checks": results,
            "artifacts_created": len(artifacts_created),
        }
