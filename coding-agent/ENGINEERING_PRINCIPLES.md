# ENGINEERING PRINCIPLES

**Status:** Immutable
**Purpose:** Guide all technical decisions
**Review:** Never (unless benchmarks prove a principle wrong)

---

These principles are more stable than any roadmap.
They define how we think about engineering intelligence.

---

## 1. Parse Before Reasoning

You cannot reason about code you don't understand.

Repository Intelligence must be accurate before advanced reasoning.

**Consequence:** Repository Intelligence is always P0.

---

## 2. Measure Before Optimizing

Intuition about improvements is often wrong.

Every optimization must be validated by benchmarks.

**Consequence:** No performance work without measurement.

---

## 3. Every Decision Must Be Reproducible

Same inputs → same reasoning → same decision.

Determinism enables debugging, testing, and trust.

**Consequence:** All decision factors must be loggable and replayable.

---

## 4. Repository IR Is Source of Truth

One canonical representation of every codebase.

All subsystems consume IR, not raw code.

**Consequence:** IR completeness and accuracy are critical.

---

## 5. Benchmarks Drive Evolution

Intelligence improvements must be proven, not claimed.

Engineering Olympics is the objective function.

**Consequence:** Every significant change must improve or add benchmarks.

---

## 6. Real Repositories Over Synthetic

Synthetic examples are useful for testing.

Real repositories expose actual complexity.

**Consequence:** Always validate on real codebases.

---

## 7. Deterministic Analysis When Possible

Static analysis is deterministic and fast.

LLM reasoning is powerful but non-deterministic.

**Consequence:** Prefer static analysis, augment with LLM when needed.

---

## 8. Tests Are Part Of Every Feature

Untested code doesn't work.

Untested intelligence cannot be trusted.

**Consequence:** No merge without tests.

---

## 9. Simplicity Beats Cleverness

Simple systems are understandable and maintainable.

Clever systems are brittle and opaque.

**Consequence:** Choose boring solutions that work.

---

## 10. Evidence Beats Intuition

We believe something works when benchmarks prove it.

Not when it feels right.

**Consequence:** All claims require experimental validation.

---

## 11. Interfaces Are Stable, Implementation Evolves

The 11 core APIs are frozen.

Internal algorithms can change freely.

**Consequence:** Refactor internals aggressively, never break interfaces.

---

## 12. Failures Are More Valuable Than Successes

Production incidents teach more than perfect code.

Failed decisions reveal edge cases.

**Consequence:** Build failure datasets first.

---

## 13. Calibration Is Critical For Autonomy

Overconfident systems are dangerous.

If system says 90% confident, it must be right 90% of time.

**Consequence:** Measure and improve calibration continuously.

---

## 14. Accumulation Creates The Moat

Features can be copied quickly.

Knowledge accumulated over years cannot.

**Consequence:** Focus on systems that compound (Knowledge Graph, Olympics).

---

## 15. Every Question Has One Answer

"Which Engineering capability improved?"

If a change doesn't improve a measurable capability, don't ship it.

**Consequence:** All PRs must answer this question with evidence.

---

## APPLICATION

### When Adding a Feature

❌ "This seems like a good idea"
✅ "Olympics score improves by 8% on refactoring tasks"

### When Optimizing

❌ "This should be faster"
✅ "Parser benchmark shows 3x speedup on 100 repos"

### When Debugging

❌ "I think this is the issue"
✅ "Replay shows decision diverged at step 7"

### When Designing

❌ "This is more elegant"
✅ "This is simpler and testable"

### When Prioritizing

❌ "This would be cool"
✅ "This unblocks Repository Intelligence"

---

## CONFLICTS

When principles conflict, priority order:

1. **Correctness** (Principle 1, 3, 8)
2. **Measurability** (Principle 2, 5, 10)
3. **Simplicity** (Principle 9, 14)
4. **Evidence** (Principle 5, 10, 15)

Example conflict:

"Should we use an LLM for type inference?"

- Principle 7 says prefer deterministic analysis
- But Principle 6 says validate on real repositories
- If static analysis only achieves 60% accuracy on real repos
- And LLM achieves 85% accuracy
- Principle 2 (measure) and Principle 5 (benchmarks) resolve conflict
- Use LLM if benchmarks prove it's better

---

## IMMUTABILITY

These principles don't change unless:

1. Benchmarks prove a principle wrong
2. Experimental evidence contradicts a principle
3. Real-world usage demonstrates a principle is harmful

Changes require:
- Documented experimental evidence
- Team consensus
- Architecture review

**Expected changes over next 5 years: 0-2**

---

## RELATIONSHIP TO OTHER DOCUMENTS

**Constitution:** Defines governance, deliverables, execution
**Principles:** Define how we think about engineering intelligence

**Constitution** = Process
**Principles** = Philosophy

---

## WHY THESE PRINCIPLES

### Principle 1 (Parse Before Reasoning)

Learned from: Every attempt to reason about code without parsing fails.

### Principle 4 (Repository IR Is Source of Truth)

Learned from: Different subsystems re-parsing the same code is wasteful and error-prone.

### Principle 5 (Benchmarks Drive Evolution)

Learned from: AI systems often regress silently without objective measurement.

### Principle 10 (Evidence Beats Intuition)

Learned from: Most intuitions about AI system behavior are wrong.

### Principle 13 (Calibration Is Critical)

Learned from: Overconfident AI systems cause more damage than underconfident ones.

### Principle 15 (Every Question Has One Answer)

Learned from: Without a single north star metric, projects drift.

---

## ANTI-PATTERNS TO AVOID

❌ "Let's add this feature because competitors have it"
✅ "Benchmarks show this capability gap is real"

❌ "We should support this because users might want it"
✅ "10 users requested this capability"

❌ "This algorithm is theoretically better"
✅ "This algorithm is 2x faster on Olympics benchmarks"

❌ "We need more subsystems"
✅ "Current subsystems cannot achieve this proven goal"

❌ "This change improves code quality"
✅ "Test coverage increased 5%, complexity decreased 12%"

---

## DECISION RUBRIC

Every engineering decision should pass this test:

1. ✅ Does it improve a measurable capability?
2. ✅ Do benchmarks validate the improvement?
3. ✅ Is it reproducible and testable?
4. ✅ Is it the simplest solution that works?
5. ✅ Does it maintain interface stability?

If all 5 are YES → Ship it
If any is NO → Reject or redesign

---

## NORTH STAR

**One metric rules them all:**

"Is Intelligence Version N measurably better at engineering than Version N-1?"

Measured by:
- Engineering Olympics score
- Repository understanding accuracy
- Decision calibration
- Real task success rate

Everything serves this goal.

---

**End of Principles**

These are immutable unless proven wrong by evidence.

They complement the Constitution but operate at a different level:
- Constitution defines what we build
- Principles define how we think

Together, they create discipline without rigidity.
