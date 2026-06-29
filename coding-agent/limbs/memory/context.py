"""
Google-style Context Manager
Tiered: hot (current turn) -> warm (session) -> cold (long-term summaries)
Auto-compacts by summarizing older turns to minimize tokens.
"""

import json, time
from dataclasses import dataclass, field
from .tokenizer import count_tokens, truncate_smart


@dataclass
class Turn:
    role: str
    content: str
    time: float = field(default_factory=time.time)
    tokens: int = 0


class Context:
    def __init__(self, max_hot_tokens: int = 2500, max_warm_turns: int = 5):
        self.hot: list[Turn] = []
        self.warm: list[Turn] = []
        self.summaries: list[str] = []
        self.max_hot_tokens = max_hot_tokens
        self.max_warm_turns = max_warm_turns

    def add(self, role: str, content: str):
        content = truncate_smart(content, 1500)
        self.hot.append(Turn(role, content))
        self._maybe_compact()

    def _estimate_tokens(self, text: str) -> int:
        return count_tokens(text)

    def _maybe_compact(self):
        hot_tokens = sum(self._estimate_tokens(t.content) for t in self.hot)
        while hot_tokens > self.max_hot_tokens and len(self.hot) > 2:
            moved = self.hot.pop(0)
            self.warm.append(moved)
            hot_tokens = sum(self._estimate_tokens(t.content) for t in self.hot)

        while len(self.warm) > self.max_warm_turns:
            moved = self.warm.pop(0)
            summary = self._summarize_turn(moved)
            self.summaries.append(summary)

        self.summaries = self.summaries[-5:]

    def _summarize_turn(self, turn: Turn) -> str:
        lines = turn.content.split("\n")
        key_line = ""
        for line in lines:
            if line.startswith("Step"):
                key_line = line.strip()[:120]
                break
        if not key_line:
            key_line = turn.content[:100]
        return f"[{turn.role[:4]}][{key_line}]"

    def build(self, task: str, system: str = "", memory: str = "") -> list[dict]:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": truncate_smart(system, 2000)})

        if memory:
            msgs.append({"role": "system", "content": f"Relevant context:\n{truncate_smart(memory, 1000)}"})

        for s in self.summaries[-3:]:
            msgs.append({"role": "system", "content": f"Earlier: {s}"})

        for t in self.warm[-3:]:
            msgs.append({"role": t.role, "content": t.content[:500]})

        for t in self.hot:
            msgs.append({"role": t.role, "content": t.content})

        msgs.append({"role": "user", "content": task})
        return msgs

    def resume(self, task: str, history: list[dict]) -> str:
        if not history:
            return task
        steps = []
        for h in history[-6:]:
            if h.get("role") == "assistant":
                content = h.get("content", "")
                for line in content.split("\n")[:3]:
                    if line.strip():
                        steps.append(line.strip()[:100])
        summary = " | ".join(steps) if steps else ""
        return f"{task}\n\nPrevious steps: {summary}" if summary else task

    def total_estimate(self) -> int:
        total = sum(self._estimate_tokens(t.content) for t in self.hot)
        total += sum(self._estimate_tokens(t.content) for t in self.warm)
        total += sum(self._estimate_tokens(s) for s in self.summaries)
        return total
