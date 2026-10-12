"""Network and graph-catalog figure builders for daf_okn.

Deterministic matplotlib (Agg) figures built from the shared
:class:`~daf_okn.core.graph.GraphDocument` contract:

* :func:`plot_network` — spring/embedding layout of a graph document with
  degree-scaled node sizes, top-N degree labels, and directed edge arrows.
* :func:`plot_graph_catalog` — horizontal bar chart of registry graph
  shortnames (e.g. ``kgs.yaml`` snapshot dicts), counting the metadata
  fields present on each entry.
* :func:`network_figure_bytes` — the network figure rendered to PNG bytes
  (used by the dashboard for data-URI embedding).

All functions are pure with respect to their inputs apart from writing the
requested output file; no network access and no optimizer imports.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)  # headless-safe backend, before pyplot import

import matplotlib.figure
import matplotlib.pyplot as plt
import networkx as nx

from ..core.graph import GraphDocument

__all__ = ["network_figure_bytes", "plot_graph_catalog", "plot_network"]

_LAYOUTS = ("spring", "circular", "kamada_kawai", "random")

_NODE_COLOR = "#3b82f6"
_EDGE_COLOR = "#64748b"
_CATALOG_COLOR = "#0072B2"


def plot_network(
    doc: GraphDocument,
    path: Path,
    *,
    layout: str = "spring",
    figsize: tuple[float, float] = (12, 9),
    node_size_scale: float = 600.0,
    seed: int = 42,
    label_top: int = 25,
) -> Path:
    """Render ``doc`` as a network figure and write it to ``path``.

    Nodes are positioned with the requested layout (deterministic for
    ``spring``/``random`` via ``seed``), sized by degree, and only the
    ``label_top`` highest-degree nodes are labelled. Directed graphs draw
    edge arrows. Returns ``path``.
    """
    data = network_figure_bytes(
        doc,
        layout=layout,
        figsize=figsize,
        node_size_scale=node_size_scale,
        seed=seed,
        label_top=label_top,
    )
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path


def network_figure_bytes(
    doc: GraphDocument,
    *,
    layout: str = "spring",
    figsize: tuple[float, float] = (12, 9),
    node_size_scale: float = 600.0,
    seed: int = 42,
    label_top: int = 25,
) -> bytes:
    """Render ``doc`` as a PNG network figure and return the raw bytes."""
    if layout not in _LAYOUTS:
        raise ValueError(f"unsupported layout {layout!r}; expected one of {_LAYOUTS}")
    graph = doc.to_networkx(directed=True)
    fig, ax = plt.subplots(figsize=figsize)
    try:
        _draw_network(
            graph,
            ax,
            layout=layout,
            node_size_scale=node_size_scale,
            seed=seed,
            label_top=label_top,
        )
        ax.set_title(doc.name)
        ax.set_axis_off()
        fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=150)
        return buffer.getvalue()
    finally:
        plt.close(fig)


def _draw_network(
    graph: nx.DiGraph | nx.Graph,
    ax: matplotlib.axes.Axes,
    *,
    layout: str,
    node_size_scale: float,
    seed: int,
    label_top: int,
) -> None:
    """Draw nodes, edges, and top-degree labels onto ``ax``."""
    if graph.number_of_nodes() == 0:
        return
    positions = _layout_positions(graph, layout, seed)
    degree = dict(graph.degree())
    max_degree = max(degree.values()) or 1
    sizes = [node_size_scale * (0.35 + 0.65 * deg / max_degree) for deg in degree.values()]
    nx.draw_networkx_edges(
        graph,
        positions,
        ax=ax,
        arrows=graph.is_directed(),
        arrowsize=10,
        edge_color=_EDGE_COLOR,
        alpha=0.6,
    )
    nx.draw_networkx_nodes(
        graph,
        positions,
        ax=ax,
        node_size=sizes,
        node_color=_NODE_COLOR,
        edgecolors="black",
        linewidths=0.5,
    )
    top_nodes = sorted(degree, key=lambda node: (-degree[node], str(node)))[: max(label_top, 0)]
    labels = {node: _short_label(node) for node in top_nodes}
    if labels:
        nx.draw_networkx_labels(graph, positions, labels=labels, ax=ax, font_size=8)


def _layout_positions(graph: nx.DiGraph | nx.Graph, layout: str, seed: int) -> dict[Any, Any]:
    """Compute node positions for the requested deterministic layout."""
    if layout == "spring":
        return nx.spring_layout(graph, seed=seed)
    if layout == "circular":
        return nx.circular_layout(graph)
    if layout == "kamada_kawai":
        return nx.kamada_kawai_layout(graph)
    if layout == "random":
        return nx.random_layout(graph, seed=seed)
    raise ValueError(f"unsupported layout {layout!r}; expected one of {_LAYOUTS}")


def _short_label(node: Any) -> str:
    """Compact an IRI-like node id to its local name for label display."""
    text = str(node)
    for separator in ("#", "/"):
        if separator in text:
            text = text.rsplit(separator, 1)[-1]
    if len(text) > 28:
        text = text[:25] + "..."
    return text


def plot_graph_catalog(graphs_meta: list[dict[str, Any]], path: Path) -> Path:
    """Render a horizontal bar chart of graph shortnames to ``path``.

    Each entry of ``graphs_meta`` is a metadata dict (e.g. a ``kgs.yaml``
    snapshot entry); the bar for its ``shortname`` is as long as the number
    of metadata fields present (truthy) on that entry. Returns ``path``.
    """
    shortnames: list[str] = []
    counts: list[int] = []
    for index, entry in enumerate(graphs_meta):
        if not isinstance(entry, Mapping):
            raise TypeError(f"graphs_meta[{index}] must be a mapping, got {type(entry).__name__}")
        shortnames.append(str(entry.get("shortname") or f"graph-{index}"))
        counts.append(sum(1 for value in entry.values() if value))

    height = max(2.0, 0.5 * len(shortnames) + 1.5)
    fig, ax = plt.subplots(figsize=(9, height))
    try:
        ax.barh(range(len(counts)), counts, color=_CATALOG_COLOR)
        ax.set_yticks(range(len(shortnames)), labels=shortnames)
        ax.invert_yaxis()
        ax.set_xlabel("metadata fields present")
        ax.set_ylabel("graph shortname")
        ax.set_title("OKN graph catalog")
        fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=150)
        data = buffer.getvalue()
    finally:
        plt.close(fig)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path
