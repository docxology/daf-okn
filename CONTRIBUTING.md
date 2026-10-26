# Contributing

Thanks for helping. The short version:

```bash
git clone https://github.com/docxology/daf-okn && cd daf-okn
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q --cov=src --cov-branch --cov-fail-under=90   # tests, with the coverage gate
ruff check .                                            # lint (ruff is in the dev extra)
```

## Ground rules

- Tests use real data and real computation: small graphs, vaults written to `tmp_path`, and
  the fixture vault in `tests/fixtures/cognitive/`. No mocks of the code under test, and no
  live network requests (network clients take an injected `requests.Session`).
- New behaviour comes with tests; coverage of `src/` must stay at or above 90%.
- Keep `scripts/` thin: logic belongs in `src/daf_okn/`, scripts only parse arguments and call it.
- Every folder keeps its `README.md` and `AGENTS.md` pair; update them when behaviour changes.
- The version lives in `pyproject.toml`, `src/daf_okn/__init__.py`, `CITATION.cff`,
  `codemeta.json`, `.zenodo.json` and `manuscript/config.yaml`; a test keeps them equal.
  Add a `CHANGELOG.md` entry for user-visible changes.
- RDF output follows the registry's guidance: reuse standard vocabularies, entity IRIs under
  `https://purl.org/okn/frink/kg/<shortname>/`. Change `src/daf_okn/core/rdf.py`, and its tests
  in `tests/core/test_rdf.py`, together.

## Reporting issues

Open a GitHub issue with the command you ran, the output, and your Python and daf-okn versions.
Security problems go to the address in [SECURITY.md](SECURITY.md) instead.
