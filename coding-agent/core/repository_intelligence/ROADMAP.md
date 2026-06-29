# REPOSITORY INTELLIGENCE ROADMAP

**Priority:** P0 - CRITICAL PATH BLOCKER
**Status:** 20% Complete
**Timeline:** 2-3 months

---

## THE 5 STAGES

### Stage 1: Parser (30%) ⚠️ IN PROGRESS
- Tree-sitter Integration
- AST Construction
- Exit: Parse 100 repos, 95%+ success

**Current:** 20%
**Timeline:** 3-4 weeks

### Stage 2: Semantics (50%) ⚠️ BLOCKED
- Symbol Table
- Reference Resolution
- Exit: 95%+ symbol resolution

**Blocked By:** Stage 1
**Timeline:** 4-5 weeks

### Stage 3: Graphs (70%) ⚠️ BLOCKED
- Call Graph
- Dependency Graph
- Type Graph
- Exit: 90%+ graph accuracy

**Blocked By:** Stage 2
**Timeline:** 5-6 weeks

### Stage 4: Architecture (85%) ⚠️ BLOCKED
- Pattern Detection
- Layer Identification
- API Extraction
- Exit: 80%+ architecture detection

**Blocked By:** Stage 3
**Timeline:** 3-4 weeks

### Stage 5: Repository IR (100%) ⚠️ BLOCKED
- JSON Export
- Unified Representation
- Exit: Complete IR for 200 repos

**Blocked By:** Stage 4
**Timeline:** 2 weeks

---

## REPOSITORY IR FORMAT

```json
{
  "repository": {"name": "", "language": "", "architecture": ""},
  "modules": [{"name": "", "layer": "", "exports": [], "imports": []}],
  "symbols": [{"name": "", "type": "", "location": {}}],
  "calls": [{"caller": "", "callee": ""}],
  "apis": [{"path": "", "method": "", "handler": ""}],
  "database": {"tables": []},
  "tests": [{"name": "", "tests_symbol": ""}],
  "metrics": {"files": 0, "lines": 0, "coverage": 0.0}
}
```

---

## BLOCKING ISSUES

**Repository Intelligence blocks everything:**
- World Model (needs IR)
- Olympics validation (needs analysis)
- Knowledge Graph (needs structured data)
- All measurement

**70% of engineering effort goes here until 60% complete.**

---

## IMMEDIATE ACTIONS

**This Week:**
1. Integrate Tree-sitter library
2. Add Python grammar
3. Build AST walker
4. Write 50 parser tests

**Next Week:**
1. Parse 10 test repos
2. Extract symbols
3. Resolve imports
4. Write 50 more tests

---

## SUCCESS METRICS

| Stage | Metric | Target |
|-------|--------|--------|
| 1 | Parseable repos | 95% |
| 2 | Symbol resolution | 95% |
| 3 | Call graph accuracy | 90% |
| 4 | Architecture detection | 80% |
| 5 | IR completeness | 100% |

---

**Next Review:** Weekly
**Critical Path:** YES
