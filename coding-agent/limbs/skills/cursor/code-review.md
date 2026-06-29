---
name: code-review-and-quality
description: Five-axis code review framework
source: cursor-skills
tags: review, quality, best-practices
when: review, code review, quality, audit
---

# Code Review & Quality

## Five-Axis Review

1. **Correctness**: Does the code do what it should?
2. **Performance**: Is it efficient? Any obvious bottlenecks?
3. **Security**: Are there injection risks, exposed secrets, or unsafe patterns?
4. **Maintainability**: Is it readable? Follows project conventions?
5. **Testability**: Is it tested? Easy to test?

## Checklist

- [ ] No hardcoded secrets or credentials
- [ ] Error handling is appropriate (not silent catches)
- [ ] Follows project naming conventions
- [ ] No dead code or commented-out code
- [ ] Dependencies are necessary and appropriate
- [ ] Logging is useful (not excessive, not missing)
