#!/usr/bin/env python3
"""Research workflow: registry pull -> cognitive export -> graph analysis -> figures.

Stage ``10`` of the daf-okn pipeline. Chains the research stages as in-process
calls (no subprocesses), reusing the same modules the thin CLI wrappers
delegate to:

1. **pull_registry** — enumerate the OKN registry graph list (``kgs.yaml``)
   via :class:`daf_okn.core.registry.OKNRegistry` and snapshot it to
   ``output/data/registry_snapshot.yaml``.
2. **export_cognitive** — export the Active Inference Institute ``cognitive``
   knowledge base to a typed graph via
   :func:`daf_okn.core.cognitive_adapter.export_cognitive_kb`. Skipped when no
   repository root is configured (``--cognitive-repo`` or
   ``$DAF_OKN_COGNITIVE_REPO``).
3. **analyze_graph** — measure the exported graph with
   :func:`daf_okn.analysis.pipeline.run_analysis`, writing
   ``output/data/graph_report.json`` — the file
   ``scripts/z_generate_manuscript_variables.py`` hydrates the manuscript from.
4. **visualize** — render ``output/figures/registry_catalog.png`` (one bar per
   registered graph) and, when a graph was analyzed, the spring-layout
   network figure ``output/figures/cognitive_network.png`` via
   :mod:`daf_okn.figures.network_figure`.

Exit codes: 0 all stages ran (or skipped by design), 1 on any stage failure.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    path_text = str(_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from daf_okn.analysis.pipeline import run_analysis  # noqa: E402
from daf_okn.core.cognitive_adapter import export_cognitive_kb  # noqa: E402
from daf_okn.core.graph import GraphDocument  # noqa: E402
from daf_okn.core.registry import OKNRegistry, RegistryError  # noqa: E402
from daf_okn.figures.network_figure import plot_graph_catalog, plot_network  # noqa: E402

logger = logging.getLogger("daf_okn.scripts.research_workflow")

DATA_DIR = PROJECT_ROOT / "output" / "data"
SNAPSHOT_PATH = DATA_DIR / "registry_snapshot.yaml"
COGNITIVE_GRAPH_PATH = DATA_DIR / "cognitive_kg.json"
REPORT_DIR = DATA_DIR


def stage_pull_registry(registry: OKNRegistry | None = None) -> int:
    """Snapshot the OKN registry graph list; returns a process exit code."""
    registry = registry or OKNRegistry()
    graphs = registry.list_graphs()
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        yaml.safe_dump({"kgs": graphs}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("[run] pull_registry: %d graphs -> %s", len(graphs), SNAPSHOT_PATH)
    return 0


def stage_export_cognitive(repo_root: Path | None) -> tuple[int, Path | None]:
    """Export the cognitive knowledge base; returns (exit code, graph path).

    A missing repository root skips the stage by design (exit 0, ``None``).
    """
    if repo_root is None:
        logger.info("[skip] export_cognitive: no cognitive repository configured")
        return 0, None
    COGNITIVE_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    document = export_cognitive_kb(repo_root, COGNITIVE_GRAPH_PATH)
    counts = document.metadata.get("counts", {})
    logger.info(
        "[run] export_cognitive: %s nodes=%s edges=%s -> %s",
        document.name,
        counts.get("nodes", len(document.nodes)),
        counts.get("edges", len(document.edges)),
        COGNITIVE_GRAPH_PATH,
    )
    return 0, COGNITIVE_GRAPH_PATH


def stage_analyze_graph(graph_path: Path) -> int:
    """Measure the graph document and write the report; returns an exit code.

    The stage fails (exit 1) when ``validate_graph`` reports structural
    problems, so an invalid document cannot silently pass into the report
    the manuscript hydrates from. The report is still written for audit.
    """
    document = GraphDocument.load_json(graph_path)
    report = run_analysis(document, REPORT_DIR)
    metrics = report["metrics"]
    logger.info(
        "[run] analyze_graph: nodes=%d edges=%d density=%.4f -> %s",
        metrics["node_count"],
        metrics["edge_count"],
        metrics["density"],
        report["report_path"],
    )
    problems = report.get("problems") or []
    if problems:
        for problem in problems:
            logger.error("graph invariant violated: %s", problem)
        return 1
    return 0


def stage_visualize(graph_path: Path | None) -> int:
    """Render the registry catalog and analyzed-network figures; returns an exit code."""
    figures_dir = PROJECT_ROOT / "output" / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    if SNAPSHOT_PATH.is_file():
        snapshot = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8")) or {}
        catalog_path = plot_graph_catalog(
            list(snapshot.get("kgs", [])), figures_dir / "registry_catalog.png"
        )
        logger.info("[run] visualize: registry catalog -> %s", catalog_path)
    if graph_path is not None:
        network_path = plot_network(
            GraphDocument.load_json(graph_path), figures_dir / "cognitive_network.png"
        )
        logger.info("[run] visualize: network figure -> %s", network_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the workflow argument parser."""
    parser = argparse.ArgumentParser(description="Run the daf-okn research workflow end to end")
    parser.add_argument(
        "--cognitive-repo",
        default=os.environ.get("DAF_OKN_COGNITIVE_REPO"),
        help="cognitive repository root for stage 2 (default: $DAF_OKN_COGNITIVE_REPO)",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=None,
        help="analyze this GraphDocument JSON in stage 3 instead of the cognitive export",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    try:
        if stage_pull_registry() != 0:
            return 1
        code, exported = stage_export_cognitive(
            Path(args.cognitive_repo).expanduser() if args.cognitive_repo else None
        )
        if code != 0:
            return 1
        graph_path = args.graph if args.graph is not None else exported
        if graph_path is not None:
            graph_path = graph_path if graph_path.is_absolute() else PROJECT_ROOT / graph_path
            if stage_analyze_graph(graph_path) != 0:
                return 1
        else:
            logger.warning(
                "[skip] analyze_graph: no graph to analyze (configure --cognitive-repo or --graph)"
            )
        return stage_visualize(graph_path)
    except (RegistryError, OSError, ValueError, KeyError) as exc:
        logger.error("research workflow failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
