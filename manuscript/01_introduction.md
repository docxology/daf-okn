# Introduction {#sec:introduction}

The [Open Knowledge Network (OKN)](https://okn.us/) program publishes a growing federation of domain knowledge graphs behind a shared registry: [registry.okn.us](https://registry.okn.us/) holds graph metadata, [apps.okn.us](https://apps.okn.us/) serves per-graph SPARQL and TPF endpoints plus a cross-graph federation triplestore, and [repository.okn.us](https://repository.okn.us/) versions contributed graph files. As of 2026-09-25 the registry's machine-readable catalog (`kgs.yaml`) lists 45 graphs. A research consumer of this fabric faces four recurring jobs: **pull** the catalog and query the graphs, **analyze** what the graphs contain structurally, **visualize** the result, and **contribute** new graphs back. `daf-okn` implements that loop as a reproducible pipeline ([@sec:methodology]) and demonstrates it on a real contribution — the Active Inference Institute's `cognitive` knowledge graph ([@sec:results]).

Every quantitative claim in this manuscript is a `{{TOKEN}}` placeholder whose value is generated from pipeline outputs by `src/daf_okn/core/manuscript_variables.py` and `scripts/z_generate_manuscript_variables.py` ([@sec:experimental_setup]). The prose cannot drift from the data because both come from the same run: `output/data/graph_report.json` is written by the analysis pipeline and read back when the variable map is built.

## Why a pipeline paper

Individually, each stage is ordinary software: an HTTP client, a networkx measurement pass, a matplotlib figure, an RDF serializer. The engineering claim is the **chain**: registry metadata → typed graph document → validated metrics → figures and dashboard → registry contribution package, each stage consuming the previous stage's artifacts and each backed by tests under the repository's zero-mock policy (≥90% statement coverage gate on `src/`). [@peng2011reproducible] argues that the full computational environment — data, code, and parameter trail — is part of the scientific claim; this repository is an attempt to make that environment the deliverable, not the byproduct.

## Contributions

1. **Registry-native client** (`src/daf_okn/core/registry.py`): a thin `OKNRegistry` client over the documented OKN surfaces — `kgs.yaml` metadata, per-graph and federation SPARQL, TPF fragments, and the embeddings service — with the endpoint facts pinned to the verified notes in [`docs/okn/api-notes.md`](../docs/okn/api-notes.md).
2. **Typed graph model with invariants** (`src/daf_okn/core/graph.py`, `src/daf_okn/core/invariants.py`): `NodeRecord`/`EdgeRecord`/`GraphDocument` documents with cheap structural checks (duplicate ids, dangling edge endpoints, self-loops) that run on every load.
3. **Measurement and reporting** (`src/daf_okn/analysis/`): deterministic structural metrics and a self-contained JSON report written to `output/data/graph_report.json`, plus figures (`src/daf_okn/figures/`) and a static dashboard (`src/daf_okn/dashboard/`).
4. **Contribution packaging** (`src/daf_okn/core/contribute.py`): graph → N-Quads RDF, registry entry draft with YAML frontmatter, contribution checklist, and a provenance receipt with SHA-256 artifact hashes (`scripts/09_provenance_record.py`).
5. **Cognitive export case study** (`src/daf_okn/core/cognitive_adapter.py`): a parser that converts the Active Inference Institute's Obsidian-format `cognitive` vault — YAML frontmatter, `semantic_relations`, wiki-links, redirect pages — into the same `GraphDocument` model, so a contributed graph and its analysis share one data path.

## Reader's guide

- **[@sec:methodology]** describes each pipeline stage and the invariants that gate it.
- **[@sec:results]** reports the cognitive-graph case study; all numbers are injected tokens (see the token contract in [@sec:experimental_setup]).
- **[@sec:reproducibility]** records the configuration hash, environment, and artifact chain of custody.
- **[@sec:scope]** states scope boundaries and related work; [@sec:conclusion] closes.

No result numbers are fabricated in this manuscript: sections that depend on a pipeline run quote `{{...}}` tokens, and draft renders without analysis outputs show explicit `N/A` sentinels rather than invented values.
