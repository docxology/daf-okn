#!/usr/bin/env python3
"""Provenance record for a packaged OKN graph contribution.

Stage ``09`` of the daf-okn pipeline: load a :class:`daf_okn.core.graph.
GraphDocument` JSON file, run the contribution packager/validator
(:func:`daf_okn.core.contribute.validate_package` — N-Quads serialization,
registry entry draft, checklist), and record a provenance receipt JSON with
SHA-256 hashes of every generated package artifact.

Usage::

    python scripts/09_provenance_record.py --graph output/data/cognitive_kg.json \
        [--out-dir output/data/provenance]

Outputs under ``--out-dir``:

* ``package/`` — the contribution package written by ``validate_package``
* ``provenance_record.json`` — the receipt

Exit codes: 0 when the packager reports no problems, 1 otherwise (the receipt
is still written so the failure is auditable).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    path_text = str(_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from daf_okn.core.contribute import PRESET_ENTRIES, validate_package  # noqa: E402
from daf_okn.core.graph import GraphDocument  # noqa: E402

logger = logging.getLogger("daf_okn.scripts.provenance_record")

DEFAULT_OUT_DIR = PROJECT_ROOT / "output" / "data" / "provenance"


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of *path*'s bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_provenance(
    doc: GraphDocument,
    problems: list[str],
    package_dir: Path,
    record_path: Path,
) -> dict[str, object]:
    """Write and return the provenance receipt for one packaged graph."""
    artifacts = {
        str(path.relative_to(record_path.parent)): _sha256(path)
        for path in sorted(package_dir.rglob("*"))
        if path.is_file()
    }
    record: dict[str, object] = {
        "graph": doc.name,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "node_count": len(doc.nodes),
        "edge_count": len(doc.edges),
        "package_dir": str(package_dir),
        "problems": problems,
        "artifact_sha256": artifacts,
    }
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def build_parser() -> argparse.ArgumentParser:
    """Build the provenance-recorder argument parser."""
    parser = argparse.ArgumentParser(
        description="Record a provenance receipt for a packaged graph contribution"
    )
    parser.add_argument(
        "--graph",
        required=True,
        type=Path,
        help="path to a GraphDocument JSON file (as written by GraphDocument.save_json)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"directory for the package and receipt (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_ENTRIES),
        help="use a ready-made registry entry when the graph document carries none",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    graph_path = args.graph if args.graph.is_absolute() else PROJECT_ROOT / args.graph
    out_dir = args.out_dir if args.out_dir.is_absolute() else PROJECT_ROOT / args.out_dir

    doc = GraphDocument.load_json(graph_path)
    if args.preset and not doc.metadata.get("entry"):
        doc.metadata["entry"] = dict(PRESET_ENTRIES[args.preset])
    package_dir = out_dir / "package"
    problems = validate_package(doc, package_dir)
    record_path = out_dir / "provenance_record.json"
    _record_provenance(doc, problems, package_dir, record_path)

    logger.info(
        "Packaged %s (%d nodes, %d edges) -> %s",
        doc.name,
        len(doc.nodes),
        len(doc.edges),
        package_dir,
    )
    logger.info("Provenance receipt written to %s", record_path)
    if problems:
        for problem in problems:
            logger.error("package problem: %s", problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
