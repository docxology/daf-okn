# docs/ — Agent-Facing Documentation Hub

## Overview

Technical guide for `docs/` — the operational rulebook for AI agents and developers working inside the daf-okn project. Every document in this directory is a hard constraint, not a suggestion.

## File Inventory

| File | Purpose | Lines | Status |
|---|---|---|---|
| `README.md` | Quick navigation and audience-targeted entry points | ~100 | Current |
| `AGENTS.md` | This index — technical overview of `docs/` | ~110 | Current |
| `agent_instructions.md` | Behavioral constraints for AI agents (read-first priority) | ~160 | Comprehensive |
| `architecture.md` | Thin orchestrator flow: layers, dependencies, forbidden patterns, how-to-add-a-capability | ~100 | Comprehensive |
| `stack-integration.md` | Local artifact status, Sidecar foothold and separate native acceptance evidence | ~90 | Current |
| `testing_philosophy.md` | Zero-mock policy; coverage mechanics; test-file inventory (live counts via `--collect-only`) | ~110 | Comprehensive |
| `faq.md` | Frequently asked questions about architecture, testing, manuscripts | ~130 | Comprehensive |
| `troubleshooting.md` | Symptom-driven recipes for common failures | ~253 | Comprehensive |
| `quickstart.md` | 5-minute first-run walkthrough | ~90 | Comprehensive |
| `output_conventions.md` | `output/` directory layout and regeneration | ~120 | Comprehensive |
| `output_inventory.md` | Producer/consumer graph for pipeline artifacts | ~100 | Comprehensive |
| `forking_guide.md` | Fork workflow, required-vs-aesthetic, friction-point table | ~120 | Comprehensive |
| `rendering_pipeline.md` | Research workflow → manuscript variables; rendering notes; config.yaml controls; troubleshooting | ~120 | Comprehensive |
| `style_guide.md` | 7 rules: Zero-Mock, Module Layering, Thin Orchestrator, Show-Not-Tell, Explicit Paths, Type Hints, Error Messages | ~190 | Comprehensive |
| `syntax_guide.md` | Markdown links, LaTeX refs, all 21 `{{VARIABLE}}` tokens, figure label registry, adding variables/figures | ~200 | Comprehensive |

## Key Conventions

**Read-first protocol**: AI agents must read `agent_instructions.md` before modifying any project file. Skipping this document is the most common source of errors in this project — agents who skip it tend to: introduce mocks (violating Rule 1), write parsing/metric logic in `scripts/` (violating Rule 3), or hardcode numbers in manuscript prose (violating Rule 4 of `style_guide.md`). The consequence of any one violation is a CI failure or a misleading project for future users.

**Architecture isolation**: the **graph core** in `src/daf_okn/core/` (`graph.py`, `invariants.py`, `cognitive_adapter.py`) is pure logic; the **orchestration modules** (`analysis/`, `figures/`, `dashboard/`, `core/manuscript_variables.py`, `core/documentation.py`) live in `src/` for testability; `scripts/` is glue (no logic). The dependency arrow remains one-directional: `scripts/` → `src/`; `tests/` → `src/`. Nothing imports upward. The pure-core claim is load-bearing: `core/graph.py` and `core/invariants.py` can be lifted into any Python environment.

**Zero-mock enforcement**: No `unittest.mock`, `MagicMock`, `@patch`, or `create_autospec` anywhere in `tests/`. HTTP boundaries use the hand-written `StubSession` injected into `OKNRegistry` (`tests/core/test_registry.py`); the real client code runs end to end. The enforcement exists because mock tests can pass even when the actual logic is wrong — they test call signatures, not structural correctness.

**Show-not-tell**: Manuscript references must use explicit file paths and function names, not vague descriptions. A reader of `02_methodology.md` should be able to open `src/daf_okn/analysis/graph_metrics.py` and find the exact function being discussed within 10 seconds. Vague descriptions like "the test suite validates accuracy" cannot be verified or linked.

## Reading Order

This sequence is intentional. Each document provides context that the next document assumes:

1. **`agent_instructions.md`** — Start here. 7 hard rules; consequence of violating each; verification checklist you run before submitting.
2. **`architecture.md`** — Understand layer boundaries before touching any file. Contains the forbidden-patterns table and the 5-step capability-addition protocol.
3. **`testing_philosophy.md`** — Understand the zero-mock constraint and test inventory before writing or modifying any test. Contains the coverage run command.
4. **`rendering_pipeline.md`** — Understand how manuscript variables are produced (and that rendering is left to your own toolchain) before editing manuscript or output paths. Contains the config.yaml controls and troubleshooting steps.
5. **`style_guide.md`** — Understand the 7 style rules before writing any source code. Rules 1–3 govern code; Rules 4–5 govern documentation; Rules 6–7 govern type hints and error messages.
6. **`syntax_guide.md`** — Understand the complete `{{VARIABLE}}` token list and figure label registry before editing any manuscript `.md` file.

## Verification Commands

These commands verify the most critical constraints. Run both before submitting any change:

```bash
# Test suite passes + coverage ≥90%
uv run pytest tests/ \
    --cov=src \
    --cov-fail-under=90 -q

# No mocks in tests/
grep -rn "unittest.mock\|MagicMock\|@patch\|create_autospec" --include='*.py' \
    tests/ || echo "Clean"
```

## REQUIRED vs AESTHETIC

A forker copying this project should know which directories and files
are gate-enforced (delete them and the gate fails) and which are
convention only (delete them and nothing complains automatically). The
distinction matters when you trim the project down to your minimum
viable tool.

| Path | Status | Enforcing gate / source of truth |
|------|--------|---------------------------------|
| `src/daf_okn/core/graph.py` | REQUIRED | Coverage gate; `tests/core/test_graph.py` |
| `src/daf_okn/core/invariants.py` | REQUIRED | `tests/core/test_invariants.py` |
| `src/daf_okn/core/registry.py` | REQUIRED | `tests/core/test_registry.py` (stub-session queries) |
| `src/daf_okn/core/cognitive_adapter.py` | REQUIRED | `tests/core/test_cognitive_adapter.py` |
| `src/daf_okn/core/contribute.py` | REQUIRED | `tests/core/test_contribute.py` |
| `src/daf_okn/core/manuscript_variables.py` | REQUIRED | `tests/core/test_manuscript_variables.py` + live `{{TOKEN}}` cross-reference |
| `src/daf_okn/analysis/` | REQUIRED (orchestration) | Exercised by `scripts/analyze_graph.py` and `scripts/10_research_workflow.py`; `tests/analysis/test_graph_metrics.py` |
| `src/daf_okn/figures/` | REQUIRED (orchestration) | `plot_network` / `plot_graph_catalog`; `tests/figures/test_network_figure.py` |
| `src/daf_okn/dashboard/` | REQUIRED (orchestration) | Exercised by `scripts/build_dashboard.py`; `tests/dashboard/test_dashboard_dafokn.py` |
| `tests/` (all `test_*.py`) | REQUIRED | 90% coverage gate (`pyproject.toml`) |
| `tests/conftest.py` | REQUIRED | Pins `MPLBACKEND=Agg` + `src/` `sys.path`; without it pytest cannot collect |
| `scripts/10_research_workflow.py` | REQUIRED | End-to-end research stages; manuscript hydration depends on `output/data/graph_report.json` |
| `scripts/z_generate_manuscript_variables.py` | REQUIRED | Hydrates `{{TOKEN}}`s; default strict mode requires `output/data/graph_report.json` (`--allow-draft` for early drafts) |
| `scripts/pull_registry.py`, `scripts/export_cognitive.py`, `scripts/analyze_graph.py`, `scripts/build_dashboard.py` | REQUIRED (CLI wrappers) | Thin delegates over the modules above |
| `scripts/generate_api_docs.py` | AESTHETIC | Auxiliary docs generator; smoke-tested by `tests/analysis/test_scripts_smoke.py`; nothing consumes its output |
| `scripts/00_preflight.py` | AESTHETIC | Environment check; smoke-tested by `tests/analysis/test_scripts_smoke.py`; the workflow still runs without it |
| `scripts/08_connector_search.py`, `scripts/09_provenance_record.py` | REQUIRED (contribution stages) | Registry connector search; provenance record for packaged contributions |
| `tests/analysis/test_scripts_smoke.py` | AESTHETIC | Subprocess smoke for auxiliary scripts (`generate_api_docs.py`, `00_preflight.py`) |
| `tests/core/test_documentation.py` | AESTHETIC | Unit tests for `core/documentation.py` API reference helpers |
| `manuscript/config.yaml` | REQUIRED | Read by `core/manuscript_variables.py`; tests and variable generation use it |
| `manuscript/*.md` | REQUIRED | Chapter sources; `test_all_manuscript_tokens_are_generated` scans them |
| `manuscript/references.bib` | AESTHETIC | Bibliography for your own Pandoc run |
| `manuscript/preamble.md` | AESTHETIC | Optional LaTeX preamble if you render with Pandoc/XeLaTeX |
| `manuscript/SYNTAX.md` | AESTHETIC | Authoring guide for humans; nothing reads it |
| `manuscript/config.yaml.example` | AESTHETIC | Documentation; forkers copy → `config.yaml` |
| `manuscript/AGENTS.md` | AESTHETIC | Agent guide; nothing reads it |
| `docs/*.md` | AESTHETIC | Agent + human documentation; no gate parses these |
| `src/STYLE.md`, `tests/PATTERNS.md`, `scripts/CONVENTIONS.md` | AESTHETIC | Per-subdir style/test/script conventions |
| `src/AGENTS.md`, `tests/AGENTS.md`, `scripts/AGENTS.md` | AESTHETIC | Per-subdir agent guides |
| `docs/output_inventory.md` | AESTHETIC | Producer/consumer graph for `output/`; lives in `docs/` because the repo `.gitignore` excludes `output/` |
| `pyproject.toml` | REQUIRED | Coverage gate config, pytest options, dependency declarations |
| `.gitignore` | REQUIRED | Keeps `output/` and local caches untracked |
| `README.md`, `AGENTS.md` (root) | AESTHETIC (load-bearing for humans/agents) | Read by every newcomer; drift = a confused forker |

"AESTHETIC" does NOT mean "throwaway" — drift in an aesthetic file
typically rots over months and silently misleads future contributors. It
means "no pre-commit hook will tell you when it rots." Treat the
AESTHETIC list as the audit surface that lives outside automated CI.

## Cross-References

- [`README.md`](README.md) — Quick reference with audience-targeted entry points
- [`../AGENTS.md`](../AGENTS.md) — Project-level documentation (API reference, known issues, full directory map)
- [`../pyproject.toml`](../pyproject.toml) — Coverage gate settings (`fail_under = 90`, `branch = true`)
- [`../tests/conftest.py`](../tests/conftest.py) — `sys.path` setup and `MPLBACKEND=Agg`
- [`../manuscript/AGENTS.md`](../manuscript/AGENTS.md) — Manuscript directory: `{{VARIABLE}}` protocol, figure list, workflow
- [`../src/AGENTS.md`](../src/AGENTS.md) — Source-layer module map and dependency rules
