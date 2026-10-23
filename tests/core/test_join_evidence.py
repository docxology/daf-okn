"""Independent term/bag/origin oracles for the pure evidence projection."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS, XSD

from daf_okn.core.join_evidence import (
    GRAPH,
    MAPPINGS,
    ROW_KEYS,
    UBERGRAPH,
    EvidenceError,
    EvidenceInputs,
    Occurrence,
    build_support,
    canonical,
    term,
)
from daf_okn.core.rdf import SCHEMA


@pytest.fixture
def inputs():
    """One real RDF/SPARQL solution with two complete reviews and raw origins."""
    dataset = Dataset()
    graph = dataset.graph(URIRef(GRAPH))
    concept, page = URIRef(GRAPH + "/concept/topic"), URIRef(GRAPH + "/page/topic")
    wd, external = (
        URIRef("http://www.wikidata.org/entity/Q1"),
        URIRef("http://purl.obolibrary.org/obo/TEST_1"),
    )
    for triple in (
        (concept, RDF.type, SKOS.Concept),
        (concept, SKOS.prefLabel, Literal("Topic", lang="en")),
        (page, RDF.type, SCHEMA.CreativeWork),
        (page, SCHEMA.about, concept),
        (page, DCTERMS.subject, concept),
        (page, DCTERMS.source, URIRef("https://example.org/topic")),
        (concept, SKOS.closeMatch, wd),
    ):
        graph.add(triple)
    for i in (1, 2):
        statement = URIRef(GRAPH + f"/mapping/{i}")
        for p, o in (
            (RDF.type, RDF.Statement),
            (RDF.subject, concept),
            (RDF.predicate, SKOS.closeMatch),
            (RDF.object, wd),
            (DCTERMS.source, URIRef(f"https://example.org/review/{i}")),
            (DCTERMS.description, Literal(f"Review {i}")),
            (DCTERMS.date, Literal("2026-10-23", datatype=XSD.date)),
        ):
            graph.add((statement, p, o))
    occurrences = []
    for i, (g, triple) in enumerate(
        (
            (MAPPINGS, (wd, SKOS.exactMatch, external)),
            (UBERGRAPH, (external, RDFS.label, Literal("External", lang="fr"))),
        )
    ):
        dataset.graph(URIRef(g)).add(triple)
        raw = {key: term(value) for key, value in zip(("s", "p", "o"), triple, strict=True)}
        response_hash = hashlib.sha256(json.dumps(raw).encode()).hexdigest()
        occurrences.append(
            Occurrence(
                g,
                i,
                0,
                f"query-{i}.rq",
                hashlib.sha256(g.encode()).hexdigest(),
                f"response-{i}.json",
                response_hash,
                raw,
                triple,
            )
        )
    query = (Path(__file__).parents[1] / "fixtures/cross_graph_obo_v3.rq").read_text()
    solutions = tuple(row.asdict() for row in dataset.query(query))
    rows = tuple({key: str(row[key]) for key in ROW_KEYS} for row in solutions)
    return EvidenceInputs(
        dataset,
        solutions,
        rows,
        tuple(occurrences),
        {
            "local_sha256": hashlib.sha256(dataset.serialize(format="nquads").encode()).hexdigest(),
            "observed_at": "2026-10-23T00:00:00+00:00",
        },
        {},
    )


def test_row_digest_and_full_review_assertions_are_bound(inputs):
    # Given a real typed solution and scalar row.
    expected = hashlib.sha256(
        json.dumps(
            dict(inputs.rows[0]), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()
    # When projected, then the row digest and all review terms remain inspectable.
    result = json.loads(build_support(inputs).json_bytes)
    (group,) = result["groups"]
    assert group["row_indices"] == [0]
    assert group["row_sha256"] == expected
    (mapping,) = group["solutions"][0]["local"]["mappings"]
    assert mapping["assertion"]["p"]["value"] == str(SKOS.closeMatch)
    assert [r["statement"]["value"] for r in mapping["reviews"]] == [
        GRAPH + "/mapping/1",
        GRAPH + "/mapping/2",
    ]
    for review in mapping["reviews"]:
        assert {a["p"]["value"] for a in review["assertions"]} == {
            str(p)
            for p in (
                RDF.type,
                RDF.subject,
                RDF.predicate,
                RDF.object,
                DCTERMS.source,
                DCTERMS.description,
                DCTERMS.date,
            )
        }


def test_duplicate_typed_solutions_retain_bag_multiplicity(inputs):
    # Given repeated identical SELECT solutions (not review or raw-row duplicates).
    duplicated = replace(inputs, solutions=inputs.solutions * 2, rows=inputs.rows * 2)
    # When projected, then one typed solution accounts for both original indices.
    (group,) = json.loads(build_support(duplicated).json_bytes)["groups"]
    assert group["row_indices"] == [0, 1]
    assert len(group["solutions"]) == 1
    assert group["solutions"][0]["multiplicity"] == 2


def test_input_iteration_order_does_not_change_support_bytes(inputs):
    # Given identical inputs with reversed graph insertion/raw-occurrence enumeration.
    reverse = Dataset()
    for s, p, o, graph in reversed(list(inputs.dataset.quads())):
        reverse.graph(graph).add((s, p, o))
    altered = replace(inputs, dataset=reverse, occurrences=tuple(reversed(inputs.occurrences)))
    # When projected, then deterministic sorting retains identical bytes.
    assert build_support(altered) == build_support(inputs)


@pytest.mark.parametrize("fault", ["scalar", "bag", "origin", "mapping"])
def test_projection_refuses_unbound_or_incomplete_support(inputs, fault):
    # Given deliberately incompatible in-memory support.
    if fault == "scalar":
        inputs = replace(inputs, rows=({**inputs.rows[0], "label": "forged"},))
    elif fault == "bag":
        inputs = replace(inputs, solutions=inputs.solutions * 2)
    elif fault == "origin":
        inputs = replace(inputs, occurrences=inputs.occurrences[:1])
    else:
        graph = inputs.dataset.graph(URIRef(GRAPH))
        graph.remove((None, SKOS.closeMatch, None))
    # When projected, then no unsupported evidence is returned.
    with pytest.raises(EvidenceError):
        build_support(inputs)


@pytest.mark.parametrize(
    "left,right",
    [
        (URIRef("http://example.org/a"), URIRef("https://example.org/a")),
        (URIRef("https://example.org/%61"), URIRef("https://example.org/a")),
        (Literal("same", lang="en"), Literal("same", lang="fr")),
        (Literal("same"), Literal("same", datatype=XSD.string)),
        (
            Literal("01", datatype=XSD.integer, normalize=False),
            Literal("1", datatype=XSD.integer, normalize=False),
        ),
    ],
)
def test_term_encoding_preserves_recorded_identity_boundaries(left, right):
    # Given two source/evaluated records differing in spelling or metadata.
    # When encoded, then the evidence never guesses an alias or drops metadata.
    assert canonical(term(left)) != canonical(term(right))


def test_payload_limit_is_an_actual_rejecting_gate(inputs):
    # Given a finite row budget exceeded by a real repeated bag.
    oversized = replace(inputs, rows=inputs.rows * 10001)
    # When projected, then the gate fails before building an enormous report.
    with pytest.raises(EvidenceError, match="10000"):
        build_support(oversized)


def test_language_case_canonicalization_matches_rdf_term_identity():
    # Given RDF language tags whose case differs, with an independent SPARQL oracle.
    query = 'SELECT (sameTerm("term"@EN, "term"@en) AS ?same) WHERE {}'
    (same,) = Dataset().query(query)
    assert bool(same[0])
    # When encoded, then equivalent tags cannot select an arbitrary case spelling.
    assert term(Literal("term", lang="EN")) == term(Literal("term", lang="en"))
