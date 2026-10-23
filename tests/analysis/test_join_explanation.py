"""Real-file, RDF/SPARQL and local-HTTP controls for offline support evidence."""

import json
import shutil
import subprocess
import sys
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from rdflib import BNode, Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS, XSD

from daf_okn.analysis import cross_graph as join
from daf_okn.analysis.join_explanation import ExplainOptions, explain_join
from daf_okn.cli import main
from daf_okn.core.join_evidence import EvidenceError
from daf_okn.core.rdf import SCHEMA

QUERY = Path(__file__).parents[1] / "fixtures/cross_graph_obo_v3.rq"
CONCEPT = URIRef(join.GRAPH + "/concept/diagnostic/topic")
PAGE = URIRef(join.GRAPH + "/page/diagnostic/topic")
WD1 = URIRef("http://www.wikidata.org/entity/Q101")
WD2 = URIRef("http://www.wikidata.org/entity/Q102")
EXTERNAL = URIRef(join.OBO + "TEST_0001")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def review(graph, number, subject, predicate, target):
    statement = URIRef(join.GRAPH + f"/mapping/review-{number}")
    for p, o in (
        (RDF.type, RDF.Statement),
        (RDF.subject, subject),
        (RDF.predicate, predicate),
        (RDF.object, target),
        (DCTERMS.source, URIRef(f"https://example.org/review/{number}")),
        (DCTERMS.description, Literal(f"Review {number}", lang="en")),
        (DCTERMS.date, Literal("2026-10-23", datatype=XSD.date)),
    ):
        graph.add((statement, p, o))
    return statement


def create_capture(root, *, numeric=False, duplicates=False, empty_batch=False):
    """Capture actual SPARQL results from a local server; then stop that server."""
    inputs = root / "inputs"
    inputs.mkdir(parents=True)
    source, query, capture = inputs / "source.nq", inputs / "join.rq", inputs / "capture"
    query.write_bytes(QUERY.read_bytes())
    local, remote = Dataset(), Dataset()
    graph = local.graph(URIRef(join.GRAPH))
    for triple in (
        (CONCEPT, RDF.type, SKOS.Concept),
        (PAGE, RDF.type, SCHEMA.CreativeWork),
        (PAGE, SCHEMA.about, CONCEPT),
        (PAGE, DCTERMS.subject, CONCEPT),
        (PAGE, DCTERMS.source, URIRef("https://example.org/topic.md")),
    ):
        graph.add(triple)
    for language in ("en", "fr"):
        graph.add((CONCEPT, SKOS.prefLabel, Literal("Diagnostic", lang=language)))
        label = (
            Literal("01", datatype=XSD.integer, normalize=False)
            if numeric
            else Literal("Diagnostic", lang=language)
        )
        remote.graph(URIRef(join.UBERGRAPH)).add((EXTERNAL, RDFS.label, label))
    for number, wd, relation in (
        (1, WD1, SKOS.closeMatch),
        (2, WD1, SKOS.closeMatch),
        (3, WD2, SKOS.exactMatch),
    ):
        graph.add((CONCEPT, relation, wd))
        review(graph, number, CONCEPT, relation, wd)
        remote.graph(URIRef(join.MAPPINGS)).add((wd, SKOS.exactMatch, EXTERNAL))
    # A same-concept direct OBO review must never attach to the Wikidata edge.
    graph.add((CONCEPT, SKOS.exactMatch, EXTERNAL))
    review(graph, "obo", CONCEPT, SKOS.exactMatch, EXTERNAL)
    if empty_batch:
        for number in range(200, 300):
            target = URIRef(f"http://www.wikidata.org/entity/Q{number}")
            graph.add((CONCEPT, SKOS.exactMatch, target))
            review(graph, number, CONCEPT, SKOS.exactMatch, target)
    local.serialize(source, format="nquads")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            text = parse_qs(urlsplit(self.path).query)["query"][0]
            raw = remote.query(text).serialize(format="json")
            payload = json.loads(raw)
            if duplicates:
                payload["results"]["bindings"] *= 2
            raw = json.dumps(payload).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        join.run(join.JoinOptions(source, query, capture, f"http://127.0.0.1:{server.server_port}"))
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    return ExplainOptions(source, query, capture, root / "support")


@pytest.fixture(scope="module")
def captured_variants(tmp_path_factory):
    root = tmp_path_factory.mktemp("join-support-baselines")
    return {
        name: create_capture(root / name, **kwargs)
        for name, kwargs in (
            ("normal", {}),
            ("numeric", {"numeric": True}),
            ("duplicate", {"duplicates": True}),
            ("empty", {"empty_batch": True}),
        )
    }


@pytest.fixture
def options(tmp_path, captured_variants):
    original = captured_variants["normal"]
    shutil.copytree(original.source.parent, tmp_path / "inputs")
    return ExplainOptions(
        tmp_path / "inputs/source.nq",
        tmp_path / "inputs/join.rq",
        tmp_path / "inputs/capture",
        tmp_path / "support",
    )


def support(options):
    return json.loads((options.output / "join-support.json").read_text())


def rebind(options, *, rebuild=True):
    """Rebind deliberate fixture changes; never change historical/canonical files."""
    manifest_path = options.capture / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["local_sha256"] = join.sha256(options.source)
    manifest["join_query_sha256"] = join.sha256(options.query)
    for record in manifest["captures"]:
        for key in ("query", "response"):
            record[key + "_sha256"] = join.sha256(options.capture / record[key + "_file"])
    if rebuild:
        dataset = join.local_dataset(options.source)
        join.add_captures(
            dataset, [join.Capture(**c) for c in manifest["captures"]], options.capture
        )
        evaluation = join.evaluate_results(
            dataset,
            options.query,
            (options.output, manifest["observed_at"]),
            provenance=join._provenance(manifest),
        )
        (options.capture / "join-results.json").write_bytes(evaluation.json_bytes)
        (options.capture / "join-results.md").write_bytes(evaluation.markdown_bytes)
    else:
        result_path = options.capture / "join-results.json"
        result = json.loads(result_path.read_text())
        result["provenance"] = join._provenance(manifest)
        write_json(result_path, result)
    manifest["files"] = {
        name: join.sha256(options.capture / name)
        for name in sorted(join.file_inventory(options.capture))
        if name != "manifest.json"
    }
    write_json(manifest_path, manifest)


def test_multilingual_paths_preserve_bags_reviews_and_parent_bytes(options):
    # Given eight RDF solutions projected into two indistinguishable scalar groups.
    before = {p: p.read_bytes() for p in options.source.parent.rglob("*") if p.is_file()}
    # When explaining the verified capture after its HTTP server has stopped.
    explain_join(options)
    # Then every index and compatible language survives, with no review multiplication.
    result = support(options)
    assert result["joined_rows"] == result["typed_solution_count"] == 8
    assert len(result["groups"]) == 2
    assert sorted(i for g in result["groups"] for i in g["row_indices"]) == list(range(8))
    reviews = set()
    for group in result["groups"]:
        assert len(group["row_indices"]) == sum(s["multiplicity"] for s in group["solutions"]) == 4
        assert len(group["solutions"]) == 4
        assert {
            (s["bindings"]["label"]["xml:lang"], s["bindings"]["externalLabel"]["xml:lang"])
            for s in group["solutions"]
        } == {("en", "en"), ("en", "fr"), ("fr", "en"), ("fr", "fr")}
        expected_predicate = str(
            SKOS.closeMatch if group["values"]["wikidata"] == str(WD1) else SKOS.exactMatch
        )
        for solution in group["solutions"]:
            (mapping,) = solution["local"]["mappings"]
            assert mapping["assertion"]["p"]["value"] == expected_predicate
            reviews.update(r["statement"]["value"] for r in mapping["reviews"])
            for name, graph in (
                ("remote_mapping", join.MAPPINGS),
                ("remote_label", join.UBERGRAPH),
            ):
                for occurrence in solution[name]["occurrences"]:
                    raw = json.loads((options.capture / occurrence["response_file"]).read_text())
                    assert (
                        occurrence["raw"] == raw["results"]["bindings"][occurrence["binding_index"]]
                    )
                    assert occurrence["graph"] == graph
                    assert occurrence["response_sha256"] == join.sha256(
                        options.capture / occurrence["response_file"]
                    )
    assert reviews == {join.GRAPH + f"/mapping/review-{i}" for i in (1, 2, 3)}
    assert all(p.read_bytes() == raw for p, raw in before.items())


def test_readonly_check_recomputes_identical_bytes_without_writes(options):
    # Given published support.
    explain_join(options)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in options.output.iterdir()}
    # When checking offline.
    explain_join(replace(options, check=True))
    # Then no artifact is touched, and repeat derivation is deterministic.
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in options.output.iterdir()}
    second = replace(options, output=options.output.with_name("support-second"))
    explain_join(second)
    assert {p.name: p.read_bytes() for p in second.output.iterdir()} == {
        p.name: p.read_bytes() for p in options.output.iterdir()
    }


@pytest.mark.parametrize("fault", ["indices", "review", "origin", "missing", "extra", "nested"])
def test_check_rejects_self_rehashed_semantic_or_inventory_tampering(options, fault):
    # Given support whose own hashes an adversary can rewrite.
    explain_join(options)
    path = options.output / "join-support.json"
    result = json.loads(path.read_text())
    if fault == "indices":
        result["groups"][0]["row_indices"][0] = 999
    elif fault == "review":
        result["groups"][0]["solutions"][0]["local"]["mappings"][0]["reviews"] = []
    elif fault == "origin":
        result["groups"][0]["solutions"][0]["remote_label"]["occurrences"][0]["binding_index"] = 999
    elif fault == "missing":
        (options.output / "join-support.md").unlink()
    elif fault == "extra":
        (options.output / "extra.json").write_text("{}")
    else:
        (options.output / "nested").mkdir()
    if fault in {"indices", "review", "origin"}:
        write_json(path, result)
        manifest = json.loads((options.output / "support-manifest.json").read_text())
        manifest["files"][path.name] = join.sha256(path)
        write_json(options.output / "support-manifest.json", manifest)
    # When checked against the parent inputs, then tampering cannot certify itself.
    with pytest.raises(EvidenceError):
        explain_join(replace(options, check=True))


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "orphan",
        "subject",
        "predicate",
        "object",
        "date",
        "rationale",
        "multivalue",
        "conflict",
        "blank",
        "normalization",
    ],
)
def test_bad_local_reviews_fail_before_publication_even_with_rebound_capture(options, fault):
    # Given a real RDF source with a deliberately invalid review profile.
    dataset = join.local_dataset(options.source)
    graph = dataset.graph(URIRef(join.GRAPH))
    statement = URIRef(join.GRAPH + "/mapping/review-1")
    if fault == "missing":
        for s in (statement, URIRef(join.GRAPH + "/mapping/review-2")):
            graph.remove((s, None, None))
    elif fault == "orphan":
        review(graph, "orphan", CONCEPT, SKOS.exactMatch, URIRef(join.OBO + "ABSENT_1"))
    elif fault in {"subject", "predicate", "object", "date", "rationale"}:
        predicate, value = {
            "subject": (RDF.subject, PAGE),
            "predicate": (RDF.predicate, SKOS.exactMatch),
            "object": (RDF.object, WD2),
            "date": (DCTERMS.date, Literal("not-a-date")),
            "rationale": (DCTERMS.description, Literal(" ")),
        }[fault]
        graph.set((statement, predicate, value))
    elif fault == "multivalue":
        graph.add((statement, DCTERMS.source, URIRef("https://example.org/other")))
    elif fault == "conflict":
        graph.add((CONCEPT, SKOS.exactMatch, WD1))
        review(graph, "conflict", CONCEPT, SKOS.exactMatch, WD1)
    elif fault == "blank":
        for p, o in list(graph.predicate_objects(statement)):
            graph.add((BNode("review"), p, o))
        graph.remove((statement, None, None))
    else:
        graph.add((PAGE, DCTERMS.description, Literal("01", datatype=XSD.integer, normalize=False)))
    dataset.serialize(options.source, format="nquads")
    rebind(options)
    # When explaining, then no support directory or partial report is published.
    expected = {
        "normalization": "local literal lexical normalization",
        "blank": "blank-node profile",
    }.get(fault, "invalid local review semantics")
    with pytest.raises(ValueError, match=expected):
        explain_join(options)
    assert not options.output.exists()


def test_raw_lexical_normalization_is_exposed(captured_variants, tmp_path):
    # Given raw remote integer lexical 01, materialized by the established join as 1.
    options = replace(captured_variants["numeric"], output=tmp_path / "support")
    # When explaining, then both terms and their difference remain inspectable.
    explain_join(options)
    occurrence = support(options)["groups"][0]["solutions"][0]["remote_label"]["occurrences"][0]
    assert occurrence["raw"]["o"]["value"] == "01"
    assert occurrence["materialized"]["o"]["value"] == "1"
    assert occurrence["lexical_or_metadata_changed"] is True


def test_duplicate_raw_occurrences_do_not_multiply_solutions(captured_variants, tmp_path):
    # Given two raw occurrences for every asserted remote triple.
    options = replace(captured_variants["duplicate"], output=tmp_path / "support")
    # When explained, then graph and solution counts remain eight, with both origins.
    explain_join(options)
    result = support(options)
    assert result["joined_rows"] == result["typed_solution_count"] == 8
    for group in result["groups"]:
        for solution in group["solutions"]:
            for name in ("remote_mapping", "remote_label"):
                occurrences = solution[name]["occurrences"]
                assert len(occurrences) == len({o["binding_index"] for o in occurrences}) == 2


@pytest.mark.parametrize(
    "fault",
    [
        "graph",
        "predicate",
        "subject",
        "label",
        "result",
        "reordered",
        "omitted",
        "extra",
        "query",
        "hash",
    ],
)
def test_bad_capture_is_rejected_before_support(options, fault):
    # Given a copied capture with a deliberate origin/semantic/inventory fault.
    manifest_path = options.capture / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    record = manifest["captures"][0 if fault != "label" else 1]
    if fault in {"predicate", "subject", "label"}:
        path = options.capture / record["response_file"]
        raw = json.loads(path.read_text())
        binding = raw["results"]["bindings"][0]
        key, value = {
            "predicate": ("p", str(SKOS.closeMatch)),
            "subject": ("s", str(WD2) + "0"),
            "label": ("o", "Forged label"),
        }[fault]
        binding[key]["value"] = value
        write_json(path, raw)
        rebind(options, rebuild=False)
    elif fault == "result":
        path = options.capture / "join-results.json"
        result = json.loads(path.read_text())
        result["rows"][0]["label"] = "Forged"
        write_json(path, result)
        rebind(options, rebuild=False)
    elif fault == "extra":
        (options.capture / "extra.json").write_text("{}")
    elif fault == "query":
        options.query.write_text(options.query.read_text() + "\n")
    elif fault == "hash":
        (options.capture / record["response_file"]).write_text("{}")
    else:
        if fault == "graph":
            manifest["captures"][0]["graph"] = join.UBERGRAPH
        elif fault == "reordered":
            manifest["captures"].reverse()
        else:
            manifest["captures"].pop()
        write_json(manifest_path, manifest)
        rebind(options, rebuild=False)
    # When explaining, then independently rebound hashes do not bypass replay.
    expected = {
        "graph": "omits or reorders",
        "reordered": "omits or reorders",
        "predicate": "outside the requested subject/predicate",
        "subject": "outside the requested subject/predicate",
        "label": "captured result differs from recomputed join",
        "result": "captured result differs from recomputed join",
    }.get(fault)
    with pytest.raises(ValueError, match=expected):
        explain_join(options)
    assert not options.output.exists()


def test_required_empty_batch_cannot_be_omitted(captured_variants, tmp_path):
    # Given a real capture with a requested batch returning zero bindings.
    original = captured_variants["empty"]
    shutil.copytree(original.source.parent, tmp_path / "inputs")
    options = ExplainOptions(
        tmp_path / "inputs/source.nq",
        tmp_path / "inputs/join.rq",
        tmp_path / "inputs/capture",
        tmp_path / "support",
    )
    manifest = json.loads((options.capture / "manifest.json").read_text())
    empty = next(
        c
        for c in manifest["captures"]
        if not json.loads((options.capture / c["response_file"]).read_text())["results"]["bindings"]
    )
    manifest["captures"].remove(empty)
    for key in ("query_file", "response_file"):
        (options.capture / empty[key]).unlink()
        del manifest["files"][empty[key]]
    write_json(options.capture / "manifest.json", manifest)
    rebind(options, rebuild=False)
    # When explaining, then even a hash-consistent inventory cannot omit the request.
    with pytest.raises(ValueError, match="omits or reorders"):
        explain_join(options)
    assert not options.output.exists()


def test_complete_empty_batch_is_retained_in_origin_catalog(captured_variants, tmp_path):
    # Given a complete capture including an empty requested batch.
    options = replace(captured_variants["empty"], output=tmp_path / "support")
    # When explained, then empty requests remain explicit in the bound catalog.
    explain_join(options)
    catalog = support(options)["origin"]["captures"]
    assert len(catalog) == 3
    assert any(
        not json.loads((options.capture / c["response_file"]).read_text())["results"]["bindings"]
        for c in catalog
    )


def test_one_to_many_remote_mappings_keep_every_target_and_label(options):
    # Given a second returned external target for the first Wikidata key.
    manifest_path = options.capture / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mapping_record, label_record = manifest["captures"]
    mapping_path = options.capture / mapping_record["response_file"]
    payload = json.loads(mapping_path.read_text())
    other = str(EXTERNAL) + "0"
    payload["results"]["bindings"].append(
        {
            "s": {"type": "uri", "value": str(WD1)},
            "p": {"type": "uri", "value": str(SKOS.exactMatch)},
            "o": {"type": "uri", "value": other},
        }
    )
    write_json(mapping_path, payload)
    label_path = options.capture / label_record["response_file"]
    labels = json.loads(label_path.read_text())
    for language in ("en", "fr"):
        labels["results"]["bindings"].append(
            {
                "s": {"type": "uri", "value": other},
                "p": {"type": "uri", "value": str(RDFS.label)},
                "o": {"type": "literal", "value": "Alternative", "xml:lang": language},
            }
        )
    write_json(label_path, labels)
    (options.capture / label_record["query_file"]).write_text(
        join.query_for(join.UBERGRAPH, sorted([str(EXTERNAL), other]))
    )
    manifest["requested_obo_terms"] = 2
    write_json(manifest_path, manifest)
    rebind(options)
    # When explained, then neither mapping nor any language alternative is ranked away.
    explain_join(options)
    result = support(options)
    assert result["joined_rows"] == result["typed_solution_count"] == 12
    assert len(result["groups"]) == 3
    assert {g["values"]["external"] for g in result["groups"]} == {str(EXTERNAL), other}


@pytest.mark.parametrize("changed", ["source", "query", "manifest"])
def test_inputs_changed_during_real_derivation_cannot_publish(options, changed):
    # Given a deterministic adversary changing an actual input at projection entry.
    # Profiling observes calls; it substitutes no function or algorithm output.
    target = {
        "source": options.source,
        "query": options.query,
        "manifest": options.capture / "manifest.json",
    }[changed]
    previous = sys.getprofile()
    altered = False

    def change_file(frame, event, _argument):
        nonlocal altered
        if not altered and event == "call" and frame.f_code.co_name == "build_support":
            target.write_bytes(target.read_bytes() + b"\n")
            altered = True

    # When all real validators/derivation execute, then the final byte check fails.
    sys.setprofile(change_file)
    try:
        with pytest.raises(EvidenceError, match="changed during derivation"):
            explain_join(options)
    finally:
        sys.setprofile(previous)
    assert altered and not options.output.exists()


@pytest.mark.parametrize(
    "fault", ["missing_source", "source_symlink", "capture_symlink", "alias", "size"]
)
def test_input_boundaries_are_real_rejecting_gates(options, tmp_path, fault):
    # Given a missing, linked, aliased or oversized input.
    if fault == "missing_source":
        options = replace(options, source=options.source.with_name("absent.nq"))
    elif fault == "source_symlink":
        alias = options.source.with_name("alias.nq")
        alias.symlink_to(options.source)
        options = replace(options, source=alias)
    elif fault == "capture_symlink":
        alias = options.capture.with_name("alias-capture")
        alias.symlink_to(options.capture, target_is_directory=True)
        options = replace(options, capture=alias)
    elif fault == "alias":
        options.query.unlink()
        options.query.hardlink_to(options.capture / "join-query.rq")
    else:
        with options.source.open("ab") as stream:
            stream.write(b" " * (32 * 1024 * 1024))
    # When invoked, then failure occurs without acquisition or partial support.
    with pytest.raises((ValueError, OSError)):
        explain_join(options)
    assert not options.output.exists()


@pytest.mark.parametrize(
    "fault",
    [
        "existing",
        "nested_capture",
        "source_tree",
        "query_tree",
        "ancestor",
        "symlink",
        "symlink_parent",
        "escaping",
        "absent_check",
    ],
)
def test_output_boundary_rejects_unsafe_destinations(options, tmp_path, fault):
    # Given an unsafe or colliding output destination.
    if fault == "existing":
        options.output.mkdir()
    elif fault == "nested_capture":
        options = replace(options, output=options.capture / "support")
    elif fault in {"source_tree", "query_tree"}:
        options = replace(options, output=options.source.parent / "support")
    elif fault == "ancestor":
        options = replace(options, output=tmp_path)
    elif fault == "symlink":
        options.output.symlink_to(tmp_path / "elsewhere")
    elif fault == "symlink_parent":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        options = replace(options, output=alias / "support")
    elif fault == "escaping":
        options = replace(options, output=tmp_path / "unused/../support")
    else:
        options = replace(options, check=True)
    # When invoked, then the boundary rejects without support files.
    with pytest.raises(ValueError):
        explain_join(options)
    assert not (options.output / "join-support.json").exists()


def test_cli_is_offline_and_check_is_available(options):
    # Given inputs from a server that is already stopped.
    arguments = [
        "explain-join",
        "--source",
        str(options.source),
        "--query",
        str(options.query),
        "--capture",
        str(options.capture),
        "--output",
        str(options.output),
    ]
    # When driving the actual CLI in a fresh interpreter.
    result = subprocess.run(
        [sys.executable, "-m", "daf_okn", *arguments], capture_output=True, text=True
    )
    # Then publication and read-only CLI verification succeed without acquisition.
    assert result.returncode == 0, result.stderr
    assert main(arguments + ["--check"]) == 0


@pytest.mark.parametrize("version", [1, 2])
def test_explanations_reject_historical_schemas(options, version):
    # Given a structurally valid historical source/capture from the old real harness.
    from test_cross_graph import LEGACY_QUERY, historical_capture

    legacy_root = options.output.parent / "legacy"
    legacy_root.mkdir()
    source, capture = historical_capture(legacy_root, version)
    # When asking the first explanation profile to consume it.
    with pytest.raises(EvidenceError, match="schema 3"):
        explain_join(ExplainOptions(source, LEGACY_QUERY, capture, options.output))
    # Then existing replay support is unaffected, with no explanation output.
    assert not options.output.exists()
