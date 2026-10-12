"""Helpers for OKN graph contribution and registry packaging.

Workflow facts are documented in:
- docs/okn/contribute.md (https://registry.okn.us/registry/contribute/)
- docs/okn/registry-help.md (https://registry.okn.us/help/setup/ and
  https://registry.okn.us/help/update/)
- docs/okn/api-notes.md (§6-7, https://registry.okn.us/reference/fabric/)
- docs/okn/contribute.md (§3, https://registry.okn.us/help/update-queries/)
- https://docs.lakefs.io/quickstart/

RDF serialization lives in :mod:`daf_okn.core.rdf` (re-exported here as
:func:`graph_to_rdf`). This module builds the registry entry, checklist and
upload commands, and bundles them into a contribution package
(:func:`validate_package`).
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from .graph import GraphDocument
from .rdf import (
    SUPPORTED_FORMATS,
    default_namespace_base,
    graph_iri,
    graph_to_rdf,
    shortname_slug,
)
from .rdf import _quote as _quote_iri_fragment

__all__ = [
    "PRESET_ENTRIES",
    "SUPPORTED_FORMATS",
    "contribution_checklist",
    "graph_to_rdf",
    "main",
    "registry_entry",
    "registry_entry_path",
    "upload_commands",
    "validate_package",
]

OKN_DOCS = {
    "contribute": "https://registry.okn.us/registry/contribute/",
    "setup": "https://registry.okn.us/help/setup/",
    "update": "https://registry.okn.us/help/update/",
    "queries": "https://registry.okn.us/help/update-queries/",
}

REGISTRY_TEMPLATE = "overrides/kg.html"
REGISTRY_KGS_DIR = Path("docs") / "registry" / "kgs"
_SHORTNAME = re.compile(r"[a-z][a-z0-9-]*")

# Ready-made registry-entry inputs for known graphs, selected explicitly with
# ``daf-okn package --preset NAME``. Explicit ``--entry-*`` options override them.
PRESET_ENTRIES: dict[str, dict[str, Any]] = {
    "cognitive-kb": {
        "shortname": "cognitive-kb",
        "title": "Cognitive Active Inference knowledge base",
        "description": (
            "Concept pages on Active Inference and related fields, with typed and untyped "
            "relations and citation records, as SKOS/Dublin Core/schema.org RDF."
        ),
        "homepage": "https://github.com/ActiveInferenceInstitute/cognitive",
        "source": "https://github.com/ActiveInferenceInstitute/cognitive",
        "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "language": "en",
        "contacts": [
            {
                "email": "daniel@activeinference.institute",
                "github": "docxology",
                "label": "Daniel Ari Friedman",
            }
        ],
    }
}


def _frontmatter_yaml(data: dict[str, Any]) -> str:
    """Render a stable YAML frontmatter block."""

    return yaml.safe_dump(
        data, sort_keys=False, default_flow_style=False, allow_unicode=True, width=1000
    ).strip()


def registry_entry_path(shortname: str) -> Path:
    """Return the entry's path in the registry repository (``docs/registry/kgs/<shortname>.md``)."""

    return REGISTRY_KGS_DIR / f"{shortname}.md"


def _normalise_contacts(contacts: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """Keep only the registry's contact fields (``email``, ``github``, ``label``), in order."""

    normalised: list[dict[str, str]] = []
    for contact in contacts:
        item = {key: str(contact[key]) for key in ("email", "github", "label") if contact.get(key)}
        if item:
            normalised.append(item)
    return normalised


def registry_entry(
    shortname: str,
    title: str,
    description: str,
    contacts: list[dict],
    *,
    homepage: str | None = None,
    funding: str | None = None,
    body: str = "",
) -> str:
    """Build a registry Markdown entry with YAML frontmatter.

    The frontmatter carries exactly the fields the registry documents for a new entry
    (https://registry.okn.us/registry/contribute/): ``template``, ``shortname``,
    ``title``, ``description``, ``stats``, ``homepage``, ``funding`` (only when given),
    ``frink-options`` (``lakefs-repo``, ``documentation-path``) and ``contacts``
    (``email``, ``github``, ``label``). ``sparql`` and ``tpf`` are deliberately never
    written: the registry asks contributors to omit them until the graph has been
    uploaded and converted; RENCI adds them once the endpoints exist.
    """

    frontmatter: dict[str, Any] = {
        "template": REGISTRY_TEMPLATE,
        "shortname": shortname,
        "title": title,
        "description": description,
        "stats": f"https://registry.okn.us/kg-stats/{shortname}",
    }
    if homepage:
        frontmatter["homepage"] = homepage
    if funding:
        frontmatter["funding"] = funding
    frontmatter["frink-options"] = {
        "lakefs-repo": shortname,
        "documentation-path": shortname,
    }
    frontmatter["contacts"] = _normalise_contacts(contacts)

    parts = ["---", _frontmatter_yaml(frontmatter), "---"]
    if body.strip():
        parts.extend(["", body.strip()])
    return "\n".join(parts) + "\n"


def _default_body(entry: dict[str, Any], namespace_base: str) -> str:
    """Prose body for a registry entry: what the graph is, its IRIs and vocabularies."""

    paragraphs = []
    if entry.get("description"):
        paragraphs.append(str(entry["description"]).strip())
    paragraphs.append(
        f"Entity IRIs are under `{namespace_base}`; the named graph is "
        f"`{graph_iri(namespace_base)}`. Terms come from SKOS, Dublin Core Terms and "
        f"schema.org; relation names that none of them covers are terms under "
        f"`{namespace_base}relation/`, declared sub-properties of `skos:semanticRelation`."
    )
    if entry.get("license"):
        paragraphs.append(f"Licence: {entry['license']}")
    return "\n\n".join(paragraphs)


def contribution_checklist() -> list[str]:
    """Return an ordered checklist for contributing a graph to OKN.

    Source: docs/okn/contribute.md (§1.2, https://registry.okn.us/registry/contribute/),
    docs/okn/registry-help.md (§2-7, https://registry.okn.us/help/setup/ and
    https://registry.okn.us/help/update/), and
    docs/okn/contribute.md (§3, https://registry.okn.us/help/update-queries/).
    """

    return [
        "Create a registry entry PR at https://registry.okn.us/registry/contribute/ by adding "
        "docs/registry/kgs/<shortname>.md in the frink-okn/okn-registry repo. Leave out sparql "
        "and tpf; RENCI adds them once the endpoints exist.",
        "Request lakeFS Access Key ID / Secret Access Key through the OKN Slack or the contact "
        "given on https://registry.okn.us/help/setup/, including your dataset name.",
        "Upload data to the develop branch of the lakeFS repository at https://repository.okn.us/; "
        "for files greater than 1G the docs recommend S3 clients such as rclone or aws-cli and "
        "recommend no parallelization: https://registry.okn.us/help/setup/.",
        "Merge develop into main to trigger conversion to HDT and creation of a stable_vX_X_X "
        "branch; the submitter receives an email to review build outputs: "
        "https://registry.okn.us/help/update/.",
        "Create a tag to trigger deployment of the SPARQL and TPF endpoints: "
        "https://registry.okn.us/help/update/.",
        "Update example queries by editing docs/registry/queries/*.rq with YAML metadata headers "
        "when needed: https://registry.okn.us/help/update-queries/.",
    ]


def upload_commands(
    repo: str,
    local_dir: Path,
    *,
    endpoint: str = "https://repository.okn.us/",
    branch: str = "develop",
    tool: str = "rclone",
) -> list[str]:
    """Build shell commands for lakeFS uploads without executing them.

    Source: docs/okn/registry-help.md (§2-6, https://registry.okn.us/help/setup/ and
    https://registry.okn.us/help/update/).
    """

    source = local_dir.as_posix()
    target_name = local_dir.name or "dataset"
    credentials = [
        "export AWS_ACCESS_KEY_ID=<your-access-key-id>",
        "export AWS_SECRET_ACCESS_KEY=<your-secret-access-key>",
        f"export LAKEFS_ENDPOINT={endpoint}",
    ]
    if tool == "rclone":
        return [
            *credentials,
            "# Configure a lakeFS-compatible S3 remote named lakefs "
            "(storage type 5 / S3, then 31 / Other) with endpoint $LAKEFS_ENDPOINT.",
            "# The OKN docs recommend no parallelization for large uploads.",
            f"rclone copy --transfers 1 --checkers 1 {source} lakefs:{repo}/{branch}/{target_name}",
        ]
    if tool == "s5cmd":
        return [
            *credentials,
            "# Use s5cmd with --endpoint-url $LAKEFS_ENDPOINT; the docs recommend S3 clients "
            "for files greater than 1G and no parallelization.",
            f"s5cmd --endpoint-url $LAKEFS_ENDPOINT cp {source} s3://{repo}/{branch}/{target_name}",
        ]
    raise ValueError(f"Unsupported upload tool: {tool!r}")


def _entry_from_metadata(doc: GraphDocument) -> dict[str, Any]:
    """Extract registry-entry inputs from graph metadata (``entry``, then ``registry``)."""

    metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
    entry = metadata.get("entry")
    if isinstance(entry, dict):
        return entry
    registry = metadata.get("registry")
    if isinstance(registry, dict):
        return registry
    return {}


def _collect_iri_issues(doc: GraphDocument) -> list[str]:
    """Collect node and edge ids that would need percent-encoding in an IRI."""

    def unsafe(identifier: str) -> bool:
        # Absolute IRIs (e.g. nodes pulled from SPARQL) are used verbatim.
        return "://" not in identifier and _quote_iri_fragment(identifier) != identifier

    problems: list[str] = []
    for node in doc.nodes:
        if unsafe(node.id):
            problems.append(f"non-IRI-safe node id: {node.id!r}")
    for edge in doc.edges:
        if unsafe(edge.source):
            problems.append(f"non-IRI-safe edge source: {edge.source!r}")
        if unsafe(edge.target):
            problems.append(f"non-IRI-safe edge target: {edge.target!r}")
    return problems


def validate_package(doc: GraphDocument, out_dir: Path) -> list[str]:
    """Write the contribution package files and return validation problems.

    Source: docs/okn/contribute.md (§1.2, https://registry.okn.us/registry/contribute/) and
    docs/okn/registry-help.md (§2-6, https://registry.okn.us/help/setup/ and
    https://registry.okn.us/help/update/).

    Files written below ``out_dir``:

    - ``<shortname>.<fmt>`` -- the graph (default N-Quads, in the named graph
      ``https://purl.org/okn/frink/kg/<shortname>``),
    - ``registry/docs/registry/kgs/<shortname>.md`` -- the registry entry, laid out so
      the ``registry/`` directory can be copied onto a clone of ``frink-okn/okn-registry``,
    - ``checklist.md`` -- the contribution steps.

    Entry inputs come from ``doc.metadata["entry"]`` (``shortname``, ``title``,
    ``description``, ``homepage``, ``funding``, ``license``, ``source``, ``language``,
    ``body``, ``contacts``). Problems are reported rather than raised; files are written
    regardless.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []

    entry = _entry_from_metadata(doc)
    graph_name = doc.name or "graph"
    if not doc.name:
        problems.append("graph name is empty")
    problems.extend(_collect_iri_issues(doc))

    shortname = str(entry.get("shortname") or shortname_slug(graph_name))
    if not _SHORTNAME.fullmatch(shortname):
        problems.append(f"shortname must be lowercase letters, digits and hyphens: {shortname!r}")
    namespace_base = str(entry.get("namespace_base") or default_namespace_base(shortname))

    fmt = doc.metadata.get("fmt", "nq") if isinstance(doc.metadata, dict) else "nq"
    if fmt not in SUPPORTED_FORMATS:
        problems.append(f"unsupported fmt: {fmt!r}")
        fmt = "nq"

    graph_to_rdf(
        doc,
        out_dir / f"{shortname}.{fmt}",
        fmt=fmt,
        namespace_base=namespace_base,
        named_graph=bool(doc.name),
        entry=entry,
    )

    title = str(entry.get("title") or doc.name or graph_name)
    description = str(entry.get("description") or "")
    raw_contacts = entry.get("contacts")
    contacts = _normalise_contacts(raw_contacts) if isinstance(raw_contacts, list) else []
    if not contacts:
        problems.append("missing contacts in entry inputs")
    for number, contact in enumerate(contacts, start=1):
        if "email" not in contact:
            problems.append(f"contact {number} has no email")
    if not entry.get("homepage"):
        problems.append("missing homepage in entry inputs")
    if not description:
        problems.append("missing description in entry inputs")

    registry_markdown = registry_entry(
        shortname=shortname,
        title=title,
        description=description,
        contacts=contacts,
        homepage=str(entry["homepage"]) if entry.get("homepage") else None,
        funding=str(entry["funding"]) if entry.get("funding") else None,
        body=str(entry.get("body") or _default_body(entry, namespace_base)),
    )
    entry_file = out_dir / "registry" / registry_entry_path(shortname)
    entry_file.parent.mkdir(parents=True, exist_ok=True)
    entry_file.write_text(registry_markdown, encoding="utf-8")

    (out_dir / "checklist.md").write_text(
        "\n".join(f"- {item}" for item in contribution_checklist()) + "\n",
        encoding="utf-8",
    )

    return problems


def _parse_contact_value(value: str) -> dict[str, str]:
    """Parse a contact specification from the CLI."""

    value = value.strip()
    if value.startswith("{"):
        return {str(k): str(v) for k, v in json.loads(value).items()}
    result: dict[str, str] = {}
    for chunk in value.split(";"):
        if not chunk:
            continue
        key, sep, item = chunk.partition("=")
        if not sep:
            raise ValueError(f"invalid contact chunk: {chunk!r}")
        result[key.strip()] = item.strip()
    return result


def add_package_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``package`` options to ``parser`` (shared with the ``daf-okn`` CLI)."""

    parser.add_argument("--graph", required=True, type=Path, help="Path to a graph JSON document")
    parser.add_argument(
        "--out-dir", required=True, type=Path, help="Output directory for the package"
    )
    parser.add_argument(
        "--fmt",
        default="nq",
        choices=sorted(SUPPORTED_FORMATS),
        help="RDF serialization format for the graph file (default: nq)",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_ENTRIES),
        help="start from a ready-made registry entry (explicit --entry-* options override it)",
    )
    parser.add_argument("--entry-shortname", help="Registry shortname (lowercase, hyphens ok)")
    parser.add_argument("--entry-title", help="Registry title")
    parser.add_argument("--entry-description", help="Registry description")
    parser.add_argument("--entry-homepage", help="Registry homepage URL")
    parser.add_argument("--entry-funding", help="Registry funding URL (omitted when not given)")
    parser.add_argument("--entry-license", help="Licence URL, mentioned in the entry body")
    parser.add_argument("--entry-source", help="URL the graph was derived from (PROV-O)")
    parser.add_argument("--entry-body", default="", help="Markdown body text")
    parser.add_argument(
        "--contact",
        action="append",
        default=[],
        metavar="JSON_OR_KV",
        help="Contact mapping as JSON or email=...;github=...;label=... (repeatable)",
    )


def run_package(args: argparse.Namespace) -> int:
    """Run the ``package`` command for parsed ``args``; returns a process exit code."""

    doc = GraphDocument.from_dict(json.loads(args.graph.read_text(encoding="utf-8")))
    doc.metadata = dict(doc.metadata or {})
    doc.metadata["fmt"] = args.fmt
    entry: dict[str, Any] = dict(_entry_from_metadata(doc))
    if args.preset:
        entry = {**PRESET_ENTRIES[args.preset], **entry}
    for key, attr in (
        ("shortname", "entry_shortname"),
        ("title", "entry_title"),
        ("description", "entry_description"),
        ("homepage", "entry_homepage"),
        ("funding", "entry_funding"),
        ("license", "entry_license"),
        ("source", "entry_source"),
        ("body", "entry_body"),
    ):
        value = getattr(args, attr)
        if value:
            entry[key] = value
    if args.contact:
        entry["contacts"] = [_parse_contact_value(value) for value in args.contact]
    if entry:
        doc.metadata["entry"] = entry
    problems = validate_package(doc, args.out_dir)
    if problems:
        for problem in problems:
            print(problem)
        return 1
    print(f"Wrote package to {args.out_dir}")
    return 0


def _build_cli() -> argparse.ArgumentParser:
    """Construct the thin register-graph CLI."""

    parser = argparse.ArgumentParser(prog="register_graph")
    subparsers = parser.add_subparsers(dest="command", required=True)

    package = subparsers.add_parser(
        "package", help="Write graph, registry entry, and checklist files"
    )
    add_package_arguments(package)

    subparsers.add_parser("checklist", help="Print the contribution checklist")

    upload = subparsers.add_parser("upload-commands", help="Print upload command strings")
    upload.add_argument("--repo", required=True, help="LakeFS repository name")
    upload.add_argument("--dir", required=True, type=Path, help="Local directory or file to upload")
    upload.add_argument(
        "--endpoint", default="https://repository.okn.us/", help="LakeFS endpoint URL"
    )
    upload.add_argument("--branch", default="develop", help="Destination branch")
    upload.add_argument(
        "--tool",
        default="rclone",
        choices=["rclone", "s5cmd"],
        help="Upload tool",
    )

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point for contribution packaging."""

    parser = _build_cli()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "checklist":
        for item in contribution_checklist():
            print(item)
        return 0

    if args.command == "upload-commands":
        for command in upload_commands(
            args.repo,
            args.dir,
            endpoint=args.endpoint,
            branch=args.branch,
            tool=args.tool,
        ):
            print(command)
        return 0

    if args.command == "package":
        return run_package(args)

    raise AssertionError(f"unhandled command: {args.command!r}")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
