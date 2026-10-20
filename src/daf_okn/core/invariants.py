"""Structural invariants for OKN graph documents.

Two entry points:

* :func:`validate_graph` — returns a list of human-readable problems found in
  a :class:`~daf_okn.core.graph.GraphDocument` (duplicate node ids, edge
  endpoints missing from the node set, self-loops, empty node ids).
* :func:`graph_stats` — a small summary dict (node/edge counts, density,
  directedness, weakly-connected component count) for dashboard and report
  consumers.

Both are pure functions over the document; no I/O, no network access.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:  # pragma: no cover — typing-only import to avoid a cycle
    from .graph import GraphDocument

__all__ = ["graph_stats", "validate_graph"]


def validate_graph(doc: GraphDocument) -> list[str]:
    """Return human-readable structural problems with ``doc``.

    Checks:
    * empty node ids (``""`` or missing),
    * duplicate node ids (a node id registered more than once),
    * edge endpoints (source or target) missing from the node set,
    * self-loops (an edge whose source equals its target).

    A valid document yields an empty list. The checks are deliberately cheap
    (single pass, no graph construction) so they can run on every load.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for node in doc.nodes:
        if not node.id:
            problems.append(f"node with empty id (title={node.title!r})")
            continue
        if node.id in seen:
            problems.append(f"duplicate node id: {node.id!r}")
        seen.add(node.id)

    for edge in doc.edges:
        for role, endpoint in (("source", edge.source), ("target", edge.target)):
            if endpoint not in seen:
                problems.append(
                    f"edge {edge.source!r} -> {edge.target!r} (relation {edge.relation!r}): "
                    f"{role} endpoint {endpoint!r} missing from nodes"
                )
        if edge.source == edge.target:
            problems.append(f"self-loop on node {edge.source!r}")
    return problems


def graph_stats(doc: GraphDocument) -> dict[str, Any]:
    """Return a small summary dict for ``doc``.

    Keys: ``node_count`` / ``edge_count`` (document record counts),
    ``projected_node_count`` / ``projected_edge_count`` count the directed
    simple projection, which also determines ``density`` and connectivity.
    ``statement_count`` counts distinct source/relation/target triples;
    ``duplicate_statement_count`` counts repeated triples irrespective of origin.
    ``parallel_statement_count`` counts distinct triples lost on projection.
    ``density`` is ``m / (n * (n - 1))`` (0 when fewer than two nodes);
    ``directed`` (always ``True`` — stats
    use the directed interpretation), and ``component_count`` (weakly
    connected components of the directed projection).
    """
    node_count = len(doc.nodes)
    edge_count = len(doc.edges)
    graph = doc.to_networkx(directed=True)
    statements = {(edge.source, edge.relation, edge.target) for edge in doc.edges}
    projected_edge_count = graph.number_of_edges()
    component_count = nx.number_weakly_connected_components(graph) if graph else 0
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "projected_node_count": graph.number_of_nodes(),
        "projected_edge_count": projected_edge_count,
        "statement_count": len(statements),
        "duplicate_statement_count": edge_count - len(statements),
        "parallel_statement_count": len(statements) - projected_edge_count,
        "relation_counts": dict(sorted(Counter(edge.relation for edge in doc.edges).items())),
        "node_type_counts": dict(sorted(Counter(node.node_type for node in doc.nodes).items())),
        "density": nx.density(graph),
        "directed": True,
        "component_count": component_count,
    }
