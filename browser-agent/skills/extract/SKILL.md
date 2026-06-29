---
name: extract
description: Data extraction from pages including screenshots, PDFs, tables, lists, and structured data
commands:
  - extract
  - snapshot
  - screenshot
  - pdf
  - table
  - list
---

# Extract Skill

Extract data from web pages: text content, tables, lists, structured data, screenshots, and PDFs.

## When to Use

- Scraping data from websites
- Taking screenshots of pages
- Saving pages as PDFs
- Extracting tables and lists
- Capturing page snapshots for analysis

## Commands

### `snapshot [--json]`

Capture the current page state including accessibility tree with element refs.

```bash
agent-browser snapshot --json
```

### `screenshot [--full-page] [path]`

Take a screenshot of the current page.

```bash
agent-browser screenshot --full-page --output page.png
```

### `pdf [path]`

Save current page as PDF.

```bash
agent-browser pdf --output page.pdf
```

### `extract <selector>`

Extract text or data from specific elements.

```bash
agent-browser eval "document.querySelector('article').innerText"
```

### `table <selector>`

Extract table data as structured JSON.

## Examples

```python
# Extract all links
links = browser.extract('a[href]', attr='href')

# Screenshot full page
browser.screenshot("fullpage.png", full_page=True)

# Save as PDF
browser.pdf("report.pdf")

# Extract table to CSV
data = browser.extract_table("table#grades")
import csv
# ... save data to CSV

# Extract structured data
items = browser.extract_list(".product-card")
for item in items:
    print(item.title, item.price)
```
