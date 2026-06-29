"""
Decision Provenance System

Every engineering decision should answer:
- WHY was this decision made?
- What EVIDENCE was considered?
- What ALTERNATIVES were evaluated?
- What TRADEOFFS were analyzed?
- What was CHOSEN?
- What was the OUTCOME?

Six months later, the system can explain why a design exists.
This is far more valuable than storing chat logs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import json


class DecisionType(Enum):
    """Types of engineering decisions"""
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    REFACTORING = "refactoring"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    DEPENDENCY = "dependency"


class DecisionOutcome(Enum):
    """How did the decision turn out?"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    REVERTED = "reverted"
    UNKNOWN = "unknown"


@dataclass
class Evidence:
    """A single piece of evidence"""
    source: str  # "code_analysis", "documentation", "metrics", "tests"
    description: str
    data: Dict[str, Any]
    confidence: float  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "description": self.description,
            "data": self.data,
            "confidence": self.confidence
        }


@dataclass
class Alternative:
    """A possible solution that was considered"""
    name: str
    description: str
    pros: List[str]
    cons: List[str]
    estimated_effort: str  # "low", "medium", "high"
    estimated_risk: str    # "low", "medium", "high"
    rejected_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "pros": self.pros,
            "cons": self.cons,
            "estimated_effort": self.estimated_effort,
            "estimated_risk": self.estimated_risk,
            "rejected_reason": self.rejected_reason
        }


@dataclass
class Tradeoff:
    """A tradeoff that was analyzed"""
    dimension: str  # "performance vs maintainability", "speed vs safety"
    chosen_value: str
    alternative_value: str
    justification: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "chosen_value": self.chosen_value,
            "alternative_value": self.alternative_value,
            "justification": self.justification
        }


@dataclass
class DecisionSignals:
    """Four key signals that influence decisions"""
    confidence: float      # "I think this is correct" (0.0 to 1.0)
    uncertainty: float     # "I don't have enough evidence" (0.0 to 1.0)
    risk: float           # "This could cause damage" (0.0 to 1.0)
    importance: float     # "This decision matters" (0.0 to 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "risk": self.risk,
            "importance": self.importance
        }


@dataclass
class DecisionRecord:
    """
    Complete provenance of an engineering decision.
    
    This is what gets stored in long-term memory.
    NOT the chat conversation.
    """
    
    # Identity
    decision_id: str
    timestamp: str
    decision_type: DecisionType
    
    # Context
    goal: str  # What were we trying to achieve?
    context: Dict[str, Any]  # Repository state, affected files, etc.
    
    # Analysis
    evidence: List[Evidence]
    alternatives: List[Alternative]
    tradeoffs: List[Tradeoff]
    
    # Decision
    chosen_solution: str
    reasoning: str
    signals: DecisionSignals
    
    # Outcome (filled in later)
    outcome: DecisionOutcome = DecisionOutcome.UNKNOWN
    outcome_description: Optional[str] = None
    outcome_timestamp: Optional[str] = None
    lessons_learned: List[str] = field(default_factory=list)
    
    # Metadata
    affected_files: List[str] = field(default_factory=list)
    affected_systems: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "decision_type": self.decision_type.value,
            "goal": self.goal,
            "context": self.context,
            "evidence": [e.to_dict() for e in self.evidence],
            "alternatives": [a.to_dict() for a in self.alternatives],
            "tradeoffs": [t.to_dict() for t in self.tradeoffs],
            "chosen_solution": self.chosen_solution,
            "reasoning": self.reasoning,
            "signals": self.signals.to_dict(),
            "outcome": self.outcome.value,
            "outcome_description": self.outcome_description,
            "outcome_timestamp": self.outcome_timestamp,
            "lessons_learned": self.lessons_learned,
            "affected_files": self.affected_files,
            "affected_systems": self.affected_systems,
            "tags": self.tags
        }
    
    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DecisionRecord':
        """Deserialize from dictionary"""
        return cls(
            decision_id=data["decision_id"],
            timestamp=data["timestamp"],
            decision_type=DecisionType(data["decision_type"]),
            goal=data["goal"],
            context=data["context"],
            evidence=[Evidence(**e) for e in data["evidence"]],
            alternatives=[Alternative(**a) for a in data["alternatives"]],
            tradeoffs=[Tradeoff(**t) for t in data["tradeoffs"]],
            chosen_solution=data["chosen_solution"],
            reasoning=data["reasoning"],
            signals=DecisionSignals(**data["signals"]),
            outcome=DecisionOutcome(data["outcome"]),
            outcome_description=data.get("outcome_description"),
            outcome_timestamp=data.get("outcome_timestamp"),
            lessons_learned=data.get("lessons_learned", []),
            affected_files=data.get("affected_files", []),
            affected_systems=data.get("affected_systems", []),
            tags=data.get("tags", [])
        )


class DecisionProvenanceStore:
    """
    Store and query decision provenance.
    
    This is the foundation of the learning system.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self.decisions: Dict[str, DecisionRecord] = {}
    
    def record_decision(self, decision: DecisionRecord):
        """Store a decision"""
        self.decisions[decision.decision_id] = decision
        if self.storage_path:
            self._persist(decision)
    
    def update_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        description: str,
        lessons_learned: List[str] = None
    ):
        """Update decision outcome after execution"""
        if decision_id not in self.decisions:
            raise ValueError(f"Decision not found: {decision_id}")
        
        decision = self.decisions[decision_id]
        decision.outcome = outcome
        decision.outcome_description = description
        decision.outcome_timestamp = datetime.utcnow().isoformat()
        if lessons_learned:
            decision.lessons_learned.extend(lessons_learned)
        
        if self.storage_path:
            self._persist(decision)
    
    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        """Retrieve a decision by ID"""
        return self.decisions.get(decision_id)
    
    def query(
        self,
        decision_type: Optional[DecisionType] = None,
        affected_file: Optional[str] = None,
        affected_system: Optional[str] = None,
        outcome: Optional[DecisionOutcome] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[DecisionRecord]:
        """Query decisions by criteria"""
        results = []
        
        for decision in self.decisions.values():
            # Filter by type
            if decision_type and decision.decision_type != decision_type:
                continue
            
            # Filter by affected file
            if affected_file and affected_file not in decision.affected_files:
                continue
            
            # Filter by affected system
            if affected_system and affected_system not in decision.affected_systems:
                continue
            
            # Filter by outcome
            if outcome and decision.outcome != outcome:
                continue
            
            # Filter by tags
            if tags and not any(tag in decision.tags for tag in tags):
                continue
            
            results.append(decision)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_lessons_for_context(self, context: Dict[str, Any]) -> List[str]:
        """
        Given current context, find relevant lessons from past decisions.
        
        This is how the system learns from history.
        """
        lessons = []
        
        # Find similar decisions
        similar_decisions = self.query(
            decision_type=context.get("decision_type"),
            affected_system=context.get("affected_system"),
            limit=10
        )
        
        for decision in similar_decisions:
            if decision.lessons_learned:
                lessons.extend(decision.lessons_learned)
        
        return lessons
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about decisions"""
        total = len(self.decisions)
        if total == 0:
            return {}
        
        outcomes = {}
        types = {}
        
        for decision in self.decisions.values():
            outcomes[decision.outcome.value] = outcomes.get(decision.outcome.value, 0) + 1
            types[decision.decision_type.value] = types.get(decision.decision_type.value, 0) + 1
        
        return {
            "total_decisions": total,
            "outcomes": outcomes,
            "types": types,
            "success_rate": outcomes.get("success", 0) / total if total > 0 else 0
        }
    
    def _persist(self, decision: DecisionRecord):
        """Persist decision to storage"""
        if not self.storage_path:
            return
        
        import os
        os.makedirs(self.storage_path, exist_ok=True)
        
        file_path = os.path.join(self.storage_path, f"{decision.decision_id}.json")
        with open(file_path, 'w') as f:
            f.write(decision.to_json())


# Global provenance store
_provenance_store = DecisionProvenanceStore()


def get_provenance_store() -> DecisionProvenanceStore:
    """Get global provenance store"""
    return _provenance_store


def record_decision(
    goal: str,
    decision_type: DecisionType,
    context: Dict[str, Any],
    evidence: List[Evidence],
    alternatives: List[Alternative],
    tradeoffs: List[Tradeoff],
    chosen_solution: str,
    reasoning: str,
    signals: DecisionSignals,
    affected_files: List[str] = None,
    affected_systems: List[str] = None,
    tags: List[str] = None
) -> str:
    """
    Convenience function to record a decision.
    Returns decision_id.
    """
    import uuid
    
    decision = DecisionRecord(
        decision_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat(),
        decision_type=decision_type,
        goal=goal,
        context=context,
        evidence=evidence,
        alternatives=alternatives,
        tradeoffs=tradeoffs,
        chosen_solution=chosen_solution,
        reasoning=reasoning,
        signals=signals,
        affected_files=affected_files or [],
        affected_systems=affected_systems or [],
        tags=tags or []
    )
    
    store = get_provenance_store()
    store.record_decision(decision)
    
    return decision.decision_id
