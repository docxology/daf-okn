"""Tests for the standard-vocabulary RDF serialization (``daf_okn.core.rdf``)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest
import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS, XSD

from daf_okn.core.cognitive_adapter import DOCUMENT_TYPES, build_cognitive_graph
from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord, bindings_to_graph
from daf_okn.core.rdf import (
    SUPPORTED_FORMATS,
    build_rdf_graph,
    default_namespace_base,
    graph_iri,
    graph_to_rdf,
    graph_to_rdf_diagnostics,
    relation_predicate,
    relation_slug,
    shortname_slug,
    validate_rdf_semantics,
)

# rdflib's own N-Quads / TriG / JSON-LD *parsers* still call deprecated rdflib APIs;
# those warnings come from inside rdflib and are not ours to fix.
rdflib_parser_warnings = pytest.mark.filterwarnings("ignore::DeprecationWarning:rdflib")

SCHEMA = rdflib.Namespace("https://schema.org/")
BASE = "https://purl.org/okn/frink/kg/demo/"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "cognitive"


def _doc() -> GraphDocument:
    return GraphDocument(
        name="demo",
        nodes=[
            NodeRecord(
                id="maths/free_energy",
                title="Free Energy",
                attributes={
                    "description": "A bound on surprise.",
                    "aliases": ["FE", "variational free energy"],
                    "created": "2024-01-02",
                    "updated": "2025-03-04",
                    "tags": ["inference", "maths"],
                    "authors": ["A. Author"],
                    "year": 2022,
                    "wikidata": "Q42",
                    "status": "stable",
                    "weight": 3,
                    "nested": {"ignored": True},
                    7: "non-string key is skipped",
                },
            ),
            NodeRecord(id="maths/blanket", title="Markov Blanket"),
            NodeRecord(
                id="citations/paper",
                title="Paper",
                node_type="citation",
                attributes={"doi": "10.1000/xyz 1"},
            ),
            NodeRecord(id="README", title="Readme", node_type="overview"),
            NodeRecord(id="old", title="Old", node_type="redirect"),
            NodeRecord(id="http://example.org/ext", title="External", node_type="uri"),
            NodeRecord(
                id="a label", title="a label", node_type="literal", attributes={"xml:lang": "en"}
            ),
        ],
        edges=[
            EdgeRecord("maths/free_energy", "maths/blanket", "relates_to"),
            EdgeRecord("maths/free_energy", "maths/blanket", "implements"),
            EdgeRecord("maths/free_energy", "README", "part_of"),
            EdgeRecord("README", "maths/free_energy", "organizes"),
            EdgeRecord("maths/blanket", "maths/free_energy", "related", origin="wikilink"),
            EdgeRecord("old", "maths/free_energy", "redirects_to", origin="redirect"),
            EdgeRecord("maths/free_energy", "http://example.org/ext", "Connects-To"),
            EdgeRecord("maths/free_energy", "a label", "label"),
        ],
        metadata={},
    )


def _graph() -> rdflib.Graph:
    return build_rdf_graph(
        _doc(),
        namespace_base=BASE,
        entry={
            "title": "Demo",
            "description": "A demo.",
            "license": "https://example.org/licence",
            "homepage": "https://example.org/",
            "source": "https://example.org/src",
        },
    )


def _page(node_id: str) -> URIRef:
    return URIRef(f"{BASE}page/{node_id}")


def _concept(node_id: str) -> URIRef:
    return URIRef(f"{BASE}concept/{node_id}")


def test_namespace_defaults_follow_frink_convention() -> None:
    assert default_namespace_base("My Graph!") == "https://purl.org/okn/frink/kg/my-graph/"
    assert str(graph_iri(BASE)) == "https://purl.org/okn/frink/kg/demo"
    assert shortname_slug("   ") == "graph"
    assert relation_slug("Foundation For") == "foundation_for"
    assert relation_slug("--") == "relates"


def test_nodes_use_standard_types_and_labels() -> None:
    graph = _graph()
    fe = _page("maths/free_energy")
    assert (fe, RDF.type, SCHEMA.CreativeWork) in graph
    assert (fe, RDF.type, SKOS.Concept) not in graph
    topic = _concept("maths/free_energy")
    assert (topic, RDF.type, SKOS.Concept) in graph
    assert (topic, RDF.type, SCHEMA.CreativeWork) not in graph
    assert (fe, SCHEMA.about, topic) in graph
    assert (fe, DCTERMS.subject, topic) in graph
    assert (topic, SKOS.inScheme, URIRef(BASE + "scheme")) in graph
    assert (topic, SKOS.prefLabel, Literal("Free Energy")) in graph
    assert (fe, DCTERMS.title, Literal("Free Energy")) in graph
    # Navigation pages are collection pages, not concepts; redirects are neither.
    readme = _page("README")
    assert (readme, RDF.type, SCHEMA.CollectionPage) in graph
    assert (readme, RDF.type, SKOS.Concept) not in graph
    old = _page("old")
    assert (old, RDF.type, SCHEMA.CreativeWork) in graph
    assert (old, RDF.type, SKOS.Concept) not in graph
    # No daf-okn-specific Node class and no legacy namespace anywhere.
    text = graph.serialize(format="nt")
    assert "purl.org/okn/daf-okn" not in text
    assert f"{BASE}Node" not in text


def test_node_fields_map_to_dcterms_skos_and_schema() -> None:
    graph = _graph()
    fe = _page("maths/free_energy")
    assert (fe, DCTERMS.description, Literal("A bound on surprise.")) in graph
    assert {str(o) for o in graph.objects(_concept("maths/free_energy"), SKOS.altLabel)} == {
        "FE",
        "variational free energy",
    }
    assert (fe, DCTERMS.created, Literal("2024-01-02", datatype=XSD.date)) in graph
    assert (fe, DCTERMS.modified, Literal("2025-03-04", datatype=XSD.date)) in graph
    assert set(graph.objects(fe, SCHEMA.keywords)) == {
        URIRef(BASE + "keyword/" + tag) for tag in ("inference", "maths")
    }
    assert (fe, SCHEMA.author, Literal("A. Author")) in graph
    assert (fe, SCHEMA.datePublished, Literal("2022", datatype=XSD.gYear)) in graph
    assert (
        _page("citations/paper"),
        SCHEMA.sameAs,
        URIRef("https://doi.org/10.1000/xyz%201"),
    ) in graph
    assert (fe, RDFS.seeAlso, URIRef("http://www.wikidata.org/entity/Q42")) in graph
    assert not list(graph.triples((fe, SKOS.closeMatch, None)))
    assert not list(graph.triples((fe, SKOS.exactMatch, None)))


def test_unmapped_attributes_live_under_vocab() -> None:
    graph = _graph()
    fe = _page("maths/free_energy")
    vocab = f"{BASE}vocab/"
    assert (fe, URIRef(vocab + "status"), Literal("stable")) in graph
    assert (fe, URIRef(vocab + "weight"), Literal(3)) in graph
    assert (fe, URIRef(vocab + "pageType"), Literal("concept")) in graph
    vocab_predicates = {str(p) for _, p, _ in graph if str(p).startswith(vocab)}
    assert vocab_predicates == {vocab + name for name in ("status", "weight", "pageType")}
    assert not any("nested" in str(p) or "ignored" in str(p) for _, p, _ in graph)
    # Every vocab term used is declared.
    for predicate in vocab_predicates:
        assert (URIRef(predicate), RDF.type, RDF.Property) in graph
        assert (URIRef(predicate), RDFS.label, None) in graph


def test_reviewed_mapping_has_reified_source_evidence() -> None:
    mapping = {
        "target": "http://purl.obolibrary.org/obo/CHEBI_17650",
        "relation": "exactMatch",
        "evidence": "https://www.ebi.ac.uk/chebi/CHEBI:17650",
        "rationale": "Both denote the cortisol substance.",
        "reviewed_on": "2026-10-20",
    }
    doc = GraphDocument(
        name="demo",
        nodes=[
            NodeRecord(id="cortisol", title="Cortisol", attributes={"external_mappings": [mapping]})
        ],
    )
    graph = build_rdf_graph(doc, namespace_base=BASE)
    page, target = _concept("cortisol"), URIRef(mapping["target"])
    assert (page, SKOS.exactMatch, target) in graph
    statement = next(graph.subjects(RDF.subject, page))
    assert (statement, RDF.predicate, SKOS.exactMatch) in graph
    assert (statement, RDF.object, target) in graph
    assert (statement, DCTERMS.source, URIRef(mapping["evidence"])) in graph
    assert (statement, DCTERMS.date, Literal("2026-10-20", datatype=XSD.date)) in graph
    assert not list(graph.triples((page, URIRef(BASE + "vocab/external_mappings"), None)))
    doc.nodes[0].node_type = "index"
    with pytest.raises(ValueError, match="non-concept"):
        build_rdf_graph(doc)


def test_multiple_reviewed_targets_stay_on_the_local_topic():
    records = [
        {
            "target": "https://example.org/term/" + name,
            "relation": "exactMatch",
            "evidence": "https://example.org/definition/" + name,
            "rationale": "Reviewed the local definition against target " + name,
            "reviewed_on": "2026-10-23",
        }
        for name in ("one", "two")
    ]
    graph = build_rdf_graph(
        GraphDocument(
            "demo",
            nodes=[
                NodeRecord(
                    "topic",
                    "Topic",
                    attributes={"external_mappings": records},
                )
            ],
        ),
        namespace_base=BASE,
    )
    topic = _concept("topic")
    assert set(graph.objects(topic, SKOS.exactMatch)) == {URIRef(r["target"]) for r in records}
    assert not list(graph.objects(_page("topic"), SKOS.exactMatch))
    statements = list(graph.subjects(RDF.subject, topic))
    assert len(statements) == 2
    assert {str(o) for s in statements for o in graph.objects(s, DCTERMS.source)} == {
        r["evidence"] for r in records
    }
    assert validate_rdf_semantics(graph, BASE) == []


def test_keyword_iris_are_declared_and_preserve_exact_source_tag() -> None:
    doc = GraphDocument(
        name="demo",
        nodes=[
            NodeRecord(id="a", title="A", attributes={"tags": ["model/fitting", "Café", "a b"]})
        ],
    )
    graph = build_rdf_graph(doc, namespace_base=BASE)
    for keyword in graph.objects(_page("a"), SCHEMA.keywords):
        assert isinstance(keyword, URIRef)
        assert (keyword, RDF.type, SKOS.Concept) in graph
        assert (keyword, RDF.type, SCHEMA.DefinedTerm) in graph
        assert (keyword, SKOS.notation, None) in graph
    assert (
        URIRef(BASE + "keyword/model%2Ffitting"),
        SKOS.notation,
        Literal("model/fitting"),
    ) in graph


def test_citation_predicates_preserve_direction() -> None:
    assert relation_predicate("cited by", BASE) == URIRef("http://purl.org/ontology/bibo/citedBy")
    assert relation_predicate("cites", BASE) == URIRef("http://purl.org/ontology/bibo/cites")
    assert relation_predicate("sio:SIO_000233", BASE) == URIRef(
        "http://semanticscience.org/resource/SIO_000233"
    )


def test_reviewed_keyword_terms_are_reused_directly() -> None:
    doc = GraphDocument(
        name="demo",
        nodes=[
            NodeRecord(
                id="a", title="A", attributes={"tags": ["model_fitting", "computational_modeling"]}
            )
        ],
    )
    graph = build_rdf_graph(doc, namespace_base=BASE)
    assert set(graph.objects(_page("a"), SCHEMA.keywords)) == {
        URIRef("http://purl.obolibrary.org/obo/STATO_0000218"),
        URIRef("http://purl.obolibrary.org/obo/NCIT_C16461"),
    }
    assert not any(str(s).startswith(BASE + "keyword/") for s in graph.subjects())


def test_keyword_reuse_preserves_exact_source_spellings():
    doc = GraphDocument(
        "demo",
        nodes=[
            NodeRecord(
                "topic",
                "Topic",
                attributes={
                    "tags": ["emotion", "genetics", "mathematics", " emotion ", "Emotion"],
                },
            )
        ],
    )
    graph = build_rdf_graph(doc, namespace_base=BASE)
    assert set(graph.objects(_page("topic"), SCHEMA.keywords)) == {
        URIRef("http://purl.obolibrary.org/obo/NCIT_C54266"),
        URIRef("http://purl.obolibrary.org/obo/NCIT_C16624"),
        URIRef("http://purl.obolibrary.org/obo/NCIT_C16825"),
        URIRef(BASE + "keyword/%20emotion%20"),
        URIRef(BASE + "keyword/Emotion"),
    }
    assert (URIRef(BASE + "keyword/%20emotion%20"), SKOS.notation, Literal(" emotion ")) in graph


def test_markdown_adapter_preserves_mapping_evidence_and_concept_scope(tmp_path: Path) -> None:
    (tmp_path / "cortisol.md").write_text(
        "---\ntitle: Cortisol\ndefinition: The cortisol chemical substance.\n"
        "scope_note: Excludes the HPA system.\nexternal_mappings:\n"
        "  - target: http://purl.obolibrary.org/obo/CHEBI_17650\n"
        "    relation: exactMatch\n"
        "    evidence: https://www.ebi.ac.uk/chebi/CHEBI:17650\n"
        "    rationale: Both denote the same chemical substance.\n"
        "    reviewed_on: 2026-10-20\n---\n"
    )
    document = build_cognitive_graph(tmp_path)
    assert document.nodes[1].attributes["external_mappings"][0]["reviewed_on"] == "2026-10-20"
    graph = build_rdf_graph(document, namespace_base=BASE)
    assert (
        _concept("cortisol"),
        SKOS.exactMatch,
        URIRef("http://purl.obolibrary.org/obo/CHEBI_17650"),
    ) in graph
    assert (_concept("cortisol"), SKOS.scopeNote, Literal("Excludes the HPA system.")) in graph


def test_invalid_wikidata_id_falls_back_to_vocab() -> None:
    doc = GraphDocument(
        name="demo",
        nodes=[NodeRecord(id="p", title="P", attributes={"wikidata": "not-a-qid"})],
    )
    graph = build_rdf_graph(doc, namespace_base=BASE)
    assert not list(graph.triples((None, SKOS.closeMatch, None)))
    assert (_page("p"), URIRef(BASE + "vocab/wikidata"), Literal("not-a-qid")) in graph


def test_relations_map_to_standard_terms_or_declared_subproperties() -> None:
    graph = _graph()
    fe, blanket, readme = (_page(x) for x in ("maths/free_energy", "maths/blanket", "README"))
    assert (_concept("maths/free_energy"), SKOS.related, _concept("maths/blanket")) in graph
    assert (fe, DCTERMS.isPartOf, readme) in graph
    assert (readme, DCTERMS.hasPart, fe) in graph
    assert (blanket, DCTERMS.references, fe) in graph  # wikilink origin
    assert (_page("old"), DCTERMS.isReplacedBy, fe) in graph
    implements = URIRef(BASE + "relation/implements")
    connects = URIRef(BASE + "relation/document/connects_to")
    assert (_concept("maths/free_energy"), implements, _concept("maths/blanket")) in graph
    assert (fe, connects, URIRef("http://example.org/ext")) in graph
    for term in (implements, connects, URIRef(BASE + "relation/document/label")):
        assert ((term, RDFS.subPropertyOf, SKOS.semanticRelation) in graph) == (term == implements)
        assert (term, RDF.type, RDF.Property) in graph
        assert any(graph.objects(term, RDFS.label))
    # Standard terms are never redeclared as custom relations.
    assert not list(graph.triples((URIRef(BASE + "relation/relates_to"), None, None)))


def test_relation_predicate_accepts_prefixed_and_absolute_names() -> None:
    assert relation_predicate("skos:broader", BASE) == SKOS.broader
    assert relation_predicate("dcterms:isPartOf", BASE) == DCTERMS.isPartOf
    assert relation_predicate("http://example.org/p", BASE) == URIRef("http://example.org/p")
    assert relation_predicate("Foundation For", BASE) == URIRef(BASE + "relation/foundation_for")
    assert relation_predicate("related_to", BASE) == SKOS.related
    # An unknown prefix is just a name.
    assert relation_predicate("zzz:thing", BASE) == URIRef(BASE + "relation/zzz_thing")


def test_external_iris_are_kept_and_literal_nodes_become_literals() -> None:
    graph = _graph()
    external = URIRef("http://example.org/ext")
    assert (external, RDFS.label, Literal("External")) in graph
    assert (external, RDF.type, SCHEMA.CreativeWork) not in graph
    assert (
        _page("maths/free_energy"),
        URIRef(BASE + "relation/document/label"),
        Literal("a label", lang="en"),
    ) in graph
    assert not list(graph.triples((_page("a label"), None, None)))


def test_dataset_domains_and_provenance_are_described() -> None:
    graph = _graph()
    dataset = URIRef(BASE + "dataset")
    assert (dataset, RDF.type, rdflib.URIRef("http://www.w3.org/ns/dcat#Dataset")) in graph
    assert (dataset, DCTERMS.title, Literal("Demo")) in graph
    assert (dataset, DCTERMS.license, URIRef("https://example.org/licence")) in graph
    assert (dataset, DCTERMS.modified, Literal("2025-03-04", datatype=XSD.date)) in graph
    assert (
        dataset,
        rdflib.URIRef("http://www.w3.org/ns/prov#wasDerivedFrom"),
        URIRef("https://example.org/src"),
    ) in graph
    assert (URIRef(BASE + "scheme"), RDF.type, SKOS.ConceptScheme) in graph
    maths = URIRef(BASE + "domain/maths")
    assert (maths, RDF.type, SKOS.Collection) in graph
    assert (maths, SKOS.member, _concept("maths/free_energy")) in graph


def test_language_tag_applies_to_human_readable_literals() -> None:
    graph = build_rdf_graph(_doc(), namespace_base=BASE, language="en")
    fe = _page("maths/free_energy")
    assert (
        _concept("maths/free_energy"),
        SKOS.prefLabel,
        Literal("Free Energy", lang="en"),
    ) in graph
    keyword = URIRef(BASE + "keyword/maths")
    assert (fe, SCHEMA.keywords, keyword) in graph
    assert (keyword, SKOS.prefLabel, Literal("maths", lang="en")) in graph


@rdflib_parser_warnings
def test_nquads_round_trip_uses_named_graph_from_base(tmp_path: Path) -> None:
    path = graph_to_rdf(_doc(), tmp_path / "g.nq", fmt="nq", namespace_base=BASE)
    dataset = rdflib.Dataset()
    dataset.parse(path, format="nquads")
    named = dataset.graph(URIRef("https://purl.org/okn/frink/kg/demo"))
    assert len(named) == len(build_rdf_graph(_doc(), namespace_base=BASE))
    assert (_concept("maths/free_energy"), RDF.type, SKOS.Concept) in named
    assert {str(g.identifier) for g in dataset.graphs() if len(g)} == {
        "https://purl.org/okn/frink/kg/demo"
    }


@rdflib_parser_warnings
def test_default_base_comes_from_graph_name(tmp_path: Path) -> None:
    doc = GraphDocument(name="My Graph", nodes=[NodeRecord(id="a", title="A")])
    path = graph_to_rdf(doc, tmp_path / "g.nq")
    text = path.read_text(encoding="utf-8")
    assert "<https://purl.org/okn/frink/kg/my-graph/page/a>" in text
    assert text.splitlines()[0].endswith(" <https://purl.org/okn/frink/kg/my-graph> .")


@pytest.mark.parametrize("fmt", sorted(SUPPORTED_FORMATS))
@rdflib_parser_warnings
def test_every_format_round_trips_to_the_same_triples(fmt: str, tmp_path: Path) -> None:
    expected = set(build_rdf_graph(_doc(), namespace_base=BASE))
    path = graph_to_rdf(_doc(), tmp_path / f"g.{fmt}", fmt=fmt, namespace_base=BASE)
    if fmt in {"nq", "trig"}:
        dataset = rdflib.Dataset()
        dataset.parse(path, format=SUPPORTED_FORMATS[fmt])
        parsed = set(dataset.graph(graph_iri(BASE)))
    else:
        parsed_graph = rdflib.Graph()
        parsed_graph.parse(path, format=SUPPORTED_FORMATS[fmt])
        parsed = set(parsed_graph)
    assert parsed == expected


@rdflib_parser_warnings
def test_unnamed_graph_option_writes_plain_triples(tmp_path: Path) -> None:
    nq = graph_to_rdf(_doc(), tmp_path / "g.nq", fmt="nq", namespace_base=BASE, named_graph=False)
    assert "<https://purl.org/okn/frink/kg/demo> ." not in nq.read_text()
    dataset = rdflib.Dataset()
    dataset.parse(nq, format="nquads")
    assert len(dataset) == len(build_rdf_graph(_doc(), namespace_base=BASE))
    trig = graph_to_rdf(
        _doc(), tmp_path / "g.trig", fmt="trig", namespace_base=BASE, named_graph=False
    )
    assert "{" not in trig.read_text()
    default_only = rdflib.Dataset()
    default_only.parse(trig, format="trig")
    assert len(default_only) == len(build_rdf_graph(_doc(), namespace_base=BASE))


def test_serialization_is_deterministic_and_order_independent(tmp_path: Path) -> None:
    forward = _doc()
    reverse = _doc()
    reverse.nodes.reverse()
    reverse.edges.reverse()
    for fmt in ("nq", "nt", "ttl"):
        first = graph_to_rdf(forward, tmp_path / f"a.{fmt}", fmt=fmt, namespace_base=BASE)
        again = graph_to_rdf(forward, tmp_path / f"b.{fmt}", fmt=fmt, namespace_base=BASE)
        shuffled = graph_to_rdf(reverse, tmp_path / f"c.{fmt}", fmt=fmt, namespace_base=BASE)
        assert first.read_bytes() == again.read_bytes()
        assert first.read_bytes() == shuffled.read_bytes()


def test_ntriples_lines_are_sorted_and_escape_special_characters(tmp_path: Path) -> None:
    doc = GraphDocument(
        name="demo",
        nodes=[
            NodeRecord(id="b", title='Quote " and \\ backslash\nnewline\ttab \x01 é'),
            NodeRecord(id="a", title="A"),
        ],
    )
    path = graph_to_rdf(doc, tmp_path / "g.nt", fmt="nt", namespace_base=BASE)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == sorted(lines)
    text = "\n".join(lines)
    assert (
        '\\"' in text and "\\\\" in text and "\\n" in text and "\\t" in text and "\\u0001" in text
    )
    reparsed = rdflib.Graph()
    reparsed.parse(path, format="nt")
    assert (
        _page("b"),
        DCTERMS.title,
        Literal('Quote " and \\ backslash\nnewline\ttab \x01 é'),
    ) in reparsed


def test_unsupported_format_is_rejected_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported RDF format"):
        graph_to_rdf(_doc(), tmp_path / "g.xyz", fmt="xyz")
    assert not (tmp_path / "g.xyz").exists()


@pytest.mark.parametrize("endpoint", ["source", "target"])
@rdflib_parser_warnings
def test_diagnostic_rdf_preserves_dangling_edges_and_strict_rejection(
    tmp_path: Path, endpoint: str
) -> None:
    """Diagnostic serialization returns actual errors; strict APIs retain their refusal."""
    doc = GraphDocument(name="demo", nodes=[NodeRecord("known", "Known")])
    source, target = ("missing", "known") if endpoint == "source" else ("known", "missing")
    doc.edges.append(EdgeRecord(source, target, "connects_to"))
    original = doc.to_dict()
    strict_path = tmp_path / "strict.nq"
    strict_path.write_text("preserve")
    with pytest.raises(ValueError, match="page requires CreativeWork type: .*page/missing"):
        build_rdf_graph(doc)
    with pytest.raises(ValueError, match="page requires CreativeWork type: .*page/missing"):
        graph_to_rdf(doc, strict_path)
    assert strict_path.read_text() == "preserve"

    diagnostic_path = tmp_path / "diagnostic.nq"
    problems = graph_to_rdf_diagnostics(doc, diagnostic_path)

    dataset = rdflib.Dataset()
    dataset.parse(diagnostic_path, format="nquads")
    graph = dataset.graph(graph_iri(BASE))
    assert (_page(source), URIRef(BASE + "relation/document/connects_to"), _page(target)) in graph
    assert not list(graph.triples((_page("missing"), RDF.type, None)))
    assert problems == validate_rdf_semantics(graph, BASE)
    assert f"page requires CreativeWork type: {_page('missing')}" in problems
    assert doc.to_dict() == original


@pytest.mark.parametrize("fmt", sorted(SUPPORTED_FORMATS))
def test_diagnostic_rdf_matches_strict_serialization_for_valid_graph(
    tmp_path: Path, fmt: str
) -> None:
    """Valid nearby data has identical triples and bytes under both APIs."""
    strict = graph_to_rdf(_doc(), tmp_path / f"strict.{fmt}", fmt=fmt)
    diagnostic = tmp_path / f"diagnostic.{fmt}"
    assert graph_to_rdf_diagnostics(_doc(), diagnostic, fmt=fmt) == []
    assert diagnostic.read_bytes() == strict.read_bytes()


def test_diagnostic_rdf_rejects_unsupported_format_before_writes(tmp_path: Path) -> None:
    """The diagnostic API cannot suppress construction/serialization failures."""
    path = tmp_path / "new" / "graph.xyz"
    with pytest.raises(ValueError, match="Unsupported RDF format: 'xyz'"):
        graph_to_rdf_diagnostics(_doc(), path, fmt="xyz")
    assert not path.parent.exists()


@pytest.mark.parametrize(
    "fault", ["mapping_without_review", "external_mapping", "bad_iri", "bad_namespace"]
)
def test_generic_export_rejects_inconsistent_rdf_before_writes(tmp_path, fault):
    doc = GraphDocument(
        name="demo", nodes=[NodeRecord("page", "Page"), NodeRecord("target", "Target")]
    )
    base = BASE
    if fault == "mapping_without_review":
        doc.edges.append(EdgeRecord("page", "target", str(SKOS.exactMatch)))
    elif fault == "external_mapping":
        doc.nodes[0] = NodeRecord(
            "https://example.org/external",
            "External",
            node_type="uri",
            attributes={
                "external_mappings": [
                    {
                        "target": "https://example.org/target",
                        "relation": "closeMatch",
                        "evidence": "https://example.org/evidence",
                        "rationale": "Compared definitions.",
                        "reviewed_on": "2026-10-20",
                    }
                ]
            },
        )
    elif fault == "bad_iri":
        doc.nodes[0] = NodeRecord("https://example.org:bad/page", "Bad IRI", node_type="uri")
    else:
        base = "https://example.org:65536/"
    path = tmp_path / "rejected.nq"
    with pytest.raises(ValueError):
        graph_to_rdf(doc, path, namespace_base=base)
    assert not path.exists()


def test_sparql_graph_export_retains_literal_values_blank_nodes_and_predicate_iris(tmp_path):
    predicate = "https://example.org/predicate"
    payload = {
        "head": {"vars": ["s", "p", "o"]},
        "results": {
            "bindings": [
                {
                    "s": {"type": "bnode", "value": "subject"},
                    "p": {"type": "uri", "value": predicate},
                    "o": {"type": "literal", "value": "01", "datatype": str(XSD.integer)},
                },
                {
                    "s": {"type": "uri", "value": "https://example.org/subject"},
                    "p": {"type": "uri", "value": predicate},
                    "o": {"type": "literal", "value": 'quoted "label"', "xml:lang": "en"},
                },
            ]
        },
    }
    doc = bindings_to_graph(payload, "sparql")
    graph = build_rdf_graph(doc)
    assert (
        rdflib.BNode("subject"),
        URIRef(predicate),
        Literal("01", datatype=XSD.integer, normalize=False),
    ) in graph
    assert (
        URIRef("https://example.org/subject"),
        URIRef(predicate),
        Literal('quoted "label"', lang="en"),
    ) in graph
    path = graph_to_rdf(doc, tmp_path / "sparql.nq")
    assert '"01"^^<' in path.read_text()


def test_cognitive_fixture_vault_exports_expected_shapes(tmp_path: Path) -> None:
    """The adapter's real output serializes with the cognitive exporter's vocabulary."""
    doc = build_cognitive_graph(FIXTURE_ROOT, collapse_redirects=False)
    base = default_namespace_base(doc.name)
    graph = build_rdf_graph(doc, namespace_base=base)
    markov = URIRef(base + "concept/mathematics/markov_blanket")
    assert base == "https://purl.org/okn/frink/kg/cognitive-kb/"
    assert (markov, RDF.type, SKOS.Concept) in graph
    assert (markov, SKOS.prefLabel, Literal("Markov Blanket")) in graph
    assert (URIRef(base + "domain/mathematics"), SKOS.member, markov) in graph
    assert any(graph.triples((None, DCTERMS.references, None)))
    assert any(graph.triples((None, DCTERMS.isReplacedBy, None)))  # kept redirect edge
    # Every relation term outside the standard set is a declared sub-property.
    custom = {p for _, p, _ in graph if str(p).startswith(base + "relation/")}
    assert custom
    for term in custom:
        scope = (
            SKOS.Concept
            if not str(term).startswith(base + "relation/document/")
            else SCHEMA.CreativeWork
        )
        assert (term, RDFS.domain, scope) in graph
        assert (term, RDFS.range, scope) in graph


@pytest.mark.parametrize(
    "fault",
    [
        "dual_type",
        "page_concept",
        "page_mapping",
        "page_relation",
        "missing_about",
        "missing_subject",
        "wrong_subject",
        "concept_source",
        "concept_citation",
        "undeclared_topic",
        "document_keyword",
        "concept_label_on_page",
        "missing_scope",
        "document_skos_scope",
        "document_containment_on_topic",
        "document_domain_member",
        "indirect_document_skos_scope",
        "empty_meaning",
        "missing_concept_superproperty",
    ],
)
def test_entity_model_rejects_conflation_and_wrong_scopes(fault):
    graph = _graph()
    page, topic, other = (
        _page("maths/free_energy"),
        _concept("maths/free_energy"),
        _concept("maths/blanket"),
    )
    if fault == "dual_type":
        graph.add((topic, RDF.type, SCHEMA.CreativeWork))
    elif fault == "page_concept":
        graph.add((page, RDF.type, SKOS.Concept))
    elif fault == "page_mapping":
        graph.add((page, SKOS.exactMatch, URIRef("https://example.org/topic")))
    elif fault == "page_relation":
        graph.add((page, SKOS.related, other))
    elif fault == "missing_about":
        graph.remove((page, SCHEMA.about, topic))
    elif fault == "missing_subject":
        graph.remove((page, DCTERMS.subject, topic))
    elif fault == "wrong_subject":
        graph.set((page, DCTERMS.subject, other))
    elif fault == "concept_source":
        graph.add((topic, DCTERMS.source, URIRef("https://example.org/page")))
    elif fault == "concept_citation":
        graph.add((topic, URIRef("http://purl.org/ontology/bibo/cites"), _page("citations/paper")))
    elif fault == "undeclared_topic":
        graph.remove((other, RDF.type, SKOS.Concept))
    elif fault == "document_keyword":
        graph.add((page, SCHEMA.keywords, _page("README")))
    elif fault == "concept_label_on_page":
        graph.add((page, SKOS.prefLabel, Literal("Conflated label")))
    elif fault == "missing_scope":
        graph.remove((URIRef(BASE + "relation/implements"), RDFS.domain, None))
    elif fault == "document_containment_on_topic":
        graph.add((topic, DCTERMS.isPartOf, _page("README")))
    elif fault == "document_domain_member":
        graph.add((URIRef(BASE + "domain/maths"), SKOS.member, page))
    elif fault == "indirect_document_skos_scope":
        bridge = URIRef(BASE + "bridge")
        graph.add((URIRef(BASE + "relation/document/connects_to"), RDFS.subPropertyOf, bridge))
        graph.add((bridge, RDFS.subPropertyOf, SKOS.semanticRelation))
    elif fault == "empty_meaning":
        graph.set((URIRef(BASE + "relation/implements"), RDFS.comment, Literal("  ")))
    elif fault == "missing_concept_superproperty":
        graph.remove((URIRef(BASE + "relation/implements"), RDFS.subPropertyOf, None))
    else:
        graph.add(
            (
                URIRef(BASE + "relation/document/connects_to"),
                RDFS.subPropertyOf,
                SKOS.semanticRelation,
            )
        )
    assert validate_rdf_semantics(graph, BASE), fault


def test_distinct_documents_topics_citations_and_navigation_are_accepted(tmp_path):
    pages = {
        "topic.md": (
            "---\ntype: concept\ntitle: Topic\nsource: https://example.org/topic\n"
            "tags: [unreviewed_exact_tag]\nsemantic_relations:\n- type: foundation_for\n"
            "  links: ['[[other]]']\n- type: cites\n  links: ['[[citations/paper]]']\n"
            "---\nBody bytes stay here.\n"
        ),
        "other.md": "---\ntype: mathematical_concept\n---\n",
        "README.md": (
            "---\ntype: overview\nsemantic_relations:\n- type: implements\n"
            "  links: ['[[topic]]']\n---\n[[topic]]\n"
        ),
        "citations/paper.md": "---\ntype: citation\ndoi: 10.1000/example\n---\n",
    }
    for name, body in pages.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    document = build_cognitive_graph(tmp_path)
    graph = build_rdf_graph(document, namespace_base=BASE)
    assert validate_rdf_semantics(graph, BASE) == []
    assert (_concept("topic"), URIRef(BASE + "relation/foundation_for"), _concept("other")) in graph
    assert (
        _page("topic"),
        URIRef("http://purl.org/ontology/bibo/cites"),
        _page("citations/paper"),
    ) in graph
    assert (_page("README"), URIRef(BASE + "relation/document/implements"), _page("topic")) in graph
    assert not list(graph.triples((_concept("citations/paper"), None, None)))
    assert (_page("topic"), DCTERMS.source, URIRef("https://example.org/topic")) in graph
    assert not list(graph.triples((_concept("topic"), DCTERMS.source, None)))
    for name, body in pages.items():
        assert (tmp_path / name).read_bytes() == body.encode()


@pytest.mark.parametrize("base", [BASE, "https://example.org/local/"])
@pytest.mark.parametrize("fault", ["swap", "extra_owner", "extra_topic", "encoded_alias"])
def test_local_topics_require_exactly_their_same_path_document(base, fault):
    """Paired predicates alone cannot establish ownership of another page's topic."""
    graph = build_rdf_graph(
        GraphDocument("demo", nodes=[NodeRecord("a", "A"), NodeRecord("b", "B")]),
        namespace_base=base,
    )
    assert validate_rdf_semantics(graph, base) == []
    pages = [URIRef(base + "page/" + name) for name in ("a", "b")]
    topics = [URIRef(base + "concept/" + name) for name in ("a", "b")]
    if fault == "encoded_alias":
        alias = URIRef(base + "concept/%61")
        original = graph
        graph = rdflib.Graph()
        for triple in original:
            graph.add(tuple(alias if term == topics[0] else term for term in triple))
    else:
        for predicate in (SCHEMA.about, DCTERMS.subject):
            if fault == "swap":
                for i in range(2):
                    graph.remove((pages[i], predicate, topics[i]))
                    graph.add((pages[i], predicate, topics[1 - i]))
            elif fault == "extra_topic":
                graph.add((pages[0], predicate, topics[1]))
            else:
                other = URIRef("https://example.org/another-document")
                graph.add((other, RDF.type, SCHEMA.CreativeWork))
                graph.add((other, predicate, topics[0]))
    assert any("matching document about/subject" in e for e in validate_rdf_semantics(graph, base))


@pytest.mark.parametrize("kind", sorted(DOCUMENT_TYPES) + ["unknown_editorial_kind"])
def test_document_only_source_types_cannot_acquire_forged_paired_topics(kind):
    """A complete concept declaration and paired links do not change the source role."""
    graph = build_rdf_graph(
        GraphDocument("demo", nodes=[NodeRecord("records/item", "Item", node_type=kind)]),
        namespace_base=BASE,
    )
    assert validate_rdf_semantics(graph, BASE) == []
    page, topic = _page("records/item"), _concept("records/item")
    for triple in (
        (page, SCHEMA.about, topic),
        (page, DCTERMS.subject, topic),
        (topic, RDF.type, SKOS.Concept),
        (topic, SKOS.prefLabel, Literal("Forged topic")),
        (topic, SKOS.inScheme, URIRef(BASE + "scheme")),
    ):
        graph.add(triple)
    assert any("document-only page" in e for e in validate_rdf_semantics(graph, BASE))


@pytest.mark.parametrize(
    "path,collection",
    [
        ("citations/smith_2022", False),
        ("biology/citations/paper", False),
        ("%63itations/paper", False),
        ("biology/AGENTS", False),
        ("biology/%41GENTS", False),
        ("biology/ReadMe", False),
        ("biology/catalog", False),
        ("biology/index", False),
        ("biology/navigation", True),
    ],
)
def test_document_only_paths_and_collection_pages_override_topic_type(path, collection):
    graph = rdflib.Graph()
    page, topic = _page(path), _concept(path)
    graph.add((page, RDF.type, SCHEMA.CreativeWork))
    graph.add((page, URIRef(BASE + "vocab/pageType"), Literal("concept")))
    if collection:
        graph.add((page, RDF.type, SCHEMA.CollectionPage))
    assert validate_rdf_semantics(graph, BASE) == []
    for triple in (
        (page, SCHEMA.about, topic),
        (page, DCTERMS.subject, topic),
        (topic, RDF.type, SKOS.Concept),
        (topic, SKOS.prefLabel, Literal("Forged topic")),
        (topic, SKOS.inScheme, URIRef(BASE + "scheme")),
    ):
        graph.add(triple)
    assert any("document-only page" in e for e in validate_rdf_semantics(graph, BASE))


def test_conflicting_source_types_cannot_override_a_document_only_role():
    graph = _graph()
    graph.add((_page("maths/free_energy"), URIRef(BASE + "vocab/pageType"), Literal("guide")))
    assert any("document-only page" in e for e in validate_rdf_semantics(graph, BASE))


@pytest.mark.parametrize("path", ["biology/stress response", "biology/β cells", "biology/%41GENTS"])
def test_encoded_local_paths_keep_exact_document_topic_iris(path):
    graph = build_rdf_graph(
        GraphDocument("demo", nodes=[NodeRecord(path, "Topic")]), namespace_base=BASE
    )
    suffix = quote(path, safe="/._-~")
    assert (_page(suffix), SCHEMA.about, _concept(suffix)) in graph
    assert validate_rdf_semantics(graph, BASE) == []


def test_external_subjects_and_sparql_imports_keep_their_original_term_identity():
    external_page = URIRef("https://example.org/document")
    external_topic = URIRef("https://example.org/topic")
    graph = rdflib.Graph()
    graph.add((external_page, RDF.type, SCHEMA.CreativeWork))
    for predicate in (SCHEMA.about, DCTERMS.subject):
        graph.add((external_page, predicate, external_topic))
    assert validate_rdf_semantics(graph, BASE) == []
    doc = GraphDocument(
        "demo",
        nodes=[NodeRecord(str(_page("citations/paper")), "Paper", node_type="uri")],
        edges=[
            EdgeRecord(str(_page("citations/paper")), str(_concept("other")), str(SCHEMA.about))
        ],
        metadata={"source": "sparql"},
    )
    imported = build_rdf_graph(doc, namespace_base=BASE)
    assert (_page("citations/paper"), SCHEMA.about, _concept("other")) in imported
    assert validate_rdf_semantics(imported, BASE, entity_model=False) == []


def test_model_modules_import_without_runtime_file_or_network_io():
    """Real audit hooks reject data reads, writes and sockets during imports."""
    script = r"""
import importlib
import os
import socket
import sys
import rdflib
import requests
import yaml
import networkx
sys.dont_write_bytecode = True
rejected = []
def guard(event, args):
    if event.startswith("socket."):
        rejected.append(event)
        raise RuntimeError("unexpected socket I/O")
    if event == "open":
        path, mode, flags = args
        if (
            not isinstance(path, str)
            or not path.endswith((".py", ".pyc", ".so"))
            or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        ):
            rejected.append(event)
            raise RuntimeError("unexpected runtime file I/O")
sys.addaudithook(guard)
for operation in (lambda: open("forbidden-import-data.txt"), socket.socket):
    try:
        operation()
    except RuntimeError:
        pass
    else:
        raise AssertionError("the rejecting control did not fail")
assert len(rejected) == 2
rejected.clear()
for module in (
    "daf_okn.core.alignment", "daf_okn.core.keyword_terms",
    "daf_okn.core.cognitive_adapter", "daf_okn.core.rdf",
    "daf_okn.core.rdf_submission", "daf_okn.analysis.cross_graph",
):
    importlib.import_module(module)
assert not rejected, rejected
print("no runtime file or network I/O")
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "no runtime file or network I/O"
