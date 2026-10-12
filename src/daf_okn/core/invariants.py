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
    ``density`` (directed simple-graph interpretation, ``m / (n * (n - 1))``,
    ``0.0`` when fewer than two nodes), ``directed`` (always ``True`` — stats
    use the directed interpretation), and ``component_count`` (weakly
    connected components of the directed projection).
    """
    node_count = len(doc.nodes)
    edge_count = len(doc.edges)
    density = (edge_count / (node_count * (node_count - 1))) if node_count > 1 else 0.0
    component_count = (
        nx.number_weakly_connected_components(doc.to_networkx(directed=True)) if node_count else 0
    )
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "density": density,
        "directed": True,
        "component_count": component_count,
    }
