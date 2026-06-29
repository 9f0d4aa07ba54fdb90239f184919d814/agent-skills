---
name: planning-prompt
description: Step-by-step planning strategy
source: built-in
tags: planning, core
---

# Planning Strategy

## Process

1. **Understand**: What is the user asking? Is it clear? If not, ask.
2. **Explore**: If the task involves an unfamiliar codebase, use `codebase_overview` or `tree` first
3. **Plan**: Break into minimal self-contained steps
4. **Execute**: Run each step and check results
5. **Verify**: Confirm the outcome matches expectations
6. **Learn**: Extract lessons for future tasks

## Plan Quality Rules

- Each step uses ONE tool only
- Steps are SELF-CONTAINED (no dependencies on previous step output)
- Use absolute paths throughout
- Prefer the simplest approach
- Include verification at the end

## When Things Go Wrong

- If a tool fails with "not found": check the path exists
- If a tool fails with "timeout": the operation is too complex, simplify
- If a tool fails with "syntax error": fix the code
- If a tool fails repeatedly: try a completely different approach

## Response Format

Return ONLY a JSON array. Each element:
{"tool": "tool_name", "args": {"key": "value"}, "desc": "what this step does"}
