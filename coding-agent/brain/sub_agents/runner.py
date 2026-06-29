"""
Sub-Agent Runner - Parallel step execution.
Takes a plan, groups independent steps, runs them in parallel.
"""

import json, time, sys
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from limbs.tools.runner import Tools


def execute_step(tool_name: str, args: dict, tools: Tools) -> dict:
    """Execute one tool step and return result."""
    fn = getattr(tools, tool_name, None)
    if not fn:
        return {"ok": False, "error": f"unknown tool: {tool_name}", "data": ""}
    import inspect
    sig = inspect.signature(fn)
    ARG_ALIASES = {"command":"cmd", "filePath":"path", "filename":"path", "file_pattern":"include", "search":"text", "dir":"workdir"}
    try:
        norm = {}
        if isinstance(args, dict):
            for k, v in args.items():
                nk = ARG_ALIASES.get(k, k)
                if nk in sig.parameters:
                    norm[nk] = v
        return fn(**norm)
    except TypeError as e:
        # Retry with only the exact matching args
        if isinstance(args, dict):
            simple_args = {k: v for k, v in args.items() if k in sig.parameters}
            return fn(**simple_args)
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "data": ""}


def run_parallel(plan: list[dict], workdir: str, brain=None, max_workers: int = 4) -> list[dict]:
    """
    Execute plan steps, running independent steps in parallel.
    Steps are parallelized when they use different tools (likely independent).
    """
    tools = Tools(workdir, brain=brain)
    results = []
    t0 = time.time()

    # Group steps into parallel batches
    batches = _group_parallel(plan)

    for batch_idx, batch in enumerate(batches):
        if len(batch) == 1:
            step = batch[0]
            result = execute_step(step.get("tool", ""), step.get("args", {}), tools)
            results.append({**step, "result": result, "time": round(time.time() - t0, 1)})
            yield results[-1]
        else:
            with ThreadPoolExecutor(max_workers=min(len(batch), max_workers)) as executor:
                futures = {}
                for step in batch:
                    fut = executor.submit(execute_step, step.get("tool", ""), step.get("args", {}), tools)
                    futures[fut] = step
                for future in as_completed(futures):
                    step = futures[future]
                    result = future.result()
                    results.append({**step, "result": result, "time": round(time.time() - t0, 1)})
                    yield results[-1]

    return results


def _group_parallel(plan: list[dict]) -> list[list[dict]]:
    """
    Group steps for parallel execution.
    Steps using different tools can run in parallel.
    Same-tool steps run sequentially.
    """
    if not plan:
        return []
    batches = []
    current_batch = [plan[0]]
    for step in plan[1:]:
        tool = step.get("tool", "")
        prev_tool = current_batch[-1].get("tool", "")
        if tool != prev_tool and len(current_batch) < 3:
            current_batch.append(step)
        else:
            batches.append(current_batch)
            current_batch = [step]
    if current_batch:
        batches.append(current_batch)
    return batches


def summarize_parallel_results(results: list[dict]) -> dict:
    """Compile parallel execution results into summary."""
    ok_count = sum(1 for r in results if r.get("result", {}).get("ok"))
    total = len(results)
    error_details = [r for r in results if not r.get("result", {}).get("ok")]
    data_parts = []
    for r in results:
        rd = r.get("result", {})
        if rd.get("ok") and rd.get("data"):
            data_parts.append(rd["data"][:200])
    compilation = "\n".join(data_parts[:5])
    return {
        "total_steps": total,
        "successful": ok_count,
        "failed": len(error_details),
        "compilation": compilation,
        "errors": [e.get("result", {}).get("error", "?")[:100] for e in error_details],
    }
