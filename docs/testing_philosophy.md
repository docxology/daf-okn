# Testing Philosophy: The Zero-Mock Standard

The daf-okn project strictly forbids mocking in validation of graph parsing, metrics, and packaging.

## Why Zero Mocks?

The core insight is architectural: if a function requires a mock to be tested, it is doing I/O, calling external systems, or producing side-effects — which means it belongs in `scripts/` (as a thin orchestrator) or behind an injected boundary, not in pure `src/` logic. The purity of `src/daf_okn/core/graph.py`, `core/invariants.py`, and `core/cognitive_adapter.py` is what makes zero-mock testing achievable: every function is deterministic and side-effect-free, so tests simply call functions with real graph fixtures and verify real structural outputs.

Where I/O is unavoidable, the boundary is injected and hand-stubbed — `OKNRegistry` takes a `requests.Session`, and `tests/core/test_registry.py` supplies a minimal `StubSession` that records calls and returns canned responses. The real client code runs end to end; no network, no mock library.

If you ever feel the urge to mock something in a test for `src/`, treat it as a signal: move that code to `scripts/` and test the `src/` boundary directly.

## The Validation Suite

| File | Role |
| --- | --- |
| `tests/core/test_graph.py` | `GraphDocument` model: records, dict/JSON round-trips, `to_networkx`, `bindings_to_graph` |
| `tests/core/test_registry.py` | Endpoint constants, SPARQL JSON / `kgs.yaml` parsing, `OKNRegistry` queries over a stub session, `RegistryError` paths |
| `tests/core/test_invariants.py` | `validate_graph` problem detection and `graph_stats` values |
| `tests/core/test_cognitive_adapter.py` | Frontmatter, wiki links, semantic relations, redirects, vault → graph |
| `tests/core/test_contribute.py` | N-Quads round-trips, registry entry, checklist, `validate_package` |
| `tests/core/test_manuscript_variables.py` | `{{TOKEN}}` map from config + `graph_report.json`, `--allow-draft` sentinels, live manuscript cross-reference |
| `tests/core/test_documentation.py` | `core/documentation.py` API reference builder |
| `tests/core/test_stack_roster.py` | `daf-stack` roster parsing and offline membership checks (`stack-health`) |
| `tests/core/test_project_paths.py` | `resolve_project_root` and context overrides |
| `tests/core/test_runtime.py` | `core/_runtime.py` helpers |
| `tests/analysis/test_graph_metrics.py` | `compute_metrics` and metric helpers |
| `tests/analysis/test_scripts_smoke.py` | Subprocess smoke (`generate_api_docs.py`, `00_preflight.py`) |
| `tests/figures/test_network_figure.py` | Deterministic PNG builders, layout validation |
| `tests/dashboard/test_dashboard_dafokn.py` | Payload contract, capped tables, static HTML CLI end to end |

Configuration: `pyproject.toml` (`fail_under = 90`, branch coverage)

Conftest: `tests/conftest.py` (sets `MPLBACKEND=Agg`, adds `src/` to `sys.path`)

Live test count and coverage percentage: `uv run pytest tests/ --collect-only -q` from the project directory — do not hardcode totals in docs.

## Test Class Inventory (graph model — `test_graph.py`)

| Class | Covers |
| --- | --- |
| `TestRecordDefaults` | `NodeRecord` / `EdgeRecord` defaults |
| `TestGraphDocumentDict` | `to_dict` / `from_dict` round-trips |
| `TestPersistence` | `save_json` / `load_json` |
| `TestToNetworkx` | Directed/undirected projections, node/edge attributes |
| `TestBindingsToGraph` | SPARQL JSON → graph, variable-role resolution |

## Coverage Mechanics

`pyproject.toml` settings relevant to coverage:

```toml
[tool.coverage.run]
source = ["src"]
branch = true
omit = ["tests/*", "*/__init__.py", "*/test_*.py"]

[tool.coverage.report]
fail_under = 90
```

Authoritative gate (measures all of `src/`, including orchestration modules):

```bash
uv run pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90
```

## Zero-Mock Checklist

Before submitting any test, verify all boxes are checked:

- [ ] Test uses real graph fixtures or real vault/files as inputs
- [ ] Test calls `src/` functions directly with real data
- [ ] Test asserts structural properties (counts, round-trips, problem lists), not call counts
- [ ] No `unittest.mock`, `MagicMock`, `create_autospec`, `@patch`, or mock factories
- [ ] Network boundaries use the injected `StubSession` pattern — real code, canned responses, never a fake of the module under test
- [ ] Timing assertions use bounds, not exact values

## Orchestration Branch Testing

Orchestration modules (`analysis/`, `dashboard/`, `figures/`, `core/manuscript_variables.py`, `scripts/`) may use **`pytest.MonkeyPatch`** on module attributes and **subprocess import isolation** to hit error paths. That is not the same as mocking algorithm output: real code runs with redirected boundaries. See [`../tests/PATTERNS.md`](../tests/PATTERNS.md) and [`../tests/analysis/test_scripts_smoke.py`](../tests/analysis/test_scripts_smoke.py).

## Structural Rule: If You Need a Mock, Move the Code

- **`src/daf_okn/core/graph.py`, `core/invariants.py`, `core/cognitive_adapter.py`** — Pure; no script or orchestration imports
- **`src/daf_okn/core/registry.py`, `core/contribute.py`** — Domain I/O behind injectable boundaries (`requests.Session`, rdflib in-memory)
- **`src/daf_okn/analysis/`, `figures/`, `dashboard/`, `core/manuscript_variables.py`** — Orchestration; build on `core/` and may write files
- **`scripts/*.py`** — CLI wrappers only

## Running the Gate

A green exit code is **not** proof the suite ran. Confirm **N collected > 0 AND coverage ≥ 90%**.

```bash
uv run pytest tests/ --cov=src --cov-fail-under=90 -q
```

See [`troubleshooting.md`](troubleshooting.md#tests-report-passed-but-ran-0-tests--00-coverage).
