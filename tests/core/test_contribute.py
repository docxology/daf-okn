#!/usr/bin/env python3
"""Tests for OKN contribution and packaging helpers."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
import rdflib
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from daf_okn.core.cognitive_adapter import separate_document_topics  # noqa: E402
from daf_okn.core.contribute import (  # noqa: E402
    PRESET_ENTRIES,
    _entry_from_metadata,
    _parse_contact_value,
    contribution_checklist,
    graph_to_rdf,
    main,
    registry_entry,
    registry_entry_path,
    upload_commands,
    validate_package,
)
from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord  # noqa: E402
from daf_okn.core.rdf import (  # noqa: E402
    build_rdf_graph,
    default_namespace_base,
    validate_rdf_semantics,
)

register_graph = importlib.import_module("register_graph")

rdflib_parser_warnings = pytest.mark.filterwarnings("ignore::DeprecationWarning:rdflib")

# The exact frontmatter field set RENCI asked for, in order (funding only if supplied).
ENTRY_FIELDS = [
    "template",
    "shortname",
    "title",
    "description",
    "stats",
    "homepage",
    "frink-options",
    "contacts",
]
CONTACT = {"email": "maintainer@example.org", "github": "maintainer", "label": "Maintainer"}


@pytest.mark.parametrize("shortname", ["../escaped", "bad/name"])
def test_unsafe_shortname_is_rejected_before_any_write(tmp_path: Path, shortname: str) -> None:
    doc = _sample_doc()
    doc.metadata["entry"]["shortname"] = shortname
    out_dir = tmp_path / "package"
    sentinel = tmp_path / "escaped.nq"
    sentinel.write_text("preserve", encoding="utf-8")

    problems = validate_package(doc, out_dir)

    assert any("shortname" in problem for problem in problems)
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert not out_dir.exists()


def test_absolute_shortname_is_rejected_before_any_write(tmp_path: Path) -> None:
    doc = _sample_doc()
    doc.metadata["entry"]["shortname"] = str(tmp_path / "absolute")

    problems = validate_package(doc, tmp_path / "package")

    assert any("shortname" in problem for problem in problems)
    assert not (tmp_path / "absolute.nq").exists()


@pytest.mark.parametrize("destination", ["graph", "registry", "checklist"])
def test_package_rejects_destination_symlink_escape(tmp_path: Path, destination: str) -> None:
    out_dir = tmp_path / "package"
    out_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    targets = {
        "graph": out_dir / "demo-graph.nq",
        "registry": out_dir / "registry",
        "checklist": out_dir / "checklist.md",
    }
    targets[destination].symlink_to(
        outside / "sentinel" if destination != "registry" else outside,
        target_is_directory=destination == "registry",
    )

    problems = validate_package(_sample_doc(), out_dir)

    assert any("escapes output directory" in problem for problem in problems)
    assert list(outside.iterdir()) == []


def test_package_allows_destination_symlink_within_output_directory(tmp_path: Path) -> None:
    out_dir = tmp_path / "package"
    out_dir.mkdir()
    registry = out_dir / "internal-registry"
    registry.mkdir()
    (out_dir / "registry").symlink_to(registry, target_is_directory=True)

    problems = validate_package(_sample_doc(), out_dir)

    assert problems == []
    assert (registry / registry_entry_path("demo-graph")).is_file()


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_package_rejects_aliased_output_files_before_writing(tmp_path: Path, kind: str) -> None:
    out_dir = tmp_path / "package"
    out_dir.mkdir()
    graph = out_dir / "demo-graph.nq"
    graph.write_text("preserve graph", encoding="utf-8")
    checklist = out_dir / "checklist.md"
    if kind == "symlink":
        checklist.symlink_to(graph.name)
    else:
        os.link(graph, checklist)

    problems = validate_package(_sample_doc(), out_dir)

    assert any("alias" in problem for problem in problems)
    assert graph.read_text(encoding="utf-8") == "preserve graph"
    assert checklist.read_text(encoding="utf-8") == "preserve graph"
    assert not (out_dir / "registry").exists()


@pytest.mark.parametrize("defect", ["dangling", "duplicate", "empty", "self-loop"])
@rdflib_parser_warnings
def test_package_reports_structural_invariants(tmp_path: Path, defect: str) -> None:
    """Structural failures retain reviewable drafts and never repair missing nodes."""
    doc = _sample_doc()
    changes = {
        "dangling": lambda: doc.edges.append(EdgeRecord("area/one", "missing")),
        "duplicate": lambda: doc.nodes.append(NodeRecord("area/one", "Duplicate")),
        "empty": lambda: doc.nodes.append(NodeRecord("", "Empty")),
        "self-loop": lambda: doc.edges.append(EdgeRecord("area/one", "area/one")),
    }
    changes[defect]()
    expected = doc.validate()

    problems = validate_package(doc, tmp_path / "package")

    assert expected and set(expected) <= set(problems)
    out_dir = tmp_path / "package"
    entry_text = (out_dir / "registry" / registry_entry_path(doc.name)).read_text()
    checklist = (out_dir / "checklist.md").read_text()
    for text in (entry_text, checklist):
        assert "Diagnostic draft" in text
        assert "Do not upload or publish" in text
        assert all(problem in text for problem in problems)
    dataset = rdflib.Dataset()
    dataset.parse(out_dir / f"{doc.name}.nq", format="nquads")
    graph = dataset.graph(rdflib.URIRef(default_namespace_base(doc.name).rstrip("/")))
    if defect == "dangling":
        base = default_namespace_base(doc.name)
        missing = rdflib.URIRef(base + "page/missing")
        assert (
            rdflib.URIRef(base + "page/area/one"),
            rdflib.URIRef(base + "relation/document/related"),
            missing,
        ) in graph
        assert not list(graph.triples((missing, None, None)))
        assert f"page requires CreativeWork type: {missing}" in problems


@rdflib_parser_warnings
def test_package_reports_semantic_failure_without_structural_failure(tmp_path: Path) -> None:
    """A valid graph structure cannot hide a forbidden document SKOS mapping."""
    doc = _sample_doc()
    for node in doc.nodes:
        node.node_type = "overview"
    doc = separate_document_topics(doc)
    doc.edges.append(EdgeRecord("area/one", "area/two", "skos:exactMatch"))
    original = doc.to_dict()
    assert doc.validate() == []
    with pytest.raises(ValueError, match="mapping endpoints must be distinct concepts"):
        build_rdf_graph(doc)

    problems = validate_package(doc, tmp_path)

    dataset = rdflib.Dataset()
    dataset.parse(tmp_path / "demo-graph.nq", format="nquads")
    base = default_namespace_base(doc.name)
    graph = dataset.graph(rdflib.URIRef(base.rstrip("/")))
    assert (
        rdflib.URIRef(base + "page/area/one"),
        rdflib.SKOS.exactMatch,
        rdflib.URIRef(base + "page/area/two"),
    ) in graph
    assert problems == validate_rdf_semantics(graph, base)
    assert any("mapping lacks complete review evidence" in problem for problem in problems)
    assert "Diagnostic draft" in (tmp_path / "checklist.md").read_text()
    assert doc.to_dict() == original


def test_package_propagates_source_construction_errors(tmp_path: Path) -> None:
    """Diagnostic packaging must not swallow source errors or replace prior files."""
    doc = _sample_doc()
    doc.nodes[0].attributes["entity_role"] = "document"
    sentinel = tmp_path / "demo-graph.nq"
    sentinel.write_text("preserve previous evidence")

    with pytest.raises(ValueError, match="unversioned entity role on node 'area/one'"):
        validate_package(doc, tmp_path)

    assert sentinel.read_text() == "preserve previous evidence"
    assert not (tmp_path / "registry").exists()
    assert not (tmp_path / "checklist.md").exists()


def _frontmatter(text: str) -> dict[str, object]:
    """Extract the YAML frontmatter from a registry entry string."""

    assert text.startswith("---\n")
    first = 4
    second = text.index("\n---\n", first)
    return yaml.safe_load(text[first:second])


def _sample_doc() -> GraphDocument:
    """Build a small graph document for packaging tests."""

    return GraphDocument(
        name="demo-graph",
        nodes=[
            NodeRecord(id="area/one", title="Subject One"),
            NodeRecord(id="area/two", title="Subject Two"),
        ],
        edges=[EdgeRecord(source="area/one", target="area/two", relation="connects-to")],
        metadata={
            "entry": {
                "shortname": "demo-graph",
                "title": "Demo Graph",
                "description": "A small example graph.",
                "homepage": "https://example.org/demo",
                "contacts": [CONTACT],
            },
            "fmt": "nq",
        },
    )


# ----------------------------------------------------------------------- graph_to_rdf
@rdflib_parser_warnings
def test_graph_to_rdf_is_reexported_and_uses_frink_iris(tmp_path: Path) -> None:
    path = graph_to_rdf(_sample_doc(), tmp_path / "graph.nq", fmt="nq")
    dataset = rdflib.Dataset()
    dataset.parse(path, format="nquads")
    base = "https://purl.org/okn/frink/kg/demo-graph/"
    named = dataset.graph(rdflib.URIRef("https://purl.org/okn/frink/kg/demo-graph"))
    assert (
        rdflib.URIRef(base + "page/area/one"),
        rdflib.RDF.type,
        rdflib.SDO.CreativeWork,
    ) in named


# ------------------------------------------------------------------------ registry entry
def test_registry_entry_has_exactly_the_requested_fields() -> None:
    text = registry_entry(
        "demo-graph",
        "Demo Graph",
        "A small example graph.",
        [CONTACT],
        homepage="https://example.org/demo",
    )
    frontmatter = _frontmatter(text)
    assert list(frontmatter) == ENTRY_FIELDS
    assert frontmatter["template"] == "overrides/kg.html"
    assert frontmatter["shortname"] == "demo-graph"
    assert frontmatter["stats"] == "https://registry.okn.us/kg-stats/demo-graph"
    assert frontmatter["homepage"] == "https://example.org/demo"
    assert frontmatter["frink-options"] == {
        "lakefs-repo": "demo-graph",
        "documentation-path": "demo-graph",
    }
    assert frontmatter["contacts"] == [CONTACT]
    for absent in ("sparql", "tpf", "funding", "license"):
        assert absent not in frontmatter


def test_registry_entry_funding_is_optional_and_placed_after_homepage() -> None:
    text = registry_entry(
        "demo-graph",
        "Demo Graph",
        "A small example graph.",
        [CONTACT],
        homepage="https://example.org/demo",
        funding="https://example.org/funding",
        body="Free-form **body** text.",
    )
    frontmatter = _frontmatter(text)
    assert list(frontmatter).index("funding") == list(frontmatter).index("homepage") + 1
    assert frontmatter["funding"] == "https://example.org/funding"
    assert text.rstrip().endswith("Free-form **body** text.")


def test_registry_entry_signature_cannot_emit_endpoint_fields() -> None:
    with pytest.raises(TypeError):
        registry_entry("g", "G", "d", [CONTACT], sparql="https://example.org/sparql")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        registry_entry("g", "G", "d", [CONTACT], tpf="https://example.org/tpf")  # type: ignore[call-arg]


def test_registry_entry_keeps_only_registry_contact_fields() -> None:
    text = registry_entry(
        "g",
        "G",
        "d",
        [{"name": "Alice", "label": "Alice", "email": "a@example.org", "phone": "n/a"}, {}],
    )
    assert _frontmatter(text)["contacts"] == [{"email": "a@example.org", "label": "Alice"}]


def test_registry_entry_without_homepage_omits_the_field() -> None:
    frontmatter = _frontmatter(registry_entry("g", "G", "d", [CONTACT]))
    assert "homepage" not in frontmatter


def test_registry_entry_is_deterministic() -> None:
    args = ("g", "G", "d", [CONTACT])
    assert registry_entry(*args, homepage="https://example.org") == registry_entry(
        *args, homepage="https://example.org"
    )


def test_registry_entry_path_matches_registry_layout() -> None:
    assert registry_entry_path("demo-graph") == Path("docs/registry/kgs/demo-graph.md")


# --------------------------------------------------------------------------- misc helpers
def test_upload_commands_include_lakefs_endpoint_and_develop_branch(tmp_path: Path) -> None:
    commands = upload_commands("demo-repo", tmp_path / "dataset", tool="rclone")
    assert any("https://repository.okn.us/" in command for command in commands)
    assert any("develop" in command for command in commands)

    s5cmd_commands = upload_commands("demo-repo", tmp_path / "dataset", tool="s5cmd")
    assert any("https://repository.okn.us/" in command for command in s5cmd_commands)
    assert any("develop" in command for command in s5cmd_commands)


def test_upload_commands_rejects_unknown_tool(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported upload tool"):
        upload_commands("demo-repo", tmp_path / "dataset", tool="ftp")


def test_checklist_contains_documented_workflow_steps_and_no_personal_contacts() -> None:
    checklist = contribution_checklist()
    assert checklist[0].startswith("Create a registry entry PR")
    assert "docs/registry/kgs/<shortname>.md" in checklist[0]
    assert any("repository.okn.us" in item for item in checklist)
    assert not any("@" in item for item in checklist)


def test_register_graph_cli_checklist_smoke(capsys) -> None:
    exit_code = register_graph.main(["checklist"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Create a registry entry PR" in captured.out


def test_entry_from_metadata_prefers_entry_then_registry() -> None:
    entry_doc = GraphDocument(name="g", metadata={"entry": {"shortname": "primary"}})
    assert _entry_from_metadata(entry_doc) == {"shortname": "primary"}

    registry_doc = GraphDocument(name="g", metadata={"registry": {"shortname": "fallback"}})
    assert _entry_from_metadata(registry_doc) == {"shortname": "fallback"}

    bare_doc = GraphDocument(name="g", metadata={"unrelated": True})
    assert _entry_from_metadata(bare_doc) == {}

    non_dict_doc = GraphDocument(name="g", metadata=None)  # type: ignore[arg-type]
    assert _entry_from_metadata(non_dict_doc) == {}


def test_parse_contact_value_accepts_json_and_kv_forms() -> None:
    assert _parse_contact_value('{"email": "a@b.c", "n": 1}') == {"email": "a@b.c", "n": "1"}
    assert _parse_contact_value("email=a@b.c; label=Maintainer") == {
        "email": "a@b.c",
        "label": "Maintainer",
    }
    with pytest.raises(ValueError, match="invalid contact chunk"):
        _parse_contact_value("[1, 2]")
    with pytest.raises(ValueError, match="invalid contact chunk"):
        _parse_contact_value("no-separator")
    with pytest.raises(ValueError):
        _parse_contact_value("{not json")
        _parse_contact_value(
            '{"a": 1}'[:0] + "{}" and '{"x":1}'.replace("{", "{").replace("}", "}")
            if False
            else "[]"[:0] + "{}"
            if False
            else '{"a": 1}'
        ) if False else None  # noqa: E501


# ----------------------------------------------------------------------- validate_package
@rdflib_parser_warnings
def test_validate_package_writes_graph_entry_and_checklist(tmp_path: Path) -> None:
    problems = validate_package(_sample_doc(), tmp_path)
    assert problems == []

    graph_file = tmp_path / "demo-graph.nq"
    entry_file = tmp_path / "registry" / "docs" / "registry" / "kgs" / "demo-graph.md"
    assert graph_file.is_file()
    assert entry_file.is_file()
    assert (tmp_path / "checklist.md").is_file()

    frontmatter = _frontmatter(entry_file.read_text(encoding="utf-8"))
    assert list(frontmatter) == ENTRY_FIELDS
    assert frontmatter["contacts"] == [CONTACT]

    dataset = rdflib.Dataset()
    dataset.parse(graph_file, format="nquads")
    named = dataset.graph(rdflib.URIRef("https://purl.org/okn/frink/kg/demo-graph"))
    assert len(named) > 0
    dataset_node = rdflib.URIRef("https://purl.org/okn/frink/kg/demo-graph/dataset")
    assert (dataset_node, rdflib.DCTERMS.title, rdflib.Literal("Demo Graph")) in named


def test_validate_package_entry_body_states_iris_and_licence(tmp_path: Path) -> None:
    doc = _sample_doc()
    doc.metadata["entry"]["license"] = "https://example.org/licence"
    validate_package(doc, tmp_path)
    text = (tmp_path / "registry" / registry_entry_path("demo-graph")).read_text(encoding="utf-8")
    assert "https://purl.org/okn/frink/kg/demo-graph/" in text
    assert "`https://purl.org/okn/frink/kg/demo-graph`" in text
    assert "Licence: https://example.org/licence" in text
    assert "license" not in _frontmatter(text)


def test_validate_package_funding_only_when_supplied(tmp_path: Path) -> None:
    without = tmp_path / "without"
    validate_package(_sample_doc(), without)
    assert "funding" not in _frontmatter(
        (without / "registry" / registry_entry_path("demo-graph")).read_text(encoding="utf-8")
    )

    funded_doc = _sample_doc()
    funded_doc.metadata["entry"]["funding"] = "https://example.org/grant"
    funded = tmp_path / "funded"
    validate_package(funded_doc, funded)
    assert (
        _frontmatter(
            (funded / "registry" / registry_entry_path("demo-graph")).read_text(encoding="utf-8")
        )["funding"]
        == "https://example.org/grant"
    )


def test_validate_package_is_deterministic(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    validate_package(_sample_doc(), first)
    validate_package(_sample_doc(), second)
    files = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file())
    for relative in files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


def test_validate_package_uses_entry_shortname_for_files_and_iris(tmp_path: Path) -> None:
    doc = _sample_doc()
    doc.metadata["entry"]["shortname"] = "demo"
    assert validate_package(doc, tmp_path) == []
    assert (tmp_path / "demo.nq").is_file()
    assert (tmp_path / "registry" / "docs" / "registry" / "kgs" / "demo.md").is_file()
    assert "<https://purl.org/okn/frink/kg/demo/page/area/one>" in (tmp_path / "demo.nq").read_text(
        encoding="utf-8"
    )


def test_validate_package_honours_fmt_and_extension(tmp_path: Path) -> None:
    doc = _sample_doc()
    doc.metadata["fmt"] = "ttl"
    assert validate_package(doc, tmp_path) == []
    assert (tmp_path / "demo-graph.ttl").is_file()
    assert not (tmp_path / "demo-graph.nq").exists()


@rdflib_parser_warnings
def test_validate_package_reports_unsupported_fmt(tmp_path: Path) -> None:
    doc = _sample_doc()
    doc.metadata["fmt"] = "bogus"

    problems = validate_package(doc, tmp_path)

    assert "unsupported fmt: 'bogus'" in problems
    dataset = rdflib.Dataset()
    dataset.parse(tmp_path / "demo-graph.nq", format="nquads")
    assert len(list(dataset.quads((None, None, None, None)))) > 0


@rdflib_parser_warnings
def test_validate_package_reports_empty_name_and_non_iri_ids(tmp_path: Path) -> None:
    """An unnamed graph still reports every fault and retains its actual dangling edge."""
    doc = GraphDocument(
        name="",
        nodes=[NodeRecord(id="has space", title="Spaced")],
        edges=[EdgeRecord(source="has space", target="ok", relation="relates")],
        metadata={"entry": {"contacts": [CONTACT]}},
    )

    problems = validate_package(doc, tmp_path)

    assert "graph name is empty" in problems
    assert "non-IRI-safe node id: 'has space'" in problems
    assert "non-IRI-safe edge source: 'has space'" in problems
    assert "non-IRI-safe edge target" not in str(problems)
    assert (tmp_path / "graph.nq").exists()
    assert (tmp_path / "registry" / registry_entry_path("graph")).exists()
    assert set(doc.validate()) <= set(problems)
    graph = rdflib.Graph().parse(tmp_path / "graph.nq", format="nt")
    base = default_namespace_base("graph")
    missing = rdflib.URIRef(base + "page/ok")
    assert (
        rdflib.URIRef(base + "page/has%20space"),
        rdflib.URIRef(base + "relation/document/relates"),
        missing,
    ) in graph
    assert not list(graph.triples((missing, None, None)))
    assert f"page requires CreativeWork type: {missing}" in problems
    assert "Diagnostic draft" in (tmp_path / "checklist.md").read_text()


def test_validate_package_accepts_absolute_iri_node_ids(tmp_path: Path) -> None:
    doc = GraphDocument(
        name="pulled",
        nodes=[NodeRecord(id="http://example.org/a", title="A", node_type="uri")],
        metadata={
            "entry": {"contacts": [CONTACT], "homepage": "https://e.org", "description": "d"}
        },
    )
    assert [p for p in validate_package(doc, tmp_path) if "IRI" in p] == []


def test_package_accepts_real_exported_topic_identifiers(tmp_path: Path) -> None:
    """The vault export must remain packageable with its distinct topic IDs."""
    from daf_okn.core.cognitive_adapter import build_cognitive_graph

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "one.md").write_text(
        "---\ntitle: One\ntype: concept\nsemantic_relations:\n"
        '  - type: foundation_for\n    links: ["[[two]]"]\n---\n',
        encoding="utf-8",
    )
    (vault / "two.md").write_text("---\ntitle: Two\ntype: concept\n---\n", encoding="utf-8")
    doc = build_cognitive_graph(vault, name="topics")
    doc.metadata["entry"] = {
        "contacts": [CONTACT],
        "homepage": "https://example.org",
        "description": "Topics",
    }
    assert validate_package(doc, tmp_path / "package") == []
    dataset = rdflib.Dataset().parse(tmp_path / "package/topics.nq", format="nquads")
    graph = dataset.graph(rdflib.URIRef("https://purl.org/okn/frink/kg/topics"))
    base = "https://purl.org/okn/frink/kg/topics/"
    assert (
        rdflib.URIRef(base + "page/one"),
        rdflib.SDO.about,
        rdflib.URIRef(base + "concept/one"),
    ) in graph
    assert (
        rdflib.URIRef(base + "concept/one"),
        rdflib.URIRef(base + "relation/foundation_for"),
        rdflib.URIRef(base + "concept/two"),
    ) in graph


def test_unmodeled_concept_prefix_does_not_bypass_id_validation(tmp_path: Path) -> None:
    """Only declared topic-role IDs receive the internal concept prefix policy."""
    doc = GraphDocument(
        name="unmodeled",
        nodes=[NodeRecord(id="concept:one", title="One", node_type="overview")],
        metadata={
            "entry": {
                "contacts": [CONTACT],
                "homepage": "https://example.org",
                "description": "One",
            }
        },
    )
    assert "non-IRI-safe node id: 'concept:one'" in validate_package(doc, tmp_path)


def test_reserved_prefix_ids_are_accepted_by_policy(tmp_path: Path) -> None:
    """Ids like ``relation/foo`` are domain folders, not the reserved predicate namespace."""
    doc = GraphDocument(
        name="reserved-prefixes",
        nodes=[
            NodeRecord(id="relation/foo", title="Relation Foo"),
            NodeRecord(id="vocab/bar", title="Vocab Bar"),
            NodeRecord(id="graph/baz", title="Graph Baz"),
        ],
        edges=[EdgeRecord(source="relation/foo", target="vocab/bar", relation="rel")],
        metadata={"entry": {"contacts": [CONTACT]}},
    )
    assert [p for p in validate_package(doc, tmp_path) if "IRI" in p] == []


def test_validate_package_reports_missing_entry_inputs(tmp_path: Path) -> None:
    doc = GraphDocument(name="bare-graph", nodes=[NodeRecord(id="solo", title="Solo")])

    problems = validate_package(doc, tmp_path)

    assert problems == [
        "missing contacts in entry inputs",
        "missing homepage in entry inputs",
        "missing description in entry inputs",
    ]
    assert (tmp_path / "registry" / registry_entry_path("bare-graph")).exists()


def test_validate_package_requires_contact_email_and_valid_shortname(tmp_path: Path) -> None:
    doc = _sample_doc()
    doc.metadata["entry"]["contacts"] = [{"github": "maintainer"}]
    doc.metadata["entry"]["shortname"] = "Bad Name"
    problems = validate_package(doc, tmp_path)
    assert "contact 1 has no email" in problems
    assert any(problem.startswith("shortname must be lowercase") for problem in problems)


def test_preset_is_not_applied_implicitly(tmp_path: Path) -> None:
    """A graph that merely shares a preset's name must not inherit someone else's entry."""
    doc = GraphDocument(name="cognitive-kb", nodes=[NodeRecord(id="a/b", title="B")])
    problems = validate_package(doc, tmp_path)
    assert "missing contacts in entry inputs" in problems
    entry_text = (tmp_path / "registry" / registry_entry_path("cognitive-kb")).read_text(
        encoding="utf-8"
    )
    assert "activeinference.institute" not in entry_text


# --------------------------------------------------------------------------------- CLI
@pytest.mark.parametrize("defect", ["dangling-source", "dangling-target", "semantic", "valid"])
@rdflib_parser_warnings
def test_package_subprocess_rejects_diagnostic_drafts(tmp_path: Path, defect: str) -> None:
    """The real CLI rejects malformed sources even with complete registry metadata."""
    doc = _sample_doc()
    if defect == "dangling-source":
        doc.edges.append(EdgeRecord("missing", "area/one"))
    elif defect == "dangling-target":
        doc.edges.append(EdgeRecord("area/one", "missing"))
    elif defect == "semantic":
        for node in doc.nodes:
            node.node_type = "overview"
        doc = separate_document_topics(doc)
        doc.edges.append(EdgeRecord("area/one", "area/two", "skos:exactMatch"))
    graph_path = doc.save_json(tmp_path / "source.json")
    original_bytes = graph_path.read_bytes()
    out_dir = tmp_path / "package"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "daf_okn",
            "package",
            "--graph",
            str(graph_path),
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == (0 if defect == "valid" else 1), result.stdout + result.stderr
    assert result.stderr == ""
    assert graph_path.read_bytes() == original_bytes
    dataset = rdflib.Dataset()
    dataset.parse(out_dir / "demo-graph.nq", format="nquads")
    base = default_namespace_base(doc.name)
    graph = dataset.graph(rdflib.URIRef(base.rstrip("/")))
    semantic_errors = validate_rdf_semantics(graph, base)
    checklist = (out_dir / "checklist.md").read_text()
    if defect == "valid":
        assert "Wrote package" in result.stdout
        assert semantic_errors == []
        assert "Diagnostic draft" not in checklist
    else:
        assert "Wrote package" not in result.stdout
        assert semantic_errors
        assert all(problem in result.stdout for problem in [*doc.validate(), *semantic_errors])
        assert "Diagnostic draft" in checklist


def test_main_package_writes_files_and_prints_summary(tmp_path: Path, capsys) -> None:
    graph_path = tmp_path / "source" / "graph.json"
    _sample_doc().save_json(graph_path)
    out_dir = tmp_path / "package"

    exit_code = main(
        [
            "package",
            "--graph",
            str(graph_path),
            "--out-dir",
            str(out_dir),
            "--entry-shortname",
            "demo",
            "--entry-title",
            "Demo Graph",
            "--entry-description",
            "A small example graph.",
            "--entry-homepage",
            "https://example.org/demo",
            "--entry-license",
            "https://example.org/license",
            "--entry-funding",
            "https://example.org/funding",
            "--entry-body",
            "Demo body text.",
            "--contact",
            '{"email": "a@b.c"}',
            "--contact",
            "github=maintainer;label=Maintainer;email=m@example.org",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"Wrote package to {out_dir}" in captured.out
    assert (out_dir / "demo.nq").exists()
    entry_text = (out_dir / "registry" / registry_entry_path("demo")).read_text(encoding="utf-8")
    frontmatter = _frontmatter(entry_text)
    assert list(frontmatter) == [
        "template",
        "shortname",
        "title",
        "description",
        "stats",
        "homepage",
        "funding",
        "frink-options",
        "contacts",
    ]
    assert frontmatter["funding"] == "https://example.org/funding"
    assert len(frontmatter["contacts"]) == 2
    assert "Demo body text." in entry_text


def test_main_package_reports_problems_and_returns_one(tmp_path: Path, capsys) -> None:
    doc = GraphDocument(name="bare-graph", nodes=[NodeRecord(id="solo", title="Solo")])
    graph_path = tmp_path / "graph.json"
    doc.save_json(graph_path)

    exit_code = main(
        ["package", "--graph", str(graph_path), "--out-dir", str(tmp_path / "package")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "missing contacts in entry inputs" in captured.out


def test_main_package_preset_fills_the_entry_and_options_override_it(
    tmp_path: Path,
) -> None:
    graph_path = tmp_path / "g.json"
    GraphDocument(name="cognitive-kb", nodes=[NodeRecord(id="a/b", title="B")]).save_json(
        graph_path
    )
    out_dir = tmp_path / "pkg"
    assert (
        main(
            [
                "package",
                "--graph",
                str(graph_path),
                "--out-dir",
                str(out_dir),
                "--preset",
                "cognitive-kb",
                "--entry-title",
                "Custom title",
            ]
        )
        == 0
    )
    frontmatter = _frontmatter(
        (out_dir / "registry" / registry_entry_path("cognitive-kb")).read_text(encoding="utf-8")
    )
    assert list(frontmatter) == ENTRY_FIELDS
    assert frontmatter["title"] == "Custom title"
    assert frontmatter["homepage"] == PRESET_ENTRIES["cognitive-kb"]["homepage"]
    assert frontmatter["contacts"][0]["email"] == "daniel@activeinference.institute"
    assert "funding" not in frontmatter


def test_main_package_rejects_endpoint_options() -> None:
    with pytest.raises(SystemExit):
        main(["package", "--graph", "g.json", "--out-dir", "o", "--entry-sparql", "x"])


def test_main_upload_commands_prints_rclone_by_default(tmp_path: Path, capsys) -> None:
    exit_code = main(["upload-commands", "--repo", "demo-repo", "--dir", str(tmp_path / "dataset")])

    captured = capsys.readouterr()
    assert exit_code == 0
    lines = captured.out.splitlines()
    assert lines[0].startswith("export AWS_ACCESS_KEY_ID=")
    assert any("rclone copy" in line for line in lines)
    assert any("lakefs:demo-repo/develop/dataset" in line for line in lines)


def test_main_upload_commands_supports_s5cmd(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "upload-commands",
            "--repo",
            "demo-repo",
            "--dir",
            str(tmp_path / "dataset"),
            "--tool",
            "s5cmd",
            "--branch",
            "main",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    lines = captured.out.splitlines()
    assert any("s5cmd --endpoint-url $LAKEFS_ENDPOINT cp" in line for line in lines)
    assert any("s3://demo-repo/main/dataset" in line for line in lines)
