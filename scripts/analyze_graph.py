#!/usr/bin/env python3
"""Compute structural metrics for a graph document and write a JSON report.

Thin wrapper over ``daf-okn analyze`` (see :mod:`daf_okn.cli`); all options are the
same as `python -m daf_okn analyze --help`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daf_okn.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["analyze", *sys.argv[1:]]))
