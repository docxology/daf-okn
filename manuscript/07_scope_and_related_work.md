# Scope, Related Work, and Positioning {#sec:scope}

This section situates the project and states explicit boundaries. The goal is not to compete with general-purpose knowledge-graph toolkits [@hogan2021knowledge] or semantic-web infrastructure [@bernerslee2001semantic], but to demonstrate a complete, test-backed registry loop — pull, analyze, visualize, contribute — as one reproducible artifact in the sense of [@peng2011reproducible].

## Knowledge graphs and the semantic web

Knowledge graphs represent entities and typed relations at web scale; [@hogan2021knowledge] surveys their models, construction, and querying. The semantic-web stack gives the interchange formats this project relies on: RDF for serialization (N-Quads with named graphs) [@bernerslee2001semantic], SPARQL 1.1 for graph queries [@sparql2013]. The OKN fabric implements querying with per-graph QLever instances [@bast2017qlever] and offers TPF as a low-cost, page-at-a-time interface [@verborgh2014tpf]. `daf-okn` consumes these interfaces as a client; it does not operate fabric infrastructure.

## The Open Knowledge Network program

The OKN program publishes a federation of domain knowledge graphs behind a shared registry, with documented per-graph endpoints, a unified federation triplestore, VoID statistics, an embeddings service, and an MCP server ([`docs/okn/api-notes.md`](../docs/okn/api-notes.md), live-verified 2026-09-25). The registry's contribution flow — versioned upload via LakeFS, per-graph endpoints after deployment, federation visibility after the weekly rebuild — is the process `daf-okn`'s packaging stage targets. The registry's own docs note that its entry metadata schema is not yet enforced upstream; the validator in this project applies the stricter local checks (`validate_graph`, `validate_package`) before any submission.

## What this project demonstrates

The scientific content through [@sec:methodology] and [@sec:results] is a demonstration, not a discovery; the procedural contribution is the enforced chain: configuration in `manuscript/config.yaml` supplies the paper metadata, `run_analysis` fixes the report schema, `generate_variables` produces the values for the prose from that schema, and a regression test fails CI on any prose token the generator does not emit. That pattern — every prose number is a token, every token has a producer, every drift is a CI failure — transfers to other domains.

## Explicit limitations

1. **Client-side only.** The project pulls from and packages toward the OKN fabric; deploying graphs, operating QLever/LakeFS services, and the federation rebuild cycle are upstream concerns.
2. **First-order metrics.** Structural measurement stops at counts, density, components, degree, triangles, and centralities; community detection, motif analysis, and temporal registry views are out of scope.
3. **Contribution stops at the validated package.** LakeFS upload requires registry-issued credentials, so the pipeline ends at the hashed, audited package rather than an automated submission.
4. **Upstream format coupling.** The cognitive adapter mirrors the upstream vault's frontmatter conventions; upstream drift is handled in the adapter's tests, not at runtime.
5. **Undocumented surfaces are treated as absent.** Where the OKN docs are silent (bulk graph download, SPARQL rate limits, registry REST API), this project implements nothing and assumes nothing ([`docs/okn/api-notes.md`](../docs/okn/api-notes.md), "[NOT DOCUMENTED]" entries).

These limitations are intentional: they keep the failure surface small enough that tests, invariants, and the token contract remain visible rather than buried under breadth.
