# Test Patterns Reference

Testing conventions and patterns for the daf-okn zero-mock test suite.

## Zero-Mock Enforcement

The following are **strictly forbidden** anywhere in the daf-okn test suite:

- `unittest.mock`, `MagicMock`, `create_autospec`, `@patch`, or other mock factories
- Synthetic result objects created solely to satisfy a type shape without executing the real code
- Replacing parser or metric bodies with stubs so tests never run real logic

Every test must exercise real code with real data.

### Hand-written stand-ins at I/O boundaries (allowed)

`OKNRegistry` accepts an injected `requests.Session`. `tests/core/test_registry.py`
defines a **minimal hand-written `StubSession`** (records calls, returns canned
responses) and a `make_registry(*responses)` factory — no network, no mock library.
This is the sanctioned pattern for HTTP boundaries: the real registry code runs
end to end against scripted responses.

### Orchestration boundary testing (allowed)

For **`src/daf_okn/analysis/`**, **`src/daf_okn/dashboard/`**, **`src/daf_okn/figures/`**, and **`src/daf_okn/core/manuscript_variables.py`** only:

- **`pytest.MonkeyPatch`** on module attributes (`project_root`, path overrides,
  logger wiring, etc.) — real functions run; I/O boundaries are redirected, not faked
- **Subprocess import isolation** — exercise CLI entry points as real subprocesses
  (see `tests/analysis/test_scripts_smoke.py`)

Pure modules (`core/graph.py`, `core/invariants.py`, `core/cognitive_adapter.py`,
parsing helpers in `core/registry.py`) should not need monkeypatch.

## Fixture Patterns

### Build small graph fixtures inline

```python
from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord

def make_graph() -> GraphDocument:
    """Two nodes, one directed edge — known counts for metric assertions."""
    return GraphDocument(
        name="fixture",
        nodes=[NodeRecord(id="a", title="A", node_type="concept"),
               NodeRecord(id="b", title="B", node_type="concept")],
        edges=[EdgeRecord(source="a", target="b", relation="related")],
    )
```

### Use fixture helpers for reusable graph shapes, not for mocking

## Tolerance Constants

```python
# Standard tolerances for floating-point comparisons
ATOL = 1e-4   # Absolute tolerance
RTOL = 1e-6   # Relative tolerance

# Use in assertions
assert abs(metrics["density"] - expected) < ATOL

- **ATOL=1e-4**: Acceptable for density/centrality comparisons
- **RTOL=1e-6**: Acceptable for ratio-style metric checks
- Use `pytest.approx` (or explicit deltas) for scalar metrics

## Test Class Organisation

```python
class TestValidateGraph:
    """Tests for validate_graph()."""

    def test_empty_ids_flagged(self):
        """Empty node ids are reported."""

    def test_dangling_endpoint(self):
        """Edges referencing unknown nodes are reported."""

    def test_self_loop(self):
        """Self-loops are reported."""

    def test_wellformed_document(self):
        """A clean graph yields an empty problem list."""
```

- One test class per public function or class
- Class name: `Test{FunctionOrClassName}`
- Method names: `test_{what_is_being_tested}`
- Each test method must have a docstring

## Parametrize Usage

```python
@pytest.mark.parametrize(
    ("iri", "expected"),
    [
        ("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "type"),
        ("https://purl.org/okn/frink/kg/biohealth", "biohealth"),
        ("plainword", "plainword"),
    ],
)
def test_local_parts(self, iri: str, expected: str) -> None:
    """local_name strips the namespace off an IRI."""
    assert local_name(iri) == expected
```

Use `parametrize` when testing the same behaviour across multiple inputs. Don't use it for fundamentally different test scenarios.

## Error-Path Testing

```python
def test_malformed_payloads_raise(self) -> None:
    """Malformed SPARQL JSON raises RegistryError."""
    with pytest.raises(RegistryError):
        parse_sparql_json({"results": {"bindings": "nope"}})
```

- Always use `match=` to verify the error message content where the message is stable
- Test every documented `Raises` clause in the docstring (`RegistryError` on HTTP ≥ 400,
  `FileNotFoundError` for a missing `graph_report.json` in pipeline mode)

## Coverage Verification

```bash
# Run with coverage (gate is 90% enforced by pyproject.toml)
uv run pytest tests/ \
    --cov=src \
    --cov-report=term-missing \
    --cov-fail-under=90

# Generate HTML report
uv run pytest tests/ \
    --cov=src \
    --cov-report=html
```

`pyproject.toml` enforces `fail_under = 90` as the CI gate. Do not delete tests to make a coverage number work — fix the gap.

## Determinism

- **Fixed inputs preferred** — parsers and metrics are deterministic; build explicit fixtures
- **Layout seeds must be pinned** — `plot_network(seed=...)` is deterministic for a
  given seed; assert file-level determinism, never pixel-exact values across platforms
- **No time-dependent assertions** — test correctness properties, not wall-clock values

## See Also

- [AGENTS.md](AGENTS.md) — Test cluster listing and run commands
- [../src/STYLE.md](../src/STYLE.md) — How source code should be structured
- [../src/daf_okn/core/invariants.py](../src/daf_okn/core/invariants.py) — Invariant checks covered by `test_invariants.py`
- [../scripts/build_dashboard.py](../scripts/build_dashboard.py) — Dashboard CLI covered by `test_dashboard_dafokn.py`
- [../scripts/generate_api_docs.py](../scripts/generate_api_docs.py) — Auxiliary smoke in `test_scripts_smoke.py`
- [../scripts/00_preflight.py](../scripts/00_preflight.py) — Auxiliary smoke in `test_scripts_smoke.py` (exit 0 or 1)
- [../docs/testing_philosophy.md](../docs/testing_philosophy.md) — Zero-mock rationale
