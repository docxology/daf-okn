"""Pure assertion-path projection over replay-verified, semantically validated inputs."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, TypeAlias

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS

from daf_okn.core.rdf import SCHEMA

Json: TypeAlias = str | int | bool | None | list["Json"] | dict[str, "Json"]
Triple: TypeAlias = tuple[URIRef, URIRef, URIRef | Literal]
Solution: TypeAlias = Mapping[str, URIRef | Literal]
GRAPH: Final = "https://purl.org/okn/frink/kg/cognitive-kb"
MAPPINGS: Final = "https://purl.org/okn/frink/kg/identifier-mappings"
UBERGRAPH: Final = "https://purl.org/okn/frink/kg/ubergraph"
PROFILE: Final = "cognitive-obo-join-support-1"
ROW_KEYS: Final = ("page", "concept", "label", "wikidata", "external", "externalLabel", "source")
MAX_PAYLOAD: Final = 32 * 1024 * 1024
LIMITS: Final = (
    "Assertion paths add no composed mapping, identity, class equivalence, membership, "
    "reasoning, remote review, scientific or human validation. Hashes do not authenticate "
    "authorship. Capture time does not establish freshness or review time. Local blank "
    "nodes/lexical normalization are unsupported. Duplicate scalar rows share all typed "
    "solutions; individual language assignments cannot be recovered."
)


@dataclass(slots=True)
class EvidenceError(ValueError):
    """An input cannot support a complete explanation within this profile."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class Occurrence:
    """One raw response binding and its existing materializer's output."""

    graph: str
    capture_index: int
    binding_index: int
    query_file: str
    query_sha256: str
    response_file: str
    response_sha256: str
    raw: Mapping[str, Mapping[str, str]]
    triple: Triple


@dataclass(frozen=True, slots=True)
class EvidenceInputs:
    """Verified dataset/SELECT bag, original scalar row order, and byte bindings."""

    dataset: Dataset
    solutions: tuple[Solution, ...]
    rows: tuple[Mapping[str, str], ...]
    occurrences: tuple[Occurrence, ...]
    origin: dict[str, Json]
    producer: dict[str, Json]


@dataclass(frozen=True, slots=True)
class SupportReport:
    """Deterministic JSON and readable Markdown for one verified explanation."""

    json_bytes: bytes
    markdown_bytes: bytes


def canonical(value: Json) -> str:
    """Fixed-key canonical JSON used for row and typed-solution digests/sorting."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def term(value: URIRef | Literal) -> dict[str, Json]:
    """Encode an evaluated RDF term without discarding literal metadata."""
    match value:
        case URIRef():
            return {"type": "uri", "value": str(value)}
        case Literal():
            result: dict[str, Json] = {"type": "literal", "value": str(value)}
            if value.datatype is not None:
                result["datatype"] = str(value.datatype)
            if value.language is not None:
                # WHY: RDF language tags are case-insensitive; RDFLib sets can
                # retain either raw spelling. Raw response records stay intact.
                result["xml:lang"] = value.language.lower()
            return result
    raise EvidenceError(f"unsupported RDF term: {value!r}")


def _assertion(graph: str, triple: Triple) -> dict[str, Json]:
    return {
        "graph": graph,
        **{key: term(t) for key, t in zip(("s", "p", "o"), triple, strict=True)},
    }


def _occurrence(value: Occurrence) -> dict[str, Json]:
    raw: dict[str, Json] = {key: dict(record) for key, record in value.raw.items()}
    materialized = _assertion(value.graph, value.triple)
    return {
        "capture_index": value.capture_index,
        "binding_index": value.binding_index,
        "json_pointer": f"/results/bindings/{value.binding_index}",
        "graph": value.graph,
        "query_file": value.query_file,
        "query_sha256": value.query_sha256,
        "response_file": value.response_file,
        "response_sha256": value.response_sha256,
        "raw": raw,
        "materialized": materialized,
        "lexical_or_metadata_changed": any(raw[k] != materialized[k] for k in ("s", "p", "o")),
    }


def _remote(
    graph: str, triple: Triple, index: Mapping[tuple[str, Triple], list[Occurrence]]
) -> dict[str, Json]:
    occurrences = index.get((graph, triple), [])
    if not occurrences:
        raise EvidenceError(f"no raw capture origin for {graph}: {triple!r}")
    return {
        "assertion": _assertion(graph, triple),
        "occurrences": sorted((_occurrence(o) for o in occurrences), key=canonical),
    }


def _local_support(inputs: EvidenceInputs, row: Solution) -> dict[str, Json]:
    local = inputs.dataset.graph(URIRef(GRAPH))
    page, concept, wikidata = (row[k] for k in ("page", "concept", "wikidata"))
    triples = (
        (page, RDF.type, SCHEMA.CreativeWork),
        (page, SCHEMA.about, concept),
        (page, DCTERMS.subject, concept),
        (page, DCTERMS.source, row["source"]),
        (concept, RDF.type, SKOS.Concept),
        (concept, SKOS.prefLabel, row["label"]),
    )
    assertions: list[Json] = []
    for s, p, o in triples:
        if (
            not isinstance(s, URIRef)
            or not isinstance(o, (URIRef, Literal))
            or (s, p, o) not in local
        ):
            raise EvidenceError(f"missing local assertion: {(s, p, o)!r}")
        assertions.append(_assertion(GRAPH, (s, p, o)))
    mappings: list[Json] = []
    for predicate in (SKOS.closeMatch, SKOS.exactMatch):
        if (concept, predicate, wikidata) not in local:
            continue
        reviews: list[Json] = []
        for statement in local.subjects(RDF.subject, concept):
            if (statement, RDF.predicate, predicate) not in local or (
                statement,
                RDF.object,
                wikidata,
            ) not in local:
                continue
            if not isinstance(statement, URIRef):
                raise EvidenceError(f"unsupported blank-node review statement: {statement!r}")
            properties: list[Json] = []
            for p in (
                RDF.type,
                RDF.subject,
                RDF.predicate,
                RDF.object,
                DCTERMS.source,
                DCTERMS.description,
                DCTERMS.date,
            ):
                for review_object in local.objects(statement, p):
                    if not isinstance(review_object, (URIRef, Literal)):
                        raise EvidenceError(f"unsupported review term: {review_object!r}")
                    properties.append(_assertion(GRAPH, (statement, p, review_object)))
            reviews.append(
                {"statement": term(statement), "assertions": sorted(properties, key=canonical)}
            )
        if not reviews or not isinstance(concept, URIRef) or not isinstance(wikidata, URIRef):
            raise EvidenceError(
                f"mapping lacks complete review evidence: {concept} {predicate} {wikidata}"
            )
        mappings.append(
            {
                "assertion": _assertion(GRAPH, (concept, predicate, wikidata)),
                "reviews": sorted(reviews, key=canonical),
            }
        )
    if not mappings:
        raise EvidenceError(f"no eligible local mapping: {concept} {wikidata}")
    return {
        "assertions": sorted(assertions, key=canonical),
        "mappings": sorted(mappings, key=canonical),
        "origin": {"local_sha256": inputs.origin["local_sha256"]},
    }


def build_support(inputs: EvidenceInputs) -> SupportReport:
    """Project verified typed solution bags and all raw origins without file/network I/O."""
    if len(inputs.rows) > 10000 or len(inputs.occurrences) > 50000:
        raise EvidenceError("explanation exceeds 10000 rows or 50000 raw occurrences")
    origins: dict[tuple[str, Triple], list[Occurrence]] = {}
    for occurrence in inputs.occurrences:
        origins.setdefault((occurrence.graph, occurrence.triple), []).append(occurrence)
    positions: dict[str, list[int]] = {}
    for i, row in enumerate(inputs.rows):
        positions.setdefault(canonical({key: row[key] for key in ROW_KEYS}), []).append(i)
    variants: dict[str, dict[str, Solution]] = {}
    multiplicities: Counter[str] = Counter()
    for row in inputs.solutions:
        scalar = canonical({key: str(row[key]) for key in ROW_KEYS})
        key = canonical({name: term(row[name]) for name in ROW_KEYS})
        variants.setdefault(scalar, {})[key] = row
        multiplicities[key] += 1
    if positions.keys() != variants.keys():
        raise EvidenceError("scalar rows differ from evaluated typed solutions")
    groups: list[Json] = []
    for scalar, indices in sorted(positions.items()):
        solutions: list[Json] = []
        for key, row in sorted(variants[scalar].items()):
            wd, external, label = (row[k] for k in ("wikidata", "external", "externalLabel"))
            if (
                not isinstance(wd, URIRef)
                or not isinstance(external, URIRef)
                or not isinstance(label, Literal)
            ):
                raise EvidenceError(f"unsupported solution terms: {row!r}")
            solutions.append(
                {
                    "bindings": {name: term(row[name]) for name in ROW_KEYS},
                    "multiplicity": multiplicities[key],
                    "local": _local_support(inputs, row),
                    "remote_mapping": _remote(MAPPINGS, (wd, SKOS.exactMatch, external), origins),
                    "remote_label": _remote(UBERGRAPH, (external, RDFS.label, label), origins),
                }
            )
        if sum(multiplicities[key] for key in variants[scalar]) != len(indices):
            raise EvidenceError(f"typed solution bag differs at row positions {indices!r}")
        groups.append(
            {
                "values": {key: inputs.rows[indices[0]][key] for key in ROW_KEYS},
                "row_sha256": hashlib.sha256(scalar.encode()).hexdigest(),
                "row_indices": list(indices),
                "solutions": solutions,
            }
        )
    payload: dict[str, Json] = {
        "explanation_schema_version": 1,
        "profile": PROFILE,
        "semantics": "assertion-path",
        "origin": inputs.origin,
        "producer": inputs.producer,
        "groups": groups,
        "joined_rows": len(inputs.rows),
        "typed_solution_count": sum(len(v) for v in variants.values()),
        "deprecation_replacement": "not_captured",
        "curation_decisions": "not_supplied",
        "limits": LIMITS,
    }
    body = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
    markdown = (
        f"# Join assertion-path support\n\n{LIMITS}\n\n"
        f"Captured observation: {inputs.origin['observed_at']}\n\n"
        "The JSON preserves typed assertions, complete local reviews and raw binding origins.\n\n"
        f"```json\n{body.decode()}```\n"
    ).encode()
    if len(body) + len(markdown) > MAX_PAYLOAD:
        raise EvidenceError(f"generated explanation exceeds {MAX_PAYLOAD} byte payload limit")
    return SupportReport(body, markdown)
