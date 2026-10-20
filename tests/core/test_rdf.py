"""Tests for the standard-vocabulary RDF serialization (``daf_okn.core.rdf``)."""

from __future__ import annotations

from pathlib import Path

import pytest
import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS, XSD

from daf_okn.core.cognitive_adapter import build_cognitive_graph
from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord, bindings_to_graph
from daf_okn.core.rdf import (
    SUPPORTED_FORMATS,
    build_rdf_graph,
    default_namespace_base,
    graph_iri,
    graph_to_rdf,
    relation_predicate,
    relation_slug,
    shortname_slug,
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
                    "doi": "10.1000/xyz 1",
                    "wikidata": "Q42",
                    "status": "stable",
                    "weight": 3,
                    "nested": {"ignored": True},
                    7: "non-string key is skipped",
                },
            ),
            NodeRecord(id="maths/blanket", title="Markov Blanket"),
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
    assert (fe, RDF.type, SKOS.Concept) in graph
    assert (fe, SKOS.inScheme, URIRef(BASE + "scheme")) in graph
    assert (fe, SKOS.prefLabel, Literal("Free Energy")) in graph
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
    assert {str(o) for o in graph.objects(fe, SKOS.altLabel)} == {"FE", "variational free energy"}
    assert (fe, DCTERMS.created, Literal("2024-01-02", datatype=XSD.date)) in graph
    assert (fe, DCTERMS.modified, Literal("2025-03-04", datatype=XSD.date)) in graph
    assert set(graph.objects(fe, SCHEMA.keywords)) == {
        URIRef(BASE + "keyword/" + tag) for tag in ("inference", "maths")
    }
    assert (fe, SCHEMA.author, Literal("A. Author")) in graph
    assert (fe, SCHEMA.datePublished, Literal("2022", datatype=XSD.gYear)) in graph
    assert (fe, SCHEMA.sameAs, URIRef("https://doi.org/10.1000/xyz%201")) in graph
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
    page, target = _page("cortisol"), URIRef(mapping["target"])
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
    assert document.nodes[0].attributes["external_mappings"][0]["reviewed_on"] == "2026-10-20"
    graph = build_rdf_graph(document, namespace_base=BASE)
    assert (
        _page("cortisol"),
        SKOS.exactMatch,
        URIRef("http://purl.obolibrary.org/obo/CHEBI_17650"),
    ) in graph
    assert (_page("cortisol"), SKOS.scopeNote, Literal("Excludes the HPA system.")) in graph


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
    assert (fe, SKOS.related, blanket) in graph
    assert (fe, DCTERMS.isPartOf, readme) in graph
    assert (readme, DCTERMS.hasPart, fe) in graph
    assert (blanket, DCTERMS.references, fe) in graph  # wikilink origin
    assert (_page("old"), DCTERMS.isReplacedBy, fe) in graph
    implements = URIRef(BASE + "relation/implements")
    connects = URIRef(BASE + "relation/connects_to")
    assert (fe, implements, blanket) in graph
    assert (fe, connects, URIRef("http://example.org/ext")) in graph
    for term in (implements, connects, URIRef(BASE + "relation/label")):
        assert (term, RDFS.subPropertyOf, SKOS.semanticRelation) in graph
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
        URIRef(BASE + "relation/label"),
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
    assert (maths, SKOS.member, _page("maths/free_energy")) in graph


def test_language_tag_applies_to_human_readable_literals() -> None:
    graph = build_rdf_graph(_doc(), namespace_base=BASE, language="en")
    fe = _page("maths/free_energy")
    assert (fe, SKOS.prefLabel, Literal("Free Energy", lang="en")) in graph
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
    assert (_page("maths/free_energy"), RDF.type, SKOS.Concept) in named
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
    markov = URIRef(base + "page/mathematics/markov_blanket")
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
        assert (term, RDFS.subPropertyOf, SKOS.semanticRelation) in graph
