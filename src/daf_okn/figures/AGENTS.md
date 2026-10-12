# `daf_okn/src/figures/` - agent guide

## Purpose

Importable figure-generation package for daf-okn.

## Rules

- Keep scripts as thin wrappers; figure assembly belongs in this package.
- Keep metric and layout math generic over NetworkX graphs; graph statistics
  belong in `core/invariants.py` and `analysis/graph_metrics.py`.
- Use real project outputs or typed config inputs in tests; avoid mocks.
- Write generated files only from explicit orchestration paths.

## See Also

- [`README.md`](README.md) - quick reference
- [`../AGENTS.md`](../AGENTS.md) - source-layer contract
