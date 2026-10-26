# Style Guide

This document defines the coding and communication style for the daf-okn project. Every rule here has a concrete consequence for test correctness, reproducibility, or manuscript accuracy.

---

## 1. Zero-Mock Policy

The most critical style rule is the absolute prohibition of mocking. The following are **forbidden** anywhere inside `tests/`:

- `import unittest.mock`
- `from unittest.mock import MagicMock, patch, create_autospec, Mock, AsyncMock`
- `@patch(...)` decorators
- `monkeypatch.setattr(...)` when used to substitute a real function with a fake callable (or fake return values)

**Allowed for orchestration modules only:** `pytest.MonkeyPatch` on module attributes (`project_root`, logger wiring, I/O boundaries) and subprocess import isolation — real code paths run; see [`../tests/PATTERNS.md`](../tests/PATTERNS.md). At the HTTP boundary, `tests/core/test_registry.py` defines a hand-written `StubSession` (records calls, returns canned responses) injected into `OKNRegistry` — the real client code runs end to end with no network and no mock library.

**Why**: `src/daf_okn/core/graph.py` and `core/invariants.py` contain pure functions. You can always test them with real graph fixtures and real structural results. A test that requires a mock is a test for the wrong thing — it tests that one function calls another (call-count assertion), not that the logic is correct.

**Forbidden pattern**:
```python
# BAD — tests call behavior, not correctness
from unittest.mock import MagicMock
fake_report = MagicMock(return_value={"metrics": {}})
result = run_analysis(doc, out_dir="output/analysis")
assert fake_report.called
```

**Correct pattern** (from `tests/analysis/test_graph_metrics.py`):
```python
# GOOD — tests real structural output
doc = GraphDocument(name="probe", nodes=nodes, edges=edges)
metrics = compute_metrics(doc)
assert metrics["node_count"] == 6
assert metrics["weakly_connected_components"] == 2
assert metrics["top_central_nodes"][0] == ("c", pytest.approx(5 / 20))
```

**Verify cleanliness**:
```bash
grep -rn "unittest.mock\|MagicMock\|@patch" --include='*.py' tests/ || echo "Clean"
```

---

## 2. Module Layering

Project code keeps `core/` free of script-level concerns. The layering table is:

| File | May Import | Must NOT Import |
|---|---|---|
| `src/daf_okn/core/graph.py`, `core/invariants.py` | `networkx`, `dataclasses`, `typing` (plus stdlib) | `scripts/`, `analysis/`, `figures/`, `dashboard/` |
| `src/daf_okn/core/registry.py`, `core/cognitive_adapter.py`, `core/contribute.py` | `requests`, `rdflib`, `yaml`, stdlib | Network I/O at import time |
| `src/daf_okn/analysis/`, `figures/`, `dashboard/`, `core/manuscript_variables.py` | `daf_okn.core.*` | Business logic (parsing, metrics math) duplicated from `core/` |
| `scripts/*.py` | `daf_okn.*` | Metric/parsing logic re-implemented locally |

**Verify `core/` does not reach into the orchestration layers**:
```bash
grep -rnE "^(from|import) (scripts|daf_okn\.(analysis|figures|dashboard))" src/daf_okn/core/ || echo "Clean"
```

---

## 3. The Thin Orchestrator Pattern

Files in `scripts/` must be "thin orchestrators": they may parse CLI arguments and write artifacts, but must not re-implement logic that belongs in `src/`.

**Forbidden** — parsing logic re-implemented in `scripts/`:
```python
# BAD — parsing belongs in src/daf_okn/core/registry.py, not in the script
def parse_sparql_json(payload):
    rows = []
    for binding in payload["results"]["bindings"]:   # BAD: duplicated dialect logic
        rows.append({k: v["value"] for k, v in binding.items()})
    return rows
```

**Correct** — `scripts/` calls `src/` for the logic:
```python
# GOOD — import and call the tested function
# (matches real usage: scripts/pull_registry.py delegates to daf_okn.core.registry)
from daf_okn.core.registry import OKNRegistry, parse_sparql_json

registry = OKNRegistry()
rows = registry.sparql_rows("cognitive", query)
```

**Decision rule**: If a line of code in `scripts/` contains parsing, metric, or packaging logic that determines the artifact's content (not just its location), move that line to `src/` and write a test for it.

---

## 4. Manuscript "Show, Not Tell"

When editing manuscript markdown (e.g., `02_methodology.md`), use explicit, verifiable file paths instead of vague descriptions. Reviewers and future agents must be able to find the referenced code.

**Forbidden (vague)**:
```markdown
Our framework parses knowledge graphs using standard techniques.
The pipeline produces the numbers automatically.
```

**Correct (concrete, from the manuscript)**:
```markdown
`bindings_to_graph()` in `src/daf_okn/core/graph.py` converts SPARQL 1.1 JSON
results into the graph document model; `validate_graph()` in
`src/daf_okn/core/invariants.py` rejects documents with dangling edge endpoints.
`compute_metrics()` in `src/daf_okn/analysis/graph_metrics.py` produces the
structural numbers that `scripts/z_generate_manuscript_variables.py` injects as tokens.
```

Two additional BAD/GOOD pairs:

| BAD (vague) | GOOD (concrete) |
|---|---|
| "The graph is reasonably connected." | "The exported cognitive graph has `{{WEAKLY_CONNECTED_COMPONENTS}}` weakly connected components over `{{NODE_COUNT}}` nodes, measured by `compute_metrics()` in `src/daf_okn/analysis/graph_metrics.py`." |
| "We validated the contribution package." | "`validate_package()` from `src/daf_okn/core/contribute.py` round-trip-parses the N-Quads and lists IRI issues; `contribution_checklist()` enumerates the remaining registry steps." |

---

## 5. Explicit Repository-Root File Paths

When AI agents or humans refer to files in logs, documentation, comments, or implementation plans, always use the path relative to the **repository root** (`daf-okn/`). This prevents ambiguity when the same filename appears in multiple directories.

**Repository-root anchors** for this project:

| Short Name | Path (from repo root) |
|---|---|
| graph model | `src/daf_okn/core/graph.py` |
| registry client | `src/daf_okn/core/registry.py` |
| invariants | `src/daf_okn/core/invariants.py` |
| cognitive adapter | `src/daf_okn/core/cognitive_adapter.py` |
| contribution packaging | `src/daf_okn/core/contribute.py` |
| metrics / pipeline | `src/daf_okn/analysis/graph_metrics.py`, `analysis/pipeline.py` |
| figures | `src/daf_okn/figures/network_figure.py` |
| dashboard | `src/daf_okn/dashboard/dashboard.py`, `dashboard/dashboard_payload.py` |
| variable map (logic) | `src/daf_okn/core/manuscript_variables.py` |
| variable map (runner) | `scripts/z_generate_manuscript_variables.py` |
| research workflow | `scripts/10_research_workflow.py` |
| config | `manuscript/config.yaml` |
| analysis report | `output/data/graph_report.json` |
| manuscript variables | `output/data/manuscript_variables.json` |

**Forbidden (relative / ambiguous)**:
```
graph.py            # Which graph module? Which project?
output/figures/     # Relative to what?
../src/graph        # Only valid from one directory
```

**Correct (absolute from repo root)**:
```
src/daf_okn/core/graph.py
output/figures/cognitive_network.png
```

---

## 6. Dataclass and Type Hint Standards

Follow the patterns established in `src/daf_okn/core/graph.py`:

- Use Python 3.10+ union syntax: `dict[str, Any] | None`, not `Optional[Dict[str, Any]]`
- Use builtin generics: `list[EdgeRecord]`, `tuple[str, str]`
- All public functions must have complete type annotations on all parameters and return values
- `@dataclass` fields use the same union syntax and `field(default_factory=...)` for mutable defaults

**Example** (following `EdgeRecord` in `src/daf_okn/core/graph.py`):
```python
@dataclass
class NewRecord:
    source: str
    target: str
    relation: str = "related"
    attributes: dict[str, Any] = field(default_factory=dict)
```

---
## 7. Error Message Format

All `ValueError` and `TypeError` raises must include the actual problematic value so that users can diagnose the issue without reading source code. Domain failures get a typed exception (`RegistryError` in `src/daf_okn/core/registry.py`).

**Forbidden (no diagnostic value)**:
```python
raise ValueError("Bad graph")
raise ValueError("Invalid endpoint")
```

**Correct** (following the patterns in `src/daf_okn/core/registry.py` and `figures/network_figure.py`):
```python
raise RegistryError(f"malformed SPARQL JSON: 'results.bindings' is not a list")
raise RegistryError(f"malformed kgs.yaml: {exc}") from exc
raise ValueError(f"unsupported layout {layout!r}; expected one of {_LAYOUTS}")
raise TypeError(f"graphs_meta[{index}] must be a mapping, got {type(entry).__name__}")
```
