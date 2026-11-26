# `daf_okn` Manuscript — OKN Pull, Analyze, Visualize, Contribute

The manuscript documents the DAF-OKN workflow and the Cognitive Knowledge Base
case study. DAF-OKN derives the measured values from the graph analysis report
and writes resolved chapters under `output/manuscript/`. Follow the
[pinned rendering guide](../rendering_pipeline.md) to build and validate the
PDF and HTML.

## Manuscript Structure

- `00_abstract.md`: Abstract; case-study numbers via `scripts/z_generate_manuscript_variables.py`.
- `01_introduction.md`: OKN registry context, contributions, reader's guide.
- `02_methodology.md`: Workflow stages (pull → export → analyze → visualize), the `GraphDocument` model, invariants, metrics, packaging.
- `03_results.md`: Registry catalog + cognitive-graph case study; both figures and the token-driven metrics table.
- `04_conclusion.md`: What the chain demonstrates; limitations.
- `05_experimental_setup.md`: Configuration surface, environment, pipeline ordering.
- `06_reproducibility.md`: Config hash, artifact chain, reproduction commands.
- `07_scope_and_related_work.md`: Scope boundaries, related literature.
- `99_references.md`: Citation list generated from [`references.bib`](references.bib).

## AI Agent Directives

If you are an AI agent operating in this repository, you **MUST** read [`AGENTS.md`](AGENTS.md) before editing prose: it defines the token protocol, the figure registry, and the zero-fabrication rule.

## See also

- [`SYNTAX.md`](SYNTAX.md) — Pandoc citation/cross-reference conventions and the token table.
- [`figure_registry.json`](figure_registry.json) — figure labels, output filenames, and alt text.
- [`config.yaml`](config.yaml) — `variables:` block reference map of the manuscript tokens.
- [`../syntax_guide.md`](../syntax_guide.md) — complete token protocol.
- [`../../AGENTS.md`](../../AGENTS.md) — project agent rules.
