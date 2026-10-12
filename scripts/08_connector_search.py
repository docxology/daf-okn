#!/usr/bin/env python3
"""Connector search over the OKN registry graph list.

Stage ``08`` of the daf-okn pipeline: enumerate the registry graphs from
``kgs.yaml`` via :class:`daf_okn.core.registry.OKNRegistry`, then run each
configured keyword through the OKN embeddings service
(:meth:`OKNRegistry.embedding_search`, api-notes §5.2) — a scored,
cross-graph "connector" search over the hosted knowledge graphs.

Queries default to the ``keywords`` list in ``manuscript/config.yaml``.
Results are written to ``output/data/connector_search/results.json``:

    {
      "graphs_considered": ["biohealth", ...],
      "queries": {"<keyword>": [ <scored match objects from the service> ]}
    }

Usage::

    python scripts/08_connector_search.py [--kgs-path kgs.yaml] [--limit 5]
        [--keywords kw1,kw2]

``--kgs-path`` reads a local ``kgs.yaml`` snapshot instead of fetching the
live registry file (offline use and tests).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    path_text = str(_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from daf_okn.core.registry import OKNRegistry, RegistryError  # noqa: E402

logger = logging.getLogger("daf_okn.scripts.connector_search")

DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "data" / "connector_search" / "results.json"


def _keywords_from_config(config_path: Path) -> list[str]:
    """Return the ``keywords`` list from ``manuscript/config.yaml``."""
    if not config_path.is_file():
        return []
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return [str(keyword) for keyword in config.get("keywords", [])]


def build_parser() -> argparse.ArgumentParser:
    """Build the connector-search argument parser."""
    parser = argparse.ArgumentParser(
        description="Search the OKN graphs via the registry + embeddings service"
    )
    parser.add_argument(
        "--kgs-path",
        type=Path,
        default=None,
        help="local kgs.yaml snapshot to enumerate instead of fetching the live registry file",
    )
    parser.add_argument(
        "--keywords",
        default=None,
        help="comma-separated query keywords (default: manuscript/config.yaml keywords)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="maximum matches per keyword (default: 5)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output JSON path (default: {DEFAULT_OUTPUT})",
    )
    return parser


def run_connector_search(
    registry: OKNRegistry,
    keywords: list[str],
    *,
    limit: int,
    kgs_path: Path | None = None,
) -> dict[str, object]:
    """Enumerate the registry graphs and run each keyword through embeddings.

    Returns the result document written by the CLI. Per-keyword failures are
    logged and skipped so one bad endpoint does not sink the stage.
    """
    graphs = registry.list_graphs(kgs_path=str(kgs_path) if kgs_path else None)
    shortnames = [str(entry.get("shortname", "")) for entry in graphs]
    logger.info("Registry lists %d graphs", len(shortnames))

    queries: dict[str, object] = {}
    for keyword in keywords:
        try:
            payload = registry.embedding_search("text", keyword, limit=limit)
        except (RegistryError, ValueError) as exc:
            logger.warning("keyword %r failed: %s", keyword, exc)
            queries[keyword] = {"error": str(exc)}
            continue
        matches = payload.get("results", []) if isinstance(payload, dict) else []
        logger.info("  %r -> %d matches", keyword, len(matches))
        queries[keyword] = matches
    return {"graphs_considered": shortnames, "queries": queries}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    if args.keywords is not None:
        keywords = [part.strip() for part in args.keywords.split(",") if part.strip()]
    else:
        keywords = _keywords_from_config(PROJECT_ROOT / "manuscript" / "config.yaml")
    if not keywords:
        logger.error(
            "no keywords to search (manuscript/config.yaml has no keywords; use --keywords)"
        )
        return 1

    registry = OKNRegistry()
    try:
        document = run_connector_search(
            registry, keywords, limit=args.limit, kgs_path=args.kgs_path
        )
    except (RegistryError, OSError) as exc:
        logger.error("registry graph list failed: %s", exc)
        return 1

    out_path = args.out if args.out.is_absolute() else PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    logger.info("Connector search results written to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
