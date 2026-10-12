#!/usr/bin/env python3
"""API reference generation — introspect the real daf_okn modules.

Builds ``output/docs/api_reference.md`` by importing each documented
``daf_okn`` module (graph core, registry, invariants, cognitive adapter,
contribute, graph metrics, analysis pipeline, figures, dashboard) and
rendering live ``inspect`` signatures. There is no static template and no
infrastructure dependency: the script is standalone-safe.

Exit codes:
    0   reference written
    1   unexpected error
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    path_text = str(_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from daf_okn.core.documentation import build_api_reference_markdown  # noqa: E402

logger = logging.getLogger("daf_okn.scripts.generate_api_docs")


def run_api_doc_generation(
    project_root: Path,
    *,
    modules: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Write the introspected API reference under ``<project_root>/output/docs``.

    Args:
        project_root: Project root; the reference is written to
            ``<project_root>/output/docs/api_reference.md`` (created if
            missing).
        modules: Optional explicit module list forwarded to
            :func:`daf_okn.core.documentation.build_api_reference_markdown`;
            defaults to the pinned daf-okn module set.

    Returns:
        Mapping with the ``api_reference`` path written.
    """
    output_dir = Path(project_root) / "output" / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    api_ref_path = output_dir / "api_reference.md"
    api_ref_path.write_text(build_api_reference_markdown(modules=modules), encoding="utf-8")
    logger.info("API reference written to %s", api_ref_path)
    return {"api_reference": str(api_ref_path)}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    parser = argparse.ArgumentParser(description="Generate the daf_okn API reference markdown")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Root receiving output/docs (defaults to this checkout)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        docs_files = run_api_doc_generation(args.project_root.resolve())
    except (OSError, ImportError) as exc:
        logger.error("API documentation generation failed: %s", exc)
        return 1
    for file_path in docs_files.values():
        print(file_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
