"""Command-line interface for daf-okn: ``daf-okn <command>`` or ``python -m daf_okn <command>``.

Commands (each is a thin wrapper over the library):

* ``pull``      -- list / snapshot the OKN registry, or run a SPARQL query
                   (:mod:`daf_okn.core.registry`; these commands use the network,
                   and ``--kgs-path`` reads a local ``kgs.yaml`` instead).
* ``export``    -- turn an Obsidian-style markdown vault (e.g. the Active Inference
                   Institute ``cognitive`` knowledge base) into a graph JSON document
                   (:mod:`daf_okn.core.cognitive_adapter`).
* ``analyze``   -- structural metrics and a JSON report for a graph document
                   (:mod:`daf_okn.analysis.pipeline`).
* ``visualize`` -- network figure and static HTML dashboard
                   (:mod:`daf_okn.figures`, :mod:`daf_okn.dashboard`).
* ``package``   -- OKN contribution package: RDF with standard vocabularies, registry
                   entry and checklist (:mod:`daf_okn.core.contribute`).

Exit status is 0 on success and 1 on a reported failure; argument errors exit 2.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .analysis import cross_graph
from .core import rdf_submission
from .core.contribute import add_package_arguments, run_package
from .core.registry import OKNRegistry, RegistryError

__all__ = ["build_parser", "main"]

COGNITIVE_REPO_ENV = "DAF_OKN_COGNITIVE_REPO"


def _cmd_status(args: argparse.Namespace) -> int:
    from .analysis.artifact_status import inspect_artifacts

    observation = inspect_artifacts(args.graph, args.report)
    print(json.dumps(observation, indent=2, sort_keys=True))
    return 0 if observation["status"] == "pass" else 1


def _cmd_join(args: argparse.Namespace) -> int:
    cross_graph.run(
        cross_graph.JoinOptions(args.source, args.query, args.output, args.endpoint, args.replay)
    )
    return 0


def _cmd_bundle_rdf(args: argparse.Namespace) -> int:
    if args.check:
        errors = rdf_submission.verify(args.output)
        print(json.dumps({"bundle_verified": not errors, "errors": errors}, indent=2))
        return 1 if errors else 0
    rdf_submission.prepare(args.root.resolve(), args.output.resolve())
    return 0


# ----------------------------------------------------------------------------- pull
def _cmd_pull_list(args: argparse.Namespace) -> int:
    graphs = OKNRegistry(timeout=args.timeout).list_graphs(kgs_path=args.kgs_path)
    header = f"{'shortname':<24} {'title':<40} sparql"
    print(header)
    print("-" * len(header))
    for entry in sorted(graphs, key=lambda item: str(item.get("shortname", ""))):
        title = str(entry.get("title", ""))[:40]
        print(f"{entry.get('shortname', '')!s:<24} {title:<40} {entry.get('sparql') or '-'}")
    print(f"\n{len(graphs)} graphs")
    return 0


def _cmd_pull_snapshot(args: argparse.Namespace) -> int:
    graphs = OKNRegistry(timeout=args.timeout).list_graphs(kgs_path=args.kgs_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"kgs": graphs}, handle, sort_keys=False, allow_unicode=True)
    print(f"wrote {len(graphs)} graph entries to {args.out}")
    return 0


def _cmd_pull_query(args: argparse.Namespace) -> int:
    payload = OKNRegistry(timeout=args.timeout).sparql(args.sparql, shortname=args.shortname)
    out = args.out or Path("output") / "data" / f"{args.shortname}_query.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    results = payload.get("results")
    bindings = results.get("bindings", []) if isinstance(results, dict) else []
    print(f"wrote {len(bindings) if isinstance(bindings, list) else 0} rows to {out}")
    return 0


# --------------------------------------------------------------------------- export
def _cmd_export(args: argparse.Namespace) -> int:
    from .core.cognitive_adapter import default_graph_name, export_cognitive_kb, vault_root

    if not args.repo:
        raise SystemExit(f"error: --repo is required (or set ${COGNITIVE_REPO_ENV})")
    repo = Path(args.repo).expanduser()
    if not repo.is_dir():
        raise SystemExit(f"error: not a directory: {repo}")
    options: dict[str, Any] = {
        "collapse_redirects": not args.keep_redirects,
        "include_wikilinks": not args.no_wikilinks,
    }
    options["name"] = args.name or default_graph_name(repo)
    document = export_cognitive_kb(repo, args.out, **options)
    counts = document.metadata.get("counts", {})
    print(f"graph: {document.name}")
    for label, key in (
        ("nodes", "nodes"),
        ("edges", "edges"),
        ("semantic edges", "semantic_edges"),
        ("wikilink edges", "wikilink_edges"),
        ("redirect edges", "redirect_edges"),
        ("unresolved targets", "unresolved_targets"),
    ):
        print(f"  {label}: {counts.get(key, 0)}")
    print(f"  vault: {vault_root(repo).name}")
    print(f"  written: {args.out}")
    return 0


# -------------------------------------------------------------------------- analyze
def _cmd_analyze(args: argparse.Namespace) -> int:
    from .analysis.pipeline import run_analysis
    from .core.graph import GraphDocument

    report = run_analysis(GraphDocument.load_json(args.graph), args.out_dir)
    metrics = report["metrics"]
    print(f"Wrote {report['report_path']}")
    print(
        f"nodes={metrics['node_count']} edges={metrics['edge_count']} "
        f"density={metrics['density']:.4f}"
    )
    for problem in report["problems"]:
        print(f"problem: {problem}", file=sys.stderr)
    return 1 if report["problems"] else 0


# ------------------------------------------------------------------------ visualize
def _cmd_visualize(args: argparse.Namespace) -> int:
    from .core.graph import GraphDocument
    from .dashboard.dashboard import build_dashboard
    from .figures.network_figure import plot_network

    document = GraphDocument.load_json(args.graph)
    if not args.no_figure:
        print(plot_network(document, args.figure, layout=args.layout))
    if not args.no_dashboard:
        metrics: dict[str, Any] | None = None
        if args.metrics is not None:
            loaded = json.loads(args.metrics.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise SystemExit("error: --metrics file must contain a JSON object")
            metrics = loaded
        print(build_dashboard(document, metrics, args.dashboard))
    return 0


# ---------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    """Build the ``daf-okn`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="daf-okn",
        description=(
            "Pull, analyze, visualize and contribute to the Open Knowledge Network "
            "(okn.us). Run `daf-okn <command> --help` for each command."
        ),
    )
    parser.add_argument("--version", action="version", version=f"daf-okn {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    pull = commands.add_parser(
        "pull",
        help="list or snapshot the OKN registry, or run a SPARQL query (network)",
        description="Registry access. Needs the network unless --kgs-path is given.",
    )
    pull.add_argument("--timeout", type=float, default=30.0, help="per-request timeout, seconds")
    pull_commands = pull.add_subparsers(dest="pull_command", required=True, metavar="<what>")

    listing = pull_commands.add_parser("list", help="print the registered graphs")
    listing.add_argument("--kgs-path", help="read this local kgs.yaml instead of fetching it")
    listing.set_defaults(func=_cmd_pull_list)

    snapshot = pull_commands.add_parser(
        "snapshot", aliases=["save-snapshot"], help="save the registry metadata as YAML"
    )
    snapshot.add_argument("--kgs-path", help="read this local kgs.yaml instead of fetching it")
    snapshot.add_argument(
        "--out",
        type=Path,
        default=Path("data/okn/kgs.yaml"),
        help="output YAML (default: %(default)s)",
    )
    snapshot.set_defaults(func=_cmd_pull_snapshot)

    query = pull_commands.add_parser("query", help="run a SPARQL query against one graph")
    query.add_argument("--shortname", required=True, help="registry shortname of the graph")
    query.add_argument("--sparql", required=True, help="SPARQL query text")
    query.add_argument(
        "--out", type=Path, help="output JSON (default: output/data/<shortname>_query.json)"
    )
    query.set_defaults(func=_cmd_pull_query)

    export = commands.add_parser(
        "export",
        help="turn a markdown vault (e.g. the cognitive knowledge base) into a graph JSON",
        description=(
            "Read an Obsidian-style vault: one page is one node, [[wiki links]] and "
            "semantic_relations frontmatter are edges. REPO may be a `cognitive` checkout "
            "(its knowledge_base/ directory is used) or any vault directory."
        ),
    )
    export.add_argument(
        "--repo",
        default=os.environ.get(COGNITIVE_REPO_ENV),
        help=f"cognitive repository or vault directory (default: ${COGNITIVE_REPO_ENV})",
    )
    export.add_argument(
        "--out",
        type=Path,
        default=Path("output/data/cognitive_kg.json"),
        help="output graph JSON (default: %(default)s)",
    )
    export.add_argument(
        "--name",
        help="graph name (default: cognitive-kb for a cognitive checkout, else the directory name)",
    )
    export.add_argument(
        "--keep-redirects",
        action="store_true",
        help="keep redirect pages instead of collapsing them",
    )
    export.add_argument(
        "--no-wikilinks", action="store_true", help="keep only semantic_relations edges"
    )
    export.set_defaults(func=_cmd_export)

    analyze = commands.add_parser("analyze", help="compute graph metrics and write a JSON report")
    analyze.add_argument("--graph", required=True, type=Path, help="graph JSON document")
    analyze.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output/analysis"),
        help="directory for graph_report.json (default: %(default)s)",
    )
    analyze.set_defaults(func=_cmd_analyze)

    visualize = commands.add_parser(
        "visualize", help="render a network figure and an HTML dashboard"
    )
    visualize.add_argument("--graph", required=True, type=Path, help="graph JSON document")
    visualize.add_argument(
        "--figure",
        type=Path,
        default=Path("output/figures/network.png"),
        help="figure PNG path (default: %(default)s)",
    )
    visualize.add_argument(
        "--dashboard",
        type=Path,
        default=Path("output/web/dashboard.html"),
        help="dashboard HTML path (default: %(default)s)",
    )
    visualize.add_argument(
        "--metrics", type=Path, help="precomputed metrics JSON for the dashboard"
    )
    visualize.add_argument(
        "--layout", default="spring", help="figure layout (default: %(default)s)"
    )
    visualize.add_argument("--no-figure", action="store_true", help="skip the figure")
    visualize.add_argument("--no-dashboard", action="store_true", help="skip the dashboard")
    visualize.set_defaults(func=_cmd_visualize)

    package = commands.add_parser(
        "package",
        help="write an OKN contribution package (RDF, registry entry, checklist)",
        description=(
            "Write <shortname>.<fmt> (RDF using SKOS / Dublin Core Terms / schema.org, entity IRIs "
            "under https://purl.org/okn/frink/kg/<shortname>/), the registry entry at "
            "registry/docs/registry/kgs/<shortname>.md, and checklist.md. Exits 1 and lists "
            "problems if the entry inputs are incomplete."
        ),
    )
    add_package_arguments(package)
    package.set_defaults(func=run_package)
    join = commands.add_parser("join", help="capture or replay a cross-graph RDF join")
    join.add_argument("--source", required=True, type=Path)
    join.add_argument("--query", required=True, type=Path)
    join.add_argument("--output", required=True, type=Path)
    join.add_argument("--endpoint", default=cross_graph.ENDPOINT)
    join.add_argument("--replay", type=Path, help="captured response directory")
    join.set_defaults(func=_cmd_join)
    bundle = commands.add_parser("bundle-rdf", help="verify and package canonical cognitive RDF")
    bundle.add_argument("--root", default=Path("."), type=Path)
    bundle.add_argument("--output", required=True, type=Path)
    bundle.add_argument("--check", action="store_true")
    bundle.set_defaults(func=_cmd_bundle_rdf)
    status = commands.add_parser(
        "status", help="inspect existing graph/report evidence offline (JSON)"
    )
    status.add_argument("--graph", required=True, type=Path, help="existing graph JSON")
    status.add_argument("--report", type=Path, help="existing graph_report.json to remeasure")
    status.set_defaults(func=_cmd_status)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        return int(args.func(args))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
