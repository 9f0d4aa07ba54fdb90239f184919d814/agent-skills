"""
ENGINEERING REASONER

This is the "senior engineer" brain that reasons about tasks BEFORE planning.

Instead of immediately jumping to implementation, it asks:
- WHY is this needed?
- WHAT systems are affected?
- WHAT are the risks?
- IS there a better approach?
- SHOULD we refactor instead of patching?
- WHAT are the tradeoffs?

This separates strategic thinking from tactical execution.
"""

import json, time
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskComplexity(Enum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class EngineeringAnalysis:
    """Result of reasoning about a task."""
    task: str
    goal: str
    affected_systems: list[str] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)  # {"risk": str, "level": RiskLevel, "mitigation": str}
    alternatives: list[dict] = field(default_factory=list)  # {"approach": str, "pros": [], "cons": []}
    recommended_approach: str = ""
    complexity: TaskComplexity = TaskComplexity.MODERATE
    estimated_effort: str = "medium"  # "small", "medium", "large", "xl"
    confidence: float = 0.5  # 0.0-1.0
    should_proceed: bool = True
    clarifying_questions: list[str] = field(default_factory=list)
    technical_debt_impact: str = ""
    architecture_impact: str = ""


class EngineeringReasoner:
    """
    The senior engineer brain that reasons about engineering tasks.
    
    This sits BEFORE the planner and makes strategic decisions:
    - Should we do this?
    - What's the right approach?
    - What are the risks?
    - What should we be careful about?
    """
    
    def __init__(self, brain=None, repo_intelligence=None):
        self.brain = brain  # LLM for reasoning
        self.repo_intel = repo_intelligence
        self._reasoning_cache = {}
    
    def reason(self, task: str, context: dict = None) -> EngineeringAnalysis:
        """
        Reason about a task before planning.
        
        Returns strategic analysis that guides planning and execution.
        """
        print(f"[Reasoner] Analyzing task: {task[:60]}...")
        
        analysis = EngineeringAnalysis(task=task, goal=task)
        
        # 1. Understand the goal
        analysis.goal = self._extract_goal(task)
        
        # 2. Classify complexity
        analysis.complexity = self._classify_complexity(task, context)
        print(f"  Complexity: {analysis.complexity.value}")
        
        # 3. Assess risk
        analysis.risks = self._assess_risks(task, context)
        risk_level = max([r["level"] for r in analysis.risks], key=lambda x: x.value) if analysis.risks else RiskLevel.LOW
        print(f"  Risk: {risk_level.value} ({len(analysis.risks)} risks identified)")
        
        # 4. Identify affected systems
        analysis.affected_systems = self._find_affected_systems(task, context)
        if analysis.affected_systems:
            print(f"  Affected: {', '.join(analysis.affected_systems)}")
        
        # 5. Generate alternatives
        analysis.alternatives = self._generate_alternatives(task, context)
        
        # 6. Recommend approach
        analysis.recommended_approach = self._recommend_approach(task, analysis)
        
        # 7. Estimate effort
        analysis.estimated_effort = self._estimate_effort(analysis)
        
        # 8. Calculate confidence
        analysis.confidence = self._calculate_confidence(task, context, analysis)
        print(f"  Confidence: {analysis.confidence:.0%}")
        
        # 9. Generate clarifying questions if needed
        if analysis.confidence < 0.7:
            analysis.clarifying_questions = self._generate_questions(task, analysis)
        
        # 10. Assess architecture impact
        analysis.architecture_impact = self._assess_architecture_impact(task, context)
        
        return analysis
    
    def _extract_goal(self, task: str) -> str:
        """Extract the underlying goal from the task description."""
        task_lower = task.lower()
        
        # Pattern matching for common goals
        if "fix" in task_lower or "bug" in task_lower:
            return "Fix a bug or error"
        elif "add" in task_lower or "create" in task_lower or "implement" in task_lower:
            return "Add new functionality"
        elif "refactor" in task_lower or "improve" in task_lower:
            return "Improve code quality"
        elif "test" in task_lower:
            return "Add test coverage"
        elif "optimize" in task_lower or "performance" in task_lower:
            return "Improve performance"
        elif "security" in task_lower:
            return "Improve security"
        elif "update" in task_lower or "upgrade" in task_lower:
            return "Update dependencies or version"
        else:
            return "General development task"
    
    def _classify_complexity(self, task: str, context: dict = None) -> TaskComplexity:
        """Classify task complexity."""
        task_lower = task.lower()
        
        # Simple indicators
        simple_indicators = ["rename", "fix typo", "update comment", "add log"]
        if any(ind in task_lower for ind in simple_indicators):
            return TaskComplexity.SIMPLE
        
        # Complex indicators
        complex_indicators = ["refactor", "migrate", "architecture", "redesign"]
        if any(ind in task_lower for ind in complex_indicators):
            return TaskComplexity.COMPLEX
        
        # Expert indicators
        expert_indicators = ["distributed", "scale", "performance", "security vulnerability"]
        if any(ind in task_lower for ind in expert_indicators):
            return TaskComplexity.EXPERT
        
        return TaskComplexity.MODERATE
    
    def _assess_risks(self, task: str, context: dict = None) -> list[dict]:
        """Identify potential risks."""
        risks = []
        task_lower = task.lower()
        
        # Database risks
        if any(word in task_lower for word in ["database", "migration", "schema", "sql"]):
            risks.append({
                "risk": "Database changes can cause data loss or downtime",
                "level": RiskLevel.HIGH,
                "mitigation": "Test migrations on copy of production data, have rollback plan"
            })
        
        # Authentication/Security risks
        if any(word in task_lower for word in ["auth", "login", "password", "security", "permission"]):
            risks.append({
                "risk": "Security changes can introduce vulnerabilities or lock out users",
                "level": RiskLevel.CRITICAL,
                "mitigation": "Security review, extensive testing, gradual rollout"
            })
        
        # Payment risks
        if any(word in task_lower for word in ["payment", "billing", "charge", "money"]):
            risks.append({
                "risk": "Payment system errors can cause financial loss",
                "level": RiskLevel.CRITICAL,
                "mitigation": "Extensive testing, audit logging, manual verification"
            })
        
        # API changes
        if any(word in task_lower for word in ["api", "endpoint", "route"]):
            risks.append({
                "risk": "API changes can break client applications",
                "level": RiskLevel.MEDIUM,
                "mitigation": "Version API, maintain backwards compatibility, notify clients"
            })
        
        # Refactoring risks
        if "refactor" in task_lower:
            risks.append({
                "risk": "Refactoring can introduce regressions",
                "level": RiskLevel.MEDIUM,
                "mitigation": "Comprehensive test coverage before refactoring"
            })
        
        # Performance changes
        if any(word in task_lower for word in ["optimize", "performance", "cache"]):
            risks.append({
                "risk": "Performance changes can have unexpected side effects",
                "level": RiskLevel.MEDIUM,
                "mitigation": "Benchmark before and after, test under load"
            })
        
        return risks
    
    def _find_affected_systems(self, task: str, context: dict = None) -> list[str]:
        """Identify which systems/components will be affected."""
        affected = []
        
        # Use repository intelligence if available
        if self.repo_intel and hasattr(self.repo_intel, 'find_concepts_for_task'):
            concepts = self.repo_intel.find_concepts_for_task(task)
            affected.extend([c.name for c in concepts])
        
        # Pattern-based detection
        task_lower = task.lower()
        system_keywords = {
            "database": ["Database", "Models", "ORM"],
            "api": ["API Layer", "Routes", "Controllers"],
            "frontend": ["Frontend", "UI", "Views"],
            "auth": ["Authentication", "Authorization", "Security"],
            "cache": ["Cache Layer", "Redis"],
            "queue": ["Message Queue", "Background Jobs"],
            "email": ["Email Service", "Notifications"],
        }
        
        for keyword, systems in system_keywords.items():
            if keyword in task_lower:
                affected.extend(systems)
        
        return list(set(affected))
    
    def _generate_alternatives(self, task: str, context: dict = None) -> list[dict]:
        """Generate alternative approaches."""
        alternatives = []
        task_lower = task.lower()
        
        # For refactoring
        if "refactor" in task_lower:
            alternatives.append({
                "approach": "Incremental refactoring with feature flags",
                "pros": ["Lower risk", "Can rollback easily", "Continuous deployment"],
                "cons": ["Takes longer", "More complex code temporarily"]
            })
            alternatives.append({
                "approach": "Complete rewrite in parallel",
                "pros": ["Clean slate", "Modern patterns"],
                "cons": ["High risk", "Duplicate effort", "Long deployment gap"]
            })
        
        # For new features
        if any(word in task_lower for word in ["add", "implement", "create"]):
            alternatives.append({
                "approach": "MVP implementation with minimal features",
                "pros": ["Fast to market", "Get user feedback early"],
                "cons": ["May need rework later"]
            })
            alternatives.append({
                "approach": "Full-featured implementation",
                "pros": ["Complete solution", "Less rework"],
                "cons": ["Takes longer", "Higher complexity"]
            })
        
        return alternatives
    
    def _recommend_approach(self, task: str, analysis: EngineeringAnalysis) -> str:
        """Recommend the best approach based on analysis."""
        # High risk -> more careful approach
        has_high_risk = any(r["level"] in [RiskLevel.HIGH, RiskLevel.CRITICAL] for r in analysis.risks)
        
        if has_high_risk:
            return "Incremental approach with extensive testing and rollback plan"
        elif analysis.complexity == TaskComplexity.EXPERT:
            return "Research and prototype first, then implement with expert review"
        elif analysis.complexity == TaskComplexity.SIMPLE:
            return "Direct implementation with basic testing"
        else:
            return "Standard development workflow with testing and code review"
    
    def _estimate_effort(self, analysis: EngineeringAnalysis) -> str:
        """Estimate effort based on complexity and risks."""
        complexity_effort = {
            TaskComplexity.TRIVIAL: "small",
            TaskComplexity.SIMPLE: "small",
            TaskComplexity.MODERATE: "medium",
            TaskComplexity.COMPLEX: "large",
            TaskComplexity.EXPERT: "xl"
        }
        
        base_effort = complexity_effort[analysis.complexity]
        
        # Increase effort for high-risk tasks
        has_critical_risk = any(r["level"] == RiskLevel.CRITICAL for r in analysis.risks)
        if has_critical_risk and base_effort in ["small", "medium"]:
            return "medium" if base_effort == "small" else "large"
        
        return base_effort
    
    def _calculate_confidence(self, task: str, context: dict = None, analysis: EngineeringAnalysis = None) -> float:
        """Calculate confidence score (0.0-1.0)."""
        confidence = 0.5  # Base confidence
        
        # Increase confidence if we have context
        if context and context.get("files"):
            confidence += 0.2
        
        # Increase confidence for simple tasks
        if analysis and analysis.complexity in [TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE]:
            confidence += 0.2
        
        # Decrease confidence for complex tasks
        if analysis and analysis.complexity == TaskComplexity.EXPERT:
            confidence -= 0.2
        
        # Decrease confidence if we don't understand affected systems
        if analysis and not analysis.affected_systems:
            confidence -= 0.1
        
        # Decrease confidence for critical risks
        if analysis and any(r["level"] == RiskLevel.CRITICAL for r in analysis.risks):
            confidence -= 0.1
        
        return max(0.1, min(1.0, confidence))
    
    def _generate_questions(self, task: str, analysis: EngineeringAnalysis) -> list[str]:
        """Generate clarifying questions when confidence is low."""
        questions = []
        
        if not analysis.affected_systems:
            questions.append("Which specific files or modules should be modified?")
        
        if analysis.complexity == TaskComplexity.EXPERT:
            questions.append("Do you have specific performance targets or constraints?")
        
        if any(r["level"] == RiskLevel.CRITICAL for r in analysis.risks):
            questions.append("What is the acceptable downtime/risk tolerance for this change?")
        
        if "database" in task.lower() and "migration" in task.lower():
            questions.append("Should this migration be reversible? Do you have a backup?")
        
        return questions
    
    def _assess_architecture_impact(self, task: str, context: dict = None) -> str:
        """Assess how this task impacts overall architecture."""
        task_lower = task.lower()
        
        if "refactor" in task_lower or "redesign" in task_lower:
            return "This task will modify the architecture. Consider documenting design decisions."
        elif "add" in task_lower and "service" in task_lower:
            return "Adding a new service increases system complexity. Document interfaces and dependencies."
        elif "database" in task_lower or "schema" in task_lower:
            return "Database changes affect data layer. Ensure backwards compatibility."
        elif "api" in task_lower and ("change" in task_lower or "modify" in task_lower):
            return "API changes affect clients. Consider versioning strategy."
        else:
            return "Minimal architecture impact expected."
