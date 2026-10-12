#!/usr/bin/env python3
"""Export the cognitive knowledge base (or any markdown vault) to graph JSON.

Thin wrapper over ``daf-okn export`` (see :mod:`daf_okn.cli`); all options are the
same as `python -m daf_okn export --help`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daf_okn.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["export", *sys.argv[1:]]))
