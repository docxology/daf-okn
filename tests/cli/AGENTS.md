# tests/cli - AGENTS.md

Scope: the `daf-okn` console script and `python -m daf_okn`.

- Call `daf_okn.cli.main(argv)` in-process and assert on exit codes, stdout/stderr and the files
  written below `tmp_path`; one test runs `python -m daf_okn --help` as a subprocess.
- Use real graphs: `GraphDocument(...).save_json(...)` or the vault in `tests/fixtures/cognitive/`.
- No mocks and no network. `pull list` and `pull snapshot` take `--kgs-path` for a local
  `kgs.yaml`; `pull query` is covered by argument handling only.
- When a subcommand gains an option, add a test for it and update `README.md` and the table in
  the root `README.md`.
