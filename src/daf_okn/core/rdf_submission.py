"""Prepare and verify a provenance-recorded cognitive-kb submission directory."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import DCTERMS


@dataclass(frozen=True, slots=True)
class SubmissionError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root: Path, output: Path) -> None:
    export = root / "output/okn"
    errors = validate_export(export, root)
    if errors:
        raise SubmissionError("; ".join(errors))
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    output.mkdir(parents=True, exist_ok=False)
    for name in ("cognitive-kb.nq", "cognitive-kb.ttl", "manifest.json"):
        shutil.copyfile(export / name, output / name)
    for name in (
        "LICENSE-KNOWLEDGE-BASE.md",
        "docs/okn/graph_description.md",
        "docs/okn/vocabulary.md",
        "docs/okn/submission_criteria.md",
        "docs/okn/interoperability.md",
        "docs/okn/landing_zone.md",
    ):
        shutil.copyfile(root / name, output / Path(name).name)
    entry = (root / "docs/okn/registry_entry.md").read_text(encoding="utf-8")
    sections = entry.split("````markdown\n")
    if len(sections) != 2 or "\n````" not in sections[1]:
        raise SubmissionError("registry entry must contain one Markdown submission block")
    registry = output / "registry/docs/registry/kgs"
    registry.mkdir(parents=True)
    (registry / "cognitive-kb.md").write_text(
        sections[1].split("\n````", 1)[0] + "\n", encoding="utf-8"
    )
    queries = output / "registry/docs/registry/queries/cognitive-kb"
    queries.mkdir(parents=True)
    for name, summary, tags in (
        (
            "concept_mappings.rq",
            "Cognitive concept pages and their candidate Wikidata mappings",
            ["cognitive-kb"],
        ),
        (
            "citation_identifiers.rq",
            "Cognitive citation pages and their DOI join keys",
            ["cognitive-kb"],
        ),
        (
            "cross_graph_obo.rq",
            "Cognitive concepts linked through Wikidata mappings to OBO ontology labels",
            ["federation"],
        ),
    ):
        header = f"#+ summary: {json.dumps(summary)}\n#+ tags:\n"
        header += "".join(f"#+   - {tag}\n" for tag in tags) + "\n"
        (queries / name).write_text(
            header + (root / "docs/okn/queries" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    files = {
        p.relative_to(output).as_posix(): sha256(p)
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    manifest = {
        "source_commit": revision,
        "source_dirty": bool(dirty),
        "source_status": dirty,
        "files": files,
        "upload_object": "s3://cognitive-kb/develop/cognitive-kb.nq",
    }
    (output / "bundle.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Prepared {len(files)} submission files at {output}")


def validate_export(directory: Path, root: Path | None = None) -> list[str]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    errors = []
    if root is not None:
        for name, expected in manifest["sources"].items():
            source = root / name
            if (
                not source.resolve().is_relative_to(root.resolve())
                or not source.is_file()
                or sha256(source) != expected
            ):
                errors.append(f"source hash mismatch: {name}")
    for name in ("cognitive-kb.nq", "cognitive-kb.ttl"):
        if manifest["artifacts"].get(name) != sha256(directory / name):
            errors.append(f"export hash mismatch: {name}")
    dataset = Dataset().parse(directory / "cognitive-kb.nq", format="nquads")
    graph = dataset.graph(URIRef(manifest["graph"]))
    if any(g != URIRef(manifest["graph"]) for _, _, _, g in dataset.quads()):
        errors.append("export contains an unexpected named graph")
    turtle = Graph().parse(directory / "cognitive-kb.ttl", format="turtle")
    if set(graph) != set(turtle):
        errors.append("Turtle and N-Quads contain different triples")
    if not len(graph):
        errors.append("empty named graph")
    allowed = {
        URIRef("https://creativecommons.org/licenses/by/4.0/"),
        URIRef("https://creativecommons.org/publicdomain/zero/1.0/"),
    }
    for subject in (URIRef(manifest["graph"] + "/dataset"), URIRef(manifest["graph"] + "/scheme")):
        licenses = set(graph.objects(subject, DCTERMS.license))
        if len(licenses) != 1 or not licenses <= allowed:
            errors.append(f"incompatible or missing license: {subject}")
    if URIRef(manifest["license"]) not in allowed:
        errors.append("incompatible manifest license")
    for page_subject, license_iri in graph.subject_objects(DCTERMS.license):
        if license_iri not in allowed:
            errors.append(f"incompatible page license: {page_subject}")
    return errors


def verify(output: Path) -> list[str]:
    manifest = json.loads((output / "bundle.json").read_text(encoding="utf-8"))
    errors = []
    for name, expected in manifest["files"].items():
        path = output / name
        if (
            not path.resolve().is_relative_to(output.resolve())
            or not path.is_file()
            or sha256(path) != expected
        ):
            errors.append(name)
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    errors += sorted(actual - set(manifest["files"]) - {"bundle.json"})
    if "cognitive-kb.nq" not in manifest["files"]:
        errors.append("cognitive-kb.nq missing from bundle manifest")
    return sorted(set(errors))
