"""
CAPABILITY REGISTRY — Workers request capabilities instead of calling tools directly.

Instead of a flat tool_map, capabilities are organized by domain:
  - Filesystem: read, write, edit, search
  - Git: status, diff, log, commit
  - Terminal: run_command, run_script
  - LSP: go_to_definition, find_references, hover, diagnostics
  - Browser: navigate, click, screenshot
  - Database: query, insert, update
  - Memory: store, retrieve, search
  - Web: fetch, search
  - AI: call_llm, embed

Workers declare what capabilities they need. The registry finds the best provider.
"""

from typing import Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Capability:
    """A capability that a worker or tool provides."""
    name: str
    description: str = ""
    domain: str = "general"  # filesystem, git, terminal, lsp, browser, database, memory, web, ai
    provider: str = ""       # Which worker/tool provides this
    priority: int = 0        # Higher = preferred
    enabled: bool = True


class CapabilityRegistry:
    """Registry of capabilities that workers can request.
    
    Instead of agent.tool_map["read_file"], workers request
    registry.get_capability("filesystem.read").execute(path=...)
    """

    def __init__(self):
        self._capabilities: dict[str, list[Capability]] = defaultdict(list)
        self._providers: dict[str, list[str]] = defaultdict(list)  # domain -> [capability_names]
        self._executors: dict[str, Callable] = {}  # capability_name -> callable

    # ── Registration ──

    def register(self, name: str, executor: Callable,
                 domain: str = "general", description: str = "",
                 provider: str = "", priority: int = 0):
        """Register a capability with an executor function."""
        cap = Capability(
            name=name,
            description=description or executor.__doc__ or "",
            domain=domain,
            provider=provider,
            priority=priority,
            enabled=True,
        )
        self._capabilities[name].append(cap)
        self._providers[domain].append(name)
        # Keep sorted by priority
        self._capabilities[name].sort(key=lambda c: c.priority, reverse=True)
        self._executors[name] = executor

    def register_tool_map(self, tool_map: dict, domain: str = "general",
                          provider: str = "agent"):
        """Bulk register from an existing tool_map dict.
        
        tool_map format: {name: callable, ...}
        """
        for name, executor in tool_map.items():
            self.register(name, executor, domain=domain, provider=provider)

    # ── Query ──

    def get_capability(self, name: str) -> Optional[Capability]:
        """Get the best capability by name."""
        caps = self._capabilities.get(name, [])
        if not caps:
            return None
        return caps[0]  # Highest priority

    def get_executor(self, name: str) -> Optional[Callable]:
        """Get the executor function for a capability."""
        return self._executors.get(name)

    def execute(self, name: str, *args, **kwargs):
        """Execute a capability by name."""
        executor = self.get_executor(name)
        if not executor:
            raise ValueError(f"Capability '{name}' not found")
        return executor(*args, **kwargs)

    def get_by_domain(self, domain: str) -> list[Capability]:
        """Get all capabilities in a domain."""
        names = self._providers.get(domain, [])
        result = []
        for name in names:
            caps = self._capabilities.get(name, [])
            if caps:
                result.append(caps[0])
        return result

    def get_by_provider(self, provider: str) -> list[Capability]:
        """Get all capabilities from a provider."""
        result = []
        for caps in self._capabilities.values():
            for cap in caps:
                if cap.provider == provider:
                    result.append(cap)
        return result

    def search(self, query: str) -> list[Capability]:
        """Search capabilities by name or description."""
        query_lower = query.lower()
        result = []
        for caps in self._capabilities.values():
            for cap in caps:
                if query_lower in cap.name.lower() or query_lower in cap.description.lower():
                    result.append(cap)
        return result

    # ── Domain Organization ──

    @property
    def domains(self) -> list[str]:
        """Get all capability domains."""
        return list(self._providers.keys())

    @property
    def capabilities(self) -> list[Capability]:
        """Get all registered capabilities (best per name)."""
        result = []
        for caps in self._capabilities.values():
            if caps:
                result.append(caps[0])
        return sorted(result, key=lambda c: (c.domain, c.name))

    @property
    def count(self) -> int:
        return len(self._capabilities)

    def get_stats(self) -> dict:
        """Get registry statistics."""
        return {
            "total_capabilities": self.count,
            "domains": self.domains,
            "providers": list(set(c.provider for caps in self._capabilities.values() for c in caps)),
            "by_domain": {d: len(caps) for d, caps in self._providers.items()},
        }

    get_statistics = get_stats  # Alias for compatibility
