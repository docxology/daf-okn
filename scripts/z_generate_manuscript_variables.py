#!/usr/bin/env python3
"""Thin orchestrator: generate manuscript variables and resolve the chapters.

Reads ``docs/manuscript/config.yaml`` and ``output/data/graph_report.json``, writes
``output/data/manuscript_variables.json``, and writes copies of the manuscript
chapters with every ``{{TOKEN}}`` substituted to ``output/manuscript/``.

All computation lives in ``src/daf_okn/core/manuscript_variables``. This repository
uses the pinned template renderer to consume ``output/manuscript/``. See
``docs/rendering_pipeline.md``.

Exit codes:
    0   variables written and chapters resolved
    1   unexpected error (for example, the graph report is missing and
        ``--allow-draft`` was not given)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate manuscript variables for daf_okn")
    parser.add_argument(
        "--allow-draft",
        action="store_true",
        help=("Allow N/A fallbacks when the graph report is missing (non-pipeline draft mode)"),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=_PROJECT_ROOT,
        help="Root containing manuscript inputs and receiving output",
    )
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()

    from daf_okn.core.manuscript_variables import (
        generate_variables,
        save_variables,
        write_resolved_manuscript,
    )
    from daf_okn.core.project_paths import manuscript_source_dir

    source = manuscript_source_dir(project_root)
    variables = generate_variables(
        source / "config.yaml",
        require_analysis_outputs=not args.allow_draft,
    )
    out_path = project_root / "output" / "data" / "manuscript_variables.json"
    save_variables(variables, out_path)

    unresolved = write_resolved_manuscript(
        source, project_root / "output" / "manuscript", variables
    )
    for name, tokens in unresolved.items():
        if tokens:
            print(f"unresolved tokens in {name}: {', '.join(tokens)}")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
