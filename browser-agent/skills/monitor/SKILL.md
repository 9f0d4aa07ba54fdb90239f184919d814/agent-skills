---
name: monitor
description: Page watching, change detection, polling, and alerts
commands:
  - watch
  - poll
  - diff
  - alert
---

# Monitor Skill

Watch web pages for changes, poll endpoints, detect diffs, and trigger alerts.

## When to Use

- Monitoring prices on e-commerce sites
- Watching for status changes
- Tracking content updates
- Polling APIs or dashboards
- Getting notified of changes

## Commands

### `watch <url> [interval=60s] [selector]`

Watch a page for changes at a regular interval. Optionally scope to a specific element.

```bash
agent-browser watch "https://example.com/status" --every 30s --selector ".status-badge"
```

### `poll <url> [interval]`

Poll a URL at regular intervals and track responses.

### `diff [before] [after]`

Compare two page snapshots and show what changed.

### `alert [condition]`

Set up an alert condition that triggers when content matches or changes in a specific way.

## Examples

```python
# Watch a page for changes
browser.watch("https://example.com/prices", interval=60, selector=".price-tag")

# Poll an API endpoint
browser.poll("https://api.example.com/status", interval=30)

# Diff two versions
browser.goto("https://example.com")
snapshot1 = browser.snapshot()
# ... time passes ...
browser.goto("https://example.com")
snapshot2 = browser.snapshot()
diff = browser.diff(snapshot1, snapshot2)
```
