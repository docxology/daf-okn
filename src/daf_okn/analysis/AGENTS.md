# `daf_okn/src/analysis/` - agent guide

## Purpose

Importable graph-analysis orchestration for daf-okn: metrics computation and
the `graph_report.json` persistence pipeline.

## Rules

- Keep graph parsing and the document model in `core/graph.py`; this package
  consumes `GraphDocument` / NetworkX projections.
- Keep CLI parsing in `scripts/`; this package should expose callable workflow
  functions (`run_analysis`, `compute_metrics`).
- Keep metric helpers pure — no I/O inside `graph_metrics.py`.
- Keep generated file writes explicit and covered by tests (`pipeline.py` writes
  `graph_report.json` only).

## See Also

- [`README.md`](README.md) - quick reference
- [`../AGENTS.md`](../AGENTS.md) - source-layer contract