"""RDF serialization of :class:`~daf_okn.core.graph.GraphDocument` using standard vocabularies.

The OKN registry's guidance (FRINK / RENCI) is to reuse existing vocabularies and to
mint entity IRIs under ``https://purl.org/okn/frink/kg/<shortname>/``, with the named
graph ``https://purl.org/okn/frink/kg/<shortname>``. This module follows that, and
produces the same shapes as the reference exporter in the Active Inference Institute
``cognitive`` repository (``code/scripts/export_rdf.py``):

* every non-literal node is a ``schema:CreativeWork``; nodes whose type is
  ``overview`` or ``index`` are also ``schema:CollectionPage``, redirect nodes are nothing
  more, every other node is a ``skos:Concept`` in one ``skos:ConceptScheme`` with a
  ``skos:prefLabel``;
* node fields map to ``dcterms:title``, ``dcterms:description``, ``skos:altLabel``,
  ``dcterms:created``, ``dcterms:modified``, ``schema:keywords``, ``schema:author``,
  ``schema:datePublished``, ``schema:sameAs`` (DOI) and ``skos:exactMatch`` (Wikidata);
* edge relations map to ``skos:related``, ``dcterms:isPartOf``, ``dcterms:hasPart``,
  ``dcterms:references`` (body wiki links) and ``dcterms:isReplacedBy`` (redirects);
  any other relation name becomes a term under ``<base>relation/`` that is declared an
  ``rdfs:subPropertyOf skos:semanticRelation`` with an ``rdfs:label``;
* all other node attributes stay available as ``<base>vocab/<key>`` properties;
* a ``dcat:Dataset`` / ``void:Dataset`` description and a small PROV-O activity describe
  the graph itself.

Output is deterministic: N-Triples and N-Quads are written with sorted lines, no
timestamps are emitted, and the dataset's ``dcterms:modified`` is the latest node
``updated`` date.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, PROV, RDF, RDFS, SKOS, VOID, XSD

from .graph import EdgeRecord, GraphDocument, NodeRecord

__all__ = [
    "KG_BASE",
    "SUPPORTED_FORMATS",
    "build_rdf_graph",
    "default_namespace_base",
    "graph_iri",
    "graph_to_rdf",
    "relation_predicate",
    "relation_slug",
    "shortname_slug",
]

KG_BASE = "https://purl.org/okn/frink/kg/"
TOOL_URL = "https://github.com/docxology/daf-okn"

SCHEMA = Namespace("https://schema.org/")

SUPPORTED_FORMATS = {
    "nt": "nt",
    "nq": "nquads",
    "ttl": "turtle",
    "jsonld": "json-ld",
    "trig": "trig",
}
_QUAD_FORMATS = {"nq", "trig"}

_PREFIXES = {
    "skos": SKOS,
    "dcterms": DCTERMS,
    "schema": SCHEMA,
    "prov": PROV,
    "dcat": DCAT,
    "void": VOID,
}

# Relation names a standard vocabulary already covers (same table as the reference
# exporter, plus the adapter's own spellings). Anything else becomes <base>relation/<slug>.
_STANDARD_RELATIONS: dict[str, URIRef] = {
    "relates": SKOS.related,
    "related": SKOS.related,
    "relates_to": SKOS.related,
    "related_to": SKOS.related,
    "part_of": DCTERMS.isPartOf,
    "component_of": DCTERMS.isPartOf,
    "has_parent": DCTERMS.isPartOf,
    "organizes": DCTERMS.hasPart,
    "redirects_to": DCTERMS.isReplacedBy,
}

# Node attributes that have a standard-vocabulary home; everything else goes to vocab/.
_MAPPED_ATTRIBUTES = frozenset(
    {
        "description",
        "aliases",
        "created",
        "updated",
        "modified",
        "tags",
        "authors",
        "year",
        "doi",
        "wikidata",
    }
)
_NAVIGATION_TYPES = frozenset({"overview", "index"})

_ABSOLUTE_IRI = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*://|urn:)")
_WIKIDATA_ID = re.compile(r"Q[1-9][0-9]*")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_IRI_SAFE_CHARS = "/._-~"


def shortname_slug(name: str) -> str:
    """Return ``name`` as a registry-style shortname (lowercase letters, digits, hyphens)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "graph"


def default_namespace_base(name: str) -> str:
    """Return the default entity-IRI base ``https://purl.org/okn/frink/kg/<shortname>/``."""
    return f"{KG_BASE}{shortname_slug(name)}/"


def graph_iri(namespace_base: str) -> URIRef:
    """Return the named-graph IRI for an entity base (the base without its trailing slash)."""
    return URIRef(namespace_base.rstrip("/"))


def relation_slug(name: str) -> str:
    """Return a relation name as a lowercase, underscore-separated IRI path segment."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "relates"


def _quote(value: str) -> str:
    """Percent-encode everything an IRI path segment cannot carry; keep readable ids."""
    return quote(value, safe=_IRI_SAFE_CHARS)


def _ensure_base(namespace_base: str) -> str:
    return namespace_base if namespace_base.endswith("/") else namespace_base + "/"


def relation_predicate(relation: str, namespace_base: str) -> URIRef:
    """Return the predicate IRI for ``relation``.

    ``prefix:name`` forms with a known prefix (``skos``, ``dcterms``, ``schema``, ...)
    and absolute IRIs are used as given; well-known names map to SKOS/DCTERMS; the rest
    become ``<base>relation/<slug>``.
    """
    text = relation.strip()
    prefix, sep, local = text.partition(":")
    if sep and prefix in _PREFIXES and local and not local.startswith("//"):
        return URIRef(str(_PREFIXES[prefix]) + local)
    if _ABSOLUTE_IRI.match(text):
        return URIRef(text)
    slug = relation_slug(text)
    standard = _STANDARD_RELATIONS.get(slug)
    if standard is not None:
        return standard
    return URIRef(f"{_ensure_base(namespace_base)}relation/{slug}")


def _is_external(node_id: str) -> bool:
    return bool(_ABSOLUTE_IRI.match(node_id))


def _node_iri(namespace_base: str, node_id: str) -> URIRef:
    if _is_external(node_id):
        return URIRef(node_id)
    return URIRef(f"{_ensure_base(namespace_base)}page/{_quote(node_id)}")


def _text(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value).strip()


def _scalars(value: Any) -> list[Any]:
    """Flatten a JSON-like attribute to its scalar leaves (dicts are skipped)."""
    if value is None or isinstance(value, dict):
        return []
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in _scalars(item)]
    if isinstance(value, (str, int, float, bool)):
        return [value]
    return []


def _typed_date(value: Any) -> Literal:
    text = _text(value)
    if _DATE.fullmatch(text):
        return Literal(text, datatype=XSD.date)
    return Literal(text)


def _lit(text: str, language: str | None) -> Literal:
    return Literal(text, lang=language) if language else Literal(text)


def _describe_node(
    graph: Graph,
    namespace_base: str,
    node: NodeRecord,
    *,
    language: str | None,
    used_terms: set[str],
    modified: list[str],
) -> None:
    base = _ensure_base(namespace_base)
    subject = _node_iri(base, node.id)
    external = _is_external(node.id)
    title = node.title or node.id
    attributes = {key: value for key, value in node.attributes.items() if isinstance(key, str)}

    if external:
        # Someone else's IRI: label it, but do not assert page/concept membership for it.
        graph.add((subject, RDFS.label, _lit(title, language)))
    else:
        graph.add((subject, RDF.type, SCHEMA.CreativeWork))
        if node.node_type in _NAVIGATION_TYPES:
            graph.add((subject, RDF.type, SCHEMA.CollectionPage))
        elif node.node_type != "redirect":
            graph.add((subject, RDF.type, SKOS.Concept))
            graph.add((subject, SKOS.inScheme, URIRef(base + "scheme")))
            graph.add((subject, SKOS.prefLabel, _lit(title, language)))
        graph.add((subject, DCTERMS.title, _lit(title, language)))
        graph.add((subject, URIRef(base + "vocab/pageType"), Literal(node.node_type)))
        used_terms.add("pageType")

    description = _text(attributes.get("description", ""))
    if description:
        graph.add((subject, DCTERMS.description, _lit(description, language)))
    for alias in _scalars(attributes.get("aliases")):
        if _text(alias):
            graph.add((subject, SKOS.altLabel, _lit(_text(alias), language)))
    if attributes.get("created") is not None:
        graph.add((subject, DCTERMS.created, _typed_date(attributes["created"])))
    updated = attributes.get("updated") or attributes.get("modified")
    if updated is not None:
        graph.add((subject, DCTERMS.modified, _typed_date(updated)))
        modified.append(_text(updated))
    for tag in _scalars(attributes.get("tags")):
        if _text(tag):
            graph.add((subject, SCHEMA.keywords, Literal(_text(tag))))
    for author in _scalars(attributes.get("authors")):
        if _text(author):
            graph.add((subject, SCHEMA.author, Literal(_text(author))))
    if attributes.get("year") is not None:
        graph.add(
            (subject, SCHEMA.datePublished, Literal(_text(attributes["year"]), datatype=XSD.gYear))
        )
    doi = _text(attributes.get("doi", ""))
    if doi:
        graph.add(
            (subject, SCHEMA.sameAs, URIRef("https://doi.org/" + quote(doi, safe="/:;()-._~")))
        )

    qid = _text(attributes.get("wikidata", ""))
    wikidata_ok = bool(_WIKIDATA_ID.fullmatch(qid))
    if wikidata_ok:
        graph.add((subject, SKOS.exactMatch, URIRef("http://www.wikidata.org/entity/" + qid)))

    for key in sorted(attributes):
        if key in _MAPPED_ATTRIBUTES and not (key == "wikidata" and qid and not wikidata_ok):
            continue
        key_slug = _quote(key)
        for leaf in _scalars(attributes[key]):
            graph.add((subject, URIRef(f"{base}vocab/{key_slug}"), Literal(leaf)))
            used_terms.add(key_slug)


def _edge_target(edge: EdgeRecord, base: str, literals: dict[str, NodeRecord]) -> URIRef | Literal:
    literal_node = literals.get(edge.target)
    if literal_node is None:
        return _node_iri(base, edge.target)
    attrs = literal_node.attributes
    if attrs.get("xml:lang"):
        return Literal(literal_node.id, lang=str(attrs["xml:lang"]))
    if attrs.get("datatype"):
        return Literal(literal_node.id, datatype=URIRef(str(attrs["datatype"])))
    return Literal(literal_node.id)


def _declare_vocabulary(
    graph: Graph, base: str, relations: set[str], terms: set[str], language: str | None
) -> None:
    for slug in sorted(relations):
        term = URIRef(f"{base}relation/{slug}")
        graph.add((term, RDF.type, RDF.Property))
        graph.add((term, RDFS.subPropertyOf, SKOS.semanticRelation))
        graph.add((term, RDFS.label, _lit(slug.replace("_", " "), language)))
        graph.add(
            (
                term,
                RDFS.comment,
                _lit(
                    f"Relation '{slug}' as written in the source graph; read it from the "
                    "subject node to the object node.",
                    language,
                ),
            )
        )
    for name in sorted(terms):
        term = URIRef(f"{base}vocab/{name}")
        graph.add((term, RDF.type, RDF.Property))
        graph.add((term, RDFS.label, _lit(name, language)))
        graph.add(
            (
                term,
                RDFS.comment,
                _lit(f"Source attribute '{name}', carried over verbatim.", language),
            )
        )


def _describe_dataset(
    graph: Graph,
    base: str,
    doc: GraphDocument,
    entry: dict[str, Any],
    modified: list[str],
    domains: set[str],
    language: str | None,
) -> None:
    dataset = URIRef(base + "dataset")
    scheme = URIRef(base + "scheme")
    activity = URIRef(base + "activity/export")
    title = str(entry.get("title") or doc.name or "graph")
    graph.add((dataset, RDF.type, DCAT.Dataset))
    graph.add((dataset, RDF.type, VOID.Dataset))
    graph.add((dataset, DCTERMS.title, _lit(title, language)))
    if entry.get("description"):
        graph.add((dataset, DCTERMS.description, _lit(str(entry["description"]), language)))
    license_value = str(entry.get("license") or "")
    if license_value:
        license_term: URIRef | Literal = (
            URIRef(license_value) if _ABSOLUTE_IRI.match(license_value) else Literal(license_value)
        )
        graph.add((dataset, DCTERMS.license, license_term))
        graph.add((scheme, DCTERMS.license, license_term))
    for vocabulary in (SKOS, DCTERMS, SCHEMA, PROV):
        graph.add((dataset, VOID.vocabulary, URIRef(str(vocabulary))))
    if entry.get("homepage"):
        graph.add((dataset, DCAT.landingPage, URIRef(str(entry["homepage"]))))
    source = str(entry.get("source") or "")
    if source:
        graph.add((dataset, DCTERMS.source, URIRef(source)))
        graph.add((dataset, PROV.wasDerivedFrom, URIRef(source)))
        graph.add((activity, PROV.used, URIRef(source)))
    dates = sorted(value for value in modified if _DATE.fullmatch(value))
    if dates:
        graph.add((dataset, DCTERMS.modified, Literal(dates[-1], datatype=XSD.date)))
    graph.add((dataset, PROV.wasGeneratedBy, activity))
    graph.add((activity, RDF.type, PROV.Activity))
    graph.add((activity, PROV.wasAssociatedWith, URIRef(TOOL_URL)))
    graph.add((URIRef(TOOL_URL), RDF.type, PROV.SoftwareAgent))
    graph.add((URIRef(TOOL_URL), RDF.type, SCHEMA.SoftwareSourceCode))

    graph.add((scheme, RDF.type, SKOS.ConceptScheme))
    graph.add((scheme, DCTERMS.title, _lit(f"{title} concepts", language)))
    graph.add((scheme, VOID.inDataset, dataset))

    for name in sorted(domains):
        domain = URIRef(f"{base}domain/{_quote(name)}")
        graph.add((domain, RDF.type, SKOS.Collection))
        graph.add((domain, SKOS.prefLabel, _lit(name.replace("_", " ").title(), language)))
        graph.add((domain, VOID.inDataset, dataset))


def build_rdf_graph(
    doc: GraphDocument,
    *,
    namespace_base: str | None = None,
    entry: dict[str, Any] | None = None,
    language: str | None = None,
) -> Graph:
    """Build the :class:`rdflib.Graph` for ``doc``.

    Args:
        doc: The graph document.
        namespace_base: Entity-IRI base; defaults to
            ``https://purl.org/okn/frink/kg/<shortname-of-doc.name>/``.
        entry: Optional registry-entry inputs (``title``, ``description``, ``license``,
            ``homepage``, ``source``, ``language``) used for the dataset description.
        language: Language tag for human-readable literals (default: ``entry["language"]``
            if present, else untagged).
    """
    entry = dict(entry or {})
    base = _ensure_base(namespace_base or default_namespace_base(doc.name))
    language = language or (str(entry["language"]) if entry.get("language") else None)

    graph = Graph()
    for prefix, namespace in _PREFIXES.items():
        graph.bind(prefix, namespace)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)
    graph.bind("kg", Namespace(base))
    graph.bind("rel", Namespace(base + "relation/"))
    graph.bind("vocab", Namespace(base + "vocab/"))
    graph.bind("page", Namespace(base + "page/"))
    graph.bind("domain", Namespace(base + "domain/"))

    literals = {node.id: node for node in doc.nodes if node.node_type == "literal"}
    used_terms: set[str] = set()
    used_relations: set[str] = set()
    modified: list[str] = []
    domains: set[str] = set()

    for node in doc.nodes:
        if node.id in literals:
            continue
        _describe_node(
            graph, base, node, language=language, used_terms=used_terms, modified=modified
        )
        if not _is_external(node.id) and "/" in node.id:
            top = node.id.split("/", 1)[0]
            domains.add(top)
            graph.add(
                (URIRef(f"{base}domain/{_quote(top)}"), SKOS.member, _node_iri(base, node.id))
            )

    for edge in doc.edges:
        if edge.source in literals:
            continue  # a literal cannot be a subject
        if edge.origin == "wikilink":
            predicate = DCTERMS.references
        else:
            predicate = relation_predicate(edge.relation, base)
        if str(predicate).startswith(base + "relation/"):
            used_relations.add(str(predicate)[len(base + "relation/") :])
        graph.add((_node_iri(base, edge.source), predicate, _edge_target(edge, base, literals)))

    _declare_vocabulary(graph, base, used_relations, used_terms, language)
    _describe_dataset(graph, base, doc, entry, modified, domains, language)
    return graph


# --------------------------------------------------------------------------- writing
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _nt_term(term: Any) -> str:
    """Return ``term`` in N-Triples syntax."""
    if isinstance(term, URIRef):
        return f"<{term}>"
    if isinstance(term, BNode):
        return f"_:{term}"
    out = []
    for char in str(term):
        if char in _ESCAPES:
            out.append(_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    text = '"' + "".join(out) + '"'
    if term.language:
        return f"{text}@{term.language}"
    if term.datatype:
        return f"{text}^^<{term.datatype}>"
    return text


def _sorted_lines(triples: Iterable[tuple[Any, Any, Any]], graph_term: URIRef | None) -> str:
    tail = f" <{graph_term}> ." if graph_term is not None else " ."
    lines = sorted(f"{_nt_term(s)} {_nt_term(p)} {_nt_term(o)}{tail}" for s, p, o in triples)
    return "".join(line + "\n" for line in lines)


def _wrap_trig(turtle: str, graph_term: URIRef) -> str:
    """Wrap a Turtle document in a TriG named-graph block.

    rdflib's own TriG writer still calls deprecated ``Dataset`` APIs, so the (already
    deterministic) Turtle output is wrapped instead: prefix declarations stay at the
    top level, every other line moves inside ``<graph> { ... }``.
    """
    lines = turtle.splitlines()
    split = 0
    while split < len(lines) and (lines[split].startswith("@prefix") or not lines[split].strip()):
        split += 1
    prefixes = lines[:split]
    body = ["    " + line if line.strip() else "" for line in lines[split:]]
    return "\n".join([*prefixes, f"<{graph_term}> {{", *body, "}", ""])


def _serialize(graph: Graph, fmt: str, base: str, named_graph: bool) -> str:
    graph_term = graph_iri(base) if named_graph else None
    if fmt == "nt":
        return _sorted_lines(graph, None)
    if fmt == "nq":
        return _sorted_lines(graph, graph_term)
    if fmt == "trig":
        turtle = graph.serialize(format="turtle")
        if graph_term is None:
            return turtle  # Turtle is valid TriG for the default graph
        return _wrap_trig(turtle, graph_term)
    return graph.serialize(format=SUPPORTED_FORMATS[fmt])


def graph_to_rdf(
    doc: GraphDocument,
    path: Path,
    *,
    fmt: str = "nq",
    namespace_base: str | None = None,
    named_graph: bool = True,
    entry: dict[str, Any] | None = None,
    language: str | None = None,
) -> Path:
    """Serialize ``doc`` as RDF to ``path`` and return ``path``.

    Entity IRIs live under ``namespace_base`` (default
    ``https://purl.org/okn/frink/kg/<shortname>/``); quad formats (``nq``, ``trig``) put
    the triples in the named graph ``namespace_base`` minus its trailing slash when
    ``named_graph`` is true. See the module docstring for the vocabulary mapping.

    Raises:
        ValueError: ``fmt`` is not one of :data:`SUPPORTED_FORMATS`.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported RDF format: {fmt!r}")
    base = _ensure_base(namespace_base or default_namespace_base(doc.name))
    graph = build_rdf_graph(doc, namespace_base=base, entry=entry, language=language)
    payload = _serialize(graph, fmt, base, named_graph and fmt in _QUAD_FORMATS)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")
    return destination
