# Source Code Style Guide

Code style and design conventions for `src/` modules in the daf-okn project.

## Pure Function Design

Functions in `core/` must be **side-effect-free**:

```python
# ✅ CORRECT: Pure function — takes input, returns output
def graph_stats(doc: GraphDocument) -> dict[str, Any]:
    return {
        "node_count": len(doc.nodes),
        "edge_count": len(doc.edges),
    }

# ❌ WRONG: Side-effect function — writes files, prints, logs
def graph_stats(doc):
    print(f"Counting {len(doc.nodes)} nodes")   # Side effect: printing
    Path("stats.json").write_text("{}")          # Side effect: file write
    return {"node_count": len(doc.nodes)}
```

File I/O, logging, and visualisation belong in the orchestration modules
(`analysis/`, `figures/`, `dashboard/`, `core/manuscript_variables.py`,
`core/documentation.py`) or in `scripts/` — not in pure `core/` logic. The
declared exceptions are `core/registry.py` (HTTP I/O inside `OKNRegistry`
methods only) and `core/_runtime.py` (the runtime adapter).

## Type Hints

Every public function must have complete type annotations, using the modern
union syntax already used across the codebase:

```python
def compute_metrics(
    graph: nx.Graph | nx.DiGraph,
    *,
    top_k: int = 5,
) -> dict[str, Any]:
```

- Use `X | None` union syntax, not `Optional[X]`
- Use `list[str]`, `dict[str, Any]`, `tuple[int, int]` builtin generics
- Use `@dataclass` for structured record types (`NodeRecord`, `EdgeRecord`)

## Docstring Format

Google-style docstrings with Args/Returns/Raises:

```python
def validate_graph(doc: GraphDocument) -> list[str]:
    """Validate structural invariants of a graph document.

    Args:
        doc: Graph document to check.

    Returns:
        Human-readable problem strings; empty when the document is well-formed.

    Raises:
        TypeError: If ``doc`` is not a ``GraphDocument``.
    """
```

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Functions | `snake_case` | `validate_graph` |
| Classes | `PascalCase` | `GraphDocument` |
| Constants | `UPPER_SNAKE` | `REPORT_FILENAME`, `KGS_YAML_URL` |
| Private | `_leading_underscore` | `_resolve_target_path` |
| Parameters | descriptive `snake_case` | `graph`, `out_dir`, `shortname` |

## Error Handling

```python
class RegistryError(Exception):
    """Raised when an OKN endpoint fails (HTTP >= 400) or returns malformed data."""
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status
```

- Define a domain exception (`RegistryError`) rather than raising bare `RuntimeError`
- Include the offending value or endpoint context in the message
- Validate inputs at function entry (`raise ValueError(f"A must be ...")` style with actual values)
- Never catch and silently swallow exceptions

## Module Exports

`src/__init__.py` is a namespace shim only — it performs no re-exports:

```python
"""Namespace shim — the real daf_okn package lives at src/daf_okn/."""
```

`src/daf_okn/__init__.py` re-exports the pure graph layer:

```python
from .core.graph import EdgeRecord, GraphDocument, NodeRecord, bindings_to_graph
from .core.invariants import graph_stats, validate_graph
```

Everything else is accessed through deep imports such as:

```python
from daf_okn.core.registry import OKNRegistry
from daf_okn.core.cognitive_adapter import export_cognitive_kb
from daf_okn.analysis.pipeline import run_analysis
from daf_okn.figures import plot_network
```

`src/daf_okn/analysis/`, `src/daf_okn/dashboard/`, and `src/daf_okn/figures/`
expose their public callables through `__init__.py` re-export barrels; submodules
may also be imported directly.

## See Also

- [AGENTS.md](daf_okn/AGENTS.md) — Full API reference and dependency rules
- [../tests/PATTERNS.md](../tests/PATTERNS.md) — How to test code written here
- [../scripts/CONVENTIONS.md](../scripts/CONVENTIONS.md) — How scripts use this code
