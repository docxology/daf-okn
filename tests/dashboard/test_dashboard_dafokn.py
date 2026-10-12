"""Tests for the daf_okn static dashboard and its payload."""

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import json
from pathlib import Path

import pytest

from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord
from daf_okn.dashboard import (
    MAX_TABLE_ROWS,
    build_dashboard,
    build_payload,
    cli_main,
    dashboard_payload,
)

EXPECTED_KEYS = {
    "name",
    "node_count",
    "edge_count",
    "density",
    "component_count",
    "stats",
    "nodes",
    "edges",
    "truncated",
}


def _document(node_count: int = 6) -> GraphDocument:
    """Build a deterministic chain graph document with ``node_count`` nodes."""
    names = [f"n{i}" for i in range(node_count)]
    nodes = [NodeRecord(id=name, title=name.capitalize()) for name in names]
    edges = [
        EdgeRecord(source=names[i], target=names[i + 1], relation="related")
        for i in range(node_count - 1)
    ]
    return GraphDocument(name="Toy Graph", nodes=nodes, edges=edges)


def test_build_payload_keys_and_json_roundtrip() -> None:
    """build_payload exposes the documented keys and survives a JSON roundtrip."""
    doc = _document()
    payload = build_payload(doc)
    assert set(payload) >= EXPECTED_KEYS
    assert payload["name"] == "Toy Graph"
    assert payload["node_count"] == 6
    assert payload["edge_count"] == 5
    assert 0.0 <= payload["density"] <= 1.0
    assert payload["component_count"] == 1
    assert json.loads(json.dumps(payload)) == payload


def test_build_payload_prefers_metrics_when_given() -> None:
    """A provided metrics dict takes precedence over computed statistics."""
    payload = build_payload(
        _document(),
        metrics={
            "node_count": 99,
            "edge_count": 5,
            "density": 0.5,
            "component_count": 3,
        },
    )
    assert payload["node_count"] == 99
    assert payload["edge_count"] == 5
    assert payload["density"] == 0.5
    assert payload["component_count"] == 3


def test_build_payload_caps_tables_at_200_rows() -> None:
    """Node and edge tables keep at most MAX_TABLE_ROWS rows and flag truncation."""
    doc = _document(node_count=MAX_TABLE_ROWS + 5)
    payload = build_payload(doc)
    assert len(payload["nodes"]) == MAX_TABLE_ROWS
    assert len(payload["edges"]) == MAX_TABLE_ROWS
    assert payload["truncated"] == {"nodes": True, "edges": True}
    assert payload["node_count"] == MAX_TABLE_ROWS + 5


def test_build_dashboard_writes_html_with_links_and_figure(tmp_path: Path) -> None:
    """build_dashboard writes HTML containing the graph name, OKN links, and figure."""
    out = tmp_path / "web" / "dashboard.html"
    result = build_dashboard(_document(), None, out)
    assert result == out
    text = out.read_text(encoding="utf-8")
    assert "Toy Graph" in text
    assert "https://okn.us/" in text
    assert "https://registry.okn.us/" in text
    assert "DAF-OKN Dashboard" in text
    assert "data:image/png;base64," in text


def test_build_dashboard_embeds_only_capped_rows(tmp_path: Path) -> None:
    """Rows beyond the cap are absent from the rendered HTML."""
    doc = _document(node_count=MAX_TABLE_ROWS + 5)
    out = tmp_path / "dashboard.html"
    build_dashboard(doc, None, out)
    text = out.read_text(encoding="utf-8")
    assert ">n0<" in text
    assert "n204" not in text


def test_build_payload_survives_stats_provider_failure(monkeypatch) -> None:
    """A raising graph_stats provider degrades to document-derived fallbacks."""

    def _boom(doc):
        raise RuntimeError("stats provider unavailable")

    monkeypatch.setattr(dashboard_payload, "graph_stats", _boom)
    payload = build_payload(_document())
    assert payload["stats"] == {}
    assert payload["node_count"] == 6
    assert payload["edge_count"] == 5
    assert payload["density"] == pytest.approx(5 / 30)
    assert payload["component_count"] == 1


def test_build_payload_ignores_non_numeric_metric_values() -> None:
    """Bool/string/None metric entries fall back to document-derived values."""
    payload = build_payload(
        _document(),
        metrics={
            "node_count": True,
            "edge_count": "many",
            "density": False,
            "component_count": None,
        },
    )
    assert payload["node_count"] == 6
    assert payload["edge_count"] == 5
    assert payload["density"] == pytest.approx(5 / 30)
    assert payload["component_count"] == 1


def test_build_payload_string_density_falls_back() -> None:
    """A non-numeric density entry falls back to the computed density."""
    payload = build_payload(_document(), metrics={"density": "high"})
    assert payload["density"] == pytest.approx(5 / 30)
    assert payload["stats"]["density"] == "high"


def test_build_payload_single_node_density_is_zero() -> None:
    """A single-node graph has zero directed density."""
    doc = GraphDocument(name="solo", nodes=[NodeRecord(id="a", title="A")], edges=[])
    payload = build_payload(doc, metrics={"node_count": 1, "edge_count": 0})
    assert payload["density"] == 0.0
    assert payload["component_count"] == 1


def test_payload_helpers_boundary_values() -> None:
    """Density is zero below two nodes; empty graphs have zero components."""
    assert dashboard_payload._directed_density(0, 5) == 0.0
    assert dashboard_payload._directed_density(1, 5) == 0.0
    assert dashboard_payload._directed_density(4, 6) == pytest.approx(0.5)
    assert dashboard_payload._weak_component_count(GraphDocument(name="empty")) == 0


def _write_graph(tmp_path: Path) -> Path:
    """Save the toy document as the CLI's graph JSON input."""
    path = tmp_path / "graph.json"
    _document().save_json(path)
    return path


def test_cli_main_builds_dashboard_from_graph_json(tmp_path: Path, capsys) -> None:
    """cli_main renders the dashboard to --out and prints the written path."""
    graph_path = _write_graph(tmp_path)
    out = tmp_path / "web" / "dashboard.html"

    cli_main(["--graph", str(graph_path), "--out", str(out)])

    captured = capsys.readouterr()
    assert out.is_file()
    assert "Toy Graph" in out.read_text(encoding="utf-8")
    assert str(out) in captured.out


def test_cli_main_uses_default_out_when_given(tmp_path: Path) -> None:
    """``default_out`` supplies the output path when --out is omitted."""
    graph_path = _write_graph(tmp_path)
    out = tmp_path / "default" / "dashboard.html"

    cli_main(["--graph", str(graph_path)], default_out=out)

    assert out.is_file()


def test_cli_main_forwards_metrics_json(tmp_path: Path) -> None:
    """--metrics values override computed statistics in the summary table."""
    graph_path = _write_graph(tmp_path)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"node_count": 42, "density": 0.25}), encoding="utf-8")
    out = tmp_path / "dashboard.html"

    cli_main(["--graph", str(graph_path), "--metrics", str(metrics_path), "--out", str(out)])

    text = out.read_text(encoding="utf-8")
    assert "<td>42</td>" in text
    assert "<td>0.2500</td>" in text


def test_cli_main_rejects_non_object_metrics(tmp_path: Path) -> None:
    """A non-object --metrics JSON file is an argument error (exit code 2)."""
    graph_path = _write_graph(tmp_path)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        cli_main(
            [
                "--graph",
                str(graph_path),
                "--metrics",
                str(metrics_path),
                "--out",
                str(tmp_path / "other.html"),
            ]
        )

    assert excinfo.value.code == 2


def test_cli_main_missing_graph_file_raises(tmp_path: Path) -> None:
    """A missing --graph file surfaces the underlying file error."""
    with pytest.raises(FileNotFoundError):
        cli_main(
            [
                "--graph",
                str(tmp_path / "missing.json"),
                "--out",
                str(tmp_path / "dashboard.html"),
            ]
        )
