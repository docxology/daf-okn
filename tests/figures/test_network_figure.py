"""Tests for the network and graph-catalog figure builders."""

import os

os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path

import pytest

from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord
from daf_okn.figures import network_figure_bytes, plot_graph_catalog, plot_network
from daf_okn.figures.network_figure import _layout_positions, _short_label

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _six_node_document() -> GraphDocument:
    """Build a small deterministic 6-node graph document."""
    names = [f"n{i}" for i in range(6)]
    nodes = [NodeRecord(id=name, title=name.capitalize()) for name in names]
    edges = [
        EdgeRecord(source="n0", target="n1", relation="depends_on"),
        EdgeRecord(source="n1", target="n2", relation="depends_on"),
        EdgeRecord(source="n2", target="n3", relation="related"),
        EdgeRecord(source="n3", target="n4", relation="related"),
        EdgeRecord(source="n4", target="n5", relation="related"),
        EdgeRecord(source="n5", target="n0", relation="related"),
        EdgeRecord(source="n0", target="n3", relation="related"),
    ]
    return GraphDocument(name="Toy Graph", nodes=nodes, edges=edges)


def test_plot_network_writes_valid_png(tmp_path: Path) -> None:
    """plot_network writes a non-empty file with PNG magic bytes."""
    out = tmp_path / "figures" / "network.png"
    result = plot_network(_six_node_document(), out)
    assert result == out
    data = out.read_bytes()
    assert data.startswith(PNG_MAGIC)
    assert len(data) > 0


def test_plot_network_is_deterministic(tmp_path: Path) -> None:
    """Two renders with the same fixed seed produce identical bytes."""
    first = tmp_path / "a.png"
    second = tmp_path / "b.png"
    plot_network(_six_node_document(), first)
    plot_network(_six_node_document(), second)
    assert first.read_bytes() == second.read_bytes()


def test_plot_network_rejects_unknown_layout(tmp_path: Path) -> None:
    """An unsupported layout name raises ValueError."""
    with pytest.raises(ValueError, match="layout"):
        plot_network(_six_node_document(), tmp_path / "x.png", layout="bogus")


def test_plot_graph_catalog_writes_valid_png(tmp_path: Path) -> None:
    """plot_graph_catalog writes a non-empty PNG from metadata dicts."""
    out = tmp_path / "catalog.png"
    graphs_meta = [
        {"shortname": "bio", "domain": "biology", "triples": 1200},
        {"shortname": "climate", "domain": "climate", "triples": None},
        {"shortname": "geo"},
    ]
    result = plot_graph_catalog(graphs_meta, out)
    assert result == out
    data = out.read_bytes()
    assert data.startswith(PNG_MAGIC)
    assert len(data) > 0


def test_network_figure_bytes_renders_empty_graph() -> None:
    """An empty document still renders a valid (label-free) PNG."""
    data = network_figure_bytes(GraphDocument(name="empty"))
    assert data.startswith(PNG_MAGIC)


def test_layout_variants_render_valid_pngs() -> None:
    """circular and random layouts produce PNG bytes (kamada_kawai needs scipy)."""
    for layout in ("circular", "random"):
        data = network_figure_bytes(_six_node_document(), layout=layout, seed=7)
        assert data.startswith(PNG_MAGIC), layout


def test_layout_positions_rejects_unknown_layout() -> None:
    """The layout dispatcher rejects names outside the supported set."""
    graph = _six_node_document().to_networkx(directed=True)
    with pytest.raises(ValueError, match="unsupported layout"):
        _layout_positions(graph, "bogus", seed=0)


def test_short_label_compacts_iris_and_truncates() -> None:
    """IRI local names survive ``#``/``/`` stripping and long ids truncate."""
    assert _short_label("https://okn.example.org/entity/markov_blanket") == "markov_blanket"
    assert _short_label("https://okn.example.org/entity/Markov#blanket") == "blanket"
    assert _short_label("b" * 40) == "b" * 25 + "..."


def test_plot_network_honours_figsize_node_size_and_label_top(tmp_path: Path) -> None:
    """Custom figsize/node_size_scale/label_top keyword arguments render fine."""
    out = tmp_path / "compact.png"

    result = plot_network(
        _six_node_document(),
        out,
        figsize=(4, 3),
        node_size_scale=200.0,
        label_top=0,
    )

    assert result == out
    assert out.read_bytes().startswith(PNG_MAGIC)


def test_plot_graph_catalog_rejects_non_mapping(tmp_path: Path) -> None:
    """Non-mapping catalog entries raise a TypeError with the entry index."""
    with pytest.raises(TypeError, match="graphs_meta\\[1\\]"):
        plot_graph_catalog([{"shortname": "ok"}, 42], tmp_path / "catalog.png")
