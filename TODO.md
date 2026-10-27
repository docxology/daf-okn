# daf-okn task index

The canonical task records are in [tasks.yaml](tasks.yaml). Follow the linked IDs
for current status, dependencies, acceptance criteria, prompts and owner holds.
This view records no independent task state. Preserve blocked and completed records.

Native contracts: [AGENTS.md](AGENTS.md). Task and gate signposts:
[public/links.toml](.docxology/public/links.toml). Resolve ecosystem members from
`daf_stack.manifest.default_manifest()`; Flywheel proposals and Horizon previews
remain subject to Operator policy, source freshness and separate execution admission.

- [daf-okn-stack-onboarding](tasks.yaml#L5) — Verify the offline package gate for stack onboarding
- [daf-okn-artifact-status](tasks.yaml#L10) — Inspect local graph and report evidence without regeneration
- [daf-okn-stack-status-consumer](tasks.yaml#L16) — Admit artifact status into stack and operator evidence views

## Retained notes

The following material is preserved verbatim as historical context. Its checkboxes,
status labels, counts and suggestions are not a current queue or validation receipt.
Unmapped suggestions require owner reconciliation against canonical task IDs before work.
Read the board above for current state; these notes grant no dispatch authority.

---

# daf-okn TODO

Forward workplan for the DAF-OKN project: pull, analyze, visualize, and
contribute to the Open Knowledge Network (okn.us / registry.okn.us).

## Backlog operating rules

- Keep deterministic and offline defaults unchanged unless a row explicitly
  scopes an opt-in.
- Do not close a row until its producer, artifact, consumer, gate, and failing
  negative control are present.
- Treat unavailable network, LLM, container, formal-tool, and publication paths
  as explicit skips or blockers.
- Re-derive counts and receipts from live source data; never copy measurements
  into this planning file.

## Phase 3 — graph-era backlog

Shipped in phase 2: `OKNRegistry` (kgs.yaml catalog, per-graph/federation
SPARQL, TPF, VoID endpoints, embeddings), `GraphDocument` model, cognitive
vault export, graph metrics + `graph_report.json`, network figures +
dashboard, and the contribute/validate package workflow
(`output/data/provenance/`).

Open limitations carried into the backlog:

- **VoID stats integration** — pull per-graph VoID statistics
  (`https://apps.okn.us/okn-void/sparql`) into the registry snapshot and
  surface catalog completeness (of 45 graphs) in `graph_report.json` and the
  dashboard.
- **Temporal registry views** — record catalog snapshots over time so
  registry drift (added/removed graphs, changed endpoints) is diffable;
  store fetch dates in `output/data/registry_snapshot.yaml`.
- **Per-graph embeddings weighting** — weight connector-search keywords by
  per-graph embeddings quality/availability instead of uniform ranking in
  `output/data/connector_search/results.json`.
- **LakeFS credentialed upload** — wire `core/contribute.py::upload_commands`
  to the versioned store at `repository.okn.us` with credentials; record
  upload receipts.
- **Upstream-format tracking** — upstream registry entry metadata schema is
  "not enforced upstream; treat fields as conventional" ([NOT DOCUMENTED]
  formal schema); track upstream format changes and validate our
  `registry_entry` output against observed conventions.
- **Tests + coverage gate** — keep ≥90% coverage on `src/`, zero-mock tests,
  deterministic fixtures for registry responses.
- **Release identifiers** — after the first tagged public release, mint a
  Zenodo DOI and add it to `CITATION.cff`, `codemeta.json` and `.zenodo.json`;
  until then leave identifiers unassigned.
- **First registry submission** — open the `cognitive-kb` pull request against
  `frink-okn/okn-registry` using `daf-okn package --preset cognitive-kb` (or the
  reference exporter in the `cognitive` repository), then upload via lakeFS.

## Current test and validator contract

- Dashboard fields and chart payloads are covered by schema assertions; extend
  those assertions with any future field change.
- `graph_report.json` shape (`graph_name`, `stats`, `problems`, `metrics`,
  `report_path`) is asserted in tests; extend assertions with any field
  change.

## Minor upcoming

| ID | Status | Size | Dependency | Next action / unblock condition | Proving artifact | Acceptance command | Negative control |
| --- | --- | --- | --- | --- | --- | --- | --- |
No active rows are currently scoped at this size.

## Medium upcoming

| ID | Status | Size | Dependency | Next action / unblock condition | Proving artifact | Acceptance command | Negative control |
| --- | --- | --- | --- | --- | --- | --- | --- |
VoID stats integration and per-graph embeddings weighting rows land here once
scoped against the live endpoints.

## Major upcoming

| ID | Status | Size | Dependency | Next action / unblock condition | Proving artifact | Acceptance command | Negative control |
| --- | --- | --- | --- | --- | --- | --- | --- |
LakeFS credentialed upload and temporal registry views land here once
contribution packaging is accepted upstream.

## Backlog status

Rows remain active until the acceptance command and negative control pass in
the same source revision. A blocked row is a deliberate boundary, not a skipped
success.
