#!/usr/bin/env python3
"""Thin CLI: build the static DAF-OKN dashboard from a GraphDocument JSON file.

Usage::

    python scripts/build_dashboard.py --graph data/graph.json \
        [--metrics data/metrics.json] [--out output/web/dashboard.html]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


sys.path.insert(0, str(PROJECT_ROOT / "src"))

from daf_okn.dashboard.dashboard import cli_main  # noqa: E402

if __name__ == "__main__":
    cli_main(default_out=PROJECT_ROOT / "output" / "web" / "dashboard.html")
