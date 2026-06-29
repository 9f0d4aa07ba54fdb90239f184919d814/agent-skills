# Browser Agent API Reference

## Core API

### `BrowserAgent(url, headless=True, viewport=(1280, 800))`

Initialize a browser agent instance.

**Parameters:**
- `url` (str): Starting URL
- `headless` (bool): Run in headless mode (default: True)
- `viewport` (tuple): Browser window size (width, height)

### `.navigate(url)`

Navigate to a URL.

### `.snapshot()`

Get current page state as JSON (title, URL, element refs).

### `.fill(selector, value)`

Fill a form field.

### `.click(selector)`

Click an element.

### `.select(selector, value)`

Select an option from a dropdown.

### `.screenshot(path, full_page=False)`

Take a screenshot.

### `.pdf(path)`

Save as PDF.

### `.extract_text(selector=None)`

Extract text from page or specific element.

### `.evaluate(js_code)`

Run JavaScript in the page context.

### `.close()`

Close the browser.

## Skill Methods

### Search

```python
agent.search(query, engine="duckduckgo", count=10)
agent.search_images(query)
agent.search_pdfs(query)
```

### Navigation

```python
agent.new_tab(url)
agent.switch_tab(index)
agent.close_tab()
agent.back()
agent.forward()
agent.refresh()
```

### Form Fill

```python
agent.detect_forms()
agent.smart_fill(data_dict)
agent.submit()
```

### Extract

```python
agent.extract_table(selector)
agent.extract_list(selector)
agent.extract_links()
```

### Auth

```python
agent.login(url, username, password)
agent.save_state(name)
agent.load_state(name)
agent.clear_state()
```

### Signup

```python
agent.signup(url, data=None)
agent.accept_terms()
agent.onboard(steps=[])
```

### Monitor

```python
agent.watch(url, interval=60, selector=None, callback=None)
agent.poll(url, interval=30)
agent.diff(snapshot1, snapshot2)
```

## CLI Arguments

```
python3 scripts/browser_agent.py [OPTIONS]

Options:
  --url TEXT         Starting URL (required)
  --task TEXT        Task description (required)
  --headless         Run headless (default: True)
  --visible          Show browser window
  --viewport WxH     Browser viewport size (default: 1280x800)
  --timeout SEC      Page load timeout (default: 30)
  --plan-only        Only generate the plan, don't execute
  --verbose          Print detailed logs
  --output FILE      Save results to file
```
