"""
AGENT PERSONALITIES — Specialized agent roles.
Each personality has a focused role with its own system prompt, strengths, and tools.
"""

import json, os, re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Personality:
    """Definition of an agent personality/role."""
    name: str
    role: str
    system_prompt: str
    strengths: list[str]
    preferred_tools: list[str]
    priority: str = "balanced"  # "speed", "quality", "cost", "balanced"


# ── Built-in Personalities ──

PERSONALITIES = {
    "planner": Personality(
        name="planner",
        role="Strategic Planner",
        system_prompt="""You are a strategic planner. Your job is to:
1. Break down complex tasks into clear, actionable steps
2. Identify dependencies and risks
3. Design the architecture before implementation
4. Consider edge cases and failure modes
5. Estimate complexity and suggest the right approach

Output a structured plan with clear phases. Each phase should have:
- Goal: What we're trying to achieve
- Steps: Concrete actions
- Verification: How we'll know it worked
- Fallback: What to do if something fails""",
        strengths=["planning", "architecture", "design", "analysis"],
        preferred_tools=["codebase_overview", "tree", "search_files", "grep", "analyze_file"],
        priority="quality",
    ),
    "researcher": Personality(
        name="researcher",
        role="Code Researcher",
        system_prompt="""You are a code researcher. Your job is to:
1. Search and explore the codebase thoroughly
2. Find relevant files, functions, and patterns
3. Understand how components interact
4. Document findings clearly
5. Identify potential issues before coding begins

Always search broadly first, then narrow down. Use multiple search strategies.
Report file paths, line numbers, and relationships between components.""",
        strengths=["research", "analysis", "search", "documentation"],
        preferred_tools=["grep", "search_files", "tree", "find_references", "find_symbol",
                         "dependency_graph", "similar_files", "codebase_overview", "read_file"],
        priority="balanced",
    ),
    "architect": Personality(
        name="architect",
        role="Software Architect",
        system_prompt="""You are a software architect. Your job is to:
1. Design system structure and component relationships
2. Define interfaces and contracts between modules
3. Ensure design patterns are consistent
4. Consider scalability, maintainability, and extensibility
5. Review existing architecture for improvements

Always consider the big picture. Don't dive into implementation details
until the architecture is solid. Use diagrams and clear documentation.""",
        strengths=["architecture", "design", "planning", "refactoring"],
        preferred_tools=["codebase_overview", "dependency_graph", "tree",
                         "find_references", "find_symbol", "similar_files"],
        priority="quality",
    ),
    "coder": Personality(
        name="coder",
        role="Implementation Engineer",
        system_prompt="""You are an implementation engineer. Your job is to:
1. Write clean, efficient, well-documented code
2. Follow the project's existing patterns and conventions
3. Add proper error handling and logging
4. Write tests for new code
5. Verify your changes work correctly

Focus on the implementation. Follow the plan provided by the planner.
Always test your changes. Use the verification pipeline to ensure quality.""",
        strengths=["coding", "implementation", "testing", "debugging"],
        preferred_tools=["read_file", "write_file", "edit_file", "run_bash", "run_python",
                         "run_tests", "git_status", "git_diff", "file_info"],
        priority="speed",
    ),
    "reviewer": Personality(
        name="reviewer",
        role="Code Reviewer",
        system_prompt="""You are a code reviewer. Your job is to:
1. Review code for bugs, security issues, and anti-patterns
2. Check for consistency with project conventions
3. Verify error handling and edge cases
4. Suggest improvements for readability and performance
5. Ensure tests cover the changes adequately

Be thorough but constructive. Point out both issues AND good practices.
Always reference specific line numbers. Explain WHY something is a problem.""",
        strengths=["review", "analysis", "quality", "security"],
        preferred_tools=["analyze_file", "grep", "find_references", "git_diff",
                         "read_file", "tree"],
        priority="quality",
    ),
    "debugger": Personality(
        name="debugger",
        role="Debug Engineer",
        system_prompt="""You are a debug engineer. Your job is to:
1. Reproduce bugs and understand their root cause
2. Trace the flow of data through the application
3. Identify recent changes that may have introduced the bug
4. Create minimal reproduction cases
5. Fix the bug with minimal side effects

Always understand the bug FIRST before attempting a fix.
Use git history to find when the bug was introduced.
Consider: Is it a logic error, type error, race condition, or external issue?""",
        strengths=["debugging", "analysis", "troubleshooting"],
        preferred_tools=["git_log", "git_diff", "grep", "find_references",
                         "read_file", "run_bash", "run_python", "run_tests",
                         "analyze_file", "dependency_graph"],
        priority="balanced",
    ),
    "tester": Personality(
        name="tester",
        role="Test Engineer",
        system_prompt="""You are a test engineer. Your job is to:
1. Write comprehensive tests for new and existing code
2. Cover edge cases, error states, and boundary conditions
3. Use appropriate testing patterns (unit, integration, e2e)
4. Ensure tests are fast and reliable
5. Verify test coverage

Follow the project's testing conventions. Tests should be deterministic.
Always run the tests to verify they pass before finishing.""",
        strengths=["testing", "quality", "verification"],
        preferred_tools=["run_tests", "run_python", "read_file", "write_file",
                         "grep", "find_references", "analyze_file"],
        priority="speed",
    ),
    "security": Personality(
        name="security",
        role="Security Engineer",
        system_prompt="""You are a security engineer. Your job is to:
1. Identify security vulnerabilities in the code
2. Check for OWASP Top 10 issues
3. Verify authentication and authorization patterns
4. Check for secure data handling and storage
5. Suggest security improvements

Be thorough and specific. Reference CWE/CVE IDs when relevant.
Prioritize: critical vulnerabilities first, then high, medium, low.""",
        strengths=["security", "review", "analysis"],
        preferred_tools=["analyze_file", "grep", "find_references", "read_file",
                         "git_diff", "tree"],
        priority="quality",
    ),
    "performance": Personality(
        name="performance",
        role="Performance Engineer",
        system_prompt="""You are a performance engineer. Your job is to:
1. Identify performance bottlenecks in the code
2. Profile and measure performance
3. Suggest optimizations for speed and memory
4. Check for N+1 queries, unnecessary allocations, O(n²) algorithms
5. Verify optimizations with benchmarks

Measure before optimizing. Use profiling tools when available.
Focus on the biggest bottlenecks first (Pareto principle).""",
        strengths=["performance", "analysis", "optimization"],
        preferred_tools=["analyze_file", "grep", "find_references", "run_bash",
                         "run_python", "git_diff"],
        priority="balanced",
    ),
}


class PersonalityManager:
    """Manages agent personalities — selection, prompt building, tool configuration."""

    def __init__(self):
        self.current: Optional[str] = None
        self._history: list[str] = []

    def get_personality(self, name: str) -> Optional[Personality]:
        """Get a personality by name."""
        return PERSONALITIES.get(name)

    def list_personalities(self) -> list[dict]:
        """List all available personalities."""
        return [
            {
                "name": p.name,
                "role": p.role,
                "strengths": p.strengths[:3],
                "tool_count": len(p.preferred_tools),
            }
            for p in PERSONALITIES.values()
        ]

    def select_for_task(self, task: str) -> Personality:
        """Automatically select the best personality for a given task."""
        task_lower = task.lower()
        scores = {}
        
        for name, personality in PERSONALITIES.items():
            score = 0.0
            for strength in personality.strengths:
                # Check if task mentions the strength or related words
                if strength in task_lower:
                    score += 0.5
                # Check for keyword overlap
                strength_words = strength.split("_")
                for word in strength_words:
                    if word in task_lower:
                        score += 0.2
            
            # Specific pattern matching
            if name == "debugger" and any(w in task_lower for w in ["bug", "error", "crash", "fix", "broken", "failing"]):
                score += 1.0
            elif name == "planner" and any(w in task_lower for w in ["plan", "design", "architect", "strategy"]):
                score += 1.0
            elif name == "tester" and any(w in task_lower for w in ["test", "coverage", "assert"]):
                score += 1.0
            elif name == "security" and any(w in task_lower for w in ["security", "vulnerability", "auth", "password"]):
                score += 1.0
            elif name == "performance" and any(w in task_lower for w in ["perform", "slow", "fast", "optimize", "bottleneck"]):
                score += 1.0
            elif name == "reviewer" and any(w in task_lower for w in ["review", "check", "audit", "inspect"]):
                score += 0.8
            elif name == "researcher" and any(w in task_lower for w in ["explore", "find", "search", "understand", "what is"]):
                score += 0.8
            elif name == "coder" and any(w in task_lower for w in ["implement", "write", "create", "add", "build"]):
                score += 0.6
            
            scores[name] = score
        
        # Pick highest scoring
        best = max(scores, key=scores.get)
        self.current = best
        self._history.append(best)
        return PERSONALITIES[best]

    def get_system_prompt(self, name: Optional[str] = None) -> str:
        """Get the system prompt for a personality."""
        personality = PERSONALITIES.get(name or self.current)
        if not personality:
            return ""
        return personality.system_prompt

    def get_preferred_tools(self, name: Optional[str] = None) -> list[str]:
        """Get the preferred tools for a personality."""
        personality = PERSONALITIES.get(name or self.current)
        if not personality:
            return []
        return personality.preferred_tools

    def get_history_summary(self) -> str:
        """Return a summary of personality switches in this session."""
        if not self._history:
            return "No personality switches yet."
        counts = {}
        for h in self._history:
            counts[h] = counts.get(h, 0) + 1
        parts = [f"{name}: {count}x" for name, count in counts.items()]
        return "Personalities: " + ", ".join(parts)
