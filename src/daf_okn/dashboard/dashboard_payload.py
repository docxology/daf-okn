"""Pure, JSON-serializable summary payload for the daf_okn dashboard.

The payload is the single producer-side contract shared by the static
dashboard (:mod:`daf_okn.dashboard.dashboard`) and the test suite: summary
statistics (from the provided ``metrics`` dict when given, otherwise from
:func:`daf_okn.core.invariants.graph_stats`), plus capped node/edge tables.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import networkx as nx

from ..core.graph import GraphDocument
from ..core.invariants import graph_stats

__all__ = ["MAX_TABLE_ROWS", "build_payload"]

MAX_TABLE_ROWS = 200


def build_payload(doc: GraphDocument, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a JSON-serializable summary payload for ``doc``.

    ``metrics`` (when provided) takes precedence over computed statistics;
    otherwise statistics come from :func:`daf_okn.core.invariants.graph_stats`
    (keys: ``node_count``, ``edge_count``, ``density``, ``component_count``).
    Node and edge tables are capped at :data:`MAX_TABLE_ROWS` rows.
    """
    provided = dict(metrics) if metrics is not None else {}
    stats: dict[str, Any] = {**_graph_stats(doc), **provided}

    node_count = _as_int(stats.get("node_count"), len(doc.nodes))
    edge_count = _as_int(stats.get("edge_count"), len(doc.edges))
    density = _as_float(stats.get("density"), _directed_density(node_count, edge_count))
    component_count = _as_int(stats.get("component_count"), _weak_component_count(doc))

    return {
        "name": doc.name,
        "node_count": node_count,
        "edge_count": edge_count,
        "density": density,
        "component_count": component_count,
        "stats": stats,
        "nodes": [
            {"id": node.id, "title": node.title, "node_type": node.node_type}
            for node in doc.nodes[:MAX_TABLE_ROWS]
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "origin": edge.origin,
            }
            for edge in doc.edges[:MAX_TABLE_ROWS]
        ],
        "truncated": {
            "nodes": len(doc.nodes) > MAX_TABLE_ROWS,
            "edges": len(doc.edges) > MAX_TABLE_ROWS,
        },
    }


def _graph_stats(doc: GraphDocument) -> dict[str, Any]:
    """Return ``graph_stats(doc)`` as a dict, tolerating provider hiccups."""
    try:
        stats = graph_stats(doc)
    except Exception:  # noqa: BLE001 - stats are best-effort; the payload must still build
        return {}
    return dict(stats) if isinstance(stats, Mapping) else {}


def _directed_density(node_count: int, edge_count: int) -> float:
    """Directed simple-graph density ``E / (N * (N - 1))`` (0 when N < 2)."""
    if node_count < 2:
        return 0.0
    return float(edge_count) / float(node_count * (node_count - 1))


def _weak_component_count(doc: GraphDocument) -> int:
    """Count weakly connected components of ``doc`` (0 for an empty graph)."""
    if not doc.nodes:
        return 0
    graph = doc.to_networkx(directed=False)
    return int(nx.number_connected_components(graph))


def _as_int(value: Any, fallback: int) -> int:
    """Coerce ``value`` to ``int`` when it is a real number, else ``fallback``."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return int(value)
    return fallback


def _as_float(value: Any, fallback: float) -> float:
    """Coerce ``value`` to ``float`` when it is a real number, else ``fallback``."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    return fallback
