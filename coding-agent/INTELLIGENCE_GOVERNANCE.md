# Intelligence Governance

**Purpose: Prevent architecture expansion without evidence**

---

## The Core Principle

> **No new top-level architectural concepts unless an experiment demonstrates that the current architecture cannot achieve a measurable target.**

---

## Current Architecture (FROZEN)

### 10 Core Subsystems ✅

1. **Executive Layer** - Goals, priorities, budget, economics
2. **World Model** - Shared mental model of engineering system
3. **Observation System** - Continuous monitoring (Git, CI, metrics, deps, security, docs)
4. **Cognitive System** - Reasoning, planning, decisions
5. **Knowledge System** - Architecture, facts, repository understanding
6. **Memory System** - Experiences, past decisions, learned patterns
7. **Trust Framework** - Evidence/tool/result/memory trust scoring
8. **Execution System** - Action execution, simulation, monitoring
9. **Learning System** - Continuous improvement, research loop
10. **Evaluation Platform** - Benchmarks, experiments, metrics

**These are sufficient.**

---

## The Approval Process

### Before Adding ANY New Subsystem

Must answer ALL of these questions:

#### 1. What hypothesis does it test?
**Format:** "We hypothesize that [new subsystem] will improve [specific metric] by [amount]"

**Example:**
- ✅ "We hypothesize that a dedicated Planning Cache will reduce planning time by 40%"
- ❌ "We need a better planning system"

#### 2. Which benchmark will improve?
**Format:** Specific Engineering Olympics category or metric

**Example:**
- ✅ "Refactoring tasks (REFACTORING category) will improve from 72.3 to 85.0"
- ❌ "Things will be better"

#### 3. Which metric will change?
**Format:** Quantifiable metric with baseline and target

**Example:**
- ✅ "Planning quality score: 78.2 → 88.0 (+12.5%)"
- ❌ "Planning will be smarter"

#### 4. What is the expected effect size?
**Format:** Minimum improvement to justify the addition

**Example:**
- ✅ "Minimum 15% improvement, expecting 25%"
- ❌ "It should help"

#### 5. How will we know it failed?
**Format:** Falsifiable failure criteria

**Example:**
- ✅ "If improvement < 10% or cost increases > 20%, remove subsystem"
- ❌ "We'll see if it works"

#### 6. Why can't existing subsystems handle this?
**Format:** Documented limitation of current architecture

**Example:**
- ✅ "Current Memory System stores linear history. Experiments show graph structure improves pattern matching by 34% (Experiment #47)"
- ❌ "Memory could be better"

#### 7. What is the experiment design?
**Format:** Control vs treatment with statistical plan

**Example:**
```
Control: v2.3 (current)
Treatment: v2.4 (with new subsystem)
Tasks: 200 randomly selected from Engineering Olympics
Metric: Planning quality score
Success: p < 0.05, improvement > 15%
Duration: 2 weeks
```

---

## Approval Tiers

### Tier 1: Internal Primitives (No approval needed)
Changes within existing subsystems that don't change interfaces

**Examples:**
- Improve reasoning algorithm in Cognitive System
- Add caching to Knowledge System
- Optimize Trust Framework scoring

**Requirement:** Pass all tests, maintain or improve benchmark scores

### Tier 2: Interface Changes (Lightweight review)
Changes to how subsystems communicate

**Requirements:**
1. Document interface change
2. Run regression tests
3. Verify no benchmark degradation

### Tier 3: New Subsystem (FULL approval process)
Adding a new top-level architectural component

**Requirements:**
1. Answer all 7 governance questions
2. Design controlled experiment
3. Build prototype
4. Run experiment
5. Demonstrate statistical improvement
6. Pass peer review
7. Add to Intelligence Version tracking

**Rejection criteria:**
- Any governance question unanswered
- Improvement below threshold
- Cost increase not justified
- Complexity increase not justified
- Existing subsystems can handle it

---

## The Burden of Proof

**The default answer is NO.**

The burden is on the proposer to prove:
1. Current architecture is insufficient
2. New subsystem will improve measurably
3. Improvement justifies complexity
4. Experiment validates hypothesis

---

## Historical Record

All proposals (approved and rejected) are documented.

### Template

```markdown
## Proposal: [Name]

**Date:** YYYY-MM-DD
**Proposer:** [Name]
**Status:** [Pending / Approved / Rejected]

### Governance Questions

1. Hypothesis: 
2. Benchmark target:
3. Metric change:
4. Effect size:
5. Failure criteria:
6. Architecture limitation:
7. Experiment design:

### Experiment Results

[After experiment runs]

Control score:
Treatment score:
Improvement:
P-value:
Validation:

### Decision

[Approved/Rejected with reasoning]
```

---

## Current Baseline

### Intelligence Version 1.0

**Benchmark Scores:**
- Overall: [TBD - establish baseline]
- Reasoning: [TBD]
- Planning: [TBD]
- Execution: [TBD]
- Trust: [TBD]
- Cost efficiency: [TBD]

**All future changes measured against this baseline.**

---

## Exception Cases

### Only 2 valid exceptions:

#### 1. Critical Bug
Security vulnerability or system-breaking bug that requires architectural change.

**Process:**
- Document bug
- Explain why it requires architectural change
- Implement minimal fix
- Add regression test
- Validate through benchmarks post-fix

#### 2. Research Discovery
Fundamental research finding that invalidates architectural assumption.

**Process:**
- Document research finding
- Explain architectural implication
- Design experiment
- Get peer review
- Follow full approval process

---

## Enforcement

### Every commit must:
1. Pass unit tests
2. Pass integration tests
3. Pass Engineering Olympics (maintain or improve score)
4. Pass regression detection
5. Update Intelligence Version if subsystem changes

### Every release must:
1. Generate intelligence report
2. Compare to previous version
3. Document all changes
4. Explain score changes
5. Update benchmark history

### Every quarter must:
1. Review all subsystems
2. Evaluate necessity
3. Consider deprecation of unused components
4. Measure complexity trend
5. Enforce simplification if needed

---

## The Promise

**This governance ensures:**

1. Architecture remains stable
2. Changes are evidence-based
3. Complexity is justified
4. Improvements are measurable
5. System remains maintainable

**We build on science, not intuition.**

---

## Violations

### If a change bypasses governance:

1. Revert immediately
2. Require full retrospective
3. Document why it happened
4. Add safeguards
5. Update governance if needed

**No exceptions.**

---

## Review Cycle

This governance document is reviewed:
- After every major release
- After 50 commits
- Quarterly
- When architecture tension appears

**Updates require:**
- Team consensus
- Documentation of reasoning
- Announcement to all contributors

---

## Final Rule

**When in doubt, the answer is no.**

Architecture is frozen.  
Prove necessity through experiments.  
Measure everything.  
Simplify whenever possible.

🔒 **Discipline prevents chaos.**
