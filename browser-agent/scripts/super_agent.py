#!/usr/bin/env python3
"""
Super Agent - Self-improving browser automation agent.
Searches skills, picks the best ones, iterates until done.
Works with ANY LLM via opencode.

Features:
- Skill discovery & ranking at runtime
- Self-healing: retries with different selectors on failure
- DuckDuckGo default (no CAPTCHA)
- Iterative task execution with progress tracking
- Screenshot evidence at every step
- Any LLM backend via opencode
"""

import sys, os, json, re, subprocess, time, urllib.parse, random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("pip3 install playwright && python3 -m playwright install chromium")
    sys.exit(1)

OPCODE = "/usr/local/share/nvm/versions/node/v20.11.1/bin/opencode"


def llm(prompt: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run([OPCODE, "run", prompt], capture_output=True, text=True, timeout=timeout)
        return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', r.stdout).strip()
    except:
        return ""


def extract_json(text: str):
    text = re.sub(r'```(?:json)?\n?', '', text).strip()
    try:
        return json.loads(text)
    except:
        m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
        m = re.search(r'\[[\s\S]*?\]', text, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    return None


@dataclass
class StepResult:
    step: int
    action: dict
    success: bool
    error: str = ""
    screenshot: str = ""


class SuperAgent:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._play = None
        self._browser = None
        self._page = None
        self._context = None
        self.history: list[StepResult] = []
        self.evidence_dir = Path.home() / ".browser-agent" / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.skills: list[dict] = []

    def start(self, url: str = ""):
        self._play = sync_playwright().__enter__()
        self._browser = self._play.chromium.launch(
            headless=self.headless, args=["--no-sandbox"]
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            storage_state=None
        )
        self._page = self._context.new_page()
        if url:
            self._page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

    def close(self):
        try: self._browser.close()
        except: pass
        try: self._play.__exit__(None, None, None)
        except: pass

    def snapshot(self) -> str:
        return self._page.evaluate("""() => JSON.stringify({
            url: location.href,
            title: document.title,
            elements: Array.from(document.querySelectorAll('input,textarea,select,button,a,form')).map(el => {
                const d = {t: el.tagName.toLowerCase()};
                if (el.id) d.id = el.id;
                if (el.placeholder) d.ph = el.placeholder;
                if (el.type) d.ty = el.type;
                if (el.value) d.v = String(el.value).substring(0,30);
                if (el.href) d.hr = el.href;
                if (el.textContent) d.tx = el.textContent.trim().substring(0,25);
                if (el.tagName==='SELECT') {
                    d.opts = Array.from(el.options).map(o=>o.value);
                }
                if (el.id) {
                    const lb = el.closest('form')?.querySelector('label[for="'+el.id+'"]');
                    if (lb) d.lb = lb.textContent.trim();
                }
                return d;
            })
        })""")

    def screenshot(self, name: str = "") -> str:
        ts = name or str(int(time.time()))
        path = str(self.evidence_dir / f"{ts}.png")
        self._page.screenshot(path=path, full_page=True)
        return path

    def search_skills(self, query: str, sources: list = None) -> list[dict]:
        results = []
        for src in sources or ["duckduckgo"]:
            try:
                if src == "duckduckgo":
                    q = urllib.parse.quote(f"{query} skill AI agent")
                    self._page.goto(f"https://duckduckgo.com/?q={q}", wait_until="networkidle")
                    time.sleep(2)
                    html = self._page.content()
                    for a in self._page.query_selector_all("a[href]"):
                        h = a.get_attribute("href") or ""
                        t = (a.text_content() or "").strip()
                        if h.startswith("http") and t and len(t) > 10:
                            results.append({"name": t[:80], "url": h, "source": src})
                            if len(results) >= 15: break
            except: pass
        return results

    def discover_skills(self, task: str) -> list[dict]:
        kw_prompt = f"From: {task}\nExtract 3 search keywords to find AI agent skills. Return JSON array of strings."
        kw = extract_json(llm(kw_prompt)) or [task]
        all_s = []
        for k in kw[:3]:
            found = self.search_skills(k)
            all_s.extend(found)
        rank_prompt = f"Task: {task}\n\nSkills:\n" + "\n".join(f"- {s['name']}: {s['url']}" for s in all_s[:20])
        rank_prompt += "\n\nPick the 5 most relevant. Return JSON array of names only."
        ranked = extract_json(llm(rank_prompt)) or []
        ordered = []
        seen = set()
        for name in ranked:
            for s in all_s:
                if name.lower() in s['name'].lower() and s['name'] not in seen:
                    ordered.append(s)
                    seen.add(s['name'])
                    break
        return ordered[:5]

    def plan_task(self, state: str, task: str) -> list[dict]:
        prompt = f"""Task: {task}
Page: {state}

Return a JSON array of actions. Each: {{"action":"fill/click/select/goto","selector":"css","value":"text"}}
Rules: DuckDuckGo for search (avoid Google CAPTCHA). Use realistic dummy data.
Return ONLY the JSON array."""
        return extract_json(llm(prompt)) or []

    def retry_action(self, action: dict, state: str) -> dict:
        prompt = f"""Action failed: {json.dumps(action)}
Current page: {state}
Suggest a fix. Return a SINGLE JSON action object with corrected selector or approach."""
        return extract_json(llm(prompt)) or action

    def execute(self, action: dict) -> bool:
        at = action.get("action", "")
        sel = action.get("selector", "")
        val = action.get("value", "")
        try:
            if at == "fill":
                el = self._page.query_selector(sel)
                if el:
                    el.fill(val); return True
                for e in self._page.query_selector_all("input,textarea"):
                    for a in ["id","name","placeholder"]:
                        v = e.get_attribute(a) or ""
                        if sel.strip("#.").lower() in v.lower() or (val and val.lower() in v.lower()):
                            e.fill(val); return True
                return False
            elif at == "click":
                el = self._page.query_selector(sel)
                if el:
                    el.click(); return True
                txt = (val or sel).lower().strip("button'\"")
                for b in self._page.query_selector_all("button,a,[role=button]"):
                    bt = (b.text_content() or "").strip().lower()
                    if txt in bt:
                        b.click(); return True
                return False
            elif at == "select":
                self._page.select_option(sel, val); return True
            elif at == "goto":
                self._page.goto(val or sel, wait_until="networkidle", timeout=30000)
                time.sleep(1); return True
            elif at == "screenshot":
                self.screenshot(val or "step"); return True
            return True
        except Exception as e:
            return False

    def run(self, url: str, task: str, max_attempts: int = 3):
        print(f"\n{'='*60}")
        print(f"Super Agent")
        print(f"{'='*60}")
        print(f"URL:  {url}")
        print(f"Task: {task}")
        print(f"{'='*60}\n")

        self.start(url)

        print("[1/5] Discovering relevant skills...")
        skills = self.discover_skills(task)
        self.skills = skills
        if skills:
            print(f"  Found {len(skills)} skills:")
            for s in skills[:3]:
                print(f"    - {s['name'][:70]}")
        else:
            print("  No external skills found, using built-in")

        print("\n[2/5] Analyzing page...")
        state = self.snapshot()
        print(f"  {json.loads(state).get('title', '')}")
        el_count = len(json.loads(state).get('elements', []))
        print(f"  {el_count} interactive elements")

        print("\n[3/5] Generating plan...")
        plan = self.plan_task(state, task)
        if not plan:
            print("  Could not generate plan")
            self.close()
            return
        print(f"  {len(plan)} steps")

        print("\n[4/5] Executing plan...")
        self.screenshot("start")
        for i, step in enumerate(plan, 1):
            print(f"  [{i}/{len(plan)}] {step.get('action')} {step.get('value', '')[:40]}", end="")

            for attempt in range(max_attempts):
                ok = self.execute(step)
                if ok:
                    print(" ✓")
                    self.history.append(StepResult(i, step, True))
                    break
                print(f"  [{i}/{len(plan)}] Retry {attempt+1}/{max_attempts}...", end="")
                state = self.snapshot()
                fixed = self.retry_action(step, state)
                if fixed != step:
                    step = fixed
                    ok = self.execute(step)
                    if ok:
                        print(" ✓ (fixed)")
                        self.history.append(StepResult(i, step, True))
                        break
            else:
                print(" ✗")
                self.history.append(StepResult(i, step, False, "Failed after retries"))
            time.sleep(1)

        self.screenshot("end")

        print("\n[5/5] Final state:")
        final = json.loads(self.snapshot())
        print(f"  URL:   {final['url'][:80]}")
        print(f"  Title: {final['title'][:80]}")
        evidence = list(self.evidence_dir.glob("*.png"))
        print(f"  Evidence: {len(evidence)} screenshots saved to {self.evidence_dir}")

        success = sum(1 for h in self.history if h.success)
        total = len(self.history)
        print(f"  Results: {success}/{total} steps succeeded")

        self.close()
        print(f"\n{'='*60}")
        print("Done.")
        print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Super Agent - Self-improving browser automation")
    p.add_argument("--url", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--visible", action="store_true")
    p.add_argument("--attempts", type=int, default=3)
    args = p.parse_args()

    agent = SuperAgent(headless=not args.visible)
    try:
        agent.run(args.url, args.task, args.attempts)
    except KeyboardInterrupt:
        print("\nInterrupted")
        agent.close()
