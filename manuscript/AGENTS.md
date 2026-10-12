---
title: "Manuscript directory: daf_okn"
type: "manuscript_guide"
version: "0.2.0"
---

# Manuscript (`manuscript/`)

Repository-wide agent rules for this project live in [`../docs/agent_instructions.md`](../docs/agent_instructions.md). This file covers **manuscript-specific** editing: file roles, the `{{TOKEN}}` protocol, the figure protocol, and the section modification workflow.

## File Inventory

| File / Pattern | Role | `{{TOKEN}}` Tokens | Figure References |
|---|---|---|---|
| `00_abstract.md` | Abstract; the pipeline and the case-study summary | `CONFIG_KEYWORDS`, `DENSITY_PCT`, `EDGE_COUNT`, `MEAN_DEGREE`, `NODE_COUNT`, `STRONGLY_CONNECTED_COMPONENTS`, `TOP_NODE_CENTRALITY`, `TOP_NODE_LABEL`, `TRIANGLE_COUNT`, `WEAKLY_CONNECTED_COMPONENTS` | None |
| `01_introduction.md` | OKN context, contributions, reader's guide | None | None |
| `02_methodology.md` | Pipeline stages, graph model, metrics, packaging | None (`eq:density`, `eq:mean_degree`) | None |
| `03_results.md` | Case-study results; both figures; the metrics table | `CONFIG_KEYWORDS`, `DENSITY_PCT`, `EDGE_COUNT`, `GRAPH_NAME`, `MEAN_DEGREE`, `NODE_COUNT`, `STRONGLY_CONNECTED_COMPONENTS`, `TOP_NODE_CENTRALITY`, `TOP_NODE_LABEL`, `TRIANGLE_COUNT`, `WEAKLY_CONNECTED_COMPONENTS` | `@fig:registry_catalog`, `@fig:cognitive_network` |
| `04_conclusion.md` | Demonstrated capabilities, limitations | None | None |
| `05_experimental_setup.md` | Configuration surface, environment, pipeline ordering | `CONFIG_KEYWORDS`, `GENERATION_TIMESTAMP`, `MATPLOTLIB_VERSION`, `NETWORKX_VERSION`, `PLATFORM`, `PYTHON_VERSION` | None |
| `06_reproducibility.md` | Config hash, artifact chain, reproduction commands | `CONFIG_FIRST_AUTHOR`, `CONFIG_HASH`, `CONFIG_KEYWORDS`, `CONFIG_TITLE`, `CONFIG_VERSION`, `GENERATION_TIMESTAMP` | None |
| `07_scope_and_related_work.md` | Scope boundaries, related literature | None | None |
| `99_references.md` | Bibliography mechanics | None | None |
| `config.yaml` | Paper metadata + a `variables:` reference map of the manuscript tokens | — | — |
| `config.yaml.example` | Reference copy; shows the configurable fields | — | — |
| `preamble.md` | Optional LaTeX preamble if you render with Pandoc/XeLaTeX | — | — |
| `references.bib` | BibTeX bibliography | — | — |
| `SYNTAX.md` | Citation, figure, equation, and token syntax reference | — | — |
| `README.md` | Human quick-reference for this directory | — | — |
| `AGENTS.md` | This file — agent technical directives | — | — |

## {{TOKEN}} Protocol

Numeric values that come from analysis outputs **must** use `{{TOKEN}}` syntax (uppercase; see the table in [`SYNTAX.md`](SYNTAX.md)). Hardcoding a number that changes when the pipeline re-runs is the primary cause of inaccurate manuscripts — and here it is also a policy violation: pipeline mode fails on a missing report, and draft mode renders `N/A` sentinels instead of invented values.

**The token pipeline**:
1. `scripts/10_research_workflow.py` runs pull → export → analyze → visualize and writes `output/data/graph_report.json`
2. `scripts/z_generate_manuscript_variables.py` calls `src/daf_okn/core/manuscript_variables.py::generate_variables()` (reads `manuscript/config.yaml` + the graph report; pipeline mode requires the report, `--allow-draft` substitutes `N/A` sentinels)
3. The script writes the full `{TOKEN: value}` mapping to `output/data/manuscript_variables.json`
4. `write_resolved_manuscript()` writes copies of the chapters with every `{{TOKEN}}` substituted to `output/manuscript/` (a token missing from the map stays visible and is reported; documentation files are not copied); rendering those copies to PDF/HTML is left to your own Markdown/Pandoc toolchain

**Adding a new token**:
1. Emit it from `generate_variables()` in `src/daf_okn/core/manuscript_variables.py`
2. Add it to the `variables:` reference map in `config.yaml` (and mirror in `SYNTAX.md`)
3. Reference it in a manuscript file as `{{MY_TOKEN}}` — the regression test `tests/core/test_manuscript_variables.py::test_all_manuscript_tokens_are_generated` fails CI if the generator does not produce a token the prose uses

**Detecting unresolved tokens** (in the output of your own substitution step):
```bash
# Replace <rendered-dir> with wherever your toolchain writes substituted Markdown
grep -r "{{" <rendered-dir>/ 2>/dev/null \
  && echo "UNRESOLVED TOKENS — re-run z_generate_manuscript_variables.py" \
  || echo "All tokens resolved"
```

## Figure Protocol

Both figures are referenced via Pandoc-crossref `[@fig:label]`, never hardcoded numbers or raw `\ref{}`:

| Label | PNG Filename | Generator in `src/daf_okn/figures/` (orchestrated via `scripts/10_research_workflow.py`) |
|---|---|---|
| `{#fig:registry_catalog}` | `output/figures/registry_catalog.png` | `plot_graph_catalog()` |
| `{#fig:cognitive_network}` | `output/figures/cognitive_network.png` | `plot_network()` |

**To add a new figure**:
1. Add a generator function to `src/daf_okn/figures/` and wire it through the workflow's `visualize` stage (`scripts/10_research_workflow.py`) so the workflow produces the PNG.
2. Add a Pandoc image line (alt text, relative path under `../output/figures/`, `{#fig:…}` anchor) in the appropriate chapter, following `03_results.md`.
3. Reference in prose: `[@fig:new_label]` (parenthetical) or `@fig:new_label` (narrative).
4. Update the registry tables in [`SYNTAX.md`](SYNTAX.md) and this file.

## Section Modification Protocol

Follow these steps in order whenever analysis behavior changes:

1. **Update the code and its tests first** — modules in `src/daf_okn/`, suites under `tests/`.
2. **Regenerate analysis outputs**:
   ```bash
   python scripts/10_research_workflow.py --cognitive-repo <path-to-cognitive-vault>
   ```
   (Stage 1 needs OKN network access; stage 2 needs the `cognitive` vault root. `--graph <file>` analyzes any `GraphDocument` JSON without stage 2.)
3. **Generate manuscript variables**:
   ```bash
   python scripts/z_generate_manuscript_variables.py            # pipeline mode (report required)
   python scripts/z_generate_manuscript_variables.py --allow-draft  # draft sentinels only
   ```
4. **Verify token coverage** with the cross-reference test:
   ```bash
   uv run pytest tests/core/test_manuscript_variables.py -q
   ```
5. **Render** the resolved chapters in `output/manuscript/` with your own Markdown/Pandoc toolchain. This repository ships no renderer.
6. **Verify figures and tables** appear in the rendered output and no literal `{{TOKEN}}` text remains.

> **Mermaid note.** If a chapter embeds a ```mermaid``` block, rendering it as an image needs a Mermaid-aware step in your own toolchain.

## RASP Conventions

1. Avoid boilerplate closers such as "In summary" / "In conclusion" at the end of sections unless the section genuinely needs them.
2. Figures and numbers in `03_results.md` must match what the workflow wrote (paths under `output/figures/`, the `graph_report.json` schema).
3. **Zero fabrication**: never write a result number in prose; use tokens. Where the OKN docs are silent, say so (see [`../docs/okn/api-notes.md`](../docs/okn/api-notes.md)) rather than filling the gap.
4. When referencing code, prefer concrete paths: `src/daf_okn/core/registry.py`, `scripts/10_research_workflow.py`.

## See also

- [`README.md`](README.md) — Quick orientation
- [`SYNTAX.md`](SYNTAX.md) — Pandoc syntax, equation/figure registries, token table
- [`../docs/rendering_pipeline.md`](../docs/rendering_pipeline.md) — Manuscript variables and rendering notes
- [`../docs/syntax_guide.md`](../docs/syntax_guide.md) — Complete `{{TOKEN}}` protocol
- [`../src/daf_okn/core/manuscript_variables.py`](../src/daf_okn/core/manuscript_variables.py) — Variable computation logic (`generate_variables()`)
- [`../scripts/z_generate_manuscript_variables.py`](../scripts/z_generate_manuscript_variables.py) — Thin orchestrator for the variable map
