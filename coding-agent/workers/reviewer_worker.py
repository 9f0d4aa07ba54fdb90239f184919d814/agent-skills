"""
REVIEWER WORKER — Reviews code quality and security.
Wraps EngineeringReviewer as an event-driven worker.
"""

import json
from pathlib import Path
from kernel import BaseWorker, EventBus, Artifact, ArtifactType, ArtifactStore
from kernel.job import Job, JobStep


class ReviewerWorker(BaseWorker):
    """Worker that reviews code quality.
    
    8 review dimensions: security, performance, accessibility,
    architecture, style, tests, documentation, maintainability.
    """

    def __init__(self, event_bus: EventBus, artifact_store: ArtifactStore,
                 reviewer=None):
        super().__init__("reviewer", "ReviewerWorker", event_bus, artifact_store)
        self.reviewer = reviewer  # EngineeringReviewer instance

    def register(self):
        sub_id = self.event_bus.subscribe(
            "verification.passed", self._on_verification_passed, self.name
        )
        self._subscriptions.append(sub_id)

    def _on_verification_passed(self, event):
        """Trigger review when verification passes."""
        pass

    def can_handle(self, step: JobStep) -> bool:
        return step.worker_type == self.worker_type or step.worker_type == "reviewer"

    def handle(self, job: Job, step: JobStep) -> dict:
        """Review code quality and security."""
        self.log(f"Reviewing code for job: {job.name[:40]}")
        
        artifacts_created = []
        review_results = {}
        
        # Get files to review
        files = job.context.get("files", [])
        if not files:
            files = step.params.get("files", [])
        
        # Run review on each file
        if self.reviewer and files:
            for file_path in files:
                path = Path(file_path)
                if not path.exists():
                    continue
                try:
                    content = path.read_text()
                    result = self.reviewer.review_file(str(path), content)
                    
                    review_results[file_path] = {
                        "score": result.score,
                        "issues": len(result.issues),
                        "passed": result.passed,
                        "summary": result.to_text()[:500],
                    }
                    
                    # Store review as artifact
                    art = Artifact(
                        f"review:{path.name}", ArtifactType.REPORT,
                        content=result.to_text(),
                        data={
                            "score": result.score,
                            "total_issues": len(result.issues),
                            "passed_checks": result.passed,
                        },
                        source_job=job.id, source_step=step.id,
                        tags=["review", path.suffix.lstrip(".")],
                    )
                    artifacts_created.append(art)
                    
                except Exception as e:
                    review_results[file_path] = {"error": str(e)}
        
        # Store aggregated review artifact
        if review_results:
            agg_art = Artifact(
                "review:aggregated", ArtifactType.REPORT,
                content=json.dumps(review_results, indent=2)[:5000],
                data={
                    "total_files": len(review_results),
                    "total_issues": sum(
                        r.get("issues", 0) for r in review_results.values()
                    ),
                },
                source_job=job.id, source_step=step.id,
                tags=["review", "aggregated"],
            )
            artifacts_created.append(agg_art)
        
        total_issues = sum(r.get("issues", 0) for r in review_results.values())
        self.log(f"Review complete: {len(review_results)} files, {total_issues} issues")
        
        return {
            "status": "completed",
            "files_reviewed": len(review_results),
            "total_issues": total_issues,
            "details": review_results,
            "artifacts_created": len(artifacts_created),
        }
