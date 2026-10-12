"""Tests for :mod:`daf_okn.core.invariants` — graph structural invariants."""

from __future__ import annotations

import pytest

from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord
from daf_okn.core.invariants import graph_stats, validate_graph


def _document(*nodes: NodeRecord, edges: tuple[EdgeRecord, ...] = ()) -> GraphDocument:
    return GraphDocument(name="probe", nodes=list(nodes), edges=list(edges))


def _clean_document() -> GraphDocument:
    return _document(
        NodeRecord("a", "A", "uri"),
        NodeRecord("b", "B", "uri"),
        NodeRecord("c", "C", "uri"),
        edges=(EdgeRecord("a", "b", "knows"), EdgeRecord("b", "c", "knows")),
    )


# ---------------------------------------------------------------------------
# validate_graph
# ---------------------------------------------------------------------------


class TestValidateGraph:
    """Each structural problem class is reported with actionable wording."""

    def test_clean_document_has_no_problems(self) -> None:
        assert validate_graph(_clean_document()) == []

    def test_dangling_target_endpoint(self) -> None:
        doc = _document(
            NodeRecord("a", "A"),
            edges=(EdgeRecord("a", "ghost"),),
        )
        problems = validate_graph(doc)
        assert len(problems) == 1
        assert "ghost" in problems[0]
        assert "target" in problems[0]

    def test_dangling_source_endpoint(self) -> None:
        doc = _document(
            NodeRecord("b", "B"),
            edges=(EdgeRecord("ghost", "b"),),
        )
        problems = validate_graph(doc)
        assert len(problems) == 1
        assert "source" in problems[0]

    def test_duplicate_node_ids(self) -> None:
        doc = _document(
            NodeRecord("a", "first"),
            NodeRecord("a", "second"),
            NodeRecord("a", "third"),
        )
        problems = validate_graph(doc)
        assert len(problems) == 2, "each extra occurrence is reported"
        assert all("duplicate node id" in problem for problem in problems)

    def test_self_loop_flagged(self) -> None:
        doc = _document(NodeRecord("a", "A"), edges=(EdgeRecord("a", "a"),))
        problems = validate_graph(doc)
        assert problems == ["self-loop on node 'a'"]

    def test_empty_node_id(self) -> None:
        doc = _document(NodeRecord("", "nameless"))
        problems = validate_graph(doc)
        assert len(problems) == 1
        assert "empty id" in problems[0]

    def test_unknown_self_loop_reports_all_problem_classes(self) -> None:
        doc = _document(NodeRecord("a", "A"), edges=(EdgeRecord("ghost", "ghost"),))
        problems = validate_graph(doc)
        assert any("self-loop" in problem for problem in problems)
        assert sum("missing from nodes" in problem for problem in problems) == 2

    def test_validate_method_delegates_to_invariants(self) -> None:
        doc = _document(
            NodeRecord("a", "first"),
            NodeRecord("a", "second"),
            edges=(EdgeRecord("a", "missing"),),
        )
        problems = doc.validate()
        assert any("duplicate node id" in problem for problem in problems)
        assert any("missing from nodes" in problem for problem in problems)


# ---------------------------------------------------------------------------
# graph_stats
# ---------------------------------------------------------------------------


class TestGraphStats:
    """Exact summary numbers on small known documents."""

    def test_stats_on_path_graph(self) -> None:
        stats = graph_stats(_clean_document())
        assert stats["node_count"] == 3
        assert stats["edge_count"] == 2
        assert stats["density"] == pytest.approx(2 / 6)
        assert stats["directed"] is True
        assert stats["component_count"] == 1

    def test_stats_on_cycle_counts_density_half(self) -> None:
        doc = _document(
            NodeRecord("a", "A"),
            NodeRecord("b", "B"),
            NodeRecord("c", "C"),
            edges=(
                EdgeRecord("a", "b"),
                EdgeRecord("b", "c"),
                EdgeRecord("c", "a"),
            ),
        )
        stats = graph_stats(doc)
        assert stats["density"] == pytest.approx(3 / 6)
        assert stats["component_count"] == 1

    def test_stats_counts_weakly_connected_components(self) -> None:
        doc = _document(
            NodeRecord("a", "A"),
            NodeRecord("b", "B"),
            NodeRecord("c", "C"),
            NodeRecord("d", "D"),
            edges=(EdgeRecord("a", "b"),),
        )
        stats = graph_stats(doc)
        assert stats["component_count"] == 3

    def test_stats_on_single_node(self) -> None:
        stats = graph_stats(_document(NodeRecord("solo", "S")))
        assert stats == {
            "node_count": 1,
            "edge_count": 0,
            "density": 0.0,
            "directed": True,
            "component_count": 1,
        }

    def test_stats_on_empty_document(self) -> None:
        stats = graph_stats(_document())
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert stats["density"] == 0.0
        assert stats["component_count"] == 0
