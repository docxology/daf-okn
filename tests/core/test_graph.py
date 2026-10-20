"""Tests for :mod:`daf_okn.core.graph` — the pinned graph document model."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from daf_okn.core.graph import (
    EdgeRecord,
    GraphDocument,
    NodeRecord,
    bindings_to_graph,
)

ALICE = "https://okn.example.org/entity/alice"
BOB = "https://okn.example.org/entity/bob"
FOAF_KNOWS = "http://xmlns.com/foaf/0.1/knows"
FOAF_AGE = "http://xmlns.com/foaf/0.1/age"
XSD_INTEGER = "http://www.w3.org/2001/XMLSchema#integer"
INTEGER_LITERAL = '"42"^^<' + XSD_INTEGER + ">"


def _sample_document() -> GraphDocument:
    """Two URI nodes, one literal node, two edges, nested metadata."""
    return GraphDocument(
        name="sample",
        nodes=[
            NodeRecord("a", "Alpha", "uri", {"kind": "agent"}),
            NodeRecord("b", "Beta", "uri"),
            NodeRecord(
                "lit-1",
                "1.5",
                "literal",
                {"datatype": "http://www.w3.org/2001/XMLSchema#decimal"},
            ),
        ],
        edges=[
            EdgeRecord("a", "b", "knows", "explicit"),
            EdgeRecord("b", "lit-1", "hasValue"),
        ],
        metadata={"source": "test", "nested": {"depth": [1, 2, 3]}},
    )


def _sparql_result() -> dict:
    """Two URI objects, one literal object, one exact-duplicate triple."""
    return {
        "head": {"vars": ["s", "p", "o"]},
        "results": {
            "bindings": [
                {
                    "s": {"type": "uri", "value": ALICE},
                    "p": {"type": "uri", "value": FOAF_KNOWS},
                    "o": {"type": "uri", "value": BOB},
                },
                {
                    "s": {"type": "uri", "value": BOB},
                    "p": {"type": "uri", "value": FOAF_AGE},
                    "o": {"type": "literal", "value": "42", "datatype": XSD_INTEGER},
                },
                {
                    "s": {"type": "uri", "value": ALICE},
                    "p": {"type": "uri", "value": FOAF_KNOWS},
                    "o": {"type": "uri", "value": BOB},
                },
            ]
        },
    }


# ---------------------------------------------------------------------------
# Record defaults
# ---------------------------------------------------------------------------


class TestRecordDefaults:
    """Pinned defaults for the two record dataclasses."""

    def test_node_record_defaults(self) -> None:
        record = NodeRecord("x", "X")
        assert record.node_type == "concept"
        assert record.attributes == {}

    def test_node_attribute_dicts_not_shared(self) -> None:
        first, second = NodeRecord("x", "X"), NodeRecord("y", "Y")
        first.attributes["tag"] = "a"
        assert second.attributes == {}

    def test_edge_record_defaults(self) -> None:
        edge = EdgeRecord("a", "b")
        assert edge.relation == "related"
        assert edge.origin == "explicit"


# ---------------------------------------------------------------------------
# to_dict / from_dict roundtrip
# ---------------------------------------------------------------------------


class TestGraphDocumentDict:
    """``to_dict`` / ``from_dict`` structure, defaults, and isolation."""

    def test_to_dict_structure(self) -> None:
        data = _sample_document().to_dict()
        assert set(data) == {"name", "nodes", "edges", "metadata"}
        assert data["name"] == "sample"
        assert data["nodes"][0] == {
            "id": "a",
            "title": "Alpha",
            "node_type": "uri",
            "attributes": {"kind": "agent"},
        }
        assert data["edges"][1] == {
            "source": "b",
            "target": "lit-1",
            "relation": "hasValue",
            "origin": "explicit",
        }
        assert data["metadata"] == {"source": "test", "nested": {"depth": [1, 2, 3]}}

    def test_to_dict_is_deep_copy(self) -> None:
        doc = _sample_document()
        data = doc.to_dict()
        data["metadata"]["source"] = "mutated"
        data["metadata"]["nested"]["depth"].append(99)
        data["nodes"][0]["attributes"]["kind"] = "mutated"
        assert doc.metadata["source"] == "test"
        assert doc.metadata["nested"]["depth"] == [1, 2, 3]
        assert doc.nodes[0].attributes["kind"] == "agent"

    def test_from_dict_roundtrip_equality(self) -> None:
        doc = _sample_document()
        assert GraphDocument.from_dict(doc.to_dict()) == doc

    def test_from_dict_applies_defaults(self) -> None:
        doc = GraphDocument.from_dict(
            {
                "name": "minimal",
                "nodes": [{"id": "a", "title": "A"}],
                "edges": [{"source": "a", "target": "a"}],
            }
        )
        assert doc.nodes[0].node_type == "concept"
        assert doc.nodes[0].attributes == {}
        assert doc.edges[0].relation == "related"
        assert doc.edges[0].origin == "explicit"
        assert doc.metadata == {}

    def test_from_dict_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError, match="must be a dict"):
            GraphDocument.from_dict(["not", "a", "dict"])


# ---------------------------------------------------------------------------
# JSON persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    """``save_json`` / ``load_json`` roundtrip through real files."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        doc = _sample_document()
        path = doc.save_json(tmp_path / "nested" / "doc.json")
        assert path == tmp_path / "nested" / "doc.json"
        assert path.is_file()
        assert GraphDocument.load_json(path) == doc

    def test_save_json_writes_parseable_sorted_json(self, tmp_path: Path) -> None:
        path = _sample_document().save_json(tmp_path / "doc.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "sample"
        assert list(data) == sorted(data)

    def test_load_json_rejects_malformed_file(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(TypeError, match="must be a dict"):
            GraphDocument.load_json(path)


# ---------------------------------------------------------------------------
# networkx projection
# ---------------------------------------------------------------------------


class TestToNetworkx:
    """Node/edge attribute projection for directed and undirected graphs."""

    def test_directed_projection_carries_attributes(self) -> None:
        graph = _sample_document().to_networkx()
        assert isinstance(graph, nx.DiGraph)
        assert set(graph.nodes) == {"a", "b", "lit-1"}
        assert graph.nodes["a"] == {
            "title": "Alpha",
            "node_type": "uri",
            "kind": "agent",
        }
        assert graph.nodes["b"] == {"title": "Beta", "node_type": "uri"}
        assert graph.nodes["lit-1"] == {
            "title": "1.5",
            "node_type": "literal",
            "datatype": "http://www.w3.org/2001/XMLSchema#decimal",
        }
        assert graph["a"]["b"] == {"relation": "knows", "origin": "explicit"}
        assert graph["b"]["lit-1"] == {"relation": "hasValue", "origin": "explicit"}
        assert not graph.has_edge("b", "a"), "projection must preserve direction"

    def test_canonical_fields_win_on_attribute_collision(self) -> None:
        doc = GraphDocument(
            name="collide",
            nodes=[NodeRecord("a", "canonical", "uri", {"title": "sneaky", "node_type": "sneaky"})],
        )
        node = doc.to_networkx().nodes["a"]
        assert node["title"] == "canonical"
        assert node["node_type"] == "uri"

    def test_undirected_projection(self) -> None:
        graph = _sample_document().to_networkx(directed=False)
        assert isinstance(graph, nx.Graph)
        assert graph.has_edge("a", "b")
        assert graph["a"]["b"]["relation"] == "knows"

    def test_dangling_endpoints_materialize_as_bare_nodes(self) -> None:
        doc = GraphDocument(
            name="dangling",
            nodes=[NodeRecord("a", "A")],
            edges=[EdgeRecord("a", "ghost")],
        )
        graph = doc.to_networkx()
        assert "ghost" in graph.nodes
        assert graph.nodes["ghost"] == {}
        assert doc.validate() != [], "dangling endpoints must be flagged by validate"


# ---------------------------------------------------------------------------
# SPARQL JSON results
# ---------------------------------------------------------------------------


class TestBindingsToGraph:
    """``bindings_to_graph`` on the standard SPARQL JSON result shape."""

    def test_distinct_rdf_terms_and_predicate_namespaces_survive(self) -> None:
        """Equal lexical forms do not identify language/datatype/URI terms."""
        objects = [
            {"type": "uri", "value": ALICE},
            {"type": "literal", "value": ALICE},
            {"type": "literal", "value": "same", "xml:lang": "en"},
            {"type": "literal", "value": "same", "xml:lang": "fr"},
            {"type": "literal", "value": "same", "datatype": XSD_INTEGER},
            {"type": "bnode", "value": "same"},
        ]
        result = {
            "head": {"vars": ["s", "p", "o"]},
            "results": {
                "bindings": [
                    {
                        "s": {"type": "uri", "value": BOB},
                        "p": {"type": "uri", "value": predicate},
                        "o": obj,
                    }
                    for obj in objects
                    for predicate in ("https://one.example/p", "https://two.example/p")
                ]
            },
        }
        doc = bindings_to_graph(result, "identity")
        assert len(doc.nodes) == 7
        assert len(doc.edges) == 12
        assert {edge.relation for edge in doc.edges} == {
            "https://one.example/p",
            "https://two.example/p",
        }

    def test_lossless_projection_preserves_parallel_records(self) -> None:
        """The multigraph retains predicate/origin records and direction."""
        doc = _sample_document()
        doc.edges.extend([EdgeRecord("a", "b", "different"), EdgeRecord("a", "b", "knows")])
        graph = doc.to_multidigraph()
        assert isinstance(graph, nx.MultiDiGraph)
        assert graph.number_of_edges() == 4
        assert [data["relation"] for data in graph["a"]["b"].values()] == [
            "knows",
            "different",
            "knows",
        ]
        assert not graph.has_edge("b", "a")

    def test_uri_and_literal_objects(self) -> None:
        doc = bindings_to_graph(_sparql_result(), "okn-sample")
        assert {node.id for node in doc.nodes} == {ALICE, BOB, INTEGER_LITERAL}

        by_id = {node.id: node for node in doc.nodes}
        assert by_id[ALICE].title == "alice"
        assert by_id[ALICE].node_type == "uri"
        assert by_id[BOB].node_type == "uri"
        literal = by_id[INTEGER_LITERAL]
        assert literal.node_type == "literal"
        assert literal.title == "42"
        assert literal.attributes == {"datatype": XSD_INTEGER}

    def test_edges_preserve_full_predicate_iris(self) -> None:
        doc = bindings_to_graph(_sparql_result(), "okn-sample")
        assert len(doc.edges) == 2, "exact duplicate triple must collapse"
        relations = {(edge.source, edge.target, edge.relation) for edge in doc.edges}
        assert (ALICE, BOB, FOAF_KNOWS) in relations
        assert (BOB, INTEGER_LITERAL, FOAF_AGE) in relations
        assert all(edge.origin == "explicit" for edge in doc.edges)

    def test_provenance_metadata(self) -> None:
        doc = bindings_to_graph(_sparql_result(), "okn-sample")
        assert doc.name == "okn-sample"
        assert doc.metadata["source"] == "sparql"
        assert doc.metadata["head_vars"] == ["s", "p", "o"]
        assert doc.metadata["binding_count"] == 3
        assert doc.metadata["skipped_bindings"] == 0

    def test_resulting_document_validates_clean(self) -> None:
        assert bindings_to_graph(_sparql_result(), "okn-sample").validate() == []

    def test_positional_variable_fallback(self) -> None:
        result = _sparql_result()
        result["head"]["vars"] = ["x", "y", "z"]
        result["results"]["bindings"] = [
            {"x": binding["s"], "y": binding["p"], "z": binding["o"]}
            for binding in result["results"]["bindings"]
        ]
        doc = bindings_to_graph(result, "positional")
        assert {(e.source, e.target, e.relation) for e in doc.edges} == {
            (ALICE, BOB, FOAF_KNOWS),
            (BOB, INTEGER_LITERAL, FOAF_AGE),
        }

    def test_unbound_object_skips_binding(self) -> None:
        result = _sparql_result()
        result["results"]["bindings"].append({"s": {"type": "uri", "value": ALICE}})
        doc = bindings_to_graph(result, "partial")
        assert doc.metadata["skipped_bindings"] == 1
        assert doc.metadata["binding_count"] == 4

    def test_fewer_than_three_variables_raises(self) -> None:
        result = {"head": {"vars": ["s", "p"]}, "results": {"bindings": []}}
        with pytest.raises(ValueError, match="three variables"):
            bindings_to_graph(result, "too-few")

    def test_literal_language_without_datatype(self) -> None:
        """A literal with only ``xml:lang`` keeps the language, no datatype."""
        result = {
            "head": {"vars": ["s", "p", "o"]},
            "results": {
                "bindings": [
                    {
                        "s": {"type": "uri", "value": ALICE},
                        "p": {"type": "uri", "value": FOAF_KNOWS},
                        "o": {"type": "literal", "value": "bonjour", "xml:lang": "fr"},
                    }
                ]
            },
        }
        doc = bindings_to_graph(result, "lang")
        literal = next(node for node in doc.nodes if node.id == '"bonjour"@fr')
        assert literal.node_type == "literal"
        assert literal.title == "bonjour"
        assert literal.attributes == {"xml:lang": "fr"}

    def test_bnode_identity_and_missing_type_rejection(self) -> None:
        """Blank-node ids are distinct from IRIs; missing term types are invalid."""
        result = {
            "head": {"vars": ["s", "p", "o"]},
            "results": {
                "bindings": [
                    {
                        "s": {"type": "bnode", "value": "b0"},
                        "p": {"type": "uri", "value": FOAF_KNOWS},
                        "o": {"type": "uri", "value": BOB},
                    }
                ]
            },
        }
        doc = bindings_to_graph(result, "bnode")
        by_id = {node.id: node for node in doc.nodes}
        assert by_id["_:b0"].node_type == "bnode"
        assert by_id["_:b0"].title == "b0"
        result["results"]["bindings"][0]["o"] = {"value": "42", "datatype": XSD_INTEGER}
        with pytest.raises(ValueError, match="type"):
            bindings_to_graph(result, "missing-type")

    @pytest.mark.parametrize(
        "term",
        [
            None,
            {},
            {"type": "literal", "value": 4},
            {"type": [], "value": "x"},
            {"type": "uri", "value": "relative"},
            {"type": "uri", "value": "http://x:bad"},
            {"type": "uri", "value": "http:///a"},
            {"type": "uri", "value": "https://[broken"},
            {"type": "uri", "value": ALICE, "datatype": XSD_INTEGER},
            {"type": "bnode", "value": ""},
            {"type": "bnode", "value": "has space"},
            {"type": "literal", "value": "x", "datatype": "relative"},
            {"type": "literal", "value": "x", "xml:lang": 3},
            {"type": "literal", "value": "x", "xml:lang": "bad space"},
            {"type": "literal", "value": "x", "xml:lang": "en", "datatype": XSD_INTEGER},
            {"type": "typed-literal", "value": "x"},
        ],
    )
    def test_malformed_bound_terms_are_rejected(self, term) -> None:
        """Present malformed terms must fail instead of disappearing as unbound."""
        result = _sparql_result()
        result["results"]["bindings"][0]["o"] = term
        with pytest.raises(ValueError):
            bindings_to_graph(result, "malformed")

    @pytest.mark.parametrize(
        "result",
        [
            None,
            [],
            {},
            {"head": []},
            {"head": {"vars": "spo"}, "results": {"bindings": []}},
            {"head": {"vars": ["s", "p", "o"]}, "results": {"bindings": None}},
            {"head": {"vars": ["s", "s", "o"]}, "results": {"bindings": []}},
            {"head": {"vars": ["s", [], "o"]}, "results": {"bindings": []}},
            {"head": {"vars": ["s", "p", "o"]}, "results": {"bindings": [[]]}},
        ],
    )
    def test_malformed_select_documents_are_rejected(self, result) -> None:
        """Malformed SELECT envelopes and duplicate roles cannot produce a graph."""
        with pytest.raises(ValueError):
            bindings_to_graph(result, "malformed-result")

    @pytest.mark.parametrize("role", ["s", "p"])
    def test_triple_roles_reject_literal_subject_or_predicate(self, role) -> None:
        """RDF subjects and predicates cannot be literal terms."""
        result = _sparql_result()
        result["results"]["bindings"][0][role] = {"type": "literal", "value": "invalid"}
        with pytest.raises(ValueError):
            bindings_to_graph(result, "bad-role")

    def test_partial_role_aliases_do_not_reuse_the_predicate_as_subject(self) -> None:
        """Named roles are reserved before positional roles are assigned."""
        result = {
            "head": {"vars": ["p", "x", "y"]},
            "results": {
                "bindings": [
                    {
                        "p": {"type": "uri", "value": FOAF_KNOWS},
                        "x": {"type": "uri", "value": ALICE},
                        "y": {"type": "uri", "value": BOB},
                    }
                ]
            },
        }
        doc = bindings_to_graph(result, "partial-alias")
        assert doc.edges == [EdgeRecord(ALICE, BOB, FOAF_KNOWS)]

    def test_literal_identity_normalizes_language_case_and_plain_string_datatype(self) -> None:
        """RDF 1.1 language case and simple/xsd:string forms identify the same terms."""
        objects = [
            {"type": "literal", "value": "hello", "xml:lang": language} for language in ("EN", "en")
        ] + [
            {"type": "literal", "value": "hello"},
            {
                "type": "typed-literal",
                "value": "hello",
                "datatype": "http://www.w3.org/2001/XMLSchema#string",
            },
        ]
        result = {
            "head": {"vars": ["s", "p", "o"]},
            "results": {
                "bindings": [
                    {
                        "s": {"type": "uri", "value": ALICE},
                        "p": {"type": "uri", "value": FOAF_KNOWS},
                        "o": obj,
                    }
                    for obj in objects
                ]
            },
        }
        doc = bindings_to_graph(result, "canonical-terms")
        assert {node.id for node in doc.nodes} == {ALICE, '"hello"', '"hello"@en'}
        assert len(doc.edges) == 2
