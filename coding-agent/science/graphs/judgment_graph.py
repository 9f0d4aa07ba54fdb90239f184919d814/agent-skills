"""
Engineering Judgment Graph - Decision DNA as an Interconnected Graph

Problem → Evidence → Decision → Outcome → Pattern → Related Decisions
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
from enum import Enum
import hashlib


class ProblemCategory(Enum):
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"


class OutcomeType(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ROLLBACK = "rollback"


@dataclass
class ProblemNode:
    node_id: str
    category: ProblemCategory
    signature: str
    context: Dict[str, Any]
    similar_problems: Set[str] = field(default_factory=set)
    decisions_made: Set[str] = field(default_factory=set)
    occurrence_count: int = 1


@dataclass
class DecisionNode:
    node_id: str
    problem_id: str
    choice: str
    reasoning: str
    alternatives: List[str]
    evidence_used: Set[str] = field(default_factory=set)
    outcome_id: Optional[str] = None
    counterfactuals: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    similar_decisions: Set[str] = field(default_factory=set)


@dataclass
class OutcomeNode:
    node_id: str
    decision_id: str
    outcome_type: OutcomeType
    success_metrics: Dict[str, float]
    lessons: List[str]


@dataclass
class PatternNode:
    node_id: str
    pattern_name: str
    problem_pattern: Dict[str, Any]
    solution_pattern: Dict[str, Any]
    success_rate: float = 0.0
    times_applied: int = 0
    confidence: float = 0.0


class EngineeringJudgmentGraph:
    """The complete graph of engineering decisions"""
    
    def __init__(self):
        self.problems: Dict[str, ProblemNode] = {}
        self.decisions: Dict[str, DecisionNode] = {}
        self.outcomes: Dict[str, OutcomeNode] = {}
        self.patterns: Dict[str, PatternNode] = {}
    
    def record_decision(self, problem: Dict, evidence: List, decision: Dict, alternatives: List) -> str:
        problem_id = self._get_or_create_problem(problem)
        decision_id = f"dec_{hashlib.sha256(str(decision).encode()).hexdigest()[:16]}"
        
        self.decisions[decision_id] = DecisionNode(
            node_id=decision_id,
            problem_id=problem_id,
            choice=decision.get("choice", ""),
            reasoning=decision.get("reasoning", ""),
            alternatives=alternatives,
            confidence=decision.get("confidence", 0.0)
        )
        
        return decision_id
    
    def record_outcome(self, decision_id: str, outcome: Dict) -> str:
        outcome_id = f"out_{hashlib.sha256(str(outcome).encode()).hexdigest()[:16]}"
        
        self.outcomes[outcome_id] = OutcomeNode(
            node_id=outcome_id,
            decision_id=decision_id,
            outcome_type=OutcomeType(outcome.get("type", "success")),
            success_metrics=outcome.get("metrics", {}),
            lessons=outcome.get("lessons", [])
        )
        
        if decision_id in self.decisions:
            self.decisions[decision_id].outcome_id = outcome_id
        
        return outcome_id
    
    def add_counterfactual(self, decision_id: str, alternative: str, estimated_outcome: Dict, confidence: float):
        if decision_id in self.decisions:
            self.decisions[decision_id].counterfactuals.append({
                "alternative": alternative,
                "estimated_outcome": estimated_outcome,
                "confidence": confidence
            })
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_problems": len(self.problems),
            "total_decisions": len(self.decisions),
            "total_outcomes": len(self.outcomes),
            "total_patterns": len(self.patterns)
        }
    
    def _get_or_create_problem(self, problem: Dict) -> str:
        signature = str(problem)
        problem_id = f"prob_{hashlib.sha256(signature.encode()).hexdigest()[:16]}"
        
        if problem_id not in self.problems:
            self.problems[problem_id] = ProblemNode(
                node_id=problem_id,
                category=ProblemCategory.DEBUGGING,
                signature=signature,
                context=problem
            )
        
        return problem_id
