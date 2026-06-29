---
name: signup
description: Account registration, email verification, onboarding workflows
commands:
  - signup
  - verify-email
  - onboard
  - accept-terms
---

# Signup Skill

Automate account registration flows including form filling, email verification, terms acceptance, and onboarding.

## When to Use

- Creating new accounts
- Registering for services
- Completing onboarding flows
- Handling email verification

## Commands

### `signup <url> [data]`

Navigate to signup page, fill registration form with provided or generated data.

```bash
agent-browser goto "https://example.com/signup"
agent-browser fill "#name" "Test User"
agent-browser fill "#email" "test@example.com"
agent-browser fill "#password" "SecurePass1!"
agent-browser select "select#plan" "free"
agent-browser click "button[type=submit]"
```

### `verify-email [code]`

Check for verification links in email (requires email access) or enter verification code.

### `onboard [steps]`

Complete multi-step onboarding wizards and tutorials.

### `accept-terms`

Accept terms of service and privacy policy checkboxes.

## Data Generation

Signup skill can auto-generate registration data:
- Username: `test_user_<random>`
- Email: `test_<random>@mailinator.com`
- Password: Auto-generated secure password
- Profile: Name, bio, preferences

## Examples

```python
# Quick signup with auto-generated data
browser.signup("https://app.example.com/register")

# Signup with custom data
browser.signup("https://example.com/signup", {
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "password": "MyP@ssw0rd!",
    "plan": "premium"
})

# Multi-step onboarding
browser.accept_terms()
browser.onboard(steps=["profile", "preferences", "integrations"])
```
