# `daf_okn` Manuscript — OKN Pull, Analyze, Visualize, Contribute

The manuscript documents the `daf-okn` pipeline for the Open Knowledge Network: registry pull, graph analysis and visualization, and the registry-contribution case study. Prose lives in these markdown files; this repository does not render a PDF or HTML itself. Every quantitative claim is a `{{TOKEN}}` whose value is generated from analysis outputs (`output/data/graph_report.json`) and this directory's `config.yaml`, and written to `output/data/manuscript_variables.json`.

## Manuscript Structure

- `00_abstract.md`: Abstract; case-study numbers via `scripts/z_generate_manuscript_variables.py`.
- `01_introduction.md`: OKN registry context, contributions, reader's guide.
- `02_methodology.md`: Workflow stages (pull → export → analyze → visualize), the `GraphDocument` model, invariants, metrics, packaging.
- `03_results.md`: Registry catalog + cognitive-graph case study; both figures and the token-driven metrics table.
- `04_conclusion.md`: What the chain demonstrates; limitations.
- `05_experimental_setup.md`: Configuration surface, environment, pipeline ordering.
- `06_reproducibility.md`: Config hash, artifact chain, reproduction commands.
- `07_scope_and_related_work.md`: Scope boundaries, related literature.
- `99_references.md`: Bibliography mechanics (`references.bib`, natbib).

## Architecture

```mermaid
graph TD
    classDef project fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef docs fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;

    subgraph "Project Space (daf-okn)"
        Workflow["scripts/10_research_workflow.py"]:::project
        Modules["src/daf_okn/ core · analysis · figures · dashboard"]:::project
        Manuscript["manuscript/*.md"]:::project
        Report["output/data/graph_report.json"]:::project
        Vars["output/data/manuscript_variables.json"]:::project
    end

    Registry["OKN registry (kgs.yaml · SPARQL · embeddings)"]
    Tests["tests/"]:::docs
    Config["config.yaml"]:::docs

    Registry -->|pull (stage 1)| Workflow
    Workflow -->|delegates to| Modules
    Workflow -->|writes| Report
    Report -->|feeds| Vars
    Config -->|feeds| Vars
    Tests -->|gates| Modules
    Vars -.->|"substituted by your own Markdown/Pandoc toolchain"| Manuscript
```

## Quick Start

```bash
# From the project root
python scripts/00_preflight.py                                  # environment check
python scripts/10_research_workflow.py --cognitive-repo <path-to-cognitive-vault>   # pull → export → analyze → visualize
python scripts/09_provenance_record.py --graph output/data/cognitive_kg.json # package + receipt
python scripts/z_generate_manuscript_variables.py               # variable map (pipeline mode)
```

Stages 1 (registry pull) and the connector search need live OKN network access; stage 2 needs the `cognitive` vault root. `--allow-draft` writes explicit `N/A` sentinels when no report exists. Rendering to PDF or HTML is left to whatever Markdown/Pandoc toolchain you use; `preamble.md` is an optional LaTeX preamble for Pandoc/XeLaTeX.

## AI Agent Directives

If you are an AI agent operating in this repository, you **MUST** read [`AGENTS.md`](AGENTS.md) before editing prose: it defines the token protocol, the figure registry, and the zero-fabrication rule.

## See also

- [`SYNTAX.md`](SYNTAX.md) — Pandoc citation/cross-reference conventions and the token table.
- [`config.yaml`](config.yaml) — `variables:` block reference map of the manuscript tokens.
- [`../docs/syntax_guide.md`](../docs/syntax_guide.md) — complete token protocol.
- [`../AGENTS.md`](../AGENTS.md) — project agent rules.
