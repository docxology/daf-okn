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
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, overload
from urllib.parse import urlsplit

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
        relation: Relation label, or the full predicate IRI for SPARQL data.
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

    @overload
    def to_networkx(self, directed: Literal[True] = True) -> nx.DiGraph: ...

    @overload
    def to_networkx(self, directed: Literal[False]) -> nx.Graph: ...

    @overload
    def to_networkx(self, directed: bool) -> nx.DiGraph | nx.Graph: ...

    def to_networkx(self, directed: bool = True) -> nx.DiGraph | nx.Graph:
        """Project the document onto a networkx graph.

        Node attributes are ``{"title", "node_type"}`` merged with the record's
        ``attributes`` (canonical fields win on key collision). Edge attributes
        are ``{"relation", "origin"}``. Dangling edge endpoints are materialized
        as bare nodes by networkx; use :meth:`validate` to detect them.
        Parallel records collapse to one edge, whose attributes come from the
        last record. Use :meth:`to_multidigraph` to preserve every record.
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

    def to_multidigraph(self) -> nx.MultiDiGraph:
        """Preserve every directed edge record, including parallel predicates.

        Integer edge keys are the original record positions, so duplicates and
        differing provenance remain inspectable. Node attributes follow the
        same canonical-field precedence as :meth:`to_networkx`.
        """
        graph: nx.MultiDiGraph = nx.MultiDiGraph()
        for node in self.nodes:
            graph.add_node(
                node.id, **{**node.attributes, "title": node.title, "node_type": node.node_type}
            )
        for key, edge in enumerate(self.edges):
            graph.add_edge(
                edge.source, edge.target, key=key, relation=edge.relation, origin=edge.origin
            )
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
    if (
        len(variables) < 3
        or any(not isinstance(variable, str) or not variable for variable in variables)
        or len(set(variables)) != len(variables)
    ):
        raise ValueError(
            "SPARQL result must select at least three variables with distinct nonempty names "
            f"(subject, predicate, object); got {variables!r}"
        )

    def _pick(aliases: frozenset[str]) -> str | None:
        lowered = {variable.lower(): variable for variable in variables}
        for alias in sorted(aliases):
            if alias in lowered:
                return lowered[alias]
        return None

    roles = [_pick(aliases) for aliases in (_SUBJECT_ALIASES, _PREDICATE_ALIASES, _OBJECT_ALIASES)]
    remaining = iter(variable for variable in variables if variable not in roles)
    resolved = [role if role is not None else next(remaining) for role in roles]
    return resolved[0], resolved[1], resolved[2]


def _term_iri(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r'[A-Za-z][A-Za-z0-9+.-]*:[^\s<>"{}|^`\\\x00-\x1f]+', value
    ):
        raise ValueError(f"SPARQL term requires an absolute IRI: {value!r}")
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"}:
            if not parsed.hostname:
                raise ValueError("invalid HTTP authority")
            _ = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid SPARQL term IRI: {value!r}") from exc
    return value


def _term_node(term: Any) -> NodeRecord:
    """Build a node record from one SPARQL term binding."""
    if not isinstance(term, dict) or not isinstance(term.get("value"), str):
        raise ValueError(f"invalid SPARQL term binding: {term!r}")
    value = term["value"]
    term_type = term.get("type")
    if term_type not in ("uri", "bnode", "literal", "typed-literal"):
        raise ValueError(f"unsupported SPARQL term type: {term_type!r}")
    attributes: dict[str, Any] = {}
    if term_type in {"literal", "typed-literal"}:
        title = value
        node_id = json.dumps(value, ensure_ascii=False)
        if "datatype" in term:
            datatype = _term_iri(term["datatype"])
            attributes["datatype"] = datatype
            if datatype != "http://www.w3.org/2001/XMLSchema#string":
                node_id += "^^<" + datatype + ">"
        if "xml:lang" in term:
            language = term["xml:lang"]
            if (
                "datatype" in term
                or not isinstance(language, str)
                or not re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z0-9]+)*", language)
            ):
                raise ValueError(f"invalid SPARQL language literal: {term!r}")
            attributes["xml:lang"] = language.lower()
            node_id += "@" + language.lower()
        if term_type == "typed-literal" and "datatype" not in term:
            raise ValueError("typed-literal requires a datatype IRI")
        node_type = "literal"
    elif term_type == "bnode":
        if not value or any(character.isspace() for character in value):
            raise ValueError(f"invalid SPARQL blank node label: {value!r}")
        node_id, title, node_type = "_:" + value, value, "bnode"
    else:
        node_id, title, node_type = _term_iri(value), _local_part(value), "uri"
    if term_type not in {"literal", "typed-literal"} and ("datatype" in term or "xml:lang" in term):
        raise ValueError(f"non-literal SPARQL term has literal metadata: {term!r}")
    return NodeRecord(
        id=node_id,
        title=title,
        node_type=node_type,
        attributes=attributes,
    )


def bindings_to_graph(sparql_json: dict[str, Any], graph_name: str) -> GraphDocument:
    """Convert a SPARQL JSON result into a :class:`GraphDocument`.

    Expects the standard ``application/sparql-results+json`` shape used by the
    OKN SPARQL endpoints: ``head.vars`` plus ``results.bindings`` where every
    binding value carries ``type`` (``uri`` | ``literal`` | ``bnode``) and
    ``value``. URI subjects and URI objects become nodes (``node_type
    "uri"``); literal objects become nodes with ``node_type "literal"``; the
    predicate's full IRI becomes the edge relation. Literal ids encode lexical
    form, datatype and normalized language; blank node ids use ``_:`` and stay
    scoped to this result document. Repeated
    subjects/objects across bindings are merged (first record wins) and exact
    duplicate edges are collapsed. Document validation separately reports
    structural profile issues such as self-links.

    Args:
        sparql_json: Parsed SPARQL JSON result document.
        graph_name: Name for the resulting :class:`GraphDocument`.

    Returns:
        GraphDocument with one node per distinct term, one edge per distinct
        (subject, predicate, object) triple, and provenance metadata.

    Raises:
        ValueError: If the SELECT result structure or a bound RDF term is invalid.
    """
    try:
        variables = sparql_json["head"]["vars"]
        bindings = sparql_json["results"]["bindings"]
    except (KeyError, TypeError) as exc:
        raise ValueError("SPARQL SELECT result requires head.vars and results.bindings") from exc
    if not isinstance(variables, list) or not isinstance(bindings, list):
        raise ValueError("SPARQL head.vars and results.bindings must be lists")
    subject_var, predicate_var, object_var = _resolve_sparql_roles(variables)

    nodes: dict[str, NodeRecord] = {}
    edges: dict[tuple[str, str, str], EdgeRecord] = {}
    skipped = 0
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ValueError(f"SPARQL result row must be an object: {binding!r}")
        subject = binding.get(subject_var)
        predicate = binding.get(predicate_var)
        obj = binding.get(object_var)
        if any(role not in binding for role in (subject_var, predicate_var, object_var)):
            skipped += 1
            continue
        if not isinstance(subject, dict) or subject.get("type") not in ("uri", "bnode"):
            raise ValueError(f"SPARQL triple subject must be an IRI or blank node: {subject!r}")
        if not isinstance(predicate, dict) or predicate.get("type") != "uri":
            raise ValueError(f"SPARQL triple predicate must be an IRI: {predicate!r}")
        source_node = _term_node(subject)
        target_node = _term_node(obj)
        nodes.setdefault(source_node.id, source_node)
        nodes.setdefault(target_node.id, target_node)
        relation = _term_iri(predicate.get("value"))
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
