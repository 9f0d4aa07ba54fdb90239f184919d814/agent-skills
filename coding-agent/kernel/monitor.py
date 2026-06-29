"""
MONITORING — Professional self-monitoring.

Tracks: CPU, RAM, Tokens, Latency, Failures, Retries, Cost, Success Rate, Model Usage.
Provides dashboards and alerting.
"""

import json, time, os, platform
from pathlib import Path
from typing import Optional
from datetime import datetime
from collections import defaultdict


MONITOR_DIR = Path.home() / ".coding-agent" / "monitor"


class MetricsStore:
    """Time-series metrics storage."""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else MONITOR_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._metrics: list[dict] = []
        self._max_in_memory = 10000

    def record(self, name: str, value: float, tags: dict = None):
        """Record a metric point."""
        point = {
            "name": name,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
        }
        self._metrics.append(point)
        if len(self._metrics) > self._max_in_memory:
            self._flush()
        return point

    def _flush(self):
        """Flush metrics to disk."""
        if not self._metrics:
            return
        day = datetime.now().strftime("%Y-%m-%d")
        daily_dir = self.base_dir / day
        daily_dir.mkdir(parents=True, exist_ok=True)
        file_path = daily_dir / f"metrics-{int(time.time())}.jsonl"
        with open(file_path, "a") as f:
            for point in self._metrics:
                f.write(json.dumps(point) + "\n")
        self._metrics = []

    def query(self, name: str = "", since: float = 0.0,
              limit: int = 100) -> list[dict]:
        """Query metrics."""
        results = []
        # Check in-memory
        for point in self._metrics:
            if (not name or point["name"] == name) and point["timestamp"] >= since:
                results.append(point)
        # Check on-disk
        for day_dir in sorted(self.base_dir.iterdir()):
            if not day_dir.is_dir():
                continue
            for file_path in sorted(day_dir.iterdir()):
                try:
                    for line in file_path.read_text().strip().split("\n"):
                        if not line:
                            continue
                        point = json.loads(line)
                        if (not name or point["name"] == name) and point["timestamp"] >= since:
                            results.append(point)
                except:
                    pass
        results.sort(key=lambda p: p["timestamp"], reverse=True)
        return results[:limit]

    def get_summary(self, since: float = 0.0) -> dict:
        """Get summary statistics for all metrics."""
        points = self.query(since=since, limit=10000)
        metrics_by_name = defaultdict(list)
        for p in points:
            metrics_by_name[p["name"]].append(p["value"])
        summary = {}
        for name, values in metrics_by_name.items():
            summary[name] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values) if values else 0,
                "last": values[-1] if values else 0,
            }
        return summary


class SystemMonitor:
    """Monitors system resources and performance."""

    def __init__(self):
        self.store = MetricsStore()
        self._start_time = time.time()

    def record_tool_call(self, tool_name: str, duration: float, success: bool):
        """Record a tool call."""
        self.store.record("tool.call", 1.0, {
            "tool": tool_name,
            "duration": round(duration, 3),
            "success": str(success),
        })
        self.store.record("tool.duration", duration, {"tool": tool_name})
        if not success:
            self.store.record("tool.failure", 1.0, {"tool": tool_name})

    def record_llm_call(self, model: str, tokens_in: int, tokens_out: int,
                         duration: float, cost: float):
        """Record an LLM call."""
        self.store.record("llm.call", 1.0, {"model": model})
        self.store.record("llm.tokens", tokens_in + tokens_out, {"model": model})
        self.store.record("llm.tokens_in", tokens_in, {"model": model})
        self.store.record("llm.tokens_out", tokens_out, {"model": model})
        self.store.record("llm.duration", duration, {"model": model})
        self.store.record("llm.cost", cost, {"model": model})

    def record_job_result(self, job_id: str, success: bool, duration: float,
                           steps: int, errors: int):
        """Record a job result."""
        self.store.record("job.completed", 1.0 if success else 0.0,
                         {"job_id": job_id[:8]})
        self.store.record("job.duration", duration)
        self.store.record("job.steps", float(steps))

    def record_error(self, error_type: str, source: str):
        """Record an error."""
        self.store.record("error.count", 1.0, {"type": error_type, "source": source})

    def get_dashboard(self) -> dict:
        """Get a monitoring dashboard snapshot."""
        since = time.time() - 3600  # Last hour
        summary = self.store.get_summary(since)
        all_points = self.store.query(since=since, limit=5000)

        # Calculate success rate
        tool_calls = [p for p in all_points if p["name"] == "tool.call"]
        successful_tools = [p for p in tool_calls if p["tags"].get("success") == "True"]
        success_rate = len(successful_tools) / len(tool_calls) * 100 if tool_calls else 0

        # Cost tracking
        total_cost = sum(p["value"] for p in all_points if p["name"] == "llm.cost")

        # Error tracking
        errors = [p for p in all_points if p["name"] == "error.count"]
        error_types = defaultdict(int)
        for e in errors:
            etype = e["tags"].get("type", "unknown")
            error_types[etype] += 1

        return {
            "uptime": time.time() - self._start_time,
            "tool_calls": len(tool_calls),
            "success_rate": round(success_rate, 1),
            "total_cost": round(total_cost, 4),
            "errors": len(errors),
            "error_types": dict(error_types),
            "metrics_summary": {k: {sk: round(sv, 2) if isinstance(sv, float) else sv
                                   for sk, sv in v.items()}
                              for k, v in summary.items()},
            "last_hour": {
                "tool_calls": len(tool_calls),
                "errors": len(errors),
            },
        }

    def get_dashboard_text(self) -> str:
        """Get a human-readable dashboard."""
        dash = self.get_dashboard()
        lines = [
            "╔══════════════════════════════════════╗",
            "║        AGENT MONITORING DASHBOARD    ║",
            "╚══════════════════════════════════════╝",
            "",
            f"Uptime: {dash['uptime']:.0f}s",
            f"Tool calls (1h): {dash['tool_calls']}",
            f"Success rate: {dash['success_rate']}%",
            f"Total cost: ${dash['total_cost']:.4f}",
            f"Errors (1h): {dash['errors']}",
            "",
            "Error types:",
        ]
        for etype, count in dash.get("error_types", {}).items():
            lines.append(f"  {etype}: {count}")
        lines.append("")
        lines.append("Metrics summary (last hour):")
        for name, stats in dash.get("metrics_summary", {}).items():
            lines.append(f"  {name}: avg={stats.get('avg', '?')}, "
                         f"max={stats.get('max', '?')}, count={stats.get('count', '?')}")
        return "\n".join(lines)


class WorkerTelemetry:
    """Per-worker telemetry tracking.
    
    Every worker emits telemetry: timing, tokens, cost, success rate.
    Enables answers to:
    - Which worker is slow?
    - Which model costs the most?
    - Which tasks fail most often?
    """

    def __init__(self, monitor: SystemMonitor = None):
        self.monitor = monitor or SystemMonitor()
        self._worker_stats: dict[str, dict] = {}  # worker_name -> stats

    def record_worker_execution(self, worker_name: str, worker_type: str,
                                 duration: float, success: bool,
                                 tokens_used: int = 0, cost: float = 0.0,
                                 command_type: str = "", error: str = ""):
        """Record a worker execution for telemetry."""
        if worker_name not in self._worker_stats:
            self._worker_stats[worker_name] = {
                "worker_type": worker_type,
                "executions": 0,
                "successful": 0,
                "failed": 0,
                "total_duration": 0.0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "errors": [],
                "by_command": defaultdict(lambda: {"count": 0, "duration": 0.0, "successful": 0}),
            }
        
        stats = self._worker_stats[worker_name]
        stats["executions"] += 1
        if success:
            stats["successful"] += 1
        else:
            stats["failed"] += 1
        stats["total_duration"] += duration
        stats["total_tokens"] += tokens_used
        stats["total_cost"] += cost
        
        if error:
            stats["errors"].append(error[:100])
            stats["errors"] = stats["errors"][-20:]  # Keep last 20
        
        if command_type:
            cmd_stats = stats["by_command"][command_type]
            cmd_stats["count"] += 1
            cmd_stats["duration"] += duration
            if success:
                cmd_stats["successful"] += 1
        
        # Record to metrics store
        self.monitor.store.record("worker.execution", 1.0, {
            "worker": worker_name,
            "type": worker_type,
            "duration": round(duration, 3),
            "success": str(success),
            "tokens": tokens_used,
            "cost": round(cost, 6),
            "command": command_type,
        })

    def get_worker_stats(self, worker_name: str = "") -> dict:
        """Get telemetry for a specific worker or all workers."""
        if worker_name:
            return self._worker_stats.get(worker_name, {})
        return dict(self._worker_stats)

    def get_summary(self) -> str:
        """Get a human-readable telemetry summary."""
        if not self._worker_stats:
            return "No worker telemetry recorded yet."
        
        lines = ["Worker Telemetry:"]
        for name, stats in sorted(self._worker_stats.items()):
            success_rate = (stats["successful"] / stats["executions"] * 100
                           if stats["executions"] > 0 else 0)
            avg_duration = (stats["total_duration"] / stats["executions"]
                           if stats["executions"] > 0 else 0)
            lines.append(f"  {name} ({stats['worker_type']}):")
            lines.append(f"    Executions: {stats['executions']}")
            lines.append(f"    Success rate: {success_rate:.1f}%")
            lines.append(f"    Avg duration: {avg_duration:.3f}s")
            lines.append(f"    Total cost: ${stats['total_cost']:.4f}")
            lines.append(f"    Total tokens: {stats['total_tokens']}")
            if stats["by_command"]:
                lines.append("    By command:")
                for cmd, cmd_stats in sorted(stats["by_command"].items()):
                    cmd_sr = (cmd_stats["successful"] / cmd_stats["count"] * 100
                             if cmd_stats["count"] > 0 else 0)
                    lines.append(f"      {cmd}: {cmd_stats['count']} runs, "
                                 f"{cmd_sr:.0f}% success, "
                                 f"{cmd_stats['duration']/cmd_stats['count']:.2f}s avg")
        return "\n".join(lines)
