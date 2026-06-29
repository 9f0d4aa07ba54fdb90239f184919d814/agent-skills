"""
EXECUTION PLANNER — Professional planning pipeline.
Architect → Planner → Risk Analysis → Estimate → Tasks → Execution.
Expands a user task into a structured, prioritized execution plan.
"""

import json, re, time
from typing import Optional
from datetime import datetime


class ExecutionPhase:
    """A phase in the execution plan."""
    def __init__(self, name: str, description: str, tasks: list[dict] = None,
                 risks: list[str] = None, estimated_effort: str = "medium"):
        self.name = name
        self.description = description
        self.tasks = tasks or []
        self.risks = risks or []
        self.estimated_effort = estimated_effort  # "small", "medium", "large", "xl"
        self.dependencies: list[str] = []

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "tasks": self.tasks,
            "risks": self.risks,
            "estimated_effort": self.estimated_effort,
            "dependencies": self.dependencies,
        }


class ExecutionPlanner:
    """Expands a user task into a structured execution plan.
    
    Pipeline:
    1. Understand: Clarify what's being asked
    2. Decompose: Break into phases
    3. Risk Analysis: Identify risks per phase
    4. Estimate: Effort estimation per phase
    5. Prioritize: Order phases by dependencies
    6. Generate: Create concrete tool-level tasks
    """

    def __init__(self):
        pass

    def plan(self, task: str, task_type: str = "general",
             context: str = "") -> list[ExecutionPhase]:
        """Generate a structured execution plan for a task."""
        
        if task_type == "testing":
            return self._plan_testing(task, context)
        elif task_type == "debugging":
            return self._plan_debugging(task, context)
        elif task_type == "refactoring":
            return self._plan_refactoring(task, context)
        elif task_type == "feature_addition":
            return self._plan_feature(task, context)
        elif task_type == "modification":
            return self._plan_modification(task, context)
        elif task_type == "deployment":
            return self._plan_deployment(task, context)
        else:
            return self._plan_general(task, context)

    def _plan_testing(self, task: str, context: str) -> list[ExecutionPhase]:
        return [
            ExecutionPhase(
                "Analysis", "Understand what needs testing",
                [
                    {"tool": "grep", "args": {"text": "def test_", "include": "*.py"},
                     "desc": "Find existing tests"},
                    {"tool": "tree", "args": {"depth": 2},
                     "desc": "Understand test directory structure"},
                ],
                risks=["Existing tests may need updates", "Test framework may not be installed"],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Strategy", "Plan test approach",
                [
                    {"tool": "read_file", "args": {"path": ""},
                     "desc": "Read source files to understand what to test"},
                ],
                risks=["Mocking dependencies could be complex"],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Implementation", "Write tests",
                [
                    {"tool": "write_file", "args": {"path": "", "content": ""},
                     "desc": "Create test files"},
                    {"tool": "run_tests", "args": {},
                     "desc": "Run tests to verify"},
                ],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Verification", "Ensure tests pass",
                [
                    {"tool": "run_tests", "args": {},
                     "desc": "Run test suite"},
                ],
                risks=["Flaky tests", "Environment differences"],
                estimated_effort="small",
            ),
        ]

    def _plan_debugging(self, task: str, context: str) -> list[ExecutionPhase]:
        return [
            ExecutionPhase(
                "Reproduce", "Understand and reproduce the bug",
                [
                    {"tool": "grep", "args": {"text": "", "include": "*.py"},
                     "desc": "Find relevant error handling code"},
                    {"tool": "run_bash", "args": {"cmd": ""},
                     "desc": "Try to reproduce the issue"},
                ],
                risks=["Bug may not be easily reproducible", "Missing error context"],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Diagnose", "Identify root cause",
                [
                    {"tool": "read_file", "args": {"path": ""},
                     "desc": "Read suspicious files"},
                    {"tool": "git_log", "args": {"count": 10},
                     "desc": "Check recent changes that may have introduced the bug"},
                ],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Fix", "Apply the fix",
                [
                    {"tool": "edit_file", "args": {"path": "", "old": "", "new": ""},
                     "desc": "Fix the root cause"},
                ],
                risks=["Fix may have side effects", "Need to check for similar patterns"],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Verify", "Confirm fix works",
                [
                    {"tool": "run_tests", "args": {},
                     "desc": "Run tests to verify fix"},
                    {"tool": "run_bash", "args": {"cmd": ""},
                     "desc": "Verify bug is fixed"},
                ],
                estimated_effort="small",
            ),
        ]

    def _plan_refactoring(self, task: str, context: str) -> list[ExecutionPhase]:
        return [
            ExecutionPhase(
                "Architecture Review", "Understand current architecture",
                [
                    {"tool": "codebase_overview", "args": {},
                     "desc": "Get full codebase overview"},
                    {"tool": "dependency_graph", "args": {},
                     "desc": "See dependency relationships"},
                ],
                risks=["Scope may be larger than expected",
                       "Multiple components may be affected"],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Design", "Design the new structure",
                [],
                risks=["Design may introduce new issues",
                       "Backward compatibility concerns"],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Implementation", "Apply changes incrementally",
                [
                    {"tool": "edit_file", "args": {"path": "", "old": "", "new": ""},
                     "desc": "Refactor file by file"},
                ],
                risks=["Changes may need rollback",
                       "Tests may fail during transition"],
                estimated_effort="large",
            ),
            ExecutionPhase(
                "Test & Verify", "Ensure nothing is broken",
                [
                    {"tool": "run_tests", "args": {},
                     "desc": "Run full test suite"},
                    {"tool": "run_bash", "args": {"cmd": "python -m compileall . -q"},
                     "desc": "Verify all files compile"},
                ],
                estimated_effort="medium",
            ),
        ]

    def _plan_feature(self, task: str, context: str) -> list[ExecutionPhase]:
        return [
            ExecutionPhase(
                "Discovery", "Find integration points",
                [
                    {"tool": "grep", "args": {"text": "", "include": "*.py"},
                     "desc": "Find relevant existing code"},
                    {"tool": "read_file", "args": {"path": ""},
                     "desc": "Read integration points"},
                ],
                risks=["Feature may conflict with existing logic",
                       "Missing dependencies"],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Design", "Design the implementation",
                [],
                risks=["API design may need iteration",
                       "Performance implications"],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Implementation", "Build the feature",
                [
                    {"tool": "write_file", "args": {"path": "", "content": ""},
                     "desc": "Create new files"},
                    {"tool": "edit_file", "args": {"path": "", "old": "", "new": ""},
                     "desc": "Modify existing files to integrate"},
                ],
                risks=["Integration may be more complex than expected",
                       "Need to handle edge cases"],
                estimated_effort="large",
            ),
            ExecutionPhase(
                "Verification", "Test and document",
                [
                    {"tool": "run_tests", "args": {},
                     "desc": "Verify feature works"},
                    {"tool": "run_bash", "args": {"cmd": ""},
                     "desc": "Manual verification"},
                ],
                estimated_effort="medium",
            ),
        ]

    def _plan_modification(self, task: str, context: str) -> list[ExecutionPhase]:
        return [
            ExecutionPhase(
                "Understand", "Read code to be modified",
                [
                    {"tool": "read_file", "args": {"path": ""},
                     "desc": "Read file to modify"},
                    {"tool": "find_references", "args": {"symbol": ""},
                     "desc": "Check what depends on this code"},
                ],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Modify", "Make the change",
                [
                    {"tool": "edit_file", "args": {"path": "", "old": "", "new": ""},
                     "desc": "Apply the modification"},
                ],
                risks=["Change may affect other parts of the system"],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Verify", "Confirm change works",
                [
                    {"tool": "run_tests", "args": {},
                     "desc": "Run relevant tests"},
                ],
                estimated_effort="small",
            ),
        ]

    def _plan_deployment(self, task: str, context: str) -> list[ExecutionPhase]:
        return [
            ExecutionPhase(
                "Check Prerequisites", "Verify deployment requirements",
                [
                    {"tool": "run_bash", "args": {"cmd": ""},
                     "desc": "Check environment and dependencies"},
                ],
                risks=["Missing environment variables",
                       "Insufficient permissions"],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Build", "Build the deployable artifact",
                [
                    {"tool": "run_bash", "args": {"cmd": ""},
                     "desc": "Build the project"},
                ],
                risks=["Build may fail due to dependency issues"],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Deploy", "Execute deployment",
                [],
                risks=["Deployment may affect running services",
                       "Rollback plan needed"],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Verify", "Confirm deployment succeeded",
                [
                    {"tool": "run_tests", "args": {},
                     "desc": "Run post-deployment tests"},
                ],
                estimated_effort="small",
            ),
        ]

    def _plan_general(self, task: str, context: str) -> list[ExecutionPhase]:
        """Generic plan for any task."""
        return [
            ExecutionPhase(
                "Explore", "Understand the relevant code",
                [
                    {"tool": "codebase_overview", "args": {},
                     "desc": "Overview of codebase"},
                    {"tool": "grep", "args": {"text": "", "include": ""},
                     "desc": "Search for relevant patterns"},
                ],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Execute", "Make changes",
                [
                    {"tool": "read_file", "args": {"path": ""},
                     "desc": "Read files to modify"},
                    {"tool": "write_file", "args": {"path": "", "content": ""},
                     "desc": "Write or modify files"},
                ],
                risks=["Unexpected complexity",
                       "Missing information"],
                estimated_effort="medium",
            ),
            ExecutionPhase(
                "Verify", "Confirm results",
                [
                    {"tool": "run_tests", "args": {},
                     "desc": "Run tests"},
                    {"tool": "run_bash", "args": {"cmd": "python -m compileall . -q"},
                     "desc": "Syntax check"},
                ],
                estimated_effort="small",
            ),
            ExecutionPhase(
                "Reflect", "Learn from the task",
                [],
                estimated_effort="small",
            ),
        ]

    def to_text(self, phases: list[ExecutionPhase]) -> str:
        """Render the plan as human-readable text."""
        lines = ["## Execution Plan"]
        total_effort = "small"
        
        for i, phase in enumerate(phases, 1):
            lines.append(f"\n### Phase {i}: {phase.name}")
            lines.append(f"**Effort:** {phase.estimated_effort}")
            if phase.description:
                lines.append(f"*{phase.description}*")
            
            if phase.tasks:
                lines.append("\n**Tasks:**")
                for j, task in enumerate(phase.tasks, 1):
                    desc = task.get("desc", "")
                    tool = task.get("tool", "")
                    lines.append(f"  {j}. [{tool}] {desc}")
            
            if phase.risks:
                lines.append("\n**Risks:**")
                for risk in phase.risks:
                    lines.append(f"  ⚠ {risk}")
        
        # Estimate total
        effort_values = {"small": 1, "medium": 2, "large": 4, "xl": 8}
        total = sum(effort_values.get(p.estimated_effort, 1) for p in phases)
        lines.append(f"\n**Total estimated effort:** {total} units")
        
        return "\n".join(lines)
