import json
import threading
from contextlib import contextmanager
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from rdflib import BNode, Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS

from daf_okn.analysis import cross_graph as join
from daf_okn.cli import main as run_cli

QUERY = Path(__file__).resolve().parents[2] / "tests/fixtures/cross_graph_obo_v3.rq"
LEGACY_QUERY = QUERY.with_name("cross_graph_obo.rq")
WD = "http://www.wikidata.org/entity/Q190875"
TERM = join.OBO + "CHEBI_17650"
CONCEPT = join.GRAPH + "/concept/biology/cortisol"
PAGE = join.GRAPH + "/page/biology/cortisol"


def local_export(tmp_path):
    dataset = Dataset()
    graph = dataset.graph(URIRef(join.GRAPH))
    graph.add(
        (
            URIRef(CONCEPT),
            URIRef(join.PREFIXES["rdf"] + "type"),
            URIRef(join.PREFIXES["skos"] + "Concept"),
        )
    )
    graph.add((URIRef(CONCEPT), URIRef(join.PREFIXES["skos"] + "prefLabel"), Literal("Cortisol")))
    graph.add((URIRef(CONCEPT), URIRef(join.PREFIXES["skos"] + "closeMatch"), URIRef(WD)))
    graph.add((URIRef(PAGE), URIRef(join.PREFIXES["rdf"] + "type"), join.SCHEMA.CreativeWork))
    graph.add((URIRef(PAGE), join.SCHEMA.about, URIRef(CONCEPT)))
    graph.add((URIRef(PAGE), URIRef(join.PREFIXES["dcterms"] + "subject"), URIRef(CONCEPT)))
    graph.add(
        (
            URIRef(PAGE),
            URIRef(join.PREFIXES["dcterms"] + "source"),
            URIRef("https://example.org/cortisol"),
        )
    )
    source = tmp_path / "local.nq"
    dataset.serialize(source, format="nquads")
    return source


@contextmanager
def endpoint_server():
    dataset = Dataset()
    dataset.graph(URIRef(join.MAPPINGS)).add((URIRef(WD), URIRef(join.EXACT), URIRef(TERM)))
    dataset.graph(URIRef(join.UBERGRAPH)).add(
        (URIRef(TERM), URIRef(join.LABEL), Literal("cortisol"))
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/failure":
                self.send_error(503)
                return
            query = parse_qs(parsed.query)["query"][0]
            raw = dataset.query(query).serialize(format="json")
            if parsed.path == "/malformed":
                raw = b"invalid json"
            if parsed.path == "/oversize":
                raw = b"x" * (join.MAX_BYTES + 1)
            self.send_response(200)
            self.send_header("Content-Type", "application/sparql-results+json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def arguments(source, out, query=QUERY):
    return ["join", "--source", str(source), "--query", str(query), "--output", str(out)]


def test_live_capture_and_offline_replay_match_real_query_results(tmp_path):
    source = local_export(tmp_path)
    snapshot = tmp_path / "capture"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, snapshot) + ["--endpoint", endpoint]) == 0
    replay = tmp_path / "replay"
    assert run_cli(arguments(source, replay) + ["--replay", str(snapshot)]) == 0
    result = json.loads((replay / "join-results.json").read_text())
    assert result["matched_pages"] == result["joined_rows"] == result["external_terms"] == 1
    assert result["rows"][0]["external"] == TERM
    assert result["rows"][0]["concept"] == CONCEPT
    assert result["rows"][0]["page"] == PAGE
    assert json.loads((snapshot / "manifest.json").read_text())["schema_version"] == 3
    assert (snapshot / "join-results.json").read_bytes() == (
        replay / "join-results.json"
    ).read_bytes()


@pytest.mark.parametrize("path", ["/failure", "/malformed", "/oversize"])
def test_network_failure_retains_receipt_and_returns_failure(tmp_path, path):
    source = local_export(tmp_path)
    out = tmp_path / "capture"
    with endpoint_server() as endpoint:
        status = run_cli(arguments(source, out) + ["--endpoint", endpoint + path])
    assert status == 1
    assert json.loads((out / "failure.json").read_text())["error"]
    assert list(out.glob("*.rq"))
    assert list(out.glob("*.json"))


def test_exact_keys_work_and_other_external_terms_are_not_requested(tmp_path):
    source = local_export(tmp_path)
    dataset = Dataset().parse(source, format="nquads")
    graph = dataset.graph(URIRef(join.GRAPH))
    graph.remove((None, URIRef(join.PREFIXES["skos"] + "closeMatch"), None))
    graph.add((URIRef(CONCEPT), URIRef(join.EXACT), URIRef(WD)))
    graph.add((URIRef(CONCEPT), URIRef(join.EXACT), URIRef(TERM)))
    graph.add(
        (
            URIRef(PAGE),
            URIRef("http://www.w3.org/2000/01/rdf-schema#seeAlso"),
            URIRef("http://www.wikidata.org/entity/Q1"),
        )
    )
    dataset.serialize(source, format="nquads")
    out = tmp_path / "capture"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, out) + ["--endpoint", endpoint]) == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["requested_wikidata_keys"] == 1
    requested = (out / "identifier-mappings-0000.rq").read_text()
    assert WD in requested and TERM not in requested


def test_reusing_capture_directory_does_not_overwrite_evidence(tmp_path):
    source = local_export(tmp_path)
    out = tmp_path / "capture"
    out.mkdir()
    receipt = out / "failure.json"
    receipt.write_text("preserved failure")
    assert run_cli(arguments(source, out)) == 1
    assert receipt.read_text() == "preserved failure"


@pytest.mark.parametrize(
    "file_name",
    ["local.nq", "manifest.json", "identifier-mappings-0000.json", "identifier-mappings-0000.rq"],
)
def test_modified_source_or_capture_is_rejected(tmp_path, file_name):
    source = local_export(tmp_path)
    out = tmp_path / "capture"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, out) + ["--endpoint", endpoint]) == 0
    path = source if file_name == "local.nq" else out / file_name
    path.write_bytes(path.read_bytes() + b" \n")
    if file_name == "manifest.json":
        manifest = json.loads(path.read_text())
        manifest["join_query_sha256"] = "corrupted"
        path.write_text(json.dumps(manifest))
    assert run_cli(arguments(source, tmp_path / "replay") + ["--replay", str(out)]) == 1


@pytest.mark.parametrize("value", ["Q190875", "https://example.org/<bad>", "file:///tmp/local"])
def test_invalid_join_iris_are_rejected(value):
    with pytest.raises(join.JoinError):
        join.checked_iri(value)


def test_empty_cross_graph_join_is_a_failure(tmp_path):
    source = local_export(tmp_path)
    source.write_text(source.read_text().replace(WD, "http://www.wikidata.org/entity/Q1"))
    out = tmp_path / "capture"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, out) + ["--endpoint", endpoint]) == 1
    assert "zero rows" in (out / "failure.json").read_text()


def test_source_without_named_graph_is_rejected(tmp_path):
    source = tmp_path / "empty.nq"
    source.write_text("")
    assert run_cli(arguments(source, tmp_path / "capture")) == 1


def test_query_builder_rejects_unsupported_graph():
    with pytest.raises(join.JoinError):
        join.query_for("https://example.org/graph", [WD])


@pytest.mark.parametrize("version", [True, 3.0, "3", 0, 4])
def test_result_schema_version_requires_an_exact_supported_integer(tmp_path, version):
    with pytest.raises(join.JoinError, match="unsupported join result schema"):
        join.write_results(
            Dataset(), QUERY, (tmp_path / "out", "2026-10-23"), schema_version=version
        )
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "field, kind, value",
    [
        ("s", "literal", "invalid"),
        ("p", "literal", "invalid"),
        ("o", "bnode", "blank"),
        ("o", "uri", "invalid"),
    ],
)
def test_response_boundary_rejects_invalid_rdf_terms(field, kind, value):
    binding = {
        "s": {"type": "uri", "value": WD},
        "p": {"type": "uri", "value": join.EXACT},
        "o": {"type": "uri", "value": TERM},
    }
    binding[field] = {"type": kind, "value": value}
    raw = json.dumps(
        {"head": {"vars": ["s", "p", "o"]}, "results": {"bindings": [binding]}}
    ).encode()
    with pytest.raises(join.JoinError):
        join.response_triples(raw)


def test_response_boundary_rejects_unexpected_projection():
    raw = b'{"head":{"vars":["x"]},"results":{"bindings":[]}}'
    with pytest.raises(join.JoinError):
        join.response_triples(raw)


@pytest.mark.parametrize(
    "fault",
    ["graph", "path", "unbounded", "query_contract", "subject", "predicate", "object", "label"],
)
def test_capture_contract_rejects_invalid_graph_response_or_query(tmp_path, fault):
    graph = join.UBERGRAPH if fault == "label" else join.MAPPINGS
    subject = TERM if fault == "label" else WD
    predicate = join.LABEL if fault == "label" else join.EXACT
    query = join.query_for(graph, [subject])
    binding = {
        "s": {"type": "uri", "value": subject},
        "p": {"type": "uri", "value": predicate},
        "o": {"type": "uri", "value": TERM},
    }
    if fault == "unbounded":
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
    if fault == "query_contract":
        query += "LIMIT 1\n"
    if fault == "subject":
        binding["s"]["value"] = "http://www.wikidata.org/entity/Q1"
    if fault == "predicate":
        binding["p"]["value"] = join.LABEL
    if fault == "object":
        binding["o"]["value"] = "http://example.org/term"
    raw = json.dumps(
        {"head": {"vars": ["s", "p", "o"]}, "results": {"bindings": [binding]}}
    ).encode()
    (tmp_path / "query.rq").write_bytes(query.encode())
    (tmp_path / "response.json").write_bytes(raw)
    capture = join.Capture(
        "https://example.org/graph" if fault == "graph" else graph,
        "../query.rq" if fault == "path" else "query.rq",
        "response.json",
        join.digest(query.encode()),
        join.digest(raw),
    )
    with pytest.raises(join.JoinError):
        join.add_captures(Dataset(), [capture], tmp_path)


def test_graph_without_join_keys_retains_failure(tmp_path):
    source = local_export(tmp_path)
    dataset = Dataset().parse(source, format="nquads")
    dataset.graph(URIRef(join.GRAPH)).remove(
        (None, URIRef(join.PREFIXES["skos"] + "closeMatch"), None)
    )
    dataset.serialize(source, format="nquads")
    out = tmp_path / "capture"
    assert run_cli(arguments(source, out)) == 1
    assert (out / "failure.json").is_file()


@pytest.mark.parametrize(
    "query",
    [
        "SELECT ?s WHERE { SERVICE <http://127.0.0.1:1/sparql> { ?s ?p ?o } }",
        "SELECT ?s FROM <http://127.0.0.1:1/data> WHERE { ?s ?p ?o }",
    ],
)
def test_offline_query_rejects_remote_loading_before_execution(tmp_path, query):
    path = tmp_path / "query.rq"
    path.write_text(query)
    with pytest.raises(join.JoinError, match="offline join query"):
        join.write_results(Dataset(), path, (tmp_path / "out", "2026-10-13"))


@pytest.mark.parametrize("query", ["invalid query", "ASK WHERE {}"])
def test_invalid_or_non_select_join_queries_report_typed_errors(tmp_path, query):
    path = tmp_path / "query.rq"
    path.write_text(query)
    with pytest.raises(join.JoinError):
        join.write_results(Dataset(), path, (tmp_path / "out", "2026-10-13"))


def test_local_export_rejects_foreign_named_graph_even_when_cognitive_exists(tmp_path):
    source = local_export(tmp_path)
    dataset = Dataset().parse(source, format="nquads")
    dataset.graph(URIRef(join.UBERGRAPH)).add((URIRef(TERM), URIRef(join.LABEL), Literal("forged")))
    dataset.serialize(source, format="nquads")
    with pytest.raises(join.JoinError, match="graph"):
        join.local_dataset(source)


@pytest.mark.parametrize("fault", ["count", "duplicate", "extra", "symlink"])
def test_replay_rejects_altered_inventory_and_metadata(tmp_path, fault):
    source = local_export(tmp_path)
    out = tmp_path / "capture"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, out) + ["--endpoint", endpoint]) == 0
    manifest = json.loads((out / "manifest.json").read_text())
    if fault == "count":
        manifest["requested_wikidata_keys"] = 999
    elif fault == "duplicate":
        manifest["captures"].append(manifest["captures"][0])
    elif fault == "extra":
        (out / "unrecorded.json").write_text("{}")
    else:
        response = out / "identifier-mappings-0000.json"
        response.rename(tmp_path / "preserved-response.json")
        response.symlink_to(tmp_path / "preserved-response.json")
    (out / "manifest.json").write_text(json.dumps(manifest))
    assert run_cli(arguments(source, tmp_path / "replay") + ["--replay", str(out)]) == 1


@pytest.mark.parametrize(
    "raw",
    [b"{}", b"[]", b"null", b"x" * (join.MAX_BYTES + 1)],
    ids=["object", "list", "null", "oversize"],
)
def test_response_parser_rejects_malformed_or_oversized_documents(tmp_path, raw):
    with pytest.raises(join.JoinError):
        join.response_triples(raw)


def historical_capture(tmp_path, version=1, extra_keys=()):
    """Construct the original source/projection contract, preserving old RDF roles."""
    dataset = Dataset()
    graph = dataset.graph(URIRef(join.GRAPH))
    rdf_type, skos = join.PREFIXES["rdf"] + "type", join.PREFIXES["skos"]
    graph.add((URIRef(PAGE), URIRef(rdf_type), URIRef(skos + "Concept")))
    graph.add((URIRef(PAGE), URIRef(skos + "prefLabel"), Literal("Cortisol")))
    for key in (WD, *extra_keys):
        graph.add((URIRef(PAGE), URIRef(skos + "closeMatch"), URIRef(key)))
    graph.add(
        (
            URIRef(PAGE),
            URIRef(join.PREFIXES["dcterms"] + "source"),
            URIRef("https://example.org/cortisol"),
        )
    )
    source = tmp_path / "legacy.nq"
    dataset.serialize(source, format="nquads")
    snapshot = tmp_path / "capture"
    snapshot.mkdir()
    keys = join._wikidata_subjects(dataset)
    with endpoint_server() as endpoint:
        captures = join.capture_stage(keys, join.MAPPINGS, (endpoint, snapshot))
        join.add_captures(dataset, captures, snapshot)
        external = sorted({str(o) for _, _, o in dataset.graph(URIRef(join.MAPPINGS))})
        label_captures = join.capture_stage(external, join.UBERGRAPH, (endpoint, snapshot))
        join.add_captures(dataset, label_captures, snapshot)
        captures += label_captures
    manifest = dict(
        observed_at="2026-10-20T12:00:00+00:00",
        endpoint=endpoint,
        local_sha256=join.sha256(source),
        join_query_sha256=join.sha256(LEGACY_QUERY),
        captures=[asdict(c) for c in captures],
        requested_wikidata_keys=len(keys),
        requested_obo_terms=len(external),
    )
    join.write_results(
        dataset,
        LEGACY_QUERY,
        (snapshot, manifest["observed_at"]),
        provenance=join._provenance(manifest),
        schema_version=version,
    )
    if version == 2:
        (snapshot / "join-query.rq").write_bytes(LEGACY_QUERY.read_bytes())
        manifest["schema_version"] = 2
        manifest["files"] = {
            name: join.sha256(snapshot / name) for name in sorted(join.file_inventory(snapshot))
        }
    (snapshot / "manifest.json").write_text(json.dumps(manifest))
    return source, snapshot


@pytest.mark.parametrize("version", [1, 2])
def test_original_capture_schema_remains_readable(tmp_path, version):
    source, snapshot = historical_capture(tmp_path, version)
    replay = tmp_path / "replay"
    assert run_cli(arguments(source, replay, LEGACY_QUERY) + ["--replay", str(snapshot)]) == 0
    assert json.loads((replay / "join-results.json").read_text())["rows"][0]["concept"] == PAGE


@pytest.mark.parametrize(
    "fault", ["page_concept", "page_mapping", "concept_source", "missing_about", "missing_subject"]
)
def test_new_capture_rejects_conflated_or_unlinked_source_models(tmp_path, fault):
    source = local_export(tmp_path)
    dataset = Dataset().parse(source, format="nquads")
    graph = dataset.graph(URIRef(join.GRAPH))
    if fault == "page_concept":
        graph.add(
            (
                URIRef(PAGE),
                URIRef(join.PREFIXES["rdf"] + "type"),
                URIRef(join.PREFIXES["skos"] + "Concept"),
            )
        )
    elif fault == "page_mapping":
        graph.remove((URIRef(CONCEPT), URIRef(join.EXACT), None))
        graph.add((URIRef(PAGE), URIRef(join.EXACT), URIRef(WD)))
    elif fault == "concept_source":
        graph.add(
            (
                URIRef(CONCEPT),
                URIRef(join.PREFIXES["dcterms"] + "source"),
                URIRef("https://example.org/cortisol"),
            )
        )
    else:
        graph.remove(
            (
                URIRef(PAGE),
                join.SCHEMA.about
                if fault == "missing_about"
                else URIRef(join.PREFIXES["dcterms"] + "subject"),
                None,
            )
        )
    dataset.serialize(source, format="nquads")
    out = tmp_path / "rejected"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, out) + ["--endpoint", endpoint]) == 1
    assert not out.exists()


def test_new_model_cannot_be_downgraded_to_historical_capture_schema(tmp_path):
    source = local_export(tmp_path)
    with pytest.raises(join.JoinError, match="historical capture schema"):
        join.write_results(
            join.local_dataset(source),
            LEGACY_QUERY,
            (tmp_path / "out", "2026-10-23"),
            schema_version=2,
        )


@pytest.mark.parametrize("fault", ["swap", "citation", "navigation", "guide"])
def test_schema3_admission_and_results_reject_forged_document_topic_pairs(tmp_path, fault):
    """Both admission paths reject paired forgeries before attributing a source."""
    source = local_export(tmp_path)
    dataset = Dataset().parse(source, format="nquads")
    graph = dataset.graph(URIRef(join.GRAPH))
    path = {
        "swap": "biology/symbiosis",
        "citation": "citations/smith_2022",
        "navigation": "biology/AGENTS",
        "guide": "biology/manual",
    }[fault]
    page, topic = (URIRef(join.GRAPH + role + path) for role in ("/page/", "/concept/"))
    graph.add((page, RDF.type, join.SCHEMA.CreativeWork))
    graph.add((page, DCTERMS.source, URIRef("https://example.org/" + path)))
    if fault == "navigation":
        graph.add((page, RDF.type, join.SCHEMA.CollectionPage))
    if fault in {"citation", "guide"}:
        graph.add((page, URIRef(join.GRAPH + "/vocab/pageType"), Literal(fault)))
    if fault == "swap":
        graph.add((topic, RDF.type, SKOS.Concept))
        graph.add((topic, SKOS.prefLabel, Literal("Symbiosis")))
        for predicate in (join.SCHEMA.about, DCTERMS.subject):
            graph.add((page, predicate, topic))
    dataset.serialize(source, format="nquads")
    join.local_dataset(source)
    dataset.graph(URIRef(join.MAPPINGS)).add((URIRef(WD), URIRef(join.EXACT), URIRef(TERM)))
    dataset.graph(URIRef(join.UBERGRAPH)).add(
        (URIRef(TERM), URIRef(join.LABEL), Literal("cortisol"))
    )
    accepted = tmp_path / "accepted"
    join.write_results(dataset, QUERY, (accepted, "2026-10-23"))
    rows = json.loads((accepted / "join-results.json").read_text())["rows"]
    assert rows[0]["page"] == PAGE
    assert rows[0]["source"] == "https://example.org/cortisol"
    if fault == "swap":
        for predicate in (join.SCHEMA.about, DCTERMS.subject):
            graph.remove((URIRef(PAGE), predicate, URIRef(CONCEPT)))
            graph.remove((page, predicate, topic))
            graph.add((URIRef(PAGE), predicate, topic))
            graph.add((page, predicate, URIRef(CONCEPT)))
    else:
        for triple in (
            (topic, RDF.type, SKOS.Concept),
            (topic, SKOS.prefLabel, Literal("Forged topic")),
            (topic, SKOS.inScheme, URIRef(join.GRAPH + "/scheme")),
            (page, join.SCHEMA.about, topic),
            (page, DCTERMS.subject, topic),
        ):
            graph.add(triple)
    # Keep the same graph for direct write_results; serialize local data separately.
    local = Dataset()
    local_graph = local.graph(URIRef(join.GRAPH))
    local_graph += graph
    local.serialize(source, format="nquads")
    with pytest.raises(join.JoinError, match="document|topic"):
        join.local_dataset(source)
    rejected = tmp_path / "rejected"
    with pytest.raises(join.JoinError, match="document|topic"):
        join.write_results(dataset, QUERY, (rejected, "2026-10-23"))
    assert not rejected.exists()


@pytest.mark.parametrize(
    "source_types,allowed",
    [
        ([BNode("concept")], False),
        ([BNode("renamed")], False),
        ([URIRef("https://example.org/concept")], False),
        ([Literal("concept"), BNode("concept")], False),
        ([Literal("concept")], True),
        ([], True),
    ],
)
def test_schema3_direct_results_check_page_type_terms_before_writing(
    tmp_path, source_types, allowed
):
    """Keep blank-node labels intact through the direct public generation boundary."""
    dataset = join.local_dataset(local_export(tmp_path))
    graph = dataset.graph(URIRef(join.GRAPH))
    for term in source_types:
        graph.add((URIRef(PAGE), URIRef(join.GRAPH + "/vocab/pageType"), term))
    dataset.graph(URIRef(join.MAPPINGS)).add((URIRef(WD), URIRef(join.EXACT), URIRef(TERM)))
    dataset.graph(URIRef(join.UBERGRAPH)).add(
        (URIRef(TERM), URIRef(join.LABEL), Literal("cortisol"))
    )
    output = tmp_path / "direct"
    if allowed:
        join.write_results(dataset, QUERY, (output, "2026-10-23"))
        rows = json.loads((output / "join-results.json").read_text())["rows"]
        assert len(rows) == 1
        assert rows[0]["page"] == PAGE
        assert rows[0]["source"] == "https://example.org/cortisol"
    else:
        with pytest.raises(join.JoinError, match="document-only page"):
            join.write_results(dataset, QUERY, (output, "2026-10-23"))
        assert not output.exists()


@pytest.mark.parametrize("fault", ["page", "source"])
def test_current_join_row_must_match_the_projected_document_source(tmp_path, fault):
    source = local_export(tmp_path)
    dataset = join.local_dataset(source)
    dataset.graph(URIRef(join.MAPPINGS)).add((URIRef(WD), URIRef(join.EXACT), URIRef(TERM)))
    dataset.graph(URIRef(join.UBERGRAPH)).add(
        (URIRef(TERM), URIRef(join.LABEL), Literal("cortisol"))
    )
    other_page = join.GRAPH + "/page/unrelated"
    graph = dataset.graph(URIRef(join.GRAPH))
    graph.add((URIRef(other_page), URIRef(join.PREFIXES["rdf"] + "type"), join.SCHEMA.CreativeWork))
    graph.add(
        (
            URIRef(other_page),
            URIRef(join.PREFIXES["dcterms"] + "source"),
            URIRef("https://example.org/cortisol"),
        )
    )
    values = dict(
        page=other_page if fault == "page" else PAGE,
        concept=CONCEPT,
        wikidata=WD,
        external=TERM,
        source="https://example.org/forged"
        if fault == "source"
        else "https://example.org/cortisol",
    )
    query = tmp_path / "swapped-document.rq"
    query.write_text(
        "SELECT "
        + " ".join(f"(<{value}> AS ?{key})" for key, value in values.items())
        + ' ("Cortisol" AS ?label) ("cortisol" AS ?externalLabel) WHERE {}'
    )
    with pytest.raises(join.JoinError, match="three named source graphs"):
        join.write_results(dataset, query, (tmp_path / "out", "2026-10-23"))


@pytest.mark.parametrize(
    "fault", ["results", "query", "metadata", "files", "schema", "missing_capture"]
)
@pytest.mark.parametrize("version", [2, 3])
def test_versioned_capture_binds_results_join_query_and_manifest_metadata(tmp_path, fault, version):
    query = LEGACY_QUERY if version == 2 else QUERY
    if version == 2:
        source, snapshot = historical_capture(tmp_path, 2)
    else:
        source = local_export(tmp_path)
        snapshot = tmp_path / "capture"
        with endpoint_server() as endpoint:
            assert run_cli(arguments(source, snapshot) + ["--endpoint", endpoint]) == 0
    manifest = json.loads((snapshot / "manifest.json").read_text())
    if fault in {"results", "query"}:
        path = snapshot / ("join-results.json" if fault == "results" else "join-query.rq")
        path.write_bytes(path.read_bytes() + b"\n")
    elif fault == "metadata":
        manifest["observed_at"] = "2000-01-01T00:00:00+00:00"
    elif fault == "files":
        del manifest["files"]["join-results.md"]
    elif fault == "schema":
        manifest["schema_version"] = 999
    else:
        manifest["captures"].pop()
    (snapshot / "manifest.json").write_text(json.dumps(manifest))
    assert run_cli(arguments(source, tmp_path / "replay", query) + ["--replay", str(snapshot)]) == 1


def test_legacy_replay_requires_even_empty_response_batches(tmp_path):
    source, snapshot = historical_capture(
        tmp_path, extra_keys=[f"http://www.wikidata.org/entity/Q{n}" for n in range(1, 102)]
    )
    manifest = json.loads((snapshot / "manifest.json").read_text())
    assert manifest["requested_wikidata_keys"] == 102
    missing = manifest["captures"].pop(1)
    for field in ("query_file", "response_file"):
        path = snapshot / missing[field]
        path.rename(tmp_path / path.name)
    (snapshot / "manifest.json").write_text(json.dumps(manifest))
    assert (
        run_cli(arguments(source, tmp_path / "replay", LEGACY_QUERY) + ["--replay", str(snapshot)])
        == 1
    )


@pytest.mark.parametrize("subjects", [[], [WD, WD], [WD] * 101])
def test_capture_query_requires_bounded_nonempty_unique_subjects(subjects):
    with pytest.raises(join.JoinError):
        join.query_for(join.MAPPINGS, subjects)


def test_query_cannot_present_constant_rows_as_a_successful_join(tmp_path):
    source = local_export(tmp_path)
    query = tmp_path / "forged-query.rq"
    values = {
        "page": PAGE,
        "concept": CONCEPT,
        "wikidata": WD,
        "external": TERM,
        "source": "https://example.org/cortisol",
    }
    query.write_text(
        "SELECT "
        + " ".join(f"(<{value}> AS ?{key})" for key, value in values.items())
        + ' ("Cortisol" AS ?label) ("invented" AS ?externalLabel) WHERE {}'
    )
    with pytest.raises(join.JoinError, match="three named source graphs"):
        join.write_results(join.local_dataset(source), query, (tmp_path / "out", "2026-10-20"))


def test_rehashed_result_changes_still_fail_recomputation(tmp_path):
    source = local_export(tmp_path)
    snapshot = tmp_path / "capture"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, snapshot) + ["--endpoint", endpoint]) == 0
    path = snapshot / "join-results.json"
    result = json.loads(path.read_text())
    result["joined_rows"] = 999
    path.write_text(json.dumps(result, indent=2) + "\n")
    manifest = json.loads((snapshot / "manifest.json").read_text())
    manifest["files"]["join-results.json"] = join.digest(path.read_bytes())
    (snapshot / "manifest.json").write_text(json.dumps(manifest))
    assert run_cli(arguments(source, tmp_path / "replay") + ["--replay", str(snapshot)]) == 1


def test_replay_cannot_overwrite_its_original_capture(tmp_path):
    source = local_export(tmp_path)
    snapshot = tmp_path / "capture"
    with endpoint_server() as endpoint:
        assert run_cli(arguments(source, snapshot) + ["--endpoint", endpoint]) == 0
    original = (snapshot / "manifest.json").read_bytes()
    assert run_cli(arguments(source, snapshot) + ["--replay", str(snapshot)]) == 1
    assert (snapshot / "manifest.json").read_bytes() == original


@pytest.mark.parametrize(
    "fault", ["bindings", "binding", "value", "language", "datatype", "both", "duplicate_json"]
)
def test_response_schema_rejects_malformed_terms_without_rdflib_fallback(fault):
    binding = {
        "s": {"type": "uri", "value": WD},
        "p": {"type": "uri", "value": join.EXACT},
        "o": {"type": "literal", "value": "label"},
    }
    payload = {"head": {"vars": ["s", "p", "o"]}, "results": {"bindings": [binding]}}
    if fault == "bindings":
        payload["results"]["bindings"] = {}
    elif fault == "binding":
        binding["extra"] = {"type": "uri", "value": TERM}
    elif fault == "value":
        binding["o"]["value"] = 42
    elif fault == "language":
        binding["o"]["xml:lang"] = "bad language"
    elif fault == "datatype":
        binding["o"]["datatype"] = None
    elif fault == "both":
        binding["o"].update(
            {"datatype": "http://www.w3.org/2001/XMLSchema#string", "xml:lang": "en"}
        )
    raw = json.dumps(payload).encode()
    if fault == "duplicate_json":
        raw = b'{"head":{},"head":{},"results":{}}'
    with pytest.raises(join.JoinError):
        join.response_triples(raw)
