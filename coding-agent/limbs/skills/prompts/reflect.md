---
name: reflection-prompt
description: Self-reflection and learning after each task
source: built-in
tags: learning, core
---

# Reflection Strategy

After each task, analyze:
1. What worked well? (keep doing this)
2. What failed? (avoid or fix)
3. What patterns emerged? (track for skill promotion)
4. What could be improved? (actionable items)

## Analysis Framework

- **Tool selection**: Did we pick the right tool?
- **Path accuracy**: Were all paths correct?
- **Error handling**: Did we recover well from failures?
- **Completeness**: Did we fully satisfy the task?
- **Efficiency**: Could we have done it in fewer steps?

## Output Format

Return JSON with:
- "lessons": array of specific, actionable lessons
- "patterns": array of recurring approaches detected
- "improvements": array of how to do better
- "importance": float 0-1, how important this task was
- "skills": array of skill names that could be created
