#!/usr/bin/env python3
"""Pre-flight check for daf-okn pipeline prerequisites.

Verifies, in order:

1. the minimum Python version (>= 3.10),
2. importability of the daf-okn dependency stack (pyyaml, requests, networkx,
   rdflib, matplotlib) and of the core pipeline modules themselves,
3. that ``manuscript/config.yaml`` exists and parses as YAML.

Exits 0 when every check passes, 1 otherwise; diagnostics go to stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
MIN_PYTHON = (3, 10)

REQUIRED_IMPORTS = (
    "yaml",
    "requests",
    "networkx",
    "rdflib",
    "matplotlib",
    "daf_okn.core.graph",
    "daf_okn.core.registry",
    "daf_okn.analysis.pipeline",
)


def run_preflight(project_root: Path) -> tuple[bool, list[str]]:
    """Run every check; return ``(all_ok, diagnostic_lines)``."""
    lines: list[str] = []
    ok = True

    if sys.version_info < MIN_PYTHON:
        lines.append(
            f"[fail] python {'.'.join(map(str, sys.version_info[:2]))} "
            f"< required {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        )
        ok = False
    else:
        lines.append(f"[ok] python {sys.version.split()[0]}")

    for module_name in REQUIRED_IMPORTS:
        try:
            __import__(module_name)
        except Exception as exc:  # noqa: BLE001 — any import failure is a preflight failure
            lines.append(f"[fail] import {module_name}: {exc}")
            ok = False
        else:
            lines.append(f"[ok] import {module_name}")

    config_path = project_root / "manuscript" / "config.yaml"
    if not config_path.is_file():
        lines.append(f"[fail] missing {config_path}")
        ok = False
    else:
        try:
            yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            lines.append(f"[fail] manuscript/config.yaml does not parse: {exc}")
            ok = False
        else:
            lines.append("[ok] manuscript/config.yaml parses")

    return ok, lines


def main() -> int:
    """CLI entry point."""
    ok, lines = run_preflight(PROJECT_ROOT)
    for line in lines:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
