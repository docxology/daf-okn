"""NetworkX-based structural metrics over graph documents.

Every helper takes a networkx graph (typically
``GraphDocument.to_networkx()``) so figures and dashboards can reuse the same
projections; :func:`compute_metrics` is the one-call summary used by the
analysis pipeline and CLI.

All functions are pure computations over the given graph — no I/O, no
network access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

from ..core.invariants import graph_stats

if TYPE_CHECKING:  # pragma: no cover — typing-only import to avoid a cycle
    from ..core.graph import GraphDocument

__all__ = [
    "centrality_scores",
    "compute_metrics",
    "degree_sequence",
    "edge_centrality_scores",
    "in_out_degrees",
    "triangle_count",
]


def degree_sequence(graph: nx.Graph | nx.DiGraph) -> list[int]:
    """Return the total-degree sequence (in + out for directed), sorted descending."""
    return sorted((degree for _, degree in graph.degree()), reverse=True)


def in_out_degrees(graph: nx.Graph | nx.DiGraph) -> dict[str, tuple[int, int]]:
    """Return ``{node: (in_degree, out_degree)}`` for a directed projection."""
    if not isinstance(graph, nx.DiGraph):
        raise TypeError("in_out_degrees requires a directed graph; use to_networkx(directed=True)")
    return {node: (graph.in_degree(node), graph.out_degree(node)) for node in graph.nodes}


def centrality_scores(
    graph: nx.Graph | nx.DiGraph, *, betweenness: bool = True
) -> dict[str, dict[str, float]]:
    """Return node centrality mappings.

    Always includes ``"degree"``; includes ``"betweenness"`` (networkx
    :func:`nx.betweenness_centrality`) unless *betweenness* is False.
    """
    scores: dict[str, dict[str, float]] = {"degree": nx.degree_centrality(graph)}
    if betweenness:
        scores["betweenness"] = nx.betweenness_centrality(graph)
    return scores


def edge_centrality_scores(
    graph: nx.Graph | nx.DiGraph,
) -> dict[tuple[str, str], float]:
    """Return edge betweenness centrality keyed by ``(source, target)``."""
    return nx.edge_betweenness_centrality(graph)


def component_counts(graph: nx.Graph | nx.DiGraph) -> dict[str, int]:
    """Return weakly (and, for directed graphs, strongly) connected component counts."""
    counts: dict[str, int] = {}
    if isinstance(graph, nx.DiGraph):
        counts["weakly"] = nx.number_weakly_connected_components(graph)
        counts["strongly"] = nx.number_strongly_connected_components(graph)
    else:
        counts["weakly"] = nx.number_connected_components(graph)
    return counts


def triangle_count(graph: nx.Graph | nx.DiGraph) -> int:
    """Count triangles in the undirected simple projection of ``graph``."""
    undirected: nx.Graph = nx.Graph(graph)
    counts = nx.triangles(undirected)
    if not isinstance(counts, dict):
        raise TypeError("triangle counts must be a node mapping")
    return sum(counts.values()) // 3


def _top_central_nodes(scores: dict[str, float], top_k: int) -> list[tuple[str, float]]:
    """Rank nodes by score (descending, id as tie-break) and keep the top *k*."""
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [(node, float(score)) for node, score in ranked[:top_k]]


def compute_metrics(
    doc: GraphDocument, *, centralities: bool = True, top_k: int = 5
) -> dict[str, Any]:
    """Compute structural metrics for ``doc`` over its directed projection.

    Args:
        doc: The graph document to measure.
        centralities: When True (default), include per-node
            ``degree_centrality`` and ``betweenness_centrality`` mappings and
            rank ``top_central_nodes`` by betweenness; otherwise rank by
            degree centrality and omit the per-node mappings.
        top_k: Length of the ``top_central_nodes`` list of ``(id, score)``
            pairs (descending score, node id as deterministic tie-break).

    Returns:
        Dict with the pinned summary keys (``node_count``, ``edge_count``,
        ``density``, ``weakly_connected_components``,
        ``strongly_connected_components``, ``mean_degree``, ``triangles``
        (undirected projection), ``top_central_nodes``) plus the optional
        centrality mappings. Record, distinct statement and collapsed parallel
        counts are reported separately from projected ``edge_count``; relation
        and node-type counts retain the document's typed information.
    """
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 0:
        raise ValueError("top_k must be a nonnegative integer")
    graph = doc.to_networkx(directed=True)
    stats = graph_stats(doc)
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    degree = dict(graph.degree())
    metrics: dict[str, Any] = {
        "node_count": node_count,
        "edge_count": edge_count,
        "density": nx.density(graph),
        "weakly_connected_components": (
            nx.number_weakly_connected_components(graph) if node_count else 0
        ),
        "strongly_connected_components": (
            nx.number_strongly_connected_components(graph) if node_count else 0
        ),
        "mean_degree": (sum(degree.values()) / node_count) if node_count else 0.0,
        "triangles": triangle_count(graph),
        "edge_record_count": stats["edge_count"],
        **{
            key: stats[key]
            for key in (
                "statement_count",
                "duplicate_statement_count",
                "parallel_statement_count",
                "relation_counts",
                "node_type_counts",
            )
        },
    }

    if centralities:
        degree_centrality = nx.degree_centrality(graph)
        betweenness_centrality = nx.betweenness_centrality(graph)
        metrics["degree_centrality"] = degree_centrality
        metrics["betweenness_centrality"] = betweenness_centrality
        ranking = betweenness_centrality
    else:
        # Rank by degree centrality without paying for betweenness.
        if node_count > 1:
            ranking = {node: graph.degree(node) / (node_count - 1) for node in graph.nodes}
        else:
            ranking = {node: 0.0 for node in graph.nodes}
    metrics["top_central_nodes"] = _top_central_nodes(ranking, top_k)
    return metrics
