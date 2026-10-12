# tests/analysis/ — analysis-cluster behavior tests

Mirrors `src/daf_okn/analysis/` (SUBMODULAR-CODE-2):
structural metric helpers over NetworkX projections (`graph_metrics.py`),
the `run_analysis` report pipeline (`pipeline.py`), and the auxiliary
script smoke tests (`scripts/` delegate to every cluster, so their smoke
tests live with the orchestration cluster). See [`../AGENTS.md`](../AGENTS.md)
for the testing contract.
