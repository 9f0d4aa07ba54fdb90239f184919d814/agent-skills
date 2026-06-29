---
name: auth
description: Login flows, session persistence, multi-account management, and SSO
commands:
  - login
  - logout
  - state-save
  - state-load
  - cookies
---

# Auth Skill

Handle authentication flows: login forms, session management, cookie persistence, and multi-account switching.

## When to Use

- Logging into websites
- Saving authenticated sessions
- Restoring sessions without re-login
- Managing multiple accounts
- Handling SSO / OAuth flows

## Commands

### `login <url> <username> <password> [selectors]`

Automate login flow. Detects login form fields automatically.

```bash
# Standard login
agent-browser goto "https://example.com/login"
agent-browser fill "#email" "user@example.com"
agent-browser fill "#password" "mypassword"
agent-browser click "button[type=submit]"
agent-browser wait --load networkidle
```

### `state-save <name>`

Save the current browser state (cookies, localStorage) for later reuse.

```bash
agent-browser state save my-session.json
```

### `state-load <name>`

Load a previously saved browser state to restore session.

```bash
agent-browser goto "https://example.com"
agent-browser state load my-session.json
agent-browser refresh
```

### `cookies [--json]`

View or export cookies for the current page.

## Session File Location

Sessions are saved to `~/.agent-browser/sessions/` by default.

## Examples

```python
# Login and save session
browser.login("https://example.com/login", "user@test.com", "pass123")
browser.save_state("my-site")

# Later: restore session
browser.load_state("my-site")
browser.goto("https://example.com/dashboard")
# Already authenticated!

# Multi-account
browser.login("https://app.com", "admin@co.com", "admin123")
browser.save_state("admin-account")

browser.login("https://app.com", "user@co.com", "user123")
browser.save_state("user-account")
```
