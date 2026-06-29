# Examples

## Example 1: Search and Extract

```python
from browser_agent import BrowserAgent

agent = BrowserAgent(headless=True)

# Search for information
results = agent.search("Python web scraping tools 2026", count=5)
for r in results:
    print(f"{r.title}: {r.url}")

# Open a result and take screenshot
agent.goto(results[0].url)
agent.screenshot("result.png", full_page=True)

agent.close()
```

## Example 2: Form Fill Automation

```python
from browser_agent import BrowserAgent

agent = BrowserAgent(
    url="https://kasabunikhilgoud.online",
    headless=True
)

# Navigate to contact section
agent.goto("https://kasabunikhilgoud.online/#contact")
agent.wait(2)

# Detect and fill forms
forms = agent.detect_forms()
print(f"Found {len(forms)} forms")

# Smart fill
agent.smart_fill({
    "name": "Test User",
    "email": "test@example.com",
    "phone": "9876543210",
    "message": "This is an automated test message."
})

# Submit
agent.click("button[type=submit]")
agent.wait(3)
agent.screenshot("submitted.png")

agent.close()
```

## Example 3: Multi-Tab Research

```python
from browser_agent import BrowserAgent

agent = BrowserAgent(headless=True)

# Open multiple tabs for comparison
agent.goto("https://github.com/trending/python")
agent.new_tab("https://news.ycombinator.com")
agent.new_tab("https://www.reddit.com/r/Python/")

# Switch and extract
tabs = agent.get_tabs()
for tab in tabs:
    agent.switch_tab(tab)
    title = agent.get_title()
    links = agent.extract_links()
    print(f"{title}: {len(links)} links")

agent.close()
```

## Example 4: Login and Monitor

```python
from browser_agent import BrowserAgent

agent = BrowserAgent(headless=True)

# Login
agent.login("https://github.com/login", "user@example.com", "mypassword")
agent.save_state("github-session")

# Navigate
agent.goto("https://github.com/notifications")
notifications = agent.extract_list(".notification")
print(f"You have {len(notifications)} notifications")

agent.close()
```

## Example 5: Download All PDFs from a Page

```python
from browser_agent import BrowserAgent
import urllib.parse

agent = BrowserAgent(headless=True)
agent.goto("https://example.com/resources")

# Find all PDF links
links = agent.extract_links()
pdfs = [l for l in links if l.endswith('.pdf')]

for pdf_url in pdfs:
    filename = urllib.parse.urlparse(pdf_url).path.split('/')[-1]
    print(f"Downloading {filename}...")
    agent.download(pdf_url, filename)

agent.close()
```

## Example 6: Watch for Changes

```python
from browser_agent import BrowserAgent

agent = BrowserAgent(headless=True)

def on_change(diff):
    print(f"Change detected: {diff}")

# Watch a page every 60 seconds
agent.watch(
    url="https://example.com/status",
    interval=60,
    selector=".status-indicator",
    callback=on_change
)
```

## CLI Usage Examples

```bash
# Basic search
python3 scripts/browser_agent.py \
  --url https://duckduckgo.com \
  --task "search for openclaw skills tutorial"

# Contact form fill
python3 scripts/browser_agent.py \
  --url https://kasabunikhilgoud.online \
  --task "fill the contact form with dummy data"

# Screenshot a page
python3 scripts/browser_agent.py \
  --url https://example.com \
  --task "take a full page screenshot" \
  --output screenshot.png

# Login workflow
python3 scripts/browser_agent.py \
  --url https://github.com/login \
  --task "login and save session"
```
