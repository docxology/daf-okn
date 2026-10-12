# Forking Guide — daf-okn

> A 5-minute walkthrough for copying this project into a new
> research-tooling repository. The point of the guide is to make every
> decision explicit so a forker doesn't have to read every other doc to
> find out *what's required vs aesthetic, what's enforced vs convention,
> and what they'll hit friction on*.

## TL;DR

```bash
# 0. From the repo root, install deps once
uv sync

# 1. Copy the repository to your new project name
cp -R daf-okn my_project && cd my_project

# 2. Run the tests against your fork
uv run pytest tests/ --cov=src --cov-fail-under=90 -q

# 3. Run the research workflow against your fork
uv run python scripts/10_research_workflow.py --cognitive-repo <vault>
```

## What you're forking

This project is a **research-tooling skeleton**: pure-logic `src/daf_okn/`,
thin-orchestrator `scripts/`, real-data `tests/`, token-substituted
`manuscript/`, and a pull → export → analyze → visualize → hydrate
workflow. The point of the pattern: every numeric in the manuscript is a
`{{TOKEN}}` registered in one Python function
(`src/daf_okn/core/manuscript_variables.py::generate_variables()`) and
cross-checked by one regression test
(`tests/core/test_manuscript_variables.py::test_all_manuscript_tokens_are_generated`).
That's the discipline being taught — your fork should
preserve it regardless of what domain you swap in.

## REQUIRED vs AESTHETIC

A test or coverage gate fails if you delete a REQUIRED path. An
AESTHETIC path is convention only — delete it and nothing complains
automatically. The full inventory lives in [`AGENTS.md`](AGENTS.md);
the short version:

| Class | Examples | Action |
|---|---|---|
| REQUIRED — pipeline gate | `src/daf_okn/core/graph.py`, `core/invariants.py`, `core/manuscript_variables.py` (graph primitives + token hydration), all `tests/test_*.py`, `pyproject.toml`, `manuscript/config.yaml`, `manuscript/*.md`, `manuscript/references.bib` | Keep them; the 90% coverage gate and the token cross-check test depend on them |
| REQUIRED — orchestration | `src/daf_okn/analysis/`, `src/daf_okn/figures/`, `src/daf_okn/dashboard/`, all `scripts/*.py` | Exercised by `scripts/10_research_workflow.py` and the CLI smoke tests |
| AESTHETIC | `docs/*.md`, `*/STYLE.md`, `*/PATTERNS.md`, `*/CONVENTIONS.md`, `*/AGENTS.md`, `*/README.md` | Convention only; aspire to update them when code changes |

## Concrete first steps after fork

### 1. Replace the domain logic
Edit `src/daf_okn/core/` with your real domain logic. Keep it
free of script-level concerns — that purity is what lets you copy
`src/daf_okn/core/` into any Python environment. The orchestration
modules (`analysis/`, `figures/`, `dashboard/`) are the right place for
code that writes files.

### 2. Update the manuscript variables
`src/daf_okn/core/manuscript_variables.py::generate_variables()` is the **single
function** that produces every numeric token referenced in
`manuscript/*.md`. When you change the domain logic:

1. Add new tokens to `generate_variables()` and declare them in the
   `variables:` block of `manuscript/config.yaml`.
2. Reference them in your manuscript as `{{NEW_TOKEN}}`.
3. The regression test
   `tests/core/test_manuscript_variables.py::test_all_manuscript_tokens_are_generated`
   automatically fails if a token is referenced but not generated.

### 3. Update the test suite
`tests/` enforces the [Zero-Mock Policy](testing_philosophy.md). Every
test exercises real logic with real data — no `unittest.mock`,
`MagicMock`, or `@patch`. Orchestration tests may use `pytest.MonkeyPatch`
on module attributes or subprocess import isolation (see [`../tests/PATTERNS.md`](../tests/PATTERNS.md)) — not mock factories that fake logic output. If you find
yourself wanting to mock something inside pure `core/`, that means the code
belongs in `scripts/` instead.

### 4. Re-run the gate before pushing
```bash
uv run pytest tests/ --cov=src --cov-fail-under=90 -q
uv run python scripts/00_preflight.py
```

## Common friction points (and fixes)

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: daf_okn` | Running a script from inside `src/` instead of the repo root | `cd` to the repo root; `uv run python scripts/10_research_workflow.py` |
| Test count drift / coverage drift | Docs in `docs/` hardcoded an old number | Report live values (`uv run pytest tests/ --collect-only -q`); never hardcode totals in docs |
| `{{TOKEN}}` appears literally in the rendered document | `scripts/z_generate_manuscript_variables.py` was not re-run, the substitution step was skipped, or the token is not in `generate_variables()` | Re-run `z_generate_manuscript_variables.py`; if still literal, add the token to `generate_variables()` |
| `FileNotFoundError` on `output/data/graph_report.json` | Analysis stage not run in pipeline mode | `uv run python scripts/10_research_workflow.py`, or pass `--allow-draft` |
| Stale `*.egg-info/` after rename | `pip install -e .` regenerated it under the old package name | `rm -rf src/*.egg-info/`; the `.gitignore` glob already covers any future occurrence |

## See also

- [`AGENTS.md`](AGENTS.md) — full doc inventory and reading order
- [`agent_instructions.md`](agent_instructions.md) — 7 hard rules
- [`architecture.md`](architecture.md) — module boundaries
- [`testing_philosophy.md`](testing_philosophy.md) — zero-mock standard
- [`output_inventory.md`](output_inventory.md) — producer/consumer graph
- [`troubleshooting.md`](troubleshooting.md) — symptom-driven fixes
