# Local status, stack roster and Sidecar evidence

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

Graph inspection checks serialized records before `GraphDocument.from_dict`
can coerce their values. Every node and edge must be an object; node `id` and
edge `source`/`target` must be present strings. Null, boolean, numeric, list and
object identifiers fail even when their string forms would match endpoints.
Existing invariant checks still reject empty or duplicate IDs, dangling
endpoints and self-loops. These type checks belong to artifact inspection;
permissive graph loading elsewhere is unchanged. An invalid graph retains the
digest of the original bytes and leaves any requested report unassessed.

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

## Roster membership (read-only)

`daf-stack` owns the stack inventory. `daf-stack-doctor roster` publishes it as
JSON, and this public checkout consumes that contract without importing
daf-stack:

```bash
# from the configured coordinator workspace, with both commands available
daf-stack-doctor roster --repo daf-okn |
  daf-okn stack-health --roster - --checkout /path/to/daf-okn
```

`src/daf_okn/core/stack_roster.py::parse_roster` validates the roster document
and `check_member` compares one member entry with the checkout on disk.
`--roster -` reads stdin, `--member` defaults to `daf-okn` and `--checkout`
defaults to the current directory. The `daf-okn.stack-roster/1` payload holds:

| Field | Meaning |
| --- | --- |
| `schema` | `daf-okn.stack-roster/1` |
| `status` | `pass` only when every check below holds |
| `member`, `roster_entry_path`, `checkout` | Roster claims compared with resolved paths |
| `expected_branch`, `measured_branch` | Roster branch and the branch in `.git/HEAD`; `null` when undeclared or unreadable |
| `checks` | One `{name, ok, detail}` per declared requirement |
| `native_gate` | Always `not_run` |

Treat roster inputs and observation output as local data. The output includes
absolute checkout paths and can include other paths supplied by the roster.
Use synthetic data in public examples and uploaded test artifacts.

The checks are `path` (the roster names this checkout), `branch`,
`required_files` (each declared checkout-relative path exists), `gate` (a
declared `gate_cmd` with an explicit script checked when possible), `board` (the roster's
`board_path`, which must stay inside the checkout, or `<checkout>/tasks.yaml`,
when `require_board`), and `sidecar` (`.docxology/manifest.toml` when
`require_sidecar`). Scoping `board_path` to the checkout keeps a mismatched
checkout from passing the board check on another tree's file.

The gate check verifies a literal checkout-relative script in one simple
command, including scripts passed to `bash`, `sh`, `python` or `python3`.
The check skips leading environment assignments and later command arguments.
Other forms, including compound commands,
report the script path as unverified and preserve `native_gate: not_run`.

Exit 0 when every declared requirement holds, 1 for a failing member or an
unreadable/malformed roster, 2 for missing arguments. No command is executed,
nothing is written and no network is used. The observation is offline
membership evidence only: it does not establish that the gate passes, that the
roster is current, or that the coordinator accepted this member. `read_branch`
follows a worktree `.git` file to its `gitdir` and reads `HEAD`; a detached
HEAD has no branch, so a declared branch then fails rather than passing by
default.

`tests/core/test_stack_roster.py` parses real roster-shaped documents, rejects
malformed, absent and duplicate members, and compares this public checkout with
the requirements the daf-stack manifest declares for it (name, path, branch,
the six required files, `bash scripts/gate.sh`, the board). Negative controls
cover a mismatched path or branch, a missing required file, a missing gate
script, an unparseable gate command, a required board/Sidecar manifest and an
out-of-checkout `required_files` entry. `tests/cli/test_cli.py` covers the CLI
exit codes, stdin input and malformed-roster reporting.

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

`tests/analysis/test_artifact_status.py` covers successful CLI inspection with
unchanged inputs, malformed nested records and non-string identifiers (including
reports matching the coerced graph), missing/malformed inputs, invalid endpoints,
altered report fields, boolean measurements and changed structure with unchanged
node/edge counts. Rejected graph bytes retain their digest; requested reports stay
unassessed. Live results belong in the handoff, not static count claims.

Next, daf-stack/daf-operator can admit this existing console entrypoint as an
artifact observation. Preserve the explicit unassessed fields. Independently
bind source revision, dirty diff, board digest and gate output when retaining
acceptance evidence; no new shared receipt format is introduced here. Native
gate output and Sidecar doctor output remain separate evidence.
