# RDF identity and structural measurement

## Preserve RDF terms before measuring them

`src/daf_okn/core/graph.py::bindings_to_graph` consumes SPARQL SELECT JSON.
An IRI, a blank node and a literal with the same spelling are different terms.
Literals also differ by lexical form, datatype and language. These distinctions
follow [RDF 1.1 term equality](https://www.w3.org/TR/rdf11-concepts/#section-Graph-Literal)
and the [SPARQL JSON term encoding](https://www.w3.org/TR/sparql11-results-json/).

The adapter preserves full predicate IRIs, including predicates with the same
final path component in different namespaces. URI node ids remain their IRIs;
blank nodes use `_:<label>`, scoped to one result document. Literal ids encode
quoted lexical form and datatype or normalized language. `"same"@en`,
`"same"@fr` and `"same"^^<urn:example:type>` remain different nodes.
Language-tag case and simple versus `xsd:string` forms are normalized.
Integer lexical forms `01` and `1` remain different terms even if their values agree.

Unbound rows are counted in `skipped_bindings`. Present malformed terms fail
with `ValueError` rather than disappearing as unbound. Subjects must be IRIs
or blank nodes, and predicates must be IRIs. Recognized variable aliases are
reserved before positional fallback, preventing reuse of one variable in two roles.

This corrects earlier graph JSON that used raw literal spelling as identity
and shortened predicates. Regenerate imported graph JSON from its saved SPARQL
results; retain earlier source-bound outputs as historical artifacts. The
generic page-oriented RDF exporter does not promise a verbatim round-trip of
the source RDF dataset or named graphs.

The Markdown adapter uses the [document/concept model](entity-model.md): source
documents and topics are separate nodes connected by about/subject edges.
Body references and citations count as document edges; semantic topic relations
count as concept edges. Total node and edge counts include both roles and the
model links. Compare measurements only when their model/projection contracts
agree. SPARQL imports retain their RDF identities and do not receive invented
CreativeWork or topic roles.

## Choose a projection explicitly

`GraphDocument.to_multidigraph()` preserves every directed edge record,
including parallel predicates, duplicate records and provenance. Integer edge
keys are the original record positions. See [NetworkX MultiDiGraph](https://networkx.org/documentation/stable/reference/classes/multidigraph.html).

`to_networkx()` retains the simple projection used for figures and connectivity.
Parallel records collapse to one edge whose attributes come from the last
record. Use the multigraph to inspect the complete predicate/provenance set.

## Distinguish statements from connectivity

| Quantity | Meaning |
|---|---|
| `stats.node_count`, `stats.edge_count` | Original node and edge record counts |
| `stats.projected_node_count`, `stats.projected_edge_count` | Nodes and directed pairs in the simple projection |
| `metrics.node_count`, `metrics.edge_count` | Projection counts used by centrality and connectivity |
| `metrics.edge_record_count` | Original edge record count |
| `statement_count` | Distinct `(source, relation, target)` tuples |
| `duplicate_statement_count` | Records repeating those tuples, irrespective of origin |
| `parallel_statement_count` | Distinct tuples collapsed by the simple projection |
| `relation_counts`, `node_type_counts` | Counts by source relation label and node type |

Relation counts precede RDF vocabulary alias normalization; they are not counts
of serialized RDF triples. Density uses projected directed pairs in both summaries,
following [NetworkX's definition](https://networkx.org/documentation/stable/reference/generated/networkx.classes.function.density.html).
Five predicates on one directed pair among two nodes give five records, five
statements, one projected edge and density `1/2`.

Self-links and dangling endpoints remain visible to `validate_graph`; invalid
documents' diagnostic metrics do not establish graph validity. Self-links can
increase NetworkX density beyond one and are separately reported as structural
profile violations. Centrality uses the directed simple projection; triangles
use its undirected projection. Ranking limits must be nonnegative integers,
with node ids breaking ties between equal scores.

Regression controls live in `tests/core/test_graph.py`, `tests/core/test_invariants.py`
and `tests/analysis/test_graph_metrics.py`. `src/daf_okn/analysis/pipeline.py::run_analysis`
persists the measurements in `graph_report.json`.
