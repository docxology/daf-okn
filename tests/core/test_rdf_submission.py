import hashlib
import json
import os
import subprocess

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from daf_okn.cli import main
from daf_okn.core import rdf_submission as submission
from daf_okn.core.rdf import SCHEMA


@pytest.mark.parametrize("payload", [b"", b"x" * (2 * 1024 * 1024 + 9)])
def test_streaming_file_hash_matches_independent_sha256(tmp_path, payload):
    path = tmp_path / "payload.bin"
    path.write_bytes(payload)
    assert submission.sha256(path) == hashlib.sha256(payload).hexdigest()


GRAPH = "https://purl.org/okn/frink/kg/cognitive-kb"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"


def source_repo(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "--allow-empty",
            "-qm",
            "source",
        ],
        check=True,
    )
    docs = root / "docs/okn"
    docs.mkdir(parents=True)
    for name in (
        "graph_description.md",
        "vocabulary.md",
        "submission_criteria.md",
        "interoperability.md",
        "landing_zone.md",
        "alignment-review.md",
        "entity-model.md",
        "keyword-curation-2026-10-23.md",
    ):
        (docs / name).write_text("Documentation\n")
    (root / "LICENSE-KNOWLEDGE-BASE.md").write_text(LICENSE)
    (root / "README.md").write_text("# Source repository\n")
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        (root / name).write_text("Source environment fixture\n")
    (root / "knowledge_base").mkdir()
    (root / "knowledge_base/example.md").write_text("# Example\n")
    (root / "code/scripts").mkdir(parents=True)
    for name in ("export_rdf.py", "rdf_alignment.py"):
        (root / "code/scripts" / name).write_text(
            "import rdf_alignment\n" if name == "export_rdf.py" else ""
        )
    (root / "code/resolution.md").write_text("# Code reference aliases\n")
    (docs / "registry_entry.md").write_text(
        "````markdown\n---\nshortname: cognitive-kb\n---\n\nCC BY 4.0\n````\n"
    )
    queries = docs / "queries"
    queries.mkdir()
    for name in (
        "concept_mappings.rq",
        "citation_identifiers.rq",
        "cross_graph_obo.rq",
        "mapping_evidence.rq",
        "keyword_concepts.rq",
        "relation_scopes.rq",
        "document_topics.rq",
    ):
        (queries / name).write_text("SELECT ?s WHERE { ?s ?p ?o }\n")
    export = root / "output/okn"
    export.mkdir(parents=True)
    dataset = Dataset()
    graph = dataset.graph(URIRef(GRAPH))
    graph.add((URIRef(GRAPH + "/dataset"), DCTERMS.license, URIRef(LICENSE)))
    graph.add((URIRef(GRAPH + "/scheme"), DCTERMS.license, URIRef(LICENSE)))
    graph.add((URIRef(GRAPH + "/page/example"), DCTERMS.title, Literal("Example")))
    graph.add((URIRef(GRAPH + "/page/example"), RDF.type, SCHEMA.CreativeWork))
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    graph.serialize(export / "cognitive-kb.ttl", format="turtle")
    refresh_manifest(export)
    return root


def refresh_manifest(export):
    root = export.parents[1]
    resolution_files = {
        path.relative_to(root).as_posix() for path in root.iterdir() if path.is_file()
    }
    for directory in ("knowledge_base", "docs", "code"):
        resolution_files.update(
            path.relative_to(root).as_posix()
            for path in (root / directory).rglob("*")
            if path.is_file()
        )
    source_paths = {
        root / name
        for name in resolution_files
        if name.casefold().endswith(".md")
        or name in {"pyproject.toml", "uv.lock", ".python-version"}
    } | {root / "code/scripts/export_rdf.py", root / "code/scripts/rdf_alignment.py"}
    manifest = {
        "graph": GRAPH,
        "license": LICENSE,
        "resolution_files": sorted(resolution_files),
        "sources": {
            path.relative_to(root).as_posix(): submission.sha256(path)
            for path in sorted(source_paths)
        },
        "artifacts": {
            name: submission.sha256(export / name)
            for name in ("cognitive-kb.nq", "cognitive-kb.ttl")
        },
    }
    (export / "manifest.json").write_text(json.dumps(manifest))


def add_topic(graph):
    page, topic = URIRef(GRAPH + "/page/example"), URIRef(GRAPH + "/concept/example")
    graph.add((topic, RDF.type, SKOS.Concept))
    graph.add((topic, SKOS.prefLabel, Literal("Example")))
    graph.add((page, SCHEMA.about, topic))
    graph.add((page, DCTERMS.subject, topic))
    return topic


@pytest.mark.parametrize("fault", ["swap", "citation", "navigation", "guide"])
def test_rehashed_export_and_bundle_reject_wrong_topic_ownership_and_roles(tmp_path, fault):
    """Current sources and refreshed hashes cannot bless semantically forged pairs."""
    root = source_repo(tmp_path)
    export = root / "output/okn"
    dataset = Dataset().parse(export / "cognitive-kb.nq", format="nquads")
    graph = dataset.graph(URIRef(GRAPH))
    first = add_topic(graph)
    second_path = {
        "swap": "other",
        "citation": "citations/smith_2022",
        "navigation": "biology/AGENTS",
        "guide": "biology/manual",
    }[fault]
    page, topic = (URIRef(GRAPH + role + second_path) for role in ("/page/", "/concept/"))
    graph.add((page, RDF.type, SCHEMA.CreativeWork))
    graph.add((page, DCTERMS.source, URIRef("https://example.org/" + second_path)))
    if fault == "navigation":
        graph.add((page, RDF.type, SCHEMA.CollectionPage))
    if fault in {"citation", "guide"}:
        graph.add((page, URIRef(GRAPH + "/vocab/pageType"), Literal(fault)))
    if fault == "swap":
        graph.add((topic, RDF.type, SKOS.Concept))
        graph.add((topic, SKOS.prefLabel, Literal("Other")))
        for predicate in (SCHEMA.about, DCTERMS.subject):
            graph.add((page, predicate, topic))
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    graph.serialize(export / "cognitive-kb.ttl", format="turtle")
    refresh_manifest(export)
    assert submission.validate_export(export, root) == []
    bundle = tmp_path / "bundle"
    submission.prepare(root, bundle)
    assert submission.verify(bundle) == []

    if fault == "swap":
        owner = URIRef(GRAPH + "/page/example")
        for predicate in (SCHEMA.about, DCTERMS.subject):
            graph.remove((owner, predicate, first))
            graph.remove((page, predicate, topic))
            graph.add((owner, predicate, topic))
            graph.add((page, predicate, first))
    else:
        for triple in (
            (topic, RDF.type, SKOS.Concept),
            (topic, SKOS.prefLabel, Literal("Forged topic")),
            (topic, SKOS.inScheme, URIRef(GRAPH + "/scheme")),
            (page, SCHEMA.about, topic),
            (page, DCTERMS.subject, topic),
        ):
            graph.add(triple)
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    graph.serialize(export / "cognitive-kb.ttl", format="turtle")
    refresh_manifest(export)
    errors = submission.validate_export(export, root)
    expected = "matching document about/subject" if fault == "swap" else "document-only page"
    assert any(expected in e for e in errors), errors
    assert not any("hash mismatch" in e or "inventory" in e for e in errors), errors
    for name in ("cognitive-kb.nq", "cognitive-kb.ttl", "manifest.json"):
        (bundle / name).write_bytes((export / name).read_bytes())
    receipt = json.loads((bundle / "bundle.json").read_text())
    receipt["files"] = {name: submission.sha256(bundle / name) for name in receipt["files"]}
    (bundle / "bundle.json").write_text(json.dumps(receipt))
    errors = submission.verify(bundle)
    assert any(expected in e for e in errors), errors
    assert not any("hash mismatch" in e or "inventory" in e for e in errors), errors


def test_bundle_preserves_canonical_graph_and_verifies_actual_files(tmp_path):
    root = source_repo(tmp_path)
    out = tmp_path / "bundle"
    assert main(["bundle-rdf", "--root", str(root), "--output", str(out)]) == 0
    assert (out / "cognitive-kb.nq").read_bytes() == (
        root / "output/okn/cognitive-kb.nq"
    ).read_bytes()
    assert (out / "registry/docs/registry/kgs/cognitive-kb.md").is_file()
    query_directory = out / "registry/docs/registry/queries/cognitive-kb"
    assert {path.name for path in query_directory.glob("*.rq")} == set(submission.QUERY_FILES)
    assert "document_topics.rq" in submission.QUERY_FILES
    assert "#+ summary:" in (query_directory / "document_topics.rq").read_text()
    query = out / "registry/docs/registry/queries/cognitive-kb/cross_graph_obo.rq"
    assert "#+ tags:\n#+   - federation\n\n" in query.read_text()
    assert main(["bundle-rdf", "--output", str(out), "--check"]) == 0
    assert json.loads((out / "bundle.json").read_text())["source_dirty"] is True


@pytest.mark.parametrize(
    "failure",
    ["hash", "license", "scheme", "page_license", "manifest_license", "different_turtle", "empty"],
)
def test_invalid_exports_are_rejected_before_bundle_writes(tmp_path, failure):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    dataset = Dataset().parse(export / "cognitive-kb.nq", format="nquads")
    graph = dataset.graph(URIRef(GRAPH))
    if failure == "hash":
        (export / "cognitive-kb.nq").write_bytes((export / "cognitive-kb.nq").read_bytes() + b"\n")
    else:
        if failure == "license":
            graph.remove((URIRef(GRAPH + "/dataset"), DCTERMS.license, None))
        if failure == "scheme":
            graph.remove((URIRef(GRAPH + "/scheme"), DCTERMS.license, None))
        if failure == "page_license":
            graph.add(
                (
                    URIRef(GRAPH + "/page/example"),
                    DCTERMS.license,
                    URIRef("https://example.org/restricted"),
                )
            )
        if failure == "empty":
            graph.remove((None, None, None))
        dataset.serialize(export / "cognitive-kb.nq", format="nquads")
        graph.serialize(export / "cognitive-kb.ttl", format="turtle")
        if failure == "different_turtle":
            (export / "cognitive-kb.ttl").write_text("")
        refresh_manifest(export)
        if failure == "manifest_license":
            manifest = json.loads((export / "manifest.json").read_text())
            manifest["license"] = "https://example.org/restricted"
            (export / "manifest.json").write_text(json.dumps(manifest))
    out = tmp_path / "bundle"
    assert main(["bundle-rdf", "--root", str(root), "--output", str(out)]) == 1
    assert not out.exists()


@pytest.mark.parametrize(
    "failure", ["modified", "missing", "additional", "traversal", "missing_manifest_entry"]
)
def test_bundle_verification_rejects_tampering(tmp_path, failure):
    root = source_repo(tmp_path)
    out = tmp_path / "bundle"
    submission.prepare(root, out)
    if failure == "modified":
        (out / "cognitive-kb.nq").write_text("modified")
    if failure == "missing":
        (out / "cognitive-kb.nq").rename(out / "preserved.nq")
    if failure == "additional":
        (out / "extra.txt").write_text("additional")
    if failure in {"traversal", "missing_manifest_entry"}:
        manifest = json.loads((out / "bundle.json").read_text())
        if failure == "traversal":
            manifest["files"]["../source/LICENSE-KNOWLEDGE-BASE.md"] = LICENSE
        else:
            del manifest["files"]["cognitive-kb.nq"]
        (out / "bundle.json").write_text(json.dumps(manifest))
    assert main(["bundle-rdf", "--output", str(out), "--check"]) == 1


def test_invalid_registry_block_reports_failure(tmp_path):
    root = source_repo(tmp_path)
    (root / "docs/okn/registry_entry.md").write_text("invalid")
    assert main(["bundle-rdf", "--root", str(root), "--output", str(tmp_path / "bundle")]) == 1


def test_missing_export_reports_failure(tmp_path):
    assert main(["bundle-rdf", "--root", str(tmp_path), "--output", str(tmp_path / "bundle")]) == 1


def test_modified_source_and_additional_graph_are_rejected(tmp_path):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    manifest = json.loads((export / "manifest.json").read_text())
    manifest["sources"] = {"LICENSE-KNOWLEDGE-BASE.md": "invalid"}
    (export / "manifest.json").write_text(json.dumps(manifest))
    assert any("source hash" in item for item in submission.validate_export(export, root))
    dataset = Dataset().parse(export / "cognitive-kb.nq", format="nquads")
    dataset.graph(URIRef("https://example.org/graph")).add(
        (URIRef(GRAPH + "/page/extra"), DCTERMS.title, Literal("Extra"))
    )
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    refresh_manifest(export)
    assert any("unexpected named graph" in item for item in submission.validate_export(export))


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "source",
        "date",
        "rationale",
        "type",
        "endpoint",
        "statement",
        "literal_keyword",
        "local_keyword",
        "custom_citation",
        "bad_date",
        "bad_evidence",
    ],
)
def test_bundle_rejects_semantic_regressions_even_with_valid_hashes(tmp_path, failure):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    dataset = Dataset().parse(export / "cognitive-kb.nq", format="nquads")
    graph = dataset.graph(URIRef(GRAPH))
    page, target, statement = (
        URIRef(value)
        for value in (
            GRAPH + "/concept/example",
            "https://example.org/external",
            GRAPH + "/mapping/review",
        )
    )
    assert page == add_topic(graph)
    graph.add((page, SKOS.exactMatch, target))
    for p, o in (
        (RDF.type, RDF.Statement),
        (RDF.subject, page),
        (RDF.predicate, SKOS.exactMatch),
        (RDF.object, target),
        (DCTERMS.source, URIRef("https://example.org/definition")),
        (DCTERMS.description, Literal("Same defined concept.")),
        (DCTERMS.date, Literal("2026-10-20", datatype=XSD.date)),
    ):
        graph.add((statement, p, o))
    if failure in {"source", "date", "rationale"}:
        predicate = {
            "source": DCTERMS.source,
            "date": DCTERMS.date,
            "rationale": DCTERMS.description,
        }[failure]
        graph.remove((statement, predicate, None))
    elif failure == "type":
        graph.remove((page, RDF.type, SKOS.Concept))
    elif failure == "endpoint":
        graph.add((page, SKOS.closeMatch, Literal("bad target")))
    elif failure == "statement":
        graph.remove((statement, RDF.type, RDF.Statement))
    elif failure == "literal_keyword":
        graph.add((page, URIRef("https://schema.org/keywords"), Literal("model_fitting")))
    elif failure == "local_keyword":
        graph.add((page, URIRef("https://schema.org/keywords"), URIRef(GRAPH + "/keyword/new")))
    elif failure == "custom_citation":
        graph.add((page, URIRef(GRAPH + "/relation/cited_by"), target))
    elif failure == "bad_date":
        graph.set((statement, DCTERMS.date, Literal("2026-10-20")))
    elif failure == "bad_evidence":
        graph.set((statement, DCTERMS.source, URIRef("file:///evidence")))
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    graph.serialize(export / "cognitive-kb.ttl", format="turtle")
    refresh_manifest(export)
    errors = submission.validate_export(export, root)
    assert bool(errors) == (failure is not None)


@pytest.mark.parametrize(
    "fault", ["empty", "partial", "new_page", "bad_hash", "bad_path", "symlink"]
)
def test_source_inventory_requires_complete_safe_current_inputs(tmp_path, fault):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    manifest = json.loads((export / "manifest.json").read_text())
    if fault == "empty":
        manifest["sources"] = {}
    elif fault == "partial":
        del manifest["sources"]["knowledge_base/example.md"]
    elif fault == "new_page":
        (root / "knowledge_base/new.md").write_text("# Unrecorded page\n")
    elif fault == "bad_hash":
        manifest["sources"]["knowledge_base/example.md"] = 42
    elif fault == "bad_path":
        manifest["sources"]["knowledge_base/../LICENSE-KNOWLEDGE-BASE.md"] = submission.sha256(
            root / "LICENSE-KNOWLEDGE-BASE.md"
        )
    elif fault == "symlink":
        page = root / "knowledge_base/example.md"
        page.rename(root / "example-preserved.md")
        page.symlink_to(root / "example-preserved.md")
    (export / "manifest.json").write_text(json.dumps(manifest))
    assert submission.validate_export(export, root)


@pytest.mark.parametrize("fault", ["missing_query", "missing_doc", "recorded_extra", "symlink"])
def test_bundle_manifest_cannot_remove_required_files_or_bless_payloads(tmp_path, fault):
    root = source_repo(tmp_path)
    out = tmp_path / "bundle"
    submission.prepare(root, out)
    manifest = json.loads((out / "bundle.json").read_text())
    name = "graph_description.md"
    if fault == "missing_query":
        name = "registry/docs/registry/queries/cognitive-kb/cross_graph_obo.rq"
    if fault in {"missing_query", "missing_doc"}:
        (out / name).rename(tmp_path / "preserved-file")
        del manifest["files"][name]
    elif fault == "recorded_extra":
        (out / "additional.nq").write_text("unexpected payload")
        manifest["files"]["additional.nq"] = submission.sha256(out / "additional.nq")
    else:
        (out / name).rename(tmp_path / "preserved-file")
        (out / name).symlink_to(tmp_path / "preserved-file")
    (out / "bundle.json").write_text(json.dumps(manifest))
    assert submission.verify(out)


@pytest.mark.parametrize(
    "raw", ["{}", "[]", "null", '{"sources": []}', '{"sources":{},"sources":{}}']
)
def test_malformed_export_manifests_return_diagnostics(tmp_path, raw):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    (export / "manifest.json").write_text(raw)
    assert submission.validate_export(export, root)


@pytest.mark.parametrize(
    "fault",
    [
        "fifo",
        "artifact_symlink",
        "parent_symlink",
        "bad_nquads",
        "bad_turtle",
        "license_disagreement",
    ],
)
def test_export_rejects_unsafe_artifacts_parse_errors_and_license_disagreement(tmp_path, fault):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    path = export / "cognitive-kb.ttl"
    if fault in {"fifo", "artifact_symlink"}:
        path.rename(tmp_path / "preserved.ttl")
        if fault == "fifo":
            os.mkfifo(path)
        else:
            path.symlink_to(tmp_path / "preserved.ttl")
    elif fault == "parent_symlink":
        scripts = root / "code/scripts"
        scripts.rename(root / "code/preserved-scripts")
        scripts.symlink_to(root / "code/preserved-scripts", target_is_directory=True)
    elif fault in {"bad_nquads", "bad_turtle"}:
        (export / ("cognitive-kb.nq" if fault == "bad_nquads" else "cognitive-kb.ttl")).write_text(
            "invalid RDF"
        )
        refresh_manifest(export)
    else:
        manifest = json.loads((export / "manifest.json").read_text())
        manifest["license"] = "https://creativecommons.org/publicdomain/zero/1.0/"
        (export / "manifest.json").write_text(json.dumps(manifest))
    assert submission.validate_export(export, root)


@pytest.mark.parametrize(
    "fault",
    [None, "conflict", "orphan", "multiple_subjects", "incomplete_extra", "self", "local_target"],
)
def test_review_evidence_must_describe_only_consistent_asserted_mappings(tmp_path, fault):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    dataset = Dataset().parse(export / "cognitive-kb.nq", format="nquads")
    graph = dataset.graph(URIRef(GRAPH))
    page, target = add_topic(graph), URIRef("https://example.org/concept")
    if fault == "self":
        target = page
    elif fault == "local_target":
        target = URIRef(GRAPH + "/page/undeclared")
    graph.add((page, RDF.type, SKOS.Concept))
    graph.add((page, SKOS.exactMatch, target))
    statement = URIRef(GRAPH + "/mapping/review")
    for predicate, value in (
        (RDF.type, RDF.Statement),
        (RDF.subject, page),
        (RDF.predicate, SKOS.exactMatch),
        (RDF.object, target),
        (DCTERMS.source, URIRef("https://example.org/evidence")),
        (DCTERMS.description, Literal("Compared source definitions.")),
        (DCTERMS.date, Literal("2026-10-20", datatype=XSD.date)),
    ):
        graph.add((statement, predicate, value))
    if fault == "conflict":
        graph.add((page, SKOS.closeMatch, target))
        for predicate, value in list(graph.predicate_objects(statement)):
            graph.add(
                (
                    URIRef(GRAPH + "/mapping/conflict"),
                    predicate,
                    SKOS.closeMatch if predicate == RDF.predicate else value,
                )
            )
    elif fault == "orphan":
        graph.remove((page, SKOS.exactMatch, target))
    elif fault == "multiple_subjects":
        graph.add((statement, RDF.subject, URIRef(GRAPH + "/page/extra")))
    elif fault == "incomplete_extra":
        graph.add((URIRef(GRAPH + "/mapping/incomplete"), RDF.subject, page))
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    graph.serialize(export / "cognitive-kb.ttl", format="turtle")
    refresh_manifest(export)
    assert bool(submission.validate_export(export, root)) == (fault is not None)


def test_bundle_revalidates_rdf_even_when_all_hashes_are_updated(tmp_path):
    root = source_repo(tmp_path)
    out = tmp_path / "bundle"
    submission.prepare(root, out)
    (out / "cognitive-kb.ttl").write_text("")
    export_manifest = json.loads((out / "manifest.json").read_text())
    export_manifest["artifacts"]["cognitive-kb.ttl"] = submission.sha256(out / "cognitive-kb.ttl")
    (out / "manifest.json").write_text(json.dumps(export_manifest))
    bundle_manifest = json.loads((out / "bundle.json").read_text())
    for name in ("cognitive-kb.ttl", "manifest.json"):
        bundle_manifest["files"][name] = submission.sha256(out / name)
    (out / "bundle.json").write_text(json.dumps(bundle_manifest))
    assert any("different triples" in error for error in submission.verify(out))


def test_transitive_exporter_runtime_imports_must_be_recorded(tmp_path):
    root = source_repo(tmp_path)
    scripts = root / "code/scripts"
    (scripts / "rdf_alignment.py").write_text("from scripts.rdf_quality import quality\n")
    (scripts / "rdf_quality.py").write_text("quality = 1\n")
    (scripts / "__init__.py").write_text("")
    export = root / "output/okn"
    refresh_manifest(export)
    errors = submission.validate_export(export, root)
    assert any("rdf_quality.py" in error and "__init__.py" in error for error in errors)
    manifest = json.loads((export / "manifest.json").read_text())
    for name in ("code/scripts/rdf_quality.py", "code/scripts/__init__.py"):
        manifest["sources"][name] = submission.sha256(root / name)
    (export / "manifest.json").write_text(json.dumps(manifest))
    assert submission.validate_export(export, root) == []


def test_new_keyword_and_relation_modules_are_in_runtime_source_closure(tmp_path):
    root = source_repo(tmp_path)
    scripts = root / "code/scripts"
    (scripts / "export_rdf.py").write_text(
        "import rdf_alignment\nfrom rdf_keywords import keyword_iri\n"
    )
    (scripts / "rdf_alignment.py").write_text(
        "from scripts.rdf_relations import CONCEPT_RELATIONS\n"
    )
    (scripts / "rdf_keywords.py").write_text(
        "KEYWORD_TERMS = {}\ndef keyword_iri(tag):\n    return KEYWORD_TERMS.get(tag)\n"
    )
    (scripts / "rdf_relations.py").write_text("CONCEPT_RELATIONS = {}\n")
    expected = {
        "code/scripts/" + name
        for name in ("export_rdf.py", "rdf_alignment.py", "rdf_keywords.py", "rdf_relations.py")
    }
    assert submission.runtime_sources(root) == expected
    export = root / "output/okn"
    refresh_manifest(export)
    errors = submission.validate_export(export, root)
    assert any("rdf_keywords.py" in error and "rdf_relations.py" in error for error in errors)
    manifest = json.loads((export / "manifest.json").read_text())
    for name in expected:
        manifest["sources"][name] = submission.sha256(root / name)
    (export / "manifest.json").write_text(json.dumps(manifest))
    assert submission.validate_export(export, root) == []
    (scripts / "rdf_keywords.py").write_text(
        "KEYWORD_TERMS = {'changed': 'https://example.org/term'}\n"
    )
    assert any(
        "source hash mismatch: code/scripts/rdf_keywords.py" in error
        for error in submission.validate_export(export, root)
    )


@pytest.mark.parametrize(
    "fault",
    [None, "page_concept", "page_mapping", "page_relation", "concept_source", "missing_about"],
)
def test_bundle_model_validation_survives_rehashed_semantic_tampering(tmp_path, fault):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    dataset = Dataset().parse(export / "cognitive-kb.nq", format="nquads")
    graph = dataset.graph(URIRef(GRAPH))
    topic, page = add_topic(graph), URIRef(GRAPH + "/page/example")
    target = URIRef("https://example.org/external")
    subject = page if fault == "page_mapping" else topic
    graph.add((subject, SKOS.exactMatch, target))
    statement = URIRef(GRAPH + "/mapping/review")
    for predicate, value in (
        (RDF.type, RDF.Statement),
        (RDF.subject, subject),
        (RDF.predicate, SKOS.exactMatch),
        (RDF.object, target),
        (DCTERMS.source, URIRef("https://example.org/evidence")),
        (DCTERMS.description, Literal("Compared definitions.")),
        (DCTERMS.date, Literal("2026-10-23", datatype=XSD.date)),
    ):
        graph.add((statement, predicate, value))
    if fault in {"page_concept", "page_mapping"}:
        graph.add((page, RDF.type, SKOS.Concept))
    elif fault == "page_relation":
        graph.add((page, SKOS.related, topic))
    elif fault == "concept_source":
        graph.add((topic, DCTERMS.source, URIRef("https://example.org/page")))
    elif fault == "missing_about":
        graph.remove((page, SCHEMA.about, topic))
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    graph.serialize(export / "cognitive-kb.ttl", format="turtle")
    refresh_manifest(export)
    errors = submission.validate_export(export, root)
    assert bool(errors) == (fault is not None)


def test_runtime_inventory_covers_local_packages_and_relative_imports(tmp_path):
    root = source_repo(tmp_path)
    scripts = root / "code/scripts"
    (scripts / "helpers").mkdir()
    (scripts / "__init__.py").write_text("")
    (scripts / "helpers/__init__.py").write_text("from . import policy\n")
    (scripts / "helpers/policy.py").write_text("")
    (scripts / "helpers/leaf.py").write_text("from ..rdf_quality import quality\n")
    (scripts / "rdf_quality.py").write_text("quality = 1\n")
    exporter = scripts / "export_rdf.py"
    exporter.write_text(exporter.read_text() + "from scripts.helpers.leaf import quality\n")
    assert submission.runtime_sources(root) == {
        "code/scripts/export_rdf.py",
        "code/scripts/rdf_alignment.py",
        "code/scripts/__init__.py",
        "code/scripts/helpers/__init__.py",
        "code/scripts/helpers/policy.py",
        "code/scripts/helpers/leaf.py",
        "code/scripts/rdf_quality.py",
    }


@pytest.mark.parametrize(
    "name",
    [
        "README.md",
        "docs/okn/graph_description.md",
        "code/resolution.md",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
    ],
)
def test_changed_resolution_markdown_and_configuration_reject_stale_exports(tmp_path, name):
    root = source_repo(tmp_path)
    (root / name).write_text("Changed source bytes\n")
    assert any(
        "source hash mismatch" in error
        for error in submission.validate_export(root / "output/okn", root)
    )


@pytest.mark.parametrize(
    "name", ["new.md", "docs/new.md", "code/new.MD", "knowledge_base/target", "code/new-data.json"]
)
def test_added_resolution_files_require_fresh_content_and_name_inventories(tmp_path, name):
    root = source_repo(tmp_path)
    (root / name).write_text("New resolution input\n")
    errors = submission.validate_export(root / "output/okn", root)
    assert any("file-name inventory" in error for error in errors)
    if name.casefold().endswith(".md"):
        assert any("source inventory mismatch" in error for error in errors)


@pytest.mark.parametrize(
    "name", ["README.md", "docs/okn/graph_description.md", "code/resolution.md", "pyproject.toml"]
)
def test_resolution_markdown_and_config_symlinks_are_rejected(tmp_path, name):
    root = source_repo(tmp_path)
    path = root / name
    preserved = tmp_path / "preserved-input"
    path.rename(preserved)
    path.symlink_to(preserved)
    assert submission.validate_export(root / "output/okn", root)


def test_new_optional_environment_file_changes_exact_source_profile(tmp_path):
    root = source_repo(tmp_path)
    path = root / ".python-version"
    preserved = tmp_path / "preserved-python-version"
    path.rename(preserved)
    refresh_manifest(root / "output/okn")
    assert submission.validate_export(root / "output/okn", root) == []
    preserved.rename(path)
    assert submission.validate_export(root / "output/okn", root)


@pytest.mark.parametrize("value", [None, [], "names", ["../outside"], ["z", "a"], ["a", "a"]])
def test_resolution_inventory_schema_rejects_aliases_and_incomplete_names(tmp_path, value):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    manifest = json.loads((export / "manifest.json").read_text())
    manifest["resolution_files"] = value
    (export / "manifest.json").write_text(json.dumps(manifest))
    assert submission.validate_export(export)


def test_unversioned_export_manifest_remains_readable_without_a_source_root(tmp_path):
    root = source_repo(tmp_path)
    export = root / "output/okn"
    manifest = json.loads((export / "manifest.json").read_text())
    del manifest["resolution_files"]
    (export / "manifest.json").write_text(json.dumps(manifest))
    assert submission.validate_export(export) == []
    assert submission.validate_export(export, root)


def test_uppercase_markdown_suffix_is_part_of_the_same_source_profile(tmp_path):
    root = source_repo(tmp_path)
    (root / "knowledge_base/example.md").rename(root / "knowledge_base/example.MD")
    export = root / "output/okn"
    refresh_manifest(export)
    assert submission.validate_export(export, root) == []
