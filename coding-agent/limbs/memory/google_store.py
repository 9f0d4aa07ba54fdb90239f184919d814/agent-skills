"""
LIMB: Google-quality Memory System
Three tiers with TF-IDF semantic search, importance scoring, and auto-compaction.
"""

import json, sqlite3, time, math, re, os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter

MEM_DIR = Path.home() / ".coding-agent" / "memory"
MEM_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Mem:
    content: str
    type: str = "fact"
    tags: list = field(default_factory=list)
    source: str = ""
    importance: float = 0.5
    ttl: int = 0
    created: float = field(default_factory=time.time)
    accessed: int = 0
    embedding: str = ""


class TFIDF:
    """Simple TF-IDF for semantic memory search without external deps."""

    def __init__(self):
        self._doc_freq = Counter()
        self._num_docs = 0
        self._token_cache = {}

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        return re.findall(r'\b[a-z]{2,}\b', text)

    def fit(self, documents: list[str]):
        self._num_docs = len(documents)
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for t in tokens:
                self._doc_freq[t] += 1

    def search(self, query: str, documents: list[str], top_n: int = 5) -> list[tuple[int, float]]:
        query_tokens = self._tokenize(query)
        if not query_tokens or not self._num_docs:
            return []
        scores = []
        for i, doc in enumerate(documents):
            doc_tokens = self._tokenize(doc)
            score = 0
            for qt in query_tokens:
                if qt in doc_tokens:
                    tf = doc_tokens.count(qt) / len(doc_tokens) if doc_tokens else 0
                    idf = math.log((self._num_docs + 1) / (self._doc_freq.get(qt, 1) + 1)) + 1
                    score += tf * idf
            if score > 0:
                scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]


class GoogleMemory:
    def __init__(self, db_path: str = str(MEM_DIR / "memory.db")):
        self.db = db_path
        self._tfidf = TFIDF()
        self._last_index_update = 0
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db)

    def _init(self):
        with self._connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT, type TEXT DEFAULT 'fact',
                    tags TEXT DEFAULT '[]', source TEXT DEFAULT '',
                    importance REAL DEFAULT 0.5, ttl INTEGER DEFAULT 0,
                    created REAL, accessed INTEGER DEFAULT 0,
                    embedding TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_type ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance);
                CREATE INDEX IF NOT EXISTS idx_created ON memories(created);
            """)

    def _rebuild_tfidf(self):
        if time.time() - self._last_index_update < 30:
            return
        with self._connect() as conn:
            rows = conn.execute("SELECT content FROM memories WHERE importance > 0.1").fetchall()
        docs = [r[0] for r in rows]
        if docs:
            self._tfidf = TFIDF()
            self._tfidf.fit(docs)
        self._last_index_update = time.time()

    def store(self, content: str, type: str = "fact", tags: list = None, source: str = "", importance: float = 0.5):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories(content,type,tags,source,importance,created) VALUES(?,?,?,?,?,?)",
                (content, type, json.dumps(tags or []), source, importance, time.time())
            )

    def search(self, query: str, limit: int = 5) -> list[Mem]:
        """TF-IDF semantic search with keyword fallback."""
        self._rebuild_tfidf()
        with self._connect() as conn:
            rows = conn.execute("SELECT id, content, type, tags, source, importance, created, accessed FROM memories ORDER BY importance DESC, created DESC").fetchall()

        documents = [r[1] for r in rows]
        if not documents:
            return []

        scored = self._tfidf.search(query, documents, limit)
        results = []
        seen_ids = set()
        for idx, score in scored:
            r = rows[idx]
            if r[0] not in seen_ids:
                seen_ids.add(r[0])
                mem = Mem(r[1], r[2], json.loads(r[3]) if r[3] else [], r[4], r[5], 0, r[6], r[7])
                results.append(mem)
                # Boost accessed count
                conn = self._connect()
                conn.execute("UPDATE memories SET accessed = accessed + 1 WHERE id = ?", (r[0],))
                conn.commit()
                conn.close()

        # Fill remaining with keyword matches
        if len(results) < limit:
            with self._connect() as conn:
                kw_rows = conn.execute("""
                    SELECT id, content, type, tags, source, importance, created, accessed
                    FROM memories WHERE content LIKE ? OR tags LIKE ?
                    ORDER BY importance DESC LIMIT ?
                """, (f"%{query}%", f"%{query}%", limit)).fetchall()
            for r in kw_rows:
                if r[0] not in seen_ids:
                    results.append(Mem(r[1], r[2], json.loads(r[3]) if r[3] else [], r[4], r[5], 0, r[6], r[7]))

        return results[:limit]

    def recall(self, type: str = "", limit: int = 10) -> list[Mem]:
        with self._connect() as conn:
            if type:
                rows = conn.execute(
                    "SELECT content,type,tags,source,importance,created,accessed FROM memories WHERE type=? ORDER BY importance DESC, created DESC LIMIT ?",
                    (type, limit)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT content,type,tags,source,importance,created,accessed FROM memories ORDER BY importance DESC, created DESC LIMIT ?",
                    (limit,)).fetchall()
        return [Mem(r[0], r[1], json.loads(r[2]) if r[2] else [], r[3], r[4], 0, r[5], r[6]) for r in rows]

    def recent(self, hours: int = 24) -> list[Mem]:
        cutoff = time.time() - hours * 3600
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT content,type,tags,source,importance,created,accessed FROM memories WHERE created > ? ORDER BY created DESC",
                (cutoff,)).fetchall()
        return [Mem(r[0], r[1], json.loads(r[2]) if r[2] else [], r[3], r[4], 0, r[5], r[6]) for r in rows]

    def promote(self, mem_id: int):
        with self._connect() as conn:
            conn.execute("UPDATE memories SET importance = MIN(importance + 0.1, 1.0), accessed = accessed + 1 WHERE id = ?", (mem_id,))

    def context(self, task: str, limit: int = 3) -> str:
        results = self.search(task, limit)
        if not results:
            return ""
        parts = []
        for r in results:
            parts.append(f"[{r.type}] {r.content[:300]}")
        return "Memory:\n" + "\n".join(parts)

    def consolidate(self):
        """Summarize old low-importance memories."""
        cutoff = time.time() - 86400 * 7
        with self._connect() as conn:
            old = conn.execute(
                "SELECT id, content FROM memories WHERE created < ? AND importance < 0.3 ORDER BY created",
                (cutoff,)).fetchall()
            if len(old) < 5:
                return 0
            ids = [r[0] for r in old]
            summary_content = "\n".join(r[1][:200] for r in old[:10])
            conn.execute("INSERT INTO memories(content,type,importance,created) VALUES(?,?,?,?)",
                        (f"Consolidated memory batch: {summary_content[:1000]}", "consolidated", 0.3, cutoff))
            conn.execute(f"DELETE FROM memories WHERE id IN ({','.join('?'*len(ids))}) AND importance < 0.3", ids)
        return len(old)

    def prune(self, max_age_days: int = 30):
        """Remove very old low-importance memories."""
        cutoff = time.time() - 86400 * max_age_days
        with self._connect() as conn:
            removed = conn.execute("DELETE FROM memories WHERE created < ? AND importance < 0.2", (cutoff,)).rowcount
        return removed

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            by_type = conn.execute("SELECT type, COUNT(*) FROM memories GROUP BY type").fetchall()
            avg_imp = conn.execute("SELECT AVG(importance) FROM memories").fetchone()[0] or 0
        return {"total": total, "by_type": dict(by_type), "avg_importance": round(avg_imp, 2)}
