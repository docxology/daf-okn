import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from rdflib import Dataset, Literal, URIRef

from daf_okn.analysis import cross_graph as join
from daf_okn.cli import main as run_cli

QUERY = Path(__file__).resolve().parents[2] / "tests/fixtures/cross_graph_obo.rq"
WD = "http://www.wikidata.org/entity/Q190875"
TERM = join.OBO + "CHEBI_17650"
PAGE = join.GRAPH + "/page/biology/cortisol"


def local_export(tmp_path):
    dataset = Dataset()
    graph = dataset.graph(URIRef(join.GRAPH))
    graph.add(
        (
            URIRef(PAGE),
            URIRef(join.PREFIXES["rdf"] + "type"),
            URIRef(join.PREFIXES["skos"] + "Concept"),
        )
    )
    graph.add((URIRef(PAGE), URIRef(join.PREFIXES["skos"] + "prefLabel"), Literal("Cortisol")))
    graph.add((URIRef(PAGE), URIRef(join.PREFIXES["skos"] + "closeMatch"), URIRef(WD)))
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


def arguments(source, out):
    return ["join", "--source", str(source), "--query", str(QUERY), "--output", str(out)]


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
    assert result["rows"][0]["concept"] == PAGE
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
    graph.add((URIRef(PAGE), URIRef(join.EXACT), URIRef(WD)))
    graph.add((URIRef(PAGE), URIRef(join.EXACT), URIRef(TERM)))
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
