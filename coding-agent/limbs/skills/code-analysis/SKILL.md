---
name: code-analysis
description: Auto-generated skill from task: Describe what each class in brain/core.py does
source: self-learning
---

# code-analysis

Learned from: Describe what each class in brain/core.py does

## Steps

1. Reliance on single-source extraction (e.g., `cls.__doc__` and `callable()` filter) without verifying the data model of the class
2. Not handling dataclass/Pydantic patterns where the class body may have no methods but significant fields defined via annotations

## When to Use

- When the task involves similar patterns
- When you see similar requirements
