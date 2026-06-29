"""
MULTI-LLM SMART ROUTER — Automatically picks the best model for each task.
Classifies tasks by type, complexity, and required capabilities.
Routes to the optimal model balancing quality, speed, and cost.
"""

import os, re, json, time
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ModelProfile:
    """Profile for a model's strengths and costs."""
    name: str
    provider: str
    strengths: list[str]          # ["planning", "coding", "debugging", "refactoring", "testing", "creative"]
    speed: float = 0.5            # 0.0 (slow) to 1.0 (fast)
    quality: float = 0.7          # 0.0 (low) to 1.0 (high)
    cost: float = 0.5             # 0.0 (free) to 1.0 (expensive)
    context_window: int = 32000
    supports_vision: bool = False
    supports_structured_output: bool = True


# ── Predefined model profiles ──
# Ordered by quality, then by speed for each category

MODEL_REGISTRY = [
    # ═══ High Quality / Expensive ═══
    ModelProfile(
        name="claude-sonnet-4-20250514", provider="anthropic",
        strengths=["planning", "coding", "refactoring", "debugging", "architecture"],
        speed=0.4, quality=0.95, cost=0.9, context_window=200000, supports_vision=True,
    ),
    ModelProfile(
        name="gpt-4o", provider="openai",
        strengths=["planning", "coding", "refactoring", "debugging", "architecture", "testing"],
        speed=0.6, quality=0.9, cost=0.8, context_window=128000, supports_vision=True,
    ),
    # ═══ Mid Range ═══
    ModelProfile(
        name="openai/gpt-4o", provider="openrouter",
        strengths=["planning", "coding", "refactoring", "debugging"],
        speed=0.6, quality=0.85, cost=0.7, context_window=128000,
    ),
    ModelProfile(
        name="gemini-2.0-flash", provider="gemini",
        strengths=["coding", "debugging", "testing", "simple_tasks", "analysis"],
        speed=0.8, quality=0.8, cost=0.2, context_window=1000000, supports_vision=True,
    ),
    ModelProfile(
        name="claude-haiku-3-5", provider="anthropic",
        strengths=["simple_tasks", "analysis", "testing", "quick_edits"],
        speed=0.85, quality=0.75, cost=0.3, context_window=200000,
    ),
    # ═══ Fast / Cheap ═══
    ModelProfile(
        name="gpt-4o-mini", provider="openai",
        strengths=["simple_tasks", "quick_edits", "formatting", "analysis"],
        speed=0.9, quality=0.7, cost=0.1, context_window=128000,
    ),
    ModelProfile(
        name="o3-mini", provider="openai",
        strengths=["debugging", "analysis", "simple_tasks", "testing"],
        speed=0.7, quality=0.8, cost=0.5, context_window=200000,
    ),
    # ═══ Local (free, variable quality) ═══
    ModelProfile(
        name="qwen3:8b", provider="local",
        strengths=["simple_tasks", "quick_edits", "formatting", "analysis"],
        speed=0.7, quality=0.4, cost=0.0, context_window=8192,
    ),
    ModelProfile(
        name="opencode", provider="opencode",
        strengths=["simple_tasks", "quick_edits", "analysis"],
        speed=1.0, quality=0.5, cost=0.0, context_window=16000,
    ),
]


# ── Task Classification ──

TASK_PATTERNS = {
    "planning": [
        r"\b(plan|design|architect|architecture|schema|structure|layout)\b",
        r"\b(roadmap|strategy|approach|blueprint|specification)\b",
    ],
    "refactoring": [
        r"\b(refactor|restructure|reorganize|clean.?up|extract|inline|rename)\b",
        r"\b(split|merge|consolidate|simplify|decouple|untangle)\b",
    ],
    "debugging": [
        r"\b(bug|fix|error|crash|broken|failing|wrong|incorrect|issue)\b",
        r"\b(debug|stack.?trace|exception|traceback|null|undefined|NaN)\b",
        r"\b(not working|doesn't work|unexpected|regression|segfault)\b",
    ],
    "testing": [
        r"\b(test|spec|assert|mock|stub|fixture|coverage|unittest|pytest)\b",
        r"\b(integration.?test|e2e|snapshot|tdd|bdd|test.?case)\b",
    ],
    "security": [
        r"\b(security|vulnerability|xss|sqli|injection|sanitize|escape)\b",
        r"\b(auth|authentication|authorization|permission|encrypt|hash)\b",
        r"\b(csrf|cors|oauth|jwt|api.?key|secret|password)\b",
    ],
    "documentation": [
        r"\b(doc|document|readme|comment|docstring|api.?doc|tutorial)\b",
        r"\b(guide|manual|how.?to|explain|describe|overview)\b",
    ],
    "analysis": [
        r"\b(analyze|understand|explain|what does|how does|review)\b",
        r"\b(summarize|compare|audit|investigate|trace)\b",
    ],
    "simple_tasks": [
        r"\b(rename|typo|format|indent|add\s+(import|type|comment))\b",
        r"\b(remove\s+(line|import|comment))\b",
    ],
}


def classify_task(task: str) -> tuple[str, float]:
    """Classify a task into a category with confidence score.
    Returns (category, confidence).
    """
    task_lower = task.lower()
    best_category = "general"
    best_score = 0.0
    
    for category, patterns in TASK_PATTERNS.items():
        score = 0.0
        for pat in patterns:
            matches = re.findall(pat, task_lower)
            score += len(matches) * 0.2
        if score > best_score:
            best_score = score
            best_category = category
    
    confidence = min(best_score, 1.0)
    return best_category, confidence


def estimate_complexity(task: str, codebase_size: int = 0) -> float:
    """Estimate task complexity from 0.0 (trivial) to 1.0 (very complex)."""
    task_lower = task.lower()
    score = 0.1  # baseline
    
    # Length-based complexity
    if len(task) > 500:
        score += 0.2
    elif len(task) > 200:
        score += 0.1
    
    # Keyword-based complexity
    complex_keywords = [
        r"\b(refactor|migrate|redesign|rewrite|architect)\b",
        r"\b(multiple|several|many|complex|complicated)\b",
        r"\b(entire|whole|full|complete|global)\b",
        r"\b(optimize|performance|scalable|distributed|async)\b",
        r"\b(database|api|service|microservice|deploy)\b",
    ]
    for pat in complex_keywords:
        if re.search(pat, task_lower):
            score += 0.1
    
    # Codebase size factor
    if codebase_size > 100:
        score += 0.1
    elif codebase_size > 50:
        score += 0.05
    
    return min(score, 1.0)


# ── Priority configuration ──

PRIORITY_SPEED = "speed"
PRIORITY_QUALITY = "quality"
PRIORITY_COST = "cost"
PRIORITY_BALANCED = "balanced"
PRIORITY_MODES = [PRIORITY_SPEED, PRIORITY_QUALITY, PRIORITY_COST, PRIORITY_BALANCED]


class ModelRouter:
    """Routes tasks to the optimal model based on classification and priority."""

    def __init__(self, priority: str = PRIORITY_BALANCED):
        self.priority = priority
        self.available_models = self._detect_available()
        self.stats = {"routing_decisions": [], "total_cost_estimate": 0.0}

    def _detect_available(self) -> list[ModelProfile]:
        """Detect which models are available based on environment variables."""
        available = []
        
        # Check each provider's API key
        provider_keys = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "local": None,  # Always available if server running
        }
        
        for profile in MODEL_REGISTRY:
            key_var = provider_keys.get(profile.provider)
            if key_var is None or os.getenv(key_var):
                available.append(profile)
        
        # If no API keys found, default to opencode
        if not available:
            for profile in MODEL_REGISTRY:
                if profile.provider == "opencode":
                    available.append(profile)
        
        return available

    def route(self, task: str, codebase_size: int = 0) -> ModelProfile:
        """Pick the best model for this task."""
        category, confidence = classify_task(task)
        complexity = estimate_complexity(task, codebase_size)
        
        candidates = []
        for model in self.available_models:
            # Check if model has relevant strengths
            relevance = 0.0
            if category in model.strengths:
                relevance = 1.0
            elif "general" in category:
                relevance = 0.7
            
            # Handle opencode specially — it's the catch-all fallback
            if model.provider == "opencode":
                relevance = max(relevance, 0.3)
            
            if relevance <= 0:
                continue
            
            # Score based on priority
            if self.priority == PRIORITY_QUALITY:
                score = model.quality * 0.7 + relevance * 0.3
                if complexity > 0.6:
                    score += model.quality * 0.2  # Prefer quality for complex tasks
            elif self.priority == PRIORITY_SPEED:
                score = model.speed * 0.6 + relevance * 0.3 + (1 - model.cost) * 0.1
            elif self.priority == PRIORITY_COST:
                score = (1 - model.cost) * 0.5 + model.speed * 0.3 + relevance * 0.2
            else:  # balanced
                score = (model.quality * 0.3 + model.speed * 0.2 +
                        (1 - model.cost) * 0.1 + relevance * 0.4)
            
            # Bonus for vision tasks
            if "vision" in task.lower() and model.supports_vision:
                score += 0.2
            
            # Bonus for very complex tasks requiring reasoning
            if complexity > 0.7 and model.quality > 0.8:
                score += 0.1
            
            candidates.append((score, model))
        
        if not candidates:
            # Fallback: use first available model
            return self.available_models[0] if self.available_models else MODEL_REGISTRY[-1]
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]
        
        # Log routing decision
        self.stats["routing_decisions"].append({
            "task_category": category,
            "complexity": round(complexity, 2),
            "selected_model": best.name,
            "selected_provider": best.provider,
            "score": round(candidates[0][0], 3),
            "priority": self.priority,
        })
        self.stats["total_cost_estimate"] += best.cost * 0.1  # rough per-task cost
        
        return best

    def get_route_summary(self) -> str:
        """Return a summary of routing decisions made."""
        if not self.stats["routing_decisions"]:
            return "No routing decisions yet."
        lines = [f"Model Router ({self.priority} mode):"]
        for d in self.stats["routing_decisions"][-5:]:
            lines.append(
                f"  [{d['task_category']}] complexity={d['complexity']} → "
                f"{d['selected_provider']}/{d['selected_model']} (score={d['score']})"
            )
        lines.append(f"  Total decisions: {len(self.stats['routing_decisions'])}")
        return "\n".join(lines)

    def configure_for_task(self, task: str, codebase_size: int = 0) -> dict:
        """Get BrainConfig for the best model for this task."""
        model = self.route(task, codebase_size)
        return {
            "provider": model.provider,
            "model": model.name,
            "temperature": 0.2,
        }
