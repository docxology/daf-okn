# Documents and topic concepts

`src/daf_okn/core/cognitive_adapter.py::separate_document_topics` separates a
Markdown document from its subject. The original node ID remains the document
ID. A declared topic gets `concept:<path>` as a separate node ID. The RDF
serializer maps these to stable `/page/<path>` CreativeWork document IRIs and
`/concept/<path>` SKOS (Simple Knowledge Organization System) concept IRIs.
Both `schema:about` and `dcterms:subject` connect the document to its topic.
No resource has both roles. The model marker is `document-concept-v1`.
`attributes.entity_role` is authoritative; a document's existing `node_type`
retains the source frontmatter category, including a category spelled `concept`.
Topic records use `node_type == "topic_concept"` and `entity_role == "concept"`.

Topic eligibility follows the explicit `TOPIC_TYPES` profile. Untyped pages
remain documents unless they carry reviewed topic mappings. Navigation,
citations, redirects, guides and unknown editorial types do not acquire topics.
The generic adapter does not import or execute cognitive's exporter.

Document titles, descriptions, dates, authors, publication identifiers, source,
license, tags, body references and redirects remain on documents. Topic labels,
aliases, definitions, scope notes and reviewed SKOS mappings belong to concepts.
Every reviewed correspondence retains its target, relation, evidence, rationale
and date; its RDF statement subject is the concept. Multiple separately reviewed
external targets are retained without selecting an arbitrary representative.
Unreviewed Wikidata fields remain document discovery links (`rdfs:seeAlso`).

Known conceptual relations connect topics. `foundation_for` points from the
foundation to the topic it supports; `foundation` points toward the foundation.
`implements` connects a method/design concept to its specification/theory
concept and asserts no execution or real-world instance. Meanings and scopes
are defined in `CONCEPT_RELATIONS`; emitted custom predicates carry comments,
domain and range. Part/component relations between topics use conceptual
predicates; document containment uses Dublin Core Terms. Citation predicates
use BIBO (Bibliographic Ontology) with their source direction. Navigation,
documentation and body links connect documents.

Unknown relations and conceptual assertions with a non-topic endpoint become
`relation/document/<source-name>` document assertions. They retain the source
direction and endpoints, have no SKOS super-property, and are listed in
`metadata.document_assertions` for curation. This preserves the source assertion
without inventing a conceptual interpretation.

Tags use the curator-owned exact lookup in
`src/daf_okn/core/keyword_terms.py::keyword_iri`; unknown tags remain local
keyword Concepts/DefinedTerms with their original spelling. Keyword reuse is
subject metadata and creates neither identity nor class-instance assertions.

`src/daf_okn/core/rdf.py::validate_entity_model` checks role separation, matching
about/subject links, labels, typed endpoints, document metadata placement and
custom predicate scopes. `validate_rdf_semantics` additionally checks all
existing mapping evidence, IRI and keyword constraints. Canonical export and
bundle validation use this current model. Historical capture schemas 1 and 2
remain replayable only under their original query/source contract; new captures
use schema 3 and derive source URLs from the linked documents.

SPARQL-imported graphs (`metadata.source == "sparql"`) keep their original RDF
identities and explicit predicates. They are not treated as Markdown documents.
This profile does not perform global ontology reasoning or verify the scientific
truth of a source-authored relation or mapping.
