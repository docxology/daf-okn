# Manuscript Variables and Rendering

The `manuscript/` directory holds the narrative as Markdown plus `config.yaml`. This repository computes the numbers that go into the prose and writes them to `output/data/manuscript_variables.json`, and writes copies of the chapters with the numbers filled in to `output/manuscript/`; it does not render a PDF or HTML itself. This document describes each step, which scripts run it, and how to troubleshoot failures.

## The Research-to-Manuscript Flow

The workflow has two steps; the second needs the first one's `graph_report.json`.

### Pull, export, analyze, visualize

**Script**: `scripts/10_research_workflow.py` (from repository root)

**Command**:
```bash
uv run python scripts/10_research_workflow.py --cognitive-repo <vault>
```

**Inputs**: the OKN registry catalog (`kgs.yaml` via `OKNRegistry`), the Active Inference Institute `cognitive` vault (via `--cognitive-repo` or `$DAF_OKN_COGNITIVE_REPO`)

**Stages** (in-process calls; each delegates to the same modules the thin CLI wrappers use):

1. `pull_registry` — snapshot the registry graph list to `output/data/registry_snapshot.yaml`
2. `export_cognitive` — export the vault to `output/data/cognitive_kg.json` (skipped by design when no repository root is configured)
3. `analyze_graph` — measure the graph into `output/data/graph_report.json` via `src/daf_okn/analysis/pipeline.py::run_analysis`
4. `visualize` — render `output/figures/registry_catalog.png` and `output/figures/cognitive_network.png` via `src/daf_okn/figures/network_figure.py`

The individual stages also have thin CLI wrappers: `scripts/pull_registry.py`, `scripts/export_cognitive.py`, `scripts/analyze_graph.py`, `scripts/build_dashboard.py`.

**Outputs**:

| File | Location | Content |
|---|---|---|
| `registry_snapshot.yaml` | `output/data/` | Registry graph catalog snapshot (`kgs:` list) |
| `cognitive_kg.json` | `output/data/` | Exported cognitive knowledge graph (`GraphDocument` JSON) |
| `graph_report.json` | `output/data/` | Structural metrics report (counts, density, connectivity, mean degree, triangles, centralities) |
| `registry_catalog.png` | `output/figures/` | Bar chart of registered graphs by metadata fields |
| `cognitive_network.png` | `output/figures/` | Spring-layout network figure of the exported graph |
| `dashboard.html` | `output/web/` | Static HTML dashboard (`scripts/build_dashboard.py`) |

### Manuscript variables

**Script**: `scripts/z_generate_manuscript_variables.py` (thin orchestrator; logic lives in `src/daf_okn/core/manuscript_variables.py`)

**Command**:
```bash
uv run python scripts/z_generate_manuscript_variables.py
```

**Inputs**: `manuscript/config.yaml` + `output/data/graph_report.json`

**What it does**: Calls `src/daf_okn/core/manuscript_variables.py::generate_variables(config_path, require_analysis_outputs=True)` (default) to compute all token values, then writes the flat `{TOKEN: value}` mapping to `output/data/manuscript_variables.json` and the token-substituted chapters to `output/manuscript/`.

**Strict default**: Fails with `FileNotFoundError` when `output/data/graph_report.json` is missing. Use `--allow-draft` only for intentional early drafts that may emit `"N/A"` for result-derived tokens.

**Output**: `output/data/manuscript_variables.json` — complete `{ "TOKEN": "value" }` mapping, plus the resolved chapters in `output/manuscript/`.

### Rendering

`scripts/z_generate_manuscript_variables.py` substitutes the `{{TOKEN}}` markers in `manuscript/*.md` with the values from `manuscript_variables.json` and writes the result to `output/manuscript/` (tokens with no value are left in place and printed). Producing PDF or HTML from those copies is left to whatever Markdown/Pandoc toolchain you use. Before publishing, check that no literal `{{TOKEN}}` text remains in the rendered output. If you render with Pandoc and XeLaTeX, `manuscript/preamble.md` holds a LaTeX package preamble you can pass in as a header include, and `manuscript/references.bib` is the bibliography. Mermaid blocks in the chapters need a Mermaid-aware step if you want them rasterised.

## config.yaml Controls

| YAML Key | Controls | Consumed by |
|---|---|---|
| `paper.title`, `paper.subtitle` | `{{CONFIG_TITLE}}`, `{{CONFIG_SUBTITLE}}` | `src/daf_okn/core/manuscript_variables.py` |
| `paper.version` | `{{CONFIG_VERSION}}` token | `src/daf_okn/core/manuscript_variables.py` |
| `authors[0].name` | `{{CONFIG_FIRST_AUTHOR}}` | `src/daf_okn/core/manuscript_variables.py` |
| `keywords` | `{{CONFIG_KEYWORDS}}` (comma-joined); default queries for `scripts/08_connector_search.py` | `src/daf_okn/core/manuscript_variables.py`, `scripts/08_connector_search.py` |

The remaining keys (`authors[*]` details, `metadata`, and the `variables:` map) are descriptive; nothing else in the code reads them.

## Troubleshooting

### Unresolved `{{VARIABLE}}` appears in rendered output

**Symptom**: The rendered document contains literal `{{TOKEN_NAME}}` text.

**Cause**: Manuscript variables (`scripts/z_generate_manuscript_variables.py`) did not run, the substitution step was skipped, or the token is not produced by `src/daf_okn/core/manuscript_variables.py::generate_variables()`.

**Fix**:
```bash
# Check whether output/data/manuscript_variables.json exists
ls output/data/manuscript_variables.json

# Re-run manuscript variables
uv run python scripts/z_generate_manuscript_variables.py

# List tokens used in the chapters
grep -rhoE "\{\{[A-Z_]+\}\}" manuscript/*.md | sort -u
```

### `FileNotFoundError` on graph_report.json

**Symptom**: Variable hydration fails with `FileNotFoundError` naming `output/data/graph_report.json`.

**Cause**: The analysis stage has not run in pipeline mode (no `--allow-draft`).

**Fix**:
```bash
uv run python scripts/10_research_workflow.py
# or analyze an existing graph document:
uv run python scripts/analyze_graph.py --graph output/data/cognitive_kg.json --out-dir output/data
```

### Missing figure in rendered output

**Symptom**: Broken image placeholder or missing figure reference.

**Cause**: The visualize stage failed to generate one or both figures, or `manuscript/*.md` references a figure that was never generated.

**Fix**:
```bash
ls output/figures/*.png
uv run python scripts/10_research_workflow.py
```

### BibTeX citation error

**Symptom**: Your Pandoc/LaTeX run reports a BibTeX error or an undefined citation key.

**Cause**: Malformed entry in `manuscript/references.bib` (unclosed braces, duplicate keys, missing required fields).

**Fix**: Validate `manuscript/references.bib` with a BibTeX linter and check your renderer's log for the specific error message.
