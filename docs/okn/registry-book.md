# OKN Book: "Building a Knowledge Graph" — Digest

> **Attribution and status.** This file summarises content from [okn.us](https://okn.us/), [registry.okn.us](https://registry.okn.us/) and [github.com/frink-okn/okn-registry](https://github.com/frink-okn/okn-registry), captured on 2026-09-25. It is an unofficial digest, is not endorsed by the Open Knowledge Network, FRINK or RENCI, and may be out of date. Quoted passages remain the work of their original authors; the registry site and repository are the authoritative sources, including for contact details and licence terms.


> Captured 2026-09-25 from the OKN registry site (https://registry.okn.us) and its mkdocs
> site-source repo (https://github.com/frink-okn/okn-registry, `main` branch as of 2026-09-25).
> Live pages matched the repo markdown on capture; repo markdown is treated as the authoritative
> site source where noted.

The "book" is the registry site's guidance section at https://registry.okn.us/book/. Its live
navigation (per `mkdocs.yml` in the site source repo) is:

- Overview: https://registry.okn.us/book/
- Graph Construction Best Practices: https://registry.okn.us/book/best-practices/
- About External Identifiers: https://registry.okn.us/book/identifiers/
- Identifier Choices:
  - Biomedical: https://registry.okn.us/book/biomedical-identifiers/
  - Environmental: https://registry.okn.us/book/environmental-identifiers/
  - Geospatial: https://registry.okn.us/book/geospatial-identifiers/
  - Institutions: https://registry.okn.us/book/institutions/
  - Justice: https://registry.okn.us/book/justice/
- Ingesting Identifier Sources: https://registry.okn.us/book/new-id-sources/

Note: the book index page (https://registry.okn.us/book/, site source
https://github.com/frink-okn/okn-registry/blob/main/docs/book/index.md) only lists four links
(best practices, external identifiers, biomedical identifiers, new identifier sources); the five
"Identifier Choices" domain pages are reachable through the site navigation.

---

## 1. Overview — what the book covers

From https://registry.okn.us/book/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/index.md):

> "This section holds informational guidance on adding and managing graphs and graph data
> within the OKN."

Contents: graph construction best practices (external guideline documents), background on
external identifiers in RDF, per-domain preferred-identifier guidance (biomedical,
environmental, geospatial, institutions, justice), and rules for ingesting new sources of
identifiers into the Fabric.

---

## 2. Graph construction best practices

From https://registry.okn.us/book/best-practices/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/best-practices.md).

This page is itself a link index — it publishes no detailed rules of its own beyond its framing
text. Verbatim framing:

> "Here are links to documents developed in collaboration with EduGate (Theme 3) and Fabric
> (Theme 2) to support Theme 1 groups in enhancing the integrity of knowledge graphs and
> advancing their interoperability."

> "If you would like to discuss these documents, ask questions, or suggest new topics that
> should be addressed, please visit us on the #kg-development-qa channel in the OKN Slack."

Linked documents (URLs verbatim):

| Topic | URL |
| --- | --- |
| Relations, Classes | https://kastle-lab.github.io/education-gateway/resource-pages/graph-construction-guidelines-part2.html |
| Identifiers, Documentation, Axioms, RDF Validation | https://kastle-lab.github.io/education-gateway/resource-pages/graph-construction-guidelines.html |
| Geospatial information | https://docs.google.com/document/d/1wy8qXeMNTnT9PtxmMJHN2Ee-sih08LfXcqrvWsK2ZCQ/edit |

Modeling guidance proper (relations, classes, axioms, validation) therefore lives in the KASTLE
EduGate documents linked above, not in the registry book itself. That is the extent of what the
sources cover; the linked documents' contents are outside the scraped material.

---

## 3. About external identifiers

From https://registry.okn.us/book/identifiers/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/identifiers.md).

### Definition

> "An external identifier (hereinafter referred to as an 'identifier') is a string that
> represents a particular concept within a particular vocabulary or ontology."

> "Identifiers are designed to be unambiguous with respect to the vocabulary in which they are
> defined, and are preferably detached from any natural language name for the concept they
> represent."

Example: in KnowWhereGraph, "Lancaster County, Pennsylvania" is represented by the string
`administrativeRegion.USA.42071` — none of the words 'Lancaster', 'County', or 'Pennsylvania'
appear in the string.

### Using identifiers in RDF

Two representation options:

1. **In the IRI.** Most external vocabularies have an IRI scheme within which an identifier
   yields a canonical reference. E.g. in KnowWhereGraph, prefixing an identifier with
   `http://stko-kwg.geog.ucsb.edu/lod/resource/` produces a standard reference usable as the
   subject of further triples.
2. **As a string via a dedicated predicate.** Some vocabularies reference identifiers of other
   vocabularies this way. Example (subject/predicate/object separated by `⸻` for clarity):

   ```
   <http://purl.obolibrary.org/obo/NCIT_C14202> ⸻ <http://purl.obolibrary.org/obo/NCIT_P331> ⸻ "7215"
   ```

   where the predicate (NCIT P331) indicates the object is an NCBI taxon ID, linking the NCIt
   'Drosophila' entity to that genus's NCBI taxon entry.

### Correspondences between vocabularies

Because different vocabularies may define the same concepts, it is "helpful to have
correspondences, however indirect, between IRIs." One way is a
[SKOS mapping property](https://www.w3.org/TR/skos-reference/#mapping):

```
<http://purl.obolibrary.org/obo/NCIT_C14202> ⸻ <http://www.w3.org/2004/02/skos/core#exactMatch> ⸻ <http://purl.uniprot.org/taxonomy/7215>
<http://purl.uniprot.org/taxonomy/7215> ⸻ <http://www.w3.org/2004/02/skos/core#exactMatch> ⸻ <http://www.wikidata.org/entity/Q312154>
```

### Identifiers in the OKN

> "It is preferred throughout the OKN that entities be referred to using IRIs that encode
> different identifiers" — i.e., the IRI-embedding representation. Lancaster, Pennsylvania
> should be referred to as
> `<http://stko-kwg.geog.ucsb.edu/lod/resource/statisticalArea.29540>` rather than an arbitrary
> IRI merely connected to that identifier string.

Starting points for linkages: the OKN Fabric provides **Wikidata's data** and the **Ubergraph**,
which contain concept definitions using different identifier schemes in their IRIs. For
Lancaster County, PA:

- NCIt (via Ubergraph): `<http://purl.obolibrary.org/obo/NCIT_C109967>` ("C109967" is the NCIt ID)
- Wikidata: `<http://www.wikidata.org/entity/Q142369>` ("Q142369" is the Wikidata item ID)
- The **'Identifier Mappings'** component graph (registry entry:
  https://registry.okn.us/registry/kgs/identifier-mappings) provides SKOS exact-match pairings
  between identifier IRIs and Wikidata items, allowing conversion between some identifier
  schemes through Wikidata.

Per-domain identifier preferences are in the Identifier Choices pages digested below.

---

## 4. Identifier Choices — biomedical

From https://registry.okn.us/book/biomedical-identifiers/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/biomedical-identifiers.md).
These guidelines were informed by:

- the [availability of such identifiers](https://prop-explorer.toolforge.org/) on Wikidata;
- the ontologies used in the Common Fund Data Ecosystem's
  [Crosscut Metadata Model (C2M2)](https://data.cfde.cloud/documentation/C2M2); and
- the prefixes preferred in the
  [Biolink Model](https://biolink.github.io/biolink-model/) — specifically the valid ID prefixes
  listed for [AnatomicalEntity](https://biolink.github.io/biolink-model/AnatomicalEntity/#valid-id-prefixes),
  [ChemicalEntity](https://biolink.github.io/biolink-model/ChemicalEntity/#valid-id-prefixes),
  [MolecularEntity](https://biolink.github.io/biolink-model/MolecularEntity/#valid-id-prefixes),
  and [NucleicAcidEntity](https://biolink.github.io/biolink-model/NucleicAcidEntity/#valid-id-prefixes).

Convention: "Each ID listed below is followed by a IRI format that references to entities
through that ID should use (that is, by substituting '$1' with the ID in question) as well as
RDF predicates that would be used to link an entity to its identifier string."

### Converting to preferred identifiers

RENCI provides a [node normalizer](https://nodenormalization-sri.renci.org/docs#/) that "may be
used to convert data using non-preferred identifiers to preferred ones if they exist." If its
output is unsatisfactory, a mapping may be achievable through identifiers present on Wikidata —
contact Mahir (RENCI; see the registry for contact details) for help.

### Identifiers with broad scopes

"These are identifiers that can refer to a wide variety of classes. While their use is
dispreferred for those entity classes listed underneath this section, their use may still be
tolerated for entity types falling outside of those classes."

| Identifier | Wikidata property | Example IRI | Wikidata coverage noted |
| --- | --- | --- | --- |
| Wikidata item IDs (Qids) | — | http://www.wikidata.org/entity/Q42 | — |
| [UMLS CUIs](https://evsexplore.semantics.cancer.gov/evsexplore/welcome?terminology=ncim) | [wdt:P2892](http://www.wikidata.org/prop/direct/P2892) | https://identifiers.org/umls:C0037379 | ~740k mapped |
| [NCIt IDs](https://www.ebi.ac.uk/ols4/ontologies/ncit) | [wdt:P1748](http://www.wikidata.org/prop/direct/P1748) | http://purl.obolibrary.org/obo/NCIT_C20047 | ~12k of 200k mapped |
| [MeSH concepts](https://id.nlm.nih.gov/mesh/) | [wdt:P6694](http://www.wikidata.org/prop/direct/P6694) | http://id.nlm.nih.gov/mesh/M0000115 | ~1.2k of ~450k mapped |
| [MeSH tree codes](https://meshb-prev.nlm.nih.gov/treeView) | [wdt:P672](http://www.wikidata.org/prop/direct/P672) | — | ~65k mapped |

### Relationship predicates

> "In general, if a relationship is indicated by a predicate in the
> [Biolink Model](https://biolink.github.io/biolink-model/predicates.html), that version of the
> predicate should be used to indicate that relationship (with the IRI prefix
> https://w3id.org/biolink/vocab/)."

Biolink provides mappings from many Biolink predicates to other ontologies, both
[in the main model definition (biolink-model.yaml)](https://github.com/biolink/biolink-model/blob/master/biolink-model.yaml)
and [in dedicated files (predicate_mapping.yaml)](https://github.com/biolink/biolink-model/blob/master/predicate_mapping.yaml).
The page reproduces (in a ~250-row table) the exact and close mappings; if a predicate is not
in the table, "Biolink does not provide a mapping for it."

Prefix definitions used in that mapping table (verbatim):

| Prefix | Expansion |
| --- | --- |
| BFO | http://purl.obolibrary.org/obo/BFO_ |
| CHEMBL.MECHANISM | https://www.ebi.ac.uk/chembl/mechanism/inspect/ |
| CTD | http://ctdbase.org/ |
| DGIdb | https://www.dgidb.org/interaction_types |
| ExO | http://purl.obolibrary.org/obo/ExO_ |
| GAMMA | http://translator.renci.org/GAMMA_ |
| GOREL | http://purl.obolibrary.org/obo/GOREL_ |
| GTEx | https://www.gtexportal.org/home/gene/ |
| IAO | http://purl.obolibrary.org/obo/IAO_ |
| RO | http://purl.obolibrary.org/obo/RO_ |
| SEMMEDDB | https://skr3.nlm.nih.gov/SemMedDB |
| SIO | http://semanticscience.org/resource/SIO_ |
| SO | http://purl.obolibrary.org/obo/SO_ |
| wdt | http://www.wikidata.org/prop/direct/ |

Sample rows from the table (Biolink predicate → exact mappings → close mappings; the full table
is at the source page):

| BioLink | exact mappings | close mappings |
| --- | --- | --- |
| active in | RO:0002432 | |
| affects | SEMMEDDB:AFFECTS; DGIdb:affects | |
| affects expression of | CTD:affects_expression_of | GTEx:affects_expression_in |
| author | dct:creator; wdt:P50 | |
| causes | SEMMEDDB:CAUSES; wdt:P1542; SNOMED:cause_of; RO:0003303 | |
| decreases abundance of | CTD:decreases_abundance_of | |
| entity negatively regulates entity | RO:0002212; RO:0002449 | |
| exact match | skos:exactMatch; WIKIDATA:P2888 | |
| has gene product | RO:0002205; wdt:P688; NCIT:gene_encodes_gene_product | PR:has_gene_template |
| in taxon | RO:0002162; wdt:P703 | |
| increases activity of | CTD:increases_activity_of; CHEMBL.MECHANISM:opener; CHEMBL.MECHANISM:positive_modulator; CHEMBL.MECHANISM:releasing_agent; DGIdb:activator; DGIdb:agonist | |
| latitude | wgs:lat | |
| longitude | wgs:long | |
| part of | BFO:0000050; SEMMEDDB:PART_OF; wdt:P361; FMA:part_of; RXNORM:constitutes; RXNORM:part_of | |
| same as | owl:sameAs; skos:exactMatch; wdt:P2888; CHEMBL.MECHANISM:equivalent_to; MONDO:equivalentTo | owl:equivalentClass |
| subclass of | rdfs:subClassOf; SEMMEDDB:ISA; wdt:P279; CHEMBL.MECHANISM:subset_of; GO:isa; MESH:isa; RXNORM:isa; VANDF:isa | LOINC:class_of; LOINC:has_class |
| treats | DRUGBANK:treats; wdt:P2175 | |

(The table also covers predicates such as: binds, catalyzes/enables, colocalizes with,
correlated with, develops from, diagnoses, disrupts, genetically interacts with, has part,
has phenotype, interacts with, located in, manifestation of, mechanism of action, mentions,
negatively/positively correlated with, occurs in, orthologous/paralogous/xenologous to,
preceded by/precedes, produces, published in, publisher, regulates, transcribed from/to,
translates to, variant-of relations (frameshift SO:0001589, missense SO:0001583, splice site
SO:0001629, synonymous SO:0001819), z score, etc. Consult the source page for the complete
mapping.)

### Entity classes (preferred identifiers)

| Entity class | Preferred identifier | IRI format (`$1` = ID) | Wikidata prop | Coverage notes |
| --- | --- | --- | --- | --- |
| Anatomical entities | [UBERON IDs](https://obophenotype.github.io/uberon/) | http://purl.obolibrary.org/obo/UBERON_$1 | [wdt:P1554](http://www.wikidata.org/prop/direct/P1554) | "no harm in adding remainder to Wikidata if not already present"; cf. [FMA IDs](https://www.ebi.ac.uk/ols4/ontologies/fma) (~79k of ~104k mapped) |
| Chemical entities (compounds, substances) | [PubChem CIDs](https://pubchem.ncbi.nlm.nih.gov/) | http://rdf.ncbi.nlm.nih.gov/pubchem/compound/CID$1 | [wdt:P662](http://www.wikidata.org/prop/direct/P662) | "CAS registry numbers are imprecise (per Tom Luechtefeld)"; BioBricks/SPOKE standardizing on PubChem CIDs already; 1.3m of ~111m mapped — "we may need to federate with other external sources" |
| Data types / file formats | [EDAM IDs](https://edamontology.org/page) | — (no Wikidata property; "must map from Wikidata item to RDF URL using [identifier mappings](https://apps.okn.us/ldf/identifier-mappings)") | — | Only 44 mapped; "no harm in adding remainder to Wikidata" |
| Diseases | [Monarch Disease Ontology (MONDO) IDs](https://github.com/monarch-initiative/mondo) | http://purl.obolibrary.org/obo/MONDO_$1 | [wdt:P5270](http://www.wikidata.org/prop/direct/P5270) | Disclaimer: some Fabric team members have been part of MONDO's development; 19k of ≥26k mapped; cf. [DOID IDs](https://www.ebi.ac.uk/ols4/ontologies/doid) (all(?) mapped) |
| Genes | [Entrez gene IDs](https://www.ncbi.nlm.nih.gov/gene/) | http://purl.uniprot.org/geneid/$1 | [wdt:P351](http://www.wikidata.org/prop/direct/P351) | 794k mapped; "we may need to federate with other external sources" |
| Phenotypes | [HPO IDs](https://hpo.jax.org/) | http://purl.obolibrary.org/obo/HP_$1 | [wdt:P3841](http://www.wikidata.org/prop/direct/P3841) | ~2k of 20k+ mapped; "no harm in adding remainder to Wikidata" |
| Proteins | [UniProt protein IDs](https://www.uniprot.org/uniprotkb/) | http://purl.uniprot.org/uniprot/$1 | [wdt:P352](http://www.wikidata.org/prop/direct/P352) | 627 of ≥8.2m mapped; "we may need to federate with other external sources" |
| Publications (references) | [DOIs](https://doi.org) — "if present" | http://dx.doi.org/$1 | [wdt:P356](http://www.wikidata.org/prop/direct/P356) | "[PubMed IDs](https://pubmed.ncbi.nlm.nih.gov) ([wdt:P698](http://www.wikidata.org/prop/direct/P698)) and [PMCIDs](https://www.ncbi.nlm.nih.gov/pmc/) ([wdt:P932](http://www.wikidata.org/prop/direct/P932)) may be allowed if no DOI exists" |
| Taxa | [NCBI taxa IDs](https://www.ebi.ac.uk/ols4/ontologies/ncbitaxon) | http://purl.obolibrary.org/obo/NCBITaxon_$1 | [wdt:P685](http://www.wikidata.org/prop/direct/P685) | 600k of 2.7m mapped; Mahir (RENCI; see the registry for contact details) "could try to map the remainder automatically (is already planning this with elurikkus.ee)" |

(The UBERON row in the source carries an apparent typo — "~6000k IDs (out of at least 16k)
mapped to Wikidata" — reproduced as written in the source.)

---

## 5. Identifier Choices — environmental

From https://registry.okn.us/book/environmental-identifiers/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/environmental-identifiers.md).

Short page; it points readers to the biomedical and geospatial identifier pages ("though some
sections of the former are also reproduced below") and lists two entity classes:

| Entity class | Preferred identifier | IRI format | Wikidata prop | Coverage notes |
| --- | --- | --- | --- | --- |
| Chemical entities (compounds, substances) | [PubChem CIDs](https://pubchem.ncbi.nlm.nih.gov/) | http://rdf.ncbi.nlm.nih.gov/pubchem/compound/CID$1 | [wdt:P662](http://www.wikidata.org/prop/direct/P662) | "CAS registry numbers are imprecise (per Tom Luechtefeld)"; BioBricks/SPOKE standardizing on PubChem CIDs already; 1.3m of ~111m mapped — "we may need to federate with other external sources" |
| Taxa | [NCBI taxa IDs](https://www.ebi.ac.uk/ols4/ontologies/ncbitaxon) | http://purl.obolibrary.org/obo/NCBITaxon_$1 | [wdt:P685](http://www.wikidata.org/prop/direct/P685) | 600k of 2.7m mapped; Mahir (RENCI; see the registry for contact details) "could try to map the remainder automatically (is already planning this with elurikkus.ee)" |

No EPA, USGS, or other environmental-agency identifiers are listed on this page.

---

## 6. Identifier Choices — geospatial

From https://registry.okn.us/book/geospatial-identifiers/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/geospatial-identifiers.md).

Framing: "References to locations occur across many graphs in the Proto-OKN, whether as areas
that certain species abound in, as points where companies are headquartered, or as jurisdictions
within which incidents take place. Regardless of the particular use case one has for locations,
it is very important that they be referred to consistently across graphs."

Recommendations are "intended to be consistent with existing
[geospatial recommendations](https://docs.google.com/document/d/1wy8qXeMNTnT9PtxmMJHN2Ee-sih08LfXcqrvWsK2ZCQ/edit)."
Each gives at minimum an IRI format (`$1` replaced by the identifying string) and an example.
"Many of the entries below refer to KnowWhereGraph, which the Proto-OKN is in the process of
incorporating sufficient geospatial components of."

### Google Data Commons warnings (prescriptive, verbatim)

- "Do not use it for an entity that is also defined in KnowWhereGraph."
  - Example: use `http://stko-kwg.geog.ucsb.edu/lod/resource/administrativeRegion.USA.23` to
    refer to Maine instead of `https://datacommons.org/browser/geoId/23`
- "Do not use it if the IRI for it contains 'wikidataId': use http://www.wikidata.org/entity/
  as the prefix to the Wikidata ID used in that IRI instead."
  - Example: use `http://www.wikidata.org/entity/Q203122` to refer to Whistler, British
    Columbia (if the need arises) instead of
    `https://datacommons.org/place/wikidataId/Q203122`
- "Do not use a relationship type defined in Data Commons if it exists somewhere else."
  - Example: use `http://stko-kwg.geog.ucsb.edu/lod/ontology/sfWithin` to link places to the
    other places they're contained in instead of
    `https://datacommons.org/browser/containedInPlace`

### Entity classes

| Entity class | Source | IRI format | Example |
| --- | --- | --- | --- |
| U.S. states | KnowWhereGraph | http://stko-kwg.geog.ucsb.edu/lod/resource/administrativeRegion.USA.$1 | California = http://stko-kwg.geog.ucsb.edu/lod/resource/administrativeRegion.USA.06 |
| U.S. cities | KnowWhereGraph/GNIS-LD | http://gnis-ld.org/lod/gnis/feature/$1 | Fontana = http://gnis-ld.org/lod/gnis/feature/2410517 |
| U.S. ZIP code regions | KnowWhereGraph | http://stko-kwg.geog.ucsb.edu/lod/resource/zipCodeArea.$1 | 04419 = http://stko-kwg.geog.ucsb.edu/lod/resource/zipCodeArea.04419 |
| U.S. census tracts | Data Commons | https://datacommons.org/browser/geoId/$1 | Census Tract 110, Penobscot County, Maine = https://datacommons.org/browser/geoId/23019011000 |
| U.S. census tract block groups | Data Commons | https://datacommons.org/browser/geoId/$1 | Block Group 1, Census Tract 110, Penobscot County, Maine = https://datacommons.org/browser/geoId/230190110001 |

(GNIS = Geographic Names Information System, appearing here via the GNIS-LD IRI scheme
`http://gnis-ld.org/lod/gnis/feature/`; the page cites no USGS registry URL beyond this.)

---

## 7. Identifier Choices — institutions

From https://registry.okn.us/book/institutions/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/institutions.md).

> "This page lists recommendations of identifiers to use for legal entities (corporate bodies,
> non-profit organizations, etc.). It is likely that these will evolve and will apply most
> leniently since, unlike with some of the other domains within the Proto-OKN, there is not one
> particular identifier which is clearly more appropriate than the others for identifying even
> organizations within a particular subdomain."

Recommendations are given either as IRI format + example, or as triple examples
(subject ⸻ predicate ⸻ object, Wikidata statements).

### Product categories

"There is in general no need for all categories of products to prefer a particular IRI format
over others, given how diverse products are in the first place." Some UN identifiers that could
be attached via predicates:

| Identifier | Predicate | Example triple | Mapped to Wikidata |
| --- | --- | --- | --- |
| Standard Products and Services Code (UNSPSC) | http://www.wikidata.org/prop/direct/P2167 | `<http://www.wikidata.org/entity/Q180481>` ⸻ P2167 ⸻ `"25101703"` | ~1.5k IDs |
| Central Product Classification (UN) | http://www.wikidata.org/prop/direct/P11373 | `<http://www.wikidata.org/entity/Q334637>` ⸻ P11373 ⸻ `"35322"` | 170 IDs |
| Harmonized System Code (2022) (UN/WCO) | http://www.wikidata.org/prop/direct/P5471 | `<http://www.wikidata.org/entity/Q174320>` ⸻ P5471 ⸻ `"903020"` | 156 IDs |

Among those not introduced by the United Nations:

| Identifier | Predicate | Example triple | Mapped to Wikidata |
| --- | --- | --- | --- |
| GS1 Global Product Classification | http://www.wikidata.org/prop/direct/P8957 | `<http://www.wikidata.org/entity/Q722338>` ⸻ P8957 ⸻ `"10000273"` | 423 IDs |

### Businesses

"The following identifiers for businesses do not have RDF-compatible IRIs known to the Fabric,
and must be attached to entities using particular predicates":

| Identifier | Predicate | Example triple | Notes |
| --- | --- | --- | --- |
| ISNI | http://www.wikidata.org/prop/direct/P213 | `<http://www.wikidata.org/entity/Q19861084>` ⸻ P213 ⸻ `"0000000446638501"` | ISO 27729-defined standard; 2.4 million IDs mapped to Wikidata |
| PermID | http://www.wikidata.org/prop/direct/P3347 | `<http://www.wikidata.org/entity/Q1022711>` ⸻ P3347 ⸻ `"4295905828"` | ~6k IDs mapped |
| D-U-N-S | http://www.wikidata.org/prop/direct/P2771 | `<http://www.wikidata.org/entity/Q19861084>` ⸻ P2771 ⸻ `"968806054"` | 491 IDs mapped |
| CAGE | http://www.wikidata.org/prop/direct/P5574 | `<http://www.wikidata.org/entity/Q19861084>` ⸻ P5574 ⸻ `"6MHA5"` | 255 IDs mapped |

One business identifier *can* form an IRI:

| Identifier | IRI format | Example | Notes |
| --- | --- | --- | --- |
| Legal Entity Code (LEI) | https://rdf.gleif.org/L1/L-$1 | ORCID, Inc. = https://rdf.gleif.org/L1/L-875500AZPSXM0HP6VP03 | ISO 17442-defined standard; 53k IDs mapped to Wikidata |

Note: no ORCID-style identifier scheme is prescribed for *people* anywhere in this book;
ORCID appears only as the example company in the LEI example.

---

## 8. Identifier Choices — justice

From https://registry.okn.us/book/justice/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/justice.md).

Points to the institutions page as also worth consulting.

### NIEM standards

> "There is a growing consensus to use [NIEM Open](https://niemopen.org/) predicates for
> representing different types of entities in the justice space."

Current graphs use, in addition to the
[core model](https://github.com/niemopen/niem-model) **version 5.0**, the
[Justice XML Data Model](https://niemopen.org/community/justice/) **version 7.3** and
[OmniClass Construction Specifications](https://github.com/niemopen/niem-model/blob/main/xsd/codes/occs.xsd)
**version 5.0**.

> "The Proto-OKN will seek to ensure a correspondence between entity types and relationships
> defined in NIEM and existing RDF entities and relationships where possible."

### Entity classes

| Entity class | Source | IRI format | Example |
| --- | --- | --- | --- |
| U.S. judicial circuits | KnowWhereGraph | http://stko-kwg.geog.ucsb.edu/lod/resource/circuit.$1 | Ninth Circuit = http://stko-kwg.geog.ucsb.edu/lod/resource/circuit.9 |
| U.S. judicial districts | KnowWhereGraph | http://stko-kwg.geog.ucsb.edu/lod/resource/federalJudicialDistrict.$1 | Northern District of Iowa = http://stko-kwg.geog.ucsb.edu/lod/resource/federalJudicialDistrict.89 |

Both rows say "See also the page on geospatial identifiers."

---

## 9. Ingesting new sources of identifiers

From https://registry.okn.us/book/new-id-sources/ (site source repo:
https://github.com/frink-okn/okn-registry/blob/main/docs/book/new-id-sources.md).

Scope: "These guidelines are relevant for graphs that are considering including, as part of
their own graph data, the entirety or a significant subset of another external knowledge graph."
There is no step-by-step procedure; the page is a set of five requirements/rules:

1. **Reasonable sizes.** "If an external database is of a reasonable size, the Fabric may
   ingest it if your graph requires it. A 'reasonable size' is one that does not cause the
   external database to form the plurality of triples in the OKN. UniProt and SemOpenAlex are
   great examples of databases of an unreasonable size."

2. **Text metadata (labels, descriptions).** "Graphs should not try to reproduce the
   labels/descriptions of entities from external sources." Duplicate triples are simply merged
   in the Fabric Federated SPARQL endpoint, but reproduction "can cause consistency issues when
   federating between graphs." Graphs may attach auxiliary information — e.g. the five SKOS
   note predicates [whose names end with 'note'](https://www.w3.org/TR/skos-reference/#notes) —
   to such entities to clarify their use in those graphs; "such notes must make clear to which
   graph they apply."

3. **Re-expression of existing relationships.** "Graphs should not publish *as part of their
   graphs* triple data that is simply re-expressed from another external knowledge graph (e.g.
   using different equivalent classes, predicates, or string value representations)." If
   re-expression is desirable, either provide it to the Fabric as a separate data store from
   the rest of the graph, or describe to the Fabric what needs to happen so the Fabric can
   perform the re-expression themselves. Exception: Wikidata information "may" be re-expressed
   (e.g. surfacing entity types as
   [rdf:type](http://www.w3.org/1999/02/22-rdf-syntax-ns#type) in addition to
   [wdt:P31](http://www.wikidata.org/prop/direct/P31)) "so long as the Fabric are notified in
   advance of these re-expressions."

4. **Redefinition of existing entities.** "Graphs should not try to redefine an external entity
   *using the URI for that entity* if there is no particularly compelling reason to do so."
   The Fabric expects the same entity appearing in multiple graphs to be referred to in much
   the same way, per the set-forth best practices, "for cross-graph consistency, clarity, and
   query performance." If the Fabric allows redefinition of a class of entities, those entities
   must: (a) all use a **novel IRI prefix**; (b) have the circumstances of the redefinition
   [documented in the graph itself](https://github.com/frink-okn/graph-descriptions/blob/main/README.md);
   and (c) all be mapped to their external equivalents using one of the **SKOS mapping
   relations**.

5. **Supplementation of existing entities.** "Graphs may ascribe *new information* to external
   entities if such information is not present elsewhere, either in the external source of
   those entities or in other OKN graphs."

---

## Quick reference: identifiers recommended across the whole book

| Domain | Identifier | IRI format | Wikidata prop |
| --- | --- | --- | --- |
| Biomedical — anatomical | UBERON | http://purl.obolibrary.org/obo/UBERON_$1 | P1554 |
| Biomedical — chemicals (also environmental) | PubChem CID | http://rdf.ncbi.nlm.nih.gov/pubchem/compound/CID$1 | P662 |
| Biomedical — data formats | EDAM | — (via identifier mappings) | — |
| Biomedical — diseases | MONDO | http://purl.obolibrary.org/obo/MONDO_$1 | P5270 |
| Biomedical — genes | Entrez gene | http://purl.uniprot.org/geneid/$1 | P351 |
| Biomedical — phenotypes | HPO | http://purl.obolibrary.org/obo/HP_$1 | P3841 |
| Biomedical — proteins | UniProt | http://purl.uniprot.org/uniprot/$1 | P352 |
| Biomedical — publications | DOI (alt: PubMed/PMCID) | http://dx.doi.org/$1 | P356 (P698 / P932) |
| Biomedical/environmental — taxa | NCBI taxon | http://purl.obolibrary.org/obo/NCBITaxon_$1 | P685 |
| Biomedical broad-scope | UMLS CUI / NCIt / MeSH concept / MeSH tree code / Wikidata Qid | e.g. https://identifiers.org/umls:C0037379 ; http://purl.obolibrary.org/obo/NCIT_C20047 ; http://id.nlm.nih.gov/mesh/M0000115 | P2892 / P1748 / P6694 / P672 |
| Geospatial — U.S. states | KnowWhereGraph | http://stko-kwg.geog.ucsb.edu/lod/resource/administrativeRegion.USA.$1 | — |
| Geospatial — U.S. cities | GNIS-LD | http://gnis-ld.org/lod/gnis/feature/$1 | — |
| Geospatial — ZIP codes | KnowWhereGraph | http://stko-kwg.geog.ucsb.edu/lod/resource/zipCodeArea.$1 | — |
| Geospatial — census tracts / block groups | Data Commons | https://datacommons.org/browser/geoId/$1 | — |
| Institutions — product categories | UNSPSC / CPC / HS 2022 / GS1 GP | statement triples only | P2167 / P11373 / P5471 / P8957 |
| Institutions — businesses | ISNI / PermID / D-U-N-S / CAGE | statement triples only | P213 / P3347 / P2771 / P5574 |
| Institutions — businesses | Legal Entity Code (LEI) | https://rdf.gleif.org/L1/L-$1 | — |
| Justice — circuits / districts | KnowWhereGraph | http://stko-kwg.geog.ucsb.edu/lod/resource/circuit.$1 ; .../federalJudicialDistrict.$1 | — |
