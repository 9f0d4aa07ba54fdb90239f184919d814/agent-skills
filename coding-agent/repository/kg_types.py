"""
KNOWLEDGE GRAPH TYPES — Node and relation definitions for the code knowledge graph.

The Knowledge Graph transforms raw file/symbol data into a rich graph of
semantic entities and their relationships. This is the foundation for
Repository Intelligence.

Node Types represent code entities:
  MODULE, CLASS, FUNCTION, METHOD, VARIABLE, CONSTANT, PACKAGE,
  API, DATABASE, TEST, ROUTE, WORKER, COMMAND, INTERFACE, ENUM, TYPE

Relation Types represent semantic relationships:
  IMPORTS, CALLS, CREATES, READS, WRITES, IMPLEMENTS, OVERRIDES,
  USES, DEPENDS_ON, OWNS, RETURNS, INHERITS, CONTAINS, REFERENCES,
  DEFINES, TESTS, DECORATES, ASSIGNS, PASSES_TO, CONVERTS_TO
"""

from enum import Enum, auto
from typing import Optional
from dataclasses import dataclass, field


# ── Node Types ──


class NodeType(Enum):
    """Types of nodes in the knowledge graph."""
    MODULE = auto()       # A file/module
    PACKAGE = auto()      # A directory/package
    CLASS = auto()        # A class definition
    FUNCTION = auto()     # A function definition
    METHOD = auto()       # A method within a class
    VARIABLE = auto()     # A variable assignment
    CONSTANT = auto()     # A constant (ALL_CAPS)
    INTERFACE = auto()    # An interface/protocol/ABC
    ENUM = auto()         # An enumeration
    TYPE = auto()         # A type alias/typedef
    API = auto()          # An API endpoint/route handler
    DATABASE = auto()     # A database model/table/schema
    TEST = auto()         # A test function/class
    ROUTE = auto()        # A URL route/endpoint definition
    WORKER = auto()       # A background worker/task
    COMMAND = auto()      # A CLI command/subcommand
    DECORATOR = auto()    # A decorator function
    CALL = auto()         # A function/method call site
    IMPORT = auto()       # An import statement
    FILE = auto()         # A generic file (fallback)
    UNKNOWN = auto()      # Unknown/unresolved


# ── Relation Types ──


class RelationType(Enum):
    """Types of relationships between nodes."""
    IMPORTS = auto()       # imports module
    CALLS = auto()         # calls function/method
    CREATES = auto()       # instantiates a class
    READS = auto()         # reads from a variable/table
    WRITES = auto()        # writes to a variable/table
    IMPLEMENTS = auto()    # implements an interface/protocol
    OVERRIDES = auto()     # overrides a parent method
    USES = auto()          # uses a type/resource
    DEPENDS_ON = auto()    # depends on another module
    OWNS = auto()          # owns/contains a definition
    RETURNS = auto()       # returns a type
    INHERITS = auto()      # inherits from a class
    CONTAINS = auto()      # contains a nested definition
    REFERENCES = auto()    # references a symbol
    DEFINES = auto()       # defines a symbol
    TESTS = auto()         # tests a function/class
    DECORATES = auto()     # applies a decorator
    ASSIGNS = auto()       # assigns to a variable
    PASSES_TO = auto()     # passes as argument
    CONVERTS_TO = auto()   # converts/casts to a type
    EXTENDS = auto()       # extends a class (JS/TS)
    MIXIN = auto()         # uses a mixin
    SATISFIES = auto()     # satisfies a protocol/contract
    EXPORTS = auto()       # exports a symbol (JS/TS)
    ROUTES = auto()        # routes to a handler
    CONFIGURES = auto()    # configures a resource
    LISTENS = auto()       # listens to events
    EMITS = auto()         # emits events
    MOCKS = auto()         # mocks a dependency (tests)
    FIXTURE = auto()       # provides test fixture
    ASSERT = auto()        # asserts about a value


# ── Data Structures ──


@dataclass
class KGNode:
    """A node in the knowledge graph representing a code entity.

    Each node has a unique ID, a type, a name, and location info.
    Properties store additional metadata (docstring, signature, etc.).
    """
    id: str                                # Unique node ID (e.g., "module:path/to/file.py")
    type: NodeType                         # Type of code entity
    name: str                              # Entity name (e.g., "MyClass", "process_data")
    file_path: str                         # Source file path
    line: int = 0                          # Start line (1-based)
    column: int = 0                        # Start column (0-based)
    end_line: int = 0                      # End line (1-based)
    docstring: str = ""                    # Documentation text
    signature: str = ""                    # Full signature if applicable
    visibility: str = "public"             # public, private, protected, module
    is_async: bool = False                 # Is this async?
    is_deprecated: bool = False            # Is this deprecated?
    is_generated: bool = False             # Is this auto-generated?
    metadata: dict = field(default_factory=dict)  # Arbitrary extra data

    @property
    def short_id(self) -> str:
        """Human-readable short identifier."""
        return f"{self.type.name.lower()}:{self.name}"


@dataclass
class KGRelation:
    """A directed edge between two nodes in the knowledge graph.

    Each relation has a source, target, type, and optional metadata.
    """
    source_id: str                         # Source node ID
    target_id: str                         # Target node ID
    type: RelationType                     # Type of relationship
    file_path: str = ""                    # File where this relation was found
    line: int = 0                          # Line where this relation was found
    weight: float = 1.0                    # Strength/confidence of relation
    label: str = ""                        # Optional human-readable label
    metadata: dict = field(default_factory=dict)  # Arbitrary extra data

    def __hash__(self):
        return hash((self.source_id, self.target_id, self.type.value))


@dataclass
class KGPath:
    """A path between two nodes in the knowledge graph."""
    nodes: list[KGNode] = field(default_factory=list)
    relations: list[KGRelation] = field(default_factory=list)
    length: int = 0

    @property
    def description(self) -> str:
        """Human-readable path description."""
        parts = []
        for i, node in enumerate(self.nodes):
            parts.append(f"{node.type.name.lower()}:{node.name}")
            if i < len(self.relations):
                parts.append(f"--[{self.relations[i].type.name.lower()}]-->")
        return " ".join(parts)


@dataclass
class KGAnalysis:
    """Result of an analysis query on the knowledge graph."""
    query_type: str                        # What was queried
    summary: str = ""                      # Human-readable summary
    nodes: list[KGNode] = field(default_factory=list)
    relations: list[KGRelation] = field(default_factory=list)
    paths: list[KGPath] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
