"""
SELF-BENCHMARKING — Track agent performance metrics over time.
Monitors: success rate, fix time, tokens used, retries, tool usage, errors.
Enables data-driven improvement of agent strategies.
"""

import json, os, time, hashlib
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict


BENCHMARK_DIR = Path.home() / ".coding-agent" / "benchmarks"


class BenchmarkTracker:
    """Track agent performance metrics over time.
    
    Metrics:
    - Success rate per task type
    - Average fix time
    - Tokens used
    - Retries per task
    - Tool usage patterns
    - Error types and frequency
    - User satisfaction (manual)
    """

    def __init__(self):
        BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
        self._session_file = BENCHMARK_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        self._daily_file = BENCHMARK_DIR / "daily.json"
        self._aggregate_file = BENCHMARK_DIR / "aggregate.json"
        self._session_metrics: list[dict] = []
        self._daily_metrics = self._load_daily()

    # ── Event Logging ──

    def log_task_complete(self, task: str, task_type: str, success: bool,
                          time_secs: float, steps: int, errors: int,
                          tools_used: list[str], model: str = "", tokens: int = 0):
        """Log a completed task."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "success": success,
            "time_secs": round(time_secs, 1),
            "steps": steps,
            "errors": errors,
            "tools_used": tools_used,
            "model": model,
            "tokens": tokens,
            "task_preview": task[:80],
        }
        self._session_metrics.append(entry)
        self._append_to_file(entry)
        self._update_daily(entry)

    def log_error(self, error_type: str, tool: str, context: str = ""):
        """Log an error occurrence."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "error",
            "error_type": error_type,
            "tool": tool,
            "context": context[:100],
        }
        self._session_metrics.append(entry)
        self._append_to_file(entry)

    def log_tool_usage(self, tool: str, success: bool, duration: float):
        """Log a tool usage event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "tool_usage",
            "tool": tool,
            "success": success,
            "duration": round(duration, 2),
        }
        self._session_metrics.append(entry)

    # ── Session Summary ──

    def get_session_summary(self) -> dict:
        """Return summary of current session."""
        if not self._session_metrics:
            return {"tasks": 0, "summary": "No tasks logged yet"}
        
        tasks = [e for e in self._session_metrics if "task_type" in e]
        errors = [e for e in self._session_metrics if e.get("type") == "error"]
        tool_usages = [e for e in self._session_metrics if e.get("type") == "tool_usage"]
        
        total_tasks = len(tasks)
        successful = sum(1 for t in tasks if t.get("success"))
        total_time = sum(t.get("time_secs", 0) for t in tasks)
        avg_time = total_time / total_tasks if total_tasks > 0 else 0
        
        # Tool usage stats
        tool_counts = defaultdict(int)
        for t in tasks:
            for tool in t.get("tools_used", []):
                tool_counts[tool] += 1
        top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Error stats
        error_types = defaultdict(int)
        for e in errors:
            error_types[e.get("error_type", "unknown")] += 1
        top_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "tasks": total_tasks,
            "successful": successful,
            "success_rate": round(successful / total_tasks * 100, 1) if total_tasks > 0 else 0,
            "total_time_secs": round(total_time, 1),
            "avg_time_per_task": round(avg_time, 1),
            "total_errors": len(errors),
            "top_tools": dict(top_tools),
            "top_errors": dict(top_errors),
        }

    def get_session_report(self) -> str:
        """Return a human-readable session report."""
        s = self.get_session_summary()
        if s["tasks"] == 0:
            return "No tasks completed in this session."
        
        lines = [
            f"## Session Report",
            f"",
            f"**Tasks:** {s['tasks']} | **Success:** {s['successful']} "
            f"({s['success_rate']}%) | **Errors:** {s['total_errors']}",
            f"**Total time:** {s['total_time_secs']:.0f}s | **Avg per task:** {s['avg_time_per_task']:.1f}s",
        ]
        
        if s["top_tools"]:
            lines.append(f"\n**Top tools:**")
            for tool, count in s["top_tools"].items():
                lines.append(f"  - {tool}: {count}x")
        
        if s["top_errors"]:
            lines.append(f"\n**Most common errors:**")
            for err, count in s["top_errors"].items():
                lines.append(f"  - {err}: {count}x")
        
        return "\n".join(lines)

    # ── Aggregated Statistics ──

    def get_aggregate(self) -> dict:
        """Get aggregate statistics across all sessions."""
        if self._aggregate_file.exists():
            try:
                return json.loads(self._aggregate_file.read_text())
            except:
                pass
        
        # Compute from daily data
        return self._compute_aggregate()

    def _compute_aggregate(self) -> dict:
        """Compute aggregate stats from all logged data."""
        daily = self._daily_metrics
        total_tasks = sum(d.get("tasks", 0) for d in daily.values())
        total_success = sum(d.get("successful", 0) for d in daily.values())
        total_errors = sum(d.get("errors", 0) for d in daily.values())
        
        # By task type
        type_stats = defaultdict(lambda: {"total": 0, "success": 0, "time": 0})
        for entries in self._session_metrics:
            if "task_type" in entries:
                tt = entries["task_type"]
                type_stats[tt]["total"] += 1
                if entries.get("success"):
                    type_stats[tt]["success"] += 1
                type_stats[tt]["time"] += entries.get("time_secs", 0)
        
        # Top error types across sessions
        error_types = defaultdict(int)
        for day_data in daily.values():
            for err_type, count in day_data.get("error_types", {}).items():
                error_types[err_type] += count
        
        aggregate = {
            "total_tasks": total_tasks,
            "total_success": total_success,
            "success_rate": round(total_success / total_tasks * 100, 1) if total_tasks > 0 else 0,
            "total_errors": total_errors,
            "by_task_type": dict(type_stats),
            "top_error_types": dict(sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]),
            "last_updated": datetime.now().isoformat(),
        }
        
        self._aggregate_file.write_text(json.dumps(aggregate, indent=2))
        return aggregate

    def get_trend(self, metric: str = "success_rate", days: int = 7) -> list[dict]:
        """Get trend data for a metric over the last N days."""
        daily = self._daily_metrics
        result = []
        
        today = date.today()
        for i in range(days):
            d = (today.isoformat() if i == 0 else 
                 today.strftime("%Y-%m-%d"))  # Simple approach
            # Find the day's data
            for day_str, data in daily.items():
                if day_str.startswith(d[:10]):
                    if metric == "success_rate":
                        tasks = data.get("tasks", 0)
                        successful = data.get("successful", 0)
                        result.append({
                            "date": day_str,
                            "value": round(successful / tasks * 100, 1) if tasks > 0 else 0,
                        })
                    elif metric == "avg_time":
                        tasks = data.get("tasks", 0)
                        total_time = data.get("total_time", 0)
                        result.append({
                            "date": day_str,
                            "value": round(total_time / tasks, 1) if tasks > 0 else 0,
                        })
                    elif metric == "errors":
                        result.append({
                            "date": day_str,
                            "value": data.get("errors", 0),
                        })
                    break
        
        return result

    # ── Persistence ──

    def _append_to_file(self, entry: dict):
        """Append an entry to the session log file."""
        with open(self._session_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _load_daily(self) -> dict:
        """Load daily metrics."""
        if self._daily_file.exists():
            try:
                return json.loads(self._daily_file.read_text())
            except:
                pass
        return {}

    def _update_daily(self, entry: dict):
        """Update daily metrics."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self._daily_metrics:
            self._daily_metrics[today] = {
                "tasks": 0, "successful": 0, "errors": 0,
                "total_time": 0, "error_types": {},
            }
        
        daily = self._daily_metrics[today]
        daily["tasks"] += 1
        if entry.get("success"):
            daily["successful"] += 1
        daily["errors"] += entry.get("errors", 0)
        daily["total_time"] += entry.get("time_secs", 0)
        
        self._daily_file.write_text(json.dumps(self._daily_metrics, indent=2))

    def save_session(self):
        """Save session metrics to persistent storage."""
        # Compute and save aggregate
        self._compute_aggregate()
