"""RDF serialization of :class:`~daf_okn.core.graph.GraphDocument` using standard vocabularies.

The OKN registry's guidance (FRINK / RENCI) is to reuse existing vocabularies and to
mint entity IRIs under ``https://purl.org/okn/frink/kg/<shortname>/``, with the named
graph ``https://purl.org/okn/frink/kg/<shortname>``. This module follows that, and
produces the same shapes as the reference exporter in the Active Inference Institute
``cognitive`` repository (``code/scripts/export_rdf.py``):

* vault pages retain ``/page/<path>`` CreativeWork document IRIs; topic-bearing
  pages link to distinct ``/concept/<path>`` SKOS concepts using both
  ``schema:about`` and ``dcterms:subject``. Citation, navigation, redirect and
  editorial records retain their document roles;
* node fields map to ``dcterms:title``, ``dcterms:description``, ``skos:altLabel``,
  ``dcterms:created``, ``dcterms:modified``, ``schema:keywords``, ``schema:author``,
  ``schema:datePublished``, ``schema:sameAs`` (DOI) and ``rdfs:seeAlso`` (unreviewed Wikidata);
  keywords are concept IRIs and explicit reviewed mappings carry RDF statement evidence;
* edge relations map to ``skos:related``, ``dcterms:isPartOf``, ``dcterms:hasPart``,
  ``dcterms:references`` (body wiki links), BIBO citation predicates and
  ``dcterms:isReplacedBy`` (redirects);
  reviewed conceptual relations have explicit direction, meaning and Concept
  domain/range. Unknown or mixed-role assertions use ``relation/document/``
  document predicates without a SKOS super-property;
* all other node attributes stay available as ``<base>vocab/<key>`` properties;
* a ``dcat:Dataset`` / ``void:Dataset`` description and a small PROV-O activity describe
  the graph itself.

Output is deterministic: N-Triples and N-Quads are written with sorted lines, no
timestamps are emitted, and the dataset's ``dcterms:modified`` is the latest node
``updated`` date.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, PROV, RDF, RDFS, SKOS, VOID, XSD

from .alignment import RELATIONS, checked_iri, reviewed_mappings
from .cognitive_adapter import (
    CONCEPT_RELATIONS,
    DOCUMENT_RELATION_MEANINGS,
    TOPIC_TYPES,
    separate_document_topics,
)
from .graph import EdgeRecord, GraphDocument, NodeRecord
from .keyword_terms import KEYWORD_TERMS as KEYWORD_TERMS
from .keyword_terms import keyword_iri

__all__ = [
    "KG_BASE",
    "SUPPORTED_FORMATS",
    "build_rdf_graph",
    "default_namespace_base",
    "graph_iri",
    "graph_to_rdf",
    "graph_to_rdf_diagnostics",
    "relation_predicate",
    "relation_slug",
    "shortname_slug",
    "validate_rdf_semantics",
    "validate_entity_model",
]

KG_BASE = "https://purl.org/okn/frink/kg/"
TOOL_URL = "https://github.com/docxology/daf-okn"

SCHEMA = Namespace("https://schema.org/")
BIBO = Namespace("http://purl.org/ontology/bibo/")

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
    "bibo": BIBO,
    "sio": Namespace("http://semanticscience.org/resource/"),
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
    "cites": BIBO.cites,
    "cited_by": BIBO.citedBy,
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
        "external_mappings",
        "definition",
        "scope_note",
        "source",
        "license",
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
    if text.startswith("document/"):
        return URIRef(f"{_ensure_base(namespace_base)}relation/document/{relation_slug(text[9:])}")
    if text.startswith("concept/"):
        return URIRef(f"{_ensure_base(namespace_base)}relation/{relation_slug(text[8:])}")
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


def _node_iri(namespace_base: str, node_id: str) -> URIRef | BNode:
    if node_id.startswith("_:"):
        return BNode(node_id[2:])
    if _is_external(node_id):
        return URIRef(node_id)
    if node_id.startswith("concept:"):
        return URIRef(f"{_ensure_base(namespace_base)}concept/{_quote(node_id[8:])}")
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

    if external or node.node_type == "bnode":
        graph.add((subject, RDFS.label, _lit(title, language)))
    elif attributes.get("entity_role") == "concept":
        graph.add((subject, RDF.type, SKOS.Concept))
        graph.add((subject, SKOS.inScheme, URIRef(base + "scheme")))
        graph.add((subject, SKOS.prefLabel, _lit(title, language)))
    else:
        graph.add((subject, RDF.type, SCHEMA.CreativeWork))
        if node.node_type in _NAVIGATION_TYPES:
            graph.add((subject, RDF.type, SCHEMA.CollectionPage))
        graph.add((subject, DCTERMS.title, _lit(title, language)))
        graph.add((subject, URIRef(base + "vocab/pageType"), Literal(node.node_type)))
        used_terms.add("pageType")

    description = _text(attributes.get("description", ""))
    if description:
        graph.add((subject, DCTERMS.description, _lit(description, language)))
    for key, predicate in (("source", DCTERMS.source), ("license", DCTERMS.license)):
        if attributes.get(key):
            graph.add((subject, predicate, URIRef(checked_iri(_text(attributes[key])))))
    for key, predicate in (("definition", SKOS.definition), ("scope_note", SKOS.scopeNote)):
        if attributes.get(key):
            if attributes.get("entity_role") == "document":
                name = "sourceDefinition" if key == "definition" else "sourceScopeNote"
                predicate = URIRef(base + "vocab/" + name)
                used_terms.add(name)
            graph.add((subject, predicate, _lit(_text(attributes[key]), language)))
    for alias in _scalars(attributes.get("aliases")):
        if _text(alias):
            predicate = SKOS.altLabel
            if attributes.get("entity_role") == "document":
                predicate = URIRef(base + "vocab/sourceAlias")
                used_terms.add("sourceAlias")
            graph.add((subject, predicate, _lit(_text(alias), language)))
    if attributes.get("created") is not None:
        graph.add((subject, DCTERMS.created, _typed_date(attributes["created"])))
    updated = attributes.get("updated") or attributes.get("modified")
    if updated is not None:
        graph.add((subject, DCTERMS.modified, _typed_date(updated)))
        modified.append(_text(updated))
    for tag in _scalars(attributes.get("tags")):
        if _text(tag):
            label = str(tag)
            external_keyword = keyword_iri(label)
            if external_keyword is not None:
                graph.add((subject, SCHEMA.keywords, URIRef(external_keyword)))
                continue
            keyword = URIRef(base + "keyword/" + quote(label, safe="-._~"))
            graph.add((subject, SCHEMA.keywords, keyword))
            graph.add((keyword, RDF.type, SKOS.Concept))
            graph.add((keyword, RDF.type, SCHEMA.DefinedTerm))
            graph.add((keyword, SKOS.prefLabel, _lit(label.replace("_", " "), language)))
            graph.add((keyword, SKOS.notation, Literal(label)))
            graph.add((keyword, SKOS.inScheme, URIRef(base + "scheme")))
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
        graph.add((subject, RDFS.seeAlso, URIRef("http://www.wikidata.org/entity/" + qid)))

    mappings = reviewed_mappings(attributes.get("external_mappings"))
    if mappings and attributes.get("entity_role") != "concept":
        raise ValueError(f"non-concept node {node.id!r} cannot carry SKOS mappings")
    for mapping in mappings:
        predicate, target = URIRef(str(SKOS) + mapping.relation), URIRef(mapping.target)
        graph.add((subject, predicate, target))
        key = hashlib.sha256(f"{subject}\n{predicate}\n{target}".encode()).hexdigest()
        statement = URIRef(base + "mapping/" + key)
        for p, o in (
            (RDF.type, RDF.Statement),
            (RDF.subject, subject),
            (RDF.predicate, predicate),
            (RDF.object, target),
            (DCTERMS.source, URIRef(mapping.evidence)),
            (DCTERMS.description, _lit(mapping.rationale, language)),
            (DCTERMS.date, Literal(mapping.reviewed_on, datatype=XSD.date)),
        ):
            graph.add((statement, p, o))

    for key in sorted(attributes):
        if key == "entity_role":
            continue
        if key in _MAPPED_ATTRIBUTES and not (key == "wikidata" and qid and not wikidata_ok):
            continue
        key_slug = _quote(key)
        for leaf in _scalars(attributes[key]):
            graph.add((subject, URIRef(f"{base}vocab/{key_slug}"), Literal(leaf)))
            used_terms.add(key_slug)


def _edge_target(
    edge: EdgeRecord, base: str, literals: dict[str, NodeRecord], *, sparql_terms: bool = False
) -> URIRef | BNode | Literal:
    literal_node = literals.get(edge.target)
    if literal_node is None:
        return _node_iri(base, edge.target)
    attrs = literal_node.attributes
    value = literal_node.title if sparql_terms else literal_node.id
    if attrs.get("xml:lang"):
        return Literal(value, lang=str(attrs["xml:lang"]), normalize=not sparql_terms)
    if attrs.get("datatype"):
        return Literal(value, datatype=URIRef(str(attrs["datatype"])), normalize=not sparql_terms)
    return Literal(value)


def _declare_vocabulary(
    graph: Graph, base: str, relations: set[str], terms: set[str], language: str | None
) -> None:
    for slug in sorted(relations):
        term = URIRef(f"{base}relation/{slug}")
        graph.add((term, RDF.type, RDF.Property))
        conceptual = slug in CONCEPT_RELATIONS
        if conceptual:
            graph.add((term, RDFS.subPropertyOf, SKOS.semanticRelation))
        scope = SKOS.Concept if conceptual else SCHEMA.CreativeWork
        graph.add((term, RDFS.domain, scope))
        graph.add((term, RDFS.range, scope))
        graph.add((term, RDFS.label, _lit(slug.replace("_", " "), language)))
        graph.add(
            (
                term,
                RDFS.comment,
                _lit(
                    CONCEPT_RELATIONS[slug]
                    if conceptual
                    else DOCUMENT_RELATION_MEANINGS.get(
                        slug.removeprefix("document/"),
                        f"Document assertion '{slug.removeprefix('document/')}' "
                        "from source document to target document; preserves a source link "
                        "for curation, without asserting a relation between topic concepts.",
                    ),
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
    for vocabulary in (SKOS, DCTERMS, SCHEMA, PROV, BIBO):
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

    Raises:
        ValueError: Source records or the resulting RDF violate the export profile.
    """
    base = _ensure_base(namespace_base or default_namespace_base(doc.name))
    graph = _build_rdf_graph(doc, namespace_base=base, entry=entry, language=language)
    errors = validate_rdf_semantics(
        graph, base, entity_model=doc.metadata.get("source") != "sparql"
    )
    if errors:
        raise ValueError("; ".join(errors))
    return graph


def _build_rdf_graph(
    doc: GraphDocument,
    *,
    namespace_base: str,
    entry: dict[str, Any] | None,
    language: str | None,
) -> Graph:
    """Assemble export triples without interpreting their validation verdict."""
    doc = separate_document_topics(doc)
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
        if node.attributes.get("entity_role") == "concept" and "/" in node.id:
            top = node.id.removeprefix("concept:").split("/", 1)[0]
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
        graph.add(
            (
                _node_iri(base, edge.source),
                predicate,
                _edge_target(
                    edge, base, literals, sparql_terms=doc.metadata.get("source") == "sparql"
                ),
            )
        )

    _declare_vocabulary(graph, base, used_relations, used_terms, language)
    _describe_dataset(graph, base, doc, entry, modified, domains, language)
    return graph


def validate_entity_model(graph: Graph, namespace_base: str) -> list[str]:
    """Check explicit document/topic roles and local predicate endpoint scopes.

    External mapping and keyword targets need not be redeclared locally. Local
    pages and topics must be typed. Each local topic has exactly its same-path
    document owner, linked with both about and subject; document-only source
    roles cannot acquire topics. This is a bounded RDF profile, not OWL reasoning.
    """
    base = _ensure_base(namespace_base)
    errors: list[str] = []
    resources = {term for s, _, o in graph for term in (s, o) if isinstance(term, URIRef)}
    pages = {term for term in resources if str(term).startswith(base + "page/")}
    topics = {term for term in resources if str(term).startswith(base + "concept/")}
    concepts = set(graph.subjects(RDF.type, SKOS.Concept))
    documents = set(graph.subjects(RDF.type, SCHEMA.CreativeWork))
    for resource in concepts & documents | concepts & pages:
        errors.append(f"document/concept conflation: {resource}")
    for concept in concepts:
        if str(concept).startswith(base) and not str(concept).startswith(
            (base + "concept/", base + "keyword/")
        ):
            errors.append(f"local concept must use a concept or keyword IRI: {concept}")
    for page in pages - documents:
        errors.append(f"page requires CreativeWork type: {page}")
    for page in pages:
        if any(
            p in {SKOS.prefLabel, SKOS.altLabel, SKOS.definition, SKOS.scopeNote, SKOS.inScheme}
            for p in graph.predicates(page)
        ):
            errors.append(f"concept labels or scope attached to document: {page}")
    for topic in topics:
        if topic not in concepts or not any(
            isinstance(v, Literal) and str(v).strip() for v in graph.objects(topic, SKOS.prefLabel)
        ):
            errors.append(f"topic requires Concept type and prefLabel: {topic}")
        about = set(graph.subjects(SCHEMA.about, topic))
        subject_documents = set(graph.subjects(DCTERMS.subject, topic))
        owner = URIRef(base + "page/" + str(topic)[len(base + "concept/") :])
        if (
            owner not in documents
            or about != {owner}
            or subject_documents != {owner}
            or any(
                set(graph.objects(owner, predicate)) != {topic}
                for predicate in (SCHEMA.about, DCTERMS.subject)
            )
        ):
            errors.append(f"topic requires matching document about/subject links: {topic}")
    for topic_predicate in (SCHEMA.about, DCTERMS.subject):
        for document, candidate_topic in graph.subject_objects(topic_predicate):
            if (
                document not in documents
                or not isinstance(candidate_topic, URIRef)
                or candidate_topic in documents
                or (str(candidate_topic).startswith(base) and candidate_topic not in concepts)
            ):
                errors.append(
                    "about/subject endpoints require a document and concept: "
                    f"{document} {candidate_topic}"
                )
    for page in pages:
        about = set(graph.objects(page, SCHEMA.about))
        subject_topics = set(graph.objects(page, DCTERMS.subject))
        page_types = {str(t) for t in graph.objects(page, URIRef(base + "vocab/pageType"))}
        suffix = str(page)[len(base + "page/") :]
        # WHY: decode only to inspect source-path roles. Ownership compares exact
        # RDF terms, so percent-encoded aliases never become interchangeable IRIs.
        parts = unquote(suffix).split("/")
        document_only = (
            bool(page_types - TOPIC_TYPES)
            or "citations" in parts[:-1]
            or parts[-1].lower() in {"readme", "agents", "catalog", "index"}
            or (page, RDF.type, SCHEMA.CollectionPage) in graph
        )
        if document_only and (about or subject_topics):
            errors.append(f"document-only page cannot have topic about/subject links: {page}")
        if about != subject_topics or (
            not document_only
            and page_types & TOPIC_TYPES
            and about != {URIRef(base + "concept/" + suffix)}
        ):
            errors.append(f"page requires matching about/subject links for its topic: {page}")
    document_predicates = {
        DCTERMS.title,
        DCTERMS.description,
        DCTERMS.created,
        DCTERMS.modified,
        DCTERMS.source,
        DCTERMS.license,
        DCTERMS.references,
        DCTERMS.isReplacedBy,
        SCHEMA.author,
        SCHEMA.datePublished,
        SCHEMA.sameAs,
        SCHEMA.keywords,
        BIBO.cites,
        BIBO.citedBy,
    }
    for concept in concepts:
        if any(
            p in document_predicates or str(p).startswith(base + "vocab/")
            for p in graph.predicates(concept)
        ):
            errors.append(f"document metadata or citations attached to concept: {concept}")
    mapping_predicates = {URIRef(str(SKOS) + relation) for relation in RELATIONS}
    semantic_predicates = {
        SKOS.related,
        SKOS.broader,
        SKOS.narrower,
        SKOS.semanticRelation,
        SKOS.broaderTransitive,
        SKOS.narrowerTransitive,
    }
    while True:
        inherited = {
            child
            for child, parent in graph.subject_objects(RDFS.subPropertyOf)
            if isinstance(child, URIRef) and parent in semantic_predicates
        }
        if inherited <= semantic_predicates:
            break
        semantic_predicates.update(inherited)
    for subject, predicate, target in graph:
        if (
            predicate == SKOS.member
            and str(subject).startswith(base + "domain/")
            and target not in concepts
        ):
            errors.append(f"domain membership requires a concept: {target}")
        if predicate in mapping_predicates and (
            subject not in concepts
            or subject in pages
            or target in documents
            or str(target).startswith(base + "page/")
        ):
            errors.append(f"mapping cannot use document endpoints: {subject} {target}")
        if predicate in semantic_predicates - mapping_predicates and (
            subject not in concepts or target not in concepts or subject in pages or target in pages
        ):
            errors.append(
                "conceptual relation requires typed concept endpoints: "
                f"{subject} {predicate} {target}"
            )
        if str(predicate).startswith(base + "relation/"):
            conceptual = (
                not str(predicate).startswith(base + "relation/document/")
                and str(predicate)[len(base + "relation/") :] in CONCEPT_RELATIONS
            )
            scope = SKOS.Concept if conceptual else SCHEMA.CreativeWork
            if (
                set(graph.objects(predicate, RDFS.domain)) != {scope}
                or set(graph.objects(predicate, RDFS.range)) != {scope}
                or (predicate, RDF.type, RDF.Property) not in graph
                or not any(
                    isinstance(v, Literal) and str(v).strip()
                    for v in graph.objects(predicate, RDFS.comment)
                )
                or (conceptual and predicate not in semantic_predicates)
            ):
                errors.append(f"custom relation lacks explicit meaning/domain/range: {predicate}")
            if not conceptual and predicate in semantic_predicates:
                errors.append(f"document relation cannot be a SKOS semantic relation: {predicate}")
            endpoints = concepts if conceptual else documents
            if any(str(t).startswith(base) and t not in endpoints for t in (subject, target)):
                errors.append(
                    f"custom relation has wrong endpoint scope: {subject} {predicate} {target}"
                )
        if predicate in {
            BIBO.cites,
            BIBO.citedBy,
            DCTERMS.references,
            DCTERMS.isReplacedBy,
            DCTERMS.hasPart,
            DCTERMS.isPartOf,
        } and any(str(t).startswith(base) and t not in documents for t in (subject, target)):
            errors.append(
                f"document relation requires document endpoints: {subject} {predicate} {target}"
            )
    return sorted(set(errors))


def validate_rdf_semantics(
    graph: Graph, namespace_base: str, *, entity_model: bool = True
) -> list[str]:
    """Check this export profile's mapping evidence and concept-valued keywords.

    These are explicit local custody constraints, not global OWL reasoning or
    independent confirmation that a reviewed correspondence is scientifically true.
    """
    base = _ensure_base(namespace_base)
    errors: list[str] = validate_entity_model(graph, base) if entity_model else []
    iris = {term for triple in graph for term in triple if isinstance(term, URIRef)}
    iris.update(
        term.datatype
        for _, _, term in graph
        if isinstance(term, Literal) and term.datatype is not None
    )
    for iri in iris:
        text = str(iri)
        if re.search(r'[\s<>"{}|^`\\\x00-\x1f\x7f]', text) or not re.match(
            r"[A-Za-z][A-Za-z0-9+.-]*:", text
        ):
            errors.append(f"invalid RDF IRI: {text!r}")
        elif text.lower().startswith(("http:", "https:")):
            try:
                checked_iri(text)
            except ValueError as error:
                errors.append(str(error))
    predicates = {URIRef(str(SKOS) + relation): relation for relation in RELATIONS}
    assertions = {(s, p, o) for s, p, o in graph if p in predicates}
    targets: dict[tuple[Any, Any], set[Any]] = {}
    for subject, predicate, target in assertions:
        targets.setdefault((subject, target), set()).add(predicate)
        if (
            not isinstance(subject, URIRef)
            or not isinstance(target, URIRef)
            or (subject, RDF.type, SKOS.Concept) not in graph
            or (
                entity_model
                and any(
                    str(endpoint).startswith(base + "page/")
                    or (endpoint, RDF.type, SCHEMA.CreativeWork) in graph
                    for endpoint in (subject, target)
                )
            )
            or subject == target
            or (str(target).startswith(base) and (target, RDF.type, SKOS.Concept) not in graph)
        ):
            errors.append(
                f"mapping endpoints must be distinct concepts and IRIs: {subject} {target}"
            )
        for endpoint in (subject, target):
            try:
                checked_iri(str(endpoint))
            except ValueError as error:
                errors.append(str(error))
    for (subject, target), relations in targets.items():
        if len(relations) != 1:
            errors.append(f"conflicting mapping relations: {subject} {target}")
    candidates = set(graph.subjects(RDF.predicate, None)) | {
        s for s in graph.subjects() if str(s).startswith(base + "mapping/")
    }
    evidenced: set[tuple[Any, Any, Any]] = set()
    for statement in candidates:
        ps = list(graph.objects(statement, RDF.predicate))
        if not str(statement).startswith(base + "mapping/") and not any(
            p in predicates for p in ps
        ):
            continue
        values = [
            list(graph.objects(statement, p))
            for p in (
                RDF.subject,
                RDF.predicate,
                RDF.object,
                DCTERMS.source,
                DCTERMS.description,
                DCTERMS.date,
            )
        ]
        if (statement, RDF.type, RDF.Statement) not in graph or any(len(v) != 1 for v in values):
            errors.append(
                f"mapping statement requires complete single-valued evidence: {statement}"
            )
            continue
        subject, predicate, target, source, rationale, reviewed = [v[0] for v in values]
        assertion = subject, predicate, target
        if not isinstance(predicate, URIRef) or assertion not in assertions:
            errors.append(f"orphan mapping evidence: {statement}")
            continue
        if (
            not isinstance(source, URIRef)
            or not isinstance(rationale, Literal)
            or not isinstance(reviewed, Literal)
            or reviewed.datatype != XSD.date
        ):
            errors.append(f"invalid mapping evidence RDF terms: {statement}")
            continue
        try:
            reviewed_mappings(
                [
                    dict(
                        target=str(target),
                        relation=predicates[predicate],
                        evidence=str(source),
                        rationale=str(rationale),
                        reviewed_on=str(reviewed),
                    )
                ]
            )
        except ValueError as error:
            errors.append(f"invalid mapping evidence: {statement}: {error}")
        else:
            evidenced.add(assertion)
    for subject, predicate, target in assertions - evidenced:
        errors.append(f"mapping lacks complete review evidence: {subject} {predicate} {target}")
    for subject, keyword in graph.subject_objects(SCHEMA.keywords):
        if not isinstance(keyword, URIRef):
            errors.append(f"keyword must be a concept IRI: {subject}")
        elif str(keyword).startswith(base) and (
            (keyword, RDF.type, SKOS.Concept) not in graph
            or not any(
                isinstance(label, Literal) and str(label).strip()
                for label in graph.objects(keyword, SKOS.prefLabel)
            )
        ):
            errors.append(f"local keyword lacks concept declaration or label: {keyword}")
        else:
            try:
                checked_iri(str(keyword))
            except ValueError as error:
                errors.append(str(error))
    return sorted(set(errors))


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


def _write_rdf(graph: Graph, path: Path, fmt: str, base: str, named_graph: bool) -> Path:
    """Write assembled triples without adding, removing or repairing assertions."""
    payload = _serialize(graph, fmt, base, named_graph and fmt in _QUAD_FORMATS)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")
    return destination


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
        ValueError: ``fmt`` is unsupported, source records are invalid, or the
            resulting RDF violates the export profile. No file is written.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported RDF format: {fmt!r}")
    base = _ensure_base(namespace_base or default_namespace_base(doc.name))
    graph = build_rdf_graph(doc, namespace_base=base, entry=entry, language=language)
    return _write_rdf(graph, path, fmt, base, named_graph)


def graph_to_rdf_diagnostics(
    doc: GraphDocument,
    path: Path,
    *,
    fmt: str = "nq",
    namespace_base: str | None = None,
    named_graph: bool = True,
    entry: dict[str, Any] | None = None,
    language: str | None = None,
) -> list[str]:
    """Write inspectable draft RDF and return its semantic validation problems.

    Uses the same triples and validators as :func:`graph_to_rdf`, retaining
    invalid assertions for diagnosis instead of raising on the RDF verdict.
    Callers must combine the returned problems with structural and package
    checks; a written file is not evidence of a publishable package.

    Args:
        doc: Source graph document; it is not repaired or modified.
        path: Destination for diagnostic RDF.
        fmt: A format in :data:`SUPPORTED_FORMATS`.
        namespace_base: Entity-IRI base, defaulting to the graph name's base.
        named_graph: Use the named graph in quad formats when true.
        entry: Optional registry-entry inputs for the dataset description.
        language: Language tag for human-readable literals.

    Returns:
        Semantic errors, empty only when the RDF passes the export profile.
        This does not replace ``doc.validate()`` or registry-entry checks.

    Raises:
        ValueError: The format or source records prevent RDF construction.
            Construction and serialization errors propagate without suppression.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported RDF format: {fmt!r}")
    base = _ensure_base(namespace_base or default_namespace_base(doc.name))
    graph = _build_rdf_graph(doc, namespace_base=base, entry=entry, language=language)
    problems = validate_rdf_semantics(
        graph, base, entity_model=doc.metadata.get("source") != "sparql"
    )
    _write_rdf(graph, path, fmt, base, named_graph)
    return problems
