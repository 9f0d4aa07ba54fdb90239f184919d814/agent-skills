"""
LIMB: Skills Loader
Parse, match, and execute SKILL.md files from multiple directories.
Supports Cursor-inspired skills, system prompts, and self-learned skills.
"""

import json, re
from pathlib import Path
from typing import Optional

SKILLS_DIR = Path(__file__).parent
SKILL_SOURCES = [
    ("cursor", SKILLS_DIR / "cursor"),
    ("prompts", SKILLS_DIR / "prompts"),
    ("learned", SKILLS_DIR),
]


class Skill:
    def __init__(self, path: Path, source: str = ""):
        self.path = path
        self.name = path.stem
        self.description = ""
        self.source = source or "custom"
        self.steps: list[str] = []
        self.when: list[str] = []
        self.tags: list[str] = []
        self.content: str = ""
        self._parse()

    def _parse(self):
        content = self.path.read_text()
        self.content = content
        fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            for line in fm.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip().lower()
                    val = val.strip().strip('"').strip("'")
                    if key == "name":
                        self.name = val
                    elif key == "description":
                        self.description = val
                    elif key == "source":
                        self.source = val
                    elif key == "tags":
                        self.tags = [t.strip() for t in val.split(",")]
                    elif key == "when":
                        self.when = [w.strip() for w in val.split(",")]

        body = content
        if fm_match:
            body = content[fm_match.end():]

        in_steps = False
        for line in body.split("\n"):
            s = line.strip()
            if s.lower().startswith("## steps") or s.lower().startswith("## process"):
                in_steps = True
                continue
            if s.lower().startswith("## ") and in_steps:
                in_steps = False
                continue
            if in_steps and s:
                step = re.sub(r'^\d+\.\s*', '', s)
                if step:
                    self.steps.append(step)

    def matches(self, task: str) -> float:
        task_lower = task.lower()
        score = 0.0
        name_parts = self.name.replace("-", " ").lower()
        if name_parts in task_lower:
            score += 0.5
        if self.description.lower()[:30] in task_lower:
            score += 0.3
        for tag in self.tags:
            if tag.lower() in task_lower:
                score += 0.2
        for w in self.when:
            if w.lower() in task_lower:
                score += 0.25
        return min(score, 1.0)

    def to_prompt(self) -> str:
        steps_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(self.steps[:5]))
        return f"""
Skill: {self.name}
Description: {self.description}
Steps:
{steps_str}
"""

    def __repr__(self):
        return f"Skill({self.name}, src={self.source}, tags={self.tags})"


class SkillsLoader:
    def __init__(self):
        self._skills: list[Skill] = []
        self._load_all()

    def _load_all(self):
        for source_name, source_dir in SKILL_SOURCES:
            if not source_dir.exists():
                continue
            for f in source_dir.iterdir():
                if f.suffix.lower() in (".md",) and not f.name.startswith("_"):
                    try:
                        skill = Skill(f, source=source_name)
                        self._skills.append(skill)
                    except Exception:
                        pass
        # Also load from learned skill directories
        if SKILLS_DIR.exists():
            for d in SKILLS_DIR.iterdir():
                if d.is_dir() and (d / "SKILL.md").exists():
                    try:
                        skill = Skill(d / "SKILL.md", source="learned")
                        if not any(s.name == skill.name for s in self._skills):
                            self._skills.append(skill)
                    except Exception:
                        pass

    def get_all(self) -> list[Skill]:
        return self._skills

    def get_by_name(self, name: str) -> Optional[Skill]:
        name_lower = name.lower()
        for s in self._skills:
            if s.name.lower() == name_lower:
                return s
        return None

    def search(self, query: str) -> list[Skill]:
        query_lower = query.lower()
        results = []
        for s in self._skills:
            score = s.matches(query)
            if score > 0:
                results.append((s, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in results]

    def by_tag(self, tag: str) -> list[Skill]:
        tag_lower = tag.lower()
        return [s for s in self._skills if tag_lower in [t.lower() for t in s.tags]]

    def by_source(self, source: str) -> list[Skill]:
        return [s for s in self._skills if s.source == source]

    def get_prompt_for(self, task: str) -> str:
        matches = self.search(task)[:3]
        if not matches:
            return ""
        parts = ["Relevant skills:"]
        for m in matches:
            if m.steps:
                parts.append(m.to_prompt())
        return "\n".join(parts)

    def categories(self) -> dict:
        cats = {}
        for s in self._skills:
            for tag in s.tags:
                tag = tag.strip()
                if tag:
                    if tag not in cats:
                        cats[tag] = []
                    cats[tag].append(s.name)
        return cats

    def stats(self) -> dict:
        return {
            "total": len(self._skills),
            "by_source": {src: len(self.by_source(src)) for _, src in SKILL_SOURCES},
            "categories": {k: len(v) for k, v in self.categories().items()}
        }
