"""
Self-Improvement System - Session summaries, cross-session learning,
and result persistence between prompts.
"""

import json, time
from pathlib import Path
from datetime import datetime

IMPROVE_DIR = Path.home() / ".coding-agent" / "improvements"
IMPROVE_DIR.mkdir(parents=True, exist_ok=True)


class SelfImprover:
    def __init__(self):
        self.session_log: list[dict] = []
        self._load_session()

    def _load_session(self):
        session_file = IMPROVE_DIR / "current_session.json"
        if session_file.exists():
            try:
                self.session_log = json.loads(session_file.read_text())
            except:
                self.session_log = []

    def _save_session(self):
        session_file = IMPROVE_DIR / "current_session.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(self.session_log, indent=2))

    def log_task(self, task: str, actions: int, errors: int, time_secs: float, success: bool, result: str = ""):
        entry = {
            "task": task[:100],
            "actions": actions,
            "errors": errors,
            "time_secs": round(time_secs, 1),
            "success": success,
            "result": result[:300],
            "timestamp": datetime.now().isoformat(),
        }
        self.session_log.append(entry)
        self._save_session()

    def summarize_session(self) -> str:
        if not self.session_log:
            return "No tasks completed in this session."
        total = len(self.session_log)
        success = sum(1 for t in self.session_log if t.get("success"))
        total_errors = sum(t.get("errors", 0) for t in self.session_log)
        total_time = sum(t.get("time_secs", 0) for t in self.session_log)
        return (
            f"Session Summary: {total} tasks, {success} successful, "
            f"{total_errors} total errors, {total_time:.0f}s total time"
        )

    def generate_improvements(self) -> list[str]:
        if not self.session_log:
            return []
        improvements = []
        error_tasks = [t for t in self.session_log if t.get("errors", 0) > 0]
        if error_tasks:
            improvements.append(f"Review {len(error_tasks)} failed tasks")
        slow_tasks = [t for t in self.session_log if t.get("time_secs", 0) > 60]
        if slow_tasks:
            improvements.append(f"Optimize {len(slow_tasks)} slow tasks")
        return improvements

    def compact_knowledge(self) -> str:
        """Return actionable context from previous tasks for the next prompt."""
        if not self.session_log:
            return ""
        lines = ["[Previously known facts: (use these instead of re-running tools)]"]
        for t in self.session_log[-3:]:
            task_short = t['task'][:60]
            result_short = t.get('result', '')[:100]
            status = "✓" if t.get('success') else "?"
            lines.append(f"  {status} {task_short}")
            if result_short:
                lines.append(f"    › {result_short}")
        return "\n".join(lines)

    def end_session(self):
        summary = self.summarize_session()
        improvements = self.generate_improvements()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        knowledge_file = IMPROVE_DIR / f"knowledge_{timestamp}.md"
        knowledge_file.write_text(f"# Session {timestamp}\n\n{summary}\n\n## Improvements\n" + "\n".join(f"- {i}" for i in improvements))
        self.session_log = []
        self._save_session()
        return summary
