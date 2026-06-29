# Quick Reference Guide - Coding Agent

## 🚀 Quick Start

### Running the Agent
```bash
cd coding-agent
python agent.py --task "your task here" --dir /path/to/project
```

### With Specific Provider
```bash
python agent.py --task "add tests" --provider openai --model gpt-4o
```

### Using Kernel Mode
```python
from agent import Agent

agent = Agent({"use_kernel": True})
result = agent.run("Create a REST API endpoint for user registration")
```

---

## 🔧 Most Important Files

### Core System
- `agent.py` - Main entry point
- `kernel/kernel.py` - Central orchestrator
- `kernel/runtime.py` - Job execution engine
- `kernel/job.py` - Job data structures
- `kernel/state_machine.py` - State management
- `kernel/event_bus.py` - Event system

### Intelligence
- `brain/core.py` - LLM integration
- `brain/execution_planner.py` - Task planning
- `brain/verifier.py` - Code verification

### Execution
- `workers/executor_worker.py` - Code execution
- `workers/planner_worker.py` - Planning
- `workers/verifier_worker.py` - Verification

---

## 🐛 Known Bugs & Quick Fixes

### Bug #1: Timeout Doesn't Work
**Symptom:** Workers keep running after timeout
**Quick Fix:** Replace `_run_with_timeout` in `kernel/runtime.py:273`
```python
from concurrent.futures import ThreadPoolExecutor

def _run_with_timeout(self, fn, *args, timeout: float, **kwargs):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout)
```

### Bug #2: Command Injection
**Symptom:** Can execute arbitrary commands
**Quick Fix:** Add to `limbs/tools/runner.py`
```python
ALLOWED = {"ls", "cat", "grep", "git", "python", "pytest"}

def run_bash(self, cmd):
    cmd_name = cmd.split()[0]
    if cmd_name not in ALLOWED:
        return {"ok": False, "error": f"Not allowed: {cmd_name}"}
    # Use list form, not shell=True
    import shlex
    subprocess.run(shlex.split(cmd), ...)
```

### Bug #3: Path Traversal
**Symptom:** Can read files outside workdir
**Quick Fix:** Add validation
```python
def _validate_path(self, path):
    resolved = Path(path).resolve()
    workdir = Path(self.workdir).resolve()
    return resolved.is_relative_to(workdir)
```

---

## 📝 Common Tasks

### Add a New Worker
```python
# 1. Create worker class
class MyWorker(BaseWorker):
    def __init__(self, event_bus, artifacts):
        super().__init__("myworker", "MyWorker", event_bus, artifacts)
    
    def handle(self, job: Job, step: JobStep) -> dict:
        # Your logic here
        return {"status": "completed"}

# 2. Register with kernel
from workers import MyWorker
worker = MyWorker(kernel.event_bus, kernel.artifacts)
kernel.register_worker(worker)
```

### Add a New Tool
```python
# In limbs/tools/runner.py
def my_new_tool(self, param1: str, param2: int) -> dict:
    """Description of what this tool does."""
    try:
        # Your implementation
        result = do_something(param1, param2)
        return {"ok": True, "data": result, "error": ""}
    except Exception as e:
        return {"ok": False, "data": "", "error": str(e)}

# Register in agent.py TOOL_DESCRIPTIONS
TOOL_DESCRIPTIONS["my_new_tool"] = "Does something useful"
```

### Add a New Skill
```python
# Create limbs/skills/my-skill/SKILL.md
"""
# My Skill

## When to use
Use this skill when...

## How it works
This skill...

## Example
```
"""
```

---

## 🧪 Testing

### Run Existing Tests
```bash
cd coding-agent
pytest tests/ -v
```

### Write a New Test
```python
# tests/test_my_feature.py
import pytest
from kernel.job import Job, JobState

def test_job_creation():
    job = Job("test job")
    assert job.status == JobState.CREATED
    assert len(job.steps) == 0

def test_job_transition():
    job = Job("test")
    job.transition_to(JobState.QUEUED)
    assert job.status == JobState.QUEUED
```

### Test Coverage
```bash
pytest --cov=kernel --cov=brain --cov=workers tests/
```

---

## 🔍 Debugging

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Job Status
```python
# Get kernel snapshot
snapshot = kernel.get_snapshot()
print(f"Active jobs: {snapshot['active_jobs']}")
print(f"Queued: {snapshot['queued_jobs']}")
```

### View Event History
```python
events = kernel.event_bus.get_history(limit=50)
for event in events:
    print(f"{event.event_type}: {event.data}")
```

### Check Worker Stats
```python
stats = kernel.get_kernel_stats()
print(f"Runtime: {stats['runtime']}")
print(f"Workers: {stats['workers']}")
```

---

## ⚡ Performance Tips

### 1. Limit Parallel Workers
```python
# Fewer workers = less memory, slower
# More workers = more memory, faster
kernel = Kernel(workdir=".", max_workers=4)
```

### 2. Control LLM Calls
```python
# Use cheaper models for simple tasks
brain = Brain(BrainConfig(
    model="gpt-4o-mini",  # Cheaper, faster
    temperature=0.1,       # More deterministic
    max_tokens=2048        # Shorter responses
))
```

### 3. Cache Aggressively
```python
# Enable all caches
from repository import FileCache, SymbolCache
file_cache = FileCache(workdir)
file_cache.warm_cache()  # Pre-populate
```

### 4. Batch Operations
```python
# Read multiple files at once
files = ["file1.py", "file2.py", "file3.py"]
contents = [tools.read_file(f) for f in files]
```

---

## 🔒 Security Checklist

Before deploying:
- [ ] All file paths validated
- [ ] Commands whitelisted
- [ ] No `shell=True` in subprocess
- [ ] API keys in env vars only
- [ ] Secrets redacted from logs
- [ ] Input validation on all tools
- [ ] Rate limiting enabled
- [ ] Sandboxing configured

---

## 📊 Monitoring

### Key Metrics
```python
# Success rate
success_rate = completed / (completed + failed)

# Average job time
avg_time = total_duration / jobs_completed

# Error rate
error_rate = errors / total_operations

# Worker utilization
utilization = busy_time / total_time
```

### Health Check
```python
def health_check():
    return {
        "kernel": kernel._initialized,
        "workers": len(kernel.list_workers()),
        "queue_depth": len(kernel.runtime.queue),
        "active_jobs": len(kernel.runtime._active),
    }
```

---

## 🆘 Troubleshooting

### "No worker registered for type: X"
**Cause:** Worker not registered with kernel
**Fix:** Add `kernel.register_worker(worker)` in agent.py

### "Cannot transition from X to Y"
**Cause:** Invalid state transition
**Fix:** Check `VALID_TRANSITIONS` in state_machine.py

### "Timeout after Xs"
**Cause:** Operation taking too long or timeout bug
**Fix:** 
1. Apply timeout bug fix from BUG_FIXES.md
2. Increase timeout: `runtime.default_timeout = 600`

### "ModuleNotFoundError"
**Cause:** Missing dependency
**Fix:** `pip install -r requirements.txt`

### Jobs stuck in QUEUED
**Cause:** Runtime not started
**Fix:** Call `kernel.initialize()`

---

## 🎯 Best Practices

### 1. Always Use Kernel Mode
```python
# Good
agent = Agent({"use_kernel": True})

# Avoid (legacy mode)
agent = Agent({"use_kernel": False})
```

### 2. Set Appropriate Priorities
```python
job = Job("urgent fix", priority=JobPriority.CRITICAL)  # High priority
job = Job("refactor", priority=JobPriority.LOW)         # Low priority
```

### 3. Add Proper Error Handling
```python
def my_tool(self, param):
    try:
        result = risky_operation(param)
        return {"ok": True, "data": result, "error": ""}
    except SpecificError as e:
        return {"ok": False, "data": "", "error": f"Specific error: {e}"}
    except Exception as e:
        return {"ok": False, "data": "", "error": f"Unexpected: {e}"}
```

### 4. Validate All Inputs
```python
def tool(self, path: str):
    if not path:
        return {"ok": False, "error": "Path required"}
    if not self._validate_path(path):
        return {"ok": False, "error": "Invalid path"}
    # ... proceed
```

### 5. Use Descriptive Step Names
```python
# Good
job.add_step("Find authentication module", "context", ...)

# Bad
job.add_step("Step 1", "context", ...)
```

---

## 📚 Further Reading

- **Full Analysis:** COMPREHENSIVE_ANALYSIS.md
- **Architecture:** HOW_IT_WORKS.md
- **Bug Fixes:** BUG_FIXES.md
- **Testing:** tests/test_state_machine.py

---

## 🤝 Contributing

### Before Submitting PR
1. Run all tests: `pytest tests/`
2. Check coverage: `pytest --cov`
3. Lint code: `pylint kernel/ brain/ workers/`
4. Update docs if needed

### Code Style
- Follow PEP 8
- Type hints on all functions
- Docstrings on all classes/methods
- Max line length: 100

---

## 🔗 Useful Commands

```bash
# Run agent
python agent.py --task "your task"

# Run tests
pytest tests/ -v

# Coverage
pytest --cov=. tests/

# Lint
pylint kernel/ brain/ workers/

# Type check
mypy kernel/ brain/ workers/

# Profile
python -m cProfile -o profile.stats agent.py --task "test"
python -m pstats profile.stats
```

---

## 📞 Quick Help

**Agent won't start?**
→ Check `kernel.initialize()` is called

**Tests failing?**
→ See BUG_FIXES.md for critical patches

**Security concerns?**
→ Review COMPREHENSIVE_ANALYSIS.md security section

**Need to understand architecture?**
→ Read HOW_IT_WORKS.md

**Want to contribute?**
→ Start with tests/test_state_machine.py as example
