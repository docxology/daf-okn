# `daf_okn/src/analysis/`

Importable analysis package for daf-okn.

This package computes structural metrics over `GraphDocument` projections and
persists the JSON analysis report. Scripts delegate here so the analysis
workflow is testable without shell logic.

## Files

| File | Role |
| --- | --- |
| `__init__.py` | Re-export barrel (`compute_metrics`, `run_analysis`, metric helpers). |
| `graph_metrics.py` | Pure NetworkX metrics: `compute_metrics` plus `degree_sequence`, `in_out_degrees`, `centrality_scores`, `edge_centrality_scores`, `component_counts`, `triangle_count`. |
| `pipeline.py` | `run_analysis(graph, out_dir)` — measure + write `graph_report.json` (`REPORT_FILENAME`), return the report dict. |

## See Also

- [`../README.md`](../README.md) - project source overview
- [`../AGENTS.md`](../AGENTS.md) - source-layer editing rules