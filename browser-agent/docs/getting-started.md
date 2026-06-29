# Getting Started with Browser Agent

## Prerequisites

- Python 3.10+
- Node.js 22+ (for agent-browser CLI)
- Chromium browser

## Installation

### Option 1: Full Install (Recommended)

```bash
git clone <repo-url>
cd browser-agent
bash scripts/install.sh
```

### Option 2: Manual Install

```bash
# Install Python dependencies
pip install playwright
python3 -m playwright install chromium

# Install agent-browser CLI (Vercel)
npm install -g agent-browser
agent-browser install

# Verify
python3 scripts/browser_agent.py --help
```

## Your First Automation

```bash
# Search the web
python3 scripts/browser_agent.py \
  --url https://duckduckgo.com \
  --task "search for latest AI news" \
  --headless

# Fill a contact form
python3 scripts/browser_agent.py \
  --url https://example.com/contact \
  --task "fill the contact form with test data" \
  --headless
```

## Using with OpenClaw

Copy the skills to your OpenClaw skills directory:

```bash
cp -r skills/* ~/.openclaw/skills/
```

Then in OpenClaw config:
```json
{
  "skills": {
    "allow": ["search", "navigation", "form-fill", "extract", "auth", "signup", "monitor"]
  }
}
```

## Using with agent-browser CLI (Vercel)

```bash
# Install the agent-browser skill
npx skills add https://github.com/vercel-labs/agent-browser --skill agent-browser

# Use it directly
agent-browser goto "https://example.com"
agent-browser snapshot --json
agent-browser fill "#search" "hello world"
agent-browser click "button"
```
