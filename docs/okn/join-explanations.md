# Offline join explanations

`daf-okn explain-join` writes inspectable assertion-path evidence for a verified
schema-3 cognitive document/concept capture. It reads the supplied local export,
join query and capture; it makes no endpoint requests. Use a fresh output directory
outside the capture and outside the directories containing the source and query:

```bash
uv run --no-sync daf-okn explain-join \
  --source path/to/local-export/cognitive-kb.nq \
  --query path/to/queries/cross_graph_obo.rq \
  --capture path/to/capture \
  --output path/to/new-support

uv run --no-sync daf-okn explain-join \
  --source path/to/local-export/cognitive-kb.nq \
  --query path/to/queries/cross_graph_obo.rq \
  --capture path/to/capture \
  --output path/to/new-support --check
```

The command exits nonzero on verification failure. `--check` recomputes all support
from the bound inputs and compares every output byte and the exact output inventory;
it performs no writes. Updating a support file and its own manifest hash cannot
make altered row indices, reviews or binding origins pass. The same implementation
and RDFLib version must be available: producer source hashes deliberately bind the
algorithm used for recomputation.

## Files and schema

The output contains exactly these siblings:

| File | Contract |
| --- | --- |
| `join-support.json` | Authoritative explanation schema version 1 |
| `join-support.md` | Readable limits and a complete JSON rendering |
| `support-manifest.json` | Explanation profile/version and SHA-256 of both reports |

The explanation profile is `cognitive-obo-join-support-1`; it is separate from the
capture schema. Existing capture, result JSON, result Markdown and query bytes are
never rewritten. Existing `join` behavior and schema-1/2/3 replay remain available;
explanation generation explicitly rejects historical schemas 1/2.

`origin` records the captured observation time and declared endpoint, exact source
and query hashes, capture-manifest hash, both captured result hashes and the ordered
capture catalog. Empty requested batches remain in that catalog. No new wall-clock
time, absolute machine path or unbound source-commit claim is introduced.
`producer` records the package/RDFLib versions and hashes of the algorithm source
modules. Those hashes identify bytes; they do not authenticate authorship.

Each `groups[]` item contains:

- `values`: all seven original scalar fields (`page`, `concept`, `label`,
  `wikidata`, `external`, `externalLabel`, `source`).
- `row_indices`: every original zero-based position having exactly those values,
  bound to the result-file hash in `origin.result_sha256`.
- `row_sha256`: SHA-256 of the seven-field JSON object, UTF-8 encoded with sorted
  keys, `ensure_ascii=True` and separators `(',', ':')`, without a trailing newline.
- `solutions`: all compatible evaluated RDF bindings, deterministically sorted,
  each with its SELECT-bag `multiplicity` and separate local and remote support.

The sum of solution multiplicities in a group equals its number of original row
indices. Language/datatype alternatives can produce indistinguishable scalar rows.
Every such row position refers to the whole compatible solution group: the report
does not invent which language occupied an indistinguishable historical position.
Review multiplicity and duplicate raw responses never multiply SELECT rows.

RDF terms retain `type`, `value`, and recorded `datatype` or `xml:lang` metadata.
Evaluated language tags use lowercase canonical spelling, following their
case-insensitive RDF identity; raw remote records retain the original spelling.
IRIs are compared in full, without HTTP/HTTPS, percent-encoding or label aliases.
Each solution's `local.assertions` explicitly records document type, about, subject
and source, and concept type and preferred label. `local.mappings` records the
asserted local exact/close predicate and **all** complete review statements matching
the full subject/predicate/object triple. Each review retains its original statement
IRI and its type, subject, predicate, object, review source, rationale and typed date.
Document source, review source and capture observation time have distinct roles.
A same-concept review of a direct OBO target cannot support the Wikidata edge.

`remote_mapping` and `remote_label` keep a materialized assertion plus every raw
occurrence. Occurrences include graph, capture index, query/response filenames and
hashes, zero-based binding index, JSON pointer and the original raw `s/p/o` SPARQL
JSON term records. `materialized` and `lexical_or_metadata_changed` expose parser
changes: raw integer lexical `01` can remain `01` while the old materializer uses
`1`. These are not claimed to be `sameTerm`. Duplicate raw bindings retain every
index while the RDF graph still contains one materialized triple. Local lexical
fidelity is checked before projection; unsupported normalization is rejected rather
than reconstructed from `str()`.

## Verification and limits

The orchestration in `src/daf_okn/analysis/join_explanation.py` reuses the existing
manifest, safe-file, query, stage-inventory, graph restriction and join evaluation
validators in `src/daf_okn/analysis/cross_graph.py`. It compares recomputed JSON
**and** Markdown to captured bytes before producing support. It also applies full
`validate_rdf_semantics` from `src/daf_okn/core/rdf.py`: missing, incomplete, orphan,
multi-valued or conflicting local review records fail even if the older join alone
can display a row. Multiple complete statements for one asserted triple are valid.
The pure projection and serialization live in `src/daf_okn/core/join_evidence.py`.

The first profile requires IRI review statement identifiers and rejects all local
blank nodes; it never skolemizes them. Existing remote capture validation already
rejects blank-node response terms. Local literals whose lexical value changes under
the established parser are unsupported. Canonical local labels, rationales and
dates are the supported case. This is a profile limit, not a change to RDF standards
or existing replay admission.

Bound input files total at most 32 MiB, with existing per-artifact limits also
enforced. The complete generated payload totals at most 32 MiB. The projection
supports at most 10,000 SELECT rows and 50,000 raw occurrences. Symlink ancestors,
aliased inputs, existing outputs, escaping destinations and output overlapping
input trees are rejected. Inputs are rechecked byte-for-byte after derivation;
complete staged output is published only after verification succeeds.

`deprecation_replacement` is explicitly `not_captured`, and `curation_decisions` is
`not_supplied`. There is no status acquisition, deferral parser, cognitive exporter
import or RDF reasoning. Label absence does not establish active status. An
assertion path adds no composed concept-to-OBO mapping, resource identity, class
equivalence, membership, remote review, authenticated authorship, or scientific or
human validation. Hash consistency does not authenticate an unsigned capture
manifest or establish that an endpoint remains unchanged.

See [cross-graph joins](cross-graph.md), [custody and replay](custody-and-replay.md)
and [the entity model](entity-model.md) for the existing capture contract.
