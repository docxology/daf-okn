"""Capture and replay joins from cognitive-kb through two named OKN graphs."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pyparsing import ParseException
from rdflib import Dataset, Literal, URIRef, Variable
from rdflib.plugins.sparql.algebra import traverse
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.query import Result, ResultRow

from daf_okn.core.join_report import JoinedRow, markdown_report

GRAPH: Final = "https://purl.org/okn/frink/kg/cognitive-kb"
PREFIXES: Final = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcterms": "http://purl.org/dc/terms/",
}

ENDPOINT: Final = "https://apps.okn.us/federation/sparql"
MAPPINGS: Final = "https://purl.org/okn/frink/kg/identifier-mappings"
UBERGRAPH: Final = "https://purl.org/okn/frink/kg/ubergraph"
EXACT: Final = PREFIXES["skos"] + "exactMatch"
LABEL: Final = PREFIXES["rdfs"] + "label"
OBO: Final = "http://purl.obolibrary.org/obo/"
MAX_BYTES: Final = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class JoinError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class OversizedResponse(JoinError):
    prefix: bytes


@dataclass(frozen=True, slots=True)
class Capture:
    graph: str
    query_file: str
    response_file: str
    query_sha256: str
    response_sha256: str


@dataclass(frozen=True, slots=True)
class JoinOptions:
    source: Path
    query: Path
    output: Path
    endpoint: str = ENDPOINT
    replay: Path | None = None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_iri(value: str) -> URIRef:
    if not re.fullmatch(r'https?://[^\s<>"{}|^`\\]+', value):
        raise JoinError(f"invalid HTTP IRI: {value!r}")
    return URIRef(value)


def response_triples(raw: bytes) -> set[tuple[URIRef, URIRef, URIRef | Literal]]:
    parsed = Result.parse(io.BytesIO(raw), format="json")
    if [str(v) for v in parsed.vars or []] != ["s", "p", "o"]:
        raise JoinError("SPARQL response must project s, p, o")
    triples: set[tuple[URIRef, URIRef, URIRef | Literal]] = set()
    for binding in parsed.bindings:
        s, p, o = (binding.get(Variable(name)) for name in ("s", "p", "o"))
        if not isinstance(s, URIRef) or not isinstance(p, URIRef):
            raise JoinError("SPARQL subject and predicate must be IRIs")
        checked_iri(str(s))
        checked_iri(str(p))
        if not isinstance(o, (URIRef, Literal)):
            raise JoinError("SPARQL object must be an IRI or literal")
        if isinstance(o, URIRef):
            checked_iri(str(o))
        triples.add((s, p, o))
    return triples


def fetch(endpoint: str, query: str) -> bytes:
    checked_iri(endpoint)
    request = Request(
        endpoint + "?" + urlencode({"query": query}),
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "cognitive-okn-join/2.1 (Active Inference Institute)",
        },
    )
    with urlopen(request, timeout=45) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise OversizedResponse(
            "SPARQL response exceeds capture size limit; saved bounded prefix", raw
        )
    return raw


def query_for(graph: str, subjects: list[str]) -> str:
    if graph not in {MAPPINGS, UBERGRAPH}:
        raise JoinError(f"unsupported graph: {graph}")
    predicate = EXACT if graph == MAPPINGS else LABEL
    values = " ".join(checked_iri(value).n3() for value in subjects)
    restriction = f'FILTER(STRSTARTS(STR(?o), "{OBO}"))' if graph == MAPPINGS else ""
    return (
        f"SELECT ?s ?p ?o WHERE {{ VALUES ?s {{ {values} }} "
        f"GRAPH <{graph}> {{ ?s <{predicate}> ?o . }} "
        f"BIND(<{predicate}> AS ?p) {restriction} }} ORDER BY ?s ?o\n"
    )


def capture_stage(subjects: list[str], graph: str, settings: tuple[str, Path]) -> list[Capture]:
    endpoint, out = settings
    captures = []
    for start in range(0, len(subjects), 100):
        query = query_for(graph, subjects[start : start + 100])
        stem = graph.rsplit("/", 1)[-1] + f"-{start:04d}"
        query_file, response_file = stem + ".rq", stem + ".json"
        (out / query_file).write_bytes(query.encode())
        try:
            raw = fetch(endpoint, query)
        except HTTPError as error:
            with error:
                (out / response_file).write_bytes(error.read(MAX_BYTES + 1))
            raise
        except OversizedResponse as error:
            (out / response_file).write_bytes(error.prefix)
            raise
        (out / response_file).write_bytes(raw)
        response_triples(raw)
        captures.append(
            Capture(graph, query_file, response_file, digest(query.encode()), digest(raw))
        )
    return captures


def add_captures(dataset: Dataset, captures: list[Capture], directory: Path) -> None:
    for capture in captures:
        if capture.graph not in {MAPPINGS, UBERGRAPH}:
            raise JoinError(f"unexpected captured graph: {capture.graph}")
        for name, expected in (
            (capture.query_file, capture.query_sha256),
            (capture.response_file, capture.response_sha256),
        ):
            if Path(name).name != name or digest((directory / name).read_bytes()) != expected:
                raise JoinError(f"capture integrity failed: {name}")
        target = dataset.graph(checked_iri(capture.graph))
        query = (directory / capture.query_file).read_text(encoding="utf-8")
        values = re.search(r"VALUES \?s \{ ([^}]+) \}", query)
        if values is None:
            raise JoinError("captured query has no bounded subject values")
        subjects = re.findall(r"<([^<>]+)>", values.group(1))
        if query != query_for(capture.graph, subjects):
            raise JoinError("captured query differs from the bounded query contract")
        expected = URIRef(EXACT if capture.graph == MAPPINGS else LABEL)
        for triple in response_triples((directory / capture.response_file).read_bytes()):
            s, p, o = triple
            if str(s) not in subjects or p != expected:
                raise JoinError("response contains triples outside the requested subject/predicate")
            if capture.graph == MAPPINGS and (
                not isinstance(o, URIRef) or not str(o).startswith(OBO)
            ):
                raise JoinError("mapping response contains a non-OBO identifier")
            if capture.graph == UBERGRAPH and not isinstance(o, Literal):
                raise JoinError("ontology label must be a literal")
            target.add(triple)


def local_dataset(source: Path) -> Dataset:
    dataset = Dataset()
    dataset.parse(source, format="nquads")
    if not len(dataset.graph(URIRef(GRAPH))):
        raise JoinError("local export has no cognitive-kb named graph")
    return dataset


def _reject_remote_clauses(node) -> None:
    if isinstance(node, CompValue) and node.name in {"ServiceGraphPattern", "DatasetClause"}:
        raise JoinError(f"offline join query cannot contain {node.name}")


def write_results(dataset: Dataset, query: Path, settings: tuple[Path, str]) -> None:
    output, observed_at = settings
    text = query.read_text(encoding="utf-8")
    try:
        syntax = parseQuery(text)
    except ParseException as error:
        raise JoinError(f"invalid join query: {error}") from error
    traverse(syntax, visitPre=_reject_remote_clauses)
    rows: list[JoinedRow] = []
    for row in dataset.query(text):
        if not isinstance(row, ResultRow):
            raise JoinError("join query must return SELECT rows")
        rows.append(
            JoinedRow(
                concept=str(row["concept"]),
                label=str(row["label"]),
                wikidata=str(row["wikidata"]),
                external=str(row["external"]),
                externalLabel=str(row["externalLabel"]),
                source=str(row["source"]),
            )
        )
    if not rows:
        raise JoinError("cross-graph join returned zero rows")
    result = {
        "joined_rows": len(rows),
        "matched_pages": len({row["concept"] for row in rows}),
        "external_terms": len({row["external"] for row in rows}),
        "rows": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "join-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output / "join-results.md").write_text(markdown_report(rows, observed_at), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


def _run(args: JoinOptions) -> None:
    source, query = Path(args.source), Path(args.query)
    dataset = local_dataset(source)
    out = Path(args.output)
    if args.replay:
        snapshot = Path(args.replay)
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        if manifest["local_sha256"] != digest(source.read_bytes()):
            raise JoinError("local export differs from captured join source")
        if manifest["join_query_sha256"] != digest(query.read_bytes()):
            raise JoinError("join query differs from captured query")
        captures = [Capture(**item) for item in manifest["captures"]]
        add_captures(dataset, captures, snapshot)
    else:
        out.mkdir(parents=True, exist_ok=False)
        local = dataset.graph(URIRef(GRAPH))
        subjects = sorted(
            {
                str(o)
                for relation in ("closeMatch", "exactMatch")
                for _, _, o in local.triples((None, URIRef(PREFIXES["skos"] + relation), None))
                if isinstance(o, URIRef)
                and re.fullmatch(r"http://www\.wikidata\.org/entity/Q[1-9][0-9]*", str(o))
            }
        )
        if not subjects:
            raise JoinError("local graph has no Wikidata join keys")
        captures = capture_stage(subjects, MAPPINGS, (args.endpoint, out))
        add_captures(dataset, captures, out)
        external = sorted({str(o) for _, _, o in dataset.graph(URIRef(MAPPINGS))})
        captures += capture_stage(external, UBERGRAPH, (args.endpoint, out))
        add_captures(dataset, captures, out)
        manifest = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": args.endpoint,
            "local_sha256": digest(source.read_bytes()),
            "join_query_sha256": digest(query.read_bytes()),
            "captures": [asdict(capture) for capture in captures],
            "requested_wikidata_keys": len(subjects),
            "requested_obo_terms": len(external),
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_results(dataset, query, (out, manifest["observed_at"]))


def run(args: JoinOptions) -> None:
    existed = Path(args.output).exists()
    try:
        _run(args)
    except (OSError, ValueError, URLError, TimeoutError, KeyError, TypeError) as error:
        out = Path(args.output)
        if out.is_dir() and not args.replay and not existed:
            (out / "failure.json").write_text(
                json.dumps({"error": str(error)}, indent=2) + "\n", encoding="utf-8"
            )
        raise
