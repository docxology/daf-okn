# Cognitive RDF interoperability review - 2026-10-20

For Mahir's review. Recommendations below concern meaning, not just successful joins. No exporter, graph, or evidence artifact was regenerated.

## Scope and observed frequencies

Canonical source: `../../../ActiveInferenceInstitute/Public/cognitive` from the daf-okn root, commit `109ff3928fe0b21c6a78a91d04db763d4f238fa1` (abbreviated **C** below). The sibling `../cognitive` is an older docxology fork. Export behavior is anchored to canonical HEAD: [C/code/scripts/export_rdf.py:130](https://github.com/ActiveInferenceInstitute/cognitive/blob/109ff3928fe0b21c6a78a91d04db763d4f238fa1/code/scripts/export_rdf.py#L130). Concurrent uncommitted exporter/alignment changes appeared in both repositories during inspection; they are excluded from this baseline.

The effective baseline mapping configuration is `STANDARD_RELATIONS` plus page frontmatter (`wikidata`, `doi`, `semantic_relations`), not a separate ontology section in the inspected root `config.yaml:1-94`. Canonical exporter lines 323-331 type non-navigation/non-redirect pages as both `schema:CreativeWork` and `skos:Concept`; lines 375-383 emit Wikidata `closeMatch` and DOI `schema:sameAs`. Daf-okn HEAD `46cfc2ea8c084e5592febcbd4a5fea3d55ce712d`, `src/daf_okn/core/rdf.py:80-90,218-264`, has analogous mappings, with different navigation classification. Its concurrent global BIBO draft is not canonical behavior.

Read-only scan of all 2,167 existing `knowledge_base/**/*.md` files on this date found 697 Wikidata-bearing pages. YAML tags were counted once per page, preserving spelling. Wiki targets were counted once per file across frontmatter/body, stripping alias text and anchors, without link resolution or code exclusion:

| Evidence | Actual document frequencies |
|---|---|
| Frequent tags | `active_inference` 138; `cognition` 112; `mathematics` 103; `learning` 98; `perception` 93 |
| Frequent raw concept-like targets | `active_inference` 251; `free_energy_principle` 215; `precision_weighting` 151; `predictive_processing` 113 |
| Review keywords | `model_fitting` 1; `computational_modeling` 2 |

These are source-document frequencies, not canonical node degrees; `active-inference` is a separate tag (76). Scan fingerprint: SHA-256 `24f975fdca1d924829c402d7cce41af1081dbfee244c5eb10d5c91cec9724bfd`, over sorted repository-relative paths, NUL, then file bytes, concatenated.

Separately, existing generated [C/docs/okn/statistics.md:15-26,87-142](https://github.com/ActiveInferenceInstitute/cognitive/blob/109ff3928fe0b21c6a78a91d04db763d4f238fa1/docs/okn/statistics.md#L87) records 2,097 concepts, 10,762 typed edges, and relation counts: `relates` 8,043; `foundation` 509; `implements` 461; `related` 442; `relates_to` 372; `extends` 154; `cited_by` 57; `part_of` 1. These are the committed export snapshot, not newly validated graph counts. Current raw frontmatter has zero `cites` or `depends_on` declarations. All 27 nonempty `cited_by` declarations are on citation pages; one additional declaration is empty. Do not infer existing topic-to-paper misuse.

## Mapping strength and referents

[SKOS section 10](https://www.w3.org/TR/skos-reference/#mapping) reserves `exactMatch` for concepts interchangeable across many retrieval contexts; `closeMatch` supports more limited interchangeability. Both are symmetric; only exact matching is transitive. Neither asserts OWL identity. Close matching is a substantive similarity assertion, not an uncertainty flag: omit wrong or unestablished topical matches. A local close match followed by a remote exact match does not justify promoting the local correspondence.

Separate the explanatory page, its topic concept, and any represented molecule, process occurrence, or publication. Prefer `page schema:about topic`; [schema:about](https://schema.org/about) expresses subject matter. A category such as cortisol is not a particular cortisol molecule; a publication discussing fitting is not a fitting activity. [OWL's classes/individuals distinction](https://www.w3.org/TR/owl2-primer/#Classes_and_Instances) makes `rdf:type` membership materially different from vocabulary alignment. Mapping an OWL class as a SKOS concept also requires an explicit metamodeling convention; do not silently treat class IRIs as specimen individuals.

## Concept decisions

**Cortisol.** [C/knowledge_base/biology/cortisol.md:2-20,25-34](https://github.com/ActiveInferenceInstitute/cognitive/blob/109ff3928fe0b21c6a78a91d04db763d4f238fa1/knowledge_base/biology/cortisol.md#L2) discusses the hormone and stress regulation, with alias `cortisol_system`. [ChEBI CHEBI:17650](https://www.ebi.ac.uk/chebi/CHEBI:17650) specifies the steroid's chemical structure and endocrine role. [NCI C2290](https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/C2290?include=full) is officially **Cortisol**, includes Hydrocortisone as a synonym, CAS 50-23-7, and explicitly cross-references CHEBI:17650. It is not solely a drug-product identifier. Both are defensible candidates for a hormone topic; recommend reviewed `closeMatch` initially, with chemical-scope clarification before any `exactMatch`. Do not map the broader HPA regulatory system to either or type the explanatory page as a chemical instance.

**Model fitting.** Its sole keyword occurrence is [C/knowledge_base/citations/smith_2022.md:15-20,48-57](https://github.com/ActiveInferenceInstitute/cognitive/blob/109ff3928fe0b21c6a78a91d04db763d4f238fa1/knowledge_base/citations/smith_2022.md#L15). [STATO:0000218](https://raw.githubusercontent.com/ISA-tools/stato/master/releases/latest_release/stato.owl) defines a data-transformation process evaluating whether a model represents data appropriately, including goodness of fit. It is not merely parameter estimation. Retain the publication keyword; if introducing a defined fitting topic, connect the publication through `schema:about`, then review that topic against STATO. Neither `rdf:type STATO:0000218` nor a fitting-topic equivalence belongs on the publication itself.

**Computational modeling.** [C/knowledge_base/research/computational_modeling.md:28-46](https://github.com/ActiveInferenceInstitute/cognitive/blob/109ff3928fe0b21c6a78a91d04db763d4f238fa1/knowledge_base/research/computational_modeling.md#L28) specifically covers executable Active Inference models, simulation, fitting, and comparison. [NCI C16461](https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/C16461?include=full), **Computer Modeling**, describes abstract mathematical modeling predicting system behavior from parameters/initial conditions; its NCI-GLOSS alternative concerns radiotherapy planning. Use the general NCI definition explicitly. Recommend `broadMatch` from this narrower Active Inference topic to C16461, subject to scope review, not exact equivalence. STATO fitting and computer modeling are distinct, related activities. Frequent Active Inference/free-energy/precision topics need their own definitions reviewed; frequency supplies priority, not equivalence evidence.

## Relation decisions

Baseline custom predicates are all subproperties of `skos:semanticRelation` (`C/code/scripts/export_rdf.py:454-467`), which entails concept endpoints. That blanket declaration also deserves review when separating pages from topics.

| Local relation | Conservative recommendation |
|---|---|
| `cited_by` | For verified publication A cited by publication B, use `A bibo:citedBy B`, equivalent in direction to `B bibo:cites A`. [BIBO](https://dcmi.github.io/bibo/) assigns Document domain/range and marks both properties unstable. Smith's frontmatter points toward the Parr book, but frontmatter does not verify its bibliography. If a future topic-to-paper declaration instead means discussion, use `paper schema:about topic`; do not globally replace it with BIBO. |
| `cites` / body links | Use BIBO only for actual document citations. Keep generic pointers as [dcterms:references](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#references). Zero current explicit `cites` declarations supplies no migration evidence. |
| `extends` | [CiTO extends](https://sparontologies.github.io/cito/current/cito.html#extends) means the citing entity develops ideas in the cited entity and entails `cito:cites`. Apply only to verified citation relationships. Source types are mixed, including concepts and implementations; retain local relations elsewhere pending interpretation. Do not equate extension with taxonomy. |
| `part_of` | Keep [dcterms:isPartOf](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#isPartOf) for physical/logical resource inclusion. Topic specialization instead needs reviewed SKOS hierarchy; class subsumption needs `rdfs:subClassOf`. |
| `related` variants | Use [skos:related](https://www.w3.org/TR/skos-reference/#semantic-relations) for associative concept links, respecting its symmetry and incompatibility with hierarchical reachability. Use `dcterms:relation` for loosely related pages/resources. |
| `depends_on` | No current declarations. [dcterms:requires](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#requires) fits a resource required for another's functioning/delivery/coherence; mathematical or causal dependence needs its own definition. |
| `implements` | [SIO_000233](https://raw.githubusercontent.com/MaastrichtU-IDS/semanticscience/master/ontology/sio.owl) relates an information entity to a specification it conforms to. It has no direct domain/range; ancestors `000011 -> 000001` inherit only entity (`000000`) domain/range. The narrower information-entity/specification requirement comes from prose. Use only for that verified pairing; concept pages pointing to theories are insufficient. |

## Limits

Official definitions were accessed on 2026-10-20. Web opening failed for NCI/OLS endpoints and the SIO term resolver; direct, in-memory urllib retrieval succeeded for NCI, EMBL-EBI OLS ChEBI/STATO, and official SIO/BIBO OWL. No bibliography truth, new federation deployment, or complete mapping inventory was established. Existing October 13 join evidence remains discovery evidence. Only this note was created; no tests were run because the authorized scope prohibited cache, environment, and output writes.
