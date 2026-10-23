"""Capture and replay joins from cognitive-kb through two named OKN graphs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from pyparsing import ParseException
from rdflib import Dataset, Literal, URIRef
from rdflib.exceptions import ParserError
from rdflib.query import ResultRow

from daf_okn.core.alignment import checked_iri as alignment_iri
from daf_okn.core.join_report import JoinedRow, markdown_report
from daf_okn.core.rdf import SCHEMA, validate_entity_model
from daf_okn.core.rdf_submission import (
    MAX_MANIFEST_BYTES,
    file_inventory,
    hash_inventory,
    json_object,
    read_bounded,
    regular_file,
    sha256,
)

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


class DocumentJoinedRow(JoinedRow):
    """Current join projection, including the document supporting a topic/source."""

    page: str


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
    try:
        return URIRef(alignment_iri(value))
    except ValueError as error:
        raise JoinError(str(error)) from error


def response_triples(raw: bytes) -> set[tuple[URIRef, URIRef, URIRef | Literal]]:
    if len(raw) > MAX_BYTES:
        raise JoinError(f"SPARQL response exceeds {MAX_BYTES} byte size limit")
    try:
        payload = json_object(raw)
    except ValueError as error:
        raise JoinError(f"invalid SPARQL JSON: {error}") from error
    if not isinstance(payload.get("head"), dict) or payload["head"].get("vars") != ["s", "p", "o"]:
        raise JoinError("SPARQL response must project s, p, o")
    if not isinstance(payload.get("results"), dict) or not isinstance(
        payload["results"].get("bindings"), list
    ):
        raise JoinError("SPARQL results.bindings must be a list")
    triples: set[tuple[URIRef, URIRef, URIRef | Literal]] = set()
    for binding in payload["results"]["bindings"]:
        if not isinstance(binding, dict) or set(binding) != {"s", "p", "o"}:
            raise JoinError("SPARQL binding must contain exactly s, p, o")
        terms: list[URIRef | Literal] = []
        for name in ("s", "p", "o"):
            term = binding[name]
            if (
                not isinstance(term, dict)
                or not {"type", "value"} <= term.keys()
                or set(term) - {"type", "value", "datatype", "xml:lang"}
                or not isinstance(term["value"], str)
            ):
                raise JoinError(f"malformed SPARQL RDF term for {name}")
            if term["type"] == "uri" and set(term) == {"type", "value"}:
                terms.append(checked_iri(term["value"]))
            elif term["type"] in ("literal", "typed-literal"):
                datatype, language = term.get("datatype"), term.get("xml:lang")
                if (
                    (datatype is not None and language is not None)
                    or ("datatype" in term and not isinstance(datatype, str))
                    or (
                        "xml:lang" in term
                        and (
                            not isinstance(language, str)
                            or not re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z0-9]+)*", language)
                        )
                    )
                    or (term["type"] == "typed-literal" and datatype is None)
                ):
                    raise JoinError(f"invalid SPARQL literal metadata for {name}")
                terms.append(
                    Literal(
                        term["value"],
                        datatype=checked_iri(datatype) if datatype is not None else None,
                        lang=language,
                    )
                )
            else:
                raise JoinError(f"unsupported SPARQL RDF term type for {name}")
        s, p, o = terms
        if not isinstance(s, URIRef) or not isinstance(p, URIRef):
            raise JoinError("SPARQL subject and predicate must be IRIs")
        triples.add((s, p, o))
    return triples


def fetch(endpoint: str, query: str) -> bytes:
    checked_iri(endpoint)
    if urlsplit(endpoint).fragment:
        raise JoinError("SPARQL endpoint must not contain a fragment")
    request = Request(
        endpoint + ("&" if urlsplit(endpoint).query else "?") + urlencode({"query": query}),
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
    if not 1 <= len(subjects) <= 100 or len(set(subjects)) != len(subjects):
        raise JoinError("captured subject batch must have 1..100 unique IRIs")
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
    used: set[str] = set()
    for capture in captures:
        if capture.graph not in {MAPPINGS, UBERGRAPH}:
            raise JoinError(f"unexpected captured graph: {capture.graph}")
        for name, expected in (
            (capture.query_file, capture.query_sha256),
            (capture.response_file, capture.response_sha256),
        ):
            try:
                raw = read_bounded(regular_file(directory, name), MAX_BYTES)
            except (OSError, ValueError) as error:
                raise JoinError(f"capture integrity failed: {name}: {error}") from error
            if Path(name).name != name or name in used or digest(raw) != expected:
                raise JoinError(f"capture integrity failed: {name}")
            used.add(name)
        target = dataset.graph(checked_iri(capture.graph))
        query = read_bounded(regular_file(directory, capture.query_file), MAX_BYTES).decode("utf-8")
        values = re.search(r"VALUES \?s \{ ([^}]+) \}", query)
        if values is None:
            raise JoinError("captured query has no bounded subject values")
        subjects = re.findall(r"<([^<>]+)>", values.group(1))
        if query != query_for(capture.graph, subjects):
            raise JoinError("captured query differs from the bounded query contract")
        expected = URIRef(EXACT if capture.graph == MAPPINGS else LABEL)
        for triple in response_triples(
            read_bounded(regular_file(directory, capture.response_file), MAX_BYTES)
        ):
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


def local_dataset(source: Path, *, entity_model: bool = True) -> Dataset:
    dataset = Dataset()
    try:
        dataset.parse(regular_file(source.parent, source.name), format="nquads")
    except (OSError, ValueError, SyntaxError, ParserError) as error:
        raise JoinError(f"invalid local export: {error}") from error
    if any(graph != URIRef(GRAPH) for _, _, _, graph in dataset.quads()):
        raise JoinError("local export contains an unexpected named graph")
    if not len(dataset.graph(URIRef(GRAPH))):
        raise JoinError("local export has no cognitive-kb named graph")
    if entity_model:
        errors = validate_entity_model(dataset.graph(URIRef(GRAPH)), GRAPH)
        if errors:
            raise JoinError("invalid document/concept model: " + "; ".join(errors))
    return dataset


def _reject_remote_clauses(node) -> None:
    from rdflib.plugins.sparql.parserutils import CompValue

    if isinstance(node, CompValue) and node.name in {"ServiceGraphPattern", "DatasetClause"}:
        raise JoinError(f"offline join query cannot contain {node.name}")


def write_results(
    dataset: Dataset,
    query: Path,
    settings: tuple[Path, str],
    *,
    provenance: dict[str, Any] | None = None,
    schema_version: int = 3,
) -> None:
    # WHY: rdflib's SPARQL plugin reads distribution metadata on import.
    from rdflib.plugins.sparql.algebra import traverse
    from rdflib.plugins.sparql.parser import parseQuery

    if type(schema_version) is not int or schema_version not in {1, 2, 3}:
        raise JoinError(f"unsupported join result schema: {schema_version!r}")
    output, observed_at = settings
    text = read_bounded(regular_file(query.parent, query.name), MAX_BYTES).decode("utf-8")
    try:
        syntax = parseQuery(text)
    except ParseException as error:
        raise JoinError(f"invalid join query: {error}") from error
    traverse(syntax, visitPre=_reject_remote_clauses)
    result_rows = dataset.query(text)
    required = {"concept", "label", "wikidata", "external", "externalLabel", "source"}
    if schema_version == 3:
        required.add("page")
    if result_rows.type != "SELECT" or {str(value) for value in result_rows.vars or []} != required:
        raise JoinError(
            f"join SELECT must project {', '.join(sorted(required))} for schema {schema_version}"
        )
    rows: list[JoinedRow] = []
    matched_pages: set[str] = set()
    local = dataset.graph(URIRef(GRAPH))
    if schema_version == 3:
        errors = validate_entity_model(local, GRAPH)
        if errors:
            raise JoinError("invalid document/concept model: " + "; ".join(errors))
    elif any(str(s).startswith(GRAPH + "/concept/") for s in local.subjects()):
        raise JoinError("historical capture schema cannot replay the document/concept model")
    mapping_graph = dataset.graph(URIRef(MAPPINGS))
    label_graph = dataset.graph(URIRef(UBERGRAPH))
    join_keys = set(_wikidata_subjects(dataset))
    for row in result_rows:
        if not isinstance(row, ResultRow):
            raise JoinError("join query must return SELECT rows")
        if any(row[name] is None for name in required):
            raise JoinError("join SELECT returned an unbound required value")
        iri_names = {"concept", "wikidata", "external", "source"}
        if schema_version == 3:
            iri_names.add("page")
        if not all(isinstance(row[name], URIRef) for name in iri_names) or not all(
            isinstance(row[name], Literal) for name in ("label", "externalLabel")
        ):
            raise JoinError("join SELECT returned invalid RDF term types")
        for name in iri_names:
            checked_iri(str(row[name]))
        if (
            (row["concept"], URIRef(PREFIXES["rdf"] + "type"), URIRef(PREFIXES["skos"] + "Concept"))
            not in local
            or (row["concept"], URIRef(PREFIXES["skos"] + "prefLabel"), row["label"]) not in local
            or not (
                (row["concept"], URIRef(PREFIXES["dcterms"] + "source"), row["source"]) in local
                if schema_version < 3
                else str(row["concept"]).startswith(GRAPH + "/concept/")
                and (row["page"], URIRef(PREFIXES["rdf"] + "type"), SCHEMA.CreativeWork) in local
                and (row["page"], SCHEMA.about, row["concept"]) in local
                and (row["page"], URIRef(PREFIXES["dcterms"] + "subject"), row["concept"]) in local
                and (row["page"], URIRef(PREFIXES["dcterms"] + "source"), row["source"]) in local
            )
            or not any(
                (row["concept"], URIRef(PREFIXES["skos"] + relation), row["wikidata"]) in local
                for relation in ("exactMatch", "closeMatch")
            )
            or (row["wikidata"], URIRef(EXACT), row["external"]) not in mapping_graph
            or (row["external"], URIRef(LABEL), row["externalLabel"]) not in label_graph
            or str(row["wikidata"]) not in join_keys
            or not str(row["external"]).startswith(OBO)
        ):
            raise JoinError("join row is not supported by the three named source graphs")
        joined = JoinedRow(
            concept=str(row["concept"]),
            label=str(row["label"]),
            wikidata=str(row["wikidata"]),
            external=str(row["external"]),
            externalLabel=str(row["externalLabel"]),
            source=str(row["source"]),
        )
        if schema_version == 3:
            rows.append(DocumentJoinedRow(**joined, page=str(row["page"])))
            matched_pages.add(str(row["page"]))
        else:
            rows.append(joined)
            matched_pages.add(str(row["concept"]))
    if not rows:
        raise JoinError("cross-graph join returned zero rows")
    result: dict[str, Any] = {
        "joined_rows": len(rows),
        "matched_pages": len(matched_pages),
        "external_terms": len({row["external"] for row in rows}),
        "rows": rows,
    }
    if schema_version == 3:
        result["schema_version"] = 3
        result["matched_concepts"] = len({row["concept"] for row in rows})
    if provenance is not None:
        result["provenance"] = provenance
    output.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise JoinError(f"join results exceed {MAX_MANIFEST_BYTES} byte size limit")
    (output / "join-results.json").write_bytes(payload)
    (output / "join-results.md").write_text(markdown_report(rows, observed_at), encoding="utf-8")
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"rows", "provenance"}}, indent=2)
    )


def _wikidata_subjects(dataset: Dataset) -> list[str]:
    local = dataset.graph(URIRef(GRAPH))
    return sorted(
        {
            str(o)
            for relation in ("closeMatch", "exactMatch")
            for _, _, o in local.triples((None, URIRef(PREFIXES["skos"] + relation), None))
            if isinstance(o, URIRef)
            and re.fullmatch(r"http://www\.wikidata\.org/entity/Q[1-9][0-9]*", str(o))
        }
    )


def _provenance(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: manifest[key]
        for key in (
            "observed_at",
            "endpoint",
            "local_sha256",
            "join_query_sha256",
            "captures",
            "requested_wikidata_keys",
            "requested_obo_terms",
        )
    }


def _replay_manifest(
    snapshot: Path, source: Path, query: Path
) -> tuple[dict[str, Any], list[Capture]]:
    manifest = json_object(
        read_bounded(regular_file(snapshot, "manifest.json"), MAX_MANIFEST_BYTES)
    )
    required = {
        "observed_at",
        "endpoint",
        "local_sha256",
        "join_query_sha256",
        "captures",
        "requested_wikidata_keys",
        "requested_obo_terms",
    }
    version = manifest.get("schema_version", 1)
    if (
        type(version) is not int
        or version not in {1, 2, 3}
        or set(manifest) != required | ({"schema_version", "files"} if version >= 2 else set())
    ):
        raise JoinError("unsupported or malformed captured join manifest schema")
    if (
        not isinstance(manifest["observed_at"], str)
        or datetime.fromisoformat(manifest["observed_at"]).tzinfo is None
    ):
        raise JoinError("captured observation time must include a timezone")
    checked_iri(manifest["endpoint"])
    if manifest["local_sha256"] != sha256(source):
        raise JoinError("local export differs from captured join source")
    if manifest["join_query_sha256"] != sha256(query):
        raise JoinError("join query differs from captured query")
    if not isinstance(manifest["captures"], list) or not manifest["captures"]:
        raise JoinError("capture manifest requires nonempty captures")
    fields = {"graph", "query_file", "response_file", "query_sha256", "response_sha256"}
    captures = []
    names: set[str] = set()
    for item in manifest["captures"]:
        if (
            not isinstance(item, dict)
            or set(item) != fields
            or not all(isinstance(value, str) for value in item.values())
        ):
            raise JoinError("malformed capture record")
        capture = Capture(**item)
        hash_inventory(
            {
                capture.query_file: capture.query_sha256,
                capture.response_file: capture.response_sha256,
            },
            "capture",
        )
        if capture.query_file == capture.response_file or names & {
            capture.query_file,
            capture.response_file,
        }:
            raise JoinError("capture manifest reuses an artifact file")
        names.update((capture.query_file, capture.response_file))
        captures.append(capture)
    actual = file_inventory(snapshot)
    result_files = {"join-results.json", "join-results.md"}
    expected = names | {"manifest.json"}
    if version >= 2:
        expected |= result_files | {"join-query.rq"}
        files = hash_inventory(manifest["files"], "captured files")
        if set(files) != expected - {"manifest.json"}:
            raise JoinError("capture artifact hash inventory is incomplete or unexpected")
        for name, expected_hash in files.items():
            if sha256(regular_file(snapshot, name)) != expected_hash:
                raise JoinError(f"capture artifact hash mismatch: {name}")
        if read_bounded(regular_file(snapshot, "join-query.rq"), MAX_BYTES) != read_bounded(
            query, MAX_BYTES
        ):
            raise JoinError("stored join query differs from captured query")
        result = json_object(
            read_bounded(regular_file(snapshot, "join-results.json"), MAX_MANIFEST_BYTES)
        )
        if result.get("provenance") != _provenance(manifest):
            raise JoinError("result provenance differs from capture manifest")
    else:
        expected |= actual & result_files
    if actual != expected:
        raise JoinError(
            f"capture file inventory differs: missing={sorted(expected - actual)}; "
            f"unexpected={sorted(actual - expected)}"
        )
    return manifest, captures


def _replay_stages(
    dataset: Dataset, captures: list[Capture], snapshot: Path, manifest: dict[str, Any]
) -> None:
    offset = 0
    for graph, count_key in (
        (MAPPINGS, "requested_wikidata_keys"),
        (UBERGRAPH, "requested_obo_terms"),
    ):
        subjects = (
            _wikidata_subjects(dataset)
            if graph == MAPPINGS
            else sorted({str(o) for _, _, o in dataset.graph(URIRef(MAPPINGS))})
        )
        if type(manifest[count_key]) is not int or manifest[count_key] != len(subjects):
            raise JoinError(f"capture requested subject count differs: {count_key}")
        for start in range(0, len(subjects), 100):
            if offset >= len(captures) or captures[offset].graph != graph:
                raise JoinError("capture manifest omits or reorders a required subject batch")
            capture = captures[offset]
            actual = read_bounded(regular_file(snapshot, capture.query_file), MAX_BYTES).decode(
                "utf-8"
            )
            if actual != query_for(graph, subjects[start : start + 100]):
                raise JoinError("captured subject batch differs from current stage inputs")
            add_captures(dataset, [capture], snapshot)
            offset += 1
    if offset != len(captures):
        raise JoinError("capture manifest contains unexpected subject batches")


def _run(args: JoinOptions) -> None:
    source, query = Path(args.source), Path(args.query)
    out = Path(args.output)
    if any(parent.is_symlink() for parent in (out, *out.absolute().parents)):
        raise JoinError(f"symlink is not a join output destination: {out}")
    regular_file(query.parent, query.name)
    if out.exists() or out.is_symlink():
        raise JoinError(f"join output already exists: {out}")
    if args.replay:
        snapshot = Path(args.replay)
        manifest, captures = _replay_manifest(snapshot, source, query)
        dataset = local_dataset(source, entity_model=manifest.get("schema_version", 1) == 3)
        _replay_stages(dataset, captures, snapshot, manifest)
    else:
        dataset = local_dataset(source)
        out.mkdir(parents=True, exist_ok=False)
        subjects = _wikidata_subjects(dataset)
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
            "local_sha256": sha256(source),
            "join_query_sha256": sha256(query),
            "captures": [asdict(capture) for capture in captures],
            "requested_wikidata_keys": len(subjects),
            "requested_obo_terms": len(external),
        }
    write_results(
        dataset,
        query,
        (out, manifest["observed_at"]),
        provenance=_provenance(manifest),
        schema_version=manifest.get("schema_version", 1) if args.replay else 3,
    )
    if args.replay and manifest.get("schema_version", 1) >= 2:
        for name in ("join-results.json", "join-results.md"):
            if sha256(regular_file(out, name)) != manifest["files"][name]:
                raise JoinError(f"captured result differs from recomputed join: {name}")
    if not args.replay:
        (out / "join-query.rq").write_bytes(read_bounded(query, MAX_BYTES))
        manifest["schema_version"] = 3
        manifest["files"] = {
            name: sha256(regular_file(out, name)) for name in sorted(file_inventory(out))
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


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
