#!/usr/bin/env python3
"""CLI for packaging OKN graph contributions (package, checklist, upload-commands).

Thin wrapper over :func:`daf_okn.core.contribute.main`; `daf-okn package` runs the same
packaging step.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daf_okn.core.contribute import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
