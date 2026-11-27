# Manuscript Variables and Rendering

The maintained sources are in [`docs/manuscript/`](manuscript/README.md).
DAF-OKN produces the graph metrics, figures, and resolved Markdown. The pinned
`docxology/template` renderer builds and validates the PDF and HTML.

## The Research-to-Manuscript Flow

The workflow has two steps; the second needs the first one's `graph_report.json`.

### Pull, export, analyze, visualize

The SciPy version in the command supports sparse spring layouts for large graphs.

**Script**: `scripts/10_research_workflow.py` (from repository root)

**Command**:
```bash
uv run --locked --with scipy==1.17.1 python scripts/10_research_workflow.py --cognitive-repo <vault>
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

**Inputs**: `docs/manuscript/config.yaml` + `output/data/graph_report.json`

**What it does**: Calls `src/daf_okn/core/manuscript_variables.py::generate_variables(config_path, require_analysis_outputs=True)` (default) to compute all token values, then writes the flat `{TOKEN: value}` mapping to `output/data/manuscript_variables.json` and the token-substituted chapters to `output/manuscript/`.

**Strict default**: Fails with `FileNotFoundError` when `output/data/graph_report.json` is missing. Use `--allow-draft` only for intentional early drafts that may emit `"N/A"` for result-derived tokens.

**Output**: `output/data/manuscript_variables.json` — complete `{ "TOKEN": "value" }` mapping, plus the resolved chapters in `output/manuscript/`.

### Render and validate with the pinned template

Use a clean checkout in a physical directory named `daf-okn` and install its locked dependencies. Set
`cognitive_vault` to the absolute path of a checkout of
[ActiveInferenceInstitute/cognitive](https://github.com/ActiveInferenceInstitute/cognitive).
The workflow command supplies SciPy for the sparse spring layout used by
NetworkX on large graphs. Record the vault commit and keep `output/data/registry_snapshot.yaml` with the
render if you need to reproduce the exact data inputs later.

```bash
# Run these commands from the daf-okn checkout.
daf_okn_root="$PWD"
export UV_PYTHON=3.14
uv sync --locked --extra dev
uv run python scripts/00_preflight.py
uv run --locked --with scipy==1.17.1 python scripts/10_research_workflow.py --cognitive-repo "$cognitive_vault"
uv run python scripts/09_provenance_record.py --graph output/data/cognitive_kg.json --preset cognitive-kb
uv run python scripts/z_generate_manuscript_variables.py
cp docs/manuscript/figure_registry.json output/figures/figure_registry.json
```

Inspect `output/data/graph_report.json` for analysis problems and
`output/data/provenance/provenance_record.json` for package validation.
Hydration writes the generated sections to `output/manuscript/` and reports
any unresolved variables. Use strict hydration for a render intended to report
results. Use `--allow-draft` for development when analysis data are unavailable.

Install Python 3.14+ for template, Pandoc, XeLaTeX with the supporting TeX
packages, and a `pandoc-crossref` build compatible with your Pandoc version.
Then register the checkout as a project leaf from the template checkout.

```bash
git clone https://github.com/docxology/template.git
cd template
git checkout --detach 87704feae0a4490ef7dad9c931d268e8c30273c2
uv sync --locked --no-dev
mkdir -p projects/working
ln -s "$daf_okn_root" projects/working/daf-okn
uv run --no-sync python scripts/pipeline/stage_03_render.py --project working/daf-okn --skip-manuscript-hydration
uv run --no-sync python scripts/pipeline/stage_04_validate.py --project working/daf-okn
```

Pass `--skip-manuscript-hydration` because the preceding DAF-OKN command
has already produced the resolved chapters. Stage 03 locates the source
configuration, preamble, and bibliography in `docs/manuscript/` and uses the
generated chapters in `output/manuscript/`. Stage 04 uses the project and its
tracked source to validate the render and write provenance. The figure registry
links the two manuscript labels to the generated PNGs checked in Stage 04.

Check `output/pdf/daf-okn_combined.pdf`, `output/web/index.html`, and
`output/reports/` inside the DAF-OKN checkout. Open the combined PDF and HTML
and confirm that the ordered sections, bibliography, registry catalog figure,
and cognitive network figure appear and that no results placeholders remain.

## config.yaml Controls

| YAML Key | Controls | Consumed by |
|---|---|---|
| `paper.title`, `paper.subtitle` | `{{CONFIG_TITLE}}`, `{{CONFIG_SUBTITLE}}` | `src/daf_okn/core/manuscript_variables.py` |
| `paper.version` | `{{CONFIG_VERSION}}` token | `src/daf_okn/core/manuscript_variables.py` |
| `authors[0].name` | `{{CONFIG_FIRST_AUTHOR}}` | `src/daf_okn/core/manuscript_variables.py` |
| `keywords` | `{{CONFIG_KEYWORDS}}` (comma-joined); default queries for `scripts/08_connector_search.py` | `src/daf_okn/core/manuscript_variables.py`, `scripts/08_connector_search.py` |

The template renderer reads paper and author metadata and enables the formats under `render.formats`. The `variables:` map documents the values DAF-OKN supplies.

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
grep -rhoE "\{\{[A-Z_]+\}\}" docs/manuscript/*.md | sort -u
```

### `FileNotFoundError` on graph_report.json

**Symptom**: Variable hydration fails with `FileNotFoundError` naming `output/data/graph_report.json`.

**Cause**: The analysis stage has not run in pipeline mode (no `--allow-draft`).

**Fix**:
```bash
uv run --locked --with scipy==1.17.1 python scripts/10_research_workflow.py --cognitive-repo "$cognitive_vault"
# or analyze an existing graph document:
uv run python scripts/analyze_graph.py --graph output/data/cognitive_kg.json --out-dir output/data
```

### Missing figure in rendered output

**Symptom**: Broken image placeholder or missing figure reference.

**Cause**: The visualize stage failed to generate one or both figures, or `docs/manuscript/*.md` references a figure that was never generated.

**Fix**:
```bash
ls output/figures/*.png
uv run --locked --with scipy==1.17.1 python scripts/10_research_workflow.py --cognitive-repo "$cognitive_vault"
```

### BibTeX citation error

**Symptom**: Your Pandoc/LaTeX run reports a BibTeX error or an undefined citation key.

**Cause**: Malformed entry in `docs/manuscript/references.bib` (unclosed braces, duplicate keys, missing required fields).

**Fix**: Validate `docs/manuscript/references.bib` with a BibTeX linter and check your renderer's log for the specific error message.
