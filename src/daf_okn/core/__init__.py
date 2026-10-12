"""Pure-logic core for the OKN package.

This cluster keeps the graph model and shared helpers:

* :mod:`daf_okn.core.graph` — the pinned graph document model
  (:class:`NodeRecord`, :class:`EdgeRecord`, :class:`GraphDocument`,
  :func:`bindings_to_graph`).
* :mod:`daf_okn.core.invariants` — structural graph invariants
  (:func:`validate_graph`, :func:`graph_stats`).
* :mod:`daf_okn.core.project_paths` — project-root and output-directory
  resolution shared by analysis, figures, dashboard.
* :mod:`daf_okn.core.manuscript_variables` — flat ``{{TOKEN}}`` substitution
  map hydrated from ``manuscript/config.yaml`` and the graph report.
* :mod:`daf_okn.core.documentation` — introspected API reference builder.
"""

from .documentation import (
    build_api_reference_markdown,
)
from .graph import (
    EdgeRecord,
    GraphDocument,
    NodeRecord,
    bindings_to_graph,
)
from .invariants import (
    graph_stats,
    validate_graph,
)
from .manuscript_variables import (
    generate_variables,
    save_variables,
)
from .project_paths import (
    project_output_dirs,
    project_root_context,
    resolve_project_root,
)

__all__ = [
    "EdgeRecord",
    "GraphDocument",
    "NodeRecord",
    "bindings_to_graph",
    "build_api_reference_markdown",
    "generate_variables",
    "graph_stats",
    "project_output_dirs",
    "project_root_context",
    "resolve_project_root",
    "save_variables",
    "validate_graph",
]
