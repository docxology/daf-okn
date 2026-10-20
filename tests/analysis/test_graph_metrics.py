"""Tests for :mod:`daf_okn.analysis.graph_metrics` and the report pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from daf_okn.analysis.graph_metrics import (
    centrality_scores,
    component_counts,
    compute_metrics,
    degree_sequence,
    edge_centrality_scores,
    in_out_degrees,
    triangle_count,
)
from daf_okn.analysis.pipeline import REPORT_FILENAME, run_analysis
from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord


def _metrics_document() -> GraphDocument:
    """Triangle ``a, b, c`` plus tail ``c → d → e`` and isolated ``f``.

    Directed edges: a→b, b→c, c→a, c→d, d→e (5 edges over 6 nodes).
    """
    return GraphDocument(
        name="metrics-sample",
        nodes=[NodeRecord(node, node.upper(), "uri") for node in "abcdef"],
        edges=[
            EdgeRecord("a", "b"),
            EdgeRecord("b", "c"),
            EdgeRecord("c", "a"),
            EdgeRecord("c", "d"),
            EdgeRecord("d", "e"),
        ],
        metadata={},
    )


# ---------------------------------------------------------------------------
# compute_metrics — exact numbers on the known graph
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    """Pinned summary keys with hand-computed expectations."""

    def test_summary_numbers(self) -> None:
        metrics = compute_metrics(_metrics_document())
        assert metrics["node_count"] == 6
        assert metrics["edge_count"] == 5
        assert metrics["density"] == pytest.approx(5 / 30)
        assert metrics["weakly_connected_components"] == 2  # {a..e} + {f}
        assert metrics["strongly_connected_components"] == 4  # {a,b,c}, {d}, {e}, {f}
        assert metrics["mean_degree"] == pytest.approx(10 / 6)
        assert metrics["triangles"] == 1  # the a-b-c cycle
        assert metrics["top_central_nodes"][0] == ("c", pytest.approx(5 / 20))

    def test_betweenness_ranks_c_first(self) -> None:
        metrics = compute_metrics(_metrics_document())
        betweenness = metrics["betweenness_centrality"]
        assert betweenness["c"] == pytest.approx(5 / 20)
        assert betweenness["b"] == pytest.approx(3 / 20)
        assert betweenness["d"] == pytest.approx(3 / 20)
        assert betweenness["e"] == 0.0
        assert [node for node, _ in metrics["top_central_nodes"]][:3] == ["c", "b", "d"]

    def test_degree_centrality_mapping(self) -> None:
        metrics = compute_metrics(_metrics_document())
        degree_centrality = metrics["degree_centrality"]
        assert degree_centrality["c"] == pytest.approx(3 / 5)
        assert degree_centrality["e"] == pytest.approx(1 / 5)
        assert degree_centrality["f"] == 0.0

    def test_centralities_disabled_ranks_by_degree(self) -> None:
        metrics = compute_metrics(_metrics_document(), centralities=False)
        assert "degree_centrality" not in metrics
        assert "betweenness_centrality" not in metrics
        assert metrics["top_central_nodes"][0] == ("c", pytest.approx(3 / 5))
        for key in (
            "node_count",
            "edge_count",
            "density",
            "weakly_connected_components",
            "strongly_connected_components",
            "mean_degree",
            "triangles",
            "top_central_nodes",
        ):
            assert key in metrics

    def test_top_k_controls_ranking_length(self) -> None:
        metrics = compute_metrics(_metrics_document(), top_k=2)
        assert len(metrics["top_central_nodes"]) == 2

    @pytest.mark.parametrize("top_k", [-1, 1.5, True])
    def test_invalid_ranking_limit_is_rejected(self, top_k) -> None:
        """Invalid limits must not silently slice or truncate the ranking."""
        with pytest.raises(ValueError, match="top_k"):
            compute_metrics(_metrics_document(), top_k=top_k)

    def test_statement_and_projection_counts_are_distinct(self) -> None:
        """Parallel predicates and duplicate provenance do not inflate density."""
        doc = GraphDocument(
            "parallel",
            [NodeRecord("a", "A"), NodeRecord("b", "B")],
            [
                EdgeRecord("a", "b", "p"),
                EdgeRecord("a", "b", "q"),
                EdgeRecord("a", "b", "p", "inferred"),
            ],
        )
        metrics = compute_metrics(doc, centralities=False, top_k=0)
        assert metrics["edge_count"] == 1
        assert metrics["edge_record_count"] == 3
        assert metrics["statement_count"] == 2
        assert metrics["parallel_statement_count"] == 1
        assert metrics["duplicate_statement_count"] == 1
        assert metrics["relation_counts"] == {"p": 2, "q": 1}
        assert metrics["density"] == pytest.approx(0.5)
        assert metrics["top_central_nodes"] == []

    def test_empty_document(self) -> None:
        metrics = compute_metrics(GraphDocument(name="empty"))
        assert metrics["node_count"] == 0
        assert metrics["edge_count"] == 0
        assert metrics["density"] == 0.0
        assert metrics["weakly_connected_components"] == 0
        assert metrics["strongly_connected_components"] == 0
        assert metrics["mean_degree"] == 0.0
        assert metrics["triangles"] == 0
        assert metrics["top_central_nodes"] == []

    def test_centralities_disabled_degenerate_sizes_rank_zero(self) -> None:
        """Without centralities, graphs below two nodes rank every node 0.0."""
        solo = GraphDocument(name="solo", nodes=[NodeRecord("a", "Alpha")], edges=[])
        metrics = compute_metrics(solo, centralities=False)
        assert metrics["node_count"] == 1
        assert metrics["top_central_nodes"] == [("a", 0.0)]
        assert "degree_centrality" not in metrics
        assert "betweenness_centrality" not in metrics

        hollow = compute_metrics(GraphDocument(name="hollow"), centralities=False)
        assert hollow["top_central_nodes"] == []


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    """Degree, component, and triangle helpers against hand-computed values."""

    def test_degree_sequence_sorted_descending(self) -> None:
        assert degree_sequence(_metrics_document().to_networkx()) == [3, 2, 2, 2, 1, 0]

    def test_in_out_degrees_on_directed_projection(self) -> None:
        degrees = in_out_degrees(_metrics_document().to_networkx())
        assert degrees == {
            "a": (1, 1),
            "b": (1, 1),
            "c": (1, 2),
            "d": (1, 1),
            "e": (1, 0),
            "f": (0, 0),
        }

    def test_in_out_degrees_requires_directed_graph(self) -> None:
        with pytest.raises(TypeError, match="directed"):
            in_out_degrees(_metrics_document().to_networkx(directed=False))

    def test_triangle_count_zero_on_path(self) -> None:
        doc = GraphDocument(
            name="path",
            nodes=[NodeRecord(node, node) for node in "abcd"],
            edges=[EdgeRecord("a", "b"), EdgeRecord("b", "c"), EdgeRecord("c", "d")],
        )
        assert triangle_count(doc.to_networkx()) == 0

    def test_triangle_counts_undirected_projection_of_double_edge(self) -> None:
        # a→b and b→a collapse to one undirected edge; the a-b-c cycle counts once.
        doc = GraphDocument(
            name="reciprocal",
            nodes=[NodeRecord(node, node) for node in "abc"],
            edges=[
                EdgeRecord("a", "b"),
                EdgeRecord("b", "a"),
                EdgeRecord("b", "c"),
                EdgeRecord("c", "a"),
            ],
        )
        assert triangle_count(doc.to_networkx()) == 1

    def test_centrality_scores(self) -> None:
        graph = _metrics_document().to_networkx()
        scores = centrality_scores(graph)
        assert set(scores) == {"degree", "betweenness"}
        assert scores["degree"]["c"] == pytest.approx(3 / 5)
        assert scores["betweenness"]["c"] == pytest.approx(5 / 20)
        assert set(centrality_scores(graph, betweenness=False)) == {"degree"}

    def test_edge_centrality_scores(self) -> None:
        scores = edge_centrality_scores(_metrics_document().to_networkx())
        assert ("a", "b") in scores
        assert all(isinstance(score, float) for score in scores.values())
        assert scores[("b", "c")] == pytest.approx(max(scores.values()))
        assert scores[("d", "e")] == pytest.approx(4 / 30)

    def test_component_counts_directed_and_undirected(self) -> None:
        doc = _metrics_document()
        directed = component_counts(doc.to_networkx())
        assert directed == {"weakly": 2, "strongly": 4}
        undirected = component_counts(doc.to_networkx(directed=False))
        assert undirected == {"weakly": 2}
        assert "strongly" not in undirected

    def test_report_written_and_returned(self, tmp_path: Path) -> None:
        doc = _metrics_document()
        report = run_analysis(doc, tmp_path)
        path = tmp_path / REPORT_FILENAME
        assert report["report_path"] == str(path)
        assert path.is_file()
        assert json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(report))
        assert report["stats"]["node_count"] == 6
        assert report["metrics"]["node_count"] == 6

    def test_valid_document_has_no_problems(self, tmp_path: Path) -> None:
        report = run_analysis(_metrics_document(), tmp_path)
        assert report["problems"] == []
        assert set(report) == {
            "graph_name",
            "stats",
            "problems",
            "metrics",
            "report_path",
        }

    def test_invalid_document_reports_problems(self, tmp_path: Path) -> None:
        doc = GraphDocument(
            name="broken",
            nodes=[NodeRecord("a", "A")],
            edges=[EdgeRecord("a", "ghost")],
        )
        report = run_analysis(doc, tmp_path)
        assert report["problems"]
        assert any("missing from nodes" in problem for problem in report["problems"])

    def test_creates_missing_out_dir(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "deep" / "nested"
        report = run_analysis(_metrics_document(), out_dir)
        assert (out_dir / REPORT_FILENAME).is_file()
        assert report["report_path"] == str(out_dir / REPORT_FILENAME)
