"""Graph document model for OKN knowledge-graph data.

This module is the single source of truth for the in-memory graph model used
across the package (analysis, figures, dashboard, adapters):

* :class:`NodeRecord` — one node (id, title, type, free-form attributes).
* :class:`EdgeRecord` — one directed edge with a relation label.
* :class:`GraphDocument` — a named collection of nodes and edges plus
  metadata, with conversion helpers (:meth:`GraphDocument.to_networkx`,
  :meth:`GraphDocument.to_dict`, :meth:`GraphDocument.from_dict`,
  :meth:`GraphDocument.save_json`, :meth:`GraphDocument.load_json`).
* :func:`bindings_to_graph` — convert a SPARQL JSON result (the
  ``application/sparql-results+json`` shape returned by the OKN SPARQL
  endpoints: ``head.vars`` / ``results.bindings``) into a
  :class:`GraphDocument`.

The module is import-time side-effect free: importing it performs no I/O and
no network calls. Serialization helpers (:meth:`GraphDocument.save_json`,
:meth:`GraphDocument.load_json`) are the only I/O entry points and they run
only when called.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

__all__ = ["EdgeRecord", "GraphDocument", "NodeRecord", "bindings_to_graph"]


@dataclass
class NodeRecord:
    """One node in a graph document.

    Attributes:
        id: Stable unique identifier (typically a full IRI for OKN data).
        title: Human-readable label.
        node_type: Coarse type tag (``"concept"``, ``"uri"``, ``"literal"``, ...).
        attributes: Free-form extra attributes merged into networkx node data.
    """

    id: str
    title: str
    node_type: str = "concept"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeRecord:
    """One directed edge in a graph document.

    Attributes:
        source: Id of the source node (must exist in the document's nodes).
        target: Id of the target node (must exist in the document's nodes).
        relation: Relation label (local part of a predicate IRI for SPARQL data).
        origin: Provenance tag, e.g. ``"explicit"`` or ``"inferred"``.
    """

    source: str
    target: str
    relation: str = "related"
    origin: str = "explicit"


@dataclass
class GraphDocument:
    """A named, serializable graph of :class:`NodeRecord` / :class:`EdgeRecord`.

    Construction is permissive so that invalid documents can be built and then
    diagnosed with :meth:`validate` (which delegates to
    :func:`daf_okn.core.invariants.validate_graph`).
    """

    name: str
    nodes: list[NodeRecord] = field(default_factory=list)
    edges: list[EdgeRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation (constructor-adjacent helper)
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return human-readable structural problems with this document.

        Delegates to :func:`daf_okn.core.invariants.validate_graph`; the import
        is local to avoid a module-level cycle (invariants imports the record
        types for typing).
        """
        from .invariants import validate_graph

        return validate_graph(self)

    # ------------------------------------------------------------------
    # Conversions
    # ------------------------------------------------------------------

    def to_networkx(self, directed: bool = True) -> nx.DiGraph | nx.Graph:
        """Project the document onto a networkx graph.

        Node attributes are ``{"title", "node_type"}`` merged with the record's
        ``attributes`` (canonical fields win on key collision). Edge attributes
        are ``{"relation", "origin"}``. Dangling edge endpoints are materialized
        as bare nodes by networkx; use :meth:`validate` to detect them.
        """
        graph: nx.DiGraph | nx.Graph = nx.DiGraph() if directed else nx.Graph()
        for node in self.nodes:
            graph.add_node(
                node.id,
                **{**node.attributes, "title": node.title, "node_type": node.node_type},
            )
        for edge in self.edges:
            graph.add_edge(edge.source, edge.target, relation=edge.relation, origin=edge.origin)
        return graph

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-JSON-able dict representation of the document."""
        return {
            "name": self.name,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "metadata": json.loads(json.dumps(self.metadata)),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphDocument:
        """Build a document from :meth:`to_dict` output (or a compatible dict).

        Missing optional fields fall back to the record defaults
        (``node_type="concept"``, ``relation="related"``, ``origin="explicit"``,
        empty ``attributes`` / ``metadata``).
        """
        if not isinstance(data, dict):
            raise TypeError(f"GraphDocument payload must be a dict, got {type(data).__name__}")
        nodes = [
            NodeRecord(
                id=str(raw["id"]),
                title=str(raw.get("title", raw["id"])),
                node_type=str(raw.get("node_type", "concept")),
                attributes=dict(raw.get("attributes", {})),
            )
            for raw in data.get("nodes", [])
        ]
        edges = [
            EdgeRecord(
                source=str(raw["source"]),
                target=str(raw["target"]),
                relation=str(raw.get("relation", "related")),
                origin=str(raw.get("origin", "explicit")),
            )
            for raw in data.get("edges", [])
        ]
        return cls(
            name=str(data.get("name", "")),
            nodes=nodes,
            edges=edges,
            metadata=dict(data.get("metadata", {})),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_json(self, path: str | Path) -> Path:
        """Write the document to ``path`` as pretty-printed JSON; return the path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def load_json(cls, path: str | Path) -> GraphDocument:
        """Load a document previously written by :meth:`save_json`."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ----------------------------------------------------------------------
# SPARQL JSON results → GraphDocument
# ----------------------------------------------------------------------

_SUBJECT_ALIASES = frozenset({"s", "subject", "src", "source", "sub"})
_PREDICATE_ALIASES = frozenset({"p", "predicate", "pred", "property", "rel"})
_OBJECT_ALIASES = frozenset({"o", "object", "obj", "target"})


def _local_part(iri: str) -> str:
    """Return the local part of an IRI (text after the last ``#`` or ``/``)."""
    cut = max(iri.rfind("#"), iri.rfind("/"))
    local = iri[cut + 1 :] if cut != -1 else iri
    return local or iri


def _resolve_sparql_roles(variables: Iterable[str]) -> tuple[str, str, str]:
    """Pick (subject, predicate, object) variable names from ``head.vars``.

    Prefers conventional names (``s``/``p``/``o`` and friends); otherwise falls
    back to positional order (first three variables).
    """
    variables = list(variables)
    if len(variables) < 3:
        raise ValueError(
            "SPARQL result must select at least three variables "
            f"(subject, predicate, object); got {variables!r}"
        )

    def _pick(aliases: frozenset[str]) -> str | None:
        lowered = {variable.lower(): variable for variable in variables}
        for alias in sorted(aliases):
            if alias in lowered:
                return lowered[alias]
        return None

    subject = _pick(_SUBJECT_ALIASES) or variables[0]
    predicate = _pick(_PREDICATE_ALIASES) or variables[1]
    obj = _pick(_OBJECT_ALIASES) or variables[2]
    return subject, predicate, obj


def _term_node_type(term_type: str) -> str:
    """Map a SPARQL term type onto a node type.

    URI and blank-node terms become ``"uri"`` nodes (blank-node ids are kept
    verbatim); only literals become ``"literal"`` nodes.
    """
    return "literal" if term_type == "literal" else "uri"


def _term_node(term: dict[str, Any]) -> NodeRecord:
    """Build a node record from one SPARQL term binding."""
    value = str(term["value"])
    term_type = str(term.get("type", "uri"))
    attributes: dict[str, Any] = {}
    if term_type == "literal":
        title = value
        if "datatype" in term:
            attributes["datatype"] = term["datatype"]
        if "xml:lang" in term:
            attributes["xml:lang"] = term["xml:lang"]
    else:
        title = _local_part(value)
    return NodeRecord(
        id=value,
        title=title,
        node_type=_term_node_type(term_type),
        attributes=attributes,
    )


def bindings_to_graph(sparql_json: dict[str, Any], graph_name: str) -> GraphDocument:
    """Convert a SPARQL JSON result into a :class:`GraphDocument`.

    Expects the standard ``application/sparql-results+json`` shape used by the
    OKN SPARQL endpoints: ``head.vars`` plus ``results.bindings`` where every
    binding value carries ``type`` (``uri`` | ``literal`` | ``bnode``) and
    ``value``. URI subjects and URI objects become nodes (``node_type
    "uri"``); literal objects become nodes with ``node_type "literal"``; the
    predicate becomes the edge relation (local part of its IRI). Repeated
    subjects/objects across bindings are merged (first record wins) and exact
    duplicate edges are collapsed, so valid results yield a valid document.

    Args:
        sparql_json: Parsed SPARQL JSON result document.
        graph_name: Name for the resulting :class:`GraphDocument`.

    Returns:
        GraphDocument with one node per distinct term, one edge per distinct
        (subject, predicate, object) triple, and provenance metadata.

    Raises:
        ValueError: If fewer than three variables are selected.
    """
    variables = list(sparql_json.get("head", {}).get("vars", []))
    bindings = list(sparql_json.get("results", {}).get("bindings", []))
    subject_var, predicate_var, object_var = _resolve_sparql_roles(variables)

    nodes: dict[str, NodeRecord] = {}
    edges: dict[tuple[str, str, str], EdgeRecord] = {}
    skipped = 0
    for binding in bindings:
        subject = binding.get(subject_var)
        predicate = binding.get(predicate_var)
        obj = binding.get(object_var)
        if not (subject and predicate and obj):
            skipped += 1
            continue
        source_node = _term_node(subject)
        target_node = _term_node(obj)
        nodes.setdefault(source_node.id, source_node)
        nodes.setdefault(target_node.id, target_node)
        relation = _local_part(str(predicate["value"]))
        edges.setdefault(
            (source_node.id, target_node.id, relation),
            EdgeRecord(
                source=source_node.id,
                target=target_node.id,
                relation=relation,
                origin="explicit",
            ),
        )

    return GraphDocument(
        name=graph_name,
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        metadata={
            "source": "sparql",
            "head_vars": variables,
            "binding_count": len(bindings),
            "skipped_bindings": skipped,
        },
    )
