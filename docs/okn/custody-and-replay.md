# RDF custody and replay contracts

`src/daf_okn/core/rdf_submission.py::validate_export` validates canonical
cognitive exports. With a source root, it compares the manifest's source names
with every root Markdown file and every Markdown file under `knowledge_base`,
`docs` and `code`, the knowledge-base license, existing `pyproject.toml`, `uv.lock`
and `.python-version`, and the local Python import closure rooted at
`code/scripts/export_rdf.py`. Markdown matching uses
`name.casefold().endswith('.md')`. Static
imports in both execution branches count; dependencies are inspected without
executing exporter code. The `scripts` package initializer counts when present.
Third-party packages and dynamic imports are outside this static inventory.
The `resolution_files` list separately binds the sorted names of all regular
root files and all files under those three trees. Extensionless files can shadow
Markdown link targets, so Markdown hashes alone cannot establish source custody.
Generated/cache names inside the three trees are included. Other checkout
directories and arbitrary filesystem probes outside these scopes remain outside
the inventory; this is a bounded source profile, not a hermetic filesystem claim.
Non-Markdown contents are hashed only for runtime modules and the named config
files; other non-Markdown files are bound by name and regular-file status.

All recorded names must be canonical POSIX relative paths. Absolute paths,
traversal, path aliases, backslashes, symlink files/directories and special files
are rejected. Directory traversal errors propagate. JSON parsing rejects
duplicate keys, non-object manifests, nonfinite constants and files over the
manifest size limit. Hash inventories must be nonempty mappings of names to
lowercase SHA-256 strings. A source-less check cannot establish that the source
tree still matches its recorded inventory. Historical source-less manifests may
omit `resolution_files`; current-root verification requires it, and explicit
null or malformed inventories are errors.

The canonical artifact inventory contains Turtle and N-Quads. Both must parse,
describe the same triples and use only the designated nonempty named graph.
Dataset and scheme licenses must agree with the manifest. Bundle verification
requires every file in the source-defined `BUNDLE_FILES` profile and rejects
additional payloads even if their hashes have been recorded. It repeats export
validation after hash verification; hashes alone cannot approve divergent RDF.
The builder validates the completed bundle and rechecks sources before success.
It preserves the canonical RDF bytes.

`src/daf_okn/core/rdf.py::validate_rdf_semantics` applies the same local mapping
and keyword constraints to generic exports and canonical bundles. Assertions
require distinct IRI endpoints and a declared source concept; local mapping
targets must also be declared concepts. Each subject/target pair has one reviewed
relation in this profile. Mapping evidence must have single-valued subject,
predicate, object, source, rationale and typed date, and describe an asserted
mapping. Incomplete or orphan evidence is an error even if another complete
statement exists. Local keyword concepts require labels and declarations.
These constraints do not add global OWL rules. The
[W3C SKOS reference](https://www.w3.org/TR/skos-reference/#mapping)
defines mapping properties; this project's review records document local
source comparisons and do not prove that they are scientifically correct.

The current [entity model](entity-model.md) also rejects page Concept typing,
document mapping endpoints, semantic relations attached to documents, concept
source/publication metadata, mismatched about/subject links, missing local types
and custom predicates without explicit meanings and endpoint scopes. The bundle
inventory includes cognitive's `entity-model.md`,
`keyword-curation-2026-10-23.md` and `relation_scopes.rq`. Static imports bring
`rdf_keywords.py` and `rdf_relations.py` into runtime custody automatically;
omitting either imported source fails current-root verification.

New joins use capture schema 3. Its seven projected variables are page, concept,
label, wikidata, external, externalLabel and source; the source must belong to
a projected CreativeWork document linked to the concept with both about and subject.
Schemas 1 and 2 retain their historical concept-local source contract for
replay, and cannot be used to downgrade a new document/concept source graph.

HTTP IRI validation uses the shared parser in
`src/daf_okn/core/alignment.py`. The export profile requires DNS/IP hosts,
valid ports and percent escapes and excludes user information and encoded
hostnames. Valid Unicode DNS names and paths retain their original bytes.
This is a deliberate local profile: Python's
[URL parser documentation](https://docs.python.org/3/library/urllib.parse.html#url-parsing-security)
explains that component splitting does not itself establish URL validity.

Captured joins use sequential batches of at most 100 distinct subjects and a
4 MiB response limit. Responses must supply the exact `s`, `p`, `o` projection
and well-formed RDF term records. Capture queries have a fixed named graph,
predicate and subject inventory. Response rows cannot introduce other subjects,
predicates or remote graphs. Local N-Quads may contain only cognitive-kb's
named graph, so local data cannot prepopulate either remote stage. Offline
queries reject `SERVICE` and dataset loading clauses. Every reported result row
must be supported by the local mapping, remote mapping and remote label graphs.

New captures use manifest schema version 3. They hash all capture queries and
responses, the stored join query and both result files. Results include
structured provenance matching the manifest. Replay derives and checks every
required batch, count and artifact, then compares the recomputed result bytes.
JSON manifests and result JSON have an 8 MiB limit. Original unversioned
manifests remain supported when they satisfy their original schema and complete
batch contract. Their historical summary files were not hashed by that schema;
replay recomputes the summaries from the hashed responses. Replay always writes
to a new output directory.

SHA-256 establishes consistency against the supplied manifest. It does not
authenticate an unsigned manifest, a remote endpoint's assertion or a source
commit, and cannot detect a coordinated rewrite of every artifact and hash
without an independently trusted digest or signature. Joining reviewed local
`closeMatch`/`exactMatch` assertions with a remote `exactMatch` assertion adds no
new correspondence or equivalence assertion to the submitted graph.

The direct tests in `tests/core/test_rdf_submission.py`,
`tests/core/test_alignment.py`, `tests/core/test_rdf.py` and
`tests/analysis/test_cross_graph.py` use real files, RDF parsing and local HTTP.
They include accepting controls alongside rejecting controls for each boundary.
