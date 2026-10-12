# Quick Start Guide

Get up and running with the `daf_okn` project in 5 minutes.

## Prerequisites

- Python 3.10 or higher
- [`uv`](https://github.com/astral-sh/uv) package manager
- Git

## Setup (One-Time)

```bash
# 1. Clone the repository (if you haven't already)
git clone https://github.com/docxology/daf-okn.git
cd daf-okn

# 2. Install dependencies at the repository root
uv sync

# 3. Verify installation
uv run python scripts/00_preflight.py
```

## Run the Test Suite

Validate the environment and check that the project test suite passes with the ≥90% coverage gate.
Falling below that floor fails the gate outright (`--cov-fail-under` enforces it), and zero-collected suites fail too rather than counting as a pass.

```bash
uv run pytest tests/ -v --tb=short
```

Expected: passing tests and coverage above the 90% gate. Report live counts with
`uv run pytest tests/ --collect-only -q` — never hardcode totals in docs.

## Run the Research Workflow

Pull the OKN registry catalog, export the cognitive knowledge base, analyze the graph, and produce figures:

```bash
uv run python scripts/10_research_workflow.py --cognitive-repo <vault>
```

**Outputs created under `output/`:**
- `data/registry_snapshot.yaml` — registry catalog snapshot
- `data/cognitive_kg.json` — exported `GraphDocument`
- `data/graph_report.json` — structural metrics and problems
- `figures/` — registry catalog + cognitive network PNGs

Network access is required for stage 1 (registry pull) and the connector
search (`scripts/08_connector_search.py`); stages 2–3 (cognitive export,
analysis) run offline once the graph JSON exists.

## Package and Contribute

Validate and package a registry contribution with per-artifact SHA-256 records:

```bash
uv run python scripts/09_provenance_record.py --graph output/data/cognitive_kg.json --preset cognitive-kb
```

Exit 1 if `validate_package` reports problems; inspect
`output/data/provenance/provenance_record.json`.

## Generate Manuscript Variables

```bash
uv run python scripts/z_generate_manuscript_variables.py
```

Strict hydration requires `output/data/graph_report.json`; add `--allow-draft`
for early drafts (`"N/A"` sentinels). The results are
`output/data/manuscript_variables.json` and the resolved chapters in
`output/manuscript/`; rendering to PDF/HTML is left to your
own Markdown/Pandoc toolchain (see [`rendering_pipeline.md`](rendering_pipeline.md)).

## View Results

- **HTML dashboard**: open `output/web/dashboard.html` (via `scripts/build_dashboard.py`)
- **Figures**: browse `output/figures/`
- **Data**: `cat output/data/graph_report.json`

## Common Next Steps

- **Analyze a different graph**: run `uv run python scripts/analyze_graph.py --graph <graph.json> --out-dir output/analysis`.
- **Query a graph**: use `scripts/pull_registry.py` (catalog snapshot, per-graph/federation SPARQL) or `OKNRegistry` directly (see `docs/architecture.md`).
- **Modify the manuscript**: edit markdown files under `manuscript/`, then regenerate the variables (step above) and re-render with your own toolchain.

## Getting Help

- **Full documentation**: [`docs/README.md`](README.md) — navigation hub
- **Agent rules**: [`docs/agent_instructions.md`](agent_instructions.md) — critical constraints before modifying code
- **Troubleshooting**: [`docs/troubleshooting.md`](troubleshooting.md) — common issues and fixes
- **FAQ**: [`docs/faq.md`](faq.md)

## Quick Command Reference

| Task | Command |
|---|---|
| Run tests | `uv run pytest tests/ -v` |
| Preflight environment check | `uv run python scripts/00_preflight.py` |
| Pull registry snapshot / SPARQL | `uv run python scripts/pull_registry.py` |
| Export cognitive vault | `uv run python scripts/export_cognitive.py --repo <vault>` |
| Analyze a graph | `uv run python scripts/analyze_graph.py --graph <graph.json>` |
| Full research workflow | `uv run python scripts/10_research_workflow.py --cognitive-repo <vault>` |
| Package contribution | `uv run python scripts/09_provenance_record.py --graph <graph.json>` |
| Connector search (network) | `uv run python scripts/08_connector_search.py` |
| Generate manuscript variables | `uv run python scripts/z_generate_manuscript_variables.py` (strict; requires `graph_report.json`; add `--allow-draft` for early drafts) |
| Build dashboard | `uv run python scripts/build_dashboard.py --graph <graph.json>` |
| Generate API docs | `uv run python scripts/generate_api_docs.py` |
| Render PDF/HTML | Not provided here; use your own Markdown/Pandoc toolchain (see [`rendering_pipeline.md`](rendering_pipeline.md)) |
| Clean outputs | `rm -rf output/` |
