"""Static HTML dashboard for daf_okn (re-export barrel)."""

from __future__ import annotations

from .dashboard import OKN_HUB_URL, OKN_REGISTRY_URL, build_dashboard, cli_main
from .dashboard_payload import MAX_TABLE_ROWS, build_payload

__all__ = [
    "MAX_TABLE_ROWS",
    "OKN_HUB_URL",
    "OKN_REGISTRY_URL",
    "build_dashboard",
    "build_payload",
    "cli_main",
]
