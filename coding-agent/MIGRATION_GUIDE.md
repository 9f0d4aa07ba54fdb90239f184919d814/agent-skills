# Migration Guide: From Engines to Subsystems

## The Problem

The codebase was heading toward "engine proliferation":
- Goal Engine
- Decision Engine
- Evidence Engine
- Hypothesis Engine
- Strategy Engine
- Reflection Engine
- Confidence Engine
- Repository Intelligence Engine
- Knowledge Graph Engine
- Simulation Engine
- ...40 more engines in the future

This scales poorly.

## The Solution

Five core subsystems with clear boundaries:

```
brain/
├── cognitive/        # Thinking processes
├── knowledge/        # Understanding
├── policy/          # Governance
├── execution/       # Action
└── learning/        # Improvement

platform/            # Infrastructure
```

---

## Migration Steps

### Step 1: Create New Structure

```bash
mkdir brain/cognitive
mkdir brain/knowledge
mkdir brain/execution
mkdir brain/learning
mkdir brain/policy
mkdir platform
```

### Step 2: Move Existing Files

**Cognitive System** (thinking processes):
```
brain/goal_engine.py          → brain/cognitive/goal.py
brain/decision_engine.py      → brain/cognitive/decision.py
brain/engineering_reasoner.py → brain/cognitive/reasoning.py
```

**Knowledge System** (understanding):
```
brain/repository_intelligence.py → brain/knowledge/repository_intelligence.py
```

**Policy System** (governance):
```
(new) brain/policy/engine.py
```

**Platform System** (infrastructure):
```
kernel/                       → platform/kernel/
capabilities/                 → platform/capabilities/
```

### Step 3: Update Imports

**Before**:
```python
from brain.goal_engine import GoalEngine
from brain.decision_engine import DecisionEngine
from brain.engineering_reasoner import EngineeringReasoner
```

**After**:
```python
from brain.cognitive.goal import GoalEngine
from brain.cognitive.decision import DecisionEngine
from brain.cognitive.reasoning import EngineeringReasoner
```

### Step 4: Create Subsystem APIs

Each subsystem needs a clean API in `__init__.py`:

**brain/cognitive/__init__.py**:
```python
"""
Cognitive System - Think like a senior engineer

Processes:
- Goal Formation: Vague request → structured engineering goal
- Hypothesis: What might need to change?
- Evidence: Gather data before deciding
- Reasoning: Analyze complexity, risks, systems
- Decision: Choose action (proceed/gather/ask/simulate)
- Strategy: Plan alternatives with tradeoffs
- Reflection: Learn from outcomes
"""

from .goal import GoalEngine
from .decision import DecisionEngine
from .reasoning import EngineeringReasoner

__all__ = ['GoalEngine', 'DecisionEngine', 'EngineeringReasoner']
```

**brain/knowledge/__init__.py**:
```python
"""
Knowledge System - Understand software deeply

Components:
- Repository Intelligence: Conceptual understanding
- Knowledge Graphs: 9 specialized graphs
- Semantic Search: Find by meaning
- World Model: Mental model of system
- Engineering Memory: Decision history
"""

from .repository_intelligence import RepositoryIntelligence

__all__ = ['RepositoryIntelligence']
```

**brain/policy/__init__.py**:
```python
"""
Policy System - Governance for autonomous execution

Every decision flows through policies:
    task → check_policies() → allowed? → proceed/block

Categories:
- Security: Input validation, secrets, commands
- Coding Standards: Style, patterns, complexity
- Architecture: Component boundaries, dependencies
- Performance: Resource usage, complexity limits
- Licensing: OSS compliance, legal constraints
"""

from .engine import (
    PolicyEngine,
    PolicyVerdict,
    PolicyResult,
    get_policy_engine,
    initialize_default_policies
)

__all__ = [
    'PolicyEngine',
    'PolicyVerdict', 
    'PolicyResult',
    'get_policy_engine',
    'initialize_default_policies'
]
```

**brain/execution/__init__.py**:
```python
"""
Execution System - Change the repository safely

Components:
- Task Planner: Break goals into tasks
- DAG Builder: Dependency graph
- Scheduler: Order and parallelization
- Worker Pool: Concurrent execution
- Tool Runtime: Safe tool execution
- Verification: Check results
- Rollback: Undo on failure
"""

# To be populated as execution components are created
__all__ = []
```

**brain/learning/__init__.py**:
```python
"""
Learning System - Improve over time

Components:
- Reflection: Analyze completed tasks
- Pattern Extraction: Identify reusable solutions
- Skill Builder: Improve capabilities
- Memory Manager: Store structured decisions
- Decision Model: Predict outcomes
- Probability Calibration: Improve confidence
"""

# To be populated as learning components are created
__all__ = []
```

### Step 5: Update Main Brain

**brain/core.py** should orchestrate subsystems:

```python
from brain.cognitive import GoalEngine, DecisionEngine, EngineeringReasoner
from brain.knowledge import RepositoryIntelligence
from brain.policy import get_policy_engine, PolicyVerdict
from brain.provenance import record_decision, DecisionType, DecisionSignals

class Brain:
    """
    Orchestrates all subsystems.
    
    Flow:
        User Request
        ↓
        Cognitive System (understand goal)
        ↓
        Knowledge System (gather context)
        ↓
        Policy System (check governance)
        ↓
        Execution System (make changes)
        ↓
        Learning System (improve)
    """
    
    def __init__(self):
        # Cognitive
        self.goal_engine = GoalEngine()
        self.decision_engine = DecisionEngine()
        self.reasoning_engine = EngineeringReasoner()
        
        # Knowledge
        self.repo_intelligence = RepositoryIntelligence()
        
        # Policy
        self.policy_engine = get_policy_engine()
        
        # (Execution and Learning to be added)
    
    def process_request(self, user_request: str, context: dict) -> dict:
        """
        Main entry point.
        
        Returns decision with provenance.
        """
        # 1. Cognitive: Form goal
        goal = self.goal_engine.form_goal(user_request, context)
        
        # 2. Knowledge: Gather evidence
        repo_analysis = self.repo_intelligence.analyze(context.get('repository_path'))
        
        # 3. Cognitive: Reason about task
        reasoning = self.reasoning_engine.reason(goal, repo_analysis)
        
        # 4. Cognitive: Make decision
        decision = self.decision_engine.decide(goal, reasoning)
        
        # 5. Policy: Check governance
        policy_result = self.policy_engine.evaluate({
            'task_type': decision.action_type,
            'files': decision.affected_files,
            'code_changes': decision.code_changes
        })
        
        if not policy_result.allowed:
            return {
                'allowed': False,
                'reason': 'Policy violation',
                'violations': policy_result.violations
            }
        
        # 6. Provenance: Record decision
        decision_id = record_decision(
            goal=goal.description,
            decision_type=DecisionType.IMPLEMENTATION,
            context=context,
            evidence=reasoning.evidence,
            alternatives=reasoning.alternatives,
            tradeoffs=reasoning.tradeoffs,
            chosen_solution=decision.solution,
            reasoning=decision.reasoning,
            signals=DecisionSignals(
                confidence=decision.confidence,
                uncertainty=decision.uncertainty,
                risk=decision.risk,
                importance=decision.importance
            ),
            affected_files=decision.affected_files
        )
        
        return {
            'allowed': True,
            'decision': decision,
            'decision_id': decision_id,
            'policy_warnings': policy_result.warnings
        }
```

### Step 6: Update Tests

Move tests to match new structure:

```
tests/
├── cognitive/
│   ├── test_goal.py
│   ├── test_decision.py
│   └── test_reasoning.py
├── knowledge/
│   └── test_repository_intelligence.py
├── policy/
│   └── test_engine.py
├── execution/
├── learning/
└── platform/
    ├── test_kernel.py
    └── test_event_bus.py
```

---

## Benefits of This Architecture

### 1. Clear Boundaries
Each subsystem has one responsibility:
- Cognitive: Think
- Knowledge: Understand  
- Policy: Govern
- Execution: Act
- Learning: Improve
- Platform: Infrastructure

### 2. Extensibility
Add new capabilities without core changes:
- New cognitive process? Add to `cognitive/`
- New knowledge source? Add to `knowledge/`
- New policy? Add to `policy/`

### 3. Testability
Test each subsystem independently:
```python
# Test cognitive system without knowledge system
def test_decision_engine():
    engine = DecisionEngine()
    decision = engine.decide(mock_goal, mock_reasoning)
    assert decision.action == "proceed"
```

### 4. Maintainability
Finding code is obvious:
- "Where is policy enforcement?" → `brain/policy/`
- "Where is goal formation?" → `brain/cognitive/goal.py`
- "Where are knowledge graphs?" → `brain/knowledge/graphs/`

### 5. Scalability
No more engine proliferation:
- Need evidence gathering? Add `cognitive/evidence.py`
- Need simulation? Add `execution/simulation.py`
- Need pattern extraction? Add `learning/patterns.py`

All within five stable subsystems.

---

## Migration Checklist

### Phase 1: Structure
- [ ] Create five subsystem directories
- [ ] Move existing files to new locations
- [ ] Create `__init__.py` for each subsystem
- [ ] Update all imports across codebase

### Phase 2: Integration
- [ ] Update `brain/core.py` to orchestrate subsystems
- [ ] Add policy checks to execution flow
- [ ] Add decision provenance recording
- [ ] Add subsystem integration tests

### Phase 3: Documentation
- [ ] Update README with new structure
- [ ] Document each subsystem's responsibility
- [ ] Create subsystem architecture diagrams
- [ ] Write developer guide for each subsystem

### Phase 4: Validation
- [ ] All tests pass
- [ ] No circular dependencies
- [ ] Clear import hierarchy
- [ ] Code coverage maintained

---

## Import Hierarchy

```
platform/          # Level 0: Infrastructure (no dependencies)
↓
brain/policy/      # Level 1: Governance (depends on platform)
↓
brain/knowledge/   # Level 2: Understanding (depends on platform)
↓
brain/cognitive/   # Level 3: Thinking (depends on knowledge, policy)
↓
brain/execution/   # Level 4: Action (depends on cognitive, policy)
↓
brain/learning/    # Level 5: Improvement (depends on all)
↓
brain/core.py      # Level 6: Orchestration (depends on all)
```

No circular dependencies allowed.

---

## Example: Adding a New Capability

**BAD (old way)**:
```
Create "ConfidenceEngine"
Create "ConfidenceCalculator" 
Create "ConfidenceCalibrator"
...now we have 13 engines
```

**GOOD (new way)**:
```
Which subsystem?
→ Learning System (improves confidence over time)

Create: brain/learning/confidence_calibration.py

Export from: brain/learning/__init__.py

Use from: brain/cognitive/decision.py
```

Still five subsystems. Just more capabilities within them.

---

## Conclusion

This migration transforms the architecture from:
- ❌ Dozens of independent "engines"
- ❌ Unclear boundaries
- ❌ Difficult to test
- ❌ Hard to navigate

To:
- ✅ Five clear subsystems
- ✅ Well-defined responsibilities  
- ✅ Easy to test independently
- ✅ Obvious where code lives

This architecture will remain coherent even as the platform grows to production scale.
