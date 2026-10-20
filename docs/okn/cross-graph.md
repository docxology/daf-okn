# Canonical RDF and cross-graph workflows

The [cognitive repository](https://github.com/ActiveInferenceInstitute/cognitive)
owns cognitive-kb's source pages, canonical exporter, license, vocabulary,
signposting, graph-specific queries and captured graph evidence. daf-okn owns
the reusable OKN methods. `bundle-rdf` preserves the canonical graph bytes;
the alternative Markdown adapter does not replace that authoritative export.

## Capture and replay

`daf-okn join` reads a local N-Quads graph and a graph-specific query. It requests
existing Wikidata mappings to OBO identifiers from the OKN identifier-mappings
named graph, requests their labels from Ubergraph, and executes the three-graph
join locally. Requests are sequential, bounded by subject batches and a response
size limit. Failures retain the query and any received response; they exit 1.
An empty final join also exits 1. Existing capture directories are preserved.

```bash
daf-okn join --source cognitive/output/okn/cognitive-kb.nq \
  --query cognitive/docs/okn/queries/cross_graph_obo.rq \
  --output output/cognitive-live-capture
daf-okn join --source cognitive/output/okn/cognitive-kb.nq \
  --query cognitive/docs/okn/queries/cross_graph_obo.rq \
  --replay cognitive/docs/okn/evidence/2026-10-20 \
  --output output/cognitive-replay
```

Paths above assume a directory containing a `cognitive` checkout; choose paths
for your actual checkout. `--source`, `--query` and `--output` are required.
The default endpoint is the [documented OKN federation endpoint](https://registry.okn.us/query/query-page/).
`--endpoint` selects a compatible endpoint explicitly. The current profile uses
the cognitive-kb, identifier-mappings and Ubergraph named graphs and the projected
variables of cognitive's OBO query; it is not an arbitrary SPARQL runner.

A capture contains the exact queries, raw SPARQL JSON responses, SHA-256 hashes,
observation time, local-export hash and join-query hash in `manifest.json`.
`join-results.json` contains all joined rows; `join-results.md` provides linked
source pages, Wikidata keys and ontology labels. Replay verifies hashes, bounded
query structure, requested subjects and predicates before adding triples.
Changing the export or query requires a new capture, preserving the old one.

The first mapping may be reviewed `skos:exactMatch` or `skos:closeMatch`. Capture
uses only well-formed Wikidata entity IRIs and excludes `rdfs:seeAlso` discovery
links. Reviewed OBO mappings are not sent to the Wikidata mapping stage.
The remote mapping graph's
`skos:exactMatch` is retained as that source's assertion. Their composition does
not establish identity between a page and an ontology class. This command adds
no equivalence assertions to the submitted graph.

## Bundle canonical RDF

```bash
daf-okn bundle-rdf --root cognitive --output output/cognitive-submission
daf-okn bundle-rdf --output output/cognitive-submission --check
```

The builder checks export hashes, available source hashes, matching Turtle/N-Quads,
named-graph scope, and dataset/scheme/page licensing. It accepts CC BY 4.0 or CC0
1.0 and refuses incompatible licensing. It copies canonical artifacts, graph
documentation and attribution, extracts the registry entry, and adds registry
query headers using the [documented query metadata](https://registry.okn.us/help/update-queries/).
`bundle.json` records the source commit, dirty state and hashes of all bundle files.
The bundle also carries cognitive's generated alignment review and queries for
mapping evidence and concept-valued keywords. Semantic checks reject literal
keywords, undeclared local keyword concepts, custom citation predicates and
SKOS mappings without complete source/rationale/date evidence.
The check rejects changed, missing, extra or escaping files. An existing output
directory is not overwritten. Partial failed bundles remain available for diagnosis.

Only the canonical N-Quads object is intended for lakeFS upload. The manifest,
documentation and captured remote responses are review evidence, not additional
RDF inputs. Follow cognitive's landing-zone handoff for commit, merge, processing
and deployment receipts. Package verification is not registry acceptance.

Implementation: `src/daf_okn/analysis/cross_graph.py`,
`src/daf_okn/core/rdf_submission.py`, and `src/daf_okn/cli.py`.
Tests use real files, real local HTTP and SPARQL evaluation. No public endpoint is
required by the offline suite.

## Semantic export profile

Both exporters treat unreviewed `wikidata` fields as `rdfs:seeAlso` discovery links.
Only explicit `external_mappings` records produce SKOS correspondences. Each
record requires exactly `target`, `relation`, `evidence`, `rationale` and
`reviewed_on`; incomplete records, unsafe IRIs, invalid dates and duplicate targets
raise errors. Supported relations are the five SKOS mapping predicates.
See the [primary-source review](semantic-review-2026-10-20.md) and cognitive's
[vocabulary contract](https://github.com/ActiveInferenceInstitute/cognitive/blob/main/docs/okn/vocabulary.md).

Tags become named SKOS concepts with labels and original spellings.
`model_fitting` and `computational_modeling` instead reuse STATO:0000218 and
NCIT:C16461 as keyword objects. This does not assert that a publication is an
instance of its subject. `cited_by`/`cites` reuse BIBO with the source direction.
Explicit SIO predicates are supported; conceptual `implements` is not globally
rewritten because SIO requires an information entity conforming to a specification.

Historical capture manifests remain bound to their original source/query bytes.
After changing mappings or serializers, create a fresh capture; never rewrite old
hashes to make historical responses appear current.
