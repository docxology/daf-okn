#!/usr/bin/env python3
"""Pull OKN registry metadata and run OKN SPARQL queries.

Thin wrapper over ``daf-okn pull`` (see :mod:`daf_okn.cli`); all options are the
same as `python -m daf_okn pull --help`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daf_okn.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["pull", *sys.argv[1:]]))
