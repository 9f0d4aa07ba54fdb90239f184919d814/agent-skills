#!/usr/bin/env python3
"""
Skill Discovery Agent - Searches, evaluates, and dynamically loads skills
from ClawHub, skills.sh, GitHub, and local directories.
Picks the best skills for any task and makes them available.
"""

import sys
import os
import json
import re
import subprocess
import urllib.request
import urllib.parse
import requests
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "skills"
CLONE_DIR = Path.home() / ".browser-agent" / "cloned-skills"

OPCODE_BIN = "/usr/local/share/nvm/versions/node/v20.11.1/bin/opencode"

CLAWHUB_API = "https://hub.openclaw.ai/api/skills"
SKILLS_SH_API = "https://skills.sh/api/skills"



def ask_llm(prompt: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(
            [OPCODE_BIN, "run", prompt],
            capture_output=True, text=True, timeout=timeout
        )
        out = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', r.stdout).strip()
        return out
    except:
        return ""



def search_skills(query: str, sources: list[str] | None = None) -> list[dict]:
    results = []
    for source in sources or ["clawhub", "skillssh", "github"]:
        try:
            if source == "clawhub":
                url = f"{CLAWHUB_API}?q={urllib.parse.quote(query)}&limit=20"
                data = requests.get(url, timeout=10).json()
                for s in data.get("skills", data.get("results", data if isinstance(data, list) else [])):
                    name = s.get("name", s.get("title", s.get("slug", "")))
                    desc = s.get("description", s.get("summary", ""))
                    if name and desc:
                        results.append({"name": name, "description": desc, "source": "clawhub", "ref": s})
            elif source == "skillssh":
                url = f"{SKILLS_SH_API}?q={urllib.parse.quote(query)}"
                data = requests.get(url, timeout=10).json()
                items = data if isinstance(data, list) else data.get("results", [])
                for s in items:
                    results.append({
                        "name": s.get("name", s.get("title", "")),
                        "description": s.get("description", ""),
                        "source": "skills.sh",
                        "ref": s
                    })
            elif source == "github":
                gq = urllib.parse.quote(f"{query} skill SKILL.md")
                url = f"https://api.github.com/search/repositories?q={gq}&sort=stars&per_page=15"
                headers = {"Accept": "application/vnd.github.v3+json"}
                data = requests.get(url, headers=headers, timeout=10).json()
                for repo in data.get("items", []):
                    name = repo.get("name", "")
                    desc = repo.get("description", "") or ""
                    results.append({
                        "name": name,
                        "description": desc,
                        "source": "github",
                        "stars": repo.get("stargazers_count", 0),
                        "url": repo.get("html_url", ""),
                        "ref": repo
                    })
        except:
            continue

    seen = set()
    unique = []
    for r in results:
        key = r["name"]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique



def rank_skills(skills: list[dict], task: str, top_n: int = 5) -> list[dict]:
    if not skills:
        return []
    desc = "\n".join(f"- {s['name']}: {s['description'][:200]}" for s in skills[:25])
    prompt = f"""Task: {task}

Available skills:
{desc}

Rank the top {top_n} most useful skills for this task. Return a JSON array of skill names only.
Example: ["skill-name-1", "skill-name-2"]
Return ONLY the JSON array."""
    response = ask_llm(prompt)
    try:
        ranked = json.loads(re.sub(r'```(?:json)?\n?', '', response).strip())
        ordered = []
        for name in ranked:
            for s in skills:
                if s["name"].lower() == name.lower() or name.lower() in s["name"].lower():
                    ordered.append(s)
                    break
        if ordered:
            return ordered[:top_n]
    except: pass
    return skills[:top_n]



def install_skill(skill: dict) -> bool:
    name = skill["name"]
    target = SKILLS_DIR / name
    target.mkdir(parents=True, exist_ok=True)
    md_path = target / "SKILL.md"
    if md_path.exists():
        return True
    content = f"""---
name: {name}
description: {skill.get('description', 'Auto-discovered skill')}
source: {skill.get('source', 'unknown')}
---

# {name}

Auto-discovered from {skill.get('source', 'unknown')}.

{skill.get('description', '')}

## Usage

This skill was dynamically discovered for your task.
"""
    md_path.write_text(content)
    return True



def discover_and_install(task: str, top_n: int = 5) -> list[dict]:
    keywords = extract_keywords(task)
    all_skills = []
    for kw in keywords[:3]:
        found = search_skills(kw)
        all_skills.extend(found)
    ranked = rank_skills(all_skills, task, top_n)
    installed = []
    for s in ranked:
        if install_skill(s):
            installed.append(s)
    return installed



def extract_keywords(task: str) -> list[str]:
    prompt = f"""From this task, extract 3-5 search keywords to find relevant skills/tools.
Task: {task}
Return a JSON array of keyword strings. Example: ["web scraping", "browser automation", "form filling"]
Return ONLY the JSON array."""
    response = ask_llm(prompt)
    try:
        return json.loads(re.sub(r'```(?:json)?\n?', '', response).strip())
    except:
        return [task]



def get_loaded_skills() -> list[dict]:
    skills = []
    for d in SKILLS_DIR.iterdir():
        if d.is_dir():
            md = d / "SKILL.md"
            if md.exists():
                content = md.read_text()
                desc = ""
                for line in content.split("\n"):
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break
                skills.append({"name": d.name, "description": desc, "path": str(md)})
    return skills



def build_context(task: str, skills: list[dict]) -> str:
    ctx = f"Task: {task}\n\nLoaded skills:\n"
    for s in skills:
        content = Path(s["path"]).read_text()
        ctx += f"\n=== {s['name']} ===\n{content[:500]}\n"
    return ctx



def main():
    if len(sys.argv) < 2:
        task = input("Enter task: ")
    else:
        task = " ".join(sys.argv[1:])

    print(f"Task: {task}")
    print("Extracting keywords...")
    keywords = extract_keywords(task)
    print(f"Keywords: {keywords}")

    print("Searching for skills...")
    all_found = []
    for kw in keywords[:3]:
        found = search_skills(kw)
        all_found.extend(found)
        print(f"  '{kw}': {len(found)} skills found")

    print(f"\nTotal unique: {len(all_found)}")
    print("Ranking best skills for task...")
    best = rank_skills(all_found, task)
    print(f"\nTop {len(best)} skills:")
    for i, s in enumerate(best, 1):
        stars = f" ({s.get('stars', '')}★)" if s.get('stars') else ""
        print(f"  {i}. {s['name']}{stars} [{s.get('source', '')}]")
        print(f"     {s['description'][:120]}")

    print("\nInstalling...")
    installed = []
    for s in best:
        if install_skill(s):
            installed.append(s)
            print(f"  ✓ {s['name']}")

    ctx = build_context(task, get_loaded_skills())
    print(f"\nContext built ({len(ctx)} chars)")

    print("\nReady. Run: python3 browser_agent.py --url <url> --task \"<task>\"")


if __name__ == "__main__":
    main()
