# Local status and Sidecar evidence

daf-okn owns OKN registry access, graph analysis, capture/replay and contribution
packaging. The cognitive repository owns its graph and exporter. daf-dot owns
the real-time voice protocol; daf-operator owns spatialized information. Stack
inventory and cross-repository acceptance belong to daf-stack. Ready work and
integration needs are recorded in `tasks.yaml`; `TODO.md` remains the research
backlog.

## Read existing artifacts

```bash
daf-okn status --graph graph.json --report report/graph_report.json
```

`src/daf_okn/analysis/artifact_status.py::inspect_artifacts` performs no writes
and no network calls. It reuses `GraphDocument`, `validate_graph`, `graph_stats`
and `compute_metrics`; it does not regenerate the report. The console entrypoint
`daf_okn.cli:main` emits JSON on stdout, including for unreadable/malformed input.
Missing arguments exit 2 through the existing parser. Requested evidence that
cannot pass inspection exits 1; successful inspection exits 0.

The `daf-okn.artifact-status/1` payload contains:

| Field | Meaning |
| --- | --- |
| `observed_at` | UTC timestamp of this observation; no reusable freshness guarantee |
| `status` | `pass` or `fail` for the requested artifact inspection only |
| `graph`, `report` | `path`, SHA-256 of exact bytes read, and `problems` |
| `report: null` | Report inspection was not requested |
| `sha256: null` | File was not read; for example a missing input or report skipped after an invalid graph |
| `native_gate` | Always `not_run` |
| `sidecar`, `registry_acceptance` | Always `not_checked` |

Report consistency requires matching graph name, statistics, invariant problems
and all metrics against fresh computation. `report_path` is informational and
does not establish provenance. Metric consistency cannot prove full source
custody: a label or metadata change can leave metrics unchanged. Input hashes
bind the bytes inspected during this call. Consumers must re-observe inputs on
reuse; the observation is not an atomic snapshot across files and does not bind
the repository revision, board, gate results or registry acceptance.

For canonical RDF custody, continue using `daf-okn bundle-rdf --check --output
BUNDLE` and the [existing custody/replay contracts](okn/custody-and-replay.md).

## Sidecar foothold

`.docxology/` was scaffolded using daf-sidecar's existing `init` interface.
`manifest.toml` and `.sidecar-lock.toml` retain their native schemas. The manifest
owner names the public repository account; author and ORCID metadata mirror the
existing `CITATION.cff`. These descriptive fields do not verify identity or
adoption. No recipient or encrypted content is provisioned.
`public/links.toml` is the native free-form signpost to this contract and board.

Run the admitted installed Sidecar CLI from this repository:

```bash
docxology-sidecar doctor . --json
```

Keep its native `{status,data,error,meta}` envelope. `status: ok` means command
execution succeeded; inspect `data.verdict` (`pass`, `concerns`, `fail`) for the
Sidecar verdict. Dirty work can yield `concerns`. Sidecar metadata, filesystem
coverage and ciphertext integrity do not establish the native Python gate,
registry submission, deployment, identity verification or adoption.

## Acceptance and next steps

The native gate stays `bash scripts/gate.sh`: locked dev dependencies, whole
suite and the existing branch coverage threshold. Install the admitted runtime
before any status/gate bridge call; do not provision during a consumer call.
An offline cache miss is an environment blocker, not a passing gate. On hosts
with cached Python 3.12 packages, `UV_OFFLINE=1 UV_PYTHON=3.12 bash
scripts/gate.sh` selects that runtime without changing the lock or gate profile.

`tests/analysis/test_artifact_status.py` proves successful CLI inspection with
unchanged inputs, then rejects missing/malformed inputs, invalid graph endpoints,
altered report fields, boolean measurements and changed structure with unchanged
node/edge counts. Live results belong in the handoff, not static count claims.

Next, daf-stack/daf-operator can admit this existing console entrypoint as an
artifact observation. Preserve the explicit unassessed fields. Independently
bind source revision, dirty diff, board digest and gate output when retaining
acceptance evidence; no new shared receipt format is introduced here. Native
gate output and Sidecar doctor output remain separate evidence.
