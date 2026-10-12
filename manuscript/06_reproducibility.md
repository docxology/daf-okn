# Reproducibility Certification {#sec:reproducibility}

This section provides the machine-verifiable provenance certificate for the study. Every metric below is either injected from a pipeline artifact or computed when the variables are generated — establishing the chain of custody from configuration to publication.

## Configuration provenance

| Property | Value |
|---|---|
| Config hash (SHA-256, truncated) | `{{CONFIG_HASH}}` |
| Paper version | {{CONFIG_VERSION}} |
| Title | {{CONFIG_TITLE}} |
| First author | {{CONFIG_FIRST_AUTHOR}} |
| Keywords | {{CONFIG_KEYWORDS}} |

The configuration hash changes whenever any byte of `config.yaml` changes, so every rendered manuscript is traceable to a specific configuration state. `SOURCE_DATE_EPOCH` pins `GENERATION_TIMESTAMP` for byte-stable rebuilds.

## Artifact chain

| Artifact | Producer stage | Consumed by |
|---|---|---|
| `output/data/registry_snapshot.yaml` | `pull_registry` (workflow stage 1) | catalog figure, connector search |
| `output/data/cognitive_kg.json` | `export_cognitive` (stage 2) | analysis |
| `output/data/graph_report.json` | `analyze_graph` (stage 3) | manuscript tokens |
| `output/figures/registry_catalog.png`, `output/figures/cognitive_network.png` | `visualize` (stage 4) | [@fig:registry_catalog], [@fig:cognitive_network] |
| `output/data/manuscript_variables.json` | `z_generate_manuscript_variables.py` | token injection |
| `output/data/provenance/provenance_record.json` | `scripts/09_provenance_record.py` | package audit |

Each artifact is written by the stage that owns it and read by the next; none is hand-edited (`output/` is a generated tree).

## Zero-fabrication verification

Every numeric claim in [@sec:results] is a `{{TOKEN}}` from `manuscript_variables.json`, which itself is derived from `graph_report.json`. The regression test `tests/core/test_manuscript_variables.py::test_all_manuscript_tokens_are_generated` fails CI on any token used in prose that the generator does not emit, and pipeline mode fails the build outright when the report is missing. Draft runs display `N/A` sentinels — a visible, greppable marker, never a plausible-looking number.

To verify token resolution after a run:

```bash
python scripts/z_generate_manuscript_variables.py
python -c "import json; d = json.load(open('output/data/manuscript_variables.json')); print(d['NODE_COUNT'], d['EDGE_COUNT'])"
# The first command prints "unresolved tokens in <file>: ..." for any token it could not fill;
# no such line means every token in output/manuscript/ is resolved.
```

## Reproduction commands

```bash
uv sync
uv run pytest tests/ --cov=src --cov-fail-under=90   # test + coverage gate
python scripts/00_preflight.py                       # environment check
python scripts/10_research_workflow.py \
    --cognitive-repo <path-to-cognitive-vault>            # pull → export → analyze → visualize
python scripts/09_provenance_record.py \
    --graph output/data/cognitive_kg.json            # package + hashed receipt
python scripts/z_generate_manuscript_variables.py    # variable map (pipeline mode)
```

Stages 1 and the connector search require live OKN network access; `export_cognitive` requires the `cognitive` repository root. With the report present, `manuscript_variables.json` reproduces byte-identically given the same config and `SOURCE_DATE_EPOCH`.

## Package provenance

The contribution package under `output/data/provenance/package/` is recorded with per-artifact SHA-256 hashes in `provenance_record.json`, alongside the validator's problem list. A package with any recorded problem must not be submitted; the receipt is the audit surface for that rule.
