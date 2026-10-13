import json
import subprocess

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS

from daf_okn.cli import main
from daf_okn.core import rdf_submission as submission

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
    ):
        (docs / name).write_text("Documentation\n")
    (root / "LICENSE-KNOWLEDGE-BASE.md").write_text(LICENSE)
    (docs / "registry_entry.md").write_text(
        "````markdown\n---\nshortname: cognitive-kb\n---\n\nCC BY 4.0\n````\n"
    )
    queries = docs / "queries"
    queries.mkdir()
    for name in ("concept_mappings.rq", "citation_identifiers.rq", "cross_graph_obo.rq"):
        (queries / name).write_text("SELECT ?s WHERE { ?s ?p ?o }\n")
    export = root / "output/okn"
    export.mkdir(parents=True)
    dataset = Dataset()
    graph = dataset.graph(URIRef(GRAPH))
    graph.add((URIRef(GRAPH + "/dataset"), DCTERMS.license, URIRef(LICENSE)))
    graph.add((URIRef(GRAPH + "/scheme"), DCTERMS.license, URIRef(LICENSE)))
    graph.add((URIRef(GRAPH + "/page/example"), DCTERMS.title, Literal("Example")))
    dataset.serialize(export / "cognitive-kb.nq", format="nquads")
    graph.serialize(export / "cognitive-kb.ttl", format="turtle")
    refresh_manifest(export)
    return root


def refresh_manifest(export):
    manifest = {
        "graph": GRAPH,
        "license": LICENSE,
        "sources": {},
        "artifacts": {
            name: submission.sha256(export / name)
            for name in ("cognitive-kb.nq", "cognitive-kb.ttl")
        },
    }
    (export / "manifest.json").write_text(json.dumps(manifest))


def test_bundle_preserves_canonical_graph_and_verifies_actual_files(tmp_path):
    root = source_repo(tmp_path)
    out = tmp_path / "bundle"
    assert main(["bundle-rdf", "--root", str(root), "--output", str(out)]) == 0
    assert (out / "cognitive-kb.nq").read_bytes() == (
        root / "output/okn/cognitive-kb.nq"
    ).read_bytes()
    assert (out / "registry/docs/registry/kgs/cognitive-kb.md").is_file()
    assert len(list((out / "registry/docs/registry/queries/cognitive-kb").glob("*.rq"))) == 3
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
