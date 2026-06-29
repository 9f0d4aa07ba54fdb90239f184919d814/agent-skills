---
name: test-driven-development
description: TDD workflow with Prove-It pattern
source: cursor-skills
tags: testing, tdd, quality
when: test, tdd, unittest, pytest, testing
---

# Test-Driven Development

## Process

1. Understand the requirement
2. Write a failing test first
3. Implement minimal code to pass
4. Verify the test passes
5. Refactor if needed
6. Run all tests to confirm no regressions

## Prove-It Pattern

Always prove your code works:
- Write a test that demonstrates the expected behavior
- Run it to see it fail (red)
- Implement the code
- Run it to see it pass (green)
- Show the test output as proof

## Example

```python
# ❌ Implementing without tests
def add(a, b):
    return a + b

# ✅ TDD approach
def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```

## When to Use

- Any feature implementation
- Bug fixes (write test that reproduces bug first)
- Refactoring (tests ensure no regression)
