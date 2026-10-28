# daf-okn

Pull, analyze, visualize and contribute to the [Open Knowledge Network](https://okn.us/) (OKN).

`daf-okn` is a small Python package and command line for working with OKN knowledge graphs:

- **pull** the registry catalog ([registry.okn.us](https://registry.okn.us/)) and query graph
  SPARQL endpoints;
- **export** a markdown vault (Obsidian-style pages with `[[links]]`) to a typed graph;
- **analyze** a graph (counts, density, connectivity, centrality) and **visualize** it (network
  figure, static HTML dashboard);
- **package** a graph for contribution to the OKN registry: RDF using standard vocabularies, a
  registry entry in the shape RENCI/FRINK asks for, and a checklist.

Its flagship use is exporting the Active Inference Institute's
[`cognitive`](https://github.com/ActiveInferenceInstitute/cognitive) knowledge base.

**Status:** version 0.2.0, the first public release. The offline parts (export, analyze,
visualize, package) are covered by tests; the registry client is tested against stubbed HTTP
sessions and has not been run against every live OKN endpoint. Nothing here uploads to the
registry for you: `package` writes files and prints the steps.

## Install

Python 3.10 or newer is declared; CI runs the tests on 3.12 and 3.14.

```bash
git clone https://github.com/docxology/daf-okn
cd daf-okn
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"      # drop [dev] if you do not need the test tools
daf-okn --version
```

## Quickstart

Export a vault, measure it, draw it, and package it for the registry:

```bash
daf-okn export --repo tests/fixtures/cognitive --out graph.json
daf-okn analyze --graph graph.json --out-dir report
daf-okn visualize --graph graph.json --figure network.png --dashboard dashboard.html
daf-okn package --graph graph.json --out-dir package \
    --entry-shortname my-kb --entry-title "My KB" --entry-description "What it holds." \
    --entry-homepage https://example.org/my-kb \
    --contact "email=you@example.org;github=you;label=You"
```

`tests/fixtures/cognitive` is a tiny vault shipped with the repository; point `--repo` at your
own vault instead. `python -m daf_okn ...` works the same as `daf-okn ...`.

## Command line

The cognitive repository owns its graph, licensing, vocabulary and graph-specific
queries. daf-okn owns capture/replay, registry packaging and upload methods.
See [canonical RDF and cross-graph workflows](docs/okn/cross-graph.md).

| Command | What it does |
| --- | --- |
| `daf-okn pull list [--kgs-path FILE]` | Print the registered graphs (reads `kgs.yaml` from the registry, or a local copy). |
| `daf-okn pull snapshot [--kgs-path FILE] [--out FILE]` | Save the registry metadata as YAML (default `data/okn/kgs.yaml`). |
| `daf-okn pull query --shortname NAME --sparql QUERY [--out FILE]` | Run a SPARQL query against one graph's endpoint and save the JSON result. |
| `daf-okn export --repo DIR [--out FILE] [--name NAME] [--keep-redirects] [--no-wikilinks]` | Read a vault (or a `cognitive` checkout, using its `knowledge_base/`) into graph JSON. |
| `daf-okn analyze --graph FILE [--out-dir DIR]` | Write `graph_report.json` with structural metrics; exits 1 if the graph breaks an invariant (dangling edge, duplicate id, ...). |
| `daf-okn status --graph FILE [--report FILE]` | Read-only JSON observation of graph invariants and optional report consistency; exits 1 for missing, malformed or inconsistent evidence. |
| `daf-okn stack-health --roster FILE [--member NAME] [--checkout DIR]` | Compare this checkout with one `daf-stack-doctor roster` member (offline, read-only): roster path, branch, required files, gate command, board and Sidecar manifest. |
| `daf-okn visualize --graph FILE [--figure PNG] [--dashboard HTML] [--metrics JSON] [--layout NAME]` | Render the network figure and the HTML dashboard (`--no-figure` / `--no-dashboard` skip one). |
| `daf-okn package --graph FILE --out-dir DIR [--fmt nq] [--preset NAME] [--entry-*] [--contact ...]` | Write the contribution package; exits 1 and lists problems if the entry is incomplete. |
| `daf-okn join --source FILE --query FILE --output DIR [--replay CAPTURE]` | Capture or replay the bounded cognitive-to-OBO assertion path. |
| `daf-okn explain-join --source FILE --query FILE --capture DIR --output DIR [--check]` | Explain a verified schema-3 path with local review records and recorded remote bindings, offline. |
| `daf-okn bundle-rdf --root COGNITIVE --output DIR [--check]` | Preserve and verify the canonical RDF and required review documentation. |

Run `daf-okn <command> --help` for every option. `pull` and live `join` use the network, and
`--kgs-path` avoids it for `list` and `snapshot`. `DAF_OKN_COGNITIVE_REPO` is the default for
`export --repo`. Captured `join --replay` and `explain-join` are offline.
The [explanation contract](docs/okn/join-explanations.md) keeps each mapping
predicate, review record and captured response origin visible for inspection.

The scripts in `scripts/` are thin wrappers over the same code (`scripts/10_research_workflow.py`
chains pull, export, analyze and visualize for the research manuscript).

Stack consumers should start with [local status, roster membership and Sidecar
evidence](docs/stack-integration.md). `stack-health` runs the roster comparison offline; it
never executes the gate.

## Contributing a graph to the OKN registry

`daf-okn package` produces three things in `--out-dir`:

- `<shortname>.nq` (or `.nt`, `.ttl`, `.trig`, `.jsonld` with `--fmt`): the graph, sorted and
  byte-stable, in the named graph `https://purl.org/okn/frink/kg/<shortname>`;
- `registry/docs/registry/kgs/<shortname>.md`: the registry entry, laid out so the `registry/`
  directory can be copied onto a clone of
  [`frink-okn/okn-registry`](https://github.com/frink-okn/okn-registry) for a pull request. Its
  frontmatter is exactly `template`, `shortname`, `title`, `description`, `stats`, `homepage`,
  `funding` (only if you pass `--entry-funding`), `frink-options` (`lakefs-repo`,
  `documentation-path`) and `contacts` (`email`, `github`, `label`). `sparql` and `tpf` are
  never written; the registry asks you to leave them out until RENCI has set up the endpoints;
- `checklist.md`: the remaining steps (lakeFS credentials, upload, conversion, tag).
  `python -m daf_okn.core.contribute upload-commands --repo NAME --dir DIR` prints upload commands.

### RDF vocabulary

Following RENCI's guidance to reuse existing vocabularies, nodes and edges become:

| In the graph document | In the RDF |
| --- | --- |
| Markdown document | `schema:CreativeWork`; navigation records also use `schema:CollectionPage` |
| Described topic | Separate `skos:Concept` with `skos:prefLabel` and `skos:inScheme`, linked from its document by `schema:about` and `dcterms:subject` |
| Document title and description | `dcterms:title`, `dcterms:description` |
| Topic aliases, `definition`, `scope_note` | `skos:altLabel`, `skos:definition`, `skos:scopeNote` on the concept |
| `created`, `updated`, `tags` | Document dates and concept-valued `schema:keywords`, reusing reviewed external terms |
| `authors`, `year`, `doi`, `wikidata` | Document `schema:author`, `schema:datePublished`, `schema:sameAs`, discovery-only `rdfs:seeAlso` |
| `external_mappings` | Source-reviewed SKOS mappings from the concept, with statement evidence |
| Conceptual `related` / `relates_to` | `skos:related` between topic concepts |
| Part and navigation relations | Role-aware conceptual or document containment; see the entity model |
| Body `[[link]]` (origin `wikilink`) | Document `dcterms:references` |
| `cited_by`, `cites` | Document `bibo:citedBy`, `bibo:cites`, preserving source direction |
| Reviewed conceptual custom predicates | Explicitly defined concept-to-concept relationships, including the scope of `foundation_for` and `implements` |
| Unknown or document-scoped typed assertions | Separate document predicates without a SKOS super-property; retained for further review |
| Other document attributes | `<base>vocab/<key>` |

Document IRIs use `https://purl.org/okn/frink/kg/<shortname>/page/<path>` and topic
IRIs use the distinct `concept/<path>` namespace. The graph also
carries a `dcat:Dataset` / `void:Dataset` description and a small PROV-O activity. Output has no
timestamps, so the same input always yields the same bytes.

The [entity model](docs/okn/entity-model.md) documents eligibility, identifier
migration, relation direction and endpoint roles. A page is not typed as its topic.

The [semantic export profile](docs/okn/cross-graph.md#semantic-export-profile)
documents mapping validation, direct STATO/NCI keyword reuse and the boundary
between discovery links and reviewed correspondences. The Markdown adapter
preserves these records, including nested review dates, before RDF serialization.

[RDF identity and structural measurement](docs/okn/graph-methods.md) documents
SPARQL term preservation, the lossless multigraph projection, and the distinction
between statement counts and the connectivity used for density and centrality.

### Relationship to the `cognitive` repository's exporter

The `cognitive` repository has its own reference exporter,
[`code/scripts/export_rdf.py`](https://github.com/ActiveInferenceInstitute/cognitive/blob/main/code/scripts/export_rdf.py),
and documents its vocabulary and registry entry in
[`docs/okn/`](https://github.com/ActiveInferenceInstitute/cognitive/tree/main/docs/okn). daf-okn
follows compatible vocabulary and IRI conventions, but link-resolution details such as links
into `docs/` and `code/`, per-page `dcterms:source`, and redirect handling differ. Use the `cognitive` exporter for the
canonical `cognitive-kb` submission; use daf-okn for the generic vault-to-graph path, analysis,
visualization and packaging of other graphs. For a `cognitive` checkout, `daf-okn package
--preset cognitive-kb` fills in that graph's registry entry:

```bash
daf-okn export --repo path/to/cognitive --out cognitive_kg.json
daf-okn package --graph cognitive_kg.json --out-dir package --preset cognitive-kb
```

## Vault adapter

`daf_okn.core.cognitive_adapter` is a generic Obsidian-vault adapter that was built for the
`cognitive` knowledge base. Markdown files produce document records and, for eligible
topic-bearing pages, separate topic records. YAML frontmatter supplies titles, types
and other fields; `semantic_relations` entries are routed according to their endpoint
roles and body `[[wiki links]]` become document references (code blocks and numeric matrix literals are
ignored). A link resolves relative to the page, then the vault root, then by file name, then by
frontmatter `aliases:`; names claimed by several pages always resolve to the alphabetically
first path. Links that resolve nowhere are listed in the graph's `metadata.unresolved_targets`
rather than dropped.

## Module map

| Module | Purpose |
| --- | --- |
| `daf_okn.cli` | The `daf-okn` command line. |
| `core/graph.py` | `GraphDocument`, `NodeRecord`, `EdgeRecord`; JSON and networkx conversion; SPARQL results to graph. |
| `core/registry.py` | `OKNRegistry`: `kgs.yaml`, per-graph and federation SPARQL, TPF, VoID, embeddings search. |
| `core/invariants.py` | `validate_graph`, `graph_stats`. |
| `core/cognitive_adapter.py` | Markdown vault to `GraphDocument`. |
| `core/keyword_terms.py` | Reviewed external subject terms, exact source-tag lookup and provenance validation. |
| `core/rdf.py` | `GraphDocument` to RDF with standard vocabularies (`graph_to_rdf`, `build_rdf_graph`). |
| `core/contribute.py` | Registry entry, checklist, upload commands, contribution package. |
| `core/manuscript_variables.py`, `core/documentation.py`, `core/project_paths.py` | Support for the research manuscript and generated API reference. |
| `analysis/` | `compute_metrics`, `run_analysis`. |
| `figures/`, `dashboard/` | Network figure, registry catalog chart, static HTML dashboard. |

Library use:

```python
from daf_okn import GraphDocument, NodeRecord, EdgeRecord
from daf_okn.core.rdf import graph_to_rdf

doc = GraphDocument("demo", [NodeRecord("a", "A"), NodeRecord("b", "B")],
                    [EdgeRecord("a", "b", "implements")])
graph_to_rdf(doc, "demo.ttl", fmt="ttl")
```

## Other folders

`docs/` holds user and developer documentation; `docs/okn/` are unofficial digests of OKN web
pages (see the note at the top of each file). `manuscript/` is a research manuscript about this
project whose numbers are filled in from pipeline output
(`python scripts/z_generate_manuscript_variables.py`); this repository does not render a PDF.
`AGENTS.md` files in each folder are written for AI coding agents.

## Development

```bash
pip install -e ".[dev]"
pytest -q --cov=src --cov-branch --cov-fail-under=90
ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests use real data and no live network requests.
Security issues: see [SECURITY.md](SECURITY.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## Cite

If you use daf-okn, please cite it using [`CITATION.cff`](CITATION.cff) (GitHub's "Cite this
repository" button reads it):

> Friedman, D. A. (2026). *DAF-OKN: Open Knowledge Network Pull, Analyze, Visualize, Contribute*
> (Version 0.2.0) [Computer software]. https://github.com/docxology/daf-okn

No DOI has been minted yet.

## License

MIT, see [LICENSE](LICENSE). The documentation digests in `docs/okn/` summarise third-party
pages and stay the property of their authors.
