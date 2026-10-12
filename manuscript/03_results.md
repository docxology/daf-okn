# Results {#sec:results}

This section reports the pipeline run whose artifacts this manuscript hydrates from. Every number below is an injected token (see [@sec:experimental_setup]); the underlying report is `output/data/graph_report.json`, written by `run_analysis` for the exported cognitive knowledge graph. The run is reproducible from the commands in [@sec:reproducibility]; draft runs without the report display explicit `N/A` sentinels rather than placeholder numbers.

## Registry catalog

Stage 1 of the workflow (`pull_registry`) snapshots the OKN registry's `kgs.yaml` catalog to `output/data/registry_snapshot.yaml`. The catalog is the pull/analyze/visualize surface for all 45 registered graphs — each entry carries the graph's `shortname`, human title, description, per-graph SPARQL and TPF endpoint URLs, VoID stats link, funding and contact fields, and LakeFS/frink options. [@fig:registry_catalog] renders the catalog as one horizontal bar per registered graph (`plot_graph_catalog`, from `scripts/10_research_workflow.py` stage 4); the per-graph endpoints themselves are consumed by the SPARQL/TPF clients described in [@sec:methodology], and the connector-search stage (`scripts/08_connector_search.py`) matches the manuscript's keywords — {{CONFIG_KEYWORDS}} — against the embeddings service across all hosted graphs.

![The OKN registry catalog: one bar per registered knowledge graph, from the `kgs.yaml` snapshot written by the `pull_registry` stage.](../output/figures/registry_catalog.png){#fig:registry_catalog width=95%}

## Case study: the cognitive knowledge graph

The case-study graph is the Active Inference Institute `cognitive` knowledge base, exported by stage 2 of the workflow (`export_cognitive_kb`) to `output/data/cognitive_kg.json`. The vault's markdown pages become typed nodes (frontmatter titles, `semantic_relations` and wiki-link edges, redirects collapsed or explicit), and the resulting document is measured by stage 3 (`run_analysis`) into `output/data/graph_report.json`.

![Spring-layout rendering of the exported cognitive knowledge graph (`plot_network`), positioned deterministically; node color follows the document's node types.](../output/figures/cognitive_network.png){#fig:cognitive_network width=95%}

[@fig:cognitive_network] renders the analyzed graph. Its structural summary is [@tbl:graph_metrics]; the report's `problems` block — the `validate_graph` invariants — must be empty for the run to gate the build.

| Quantity | Value | Report source |
|---|---|---|
| Graph name | `{{GRAPH_NAME}}` | `graph_name` |
| Nodes | {{NODE_COUNT}} | `metrics.node_count` |
| Directed edges | {{EDGE_COUNT}} | `metrics.edge_count` |
| Density | {{DENSITY_PCT}}% | `metrics.density` |
| Weakly connected components | {{WEAKLY_CONNECTED_COMPONENTS}} | `metrics.weakly_connected_components` |
| Strongly connected components | {{STRONGLY_CONNECTED_COMPONENTS}} | `metrics.strongly_connected_components` |
| Mean degree | {{MEAN_DEGREE}} | `metrics.mean_degree` |
| Triangles (undirected projection) | {{TRIANGLE_COUNT}} | `metrics.triangles` |
| Most central node | `{{TOP_NODE_LABEL}}` | `metrics.top_central_nodes[0]` |
| Its betweenness centrality | {{TOP_NODE_CENTRALITY}} | `metrics.top_central_nodes[0]` |

: Structural metrics of the analyzed cognitive knowledge graph, hydrated from `output/data/graph_report.json`. {#tbl:graph_metrics}

Reading [@tbl:graph_metrics]: the node/edge counts bound the export's coverage of the vault (pages and typed links); the weak/strong component counts expose fragmentation that redirect collapsing did not heal; the density of {{DENSITY_PCT}}% and mean degree {{MEAN_DEGREE}} place the graph far from the dense regime where structural measurement degenerates; and the top-central node `{{TOP_NODE_LABEL}}` (centrality {{TOP_NODE_CENTRALITY}}) identifies the hub through which vault concepts are connected — the natural anchor for curation.

## Contribution packaging

Stage 4 packages the analyzed graph for the registry: `validate_package` writes the N-Quads serialization (`output/data/provenance/package/{name}.nq`, named graph `https://purl.org/okn/frink/kg/{name}`), the registry entry draft (`package/registry/docs/registry/kgs/{shortname}.md`, YAML frontmatter with `contacts`, `stats`, `frink-options`), and the documented contribution checklist; `scripts/09_provenance_record.py` records the receipt with per-artifact SHA-256 hashes to `output/data/provenance/provenance_record.json`. The packaging stage gates on the validator's problem list: a non-empty list (empty graph name, missing contacts, non-IRI-safe ids) fails the stage and is preserved in the receipt for audit.

## What the chain establishes

The run demonstrates the full loop this paper claims: registry catalog pulled (45 graphs), a real knowledge base exported to the typed model, structure measured into a stable report schema, two deterministic figures rendered, and a contribution package validated and hashed. Nothing in the chain depends on hand-transcribed numbers: replacing the exported graph with any other `GraphDocument` JSON (for example, one converted from a SPARQL result via `bindings_to_graph`) re-runs identically and regenerates every token in this section.
