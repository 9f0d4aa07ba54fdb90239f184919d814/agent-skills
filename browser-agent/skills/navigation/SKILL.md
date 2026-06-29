---
name: navigation
description: Page navigation, tab management, session control, and history
commands:
  - goto
  - back
  - forward
  - tabs
  - sessions
  - refresh
---

# Navigation Skill

Control page navigation, manage multiple tabs/sessions, and handle history.

## When to Use

- Navigating to URLs
- Managing multiple open pages
- Working with browser history
- Handling sessions across different logins

## Commands

### `goto <url>`

Navigate to a URL. Always wait for network idle.

```bash
agent-browser goto "https://example.com"
agent-browser wait --load networkidle
agent-browser snapshot --json
```

### `back` / `forward`

Browser history navigation.

### `tabs`

List and switch between open tabs.

```bash
agent-browser tabs --json
agent-browser switch --tab 1
```

### `sessions`

Isolated browser sessions for multi-account workflows.

```bash
# Create separate sessions
agent-browser --session admin goto "https://admin.example.com"
agent-browser --session user goto "https://user.example.com"
```

## Examples

```python
# Multi-tab research
browser.goto("https://example.com")
browser.new_tab("https://other.com")
tabs = browser.get_tabs()
browser.switch_tab(tabs[0])

# Session isolation
with browser.session("admin"):
    browser.goto("https://dashboard.example.com")
    browser.login(user="admin", pass="****")

with browser.session("user"):
    browser.goto("https://app.example.com")
```
