# `daf_okn/src/figures/`

Figure builders for the daf-okn Open Knowledge Network tooling.

This package renders deterministic matplotlib (Agg) figures from the shared
`GraphDocument` contract in `src/daf_okn/core/graph.py`. Keep figure-specific
data shaping here, keep graph statistics in `src/daf_okn/core/invariants.py`,
and keep CLI parsing in `scripts/`.

## Files

| File | Role |
| --- | --- |
| `__init__.py` | Public figure-builder exports. |
| `network_figure.py` | Network figure (spring layout, degree-scaled nodes, top-N labels) and graph-catalog bar chart. |

## See Also

- [`../README.md`](../README.md) - project source overview
- [`../AGENTS.md`](../AGENTS.md) - source-layer editing rules
