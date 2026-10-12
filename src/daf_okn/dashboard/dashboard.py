"""Static, self-contained HTML dashboard for daf_okn graphs.

``build_dashboard`` writes a dependency-free HTML page embedding summary
statistics, capped node/edge tables, and a data-URI PNG network figure
(generated via :mod:`daf_okn.figures`), with header links to the
documented OKN hosts ``https://okn.us/`` and ``https://registry.okn.us/``.
CLI entry point: ``scripts/build_dashboard.py`` → :func:`cli_main`.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from typing import Any

from ..core.graph import GraphDocument
from ..figures.network_figure import network_figure_bytes
from .dashboard_payload import MAX_TABLE_ROWS, build_payload

__all__ = ["OKN_HUB_URL", "OKN_REGISTRY_URL", "build_dashboard", "cli_main"]

OKN_HUB_URL = "https://okn.us/"
OKN_REGISTRY_URL = "https://registry.okn.us/"

_PAGE_CSS = """\
body{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;margin:0;\
background:#0f172a;color:#e2e8f0}
header{padding:1.2rem 2rem;background:#1e293b;border-bottom:1px solid #334155}
header h1{margin:0 0 .3rem 0;font-size:1.4rem;color:#f8fafc}
header nav a{color:#7dd3fc;margin-right:1rem;text-decoration:none}
header nav a:hover{text-decoration:underline}
main{padding:1.5rem 2rem;max-width:1200px}
section{margin-bottom:2rem}
h2{font-size:1.1rem;color:#93c5fd;border-bottom:1px solid #334155;padding-bottom:.3rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{border:1px solid #334155;padding:.35rem .6rem;text-align:left}
th{background:#1e293b;color:#cbd5e1}
tr:nth-child(even){background:#16223b}
img.network{max-width:100%;height:auto;background:#fff;border-radius:6px}
"""


def build_dashboard(
    doc: GraphDocument,
    metrics: dict[str, Any] | None,
    out_path: Path,
    *,
    title: str = "DAF-OKN Dashboard",
) -> Path:
    """Build the static dashboard HTML for ``doc`` and write it to ``out_path``.

    ``metrics`` (optional precomputed statistics dict) is forwarded to
    :func:`daf_okn.dashboard.dashboard_payload.build_payload`. Returns
    ``out_path``.
    """
    payload = build_payload(doc, metrics)
    png_b64 = base64.b64encode(network_figure_bytes(doc)).decode("ascii")
    page = _render_html(title, payload, png_b64)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def _render_html(title: str, payload: dict[str, Any], png_b64: str) -> str:
    """Render the full self-contained HTML page."""
    summary_rows = [
        ("Graph name", html.escape(str(payload["name"]))),
        ("Node count", str(payload["node_count"])),
        ("Edge count", str(payload["edge_count"])),
        ("Density", f"{float(payload['density']):.4f}"),
        ("Component count", str(payload["component_count"])),
    ]
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>",
        html.escape(title),
        "</title>",
        "<style>",
        _PAGE_CSS,
        "</style>",
        "</head>",
        "<body>",
        "<header>",
        f"<h1>{html.escape(title)}</h1>",
        "<nav>",
        f'<a href="{OKN_HUB_URL}">OKN Hub</a>',
        f'<a href="{OKN_REGISTRY_URL}">OKN Registry</a>',
        "</nav>",
        "</header>",
        "<main>",
        _summary_section(summary_rows),
        _figure_section(png_b64),
        _node_table_section(payload["nodes"]),
        _edge_table_section(payload["edges"]),
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


def _summary_section(rows: list[tuple[str, str]]) -> str:
    """Render the summary statistics table."""
    body = "".join(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows)
    return (
        '<section id="summary"><h2>Summary statistics</h2>'
        f"<table><tbody>{body}</tbody></table></section>"
    )


def _figure_section(png_b64: str) -> str:
    """Render the embedded network figure."""
    return (
        '<section id="network"><h2>Network figure</h2>'
        f'<img class="network" alt="Network figure" src="data:image/png;base64,{png_b64}">'
        "</section>"
    )


def _node_table_section(nodes: list[dict[str, Any]]) -> str:
    """Render the capped node table."""
    header = "<tr><th>id</th><th>title</th><th>node_type</th></tr>"
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(node['id']))}</td>"
        f"<td>{html.escape(str(node['title']))}</td>"
        f"<td>{html.escape(str(node['node_type']))}</td>"
        "</tr>"
        for node in nodes
    )
    return (
        '<section id="nodes"><h2>Nodes'
        f" (first {MAX_TABLE_ROWS})</h2><table>{header}{rows}</table></section>"
    )


def _edge_table_section(edges: list[dict[str, Any]]) -> str:
    """Render the capped edge table."""
    header = "<tr><th>source</th><th>relation</th><th>target</th><th>origin</th></tr>"
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(edge['source']))}</td>"
        f"<td>{html.escape(str(edge['relation']))}</td>"
        f"<td>{html.escape(str(edge['target']))}</td>"
        f"<td>{html.escape(str(edge['origin']))}</td>"
        "</tr>"
        for edge in edges
    )
    return (
        '<section id="edges"><h2>Edges'
        f" (first {MAX_TABLE_ROWS})</h2><table>{header}{rows}</table></section>"
    )


def cli_main(argv: list[str] | None = None, *, default_out: Path | None = None) -> None:
    """Parse CLI arguments and build the dashboard.

    ``default_out`` is supplied by ``scripts/build_dashboard.py`` (project
    root is only knowable there); it defaults to ``output/web/dashboard.html``
    relative to the working directory.
    """
    parser = argparse.ArgumentParser(description="Build the static DAF-OKN dashboard HTML.")
    parser.add_argument("--graph", type=Path, required=True, help="GraphDocument JSON file")
    parser.add_argument(
        "--metrics",
        type=Path,
        default=None,
        help="optional JSON file of precomputed graph metrics",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_out or Path("output/web/dashboard.html"),
        help="output HTML path",
    )
    args = parser.parse_args(argv)
    doc = GraphDocument.load_json(args.graph)
    metrics: dict[str, Any] | None = None
    if args.metrics is not None:
        loaded = json.loads(args.metrics.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            parser.error("--metrics file must contain a JSON object")
        metrics = loaded
    written = build_dashboard(doc, metrics, args.out)
    print(written)
