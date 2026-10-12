# OKN Overview — the Open Knowledge Network per okn.us and registry.okn.us

> **Attribution and status.** This file summarises content from [okn.us](https://okn.us/), [registry.okn.us](https://registry.okn.us/) and [github.com/frink-okn/okn-registry](https://github.com/frink-okn/okn-registry), captured on 2026-09-25. It is an unofficial digest, is not endorsed by the Open Knowledge Network, FRINK or RENCI, and may be out of date. Quoted passages remain the work of their original authors; the registry site and repository are the authoritative sources, including for contact details and licence terms.


> Capture date: 2026-09-25. Sources: live pages of https://okn.us/ and https://registry.okn.us/ (scraped 2026-09-25) and the site source repo https://github.com/frink-okn/okn-registry (main branch as of 2026-09-25). Every fact below is quoted or paraphrased from those sources; anything not covered by them is marked `[NOT DOCUMENTED]`.

## 1. What the OKN is

From the registry's own definition (https://registry.okn.us/FRINK-index/ — site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/FRINK-index.md):

> "An *open knowledge network* is a publicly accessible system of interconnected data repositories and knowledge graphs, designed to support data-driven, AI-powered solutions to societal and economic challenges. *Knowledge graphs* facilitate the integration, structuring, and analysis of information across various scientific and technological domains."

The site home page (https://registry.okn.us/ — site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/index.md) phrases it as: "An open knowledge network is a publicly accessible, interconnected set of data repositories and associated knowledge graphs that will enable data-driven, artificial intelligence-based solutions for a broad set of societal and economic challenges."

### The Proto-OKN program

- The U.S. National Science Foundation (NSF), "in collaboration with five other U.S. government agencies, ... has invested $26.7 million in 18 projects through its Building the Prototype Open Knowledge Network (Proto-OKN program)" (https://registry.okn.us/FRINK-index/).
- Partner agencies: "NASA, NIH, the National Institute of Justice, NOAA and the U.S. Geological Survey are partnering with NSF on this effort and will work closely with the awardees to ensure that Proto-OKN supports each agency's data strategy while addressing use cases associated with agency data." An additional 15 U.S. federal and state agencies "have shown interest in collaborating with the 18 awardees" (https://registry.okn.us/, site source repo: docs/index.md).
- Program website: https://www.proto-okn.net/

### FRINK (Theme 1)

- FRINK = **Fabric Integrating Networked Knowledge**, one of the 18 Proto-OKN projects: "the Fabric Integrating Networked Knowledge (FRINK) focuses on synthesizing the independently developed graphs within Proto-OKN, enabling seamless deployment, integration, harmonization, and analysis of knowledge across these graphs" (https://registry.okn.us/FRINK-index/).
- "The FRINK project is supported by NSF ITE 2333810."
- The registry.okn.us website "serves as a resource for Theme 1 participants in the Proto-OKN program and provides information on FRINK's work for the broader public", including the Quick Start Guide, Best Practices guidance, and the OKN Registry of Theme 1 graphs.

### Governance / operators

The footer of every okn.us page reads: "Powered by **UNC Chapel Hill / RENCI** and **Onai Inc.** — NSF Award #2535091" (https://okn.us/, https://okn.us/crosswalks, https://okn.us/mcp). FRINK infrastructure items in the registry (e.g. the `okn-void` graph) also cite NSF award 2535091 (https://registry.okn.us/registry/kgs/okn-void/).

## 2. The surfaces (one line each)

| Surface | URL | What it is |
| --- | --- | --- |
| okn.us hub | https://okn.us/ | Public portal: "Query across 40+ interconnected knowledge graphs"; browse graphs, crosswalks, sample query library, and the MCP server. |
| Registry | https://registry.okn.us/ | "OKN registry — Knowledge graphs registered with the Open Knowledge Network"; detailed per-graph pages, kg-stats, and quick-start/best-practices docs for Theme 1 participants. |
| Apps / query service | https://apps.okn.us/ | "Proto-OKN SPARQL Query Service" — hosts the per-graph SPARQL endpoints (`https://apps.okn.us/{shortname}/sparql`) and TPF endpoints (`https://apps.okn.us/ldf/{shortname}`), plus Embeddings search at https://apps.okn.us/embeddings/ ("Frink Embeddings Query" over graph/node text features) and a federated endpoint `https://apps.okn.us/federation/sparql` (per https://github.com/sbl-sdsc/mcp-okn README). |
| Repository | https://repository.okn.us/ | The FRINK Landing zone / lakeFS service. Graph owners log in with Access Key/Secret Key and push graph files (S3-style: `LAKEFS_ENDPOINT=https://repository.okn.us/`) (https://registry.okn.us/help/setup/, site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/setup.md). The kg-stats intro says graph information "was obtained from an analysis of the graphs that were deposited in the FRINK Landing zone" (https://registry.okn.us/kg-stats/). |
| MCP server | https://okn.us/mcp | "MCP OKN Server" — a Model Context Protocol server letting AI assistants (Claude Desktop, ChatGPT, Claude Code, VS Code Copilot, Cursor) query the graphs in natural language; hosted endpoint **https://apps.okn.us/okn-mcp-dev/mcp** (legacy `https://apps.okn.us/okn-mcp/mcp` retained for a transition period). (https://okn.us/mcp) |

## 3. Connected knowledge graphs — full registry table

The registry is a GitHub-generated site: each KG's Markdown file under `docs/registry/kgs/` is "the source of truth", "automatically compiled into the registry metadata file" `kgs.yaml` (https://github.com/frink-okn/okn-registry README — https://github.com/frink-okn/okn-registry/blob/main/README.md). The machine-readable list is `kgs.yaml`, raw at https://raw.githubusercontent.com/frink-okn/okn-registry/refs/heads/main/docs/registry/kgs.yaml, rendered as the browsable table at https://registry.okn.us/registry/ (site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/registry/index.md and https://github.com/frink-okn/okn-registry/blob/main/docs/registry/kgs.yaml).

**Count: 45 graphs registered in `kgs.yaml` (parsed 2026-09-25).** 42 have a SPARQL endpoint and TPF (Linked Data Fragments) endpoint at apps.okn.us; 3 (`glygenkg`, `rdkg`, `bio101`) have neither listed. The okn.us hub page advertises "40+ interconnected knowledge graphs" (https://okn.us/).

| Shortname | Title | Description (truncated ~120 chars) | SPARQL | TPF |
| --- | --- | --- | --- | --- |
| `biohealth` | Bio-Health KG | Bio-Health KG is a dynamically-updated open knowledge network for health, integrating biomedical insights with social... | Yes | Yes |
| `geoconnex` | GEOCONNEX | Geoconnex is an open, community-driven knowledge graph linking U.S. hydrologic features to enable seamless water data... | Yes | Yes |
| `babel` | Babel KG | Babel creates cliques of equivalent identifiers across many biomedical vocabularies | Yes | Yes |
| `okn-void` | OKN VoID graph descriptions | Collected VoID (Vocabulary of Interlinked Datasets) metadata for all OKN graphs | Yes | Yes |
| `ubergraph` | Ubergraph | Integrated suite of OBO ontologies with precomputed inferred relationships | Yes | Yes |
| `wikidata` | Wikidata | Wikidata is a free and open knowledge base that can be read and edited by both humans and machines | Yes | Yes |
| `prokn` | Protein Knowledge Network | The Protein Knowledge Network (ProKN) integrates protein-centric data with the genomic-centric datasets of the Common... | Yes | Yes |
| `sockg` | SOCKG | The Soil Organic Carbon Knowledge Graph (SOCKG) enhances robust soil carbon modeling, which is crucial for voluntary... | Yes | Yes |
| `climatemodelskg` | Climate Models KG | Climate Models KG is a knowledge graph to support evaluation and development of climate models. | Yes | Yes |
| `sudokn` | SUDOKN | Supply and Demand Open Knowledge Network is an interconnected network of publicly available manufacturing capability... | Yes | Yes |
| `biomarkerkg` | BiomarkerKB KG | The BiomarkerKB knowledge graph is a structured network that connects biomarkers to diseases, drugs, biological entit... | Yes | Yes |
| `ruralkg` | Rural Resilience KG | Rural Resilience KG is a cross-domain knowledge graph to integrate health and justice for rural resilience. | Yes | Yes |
| `nasa-gesdisc-kg` | NASA-GESDISC-KG | The NASA Knowledge Graph Dataset is an expansive graph-based dataset designed to integrate and interconnect informati... | Yes | Yes |
| `identifier-mappings` | ID Mappings | Mappings using standard RDF predicates between Wikidata entities and external identifiers represented as RDF IRIs | Yes | Yes |
| `spoke-genelab` | SPOKE GeneLab | The spoke-genelab KG complements the spokeokn (SPOKE Open Knowledge Network) KG and is designed to integrate omics da... | Yes | Yes |
| `spoke-okn` | SPOKE-OKN | The spoke-okn (SPOKE Open Knowledge Network) KG is a comprehensive biomedical and environmental health knowledge grap... | Yes | Yes |
| `ncipidkg` | NCI-PID 2.0 KG | The NCI-PID 2.0 Knowledge Graph converts NCI Pathway Interaction Database version 2.0 networks into RDF, capturing pr... | Yes | Yes |
| `nestkg` | NeST KG | The NeST (Nested Systems in Tumors) Knowledge Graph converts the NeST hierarchical map of cancer protein systems into... | Yes | Yes |
| `biobricks-aopwiki` | BioBricks AOP-Wiki | BioBricks AOP-Wiki is an open knowledge graph for Adverse Outcome Pathways from the AOP-Wiki. | Yes | Yes |
| `biobricks-ice` | BioBricks ICE | BioBricks ICE (Integrated Chemical Environment) is an open knowledge graph for cheminformatics and chemical safety da... | Yes | Yes |
| `biobricks-mesh` | BioBricks MeSH | BioBricks MeSH is an open knowledge graph of Medical Subject Headings (MeSH) biomedical vocabulary. | Yes | Yes |
| `biobricks-pubchem-annotations` | BioBricks PubChem Annotations | BioBricks PubChem Annotations is an open knowledge graph of chemical annotations from PubChem. | Yes | Yes |
| `biobricks-tox21` | BioBricks Tox21 | BioBricks Tox21 is an open knowledge graph for Tox21 toxicology screening data. | Yes | Yes |
| `biobricks-toxcast` | BioBricks ToxCast | BioBricks ToxCast is an open knowledge graph for EPA ToxCast high-throughput screening data. | Yes | Yes |
| `wildlifekn` | Wildlife-KN | This project seeks to create a comprehensive, integrative knowledge network for the management of wildlife in the con... | Yes | Yes |
| `ufokn` | UF-OKN | The Urban Flooding Open Knowledge Network (UF-OKN) is an informational infrastructure built using knowledge graphs ai... | Yes | Yes |
| `dreamkg` | DREAM-KG | Develop Dynamic, REsponsive, Adaptive, and Multifaceted Knowledge Graphs to Address Homelessness With Explainable AI | Yes | Yes |
| `evoweb` | EvoWeb | EvoWeb - An Open Knowledge Graph of Co-evolving Genes (NIAID) | Yes | Yes |
| `gene-expression-atlas-okn` | Gene Expression Atlas | Query pre-computed differential gene expression (log2 fold changes and adjusted p-values) for genes across diseases,... | Yes | Yes |
| `nde` | NIAID Data Ecosystem KG | The nde (NIAID Data Ecosystem) knowledge graph is a dataset-discovery index for finding biomedical research datasets... | Yes | Yes |
| `oard-kg` | Open Annotations for Rare Diseases (OARD) Knowledge Graph | Clinical associations between rare diseases and phenotypes derived from electronic health records | Yes | Yes |
| `scales` | SCALES | SCALES is an integrated justice platform to connect criminal justice data across data silos. | Yes | Yes |
| `hydrologykg` | SAWGraph Hydrology KG | The Hydrology KG is the part of the SAWGraph project that describes streams, waterbodies and wells and their locations. | Yes | Yes |
| `spatialkg` | SAWGraph Spatial KG | The SAWGraph Spatial KG is part of the Safe Agricultural Products and Water Graph (SAWGraph) project. It contains all... | Yes | Yes |
| `pankgraph` | PanKgraph | PanKgraph — PanKbase Knowledge Graph (NIDDK) | Yes | Yes |
| `digcfdekg` | CFDE REVEAL Knowledge Graph | The CFDE REVEAL Knowledge Graph is a statistically inferred genomic evidence graph to integrate and disseminate knowl... | Yes | Yes |
| `glygenkg` | GlyGen KG | A knowledge graph of glycans, glycoproteins, genes that code for these proteins and glycosylation sites integrated wi... | No | No |
| `rdkg` | Rare Disease Knowledge Graph | RDKG is an open knowledge graph for rare diseases that integrates standardized disease identifiers and cross-referenc... | No | No |
| `phaseskg` | PHASES KG | Knowledge graph Promoting Healthy Aging through Semantic Enrichment | Yes | Yes |
| `fiokg` | SAWGraph FRS KG | The FRS (Facility Registry Service) KG is the part of the SAWGraph project that stores data about facilities from EPA... | Yes | Yes |
| `sawgraph` | SAWGraph PFAS KG | The Safe Agricultural Products and Water Graph (SAWGraph) PFAS KG stores data on PFAS observations and releases, desc... | Yes | Yes |
| `medical-device-kg` | Medical Device Knowledge Graph | A unified medical-device knowledge graph integrating regulatory, clinical, research, safety, and other relevant data... | Yes | Yes |
| `securechainkg` | SecureChain KG | SecureChain is a knowledge graph for resilient, trustworthy, and secure software supply chains. | Yes | Yes |
| `bio101` | KB Bio 101 | A knowledge base created from an introductory biology textbook | No | No |
| `nikg` | Neighborhood Information KG | Neighborhood Information KG (NIKG) is a knowledge graph warehouse for neighborhood information. | Yes | Yes |

Descriptions are verbatim from `kgs.yaml`, truncated at ~120 chars. "SPARQL" = a `sparql:` field is present (all at `https://apps.okn.us/{shortname}/sparql`); "TPF" = a `tpf:` field is present (all at `https://apps.okn.us/ldf/{shortname}`). Where present, each entry also carries a `stats:` link (per-graph kg-stats page) and `lakefs-repo:` name. Note the okn.us hub card carousel (https://okn.us/) additionally shows "FDA MAUDE Adverse Events" and "SemOpenAlex" cards, which are not in `kgs.yaml` — the `kgs.yaml` table above is the authoritative registry list per the registry itself.

## 4. kg-stats pages

https://registry.okn.us/kg-stats/ ("Learn More about the Knowledge Graphs in PROTO-OKN") provides per-graph entity/predicate statistics: "The information provided about Theme 1 graphs was obtained from an analysis of the graphs that were deposited in the FRINK Landing zone, using LinkML schema to generate the schema and using a modification of this documentation generator to produce readable pages with class diagrams from that schema." Graph pages list classes and predicates with occurrence counts (e.g. "Class with 107 occurences.", "28216 occurrences with subject type schema_Dataset and object type schema_PropertyValue" on https://registry.okn.us/kg-stats/geoconnex/). Corrections go to the contact named on that page (see the registry).

The index documents 12 graph pages: Biobricks, Climate Models, DREAM KG, Neighborhood Information, Rural Resilience, SAW Graph, SCALES, Secure Chain, SPOKE, SOC KG, SUDOKN, WEN KG — plus a shared "Graph Notation & Assumptions" section: documented IRI prefixes for the Theme 1 graphs (sosa:, umls:, dc:, geo:, skos:, sawgraph family, sudokn:, etc.), the assumption that each graph is a single HDT file whose top entity is an `owl:Ontology` (with `dct:title`, `dct:description`, `dct:hasVersion`, `dct:created`), that entities are `rdfs:Class`/`owl:Class` with `rdfs:label`/`rdfs:comment`/`rdfs:subClassOf`, and that predicates appear as `rdf:Property`, `owl:DatatypeProperty`, `owl:ObjectProperty`, etc., with `rdfs:label`/`skos:definition`/`rdfs:domain`/`rdfs:range`. (Site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/kg-stats/index.md.)

## 5. Crosswalks

https://okn.us/crosswalks ("Crosswalks — Shared identifiers and mappings that link the OKN knowledge graphs") defines:

> "A crosswalk is a verified way to join two knowledge graphs on a shared identifier — so a question that no single graph can answer becomes answerable by combining them."

Key figures on that page (as captured 2026-09-25): **162 verified crosswalks**, **35 knowledge graphs connected**, **328 worked example questions**, **15 domains covered**. Every crosswalk names a "shared key" (identifier both graphs use for the same real-world thing) with the predicates carrying it on each side and the row count the join returns. Common shared keys named on the page: MONDO / DOID disease identifiers; Entrez / HGNC / Ensembl gene identifiers; CHEBI / PubChem chemical identifiers; NCBITaxon organism identifiers; FIPS / GEOID geographic area identifiers. Where schemes differ, joins route through bridge graphs — `ubergraph` maps DOID to MONDO, `wikidata` maps HGNC to Entrez. Crosswalks are "verified, not inferred": each has been run as live federated SPARQL and checked against an authoritative source. The page offers a Crosswalk network (interactive map) and Crosswalk inventory (full table with transcripts).

Example questions given on the page: "Which genes are associated with autism spectrum disorder, and what is known about them?" and "What is the maximum PFAS measurement in each county?"

The 15 domains listed: Anatomy & Cell Type, Chemicals, Disease & Phenotype, Earth Observation, Environmental Toxicology, Function & Pathways, Genes, Geospatial, Hydrology, Industry & Supply Chain, Justice & Public Safety, Proteins, Publications, Social Determinants & Services, Taxonomy.

Crosswalk/case-study items featured on the okn.us hub (https://okn.us/): **"Support for the unhoused"** (DREAM-KG, Rural-KG), **"Web of Biological Data"** (WOBD — "Connected biomedical knowledge graphs and dataset metadata", app at https://apps.okn.us/wobd/), **"Biomedical research"** — explore gene, protein and drug interactions (SPOKE, BioBricks), **"Water and Infrastructure"** — link hydrology, infrastructure, demographics, and environmental risk data across the U.S. (WEN-OKN, SAWGraph). The MCP page (https://okn.us/mcp) additionally links worked crosswalk example transcripts such as "Which genes does rdkg associate with autism spectrum disorder?" and "How do I join spoke-okn and prokn?". The mcp-okn README (https://github.com/sbl-sdsc/mcp-okn) describes larger counts (181 crosswalks / 37 graphs / 366 questions / 16 domains incl. Variants) plus 16 end-to-end case studies — the live crosswalks page numbers above are the site-of-record figures captured on 2026-09-25.

## 6. Machine-readable graph list

- The browsable registry table is generated from the repo: registry entries live at https://github.com/frink-okn/okn-registry/tree/main/docs/registry/kgs (one Markdown file per KG, YAML front-matter + narrative), "automatically compiled into the registry metadata file" `kgs.yaml` (https://raw.githubusercontent.com/frink-okn/okn-registry/refs/heads/main/docs/registry/kgs.yaml) — i.e., the registry is GitHub-generated from `kgs.yaml`/per-KG markdown, not served from a live database (https://github.com/frink-okn/okn-registry/blob/main/README.md).
- `kgs.yaml` (YAML) is the machine-readable list: 45 entries with `shortname`, `title`, `description`, `contact`, `sparql`, `tpf`, `stats`, `homepage`, `license`, `funding`, and FRINK options (`lakefs-repo`, ontology prefixes, label-role predicates).
- Example queries per KG live under https://github.com/frink-okn/okn-registry/tree/main/docs/registry/queries (README, site source repo).
- A JSON REST API for the registry: [NOT DOCUMENTED] — the sources document only the raw `kgs.yaml` file; the registry site's "Using OKN Fabric APIs" help page (https://registry.okn.us/help/apis/, site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/apis.md) is an empty stub containing only the heading.