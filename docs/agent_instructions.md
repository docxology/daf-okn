# AI Agent Instructions — daf_okn

## Why This File Exists

`daf_okn` is a research tooling project for the Open Knowledge Network
(OKN): pulling registry data, analyzing and visualizing knowledge graphs, and
contributing back. Deviating from the rules below — introducing a mock, or moving
project logic into scripts/ — breaks
the project's reproducibility guarantees and misleads future users.

Read this file before touching any other file in this project.

---

## Rule 1: Read the Hub First

Reading order is mandatory, not advisory. Each document gates a category of action:

| Document | Governs | Skip consequence |
|---|---|---|
| **This file** | All modifications | Risk all violations below |
| [`architecture.md`](architecture.md) | Any file-boundary change | Risk violating src/scripts boundary |
| [`testing_philosophy.md`](testing_philosophy.md) | Any test modification | Risk introducing mocks or reducing coverage |
| [`rendering_pipeline.md`](rendering_pipeline.md) | Any manuscript or output change | Risk unresolved `{{VARIABLE}}` tokens in rendered output |
| [`style_guide.md`](style_guide.md) | Any source code modification | Risk mock usage, logic in scripts, bad error messages |
| [`syntax_guide.md`](syntax_guide.md) | Any manuscript `.md` modification | Risk hardcoded numbers, broken figure references |

---

## Rule 2: Coverage Gate — ≥90% on `src/`

The test suite spans `tests/core/` (graph, registry, invariants, cognitive
adapter, contribute, manuscript variables, documentation, project paths,
runtime), `tests/analysis/` (graph metrics, script smoke), `tests/figures/`
(network figures), and `tests/dashboard/`. The project `pyproject.toml`
gate sets coverage at **90%**. Live test count + coverage percentage — report them with
`uv run pytest tests/ --collect-only -q` and
`uv run pytest tests/ --cov=src --cov-fail-under=90`; do not hardcode either
number in prose, because both drift faster than the docs touching them.

Before modifying a module in `src/daf_okn/`, count the existing tests for the
function you are changing. After modifying, run:

```bash
uv run pytest tests/ \
    --cov=src \
    --cov-fail-under=90 \
    --cov-report=term-missing \
    -v
```

If coverage drops, do not delete tests to make the number work — fix the gap.

---

## Rule 3: The Thin Orchestrator Boundary — `scripts/` vs `src/`

**`src/daf_okn/core/`** contains pure project logic: no side-effects at
import (the registry performs I/O only on request). `core/_runtime.py` holds
the shared helpers (`get_logger`, `save_figure_data`).

**`scripts/*.py`** contains orchestration: CLI argument parsing, calls to
`src/` functions, and writing JSON/PNG/HTML artifacts. Each script depends only
on `src/daf_okn` and the declared project dependencies.

**The boundary test**: If a line of code in `scripts/` implements project
behavior (graph construction, metric computation, RDF serialization,
contribution packaging) rather than coordinating it, it violates the
boundary. Move that logic to `src/` and write a test for it.

**Forbidden**:
```python
# In scripts/analyze_graph.py — BAD
density = 2 * edge_count / (node_count * (node_count - 1))  # Metric belongs in src/
```

**Correct**:
```python
# In scripts/analyze_graph.py — GOOD
report = run_analysis(graph, out_dir=args.out_dir)
```

---

## Rule 4: "Show, Not Tell" Documentation

When updating `manuscript/` files, use explicit, verifiable references instead of vague descriptions.

**BAD** (vague, unverifiable):
```markdown
Our testing framework validates graph metrics using standard approaches.
```

**GOOD** (concrete, linkable):
```markdown
`tests/analysis/test_graph_metrics.py` validates density, connectivity, and
centrality against hand-computed graphs without mocks, using fixed
`GraphDocument` fixtures.
```

**BAD** (vague):
```markdown
The pipeline computes the network metrics automatically.
```

**GOOD** (concrete):
```markdown
`src/daf_okn/analysis/pipeline.py::run_analysis` calls `compute_metrics` and
writes `output/data/graph_report.json`.
```

---

## Rule 5: Determinism Policy

Prefer fixed inputs in `src/` and tests. When a test uses random draws (e.g., layout coordinates for network figures), two requirements apply:

1. Assertions must use **bounds** (`assert elapsed < 5.0`), not exact values (`assert elapsed == 0.003`).
2. The test docstring must explain why the nondeterministic property is the relevant one to check.

Fixed seeds are acceptable for layout randomness:
```python
rng = np.random.default_rng(42)
positions = spring_layout(graph, seed=42)
```

Prefer analytical fixtures (hand-built `GraphDocument`s) over generated data
whenever a structural property (density, component counts) can be directly
verified.

---

## Rule 6: Style and Syntax Guides Govern Their Domains

- **[`style_guide.md`](style_guide.md)** governs: `src/daf_okn/`, `tests/`, `scripts/*.py` — mock prohibition, thin orchestrator, error message format, type hints.
- **[`syntax_guide.md`](syntax_guide.md)** governs: `manuscript/*.md` — `{{VARIABLE}}` injection, `[@label]` Pandoc-crossref cross-references, figure labels, table captions.

Do not apply code-style rules to manuscript prose, and do not apply manuscript syntax rules to Python source.

---

## Rule 7: `output/` Is Disposable — Never Edit Generated Files

The entire `output/` tree is written by the pipeline and overwritten on every run. Editing a file in `output/` has zero lasting effect and will confuse future agents.

If you need to change what a generated file contains, change the **generator**:
- To change `output/data/graph_report.json` → modify `src/daf_okn/analysis/pipeline.py` (re-run via `scripts/analyze_graph.py`)
- To change `output/data/manuscript_variables.json` → modify `src/daf_okn/core/manuscript_variables.py` and/or `manuscript/config.yaml`, then re-run `scripts/z_generate_manuscript_variables.py`
- To change a rendered manuscript (PDF/HTML) → modify the files in `manuscript/`, then re-render with your own Markdown/Pandoc toolchain

See [`output_conventions.md`](output_conventions.md) for the complete regeneration sequence.

---

## Verification Checklist

Run both commands before submitting any change to this project:

```bash
# 1. Tests pass and coverage gate is met
uv run pytest tests/ \
    --cov=src \
    --cov-fail-under=90 -q

# 2. No mocks exist anywhere in tests/
grep -r "unittest.mock\|MagicMock\|@patch\|create_autospec" \
    tests/ || echo "Clean — no mocks found"
```

Both must pass (tests green and coverage met; the "Clean" message for check 2).
