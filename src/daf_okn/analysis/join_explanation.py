"""Verified offline explanations, published separately from immutable captures."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal as TypingLiteral

import rdflib
from rdflib import BNode, Dataset, Literal
from rdflib.parser import create_input_source
from rdflib.plugins.parsers.nquads import NQuadsParser
from rdflib.plugins.parsers.ntriples import r_literal, unquote

from daf_okn import __version__
from daf_okn.analysis import cross_graph as join
from daf_okn.core import alignment, join_evidence, join_report, rdf, rdf_submission
from daf_okn.core.join_evidence import (
    MAX_PAYLOAD,
    PROFILE,
    EvidenceError,
    EvidenceInputs,
    Json,
    Occurrence,
    SupportReport,
    build_support,
)
from daf_okn.core.rdf import validate_rdf_semantics
from daf_okn.core.rdf_submission import file_inventory, json_object, read_bounded, regular_file


@dataclass(frozen=True, slots=True)
class ExplainOptions:
    """Explicit offline inputs and a new sibling output, or read-only check."""

    source: Path
    query: Path
    capture: Path
    output: Path
    check: bool = False


class _LexicalGuard(NQuadsParser):
    """Reject source lexical normalization instead of reconstructing lost terms."""

    def literal(self) -> Literal | TypingLiteral[False]:
        before = self.line
        value = super().literal()
        if isinstance(value, Literal):
            if before is None:
                raise EvidenceError("unsupported local literal without a source line")
            match = r_literal.match(before)
            if match is None or unquote(match.group(1)) != str(value):
                raise EvidenceError(f"unsupported local literal lexical normalization: {before!r}")
        return value


def _bound_inputs(options: ExplainOptions) -> dict[Path, bytes]:
    paths = [options.source, options.query]
    paths.extend(options.capture / name for name in sorted(file_inventory(options.capture)))
    result: dict[Path, bytes] = {}
    size = 0
    identities: set[tuple[int, int]] = set()
    for path in paths:
        regular_file(path.parent, path.name)
        identity = (path.stat().st_dev, path.stat().st_ino)
        if identity in identities:
            raise EvidenceError(f"aliased input files: {path}")
        identities.add(identity)
        raw = read_bounded(path, MAX_PAYLOAD - size)
        result[path] = raw
        size += len(raw)
    return result


def _destination(options: ExplainOptions) -> None:
    output = options.output
    if any(p.is_symlink() for p in (output, *output.absolute().parents)):
        raise EvidenceError(f"symlink explanation destination: {output}")
    resolved = output.resolve()
    if output.absolute() != resolved:
        raise EvidenceError(f"escaping or aliased explanation destination: {output}")
    for tree in (
        options.capture.resolve(),
        options.source.parent.resolve(),
        options.query.parent.resolve(),
    ):
        physical_ancestor = any(p.exists() and p.samefile(tree) for p in output.parents)
        if resolved.is_relative_to(tree) or tree.is_relative_to(resolved) or physical_ancestor:
            raise EvidenceError(f"explanation destination overlaps input tree: {output} and {tree}")
    if options.check:
        if not output.is_dir():
            raise EvidenceError(f"explanation directory is absent: {output}")
    elif output.exists():
        raise EvidenceError(f"explanation output already exists: {output}")


def _producer() -> dict[str, Json]:
    modules = (
        join_evidence,
        sys.modules[__name__],
        join,
        rdf,
        alignment,
        join_report,
        rdf_submission,
    )
    sources: dict[str, Json] = {}
    for module in modules:
        if module.__file__ is None:
            raise EvidenceError(f"producer source unavailable: {module.__name__}")
        sources[module.__name__] = join.digest(read_bounded(Path(module.__file__), MAX_PAYLOAD))
    return {"version": __version__, "rdflib_version": rdflib.__version__, "source_sha256": sources}


def _derive(options: ExplainOptions, bound: dict[Path, bytes]) -> SupportReport:
    manifest, captures = join._replay_manifest(options.capture, options.source, options.query)
    if manifest.get("schema_version", 1) != 3:
        raise EvidenceError(
            "explain-join requires schema 3; historical schemas 1/2 remain replay-only"
        )
    dataset = join.local_dataset(options.source)
    guard = _LexicalGuard()
    guard.parse(create_input_source(data=bound[options.source], format="nquads"), Dataset())
    local = dataset.graph(join.checked_iri(join.GRAPH))
    if any(isinstance(term, BNode) for triple in local for term in triple):
        raise EvidenceError(
            "unsupported local blank-node profile; IRI review identifiers are required"
        )
    errors = validate_rdf_semantics(local, join.GRAPH)
    if errors:
        raise EvidenceError("invalid local review semantics: " + "; ".join(errors))
    join._replay_stages(dataset, captures, options.capture, manifest)
    evaluation = join.evaluate_results(
        dataset,
        options.query,
        (options.output, manifest["observed_at"]),
        provenance=join._provenance(manifest),
        schema_version=3,
    )
    for name, raw in (
        ("join-results.json", evaluation.json_bytes),
        ("join-results.md", evaluation.markdown_bytes),
    ):
        if raw != bound[options.capture / name]:
            raise EvidenceError(f"captured result differs from recomputed join: {name}")
    occurrences: list[Occurrence] = []
    for capture_index, capture in enumerate(captures):
        raw = bound[options.capture / capture.response_file]
        bindings = json_object(raw)["results"]["bindings"]
        for binding_index, binding in enumerate(bindings):
            # WHY: the established parser defines legacy materialization; the raw
            # term records remain separate even when lexical forms normalize.
            singleton = json.dumps(
                {"head": {"vars": ["s", "p", "o"]}, "results": {"bindings": [binding]}}
            ).encode()
            (triple,) = join.response_triples(singleton)
            occurrences.append(
                Occurrence(
                    capture.graph,
                    capture_index,
                    binding_index,
                    capture.query_file,
                    capture.query_sha256,
                    capture.response_file,
                    capture.response_sha256,
                    binding,
                    triple,
                )
            )
            if len(occurrences) > 50000:
                raise EvidenceError("explanation exceeds 50000 raw occurrences")
    origin: dict[str, Json] = {
        "capture_schema_version": 3,
        "result_basis": "captured-and-recomputed",
        "capture_manifest_sha256": join.digest(bound[options.capture / "manifest.json"]),
        "local_sha256": manifest["local_sha256"],
        "join_query_sha256": manifest["join_query_sha256"],
        "observed_at": manifest["observed_at"],
        "endpoint": manifest["endpoint"],
        "result_sha256": {
            name: join.digest(bound[options.capture / name])
            for name in ("join-results.json", "join-results.md")
        },
        "captures": [asdict(capture) for capture in captures],
    }
    return build_support(
        EvidenceInputs(
            dataset,
            evaluation.typed_rows,
            tuple(evaluation.result["rows"]),
            tuple(occurrences),
            origin,
            _producer(),
        )
    )


def _files(report: SupportReport) -> dict[str, bytes]:
    files = {"join-support.json": report.json_bytes, "join-support.md": report.markdown_bytes}
    manifest = {
        "explanation_schema_version": 1,
        "profile": PROFILE,
        "files": {name: join.digest(raw) for name, raw in files.items()},
    }
    files["support-manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    if sum(map(len, files.values())) > MAX_PAYLOAD:
        raise EvidenceError(f"explanation exceeds {MAX_PAYLOAD} byte payload limit")
    return files


def explain_join(options: ExplainOptions) -> None:
    """Recompute and verify every parent check before publishing or checking.

    Check mode performs no writes. Publication reserves a fresh directory and
    atomically replaces that owned empty reservation with fully staged files.
    Inputs are bounded to 32 MiB total and rechecked byte-for-byte after derivation.
    """
    _destination(options)
    bound = _bound_inputs(options)
    files = _files(_derive(options, bound))
    if _bound_inputs(options) != bound:
        raise EvidenceError("bound explanation inputs changed during derivation")
    _destination(options)
    if options.check:
        if {p.name for p in options.output.iterdir()} != set(files):
            raise EvidenceError("explanation file inventory differs from recomputed output")
        for name, expected in files.items():
            if read_bounded(regular_file(options.output, name), MAX_PAYLOAD) != expected:
                raise EvidenceError(f"explanation differs from recomputed support: {name}")
        return
    options.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".join-support-", dir=options.output.parent) as stage:
        for name, raw in files.items():
            with (Path(stage) / name).open("xb") as stream:
                stream.write(raw)
        _destination(options)
        options.output.mkdir(exist_ok=False)
        identity = options.output.stat()
        try:
            os.rename(stage, options.output)
        except OSError:
            current = options.output.lstat()
            if (identity.st_dev, identity.st_ino) == (current.st_dev, current.st_ino):
                options.output.rmdir()
            raise
