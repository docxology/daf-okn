# tests/cli

Tests for the `daf-okn` command line (`src/daf_okn/cli.py`).

| File | Focus |
| --- | --- |
| `test_cli.py` | Every subcommand (`pull`, `export`, `analyze`, `visualize`, `package`) run against real files in `tmp_path`; `--help` for each; argument and error handling. `pull` is only exercised through `--kgs-path` and argument parsing, so no test touches the network. |

Technical notes: [`AGENTS.md`](AGENTS.md).

`tests/analysis/test_artifact_status.py` drives `status` through the real CLI
and checks file hashes, unchanged input files, malformed/missing inputs, graph
invariant failures and stale report refusals.
