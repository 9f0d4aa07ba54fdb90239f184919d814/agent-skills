"""
DECISION ENGINE

The cognitive core that decides WHAT to do at each step.

This is the missing layer between reasoning and execution.
Instead of the planner making every decision, the Decision Engine evaluates:
- Should we search for more context?
- Should we ask the user for clarification?
- Should we simulate before executing?
- Should we proceed or stop?
- Which strategy should we use?

This is what separates reactive agents from intelligent engineers.
"""

import time
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class DecisionType(Enum):
    """Types of decisions the engine can make."""
    PROCEED = "proceed"
    GATHER_MORE_CONTEXT = "gather_more_context"
    ASK_USER = "ask_user"
    SIMULATE_FIRST = "simulate_first"
    SPLIT_TASK = "split_task"
    DELEGATE = "delegate"
    STOP = "stop"
    RETRY_DIFFERENT_APPROACH = "retry_different_approach"


@dataclass
class Evidence:
    """Evidence supporting a decision."""
    type: str  # "performance_data", "test_results", "similar_task", etc.
    description: str
    confidence: float  # 0.0-1.0
    source: str
    data: dict = field(default_factory=dict)


@dataclass
class Decision:
    """A decision made by the engine."""
    decision_type: DecisionType
    confidence: float  # 0.0-1.0
    reasoning: str
    evidence: list[Evidence] = field(default_factory=list)
    alternatives: list[dict] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DecisionEngine:
    """
    The cognitive core that makes strategic decisions.
    
    This sits between reasoning and execution, deciding:
    - What information do we need?
    - What should we do next?
    - How should we proceed?
    - When should we stop?
    """
    
    def __init__(self, reasoner=None, repo_intelligence=None, knowledge_graph=None):
        self.reasoner = reasoner
        self.repo_intel = repo_intelligence
        self.knowledge_graph = knowledge_graph
        self._decision_history: list[Decision] = []
    
    def decide(self, task: str, context: dict = None, analysis=None) -> Decision:
        """
        Make a strategic decision about how to proceed.
        
        Args:
            task: The task to accomplish
            context: Current context (files, concepts, etc.)
            analysis: EngineeringAnalysis from reasoner (if available)
        
        Returns:
            Decision object with recommended action
        """
        print(f"[DecisionEngine] Evaluating task: {task[:60]}...")
        
        # Gather evidence
        evidence = self._gather_evidence(task, context, analysis)
        
        # Calculate confidence
        confidence = self._calculate_confidence(evidence, context, analysis)
        print(f"  Confidence: {confidence:.0%}")
        
        # Make decision based on confidence and evidence
        if confidence < 0.3:
            decision = self._decide_insufficient_info(task, evidence)
        elif confidence < 0.6:
            decision = self._decide_needs_clarification(task, evidence, analysis)
        elif analysis and self._has_critical_risk(analysis):
            decision = self._decide_simulate_first(task, evidence, analysis)
        elif self._should_split_task(task, context, analysis):
            decision = self._decide_split_task(task, evidence)
        else:
            decision = self._decide_proceed(task, evidence, analysis)
        
        # Store decision
        self._decision_history.append(decision)
        
        print(f"  Decision: {decision.decision_type.value}")
        print(f"  Reasoning: {decision.reasoning[:100]}...")
        
        return decision
    
    def _gather_evidence(self, task: str, context: dict = None, analysis=None) -> list[Evidence]:
        """Gather evidence to support decision-making."""
        evidence = []
        
        # Evidence from context
        if context:
            if context.get("files"):
                evidence.append(Evidence(
                    type="context_files",
                    description=f"Found {len(context['files'])} relevant files",
                    confidence=0.7,
                    source="context",
                    data={"file_count": len(context["files"])}
                ))
            
            if context.get("concepts"):
                evidence.append(Evidence(
                    type="concepts_identified",
                    description=f"Identified {len(context['concepts'])} relevant concepts",
                    confidence=0.8,
                    source="repository_intelligence",
                    data={"concepts": context["concepts"]}
                ))
        
        # Evidence from analysis
        if analysis:
            if analysis.complexity:
                evidence.append(Evidence(
                    type="complexity_assessment",
                    description=f"Task complexity: {analysis.complexity.value}",
                    confidence=0.9,
                    source="engineering_reasoner",
                    data={"complexity": analysis.complexity.value}
                ))
            
            if analysis.risks:
                evidence.append(Evidence(
                    type="risk_assessment",
                    description=f"Identified {len(analysis.risks)} risks",
                    confidence=0.8,
                    source="engineering_reasoner",
                    data={"risk_count": len(analysis.risks), "risks": analysis.risks}
                ))
        
        # Evidence from repository intelligence
        if self.repo_intel:
            architecture = self.repo_intel.architecture
            if architecture:
                evidence.append(Evidence(
                    type="architecture_understanding",
                    description=f"Architecture: {architecture.pattern}, Frameworks: {', '.join(architecture.frameworks[:3])}",
                    confidence=0.9,
                    source="repository_intelligence",
                    data={"pattern": architecture.pattern, "frameworks": architecture.frameworks}
                ))
        
        return evidence
    
    def _calculate_confidence(self, evidence: list[Evidence], context: dict = None, analysis=None) -> float:
        """Calculate overall confidence based on evidence."""
        if not evidence:
            return 0.2  # Very low confidence with no evidence
        
        # Weight different evidence types
        weights = {
            "context_files": 0.3,
            "concepts_identified": 0.3,
            "complexity_assessment": 0.2,
            "risk_assessment": 0.2,
            "architecture_understanding": 0.2,
        }
        
        total_confidence = 0.0
        total_weight = 0.0
        
        for ev in evidence:
            weight = weights.get(ev.type, 0.1)
            total_confidence += ev.confidence * weight
            total_weight += weight
        
        base_confidence = total_confidence / total_weight if total_weight > 0 else 0.5
        
        # Adjust based on analysis
        if analysis:
            # Reduce confidence for high complexity
            if hasattr(analysis, 'complexity'):
                from brain.engineering_reasoner import TaskComplexity
                if analysis.complexity == TaskComplexity.EXPERT:
                    base_confidence *= 0.7
                elif analysis.complexity == TaskComplexity.COMPLEX:
                    base_confidence *= 0.85
            
            # Reduce confidence for critical risks
            if hasattr(analysis, 'risks'):
                from brain.engineering_reasoner import RiskLevel
                has_critical = any(r.get("level") == RiskLevel.CRITICAL for r in analysis.risks)
                if has_critical:
                    base_confidence *= 0.6
        
        return max(0.0, min(1.0, base_confidence))
    
    def _has_critical_risk(self, analysis) -> bool:
        """Check if analysis contains critical risks."""
        if not hasattr(analysis, 'risks'):
            return False
        
        from brain.engineering_reasoner import RiskLevel
        return any(r.get("level") == RiskLevel.CRITICAL for r in analysis.risks)
    
    def _should_split_task(self, task: str, context: dict = None, analysis=None) -> bool:
        """Determine if task should be split into subtasks."""
        task_lower = task.lower()
        
        # Large refactorings should be split
        if "refactor" in task_lower and ("entire" in task_lower or "all" in task_lower):
            return True
        
        # Complex migrations should be split
        if "migrate" in task_lower and "database" in task_lower:
            return True
        
        # Multiple features in one task
        if task_lower.count(" and ") > 2:
            return True
        
        # Analysis suggests high complexity
        if analysis and hasattr(analysis, 'complexity'):
            from brain.engineering_reasoner import TaskComplexity
            if analysis.complexity == TaskComplexity.EXPERT:
                return True
        
        return False
    
    def _decide_insufficient_info(self, task: str, evidence: list[Evidence]) -> Decision:
        """Decide to gather more context when confidence is very low."""
        return Decision(
            decision_type=DecisionType.GATHER_MORE_CONTEXT,
            confidence=0.9,  # High confidence in this decision
            reasoning="Insufficient information to proceed confidently. Need to gather more context about the codebase.",
            evidence=evidence,
            recommended_actions=[
                "Scan repository for relevant files",
                "Build knowledge graph of affected components",
                "Identify similar patterns in codebase",
                "Check documentation and comments"
            ]
        )
    
    def _decide_needs_clarification(self, task: str, evidence: list[Evidence], analysis=None) -> Decision:
        """Decide to ask user for clarification."""
        questions = []
        
        if analysis and hasattr(analysis, 'clarifying_questions'):
            questions = analysis.clarifying_questions
        else:
            questions = [
                "Which specific files or modules should be modified?",
                "What is the expected behavior after this change?",
                "Are there any constraints or requirements I should know about?"
            ]
        
        return Decision(
            decision_type=DecisionType.ASK_USER,
            confidence=0.85,
            reasoning="Task is ambiguous or missing critical information. User clarification needed before proceeding.",
            evidence=evidence,
            recommended_actions=questions,
            metadata={"questions": questions}
        )
    
    def _decide_simulate_first(self, task: str, evidence: list[Evidence], analysis) -> Decision:
        """Decide to simulate before executing due to high risk."""
        risks = [r["risk"] for r in analysis.risks] if hasattr(analysis, 'risks') else []
        
        return Decision(
            decision_type=DecisionType.SIMULATE_FIRST,
            confidence=0.95,
            reasoning="Task involves critical systems or high risk. Simulation required before execution.",
            evidence=evidence,
            risks=risks,
            recommended_actions=[
                "Run static analysis on proposed changes",
                "Simulate impact on affected systems",
                "Verify rollback capability",
                "Run comprehensive test suite",
                "Generate detailed execution plan for review"
            ]
        )
    
    def _decide_split_task(self, task: str, evidence: list[Evidence]) -> Decision:
        """Decide to split task into subtasks."""
        return Decision(
            decision_type=DecisionType.SPLIT_TASK,
            confidence=0.8,
            reasoning="Task is too complex to execute in one step. Should be broken into smaller, manageable subtasks.",
            evidence=evidence,
            recommended_actions=[
                "Decompose into independent subtasks",
                "Execute subtasks incrementally",
                "Verify each subtask before proceeding",
                "Maintain rollback capability at each step"
            ]
        )
    
    def _decide_proceed(self, task: str, evidence: list[Evidence], analysis=None) -> Decision:
        """Decide to proceed with execution."""
        actions = ["Create detailed execution plan", "Execute planned changes", "Verify results"]
        
        # Add extra verification for medium-risk tasks
        if analysis and hasattr(analysis, 'risks') and analysis.risks:
            actions.append("Run extra verification due to identified risks")
        
        return Decision(
            decision_type=DecisionType.PROCEED,
            confidence=0.9,
            reasoning="Sufficient information and confidence to proceed with implementation.",
            evidence=evidence,
            recommended_actions=actions
        )
    
    def get_decision_history(self) -> list[Decision]:
        """Get history of decisions made."""
        return self._decision_history
    
    def analyze_decision_quality(self) -> dict:
        """Analyze quality of past decisions."""
        if not self._decision_history:
            return {"total_decisions": 0}
        
        decision_types = {}
        avg_confidence = sum(d.confidence for d in self._decision_history) / len(self._decision_history)
        
        for d in self._decision_history:
            decision_types[d.decision_type.value] = decision_types.get(d.decision_type.value, 0) + 1
        
        return {
            "total_decisions": len(self._decision_history),
            "average_confidence": avg_confidence,
            "decision_distribution": decision_types,
            "most_common": max(decision_types, key=decision_types.get) if decision_types else None
        }
