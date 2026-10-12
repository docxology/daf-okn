"""Manuscript variable generation for the daf-okn graph pipeline.

Called exclusively by ``scripts/z_generate_manuscript_variables.py`` (thin
orchestrator), :func:`generate_variables` reads:

* ``manuscript/config.yaml`` — paper metadata (title, subtitle, version,
  authors, keywords) consumed for the ``CONFIG_*`` tokens, and
* ``output/data/graph_report.json`` — the JSON report written by
  :func:`daf_okn.analysis.pipeline.run_analysis` (wired through
  ``scripts/analyze_graph.py``), consumed for the graph-metric tokens.

The returned flat ``{{TOKEN}}`` map is written to
``output/data/manuscript_variables.json`` by :func:`save_variables` and
substituted into ``output/manuscript/`` copies of the chapters by
:func:`write_resolved_manuscript`. No result numbers are hardcoded in prose:
every quantitative claim in the manuscript chapters is one of these tokens.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ._runtime import get_logger

logger = get_logger(__name__)

REPORT_PATH = Path("output") / "data" / "graph_report.json"

# Report-derived tokens: filled from the metrics block of graph_report.json.
_GRAPH_TOKENS: tuple[str, ...] = (
    "GRAPH_NAME",
    "NODE_COUNT",
    "EDGE_COUNT",
    "DENSITY_PCT",
    "WEAKLY_CONNECTED_COMPONENTS",
    "STRONGLY_CONNECTED_COMPONENTS",
    "MEAN_DEGREE",
    "TRIANGLE_COUNT",
    "TOP_NODE_LABEL",
    "TOP_NODE_CENTRALITY",
)

_DRAFT_SENTINEL = "N/A"


# ---------------------------------------------------------------------------
# I/O helpers — thin readers, no business logic
# ---------------------------------------------------------------------------


def _load_config(config_path: Path) -> dict[str, Any]:
    """Load ``manuscript/config.yaml``; an absent file degrades to ``{}``."""
    if not config_path.is_file():
        logger.warning("Manuscript config not found: %s", config_path)
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_graph_report(project_root: Path) -> dict[str, Any]:
    """Load ``output/data/graph_report.json``; an absent file degrades to ``{}``."""
    report_path = project_root / REPORT_PATH
    if not report_path.is_file():
        return {}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Malformed graph report %s: %s", report_path, exc)
        return {}
    return report if isinstance(report, dict) else {}


def _build_timestamp() -> str:
    """Build timestamp, honoring ``SOURCE_DATE_EPOCH`` for reproducible builds."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        try:
            moment = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
            return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError, OverflowError):
            logger.warning("Invalid SOURCE_DATE_EPOCH %r — using wall clock", epoch)
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_config_hash(config_path: Path) -> str:
    """Return a short SHA-256 fingerprint of ``config.yaml`` (or a sentinel)."""
    if not config_path.is_file():
        return _DRAFT_SENTINEL
    return hashlib.sha256(config_path.read_bytes()).hexdigest()[:16]


def _library_versions() -> dict[str, str]:
    """Return the versions of the graph stack pinned into the environment table."""
    versions: dict[str, str] = {}
    for module_name, token in (
        ("networkx", "NETWORKX_VERSION"),
        ("matplotlib", "MATPLOTLIB_VERSION"),
    ):
        try:
            module = __import__(module_name)
            versions[token] = str(getattr(module, "__version__", "unknown"))
        except Exception as exc:  # pragma: no cover — import guard for exotic installs
            logger.warning("Could not read %s version: %s", module_name, exc)
            versions[token] = "unknown"
    return versions


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------


def _graph_token_strings(report: dict[str, Any]) -> dict[str, str]:
    """Map a ``graph_report.json`` payload onto the flat token strings.

    The report shape is the one written by
    :func:`daf_okn.analysis.pipeline.run_analysis`: ``graph_name`` plus
    ``metrics`` (see :func:`daf_okn.analysis.graph_metrics.compute_metrics`).
    Anything missing degrades to the draft sentinel.
    """
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        return {token: _DRAFT_SENTINEL for token in _GRAPH_TOKENS}
    density = float(metrics.get("density", 0.0))
    top_nodes = metrics.get("top_central_nodes") or []
    if top_nodes:
        top_label, top_score = top_nodes[0][0], float(top_nodes[0][1])
    else:
        top_label, top_score = _DRAFT_SENTINEL, 0.0
    return {
        "GRAPH_NAME": str(report.get("graph_name") or _DRAFT_SENTINEL),
        "NODE_COUNT": str(int(metrics.get("node_count", 0))),
        "EDGE_COUNT": str(int(metrics.get("edge_count", 0))),
        "DENSITY_PCT": f"{density * 100:.2f}",
        "WEAKLY_CONNECTED_COMPONENTS": str(int(metrics.get("weakly_connected_components", 0))),
        "STRONGLY_CONNECTED_COMPONENTS": str(int(metrics.get("strongly_connected_components", 0))),
        "MEAN_DEGREE": f"{float(metrics.get('mean_degree', 0.0)):.2f}",
        "TRIANGLE_COUNT": str(int(metrics.get("triangles", 0))),
        "TOP_NODE_LABEL": str(top_label),
        "TOP_NODE_CENTRALITY": f"{top_score:.4f}",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_variables(
    config_path: Path, *, require_analysis_outputs: bool = True
) -> dict[str, str]:
    """Generate all manuscript variables from config and the graph report.

    Args:
        config_path: Path to ``manuscript/config.yaml``. The project root is
            its parent directory, so the graph report is read from
            ``<root>/output/data/graph_report.json``.
        require_analysis_outputs: When True (pipeline path), a missing or
            malformed graph report raises :class:`FileNotFoundError` instead of
            emitting ``"N/A"`` sentinels. Draft callers (``--allow-draft``)
            pass False so the manuscript still renders without analysis
            outputs.

    Returns:
        Flat ``dict[str, str]`` of token name → value (no surrounding braces),
        ready for :func:`save_variables` and :func:`write_resolved_manuscript`.
    """
    config_path = Path(config_path)
    project_root = config_path.resolve().parent.parent
    config = _load_config(config_path)
    report = _load_graph_report(project_root)

    if require_analysis_outputs and not report.get("metrics"):
        report_path = project_root / REPORT_PATH
        raise FileNotFoundError(
            f"Analysis outputs required but missing or empty: {report_path}. "
            "Run scripts/analyze_graph.py --graph <graph.json> --out-dir output/data first."
        )

    variables: dict[str, str] = {}

    # ---- Configuration-derived ----
    paper = config.get("paper", {}) if isinstance(config, dict) else {}
    variables["CONFIG_TITLE"] = str(paper.get("title", _DRAFT_SENTINEL))
    variables["CONFIG_SUBTITLE"] = str(paper.get("subtitle", _DRAFT_SENTINEL))
    variables["CONFIG_VERSION"] = str(paper.get("version", "1.0"))
    authors = config.get("authors", []) if isinstance(config, dict) else []
    variables["CONFIG_FIRST_AUTHOR"] = (
        str(authors[0].get("name", "Unknown")) if authors else "Unknown"
    )
    keywords = config.get("keywords", []) if isinstance(config, dict) else []
    variables["CONFIG_KEYWORDS"] = ", ".join(str(keyword) for keyword in keywords)

    # ---- Graph-report-derived ----
    if report:
        variables.update(_graph_token_strings(report))
    else:
        logger.warning(
            "No graph report available — using %r sentinels for graph tokens",
            _DRAFT_SENTINEL,
        )
        variables.update(dict.fromkeys(_GRAPH_TOKENS, _DRAFT_SENTINEL))

    # ---- Provenance ----
    variables["CONFIG_HASH"] = _compute_config_hash(config_path)
    # Deterministic when SOURCE_DATE_EPOCH is set (pipeline deterministic mode)
    # so the rendered manuscript is byte-stable; wall-clock otherwise.
    variables["GENERATION_TIMESTAMP"] = _build_timestamp()
    variables["PYTHON_VERSION"] = platform.python_version()
    variables["PLATFORM"] = f"{platform.system()} {platform.machine()}"
    variables.update(_library_versions())

    logger.info("Generated %d manuscript variables", len(variables))
    return variables


def save_variables(variables: dict[str, str], output_path: Path) -> Path:
    """Persist *variables* as JSON for downstream rendering and debugging.

    Args:
        variables: The flat token → value mapping from :func:`generate_variables`.
        output_path: Destination ``.json`` file (parent is created if absent).

    Returns:
        Resolved path to the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(variables, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved %d variables to %s", len(variables), output_path)
    return output_path


_TOKEN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
_CHAPTER = re.compile(r"\d{2}_.*\.md")
# Generic placeholder names that the chapters quote when explaining the syntax.
_SYNTAX_EXAMPLES = frozenset({"TOKEN", "MY_TOKEN"})


def write_resolved_manuscript(
    manuscript_dir: Path, output_dir: Path, variables: dict[str, str]
) -> dict[str, list[str]]:
    """Copy the chapters (``NN_*.md``) into ``output_dir`` with ``{{TOKEN}}`` markers substituted.

    Tokens missing from ``variables`` are left in place so they stay visible. The generic
    names ``TOKEN`` and ``MY_TOKEN``, which chapters quote to explain the syntax, are left
    alone and not reported. Documentation files (``README.md``, ``AGENTS.md``,
    ``SYNTAX.md``) are not copied.

    Returns:
        ``{file name: [unresolved token names]}`` for every file written (an empty list
        means the file is fully resolved).
    """
    manuscript_dir, output_dir = Path(manuscript_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    unresolved: dict[str, list[str]] = {}
    for source in sorted(manuscript_dir.glob("*.md")):
        if not _CHAPTER.fullmatch(source.name):
            continue
        text = source.read_text(encoding="utf-8")
        missing: list[str] = []

        def replace(match: re.Match[str], missing: list[str] = missing) -> str:
            name = match.group(1)
            if name in variables:
                return str(variables[name])
            if name not in _SYNTAX_EXAMPLES:
                missing.append(name)
            return match.group(0)

        (output_dir / source.name).write_text(_TOKEN.sub(replace, text), encoding="utf-8")
        unresolved[source.name] = sorted(set(missing))
    return unresolved


__all__ = [
    "REPORT_PATH",
    "generate_variables",
    "save_variables",
    "write_resolved_manuscript",
]
