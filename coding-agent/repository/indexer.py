"""
INDEXER — Parser → AST → Indexer pipeline for building the Knowledge Graph.

Pipeline:
  File Watcher → Parser → AST → Indexer → Knowledge Graph → Embeddings → Repository Cache

The Indexer:
  1. Watches files (via FileWatcher) or indexes on demand
  2. Parses source code into AST (Python 'ast' module, regex fallback for others)
  3. Walks the AST to extract code entities (classes, functions, imports, etc.)
  4. Creates KGNode and KGRelation objects
  5. Populates the Knowledge Graph
  6. Updates the specialized caches (FileCache, SymbolCache, DependencyCache)

This is the bridge between raw filesystem data and structured code knowledge.
"""

import os, ast, re, time, hashlib, threading
from typing import Optional, Callable
from collections import defaultdict
from pathlib import Path

from .kg_types import (
    NodeType, RelationType,
    KGNode, KGRelation,
)
from .knowledge_graph import KnowledgeGraph


# ── Python AST Walker ──


class PythonASTWalker(ast.NodeVisitor):
    """Walk a Python AST and extract code entities and relations.

    Visits every node in the AST and produces:
      - nodes: list of KGNode objects (classes, functions, etc.)
      - relations: list of KGRelation objects (inherits, calls, etc.)
    """

    def __init__(self, file_path: str, source_code: str, module_name: str):
        self.file_path = file_path
        self.source_code = source_code
        self.module_name = module_name
        self.lines = source_code.split("\n")

        # Output
        self.nodes: list[KGNode] = []
        self.relations: list[KGRelation] = []

        # Tracking
        self._current_class: Optional[str] = None
        self._current_function: Optional[str] = None
        self._imports: dict[str, str] = {}  # alias -> full module name
        self._module_node_id: str = f"module:{file_path}"

        # Scope tracking for nested definitions
        self._scope_stack: list[str] = []

    def walk(self):
        """Walk the full AST and return (nodes, relations)."""
        # Create module node
        module_node = KGNode(
            id=self._module_node_id,
            type=NodeType.MODULE,
            name=self.module_name or Path(self.file_path).stem,
            file_path=self.file_path,
            line=1,
            column=0,
            end_line=len(self.lines),
            signature=f"module {self.module_name}" if self.module_name else "",
        )
        self.nodes.append(module_node)

        try:
            tree = ast.parse(self.source_code, filename=self.file_path)
            self.visit(tree)
        except SyntaxError as e:
            # Create error node
            error_node = KGNode(
                id=f"error:{self.file_path}:{e.lineno or 0}",
                type=NodeType.UNKNOWN,
                name=f"SyntaxError: {e.msg}",
                file_path=self.file_path,
                line=e.lineno or 0,
                metadata={"error": str(e)},
            )
            self.nodes.append(error_node)

        return self.nodes, self.relations

    # ── Generic visitors ──

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)

    def generic_visit(self, node: ast.AST):
        """Override to visit all children."""
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    # ── Class definitions ──

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit a class definition and create a CLASS node."""
        class_id = f"class:{self.file_path}:{node.name}"
        docstring = ast.get_docstring(node) or ""

        # Determine if this is an interface/protocol/ABC
        node_type = NodeType.CLASS
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{self._get_attribute_fullname(base)}")

        if "ABC" in bases or "Protocol" in bases:
            node_type = NodeType.INTERFACE
        if "Enum" in bases:
            node_type = NodeType.ENUM

        class_node = KGNode(
            id=class_id,
            type=node_type,
            name=node.name,
            file_path=self.file_path,
            line=node.lineno,
            column=node.col_offset,
            end_line=getattr(node, 'end_lineno', node.lineno),
            docstring=docstring,
            signature=f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}",
            visibility="public" if not node.name.startswith("_") else "private",
            metadata={
                "bases": bases,
                "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
                "methods": [],
                "attributes": [],
            },
        )
        self.nodes.append(class_node)

        # Add OWNS relation from module to class
        self.relations.append(KGRelation(
            source_id=self._module_node_id,
            target_id=class_id,
            type=RelationType.OWNS,
            file_path=self.file_path,
            line=node.lineno,
        ))

        # Add INHERITS relations
        for base_name in bases:
            base_id = self._resolve_name(base_name)
            self.relations.append(KGRelation(
                source_id=class_id,
                target_id=base_id,
                type=RelationType.INHERITS,
                file_path=self.file_path,
                line=node.lineno,
                label=f"inherits {base_name}",
            ))

        # Handle decorators
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name:
                decorator_id = self._resolve_name(decorator_name)
                self.relations.append(KGRelation(
                    source_id=class_id,
                    target_id=decorator_id,
                    type=RelationType.DECORATES,
                    file_path=self.file_path,
                    line=decorator.lineno if hasattr(decorator, 'lineno') else node.lineno,
                    label=f"@{decorator_name}",
                ))

        # Visit methods within the class
        old_class = self._current_class
        self._current_class = node.name
        self._scope_stack.append(class_id)

        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                self.visit_FunctionDef(item, parent_class=node.name, class_id=class_id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_node.metadata["attributes"].append(target.value if isinstance(target, ast.Name) else str(target))
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                class_node.metadata["attributes"].append(item.target.id)

        self._scope_stack.pop()
        self._current_class = old_class

    # ── Function/method definitions ──

    def visit_FunctionDef(self, node: ast.FunctionDef, parent_class: str = None,
                          class_id: str = None):
        """Visit a function/method definition."""
        is_method = parent_class is not None
        func_type = NodeType.METHOD if is_method else NodeType.FUNCTION

        if is_method:
            func_id = f"method:{self.file_path}:{parent_class}.{node.name}"
        else:
            func_id = f"function:{self.file_path}:{node.name}"

        docstring = ast.get_docstring(node) or ""
        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Build signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.dump(arg.annotation)}"
            args.append(arg_str)
        returns = ""
        if node.returns:
            returns = f" -> {ast.dump(node.returns)}"
        signature = f"{'async ' if is_async else ''}def {node.name}({', '.join(args)}){returns}"

        # Determine visibility
        if node.name.startswith("__"):
            visibility = "private"
        elif node.name.startswith("_"):
            visibility = "protected"
        else:
            visibility = "public"

        # Check for test functions
        node_type = func_type
        if node.name.startswith("test_") or node.name.endswith("_test"):
            node_type = NodeType.TEST

        func_node = KGNode(
            id=func_id,
            type=node_type,
            name=node.name,
            file_path=self.file_path,
            line=node.lineno,
            column=node.col_offset,
            end_line=getattr(node, 'end_lineno', node.lineno),
            docstring=docstring,
            signature=signature,
            visibility=visibility,
            is_async=is_async,
            metadata={
                "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
                "args": [arg.arg for arg in node.args.args],
                "returns": ast.dump(node.returns) if node.returns else "",
            },
        )
        self.nodes.append(func_node)

        # Add OWNS relation
        if is_method and class_id:
            owner_id = class_id
        else:
            owner_id = self._module_node_id

        self.relations.append(KGRelation(
            source_id=owner_id,
            target_id=func_id,
            type=RelationType.OWNS,
            file_path=self.file_path,
            line=node.lineno,
        ))

        # Add OVERRIDES relation if this looks like an override
        if is_method and node.name not in ("__init__", "__new__", "__str__", "__repr__"):
            # Check if it might override a base class method
            base_method_id = f"function:::{node.name}"  # Generic lookup
            self.relations.append(KGRelation(
                source_id=func_id,
                target_id=base_method_id,
                type=RelationType.OVERRIDES,
                file_path=self.file_path,
                line=node.lineno,
                weight=0.5,  # Speculative
                label=f"overrides {node.name}",
            ))

        # Handle decorators
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name:
                if decorator_name in ("property", "staticmethod", "classmethod"):
                    func_node.metadata["decorator_type"] = decorator_name
                decorator_id = self._resolve_name(decorator_name)
                self.relations.append(KGRelation(
                    source_id=func_id,
                    target_id=decorator_id,
                    type=RelationType.DECORATES,
                    file_path=self.file_path,
                    line=decorator.lineno if hasattr(decorator, 'lineno') else node.lineno,
                    label=f"@{decorator_name}",
                ))

        # Visit body for call sites and references
        old_func = self._current_function
        self._current_function = node.name
        self._scope_stack.append(func_id)

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Nested function
                self.visit_FunctionDef(child, parent_class=None, class_id=None)
            else:
                self._visit_body_statement(child, func_id)

        self._scope_stack.pop()
        self._current_function = old_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Handle async functions."""
        self.visit_FunctionDef(node)

    # ── Imports ──

    def visit_Import(self, node: ast.Import):
        """Visit import statements."""
        for alias in node.names:
            module_name = alias.name
            asname = alias.asname or module_name
            self._imports[asname] = module_name

            # Import node
            import_id = f"import:{self.file_path}:{module_name}"
            import_node = KGNode(
                id=import_id,
                type=NodeType.IMPORT,
                name=module_name,
                file_path=self.file_path,
                line=node.lineno,
                metadata={"alias": alias.asname or ""},
            )
            self.nodes.append(import_node)

            # IMPORTS relation from module to import
            self.relations.append(KGRelation(
                source_id=self._module_node_id,
                target_id=import_id,
                type=RelationType.IMPORTS,
                file_path=self.file_path,
                line=node.lineno,
                label=f"import {module_name}",
            ))

            # DEPENDS_ON relation
            target_module_id = f"module:{module_name.replace('.', '/')}"
            self.relations.append(KGRelation(
                source_id=self._module_node_id,
                target_id=target_module_id,
                type=RelationType.DEPENDS_ON,
                file_path=self.file_path,
                line=node.lineno,
                label=f"depends on {module_name}",
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Visit 'from X import Y' statements."""
        module_name = node.module or ""
        for alias in node.names:
            name = alias.name
            asname = alias.asname or name
            full_name = f"{module_name}.{name}" if module_name else name
            self._imports[asname] = full_name

            import_id = f"import:{self.file_path}:{full_name}"
            import_node = KGNode(
                id=import_id,
                type=NodeType.IMPORT,
                name=full_name,
                file_path=self.file_path,
                line=node.lineno,
                metadata={"alias": alias.asname or "", "module": module_name},
            )
            self.nodes.append(import_node)

            # IMPORTS relation
            self.relations.append(KGRelation(
                source_id=self._module_node_id,
                target_id=import_id,
                type=RelationType.IMPORTS,
                file_path=self.file_path,
                line=node.lineno,
                label=f"from {module_name} import {name}",
            ))

            # USES relation for the imported symbol
            symbol_id = self._resolve_name(full_name)
            self.relations.append(KGRelation(
                source_id=self._module_node_id,
                target_id=symbol_id,
                type=RelationType.USES,
                file_path=self.file_path,
                line=node.lineno,
                label=f"uses {full_name}",
            ))

    # ── Body statement visitors ──

    def _visit_body_statement(self, node: ast.AST, func_id: str):
        """Visit a statement within a function body to extract references."""
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            self._visit_call(node.value, func_id)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                self._visit_assign_target(target, func_id)
            if isinstance(node.value, ast.Call):
                self._visit_call(node.value, func_id)
        elif isinstance(node, ast.Return):
            if isinstance(node.value, ast.Call):
                self._visit_call(node.value, func_id)
            elif isinstance(node.value, ast.Name):
                # RETURNS relation
                return_id = self._resolve_name(node.value.id)
                self.relations.append(KGRelation(
                    source_id=func_id,
                    target_id=return_id,
                    type=RelationType.RETURNS,
                    file_path=self.file_path,
                    line=node.lineno,
                    label=f"returns {node.value.id}",
                ))
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.value, ast.Call):
                self._visit_call(node.value, func_id)
        elif isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            for child in ast.iter_child_nodes(node):
                self._visit_body_statement(child, func_id)
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                for child in ast.iter_child_nodes(handler):
                    self._visit_body_statement(child, func_id)
            for child in ast.iter_child_nodes(node):
                self._visit_body_statement(child, func_id)

    def _visit_call(self, node: ast.Call, caller_id: str):
        """Visit a function call site."""
        callee_name = self._get_call_name(node)
        if not callee_name:
            return

        callee_id = self._resolve_name(callee_name)

        # CALLS relation
        self.relations.append(KGRelation(
            source_id=caller_id,
            target_id=callee_id,
            type=RelationType.CALLS,
            file_path=self.file_path,
            line=node.lineno,
            label=f"calls {callee_name}",
        ))

        # Check for class instantiation (ClassName())
        if callee_name[0].isupper():
            self.relations.append(KGRelation(
                source_id=caller_id,
                target_id=callee_id,
                type=RelationType.CREATES,
                file_path=self.file_path,
                line=node.lineno,
                label=f"creates {callee_name}",
            ))

    def _visit_assign_target(self, node: ast.AST, func_id: str):
        """Visit an assignment target to create VARIABLE nodes."""
        if isinstance(node, ast.Name):
            var_id = f"variable:{self.file_path}:{node.id}"
            if not self._node_exists(var_id):
                var_node = KGNode(
                    id=var_id,
                    type=NodeType.VARIABLE,
                    name=node.id,
                    file_path=self.file_path,
                    line=node.lineno,
                    visibility="private" if node.id.startswith("_") else "public",
                )
                self.nodes.append(var_node)
                self.relations.append(KGRelation(
                    source_id=func_id,
                    target_id=var_id,
                    type=RelationType.ASSIGNS,
                    file_path=self.file_path,
                    line=node.lineno,
                ))
        elif isinstance(node, ast.Tuple):
            for elt in node.elts:
                self._visit_assign_target(elt, func_id)
        elif isinstance(node, ast.Attribute):
            # obj.attr = value — WRITES relation
            if isinstance(node.value, ast.Name):
                obj_id = self._resolve_name(node.value.id)
                self.relations.append(KGRelation(
                    source_id=func_id,
                    target_id=obj_id,
                    type=RelationType.WRITES,
                    file_path=self.file_path,
                    line=node.lineno,
                    label=f"writes {node.value.id}.{node.attr}",
                ))

    # ── Helpers ──

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Get the full name of a call target."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
            elif isinstance(node.func.value, ast.Call):
                return None
            return node.func.attr
        return None

    def _get_decorator_name(self, node: ast.expr) -> Optional[str]:
        """Get the name of a decorator."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                return f"{node.value.id}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return None

    def _get_attribute_fullname(self, node: ast.Attribute) -> str:
        """Get the full dotted name of an attribute."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._get_attribute_fullname(node.value)}.{node.attr}"
        return node.attr

    def _resolve_name(self, name: str) -> str:
        """Resolve a name to a knowledge graph node ID.

        Handles imports, module paths, and local names.
        """
        # Check if it's a known import alias
        if name in self._imports:
            full = self._imports[name]
            return f"module:{full.replace('.', '/')}"

        # Check for dotted names
        if "." in name:
            parts = name.split(".")
            if parts[0] in self._imports:
                # e.g., "os.path" -> import os → module:os/path
                full = self._imports[parts[0]]
                rest = ".".join(parts[1:])
                return f"module:{full.replace('.', '/')}/{rest}"

        # Try various node ID patterns
        candidates = [
            f"function:{self.file_path}:{name}",
            f"class:{self.file_path}:{name}",
            f"variable:{self.file_path}:{name}",
            f"method:{self.file_path}:{name}",
            f"function:::{name}",
            f"class:::{name}",
        ]
        # Return the most specific one (local first)
        return f"function:::{name}"

    def _node_exists(self, node_id: str) -> bool:
        """Check if a node with this ID already exists."""
        return any(n.id == node_id for n in self.nodes)


# ── Generic (Regex-based) Parser ──


class GenericParser:
    """Regex-based parser for non-Python files (JS, TS, Java, etc.).

    Provides basic entity extraction where full AST parsing isn't available.
    """

    # Language-specific patterns
    PATTERNS = {
        "javascript": {
            "function": [r"(?:async\s+)?function\s+(\w+)\s*\(", r"(\w+)\s*=\s*(?:async\s+)?function\s*\("],
            "class": [r"class\s+(\w+)(?:\s+extends\s+(\w+))?"],
            "method": [r"(\w+)\s*\([^)]*\)\s*\{", r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{"],
            "import": [r"(?:import|require)\s+['\"]([^'\"]+)['\"]", r"from\s+['\"]([^'\"]+)['\"]"],
            "const": [r"(?:const|let|var)\s+(\w+)"],
        },
        "typescript": {
            "function": [r"(?:async\s+)?function\s+(\w+)\s*\(", r"(\w+)\s*=\s*(?:async\s+)?function\s*\("],
            "class": [r"class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+(\w+))?"],
            "interface": [r"interface\s+(\w+)"],
            "type": [r"type\s+(\w+)"],
            "method": [r"(\w+)\s*\([^)]*\)\s*\{", r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{"],
            "import": [r"import\s+\{[^}]*\}\s+from\s+['\"]([^'\"]+)['\"]", r"from\s+['\"]([^'\"]+)['\"]"],
            "const": [r"(?:const|let|var)\s+(\w+)"],
            "route": [r"(?:router|app)\.(?:get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]"],
            "api": [r"@(?:Get|Post|Put|Delete|Patch)\s*\(?['\"]?([^'\")]*)['\"]?\)?"],
        },
        "java": {
            "class": [r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+(\w+(?:\s*,\s*\w+)*))?"],
            "interface": [r"(?:public\s+)?interface\s+(\w+)"],
            "enum": [r"(?:public\s+)?enum\s+(\w+)"],
            "method": [r"(?:public|private|protected)\s+(?:\w+\s+)*(\w+)\s*\([^)]*\)"],
            "import": [r"import\s+(?:static\s+)?(\w+(?:\.\w+)*)"],
        },
    }

    def __init__(self, file_path: str, source_code: str):
        self.file_path = file_path
        self.source_code = source_code
        self.lines = source_code.split("\n")
        self.ext = os.path.splitext(file_path)[1].lower()

    def parse(self) -> tuple[list[KGNode], list[KGRelation]]:
        """Parse the file and extract entities."""
        nodes: list[KGNode] = []
        relations: list[KGRelation] = []
        module_node_id = f"module:{self.file_path}"

        # Create module node
        module_name = Path(self.file_path).stem
        module_node = KGNode(
            id=module_node_id,
            type=NodeType.MODULE,
            name=module_name,
            file_path=self.file_path,
            line=1,
        )
        nodes.append(module_node)

        # Detect language
        lang = self._detect_language()
        patterns = self.PATTERNS.get(lang, {})

        # Apply each pattern
        for entity_type, regexes in patterns.items():
            for regex_str in regexes:
                try:
                    regex = re.compile(regex_str)
                    for match in regex.finditer(self.source_code):
                        line_no = self.source_code[:match.start()].count("\n") + 1

                        if entity_type == "class":
                            self._add_class_node(nodes, relations, module_node_id,
                                                 match, line_no)
                        elif entity_type == "function":
                            self._add_function_node(nodes, relations, module_node_id,
                                                    match, line_no)
                        elif entity_type == "method":
                            self._add_method_node(nodes, relations, module_node_id,
                                                  match, line_no)
                        elif entity_type == "import":
                            self._add_import_node(nodes, relations, module_node_id,
                                                  match, line_no)
                        elif entity_type == "const":
                            self._add_variable_node(nodes, relations, module_node_id,
                                                    match, line_no)
                        elif entity_type in ("interface", "type"):
                            self._add_type_node(nodes, relations, module_node_id,
                                                match, line_no, entity_type)
                        elif entity_type == "route":
                            self._add_route_node(nodes, relations, module_node_id,
                                                 match, line_no)
                        elif entity_type == "api":
                            self._add_api_node(nodes, relations, module_node_id,
                                               match, line_no)
                except re.error:
                    continue

        return nodes, relations

    def _detect_language(self) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
            ".java": "java", ".kt": "kotlin",
            ".go": "go", ".rs": "rust",
            ".rb": "ruby", ".php": "php",
        }
        return ext_map.get(self.ext, "unknown")

    def _add_class_node(self, nodes, relations, module_id, match, line_no):
        name = match.group(1)
        node_id = f"class:{self.file_path}:{name}"
        base_name = match.group(2) if match.lastindex >= 2 and match.group(2) else ""

        node = KGNode(
            id=node_id, type=NodeType.CLASS, name=name,
            file_path=self.file_path, line=line_no,
            signature=f"class {name}",
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.OWNS,
                                    file_path=self.file_path, line=line_no))
        if base_name:
            relations.append(KGRelation(
                node_id, f"class:::{base_name}", RelationType.INHERITS,
                file_path=self.file_path, line=line_no,
            ))

    def _add_function_node(self, nodes, relations, module_id, match, line_no):
        name = match.group(1)
        node_id = f"function:{self.file_path}:{name}"
        node = KGNode(
            id=node_id, type=NodeType.FUNCTION, name=name,
            file_path=self.file_path, line=line_no,
            signature=f"function {name}",
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.OWNS,
                                    file_path=self.file_path, line=line_no))

    def _add_method_node(self, nodes, relations, module_id, match, line_no):
        name = match.group(1)
        if name in ("if", "else", "for", "while", "switch", "catch", "then"):
            return
        node_id = f"method:{self.file_path}:{name}"
        node = KGNode(
            id=node_id, type=NodeType.METHOD, name=name,
            file_path=self.file_path, line=line_no,
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.OWNS,
                                    file_path=self.file_path, line=line_no))

    def _add_import_node(self, nodes, relations, module_id, match, line_no):
        name = match.group(1)
        node_id = f"import:{self.file_path}:{name}"
        node = KGNode(
            id=node_id, type=NodeType.IMPORT, name=name,
            file_path=self.file_path, line=line_no,
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.IMPORTS,
                                    file_path=self.file_path, line=line_no))

    def _add_variable_node(self, nodes, relations, module_id, match, line_no):
        name = match.group(1)
        node_id = f"variable:{self.file_path}:{name}"
        node = KGNode(
            id=node_id, type=NodeType.VARIABLE, name=name,
            file_path=self.file_path, line=line_no,
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.OWNS,
                                    file_path=self.file_path, line=line_no))

    def _add_type_node(self, nodes, relations, module_id, match, line_no, type_name):
        name = match.group(1)
        ntype = NodeType.INTERFACE if type_name == "interface" else NodeType.TYPE
        node_id = f"{ntype.name.lower()}:{self.file_path}:{name}"
        node = KGNode(
            id=node_id, type=ntype, name=name,
            file_path=self.file_path, line=line_no,
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.OWNS,
                                    file_path=self.file_path, line=line_no))

    def _add_route_node(self, nodes, relations, module_id, match, line_no):
        route = match.group(1)
        node_id = f"route:{self.file_path}:{route}"
        node = KGNode(
            id=node_id, type=NodeType.ROUTE, name=route,
            file_path=self.file_path, line=line_no,
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.OWNS,
                                    file_path=self.file_path, line=line_no))

    def _add_api_node(self, nodes, relations, module_id, match, line_no):
        route = match.group(1) or "/"
        node_id = f"api:{self.file_path}:{route}"
        node = KGNode(
            id=node_id, type=NodeType.API, name=route,
            file_path=self.file_path, line=line_no,
        )
        nodes.append(node)
        relations.append(KGRelation(module_id, node_id, RelationType.OWNS,
                                    file_path=self.file_path, line=line_no))


# ── Indexer ──


class Indexer:
    """Orchestrates parsing and knowledge graph population.

    Pipeline:
        File path → Parser → AST → Indexer → Knowledge Graph

    Usage:
        indexer = Indexer(knowledge_graph)
        indexer.index_file("src/main.py")
        indexer.index_all()
        indexer.index_file("src/utils.py", source_code="...")
    """

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self._indexed_files: set[str] = set()
        self._stats = {"files_indexed": 0, "nodes_created": 0, "errors": 0}

    def index_file(self, file_path: str, source_code: str = None) -> int:
        """Index a single file into the knowledge graph.

        Args:
            file_path: Path to the file (relative to repo_root or absolute).
            source_code: Optional source code. If not provided, reads from disk.

        Returns:
            Number of nodes created.
        """
        # Read source if not provided
        if source_code is None:
            abs_path = file_path if os.path.isabs(file_path) else \
                os.path.join(self.kg.repo_root, file_path)
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    source_code = f.read()
            except (IOError, OSError) as e:
                self._stats["errors"] += 1
                return 0

        # Make file path relative to repo root
        try:
            rel_path = file_path
            if os.path.isabs(file_path):
                rel_path = os.path.relpath(file_path, self.kg.repo_root)
        except ValueError:
            rel_path = file_path

        # Detect language and choose parser
        ext = os.path.splitext(rel_path)[1].lower()
        module_name = Path(rel_path).stem

        try:
            if ext == ".py":
                nodes, relations = self._parse_python(rel_path, source_code, module_name)
            else:
                nodes, relations = self._parse_generic(rel_path, source_code)
        except Exception as e:
            self._stats["errors"] += 1
            return 0

        # Add to knowledge graph
        node_count = 0
        for node in nodes:
            if not self.kg.has_node(node.id):
                self.kg.add_node(node)
                node_count += 1

        for relation in relations:
            self.kg.add_relation(relation)

        self._indexed_files.add(rel_path)
        self._stats["files_indexed"] += 1
        self._stats["nodes_created"] += node_count

        return node_count

    def _parse_python(self, file_path: str, source_code: str,
                      module_name: str) -> tuple[list, list]:
        """Parse a Python file using the AST walker."""
        walker = PythonASTWalker(file_path, source_code, module_name)
        return walker.walk()

    def _parse_generic(self, file_path: str, source_code: str) -> tuple[list, list]:
        """Parse a non-Python file using regex patterns."""
        parser = GenericParser(file_path, source_code)
        return parser.parse()

    def index_all(self, file_paths: list[str] = None) -> int:
        """Index all specified files (or all Python/JS/TS files in repo).

        Args:
            file_paths: Optional list of file paths. If None, walks repo.

        Returns:
            Total number of nodes created.
        """
        total = 0

        if file_paths is None:
            file_paths = self._discover_files()

        for file_path in file_paths:
            total += self.index_file(file_path)

        return total

    def _discover_files(self) -> list[str]:
        """Discover all indexable files in the repository."""
        # Supported extensions
        exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt",
                ".go", ".rs", ".rb", ".php"}

        results = []
        repo = Path(self.kg.repo_root)
        for f in repo.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in exts:
                continue
            # Skip ignored directories
            if any(part.startswith(".") or part == "node_modules"
                   or part == "__pycache__" or part == "venv"
                   for part in f.parts):
                continue
            try:
                results.append(str(f.relative_to(repo)))
            except ValueError:
                results.append(str(f))

        return sorted(results)

    def index_file_event(self, file_path: str):
        """Handle a file change event from the watcher.

        Args:
            file_path: Path to the changed file.

        Returns:
            Number of nodes created/modified.
        """
        # Re-index the file (removes old nodes for this file first)
        self._remove_file_nodes(file_path)
        return self.index_file(file_path)

    def _remove_file_nodes(self, file_path: str):
        """Remove all knowledge graph nodes for a file."""
        nodes = self.kg.find_in_file(file_path)
        for node in nodes:
            self.kg.remove_node(node.id)
        self._indexed_files.discard(file_path)

    def get_stats(self) -> dict:
        return {**self._stats, "indexed_files": len(self._indexed_files)}
