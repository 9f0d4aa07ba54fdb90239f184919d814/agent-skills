---
name: incremental-implementation
description: Build in small, verifiable slices
source: cursor-skills
tags: implementation, workflow
when: implement, build, create, develop
---

# Incremental Implementation

## Strategy

Build features in small, verifiable slices instead of one large change:

1. **Slice 1**: Core data structures / types
2. **Slice 2**: Basic functionality (happy path)
3. **Slice 3**: Error handling and edge cases
4. **Slice 4**: Integration with existing code
5. **Slice 5**: Tests and documentation

## After Each Slice

- Verify the code works
- Run existing tests
- Commit the working slice

## Benefits

- Easy to roll back if something goes wrong
- Clear progress visible at each step
- Each slice is reviewable independently
- Reduces the risk of large breaking changes
