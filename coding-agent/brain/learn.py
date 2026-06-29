"""
Self-Learning Loop - Hermes-inspired.
After every task: reflect -> extract patterns -> promote patterns to skills.
"""

import json
from pathlib import Path
from .core import Brain
from datetime import datetime

SKILLS_DIR = Path(__file__).parent.parent / "limbs" / "skills"


class LearningLoop:
    def __init__(self, brain: Brain):
        self.brain = brain
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def after_task(self, task: str, actions: list[dict], results: list[str], errors: list[str]):
        # Skip reflection for trivial tasks (1-2 steps, no errors, simple)
        if len(actions) <= 2 and not errors:
            for r in results:
                if r and len(r) < 50:  # Very simple result, no need to reflect
                    return
        if not errors and len(actions) <= 1:
            return  # Single successful step needs no reflection

        reflection = self.brain.reflect(task, actions, str(results[-1]) if results else "", "\n".join(errors))
        if not isinstance(reflection, dict):
            return

        for lesson in reflection.get("lessons", []):
            lesson_str = str(lesson) if not isinstance(lesson, str) else lesson
            self._save_lesson(lesson_str, task)
            self.brain.learn(lesson_str)

        for pattern in reflection.get("patterns", []):
            if isinstance(pattern, str):
                self._track_pattern(pattern)

        if reflection.get("skills"):
            for skill in reflection["skills"][:2]:
                if isinstance(skill, dict):
                    self._create_skill(skill.get("name", "unnamed"), task, reflection.get("patterns", []))
                else:
                    self._create_skill(str(skill), task, reflection.get("patterns", []))

    def _save_lesson(self, lesson: str, task: str):
        if not lesson or len(lesson) < 5:
            return
        lessons_file = SKILLS_DIR / "lessons.md"
        entry = f"- [{datetime.now().strftime('%Y-%m-%d')}] {lesson} (from: {task[:80]})\n"
        if lessons_file.exists():
            content = lessons_file.read_text()
            if lesson[:60] not in content:
                lessons_file.write_text(entry + content)
        else:
            lessons_file.write_text(f"# Lessons Learned\n\n{entry}")

    def _track_pattern(self, pattern_text: str):
        if not pattern_text or len(pattern_text) < 5:
            return
        patterns_file = SKILLS_DIR / "patterns.json"
        data = {"patterns": [], "counts": {}}
        if patterns_file.exists():
            try:
                data = json.loads(patterns_file.read_text())
            except:
                pass
        key = str(pattern_text)[:100]
        data["counts"][key] = data["counts"].get(key, 0) + 1
        if data["counts"][key] >= 3 and key not in [p.get("text","") for p in data["patterns"]]:
            data["patterns"].append({"text": key, "count": data["counts"][key]})
            self._create_skill_from_pattern(key)
        patterns_file.write_text(json.dumps(data, indent=2))

    def _skill_exists(self, name: str) -> bool:
        """Check if a skill with this name (or similar) already exists."""
        name_lower = name.lower().replace("-", " ").strip()
        if not SKILLS_DIR.exists():
            return False
        for d in SKILLS_DIR.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                existing_name = d.name.lower().replace("-", " ").strip()
                # Exact or near-exact match
                if existing_name == name_lower or name_lower in existing_name or existing_name in name_lower:
                    return True
        return False

    def _create_skill(self, name: str, task: str, patterns: list):
        name = name.lower().replace(" ", "-").replace("_", "-")[:40].strip("-")
        if not name or self._skill_exists(name):
            return
        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        steps_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(patterns[:5])) if patterns else "1. Follow standard approach"
        content = f"""---
name: {name}
description: Auto-generated skill from task: {task[:100]}
source: self-learning
---

# {name}

Learned from: {task}

## Steps

{steps_text}

## When to Use

- When the task involves similar patterns
- When you see similar requirements
"""
        md_path = skill_dir / "SKILL.md"
        if not md_path.exists():
            md_path.write_text(content)

    def _create_skill_from_pattern(self, pattern: str):
        name = pattern.lower().replace(" ", "-")[:40].strip("-")
        if not name or self._skill_exists(name):
            return
        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        content = f"""---
name: {name}
description: Skill promoted from repeated pattern
source: self-promotion
---

# {name}

Pattern detected 3+ times: {pattern}

## Usage

Apply this pattern when the situation matches.

## Steps

1. Detect the pattern match
2. Apply the known solution
3. Verify the result
"""
        md_path = skill_dir / "SKILL.md"
        if not md_path.exists():
            md_path.write_text(content)

    def get_skills(self) -> list[dict]:
        skills = []
        if not SKILLS_DIR.exists():
            return skills
        for d in SKILLS_DIR.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                try:
                    content = (d / "SKILL.md").read_text()
                    desc = ""
                    for line in content.split("\n"):
                        if line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                    skills.append({"name": d.name, "description": desc or "auto-generated skill"})
                except:
                    pass
        return skills

    def find_relevant_skills(self, task: str) -> list[dict]:
        skills = self.get_skills()
        if not skills or not task:
            return []
        task_lower = task.lower()
        relevant = []
        for s in skills:
            name_match = s["name"].replace("-", " ") in task_lower
            desc_match = s["description"][:30].lower() in task_lower
            if name_match or desc_match:
                relevant.append(s)
        return relevant[:3]
