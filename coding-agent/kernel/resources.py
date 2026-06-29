"""
RESOURCE MANAGEMENT — Budget-aware resource tracking and model selection.

Tracks and enforces:
  - CPU Budget: max concurrent workers, CPU time
  - Memory Budget: estimated memory usage per operation
  - Token Budget: LLM token usage (input + output) per model
  - Cost Budget: monetary cost across model providers
  - Time Budget: execution time limits

The runtime uses ResourceManager to decide:
  - Which model to use (GPT-4, Claude, Gemini, DeepSeek, Local)
  - Whether a new job can be accepted
  - When to throttle or queue operations
"""

import time, threading
from typing import Optional
from dataclasses import dataclass, field


# ── Budget Data Classes ──


@dataclass
class CpuBudget:
    """CPU resource tracking."""
    max_concurrency: int = 4           # Max parallel CPU-bound operations
    current_concurrency: int = 0
    total_cpu_time: float = 0.0        # Accumulated CPU seconds
    cpu_time_limit: float = float('inf')
    measurement_start: float = field(default_factory=time.time)


@dataclass
class MemoryBudget:
    """Memory resource tracking."""
    max_memory_mb: float = 4096.0      # Total memory budget in MB
    current_estimated_mb: float = 0.0  # Estimated current usage
    peak_mb: float = 0.0
    per_operation_mb: float = 256.0    # Estimated per-operation memory


@dataclass
class TokenBudget:
    """Token usage tracking per model."""
    budgets: dict[str, int] = field(default_factory=lambda: {
        "gpt-4": 100000,
        "gpt-4o": 500000,
        "gpt-4o-mini": 1000000,
        "claude-3-opus": 100000,
        "claude-3-sonnet": 500000,
        "claude-3-haiku": 1000000,
        "gemini-1.5-pro": 500000,
        "gemini-1.5-flash": 1000000,
        "deepseek-coder": 500000,
        "deepseek-chat": 1000000,
        "local": 2000000,
    })
    usage: dict[str, int] = field(default_factory=lambda: {
        "gpt-4": 0,
        "gpt-4o": 0,
        "gpt-4o-mini": 0,
        "claude-3-opus": 0,
        "claude-3-sonnet": 0,
        "claude-3-haiku": 0,
        "gemini-1.5-pro": 0,
        "gemini-1.5-flash": 0,
        "deepseek-coder": 0,
        "deepseek-chat": 0,
        "local": 0,
    })
    input_tokens: dict[str, int] = field(default_factory=dict)
    output_tokens: dict[str, int] = field(default_factory=dict)
    total_tokens: int = 0
    reset_interval: float = 3600.0     # Reset budgets every hour
    last_reset: float = field(default_factory=time.time)


@dataclass
class CostBudget:
    """Monetary cost tracking per model."""
    model_costs_per_1k: dict[str, tuple[float, float]] = field(default_factory=lambda: {
        # (input_cost_per_1k_tokens, output_cost_per_1k_tokens)
        "gpt-4": (0.03, 0.06),
        "gpt-4o": (0.01, 0.03),
        "gpt-4o-mini": (0.0015, 0.006),
        "claude-3-opus": (0.015, 0.075),
        "claude-3-sonnet": (0.003, 0.015),
        "claude-3-haiku": (0.00025, 0.00125),
        "gemini-1.5-pro": (0.0035, 0.0105),
        "gemini-1.5-flash": (0.000075, 0.0003),
        "deepseek-coder": (0.00014, 0.00028),
        "deepseek-chat": (0.00027, 0.0011),
        "local": (0.0, 0.0),
    })
    total_spent: float = 0.0
    budget_limit: float = float('inf')
    daily_budget: float = 10.0          # Daily spending cap
    daily_spent: float = 0.0
    last_daily_reset: float = field(default_factory=time.time)


@dataclass
class TimeBudget:
    """Execution time tracking."""
    total_time: float = 0.0
    time_limit: float = float('inf')
    per_job_timeout: float = 600.0     # 10 minutes default
    per_step_timeout: float = 120.0    # 2 minutes default


# ── Model Selection ──


class ModelSelector:
    """Intelligently selects models based on task type and budget constraints."""

    # Task categories and their preferred model tiers
    TASK_TIERS = {
        "code_generation":    ["gpt-4o", "claude-3-sonnet", "deepseek-coder", "gpt-4o-mini", "local"],
        "code_review":        ["claude-3-opus", "gpt-4", "gpt-4o", "deepseek-coder", "gpt-4o-mini"],
        "debugging":          ["gpt-4o", "claude-3-sonnet", "deepseek-coder", "gpt-4o-mini"],
        "planning":           ["claude-3-opus", "gpt-4", "gpt-4o", "gpt-4o-mini"],
        "analysis":           ["claude-3-sonnet", "gpt-4o", "deepseek-chat", "gpt-4o-mini"],
        "simple_query":       ["gpt-4o-mini", "claude-3-haiku", "gemini-1.5-flash", "local"],
        "refactoring":        ["gpt-4o", "claude-3-sonnet", "deepseek-coder", "gpt-4o-mini"],
        "testing":            ["gpt-4o", "deepseek-coder", "gpt-4o-mini", "local"],
        "documentation":      ["gpt-4o-mini", "claude-3-haiku", "gemini-1.5-flash", "local"],
        "embedding":          ["local"],  # Embeddings always local
    }

    # Cost tiers (1 = cheapest, 5 = most expensive)
    MODEL_COST_TIER = {
        "local": 1,
        "gemini-1.5-flash": 1,
        "claude-3-haiku": 2,
        "gpt-4o-mini": 2,
        "deepseek-coder": 2,
        "deepseek-chat": 2,
        "gemini-1.5-pro": 3,
        "gpt-4o": 4,
        "claude-3-sonnet": 4,
        "gpt-4": 5,
        "claude-3-opus": 5,
    }

    def __init__(self, resource_manager: "ResourceManager"):
        self.rm = resource_manager

    def select_model(self, task_type: str, complexity: str = "medium",
                     prefer_cheap: bool = False) -> str:
        """Select the best model for a task given current budget constraints.

        Args:
            task_type: Type of task (code_generation, review, etc.)
            complexity: 'simple', 'medium', 'complex'
            prefer_cheap: If True, bias toward cheaper models.

        Returns:
            Model name string (e.g., 'gpt-4o', 'claude-3-sonnet')
        """
        candidates = self.TASK_TIERS.get(task_type, self.TASK_TIERS["simple_query"])
        budget = self.rm.tokens
        cost = self.rm.cost

        # Filter by available budget
        available = []
        for model in candidates:
            # Check token budget
            if budget.usage.get(model, 0) >= budget.budgets.get(model, 100000):
                continue

            # Check daily cost
            if cost.daily_spent >= cost.daily_budget:
                # Only allow free/cheap models
                if self.MODEL_COST_TIER.get(model, 5) > 2:
                    continue

            available.append(model)

        if not available:
            # Fall back to cheapest available
            available = sorted(candidates, key=lambda m: self.MODEL_COST_TIER.get(m, 5))

        if prefer_cheap:
            return available[0]

        # Select based on complexity
        if complexity == "complex":
            # Prefer most capable model within budget
            return available[-1] if len(available) > 1 else available[0]
        elif complexity == "simple":
            return available[0]
        else:
            # Medium: pick middle
            return available[len(available) // 2]

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate monetary cost for a model call."""
        costs = self.rm.cost.model_costs_per_1k.get(model, (0, 0))
        return (input_tokens / 1000 * costs[0]) + (output_tokens / 1000 * costs[1])


# ── Resource Manager ──


class ResourceManager:
    """Central resource manager tracking all budgets.

    The runtime consults ResourceManager before:
      - Accepting new jobs (check CPU, memory, time budgets)
      - Choosing a model (check token and cost budgets)
      - Executing operations (enforce timeouts)
      - Rate limiting (prevent resource exhaustion)

    Each budget can be independently configured and queried.
    """

    def __init__(self):
        self.cpu = CpuBudget()
        self.memory = MemoryBudget()
        self.tokens = TokenBudget()
        self.cost = CostBudget()
        self.time = TimeBudget()

        self.model_selector = ModelSelector(self)

        self._lock = threading.Lock()
        self._stats = {
            "total_operations": 0,
            "throttled_operations": 0,
            "budget_exhausted_events": 0,
        }

    # ── CPU Management ──

    def acquire_cpu(self) -> bool:
        """Try to acquire a CPU slot. Returns False if at capacity."""
        with self._lock:
            if self.cpu.current_concurrency >= self.cpu.max_concurrency:
                self._stats["throttled_operations"] += 1
                return False
            if self.cpu.total_cpu_time >= self.cpu.cpu_time_limit:
                self._stats["budget_exhausted_events"] += 1
                return False
            self.cpu.current_concurrency += 1
            return True

    def release_cpu(self, duration: float = 0.0):
        """Release a CPU slot and record CPU time."""
        with self._lock:
            self.cpu.current_concurrency = max(0, self.cpu.current_concurrency - 1)
            self.cpu.total_cpu_time += duration
            self._stats["total_operations"] += 1

    @property
    def cpu_available(self) -> int:
        return self.cpu.max_concurrency - self.cpu.current_concurrency

    @property
    def cpu_usage_percent(self) -> float:
        return (self.cpu.current_concurrency / self.cpu.max_concurrency) * 100 if self.cpu.max_concurrency > 0 else 0

    # ── Memory Management ──

    def reserve_memory(self, mb: float = None) -> bool:
        """Reserve memory for an operation. Returns False if over budget."""
        mb = mb or self.memory.per_operation_mb
        with self._lock:
            new_usage = self.memory.current_estimated_mb + mb
            if new_usage > self.memory.max_memory_mb:
                self._stats["budget_exhausted_events"] += 1
                return False
            self.memory.current_estimated_mb = new_usage
            self.memory.peak_mb = max(self.memory.peak_mb, new_usage)
            return True

    def release_memory(self, mb: float = None):
        """Release previously reserved memory."""
        mb = mb or self.memory.per_operation_mb
        with self._lock:
            self.memory.current_estimated_mb = max(0, self.memory.current_estimated_mb - mb)

    @property
    def memory_usage_percent(self) -> float:
        return (self.memory.current_estimated_mb / self.memory.max_memory_mb) * 100 if self.memory.max_memory_mb > 0 else 0

    # ── Token Management ──

    def record_token_usage(self, model: str, input_tokens: int, output_tokens: int):
        """Record token usage for a model."""
        with self._lock:
            # Reset budgets if interval passed
            now = time.time()
            if now - self.tokens.last_reset > self.tokens.reset_interval:
                self.tokens.usage = {k: 0 for k in self.tokens.usage}
                self.tokens.input_tokens = {}
                self.tokens.output_tokens = {}
                self.tokens.last_reset = now

            self.tokens.usage[model] = self.tokens.usage.get(model, 0) + input_tokens + output_tokens
            self.tokens.input_tokens[model] = self.tokens.input_tokens.get(model, 0) + input_tokens
            self.tokens.output_tokens[model] = self.tokens.output_tokens.get(model, 0) + output_tokens
            self.tokens.total_tokens += input_tokens + output_tokens

    def can_use_model(self, model: str, estimated_tokens: int = 0) -> bool:
        """Check if a model is within budget."""
        budget = self.tokens.budgets.get(model, 100000)
        used = self.tokens.usage.get(model, 0)
        return (used + estimated_tokens) <= budget

    def token_usage_percent(self, model: str = None) -> float:
        """Get token usage percentage for a model or all models."""
        if model:
            budget = self.tokens.budgets.get(model, 1)
            used = self.tokens.usage.get(model, 0)
            return (used / budget) * 100
        total_budget = sum(self.tokens.budgets.values())
        if total_budget == 0:
            return 0
        return (self.tokens.total_tokens / total_budget) * 100

    # ── Cost Management ──

    def record_cost(self, model: str, input_tokens: int, output_tokens: int):
        """Record monetary cost for a model call."""
        costs = self.cost.model_costs_per_1k.get(model, (0, 0))
        cost = (input_tokens / 1000 * costs[0]) + (output_tokens / 1000 * costs[1])

        with self._lock:
            now = time.time()
            if now - self.cost.last_daily_reset >= 86400:  # 24 hours
                self.cost.daily_spent = 0.0
                self.cost.last_daily_reset = now

            self.cost.total_spent += cost
            self.cost.daily_spent += cost

    def can_afford(self, model: str, input_tokens: int, output_tokens: int) -> bool:
        """Check if a model call is within cost budget."""
        costs = self.cost.model_costs_per_1k.get(model, (0, 0))
        estimated = (input_tokens / 1000 * costs[0]) + (output_tokens / 1000 * costs[1])
        return (self.cost.daily_spent + estimated) <= self.cost.daily_budget

    @property
    def cost_usage_percent(self) -> float:
        return (self.cost.daily_spent / self.cost.daily_budget) * 100 if self.cost.daily_budget > 0 else 0

    # ── Time Management ──

    def check_time_budget(self, elapsed: float) -> bool:
        """Check if we're within the global time budget."""
        with self._lock:
            return (self.time.total_time + elapsed) <= self.time.time_limit

    def record_time(self, duration: float):
        with self._lock:
            self.time.total_time += duration

    # ── Budget Enforcement ──

    def can_accept_job(self, estimated_memory_mb: float = None,
                       estimated_duration: float = None) -> bool:
        """Check if the system can accept a new job based on all budgets."""
        if not self.acquire_cpu():
            return False

        mem = estimated_memory_mb or self.memory.per_operation_mb
        if not self.reserve_memory(mem):
            self.release_cpu()
            return False

        dur = estimated_duration or self.time.per_step_timeout
        if not self.check_time_budget(dur):
            self.release_cpu()
            self.release_memory(mem)
            return False

        # Release immediately (caller will acquire properly)
        self.release_cpu()
        self.release_memory(mem)
        return True

    def get_stats(self) -> dict:
        """Get comprehensive resource statistics."""
        return {
            "cpu": {
                "max_concurrency": self.cpu.max_concurrency,
                "current_concurrency": self.cpu.current_concurrency,
                "available": self.cpu_available,
                "usage_percent": self.cpu_usage_percent,
                "total_cpu_time": self.cpu.total_cpu_time,
                "cpu_time_limit": self.cpu.cpu_time_limit,
            },
            "memory": {
                "max_mb": self.memory.max_memory_mb,
                "current_estimated_mb": self.memory.current_estimated_mb,
                "peak_mb": self.memory.peak_mb,
                "usage_percent": self.memory_usage_percent,
            },
            "tokens": {
                "total_tokens": self.tokens.total_tokens,
                "usage": dict(self.tokens.usage),
                "budgets": dict(self.tokens.budgets),
                "overall_percent": self.token_usage_percent(),
            },
            "cost": {
                "total_spent": self.cost.total_spent,
                "daily_spent": self.cost.daily_spent,
                "daily_budget": self.cost.daily_budget,
                "usage_percent": self.cost_usage_percent,
            },
            "time": {
                "total_time": self.time.total_time,
                "time_limit": self.time.time_limit,
                "per_job_timeout": self.time.per_job_timeout,
                "per_step_timeout": self.time.per_step_timeout,
            },
            "stats": dict(self._stats),
        }

    def get_summary(self) -> str:
        """Human-readable summary of resource usage."""
        s = self.get_stats()
        lines = [
            "💻 Resource Management Summary",
            f"  🖥️  CPU: {s['cpu']['current_concurrency']}/{s['cpu']['max_concurrency']} "
                f"({s['cpu']['usage_percent']:.0f}%)",
            f"  🧠 Memory: {s['memory']['current_estimated_mb']:.0f}/{s['memory']['max_mb']:.0f} MB "
                f"({s['memory']['usage_percent']:.0f}%)",
            f"  🔤 Tokens: {s['tokens']['total_tokens']:,} total "
                f"({s['tokens']['overall_percent']:.0f}% of budget)",
            f"  💰 Cost: ${s['cost']['daily_spent']:.4f} / ${s['cost']['daily_budget']:.2f} today "
                f"(${s['cost']['total_spent']:.4f} total)",
            f"  ⏱️  Time: {s['time']['total_time']:.1f}s / "
                f"{'∞' if s['time']['time_limit'] == float('inf') else f'{s['time']['time_limit']}s'}",
        ]
        return "\n".join(lines)
