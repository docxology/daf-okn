"""Graph analysis pipeline: compute metrics and persist a JSON report.

This module replaces the old optimization-convergence pipeline. A single
entry point, :func:`run_analysis`, measures a :class:`~daf_okn.core.graph.
GraphDocument` (via :mod:`daf_okn.analysis.graph_metrics` and
:mod:`daf_okn.core.invariants`), writes a self-contained JSON report into the
requested directory, and returns the same report as a dict. Scripts stay thin
wrappers around this function.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.graph import GraphDocument
from ..core.invariants import graph_stats, validate_graph
from .graph_metrics import compute_metrics

__all__ = ["REPORT_FILENAME", "run_analysis"]

REPORT_FILENAME = "graph_report.json"


def run_analysis(graph: GraphDocument, out_dir: str | Path) -> dict[str, Any]:
    """Compute metrics for ``graph`` and write a JSON report into ``out_dir``.

    The report contains the graph name, :func:`~daf_okn.core.invariants.
    graph_stats` summary, structural problems found by
    :func:`~daf_okn.core.invariants.validate_graph` (empty for a valid
    document), and the :func:`~daf_okn.analysis.graph_metrics.compute_metrics`
    dict. The same payload (plus the report path) is returned so callers can
    inspect or forward it without re-reading the file.

    Args:
        graph: The graph document to analyze.
        out_dir: Directory the ``graph_report.json`` report is written to
            (created if missing).

    Returns:
        The written report dict, including a ``report_path`` key.
    """
    report: dict[str, Any] = {
        "graph_name": graph.name,
        "stats": graph_stats(graph),
        "problems": validate_graph(graph),
        "metrics": compute_metrics(graph),
    }
    out_path = Path(out_dir) / REPORT_FILENAME
    report["report_path"] = str(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
