---
name: form-fill
description: Smart form detection, field filling, option selection, and submission
commands:
  - fill
  - select
  - submit
  - detect-forms
  - clear
---

# Form Fill Skill

Detect forms on a page, identify fields, fill them intelligently, select options, and submit.

## When to Use

- Filling out contact forms
- Submitting search queries
- Creating accounts (use with signup skill)
- Filling checkout/payment forms
- Any form interaction

## Commands

### `detect-forms`

Scan page for all forms and list their fields with types, labels, and placeholders.

```bash
agent-browser snapshot --json | extract forms
```

### `fill <selector> <value>`

Fill a form field. Prefer CSS selectors (id, class, attributes).

```bash
# By ID
agent-browser fill "#name" "John Doe"

# By placeholder
agent-browser fill "input[placeholder='Enter email']" "john@example.com"
```

### `select <selector> <value>`

Select an option from a dropdown.

```bash
agent-browser select "select#country" "US"
```

### `submit`

Submit a form. Usually clicking the submit button.

```bash
agent-browser click "button[type=submit]"
```

## Smart Fill Rules

The system auto-generates realistic dummy data based on field labels:
- `name`, `fullname` → "John Doe"
- `email` → "john.doe@example.com"
- `phone`, `tel` → "+1 234 567 8900"
- `address` → "123 Main St, Springfield"
- `message`, `comments` → "Test message from automation"
- `password` → "TestPass123!"
- `search` → Uses the user's search query

## Examples

```python
# Detect and fill a contact form
forms = browser.detect_forms()
form = forms[0]
browser.fill(form.fields[0].selector, "Jane Smith")
browser.fill(form.fields[1].selector, "jane@example.com")
browser.click("button[type=submit]")

# Smart fill based on labels
browser.smart_fill({
    "name": "Jane Smith",
    "email": "jane@test.com",
    "message": "Hello, this is a test."
})
```
