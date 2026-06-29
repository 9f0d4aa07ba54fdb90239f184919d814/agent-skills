# Repository Restructuring: From Software to Engineering Science Platform

## Current State → Target State

### Current Structure
```
brain/          ← Intelligence implementation
kernel/         ← Runtime
platform/       ← Infrastructure
engineering/    ← Tacked on later
```

### Target Structure
```
core/           ← Core intelligence primitives
science/        ← First-class scientific infrastructure
products/       ← User-facing agents
sdk/            ← Plugin system
plugins/        ← Extensions
research/       ← Research archive
```

---

## The Transformation

### 1. Core (`core/`)
**Pure intelligence primitives**

```
core/
  runtime/          ← kernel/ moves here
  cognition/        ← brain/cognitive/ + decision_engine.py
  knowledge/        ← brain/knowledge/ + repository/
  memory/           ← limbs/memory/ + enterprise_memory.py
  execution/        ← brain/execution/ + workers/
  learning/         ← brain/learning/ + improve.py + learn.py
  trust/            ← brain/policy/
  observation/      ← NEW: continuous monitoring
  world_model/      ← brain/world_model.py expanded
```

### 2. Science (`science/`)
**First-class scientific infrastructure - not an afterthought**

```
science/
  benchmarks/
    olympics.py              ← Engineering Olympics (EngineeringNet)
    calibration.py           ← Confidence calibration tests
    regression.py            ← Detect intelligence regressions
  
  experiments/
    decision_lab.py          ← Hypothesis testing
    intelligence_ci.py       ← Automated intelligence testing
    evaluation_platform.py   ← Live repository evaluation
  
  datasets/
    engineering_tasks/       ← 100,000 task dataset
    failure_cases/           ← Mistakes, wrong reasoning, rollbacks
    counterfactuals/         ← Alternate history scenarios
  
  metrics/
    reasoning_quality.py
    planning_quality.py
    execution_quality.py
    trust_calibration.py
    cost_efficiency.py
  
  graphs/
    judgment_graph.py        ← Decision DNA as interconnected graph
    pattern_similarity.py
    success_predictor.py
  
  reports/
    intelligence_ci_report.py
    version_comparison.py
    benchmark_history.py
```

### 3. Products (`products/`)
**User-facing implementations**

```
products/
  coding_agent/              ← The main coding agent
    __init__.py
    agent.py
    config.py
```

### 4. SDK (`sdk/`)
**Plugin system for extensions**

```
sdk/
  plugin_api.py
  primitives.py
  hooks.py
```

### 5. Plugins (`plugins/`)
**Extensions built on SDK**

```
plugins/
  languages/
    python/
    javascript/
    java/
  tools/
    git/
    ci_cd/
    monitoring/
```

### 6. Research (`research/`)
**Research archive - internal papers**

```
research/
  papers/
    001_engineering_world_model.md
    002_decision_dna_graph.md
    003_trust_framework_evaluation.md
  experiments/
    world_model_hypothesis/
      design.md
      results.json
      analysis.md
  datasets/
    published_benchmarks/
```

---

## Key Changes

### 1. Science Becomes First-Class
**Before:** `engineering/` folder tacked on  
**After:** `science/` at top level with full infrastructure

### 2. Decision DNA → Engineering Judgment Graph
**Before:** Linear decision storage  
**After:** Graph connecting problems → evidence → decisions → outcomes → patterns → related decisions

### 3. Benchmarks vs Evaluations (Separated)
**Benchmarks:** Fixed datasets, version comparison (Engineering Olympics)  
**Evaluations:** Live repositories, real customer work, usefulness measurement

### 4. Intelligence CI Pipeline
Every commit runs:
1. Unit tests
2. Integration tests
3. Engineering Olympics
4. Calibration tests
5. Regression detection
6. Cost analysis
7. Generate intelligence report

**If benchmark score drops → merge fails**

### 5. Calibration Benchmark (NEW)
Track: If system says 90% confidence, is it actually right 90% of the time?

### 6. Failure Datasets (NEW)
Store mistakes, wrong reasoning, bad plans, rollbacks, near misses.
Often more valuable than success cases.

### 7. Counterfactuals in Decision DNA (NEW)
Not just "what happened"  
Also: "what if we chose differently?" with estimated outcomes

### 8. Research Papers (NEW)
Every major milestone becomes an internal research paper:
- Hypothesis
- Evaluation
- Results
- Failure cases
- Future work

---

## Intelligence Governance

**Before adding ANY new subsystem, require:**

1. What hypothesis does it test?
2. Which benchmark will improve?
3. Which metric will change?
4. What is the expected effect size?
5. How will we know it failed?

**If not answered → don't build it**

---

## Architecture Freeze

**The architecture is now frozen.**

Current subsystems:
- Executive Layer ✅
- World Model ✅
- Observation ✅
- Cognition ✅
- Knowledge ✅
- Memory ✅
- Trust ✅
- Execution ✅
- Learning ✅
- Evaluation ✅

**Rule:** No new top-level architectural concepts unless an experiment demonstrates that the current architecture cannot achieve a measurable target.

---

## Migration Path

### Phase 1: Restructure (Week 8)
1. Create new directory structure
2. Move existing code to appropriate locations
3. Update all imports
4. Ensure tests pass

### Phase 2: Enhance Science Infrastructure (Week 9-10)
1. Expand Engineering Olympics to 1000 tasks
2. Build Intelligence CI pipeline
3. Implement calibration benchmarks
4. Create failure datasets

### Phase 3: Build Judgment Graph (Week 11-12)
1. Transform Decision DNA from list to graph
2. Implement pattern similarity
3. Add counterfactual storage
4. Build success predictor

### Phase 4: Establish Baselines (Week 13-14)
1. Run full Engineering Olympics
2. Establish Intelligence v1.0 baseline
3. Generate first intelligence report
4. Document calibration baseline

---

## The Roadmap

### Phase A (Month 1-3): Foundation
- Build Engineering World Model
- 100 Engineering Olympics tasks
- Intelligence CI established
- Reproducible baseline score

### Phase B (Month 4-6): Scale
- 1,000 benchmark tasks
- Engineering Judgment Graph operational
- Continuous calibration testing
- Real-world evaluation data collection

### Phase C (Month 7-12): Evidence
- Internal benchmark reports after every release
- Intelligence version tracking
- Statistically significant improvements demonstrated
- First research papers published internally

---

## What Makes This Different

**Most AI projects:**
```
Prototype → Features → More features → Rewrite
```

**This project:**
```
Architecture → Scientific methodology → Evidence → 
Measured intelligence → Accumulated judgment
```

**The key insight:**
> Science is not a supporting activity. Science IS the platform.

---

## Success Metrics

After 12 months, we should be able to say:

"Intelligence Version 24 scores **91.2** on Engineering Olympics (EngineeringNet), a **47% improvement** over Version 1, with p < 0.05.

The Engineering Judgment Graph contains **45,000 decision patterns** with **89% reuse rate**.

Calibration analysis shows **92% accuracy** in confidence predictions.

Failure dataset analysis identified **12 systemic weaknesses**, 11 of which are now resolved.

All improvements are scientifically validated through controlled experiments."

---

## The Moat

**Accumulated Engineering Judgment Graph**

- Year 1: 10,000 patterns
- Year 5: 100,000 patterns
- Year 10: 1,000,000 patterns

Competitors can copy architecture in days.  
**They cannot copy 5 years of graph-structured, scientifically validated engineering judgment.**

---

## Files to Create

1. `RESTRUCTURING_PLAN.md` (this file)
2. `science/benchmarks/olympics.py` (expand existing)
3. `science/benchmarks/calibration.py` (new)
4. `science/benchmarks/regression.py` (new)
5. `science/experiments/intelligence_ci.py` (new)
6. `science/experiments/evaluation_platform.py` (new)
7. `science/datasets/failure_cases/` (new)
8. `science/graphs/judgment_graph.py` (new)
9. `science/metrics/` (new - all metric files)
10. `research/papers/001_engineering_world_model.md` (new)
11. `INTELLIGENCE_GOVERNANCE.md` (new)

---

## Next Steps

1. **This document** - Define complete restructuring
2. **Execute restructuring** - Move code to new structure
3. **Build Intelligence CI** - Automated regression testing
4. **Expand Olympics** - 100 → 1000 tasks
5. **Build Judgment Graph** - Transform DNA to graph
6. **Establish baseline** - Intelligence v1.0 score
7. **Freeze architecture** - Evidence-only changes

---

**Status: Architecture frozen. Science infrastructure building. Evidence collection starting.**

🎯 **This is no longer a software project. This is an engineering science platform.**
