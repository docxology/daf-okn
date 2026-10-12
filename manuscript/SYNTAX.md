# Manuscript Syntax Reference (daf_okn)

Project-specific overlay on the canonical [`docs/syntax_guide.md`](../docs/syntax_guide.md) — read that file first; this file documents the **daf_okn**-specific figure registry, equation labels, and `{{TOKEN}}` table.

## Citation Syntax (Pandoc)

```markdown
<!-- Single citation -->
[@peng2011reproducible]

<!-- Multiple citations -->
[@peng2011reproducible; @hogan2021knowledge]

<!-- Citation with locator -->
[@sparql2013, §2]

<!-- Narrative citation -->
@peng2011reproducible argues that...
```

All citation keys must exist in [`references.bib`](references.bib). If you render with Pandoc, `--natbib` converts `[@key]` to the right LaTeX cite command automatically; **never** write raw `\cite{}` in Markdown.

## Equation Environments

```markdown
<!-- Numbered equation with label -->
\begin{equation}
\label{eq:density}
d = \frac{m}{n\,(n-1)}
\end{equation}

<!-- Reference in text -->
[@eq:density] gives the density.
```

Reference equations with `[@eq:label]` (parenthetical) or `@eq:label` (narrative). **Never** use raw LaTeX `\ref` / `\eqref` macros in Markdown source — the Pandoc bracket form renders portably across PDF / HTML in Pandoc.

### Equation label registry

| Label | Equation | Source file |
|---|---|---|
| `{#eq:density}` | $d = m / (n(n-1))$ | `02_methodology.md` |
| `{#eq:mean_degree}` | $\bar{k} = 2m/n$ | `02_methodology.md` |

## Figure References

```markdown
<!-- Figure with label -->
![Registry catalog bar chart](../output/figures/registry_catalog.png){#fig:registry_catalog width=95%}

<!-- Reference in text -->
[@fig:registry_catalog] demonstrates...
```

- Images must exist in `output/figures/` when you render — both are produced by workflow stage 4 (`scripts/10_research_workflow.py`, `visualize` stage)
- Use `width=` or `height=` to control sizing (prevents float-too-large warnings)
- Captions are self-contained — they appear in the rendered document and as alt text in HTML

### Figure label registry

| Label | PNG filename | Generator in `src/daf_okn/figures/` (orchestrated via `scripts/10_research_workflow.py`) |
|---|---|---|
| `{#fig:registry_catalog}` | `output/figures/registry_catalog.png` | `plot_graph_catalog()` |
| `{#fig:cognitive_network}` | `output/figures/cognitive_network.png` | `plot_network()` |

## Table References

```markdown
| Quantity | Value |
|-----------|-----------|
| Nodes     | {{NODE_COUNT}} |

: Structural metrics of the analyzed graph. {#tbl:graph_metrics}

<!-- Reference in text -->
[@tbl:graph_metrics] shows...
```

### Table label registry

| Label | Caption summary | Source file |
|---|---|---|
| `{#tbl:graph_metrics}` | Structural metrics of the analyzed cognitive graph | `03_results.md` |

## Section Labels

Every H1 in this manuscript carries a `{#sec:<name>}` label so cross-section references (`[@sec:methodology]`) survive reordering:

| File | Section H1 | Label |
|---|---|---|
| `00_abstract.md` | Abstract | `{#sec:abstract}` |
| `01_introduction.md` | Introduction | `{#sec:introduction}` |
| `02_methodology.md` | Methodology | `{#sec:methodology}` |
| `03_results.md` | Results | `{#sec:results}` |
| `04_conclusion.md` | Conclusion | `{#sec:conclusion}` |
| `05_experimental_setup.md` | Experimental Setup | `{#sec:experimental_setup}` |
| `06_reproducibility.md` | Reproducibility Certification | `{#sec:reproducibility}` |
| `07_scope_and_related_work.md` | Scope, Related Work, and Positioning | `{#sec:scope}` |
| `99_references.md` | References | `{#sec:references}` |

## Preamble (if you render with Pandoc/XeLaTeX)

[`preamble.md`](preamble.md) lists LaTeX packages in a fenced `latex` block. This repository does not consume it; if you render with Pandoc and XeLaTeX, you can extract that block and pass it as a header include:

```markdown
---
header-includes:
  - \usepackage{amsmath}
  - \usepackage[capitalise,noabbrev]{cleveref}
  - \usepackage{natbib}
---
```

- Changes to tolerance/hfuzz affect line-breaking globally
- Do **not** duplicate package imports your own toolchain already adds

## BibTeX Entry Format

```bibtex
@article{peng2011reproducible,
  author  = {Peng, Roger D.},
  title   = {Reproducible Research in Computational Science: Really?},
  journal = {Science},
  year    = {2011},
  volume  = {334},
  number  = {6060},
  pages   = {1226--1227}
}
```

- Keys must be lowercase alphanumeric with optional underscores
- Author names use `{Last, First}` or `{First Last}` format
- All entries must have at minimum: `author`, `title`, `year`

## Section Numbering

```text
00_abstract.md              → Abstract (unnumbered in Pandoc output)
01_introduction.md          → Section 1
02_methodology.md           → Section 2
03_results.md               → Section 3
04_conclusion.md            → Section 4
05_experimental_setup.md    → Section 5
06_reproducibility.md       → Section 6
07_scope_and_related_work.md → Section 7
99_references.md            → References (Pandoc--natbib bibliography)
```

If you assemble the chapters yourself, use lexicographic file order. The `00_` prefix ensures the abstract renders first; `99_` ensures the references come last.

## `{{TOKEN}}` table

Token values are produced by `src/daf_okn/core/manuscript_variables.py::generate_variables()` from `manuscript/config.yaml` (listed in its `variables:` reference map) and `output/data/graph_report.json`; the authoritative list is the generator's return value. The regression test `tests/core/test_manuscript_variables.py::test_all_manuscript_tokens_are_generated` reads every `manuscript/*.md` file and fails CI on any token used in prose that the generator does not emit.

| Token | Source | Used in |
|---|---|---|
| `{{CONFIG_TITLE}}` | `paper.title` | 06 |
| `{{CONFIG_SUBTITLE}}` | `paper.subtitle` | — |
| `{{CONFIG_VERSION}}` | `paper.version` | 06 |
| `{{CONFIG_FIRST_AUTHOR}}` | `authors[0].name` | 06 |
| `{{CONFIG_KEYWORDS}}` | comma-joined `keywords` | 00, 03 |
| `{{GRAPH_NAME}}` | `graph_report.graph_name` | 03 |
| `{{NODE_COUNT}}` / `{{EDGE_COUNT}}` | `metrics.node_count` / `metrics.edge_count` | 00, 03 |
| `{{DENSITY_PCT}}` | `metrics.density × 100` | 00, 03 |
| `{{WEAKLY_CONNECTED_COMPONENTS}}` / `{{STRONGLY_CONNECTED_COMPONENTS}}` | `metrics.*_components` | 00, 03 |
| `{{MEAN_DEGREE}}` | `metrics.mean_degree` | 00, 03 |
| `{{TRIANGLE_COUNT}}` | `metrics.triangles` | 00, 03 |
| `{{TOP_NODE_LABEL}}` / `{{TOP_NODE_CENTRALITY}}` | `metrics.top_central_nodes[0]` | 00, 03 |
| `{{CONFIG_HASH}}` | SHA-256 of config.yaml (truncated) | 06 |
| `{{GENERATION_TIMESTAMP}}` | generation time / `SOURCE_DATE_EPOCH` | 05 |
| `{{PYTHON_VERSION}}` / `{{PLATFORM}}` | runtime | 05 |
| `{{NETWORKX_VERSION}}` / `{{MATPLOTLIB_VERSION}}` | runtime | 05 |

**Zero-fabrication rule:** result-derived tokens show real values only after `output/data/graph_report.json` exists (pipeline mode); draft runs (`--allow-draft`) display `N/A` sentinels. Never hardcode a number that the pipeline computes.

## Prose Conventions

- No "In summary" or "In conclusion" at section ends (RASP standard)
- Use active voice for methodology descriptions
- Use explicit file paths when referencing code: `src/daf_okn/core/registry.py`, not "the registry module"
- Keep paragraphs focused — one idea per paragraph

## See Also

- [`../docs/syntax_guide.md`](../docs/syntax_guide.md) — complete `{{TOKEN}}` protocol
- [`AGENTS.md`](AGENTS.md) — RASP protocol and AI agent constraints
- [`config.yaml`](config.yaml) — `variables:` reference map of this token table
