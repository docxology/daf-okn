# Conclusion {#sec:conclusion}

`daf-okn` closes the loop it set out to build: pull the OKN registry catalog, export a real knowledge base to a typed graph, measure it, visualize it, and package a validated contribution back toward the registry — with every quantitative manuscript claim hydrated from the pipeline's own outputs.

## What the implementation demonstrates

- **Registry-native integration.** The `OKNRegistry` client implements the documented OKN surfaces (`kgs.yaml` metadata, per-graph and federation SPARQL, TPF fragments, embeddings search) without a registry REST API — because none is documented ([`docs/okn/api-notes.md`](../docs/okn/api-notes.md)). The 45-graph catalog is the integration test surface.
- **One data path from vault to registry.** The `cognitive` Obsidian vault, SPARQL result bindings, and hand-built documents all enter through the same `GraphDocument` model and the same invariants, so the analysis and packaging stages are graph-source-agnostic.
- **Zero-fabrication rendering.** Prose numbers are `{{TOKEN}}` placeholders hydrated from `output/data/graph_report.json`; a missing report either fails the build (pipeline mode) or renders visible `N/A` sentinels (draft mode). The manuscript cannot quietly drift from the analysis.
- **Auditable packaging.** Contribution packages are validated against structural problems and hashed into a provenance receipt before anything is submitted.

## Key insights

1. **Metadata is an API.** With no documented registry REST API, `kgs.yaml` plus the per-graph query endpoints are the machine interface; treating that file as a typed, validated artifact (`parse_kgs_yaml`) is what makes the rest of the pipeline stable.
2. **Invariants belong at load time.** Duplicate ids, dangling edges, and self-loops are cheap to check on every load and expensive to debug after they reach a report; `validate_graph` at load time keeps downstream metrics honest.
3. **Reports are the manuscript's interface.** The `graph_report.json` schema (`graph_name`, `stats`, `problems`, `metrics`) is a deliberate contract between the analysis stage and the manuscript; narrowing it to what prose consumes is why the token table stays small.

## Limitations and future extensions

- The structural metrics are deliberately first-order (counts, density, components, degree, triangles, centralities). Temporal views of registry churn (new graphs, weekly federation rebuilds) and VoID-statistics integration (`https://apps.okn.us/okn-void/sparql`) are natural next steps.
- The embeddings-backed connector search treats the whole hosted corpus as one search space; per-graph weighting and the include/exclude graph filters are wired but not yet exploited in the manuscript workflow.
- Contribution submission stops at the validated, hashed package: the documented LakeFS upload step requires credentials requested from the registry maintainers, so the pipeline records the package and receipt but does not push.
- The cognitive adapter mirrors the upstream vault conventions (`semantic_relations`, wiki-links, redirects); upstream format drift must be tracked in the adapter's test suite.

## Final assessment

The registry catalog, the exported cognitive graph, its report, and this manuscript form one custody chain: `registry_snapshot.yaml` → `cognitive_kg.json` → `graph_report.json` → `manuscript_variables.json` → the rendered manuscript. The chain is re-runnable end to end with the commands in [@sec:reproducibility], and each link is covered by the test suites gated at ≥90% coverage on `src/`.
