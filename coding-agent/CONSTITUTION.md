# PROJECT CONSTITUTION

**Date:** 2024
**Status:** Active
**Last Review:** Never (First Version)
**Next Review:** After Deliverable 3

---

## PREAMBLE

This document defines the principles and execution framework for building an engineering intelligence platform. It replaces all previous planning documents and roadmaps.

**Purpose:** Build a system whose engineering capabilities can be measured, improved, and demonstrated with evidence rather than claims.

---

## ARTICLE I: ARCHITECTURAL STABILITY

### Section 1: Interface Freeze

The following interfaces are FROZEN:

```python
observe()      # Gather information
represent()    # Structure knowledge
retrieve()     # Find relevant context
reason()       # Analyze and understand
predict()      # Forecast outcomes
decide()       # Make strategic choices
plan()         # Create execution plans
execute()      # Take actions
verify()       # Validate results
evaluate()     # Measure quality
learn()        # Improve from experience
```

These APIs are stable. Internal implementation can evolve freely.

### Section 2: Subsystem Freeze

The 10 core subsystems are FROZEN:
1. Executive Layer
2. World Model
3. Observation System
4. Cognitive System
5. Knowledge System
6. Memory System
7. Trust Framework
8. Execution System
9. Learning System
10. Evaluation Platform

No new top-level subsystems without governance approval (see Article III).

### Section 3: Internal Evolution

Everything below the interface layer can change:
- Algorithms
- Data structures
- Performance optimizations
- Implementation details

Changes require: tests + benchmarks.

---

## ARTICLE II: ENGINEERING DISCIPLINE

### Section 1: Contribution Requirements

Every architectural decision must produce:

1. **Production code** - Working implementation
2. **Tests** - Unit and integration tests
3. **Benchmark** - Either improvement OR new benchmark task
4. **Documentation** - Only if behavior changes

### Section 2: Prohibited Actions

❌ Creating new architecture documents without code
❌ Adding subsystems without experimental proof
❌ Committing code without tests
❌ Claiming improvements without benchmarks
❌ Using LOC as a productivity metric

### Section 3: Progress Measurement

Progress is measured ONLY by:

✅ Repository Intelligence accuracy
✅ Engineering Olympics score
✅ Test coverage percentage
✅ Judgment Graph nodes
✅ Calibration accuracy
✅ Benchmark improvements

Not measured:
- Lines of documentation
- Number of features
- Lines of code
- Diagrams produced

---

## ARTICLE III: GOVERNANCE

### Section 1: Change Approval

Before any new subsystem:

1. What hypothesis does it test?
2. Which benchmark will improve?
3. Which metric will change?
4. What is expected effect size?
5. How will we know it failed?
6. Why can't existing subsystems handle this?
7. What is the experiment design?
8. **What is the rollback plan?**

Default answer: **NO**

### Section 2: Governance Review

This constitution is reviewed:
- After every 3 deliverables
- When architectural tension appears
- Annually

Updates require consensus and documentation.

---

## ARTICLE IV: TRUTH AND EVIDENCE

### Section 1: Sources of Truth

Truth comes from:
1. Benchmark results
2. Test coverage
3. Experimental validation
4. Measurement data
5. Reproducible results

Not from:
- Intuition
- Claims
- Opinions
- Theoretical performance
- Design documents

### Section 2: Reproducibility

Every decision must be reproducible:
- Same inputs → same reasoning → same decision
- All experiments must be replayable
- Benchmarks must be deterministic
- Results must be stored and versioned

### Section 3: Failure Value

Failures are more valuable than successes:
- Production incidents
- Bad pull requests
- Rollbacks
- Failed migrations
- Security breaches
- Performance regressions

Build failure datasets first.

---

## ARTICLE V: THE DELIVERABLES

Success is measured by deliverables, not time.

### Deliverable 1: Repository Intelligence IR ⚠️ CRITICAL

**Goal:** Machine-readable intermediate representation of any codebase

**Components:**
1. Tree-sitter integration (Python, JS, Java, Go, C++, Rust)
2. AST parser
3. Symbol table builder
4. Import resolver
5. Call graph constructor
6. Type inference engine
7. Dependency graph
8. Module graph

**Output:** Repository Index JSON
```json
{
  "repository": "name",
  "language": "python",
  "modules": [...],
  "symbols": [...],
  "types": [...],
  "calls": [...],
  "imports": [...],
  "dependencies": [...],
  "architecture": {...},
  "tests": [...]
}
```

**Exit Criteria:**
- Parse 200 real repositories
- 95% symbol resolution accuracy
- Complete call graphs
- Type inference working
- Architecture pattern detection
- Zero crashes on valid code

**Priority:** P0 - Everything depends on this
**Estimated:** 2-3 months
**Current Status:** 20%

---

### Deliverable 2: Engineering Olympics v1 ⚠️ CRITICAL

**Goal:** 100 gold-standard engineering tasks

**Structure:** Not random tasks. A curriculum.

**20 Categories × 5 Levels:**

Example Category: **Debugging**
```
Level 1: Find Bug
  - Given error message, locate bug
  - Score: understanding

Level 2: Explain Bug
  - Root cause analysis
  - Score: reasoning + evidence

Level 3: Fix Bug
  - Implement correct fix
  - Score: implementation + tests

Level 4: Prevent Bug
  - Add preventive measures
  - Score: verification + patterns

Level 5: Generalize Pattern
  - Extract reusable pattern
  - Score: learning + abstraction
```

**Task Schema:**
```yaml
id: debug_python_memory_leak_001
category: debugging
level: 3
language: python
framework: fastapi
repository: benchmark_023
difficulty: advanced

issue: |
  Memory consumption grows with request count

constraints:
  - no new dependencies
  - maintain API compatibility
  - fix must be in <50 LOC

expected:
  understanding:
    - "identify object retention pattern"
    - "locate leak source"
  evidence:
    - "memory profiler output showing growth"
    - "object reference graph"
  reasoning:
    - "objects not cleared from list"
    - "background tasks retain references"
  plan:
    - "add memory profiling"
    - "identify retention source"
    - "add cleanup in finally block"
    - "verify with load test"
  implementation: |
    # Expected patch location and approach
  tests: |
    # Expected test additions
  verification:
    - "memory usage stable under load"
    - "no object leaks in profiler"

scoring:
  understanding: 15%
  evidence_collection: 10%
  reasoning: 15%
  planning: 10%
  implementation: 25%
  testing: 10%
  verification: 10%
  safety: 5%

ground_truth:
  leak_location: "background_tasks.py:45"
  root_cause: "task objects not garbage collected"
  fix_type: "add explicit cleanup"
  lines_changed: 8
```

**Additional Benchmarks:**

**Repository Understanding:**
```
Task: "Find the login flow"

Expected Output:
  Frontend Login Component
    ↓
  API Endpoint (/auth/login)
    ↓
  Authentication Service
    ↓
  JWT Generator
    ↓
  User Repository
    ↓
  Database
    ↓
  Tests
```

**Impact Analysis:**
```
Task: "What breaks if I rename this method?"

Expected Output:
  - Direct callers (list)
  - Tests that reference it
  - Documentation mentions
  - API contracts
  - Serialization schemas
  - Database migrations
```

**Exit Criteria:**
- 100 tasks across 20 categories
- All reproducible and automated
- Scoring functions validated
- Baseline Intelligence v1.0 established
- Version comparison working

**Priority:** P0 - Can't measure without this
**Estimated:** 1-2 months
**Current Status:** 10%

---

### Deliverable 3: Intelligence CI ⚠️ HIGH

**Goal:** Every PR automatically benchmarked

**Pipeline:**
```
PR Created
  ↓
Run Unit Tests (must pass)
  ↓
Run Integration Tests (must pass)
  ↓
Run Engineering Olympics (full or sample)
  ↓
Run Calibration Tests
  ↓
Detect Regressions
  ↓
Measure Cost
  ↓
Generate Report
  ↓
Pass/Fail Decision
```

**Pass Criteria:**
- All tests pass
- Olympics score >= baseline * 0.95 (max 5% regression)
- No critical calibration degradation
- Cost increase < 20%

**Report Contents:**
- Test coverage delta
- Olympics score comparison
- Calibration accuracy
- Cost analysis
- Regression warnings
- Improvement areas

**Exit Criteria:**
- Automated PR checks
- Score comparison working
- Regression detection accurate
- Reports generated automatically
- Merge blocked on failure

**Priority:** P1
**Estimated:** 2 weeks (after D1, D2)
**Current Status:** 10%

---

### Deliverable 4: World Model v1 🔧 HIGH

**Goal:** Structured understanding of any repository

**Not:** Business strategy, economics, deployment details

**Only:** Software structure

**Layers:**

**Layer 1: Modules**
```
Components
Files per component
Dependencies between components
Entry points
```

**Layer 2: Services**
```
Service boundaries
APIs exposed
APIs consumed
Data ownership
Communication patterns
```

**Layer 3: APIs**
```
REST endpoints
GraphQL schemas
gRPC services
Internal APIs
External APIs
```

**Layer 4: Database**
```
Tables/Collections
Schemas
Relationships
Indexes
Migrations
Queries
```

**Layer 5: Tests**
```
Unit tests
Integration tests
E2E tests
Coverage map
Test dependencies
```

**Implementation:**
Built on top of Repository Intelligence IR (Deliverable 1)

**Exit Criteria:**
- Correctly models all 5 layers for 100 repos
- Auto-extraction working
- Architecture diagram generation
- 90%+ accuracy validated against human assessment

**Priority:** P1
**Estimated:** 1 month (requires D1)
**Current Status:** 5%

---

### Deliverable 5: Engineering Knowledge Graph 🔧 MEDIUM

**Goal:** 10,000 connected entities representing engineering knowledge

**Node Types:**
```
Problem
Decision
Evidence
Pattern
Failure
Success
Repository
Architecture
API
Bug
Test
Migration
Refactoring
Performance
Security
```

**Edge Types:**
```
causes
fixes
depends_on
similar_to
validated_by
invalidated_by
derived_from
requires
introduced_by
prevented_by
related_to
supersedes
```

**Integration:**
- Decision Provenance feeds into graph
- Repository Intelligence provides entities
- Olympics results validate patterns
- World Model structures architecture

**Exit Criteria:**
- 10,000+ connected nodes
- Queryable via API
- Pattern extraction working
- Similarity matching functional
- Visualizable via UI

**Priority:** P2
**Estimated:** 1 month (requires D1, D4)
**Current Status:** 5%

---

## ARTICLE VI: THE ENGINEERING CORPUS

### Section 1: Real-World Data

Build a curated corpus:

**200 Repositories:**
- Open source (various sizes)
- Multiple languages
- Different architectures
- Active maintenance

**1,000 Historical Bugs:**
- Real GitHub issues
- With fixes
- Before/after code
- Discussion context

**500 CVEs:**
- Security vulnerabilities
- Patches
- Exploit details
- Impact analysis

**500 Refactorings:**
- Real refactoring PRs
- Reasoning
- Before/after metrics
- Review feedback

**500 Performance Fixes:**
- Bottleneck identification
- Optimization PRs
- Benchmarks
- Results

**500 Migrations:**
- Framework upgrades
- Breaking changes
- Migration paths
- Lessons learned

**500 Failed PRs:**
- Rejected changes
- Why rejected
- Alternative approaches
- Final resolution

**500 Production Incidents:**
- Outage details
- Root cause
- Fix
- Prevention measures

### Section 2: Synthetic Data

Only after real data is established.

**Synthetic Generation:**
- Repository variations
- Bug injections
- Refactoring scenarios
- Performance challenges

---

## ARTICLE VII: PRIORITY SYSTEM

### P0 - Production Blockers
**Must complete before anything else:**
1. Repository Intelligence IR (D1)
2. Engineering Olympics v1 (D2)
3. 80% test coverage

### P1 - Core Features
**Critical for v1.0:**
4. Intelligence CI (D3)
5. World Model v1 (D4)
6. Judgment Graph foundation

### P2 - Enhancement
**Nice to have for v1.0:**
7. Knowledge Graph (D5)
8. Observation System
9. Trust Framework expansion

### P3 - Future
**Post v1.0:**
10. Executive Layer
11. Continuous Stewardship
12. Economics Layer
13. Research Platform

---

## ARTICLE VIII: REALISTIC TIMELINE

**Not weeks. Not months. Deliverables.**

### Phase 1: Foundation (D1, D2)
**Estimated:** 3-4 months
**Deliverables:**
- Repository Intelligence IR working
- 100 Olympic tasks created
- Test coverage 50%+

**Success Criteria:**
- Parse 200 repos with 95% accuracy
- Baseline Intelligence v1.0 established

---

### Phase 2: Measurement (D3, D4)
**Estimated:** 2 months
**Deliverables:**
- Intelligence CI operational
- World Model v1 complete
- Test coverage 80%+

**Success Criteria:**
- Every PR benchmarked automatically
- World Model accurate for 100 repos

---

### Phase 3: Knowledge (D5)
**Estimated:** 1-2 months
**Deliverables:**
- Engineering Knowledge Graph
- 10,000+ nodes
- Pattern extraction working

**Success Criteria:**
- Queryable knowledge graph
- Decision provenance integrated

---

### Phase 4: Production
**Estimated:** 2 months
**Deliverables:**
- Security audit
- Performance optimization
- Documentation
- Beta deployment

**Success Criteria:**
- Production-ready
- 10 beta users
- Measurable improvement over baseline

---

**Total: 8-10 months to production**

---

## ARTICLE IX: THE MOAT

### What Can Be Copied Quickly:
- Architecture documents
- Feature lists
- UI design
- Integration patterns

### What Cannot Be Copied:
1. **Repository Intelligence Engine** (2-3 months head start)
2. **Engineering Olympics Dataset** (continuous growth)
3. **Engineering Knowledge Graph** (100,000 nodes after 5 years)
4. **Validated Improvements** (scientific experiments take time)
5. **Calibrated Confidence** (requires extensive data)
6. **Engineering Corpus** (curated real-world data)

**Time-based competitive advantage:**
- Year 1: 10,000 judgment graph nodes
- Year 3: 50,000 nodes
- Year 5: 100,000 nodes + proprietary patterns

**Competitors can copy features.**
**They cannot copy 5 years of validated engineering knowledge.**

---

## ARTICLE X: WEEKLY PROGRESS

**Every Friday, report:**

| Metric | Last Week | This Week | Change |
|--------|-----------|-----------|--------|
| Test Coverage | X% | Y% | +Z% |
| Olympic Tasks | X | Y | +Z |
| Repo Understanding Accuracy | X% | Y% | +Z% |
| Knowledge Graph Nodes | X | Y | +Z |
| Benchmarks Passing | X/100 | Y/100 | +Z |
| Deliverable Progress | X% | Y% | +Z% |

**If metrics don't improve, investigate why.**

---

## ARTICLE XI: WHAT THIS PROJECT IS

This is **not** another coding assistant.

This is a **research platform** for engineering intelligence with:

1. **Measurable capabilities** (Olympics benchmarks)
2. **Reproducible improvements** (experimental validation)
3. **Accumulated knowledge** (growing graph)
4. **Scientific discipline** (evidence-based development)

**Success = System becomes measurably better at engineering over time**

---

## ARTICLE XII: AMENDMENTS

This constitution can be amended:
- After completing 3 deliverables
- When fundamental assumptions change
- Annually

Amendments require:
- Justification
- Team consensus
- Documentation

---

## RATIFICATION

**Status:** Active
**Effective:** Immediately
**Signatories:** Project Team
**Next Review:** After Deliverable 3

---

## APPENDIX A: CURRENT REALITY

### What's Working:
✅ Kernel (90% coverage)
✅ Event Bus (90% coverage)
✅ Policy System (80% coverage)
✅ Provenance (solid foundation)

### Critical Gaps:
❌ Repository Intelligence (20%)
❌ Olympics Integration (10%)
❌ World Model (5%)
❌ Knowledge Graph (5%)
❌ Test Coverage (15%)

### Real Completion: **30%**

### Estimated Time to Production: **8-10 months**

---

## APPENDIX B: NEXT ACTIONS

**This Week:**
1. Start Repository Intelligence (Tree-sitter integration)
2. Create first 10 Olympic tasks in YAML
3. Write 50+ unit tests
4. Set up Intelligence CI framework

**This Month:**
1. Complete Tree-sitter for Python
2. Build AST parser
3. Create 50 Olympic tasks
4. Reach 30% test coverage

**This Quarter:**
1. Complete Deliverable 1 (Repository Intelligence)
2. Complete Deliverable 2 (Olympics v1)
3. Reach 60% test coverage
4. Establish baseline Intelligence v1.0

---

**END OF CONSTITUTION**

**Remember:** Every commit must improve a measurable metric. No more design. Only execution.
