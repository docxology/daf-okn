"""Graph analysis package — metrics over OKN graph documents plus report pipeline.

Layout:

* :mod:`daf_okn.analysis.graph_metrics` — networkx-based structural metrics
  (:func:`compute_metrics` and friends).
* :mod:`daf_okn.analysis.pipeline` — :func:`run_analysis`, the one-call
  "measure + write JSON report" orchestration; scripts delegate here.
"""

from __future__ import annotations

from .graph_metrics import (
    centrality_scores,
    compute_metrics,
    degree_sequence,
    edge_centrality_scores,
    in_out_degrees,
    triangle_count,
)
from .pipeline import REPORT_FILENAME, run_analysis

__all__ = [
    "REPORT_FILENAME",
    "centrality_scores",
    "compute_metrics",
    "degree_sequence",
    "edge_centrality_scores",
    "in_out_degrees",
    "run_analysis",
    "triangle_count",
]
