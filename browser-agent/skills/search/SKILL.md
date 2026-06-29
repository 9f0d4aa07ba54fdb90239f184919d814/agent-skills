---
name: search
description: Multi-engine web search with result extraction and filtering
commands:
  - search
  - search-images
  - search-news
  - search-pdfs
---

# Search Skill

Search the web across multiple search engines. Extracts titles, URLs, snippets, and metadata from results.

## When to Use

- User asks to search for something
- Need to find information on the web
- Need to find PDFs, documents, or specific file types
- Need images or news results

## Commands

### `search <query> [engine=duckduckgo] [count=10]`

Search the web. Prefer DuckDuckGo to avoid CAPTCHA issues.

```bash
agent-browser goto "https://duckduckgo.com/?q=example+search"
agent-browser snapshot --json | extract results
```

### `search-images <query>`

Search for images.

### `search-news <query>`

Search for news results.

### `search-pdfs <query>`

Search for PDF documents. Append `filetype:pdf` to queries.

## Examples

```python
# Search for something
result = browser.search("best ai agents 2026", engine="duckduckgo", count=5)
for r in result.results:
    print(f"{r.title}: {r.url}")

# Search for PDFs
pdfs = browser.search("machine learning algorithms filetype:pdf")
```

## Multi-Engine Support

| Engine | URL | Notes |
|--------|-----|-------|
| DuckDuckGo | `https://duckduckgo.com/?q=` | Recommended - no CAPTCHA |
| Google | `https://google.com/search?q=` | May get CAPTCHA in headless |
| Bing | `https://bing.com/search?q=` | Moderate CAPTCHA risk |
| Brave | `https://search.brave.com/search?q=` | Low CAPTCHA risk |
