---
name: code-search
description: Auto-generated skill from task: Use grep to count how many class definitions are in the codebase
source: self-learning
---

# code-search

Learned from: Use grep to count how many class definitions are in the codebase

## Steps

1. Relying on a single regex pattern to count definitions is fragile and often misses edge cases
2. Using `^` anchor assumes class definitions always start at column 0, which is false for nested classes

## When to Use

- When the task involves similar patterns
- When you see similar requirements
