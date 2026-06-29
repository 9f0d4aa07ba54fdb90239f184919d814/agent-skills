"""
Token counting and smart truncation.
Uses tiktoken if available, falls back to character-based estimation.
"""

import re
from functools import lru_cache


@lru_cache(maxsize=1)
def _has_tiktoken() -> bool:
    try:
        import tiktoken
        return True
    except ImportError:
        return False


def count_tokens(text: str) -> int:
    if _has_tiktoken():
        import tiktoken
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except:
            pass
    return len(text) // 4 + 10


def truncate_smart(text: str, max_tokens: int = 2000) -> str:
    """Keep the most important parts: beginning and end."""
    estimated = count_tokens(text)
    if estimated <= max_tokens:
        return text

    chars = len(text)
    keep_ratio = max_tokens / estimated

    if keep_ratio < 0.3:
        head_chars = int(chars * keep_ratio * 0.7)
        tail_chars = int(chars * keep_ratio * 0.3)
        return text[:head_chars] + "\n\n[...truncated...]\n\n" + text[-tail_chars:]
    else:
        return text[:int(chars * keep_ratio)]


def truncate_lines(text: str, max_lines: int = 100) -> str:
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    head = max_lines // 2
    tail = max_lines // 2
    return "\n".join(lines[:head] + [f"... ({len(lines) - head - tail} lines omitted) ..."] + lines[-tail:])


def chunk_text(text: str, max_chunk_tokens: int = 3000) -> list[str]:
    """Split text into chunks that fit within token limit."""
    estimated = count_tokens(text)
    if estimated <= max_chunk_tokens:
        return [text]

    lines = text.split("\n")
    chunks = []
    current = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)
        if current_tokens + line_tokens > max_chunk_tokens and current:
            chunks.append("\n".join(current))
            current = []
            current_tokens = 0
        current.append(line)
        current_tokens += line_tokens

    if current:
        chunks.append("\n".join(current))
    return chunks


class ResponseCache:
    def __init__(self, max_size: int = 50):
        self._cache: dict = {}
        self._max_size = max_size

    def get(self, key: str) -> str:
        return self._cache.get(key)

    def set(self, key: str, value: str):
        if len(self._cache) >= self._max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = value

    def make_key(self, prompt: str, system: str = "") -> str:
        return str(hash(prompt + system))

    def clear(self):
        self._cache.clear()
