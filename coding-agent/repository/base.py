"""
BASE CACHE — Common persistence and event integration for specialized caches.

Each specialized cache (FileCache, SymbolCache, etc.) extends BaseCache
to get:
  - JSON-based persistence (save/load)
  - Event bus integration (subscribe to file change events)
  - Dirty tracking (coalesce writes)
  - Thread-safe operations
"""

import os, json, time, threading
from typing import Optional, Any


class BaseCache:
    """Base class for all specialized caches.
    
    Provides:
      - JSON persistence to cache_dir
      - Dirty flag for write coalescing
      - Lock for thread safety
      - Event bus integration (optional)
    """

    def __init__(self, name: str, cache_dir: str):
        self.name = name
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._dirty = False
        self._event_bus = None
        self._subscriptions: list[str] = []

    # ── Persistence ──

    def _cache_path(self) -> str:
        return os.path.join(self.cache_dir, f"{self.name}.json")

    def save(self):
        """Save cache to disk. Override in subclass."""
        pass

    def _save_json(self, data: dict):
        """Atomic JSON save with write coalescing."""
        with self._lock:
            path = self._cache_path()
            tmp = path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                os.replace(tmp, path)
                self._dirty = False
            except (IOError, OSError) as e:
                print(f"[{self.name}] Save error: {e}")

    def load(self):
        """Load cache from disk. Override in subclass."""
        pass

    def _load_json(self) -> dict:
        """Load JSON data from disk."""
        path = self._cache_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            return {}

    def save_if_dirty(self):
        """Save only if dirty."""
        if self._dirty:
            self.save()

    def mark_dirty(self):
        """Mark cache as dirty (needs saving)."""
        self._dirty = True

    # ── Event Bus Integration ──

    def connect_event_bus(self, event_bus):
        """Connect to an event bus for event-driven updates."""
        self._event_bus = event_bus
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """Subscribe to relevant events. Override in subclass."""
        pass

    def _subscribe(self, event_type: str, handler) -> str:
        """Subscribe to an event and track the subscription."""
        if not self._event_bus:
            return ""
        sub_id = self._event_bus.subscribe(event_type, handler, self.name)
        self._subscriptions.append(sub_id)
        return sub_id

    def disconnect(self):
        """Unsubscribe from all events."""
        if self._event_bus:
            for sub_id in self._subscriptions:
                self._event_bus.unsubscribe(sub_id)
        self._subscriptions.clear()

    # ── Statistics ──

    def get_stats(self) -> dict:
        """Get cache statistics. Override in subclass."""
        return {"name": self.name}

    def clear(self):
        """Clear all cached data. Override in subclass."""
        self._dirty = True
