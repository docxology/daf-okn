# Methodology {#sec:methodology}

The pipeline has four stages — **pull**, **export**, **analyze**, **visualize** — plus the packaging path that turns an analyzed graph into a registry contribution. Each stage is a thin script (`scripts/`) delegating to an importable module (`src/daf_okn/`), so the workflow is testable without shell logic and the manuscript variables come from the same artifacts the stages write.

## Registry pull

`OKNRegistry` (`src/daf_okn/core/registry.py`) reads the registry's single machine-readable metadata file, `kgs.yaml` — a YAML mapping with a top-level `kgs:` list of graph entries (`shortname`, `title`, `description`, `sparql`, `tpf`, `stats`, `funding`, `contact`, `frink-options`). `parse_kgs_yaml` validates the envelope, and `list_graphs` returns the 45 graph entries (as of the 2026-09-25 capture documented in [`docs/okn/api-notes.md`](../docs/okn/api-notes.md)). The module performs no I/O at import time: network access happens only inside methods, through an injected `requests.Session` with a per-request timeout, and every HTTP ≥ 400 response or malformed payload raises `RegistryError`.

Query access follows the documented endpoint map:

- **Per-graph SPARQL**: `https://apps.okn.us/{shortname}/sparql` — standard SPARQL 1.1 JSON results [@sparql2013] served by a dedicated QLever instance per graph [@bast2017qlever].
- **Federation SPARQL**: `https://apps.okn.us/federation/sparql` — one large triplestore with a named graph per KG; cross-graph queries scope results with `FROM <https://purl.org/okn/frink/kg/{shortname}>` clauses. ("Federation" is a legacy name: the endpoint is a unified triplestore, no longer federating.)
- **TPF fragments**: `https://apps.okn.us/ldf/{shortname}` — one triple pattern at a time [@verborgh2014tpf], with `subject`/`predicate`/`object` fragment arguments.
- **Embeddings**: `POST https://apps.okn.us/embeddings/query` — a Qdrant-backed nearest-neighbor service over graph content, used by the connector-search stage (`scripts/08_connector_search.py`) to match manuscript keywords against all hosted graphs.

`bindings_to_graph` converts any SPARQL JSON result into the graph model below, which is how a queried subgraph becomes a first-class analysis target.

## Graph document model

`GraphDocument` (`src/daf_okn/core/graph.py`) is the pinned interchange model: `NodeRecord` (id, title, type, attributes), `EdgeRecord` (source, target, relation, origin), and a metadata dict. Documents serialize to/from JSON (`save_json`/`load_json`) and project onto networkx graphs (`to_networkx(directed=True)`) for measurement.

Structural invariants (`src/daf_okn/core/invariants.py`) gate every load: `validate_graph` reports empty or duplicate node ids, edge endpoints missing from the node set, and self-loops; `graph_stats` computes the cheap summary (node/edge counts, density, weakly-connected component count) reused by the dashboard. Checks are single-pass with no graph construction so they can run on every load.

## Analysis

`run_analysis(graph, out_dir)` (`src/daf_okn/analysis/pipeline.py`) measures a document via `compute_metrics` (`src/daf_okn/analysis/graph_metrics.py`) over the directed projection and writes a self-contained JSON report to `<out-dir>/graph_report.json` with blocks:

- `graph_name` — the document name;
- `stats` — the `graph_stats` summary (node/edge counts, density, directedness, component count);
- `problems` — the `validate_graph` list (empty for a valid document);
- `metrics` — `node_count`, `edge_count`, `density`, `weakly_connected_components`, `strongly_connected_components`, `mean_degree`, `triangles`, centrality mappings, and the `top_central_nodes` ranking (descending score, id as deterministic tie-break).

Density of the directed projection is [@eq:density]:

\begin{equation}
\label{eq:density}
d = \frac{m}{n\,(n-1)},
\end{equation}

where $n$ is the node count and $m$ the directed edge count (0.0 when $n < 2$). Mean degree is [@eq:mean_degree]:

\begin{equation}
\label{eq:mean_degree}
\bar{k} = \frac{2m}{n}.
\end{equation}

Both are computed by networkx over the directed projection, so parallel edges and attribute payloads do not affect the structural measurement.

## Cognitive export (case-study path)

`src/daf_okn/core/cognitive_adapter.py` ports the Active Inference Institute `cognitive` vault parser: markdown files with YAML frontmatter become nodes (path-derived ids, normalized titles, flattened frontmatter attributes), `semantic_relations` frontmatter entries and body wiki-links (`[[target|display]]`) become typed edges, code spans and fenced blocks are excluded from link extraction, and `type: redirect` pages either collapse into their targets or survive as explicit `redirects_to` edges. The export (`export_cognitive_kb`) writes `output/data/cognitive_kg.json` and a `counts` metadata block (nodes, edges by kind, unresolved targets) that stages downstream report verbatim.

## Contribution packaging

`src/daf_okn/core/contribute.py` turns a `GraphDocument` into a registry contribution package: `graph_to_rdf` serializes nodes and edges to N-Quads using SKOS, DCTERMS, and schema.org terms, with entity IRIs under `https://purl.org/okn/frink/kg/{name}/` and the named graph `https://purl.org/okn/frink/kg/{name}`; `registry_entry` drafts the registry page (YAML frontmatter with `shortname`, `title`, `description`, `stats`, `frink-options`, `contacts`); `contribution_checklist` embeds the documented upload steps. `validate_package` writes the package and returns structural problems (empty graph name, missing contacts, non-IRI-safe ids); `scripts/09_provenance_record.py` runs it and records a provenance receipt — per-artifact SHA-256 hashes plus the problem list — to `output/data/provenance/provenance_record.json`.

## Visualization

`src/daf_okn/figures/network_figure.py` renders the two figures referenced in [@sec:results]: `plot_graph_catalog` (one horizontal bar per registry graph, from the `kgs.yaml` snapshot) and `plot_network` (spring, circular, Kamada–Kawai, or seeded random layouts of an analyzed document). Both write deterministic PNGs under `output/figures/` with an `MPLBACKEND=Agg` default; the dashboard builder (`src/daf_okn/dashboard/`) consumes the same report payload for the static HTML view.

## Token hydration contract

`src/daf_okn/core/manuscript_variables.py` reads `manuscript/config.yaml` (title, authors, keywords, version) and `output/data/graph_report.json` (the `run_analysis` report) and emits the flat `{{TOKEN}}` map persisted to `output/data/manuscript_variables.json`. In pipeline mode (`require_analysis_outputs=True`, the default), a missing or malformed report is a hard `FileNotFoundError`; draft mode (`--allow-draft`) substitutes explicit `N/A` sentinels instead, so a half-run is always visible in the rendered text rather than silently fabricated. `scripts/z_generate_manuscript_variables.py` is the thin orchestrator for this step; it writes only the variables JSON, and substituting the values into the chapters is left to the reader's own Markdown/Pandoc toolchain.
