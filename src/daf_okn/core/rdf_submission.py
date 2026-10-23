"""Prepare and verify a provenance-recorded cognitive-kb submission directory."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from rdflib import Dataset, Graph, URIRef
from rdflib.exceptions import ParserError
from rdflib.namespace import DCTERMS

from .rdf import validate_rdf_semantics

GRAPH = "https://purl.org/okn/frink/kg/cognitive-kb"
EXPORT_FILES = frozenset({"cognitive-kb.nq", "cognitive-kb.ttl"})
SOURCE_FILES = frozenset({"LICENSE-KNOWLEDGE-BASE.md", "code/scripts/export_rdf.py"})
SOURCE_DIRECTORIES = ("knowledge_base", "docs", "code")
ENVIRONMENT_FILES = frozenset({"pyproject.toml", "uv.lock", ".python-version"})
DOCUMENT_FILES = (
    "LICENSE-KNOWLEDGE-BASE.md",
    "docs/okn/graph_description.md",
    "docs/okn/vocabulary.md",
    "docs/okn/submission_criteria.md",
    "docs/okn/interoperability.md",
    "docs/okn/landing_zone.md",
    "docs/okn/alignment-review.md",
    "docs/okn/entity-model.md",
    "docs/okn/keyword-curation-2026-10-23.md",
)
QUERY_FILES = (
    "concept_mappings.rq",
    "mapping_evidence.rq",
    "keyword_concepts.rq",
    "citation_identifiers.rq",
    "cross_graph_obo.rq",
    "relation_scopes.rq",
    "document_topics.rq",
)
QUERY_DIRECTORY = "registry/docs/registry/queries/cognitive-kb"
BUNDLE_FILES = (
    EXPORT_FILES
    | {"manifest.json", "registry/docs/registry/kgs/cognitive-kb.md"}
    | {Path(name).name for name in DOCUMENT_FILES}
    | {f"{QUERY_DIRECTORY}/{name}" for name in QUERY_FILES}
)
SHA256 = re.compile(r"[0-9a-f]{64}")
MAX_MANIFEST_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SubmissionError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def sha256(path: Path) -> str:
    """Hash a regular custody file without loading its entire contents."""
    path = regular_file(path.parent, path.name)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def relative_name(name: Any) -> str:
    """Require a canonical POSIX relative path without aliases or traversal."""
    if (
        not isinstance(name, str)
        or not name
        or "\\" in name
        or "\x00" in name
        or PurePosixPath(name).is_absolute()
        or PurePosixPath(name).as_posix() != name
        or any(part in {".", ".."} for part in name.split("/"))
    ):
        raise SubmissionError(f"unsafe relative file name: {name!r}")
    return name


def regular_file(directory: Path, name: str) -> Path:
    """Resolve a relative regular file while rejecting symlink ancestors."""
    path = directory
    if (
        any(parent.is_symlink() for parent in (directory, *directory.absolute().parents))
        or not directory.is_dir()
    ):
        raise SubmissionError(f"expected a real directory: {directory}")
    for part in PurePosixPath(relative_name(name)).parts:
        path = path / part
        if path.is_symlink():
            raise SubmissionError(f"symlink is not a custody file: {path}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise SubmissionError(f"expected a regular custody file: {path}")
    return path


def read_bounded(path: Path, limit: int) -> bytes:
    """Read a regular file up to ``limit`` bytes; reject larger files."""
    path = regular_file(path.parent, path.name)
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise SubmissionError(f"file exceeds {limit} byte limit: {path}")
    return raw


def json_object(raw: bytes) -> dict[str, Any]:
    """Parse a JSON object, rejecting duplicate keys and nonfinite constants."""

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SubmissionError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    try:

        def invalid_constant(value: str) -> None:
            raise SubmissionError(f"invalid JSON constant: {value}")

        value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SubmissionError(f"invalid JSON document: {error}") from error
    if not isinstance(value, dict):
        raise SubmissionError(f"JSON document must be an object, got {type(value).__name__}")
    return value


def file_inventory(directory: Path) -> set[str]:
    """Inventory regular files, rejecting links, special files and unreadable trees."""
    if (
        any(parent.is_symlink() for parent in (directory, *directory.absolute().parents))
        or not directory.is_dir()
    ):
        raise SubmissionError(f"expected a real directory: {directory}")
    files = set()

    def fail(error: OSError) -> None:
        raise error

    for parent, dirs, names in os.walk(directory, followlinks=False, onerror=fail):
        for name in dirs:
            path = Path(parent) / name
            if path.is_symlink():
                raise SubmissionError(f"symlink directory is not a custody directory: {path}")
        for name in names:
            relative = (Path(parent) / name).relative_to(directory).as_posix()
            regular_file(directory, relative)
            files.add(relative)
    return files


def hash_inventory(value: Any, field: str) -> dict[str, str]:
    """Validate a nonempty canonical relative-path/SHA-256 inventory."""
    if not isinstance(value, dict) or not value:
        raise SubmissionError(f"{field} must be a nonempty file/hash object")
    for name, expected in value.items():
        relative_name(name)
        if not isinstance(expected, str) or not SHA256.fullmatch(expected):
            raise SubmissionError(f"{field} hash is not SHA-256: {name!r}: {expected!r}")
    return value


def runtime_sources(root: Path) -> set[str]:
    """Discover the exporter's static local Python import closure without execution."""
    pending = ["code/scripts/export_rdf.py"]
    package = root / "code/scripts/__init__.py"
    if package.exists() or package.is_symlink():
        pending.append("code/scripts/__init__.py")
    sources: set[str] = set()
    while pending:
        name = pending.pop()
        if name in sources:
            continue
        path = regular_file(root, name)
        syntax = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        sources.add(name)
        for node in ast.walk(syntax):
            modules: list[tuple[str, int]] = []
            if isinstance(node, ast.Import):
                modules = [(alias.name, 0) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules = [(node.module, node.level)]
                modules.extend(
                    ((node.module + "." if node.module else "") + alias.name, node.level)
                    for alias in node.names
                    if alias.name != "*"
                )
            for module, level in modules:
                parts = module.split(".")
                if level:
                    parent = Path(name).parent
                    for _ in range(level - 1):
                        parent = parent.parent
                    if len(parent.parts) < 2 or parent.parts[0] != "code":
                        raise SubmissionError(
                            f"relative import escapes source package: {name}: {module}"
                        )
                    candidates = [parent.joinpath(*parts)]
                else:
                    candidates = [Path("code", *parts)]
                    if parts[0] != "scripts":
                        candidates.append(Path("code/scripts", *parts))
                for candidate in candidates:
                    for relative in (candidate.with_suffix(".py"), candidate / "__init__.py"):
                        target = root / relative
                        if target.exists() or target.is_symlink():
                            pending.append(relative.as_posix())
                            for package_dir in relative.parents:
                                if len(package_dir.parts) < 2:
                                    break
                                initializer = package_dir / "__init__.py"
                                if (root / initializer).exists() or (
                                    root / initializer
                                ).is_symlink():
                                    pending.append(initializer.as_posix())
    return sources


def resolution_file_inventory(root: Path) -> set[str]:
    """Inventory root files and scoped trees whose names can affect wiki resolution."""
    names: set[str] = set()
    for path in root.iterdir():
        if path.name in SOURCE_DIRECTORIES:
            names.update(f"{path.name}/{name}" for name in file_inventory(path))
        elif path.name in ENVIRONMENT_FILES or not path.is_dir():
            regular_file(root, path.name)
            names.add(path.name)
    return names


def prepare(root: Path, output: Path) -> None:
    """Create a byte-preserving, validated bundle in a new directory."""
    if any(parent.is_symlink() for parent in (output, *output.absolute().parents)):
        raise SubmissionError(f"symlink is not a bundle destination: {output}")
    export = root / "output/okn"
    errors = validate_export(export, root)
    if errors:
        raise SubmissionError("; ".join(errors))
    for name in (
        *DOCUMENT_FILES,
        "docs/okn/registry_entry.md",
        *(f"docs/okn/queries/{name}" for name in QUERY_FILES),
    ):
        regular_file(root, name)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    output.mkdir(parents=True, exist_ok=False)
    for name in ("cognitive-kb.nq", "cognitive-kb.ttl", "manifest.json"):
        shutil.copyfile(export / name, output / name)
    for name in DOCUMENT_FILES:
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
            "Cognitive concepts and their source-reviewed external mappings",
            ["cognitive-kb"],
        ),
        (
            "mapping_evidence.rq",
            "Sources, rationales and dates for reviewed cognitive correspondences",
            ["cognitive-kb"],
        ),
        (
            "keyword_concepts.rq",
            "Concept identifiers used as cognitive page keywords",
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
        (
            "relation_scopes.rq",
            "Document and concept relation meanings, directions and endpoint scopes",
            ["cognitive-kb"],
        ),
        (
            "document_topics.rq",
            "Markdown documents and their separately identified topic concepts",
            ["cognitive-kb"],
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
    errors = verify(output) + validate_export(export, root)
    if errors:
        raise SubmissionError("; ".join(errors))
    print(f"Prepared {len(files)} submission files at {output}")


def validate_export(directory: Path, root: Path | None = None) -> list[str]:
    """Report manifest and RDF errors; recheck complete current sources when given ``root``."""
    try:
        manifest = json_object(
            read_bounded(regular_file(directory, "manifest.json"), MAX_MANIFEST_BYTES)
        )
        sources = hash_inventory(manifest.get("sources"), "source")
        artifacts = hash_inventory(manifest.get("artifacts"), "artifact")
        if manifest.get("graph") != GRAPH:
            raise SubmissionError(f"unexpected export graph: {manifest.get('graph')!r}")
        if set(artifacts) != EXPORT_FILES:
            raise SubmissionError(f"export artifact inventory differs: {sorted(artifacts)}")
        kb_sources = {
            name
            for name in sources
            if name.startswith("knowledge_base/") and name.casefold().endswith(".md")
        }
        if not sources.keys() >= SOURCE_FILES or not kb_sources:
            raise SubmissionError(
                "source inventory lacks exporter, alignment, license or knowledge-base inputs"
            )
        recorded_names = manifest.get("resolution_files")
        if "resolution_files" in manifest:
            if (
                not isinstance(recorded_names, list)
                or not recorded_names
                or not all(isinstance(name, str) for name in recorded_names)
                or recorded_names != sorted(set(recorded_names))
            ):
                raise SubmissionError("resolution_files must be a nonempty sorted unique path list")
            for name in recorded_names:
                relative_name(name)
            if not sources.keys() <= set(recorded_names):
                raise SubmissionError("resolution_files omits recorded source files")
        errors = []
        if root is not None:
            current_names = resolution_file_inventory(root)
            expected_sources = (
                SOURCE_FILES
                | runtime_sources(root)
                | {
                    name
                    for name in current_names
                    if name.casefold().endswith(".md") or name in ENVIRONMENT_FILES
                }
            )
            if recorded_names != sorted(current_names):
                errors.append("resolution file-name inventory differs from current source tree")
            if set(sources) != expected_sources:
                errors.append(
                    "source inventory mismatch: "
                    f"missing={sorted(expected_sources - sources.keys())}; "
                    f"unexpected={sorted(sources.keys() - expected_sources)}"
                )
            for name, expected in sources.items():
                if sha256(regular_file(root, name)) != expected:
                    errors.append(f"source hash mismatch: {name}")
        for name in EXPORT_FILES:
            if artifacts[name] != sha256(regular_file(directory, name)):
                errors.append(f"export hash mismatch: {name}")
        dataset = Dataset().parse(regular_file(directory, "cognitive-kb.nq"), format="nquads")
        graph = dataset.graph(URIRef(GRAPH))
        if any(g != URIRef(GRAPH) for _, _, _, g in dataset.quads()):
            errors.append("export contains an unexpected named graph")
        turtle = Graph().parse(regular_file(directory, "cognitive-kb.ttl"), format="turtle")
    except (OSError, ValueError, SyntaxError, ParserError) as error:
        return [f"invalid export: {error}"]
    if set(graph) != set(turtle):
        errors.append("Turtle and N-Quads contain different triples")
    if not len(graph):
        errors.append("empty named graph")
    allowed = {
        URIRef("https://creativecommons.org/licenses/by/4.0/"),
        URIRef("https://creativecommons.org/publicdomain/zero/1.0/"),
    }
    for licensed_resource in (
        URIRef(manifest["graph"] + "/dataset"),
        URIRef(manifest["graph"] + "/scheme"),
    ):
        licenses = set(graph.objects(licensed_resource, DCTERMS.license))
        if len(licenses) != 1 or not licenses <= allowed:
            errors.append(f"incompatible or missing license: {licensed_resource}")
    if not isinstance(manifest.get("license"), str) or URIRef(manifest["license"]) not in allowed:
        errors.append("incompatible manifest license")
    elif any(
        set(graph.objects(URIRef(GRAPH + suffix), DCTERMS.license)) != {URIRef(manifest["license"])}
        for suffix in ("/dataset", "/scheme")
    ):
        errors.append("manifest license differs from RDF dataset/scheme license")
    for page_subject, license_iri in graph.subject_objects(DCTERMS.license):
        if license_iri not in allowed:
            errors.append(f"incompatible page license: {page_subject}")
    errors.extend(validate_rdf_semantics(graph, GRAPH))
    for name in ("cited_by", "cites"):
        if any(graph.triples((None, URIRef(manifest["graph"] + "/relation/" + name), None))):
            errors.append(f"use BIBO rather than custom citation predicate: {name}")
    return errors


def verify(output: Path) -> list[str]:
    """Verify the complete bundle payload and revalidate its canonical RDF offline."""
    try:
        manifest = json_object(
            read_bounded(regular_file(output, "bundle.json"), MAX_MANIFEST_BYTES)
        )
        files = hash_inventory(manifest.get("files"), "bundle files")
        actual = file_inventory(output) - {"bundle.json"}
        errors = []
        if set(files) != BUNDLE_FILES or actual != BUNDLE_FILES:
            errors.append(
                f"bundle inventory mismatch: required missing={sorted(BUNDLE_FILES - actual)}; "
                f"manifest missing={sorted(BUNDLE_FILES - files.keys())}; "
                f"unexpected={sorted((actual | files.keys()) - BUNDLE_FILES)}"
            )
        for name, expected in files.items():
            if sha256(regular_file(output, name)) != expected:
                errors.append(f"bundle hash mismatch: {name}")
        if (
            not isinstance(manifest.get("source_commit"), str)
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", manifest["source_commit"])
            or not isinstance(manifest.get("source_dirty"), bool)
            or not isinstance(manifest.get("source_status"), list)
            or not all(isinstance(item, str) for item in manifest["source_status"])
            or manifest["source_dirty"] != bool(manifest["source_status"])
            or manifest.get("upload_object") != "s3://cognitive-kb/develop/cognitive-kb.nq"
        ):
            errors.append("invalid bundle provenance metadata")
        return sorted(set(errors + validate_export(output)))
    except (OSError, ValueError) as error:
        return [f"invalid bundle: {error}"]
