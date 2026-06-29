"""
BRAIN CORE - The central intelligence.
Pluggable providers (OpenAI, Anthropic, OpenRouter, local, opencode).
Self-learning loop: Plan -> Act -> Observe -> Reflect -> Improve.
"""

import json, os, time, subprocess, re
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

OPCODE = os.getenv("OPCODE_BIN") or os.environ.get("HOME", "") and os.path.expanduser("~/.local/bin/opencode") or "opencode"

PROVIDERS = {
    "openai":     {"url": "https://api.openai.com/v1",     "models": ["gpt-4o","gpt-4o-mini","o3-mini"]},
    "anthropic":  {"url": "https://api.anthropic.com/v1",  "models": ["claude-sonnet-4-20250514","claude-haiku-3-5"]},
    "openrouter": {"url": "https://openrouter.ai/api/v1",  "models": ["openai/gpt-4o","anthropic/claude-sonnet-4"]},
    "local":      {"url": "http://localhost:11434/v1",     "models": ["qwen3:8b","llama3.1:8b"]},
    "gemini":     {"url": "https://generativelanguage.googleapis.com/v1beta", "models": ["gemini-2.0-flash"]},
}

PLAN_SYSTEM_PROMPT = """You are a senior engineer planning how to accomplish a task using available tools.

RULES:
1. Each step MUST be SELF-CONTAINED - do NOT reference outputs of previous steps
2. Use absolute file paths from the Working directory provided
3. Prefer simple solutions with minimal steps
4. Always VERIFY the result after making changes
5. If you need to understand the codebase first, use codebase_overview or tree
6. If a step might fail, include a fallback approach

RESPONSE FORMAT: Return ONLY a JSON array of step objects.
Each step: {"tool": "tool_name", "args": {"arg1": "value1"}, "desc": "brief description"}

EXAMPLE for "count lines in a file":
[{"tool": "run_bash", "args": {"cmd": "wc -l /path/to/file.py"}, "desc": "Count lines in file"}]

EXAMPLE for "find a class definition and its location":
[{"tool": "grep", "args": {"text": "class MyClass", "include": "*.py"}, "desc": "Find class definition"}]

EXAMPLE for "create a new file":
[{"tool": "write_file", "args": {"path": "/path/to/new.py", "content": "print('hello')"}, "desc": "Create new file"}]
"""


@dataclass
class BrainConfig:
    provider: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096


class Brain:
    def __init__(self, config: Optional[BrainConfig] = None):
        self.cfg = config or BrainConfig()
        self._resolve()
        self.history: list[dict] = []
        self.memory_cache: str = ""

    def _resolve(self):
        c = self.cfg
        if not c.provider:
            c.provider = os.getenv("LLM_PROVIDER", "opencode")
        if c.provider != "opencode":
            info = PROVIDERS.get(c.provider, PROVIDERS["openai"])
            if not c.model:
                c.model = info["models"][0]
            if not c.api_key:
                # Try provider-specific key first, fall back to generic LLM_API_KEY
                c.api_key = os.getenv(f"{c.provider.upper()}_API_KEY", "") or os.getenv("LLM_API_KEY", "")

    def _call_api(self, messages: list[dict], system: str = "") -> dict:
        c = self.cfg
        body = {"model": c.model, "messages": [], "temperature": c.temperature, "max_tokens": c.max_tokens}
        if system:
            body["messages"].append({"role": "system", "content": system})
        body["messages"].extend(messages)

        headers = {"content-type": "application/json"}
        if c.provider == "anthropic":
            headers["x-api-key"] = c.api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["authorization"] = f"Bearer {c.api_key}"

        for attempt in range(3):
            try:
                import httpx
                r = httpx.post(f"{PROVIDERS[c.provider]['url']}/chat/completions",
                               headers=headers, json=body, timeout=120)
                r.raise_for_status()
                data = r.json()
                return {"ok": True, "data": data["choices"][0]["message"]["content"], "error": ""}
            except httpx.HTTPStatusError as e:
                err = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            except httpx.TimeoutException:
                err = "timeout after 120s"
            except Exception as e:
                err = str(e)
            if attempt < 2:
                time.sleep(1.5 ** attempt)
        return {"ok": False, "data": "", "error": err}

    def _call_opencode(self, prompt: str) -> dict:
        for attempt in range(3):
            try:
                r = subprocess.run([OPCODE, "run", prompt], capture_output=True, text=True, timeout=120)
                out = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', r.stdout).strip()
                if r.returncode == 0 and out:
                    return {"ok": True, "data": out, "error": ""}
                err = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', r.stderr).strip()
                if not out and not err:
                    err = "empty response"
                return {"ok": bool(out), "data": out or "", "error": err[:500]}
            except subprocess.TimeoutExpired:
                err = "timeout after 120s"
            except Exception as e:
                err = str(e)
            if attempt < 2:
                time.sleep(1.5 ** attempt)
        return {"ok": False, "data": "", "error": err}

    def think(self, prompt: str, system: str = "") -> str:
        if self.cfg.provider == "opencode":
            full = (system + "\n\n" + prompt) if system else prompt
            return self._call_opencode(full)["data"]
        result = self._call_api([{"role": "user", "content": prompt}], system)
        return result["data"]

    def think_json(self, prompt: str, system: str = "") -> Optional[dict | list]:
        resp = self.think(prompt, system or "Return ONLY valid JSON. No explanation.")
        return self._parse_json(resp)

    def _parse_json(self, text: str):
        if not text:
            print("[WARN] _parse_json: Empty text provided")
            return None
        
        text = re.sub(r'```(?:json)?\n?', '', text).strip()
        
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Direct JSON parse failed: {e}")
        
        # Try to find JSON array or object in the text
        for pat in [r'\[[\s\S]*?\]', r'\{[\s\S]*?\}']:
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

    def plan(self, task: str, context: str = "", tools_info: str = "", workdir: str = "") -> list[dict]:
        cwd = workdir or os.getcwd()
        # Include past results as direct knowledge
        knowledge = ""
        if tools_info and "[Previous session context]" in tools_info:
            knowledge = "\nPREVIOUS RESULTS (use these instead of re-running tools):\n" + tools_info[tools_info.index("[Previous session context]"):]
        valid_tools = [
            "run_bash","run_python","read_file","write_file","edit_file",
            "search_files","grep","tree","web_search","web_fetch",
            "install_deps","run_tests","ask_user","analyze_file","find_file",
            "codebase_overview","find_references","find_symbol","dependency_graph","similar_files",
            "generate_image_prompt","generate_story","analyze_dataframe","run_ml_experiment","visualize_data",
            "git_status","git_diff","git_log","read_directory","file_info","run_command",
        ]
        prompt = f"""Task: {task}
Working directory: {cwd}
Context: {context[:1500] if context else 'None'}
{tools_info}

Create a minimal step-by-step plan. Each step: {{"tool":"tool_name","args":{{}},"desc":"what to do"}}
Available tools: {', '.join(valid_tools)}

IMPORTANT: Use absolute paths (e.g. "{cwd}/brain/core.py") when referring to files.
Each step must be SELF-CONTAINED - do NOT rely on output from previous steps.
{knowledge}
CRITICAL: If PREVIOUSLY KNOWN FACTS already provide the answer, DO NOT re-run tools. Use the fact directly.

CRITICAL: Use the CORRECT arg NAMES for each tool:
- run_bash: cmd (bash command string)
- run_python: code (python code string)
- read_file: path (file path), offset (optional), limit (optional)
- write_file: path, content
- edit_file: path, old (text to find), new (replacement)
- search_files: pattern (glob like "*.py")
- grep: text (search term), include (file pattern, default "*.py"), path (dir, optional)
- tree: depth (int, default 3)
- web_search: query
- web_fetch: url
- install_deps: packages (space-separated string)
- run_tests: cmd (test command), path (optional)
- ask_user: question (string)
- analyze_file: path
- find_file: name (filename or glob pattern), path (dir, optional)
- codebase_overview: use to understand the full project structure (no args)
- find_references: name (symbol name) - find all references to a symbol
- find_symbol: symbol - find classes/functions matching name
- dependency_graph: show file dependency graph (no args)
- similar_files: path - find files similar to given file
- generate_image_prompt: concept (what to visualize)
- generate_story: topic (story topic)
- analyze_dataframe: code (pandas analysis code)
- run_ml_experiment: code (ML training code)
- visualize_data: code (plotting code), output_path (optional)

Return ONLY a JSON array of steps."""
        result = self.think_json(prompt)
        if isinstance(result, list) and result:
            for step in result:
                if step.get("tool") not in valid_tools:
                    step["tool"] = "run_bash"
                    desc = step.get("desc", "")[:60]
                    step["args"] = {"cmd": f"echo 'Tool not found, fallback: {desc}'"}
            return result
        return [{"tool":"run_bash","args":{"cmd":f"echo 'Task: {task[:80]}'"}}]

    def reflect(self, task: str, actions: list[dict], result: str, error: str = "") -> dict:
        prompt = f"""Task: {task}
Actions taken: {json.dumps(actions[:5])}
Result: {result[:800] if result else 'None'}
Error: {error[:400] if error else 'None'}

Analyze what happened and return JSON:
{{"lessons":["specific lesson learned"],"patterns":["repeated approach detected"],"improvements":["how to do better next time"],"importance":0.5,"skills":["optional skill name"]}}
Be specific and actionable."""
        result_data = self.think_json(prompt)
        if isinstance(result_data, dict):
            return result_data
        return {"lessons":[],"patterns":[],"improvements":[],"importance":0.3}

    def remember(self, query: str) -> str:
        prompt = f"""Recall relevant context for: {query}
Previous memory: {self.memory_cache[:800]}

Return relevant facts, lessons, or patterns as a short paragraph."""
        result = self.think(prompt, "You are a memory retrieval system. Be concise.")
        return result

    def learn(self, lesson: str):
        self.memory_cache += f"\n- {lesson}"
        if len(self.memory_cache) > 10000:
            self.memory_cache = self.memory_cache[-5000:]

    def deep_think(self, task: str, context: str = "") -> str:
        """Deep analysis before executing - think about what's needed."""
        prompt = f"""Task: {task}
Context: {context[:700] if context else 'None'}

Analyze before acting:
1. What does the task really need?
2. What do we already know? (CHECK PREVIOUSLY KNOWN FACTS above)
3. What tools/approach is best, avoiding redundant work?
4. What are the risks?
5. How to verify success?

Return 2-3 sentences. If previously known facts answer the question, state that."""
        return self.think(prompt, "You are a thorough analyst. Think step by step. Use existing knowledge before re-running tools.")

    def get_providers(self) -> dict:
        info = {}
        for name, p in PROVIDERS.items():
            info[name] = {"models": p["models"], "key_set": bool(os.getenv(f"{name.upper()}_API_KEY"))}
        info["opencode"] = {"models": ["deepseek-v4-flash-free"], "key_set": True, "free": True}
        return info
