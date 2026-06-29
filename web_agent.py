#!/usr/bin/env python3
"""
Web Agent - AI-powered browser automation using opencode as the reasoning backend.
Dynamically analyzes web pages and decides next actions at runtime.
"""

import sys
import json
import subprocess
import re
import time
from playwright.sync_api import sync_playwright

OPCODE_BIN = "/usr/local/share/nvm/versions/node/v20.11.1/bin/opencode"


def strip_ansi(s: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', s).strip()


def ask_opencode(prompt: str) -> str:
    result = subprocess.run(
        [OPCODE_BIN, "run", prompt],
        capture_output=True, text=True, timeout=60
    )
    output = strip_ansi(result.stdout)
    json_match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
    if json_match:
        return json_match.group(0)
    lines = [l for l in output.split("\n") if l.strip()]
    return lines[-1] if lines else output


def extract_page_state(page):
    return page.evaluate("""() => {
        const info = [];
        const sel = 'input, textarea, select, button, a';
        document.querySelectorAll(sel).forEach(el => {
            const d = {};
            d.t = el.tagName.toLowerCase();
            if (el.id) d.id = el.id;
            if (el.placeholder) d.ph = el.placeholder;
            if (el.type) d.ty = el.type;
            if (el.value) d.v = String(el.value).substring(0, 30);
            if (el.href) d.hr = el.href;
            if (el.textContent) d.tx = el.textContent.trim().substring(0, 25);
            if (el.tagName === 'SELECT') {
                d.opts = [];
                for (let i = 0; i < el.options.length; i++) d.opts.push(el.options[i].value);
            }
            if (el.id) {
                const lb = el.closest('form')?.querySelector('label[for=\"' + el.id + '\"]');
                if (lb) d.lb = lb.textContent.trim();
            }
            info.push(d);
        });
        return JSON.stringify({ url: window.location.href, title: document.title, elements: info });
    }""")


def get_plan(page_state: str, task: str) -> list:
    prompt = f"""Task: {task}
Current page: {page_state}

Create a step-by-step plan as a JSON array of actions to complete the task.
Each action is: {{"action":"fill/click/select/goto","selector":"css-selector","value":"text"}}
Examples:
- Fill: {{"action":"fill","selector":"input#name","value":"John Doe"}}
- Click: {{"action":"click","selector":"button[type=submit]"}}
- Select: {{"action":"select","selector":"select","value":"+91"}}

Return ONLY a JSON array, nothing else. Use realistic dummy data."""
    raw = ask_opencode(prompt)
    try:
        plan = json.loads(raw)
        if isinstance(plan, list):
            return plan
    except json.JSONDecodeError:
        pass
    return []


def run_action(page, action: dict):
    at = action.get("action")
    sel = action.get("selector", "")
    val = action.get("value", "")

    if at == "fill":
        el = page.query_selector(sel)
        if el:
            el.fill(val)
            print(f"  Filled {sel} <- {val}")
            return True
        for e in page.query_selector_all("input, textarea"):
            eid = e.get_attribute("id") or ""
            eph = e.get_attribute("placeholder") or ""
            enm = e.get_attribute("name") or ""
            target = sel.strip("input#.")
            if target in eid or target in eph or target in enm:
                e.fill(val)
                print(f"  Filled (fuzzy) '{target}' <- {val}")
                return True
        return False

    elif at == "click":
        el = page.query_selector(sel)
        if el:
            el.click()
            print(f"  Clicked {sel}")
            return True
        txt = val.lower() if val else sel.lower()
        for b in page.query_selector_all("button, a"):
            bt = (b.text_content() or "").strip().lower()
            if txt in bt:
                b.click()
                print(f"  Clicked '{txt}'")
                return True
        return False

    elif at == "select":
        page.select_option(sel, val)
        print(f"  Selected {sel} -> {val}")
        return True

    elif at == "goto":
        page.goto(val or sel, wait_until="networkidle")
        print(f"  Navigated to {val or sel}")
        return True

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 web_agent.py <url> [task]")
        sys.exit(1)

    url = sys.argv[1]
    task = sys.argv[2] if len(sys.argv) > 2 else "Fill the contact form with dummy data and submit it"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        print(f"Navigating to {url}...")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(2000)

        state = extract_page_state(page)
        print("Analyzing page and generating plan...")
        plan = get_plan(state, task)

        if not plan:
            print("Could not generate a plan.")
            browser.close()
            return

        print(f"\nPlan ({len(plan)} steps):")
        for i, step in enumerate(plan, 1):
            print(f"  {i}. {step.get('action')}: {step.get('selector', '')} {step.get('value', '')}")

        print("\nExecuting plan...")
        for step in plan:
            if not run_action(page, step):
                print(f"  Failed: {step}")
            page.wait_for_timeout(1000)

        page.wait_for_timeout(2000)
        print(f"\nFinal URL: {page.url}")
        browser.close()
        print("Done.")


if __name__ == "__main__":
    main()
