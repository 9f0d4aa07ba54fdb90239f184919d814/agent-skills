# Critical Bug Fixes for Coding Agent

## This file contains patches for the 7 most critical bugs identified in the analysis.

---

## BUG FIX #1: State Machine Missing PAUSED Transition
**File:** coding-agent/kernel/state_machine.py
**Line:** 50
**Severity:** HIGH

### Original Code (Line 38-51):
```python
VALID_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.QUEUED, JobState.CANCELLED},
    JobState.QUEUED: {JobState.PLANNING, JobState.CANCELLED, JobState.PAUSED},
    JobState.PLANNING: {JobState.CONTEXT_BUILDING, JobState.EXECUTING, JobState.FAILED, JobState.CANCELLED},
    JobState.CONTEXT_BUILDING: {JobState.EXECUTING, JobState.PLANNING, JobState.FAILED, JobState.CANCELLED},
    JobState.EXECUTING: {JobState.VERIFYING, JobState.FAILED, JobState.CANCELLED, JobState.PAUSED},
    JobState.VERIFYING: {JobState.REVIEWING, JobState.EXECUTING, JobState.FAILED, JobState.CANCELLED},
    JobState.REVIEWING: {JobState.COMPLETED, JobState.EXECUTING, JobState.FAILED, JobState.CANCELLED},
    JobState.COMPLETED: set(),  # Terminal state
    JobState.FAILED: {JobState.RETRYING, JobState.QUEUED, JobState.CANCELLED},
    JobState.RETRYING: {JobState.PLANNING, JobState.EXECUTING, JobState.VERIFYING, JobState.FAILED, JobState.CANCELLED},
    JobState.CANCELLED: set(),  # Terminal state
    JobState.PAUSED: {JobState.QUEUED, JobState.CANCELLED},
}
```

### Fixed Code:
The fix is already present in line 50. No change needed, but verify PAUSED is in the dict.

**Status:** ✅ ALREADY FIXED

---

## BUG FIX #2: Broken Timeout Implementation
**File:** coding-agent/kernel/runtime.py
**Lines:** 273-289
**Severity:** CRITICAL

### Original Code:
```python
def _run_with_timeout(self, fn, *args, timeout: float, **kwargs):
    """Run a function with a timeout."""
    result = [None]
    error = [None]
    done = threading.Event()

    def runner():
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            error[0] = e
        finally:
            done.set()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    done.wait(timeout=timeout)

    if not done.is_set():
        raise TimeoutError(f"Execution timed out after {timeout}s")

    if error[0]:
        raise error[0]

    return result[0]
```

### Fixed Code:
```python
def _run_with_timeout(self, fn, *args, timeout: float, **kwargs):
    """Run a function with a timeout using ThreadPoolExecutor."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            future.cancel()
            raise TimeoutError(f"Execution timed out after {timeout}s")
        except Exception as e:
            raise e
```

**Rationale:** The original implementation can't actually stop daemon threads. ThreadPoolExecutor provides proper cancellation.

---

## BUG FIX #3: Thread Safety Violation in Runtime
**File:** coding-agent/kernel/runtime.py
**Lines:** 175-210
**Severity:** HIGH

### Issue:
Lock is released before job completes, allowing race conditions.

### Original Code:
```python
def _execute_job(self, job: Job):
    """Execute a single job through its steps."""
    with self._lock:
        self._active[job.id] = job
        self._stats["jobs_started"] += 1

    job.transition_to(JobState.EXECUTING)
    job.started_at = time.time()
    # ... rest of execution without lock
```

### Fixed Code:
```python
def _execute_job(self, job: Job):
    """Execute a single job through its steps."""
    # Add to active jobs with lock
    with self._lock:
        self._active[job.id] = job
        self._stats["jobs_started"] += 1

    try:
        job.transition_to(JobState.EXECUTING)
        job.started_at = time.time()

        # Execute steps...
        retry_count = 0
        for step in job.steps:
            if step.status == StepState.COMPLETED:
                continue

            executed = self._execute_step(job, step, retry_count)
            if not executed:
                if job.status == JobState.CANCELLED:
                    break
                while retry_count < self.max_retries:
                    retry_count += 1
                    self._stats["retries"] += 1
                    job.metrics["retries"] += 1
                    self.event_bus.publish(
                        "system.log",
                        source="runtime",
                        data={"message": f"Retrying step '{step.name}' (attempt {retry_count + 1})",
                              "level": "warning"},
                    )
                    executed = self._execute_step(job, step, retry_count)
                    if executed:
                        break
                if not executed:
                    break
    finally:
        # Finalize with lock
        with self._lock:
            self._finalize_job(job)
            if job.id in self._active:
                del self._active[job.id]
```

**Rationale:** Ensures job cleanup happens atomically, preventing race conditions.

---

## BUG FIX #4: JSON Parsing Fails Silently
**File:** coding-agent/brain/core.py
**Lines:** 138-154
**Severity:** MEDIUM

### Original Code:
```python
def _parse_json(self, text: str):
    if not text:
        return None
    text = re.sub(r'```(?:json)?\\n?', '', text).strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except:
        pass
    # ... more attempts ...
    return None
```

### Fixed Code:
```python
def _parse_json(self, text: str):
    if not text:
        print("[WARN] _parse_json: Empty text provided")
        return None
    
    text = re.sub(r'```(?:json)?\\n?', '', text).strip()
    
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[DEBUG] Direct JSON parse failed: {e}")
    
    # Try to find JSON array or object in the text
    for pat in [r'\\[[\\s\\S]*?\\]', r'\\{[\\s\\S]*?\\}']:
        for m in re.finditer(pat, text):
            try:
                result = json.loads(m.group(0))
                if isinstance(result, (list, dict)):
                    print(f"[DEBUG] Found JSON via pattern matching")
                    return result
            except json.JSONDecodeError:
                continue
    
    # Last resort: try to fix common issues
    fixed = text.strip()
    if fixed.startswith("'") and fixed.endswith("'"):
        fixed = fixed[1:-1]
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        print(f"[ERROR] All JSON parsing attempts failed for text: {text[:200]}")
        print(f"[ERROR] Final error: {e}")
    
    return None
```

**Rationale:** Adds logging so failures are visible, making debugging much easier.

---

## BUG FIX #5: Command Injection Vulnerability
**File:** coding-agent/limbs/tools/runner.py (inferred location)
**Severity:** CRITICAL

### Add Command Whitelist:
```python
# Add at top of file
ALLOWED_COMMANDS = {
    "ls", "cat", "grep", "find", "echo", "pwd", "git",
    "python", "node", "npm", "pip", "pytest", "which"
}

def run_bash(self, cmd: str) -> dict:
    """Execute a bash command with security controls."""
    import shlex
    
    if not cmd or not cmd.strip():
        return {"ok": False, "data": "", "error": "Empty command"}
    
    # Extract command name
    try:
        args = shlex.split(cmd)
        cmd_name = args[0] if args else ""
    except ValueError as e:
        return {"ok": False, "data": "", "error": f"Invalid command syntax: {e}"}
    
    # Check whitelist
    if cmd_name not in ALLOWED_COMMANDS:
        return {
            "ok": False,
            "data": "",
            "error": f"Command not allowed: {cmd_name}. Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
        }
    
    # Execute with proper argument handling (no shell=True!)
    try:
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=self.workdir
        )
        return {
            "ok": r.returncode == 0,
            "data": r.stdout,
            "error": r.stderr if r.returncode != 0 else ""
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "data": "", "error": "Command timed out after 30s"}
    except Exception as e:
        return {"ok": False, "data": "", "error": str(e)}
```

**Rationale:** Prevents arbitrary command execution by whitelisting and using proper subprocess argument handling.

---

## BUG FIX #6: Path Traversal Vulnerability
**File:** coding-agent/limbs/tools/runner.py
**Severity:** HIGH

### Add Path Validation:
```python
def _validate_path(self, path: str) -> tuple[bool, str]:
    """Validate that path is within workdir and safe to access."""
    try:
        # Resolve to absolute path
        requested = Path(path).resolve()
        workdir_resolved = Path(self.workdir).resolve()
        
        # Check if path is within workdir
        try:
            requested.relative_to(workdir_resolved)
        except ValueError:
            return False, f"Path outside workdir: {path}"
        
        # Check for suspicious patterns
        path_str = str(path)
        if ".." in path_str or path_str.startswith("/"):
            return False, f"Suspicious path pattern: {path}"
        
        return True, ""
    except Exception as e:
        return False, f"Path validation error: {e}"

def read_file(self, path: str, offset: int = 0, limit: int = 100000) -> dict:
    """Read file with path validation."""
    valid, error = self._validate_path(path)
    if not valid:
        return {"ok": False, "data": "", "error": error}
    
    try:
        file_path = Path(self.workdir) / path
        content = file_path.read_text(encoding="utf-8", errors="replace")
        
        # Apply offset/limit
        if offset:
            content = content[offset:]
        if limit:
            content = content[:limit]
        
        return {"ok": True, "data": content, "error": ""}
    except FileNotFoundError:
        return {"ok": False, "data": "", "error": f"File not found: {path}"}
    except Exception as e:
        return {"ok": False, "data": "", "error": str(e)}

def write_file(self, path: str, content: str) -> dict:
    """Write file with path validation."""
    valid, error = self._validate_path(path)
    if not valid:
        return {"ok": False, "data": "", "error": error}
    
    try:
        file_path = Path(self.workdir) / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {"ok": True, "data": f"Wrote {len(content)} bytes to {path}", "error": ""}
    except Exception as e:
        return {"ok": False, "data": "", "error": str(e)}
```

**Rationale:** Prevents directory traversal attacks by validating all file paths.

---

## BUG FIX #7: Memory Leak in Event Bus
**File:** coding-agent/kernel/event_bus.py
**Lines:** 69-82
**Severity:** MEDIUM

### Original Code:
```python
def unsubscribe(self, sub_id: str) -> bool:
    """Unsubscribe by subscription ID."""
    for event_type, subs in self._subscribers.items():
        for sub in subs:
            if sub["id"] == sub_id:
                sub["active"] = False
                return True
    for sub in self._wildcard_subscribers:
        if sub["id"] == sub_id:
            sub["active"] = False
            return True
    return False
```

### Fixed Code:
```python
def unsubscribe(self, sub_id: str) -> bool:
    """Unsubscribe by subscription ID and remove from list."""
    # Remove from type-specific subscribers
    for event_type, subs in self._subscribers.items():
        for i, sub in enumerate(subs):
            if sub["id"] == sub_id:
                del subs[i]
                return True
    
    # Remove from wildcard subscribers
    for i, sub in enumerate(self._wildcard_subscribers):
        if sub["id"] == sub_id:
            del self._wildcard_subscribers[i]
            return True
    
    return False

def _prune_inactive_subscribers(self):
    """Remove inactive subscribers (called periodically)."""
    for event_type in list(self._subscribers.keys()):
        self._subscribers[event_type] = [
            sub for sub in self._subscribers[event_type]
            if sub.get("active", True)
        ]
        if not self._subscribers[event_type]:
            del self._subscribers[event_type]
    
    self._wildcard_subscribers = [
        sub for sub in self._wildcard_subscribers
        if sub.get("active", True)
    ]

# Add to _deliver method:
def _deliver(self, event: Event):
    """Deliver event to all matching subscribers."""
    # Prune every 100 events
    if self._stats["published"] % 100 == 0:
        self._prune_inactive_subscribers()
    
    # ... rest of delivery logic
```

**Rationale:** Actually removes subscribers instead of just marking inactive, preventing memory leak.

---

## Summary of Fixes

1. ✅ State Machine PAUSED transition - Already fixed
2. ✅ Timeout implementation - Use ThreadPoolExecutor
3. ✅ Thread safety - Use finally block for cleanup
4. ✅ JSON parsing - Add logging
5. ✅ Command injection - Whitelist and shlex
6. ✅ Path traversal - Validate all paths
7. ✅ Memory leak - Actually remove subscribers

Apply these fixes immediately before any further development.
