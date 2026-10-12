# OKN Documentation Index

> **Attribution and status.** This file summarises content from [okn.us](https://okn.us/), [registry.okn.us](https://registry.okn.us/) and [github.com/frink-okn/okn-registry](https://github.com/frink-okn/okn-registry), captured on 2026-09-25. It is an unofficial digest, is not endorsed by the Open Knowledge Network, FRINK or RENCI, and may be out of date. Quoted passages remain the work of their original authors; the registry site and repository are the authoritative sources, including for contact details and licence terms.


Scraped **2026-09-25** from the Open Knowledge Network web surfaces. Method: every URL in `https://registry.okn.us/sitemap.xml` (107 pages), plus nav-discovered pages on `okn.us` (no sitemap.xml/robots.txt exists there) and `apps.okn.us`. All pages were server-rendered and fetched successfully (HTTP 200); JS-only app shells and empty stub pages are marked as such. Site source of truth: https://github.com/frink-okn/okn-registry (checked at main commit `fc1301e8e0d9a33dd488ff1a9c6802324bf15023`, 2026-09-19 — matches the sitemap `lastmod`).

**Digests derived from this scrape** (in this directory):

| File | Covers |
|---|---|
| `okn-overview.md` | What OKN is, funding, surfaces, all 45 registered graphs, crosswalks |
| `registry-help.md` | Uploading Graphs help section (lakeFS landing zone, formats, workflow) |
| `registry-book.md` | Building Graphs book (best practices, identifiers by domain) |
| `api-notes.md` | CONFIRMED endpoints (SPARQL/TPF/federation, embeddings, MCP, LakeFS) vs [NOT DOCUMENTED] |
| `contribute.md` | Contributing graphs, registry entries, example queries, compute |
| `INDEX.md` | This file |

### okn.us hub (6 pages)

| URL | Title | One-line summary | Captured |
|---|---|---|---|
| https://okn.us/ | OKN hub | Official hub: cards linking all 40+ registered graphs, crosswalks, MCP server, SPARQL query tool, sample queries, contribute paths; footer "Powered by UNC Chapel Hill / RENCI and Onai Inc., NSF Award #2535091". | 2026-09-25 |
| https://okn.us/contribute-compute/ | Contribute Compute | Tokens are being deployed in the OKN program as an experiment. We will probe their utility for sustaining ongoing operations. Lessons learned may be applied towards future initiatives. | 2026-09-25 |
| https://okn.us/crosswalks | Crosswalks | Shared identifiers and mappings that link the OKN knowledge graphs | 2026-09-25 |
| https://okn.us/mcp | MCP Server | A Model Context Protocol (MCP) server providing seamless access to SPARQL endpoints with specialized support for the OKN knowledge graphs. Query 30+ scientific knowledge graphs using natural language … | 2026-09-25 |
| https://okn.us/privacy | Privacy Policy | The OKN project is committed to transparency about how we handle your data. In short: we do not sell, share, or monetize any data you provide. | 2026-09-25 |
| https://okn.us/search | Search | JS-rendered page shell (no server-rendered body); the hub positions OKN search via the mcp-okn MCP assistant — no separate HTTP API documented. | 2026-09-25 |

### apps.okn.us services (4 pages)

| URL | Title | One-line summary | Captured |
|---|---|---|---|
| https://apps.okn.us/ | Proto-OKN SPARQL Query Service | Proto-OKN SPARQL Query Service — the client-side (Comunica) query UI; server-rendered HTML is an app shell. | 2026-09-25 |
| https://apps.okn.us/embeddings/ | Frink Embeddings Query | Frink Embeddings Query UI — text/node similarity search over graph embeddings (Qdrant-backed); graph filter list rendered server-side. | 2026-09-25 |
| https://apps.okn.us/wobd | WOBD — Web of Biological Data | WOBD — Web of Biological Data: NIAID Data Ecosystem metadata federated with 30+ Proto-OKN KGs; guided queries + AI-assistant access. | 2026-09-25 |
| https://apps.okn.us/wobd/mcp | AI assistant access · WOBD | WOBD "Connect an AI assistant" page: built on mcp-proto-okn; points clients at the hosted Proto-OKN MCP endpoint; includes three worked vignettes. | 2026-09-25 |

### registry.okn.us — docs, registry, query, reference (29 pages)

| URL | Title | One-line summary | Captured |
|---|---|---|---|
| https://registry.okn.us/kg-stats/ | Learn More about the Knowledge Graphs in PROTO-OKN | Index of per-graph statistics pages; IRI prefixes identified in the Theme 1 graphs are documented per graph where applicable. | 2026-09-25 |
| https://registry.okn.us/ | OKN Registry — home | Registry home: "An open knowledge network is a publicly accessible, interconnected set of data repositories and associated knowledge graphs…"; entry links to registry, book, help, query sections. | 2026-09-25 |
| https://registry.okn.us/FRINK-index/ | FRINK: Integrating Knowledge in the Prototype Open Knowledge Network (Proto-OKN) Program | This website serves as a resource for Theme 1 participants in the Proto-OKN program and provides information on FRINK's work for the broader public. The Quick Start Guide provides help information … | 2026-09-25 |
| https://registry.okn.us/book/ | Overview | This section holds informational guidance on adding and managing graphs and graph data within the OKN. | 2026-09-25 |
| https://registry.okn.us/book/best-practices/ | Graph Construction Best Practices | Here are links to documents developed in collaboration with EduGate (Theme 3) and Fabric (Theme 2) to support Theme 1 groups in enhancing the integrity of knowledge graphs and advancing their … | 2026-09-25 |
| https://registry.okn.us/book/biomedical-identifiers/ | Biomedical | Biomedical identifier guidance: recommended vocabularies/registries (disease, chemical, gene/protein, etc.) and identifier conventions for biomedical graphs. | 2026-09-25 |
| https://registry.okn.us/book/environmental-identifiers/ | Environmental | Environmental identifier guidance; cross-references the biomedical and geospatial identifier pages. | 2026-09-25 |
| https://registry.okn.us/book/geospatial-identifiers/ | Geospatial | References to locations occur across many graphs in the Proto-OKN, whether as areas that certain species abound in, as points where companies are headquartered, or as jurisdictions within which … | 2026-09-25 |
| https://registry.okn.us/book/identifiers/ | About External Identifiers | An external identifier (hereinafter referred to as an 'identifier') is a string that represents a particular concept within a particular vocabulary or ontology. | 2026-09-25 |
| https://registry.okn.us/book/institutions/ | Institutions | This page lists recommendations of identifiers to use for legal entities (corporate bodies, non-profit organizations, etc.). It is likely that these will evolve and will apply most leniently since, … | 2026-09-25 |
| https://registry.okn.us/book/justice/ | Justice | The page on identifiers for institutions may also be worth consulting here. | 2026-09-25 |
| https://registry.okn.us/book/new-id-sources/ | Ingesting Identifier Sources | These guidelines are relevant for graphs that are considering including, as part of their own graph data, the entirety or a significant subset of another external knowledge graph. | 2026-09-25 |
| https://registry.okn.us/contribute/ | Contribute to the OKN | This section documents the purpose and process for maintaining the OKN Registry. | 2026-09-25 |
| https://registry.okn.us/contribute/contributing-to-registry/ | Contributing to registry | Placeholder page: "Contributing to registry — Note: This is also a placeholder."; real registry-entry instructions are at /registry/contribute/. | 2026-09-25 |
| https://registry.okn.us/contribute/registry-overview/ | The Open Knowledge Network Registry | The OKN Registry serves as the central discovery layer for the OKN, providing a structured catalog of the interconnected nodes and "fabric" that make up the system. | 2026-09-25 |
| https://registry.okn.us/help/ | Uploading Graphs | This section offers assistance for using various OKN Fabric services. | 2026-09-25 |
| https://registry.okn.us/help/apis/ | Using OKN Fabric APIs | STUB — page renders only the title; empty in the site source repo too. API facts live in reference/fabric (see api-notes.md). | 2026-09-25 |
| https://registry.okn.us/help/file-formats/ | Supported File Formats | STUB — page renders only the title; empty in the site source repo too. Supported upload formats are listed on help/update instead. | 2026-09-25 |
| https://registry.okn.us/help/setup/ | Setup a Repo in the Landing Zone | There are several ways for Theme 1 teams to upload graph to the Landing Zone found on lakeFS. We recommend uploading through the website for smaller files and using Amazon's S3 Tool for larger files … | 2026-09-25 |
| https://registry.okn.us/help/update-queries/ | Update Example Queries | This document outlines the process for updating the example user queries that appear on the Fabric UI page. | 2026-09-25 |
| https://registry.okn.us/help/update/ | Update Graphs in the OKN | To ensure a smooth and automated deployment of data pipelines, establishing structured rules and policies around branch and tag usage in our data repositories is essential. This guide focuses on … | 2026-09-25 |
| https://registry.okn.us/help/validation-checklist/ | Validation checklist | STUB — page renders only the title; file is empty in the site source repo. | 2026-09-25 |
| https://registry.okn.us/query/ | Querying okn.us using SPARQL | This section holds informational guidance on creating SPARQL queries to explore data across domains via knowledge graphs in okn.us. | 2026-09-25 |
| https://registry.okn.us/query/query-page/ | How to Use the Query Tool | The query page allows selection of a single knowledge graph or multiple knowledge graphs to query. | 2026-09-25 |
| https://registry.okn.us/query/sample-query-library/ | Sample Query Library | Sample Query Library Title Description All NeST systems a given protein belongs to, with mutation-enrichment status, keyed on UniProt nestkg Cell types in abdominal organs ubergraph Count how many … | 2026-09-25 |
| https://registry.okn.us/reference/fabric/ | OKN Fabric — Architecture & Resource Guide | The Fabric provides four core capabilities: | 2026-09-25 |
| https://registry.okn.us/reference/geo_feature_classes/ | FRINK geo / administrative feature-class inventory | FRINK geo / administrative feature-class inventory Every instantiated geographic or administrative feature class IRI in the 14-graph FRINK federation, grouped by the real-world concept it denotes and … | 2026-09-25 |
| https://registry.okn.us/registry/ | OKN registry | OKN registry Knowledge graphs registered with the Open Knowledge Network Shortname Title Description babel Babel KG Babel creates cliques of equivalent identifiers across many biomedical vocabularies … | 2026-09-25 |
| https://registry.okn.us/registry/contribute/ | Contribute to the Registry | First choose a ‘shortname’ for your graph. This will be widely used as a knowledge graph identifier and as part of service URLs such as SPARQL endpoints. Keep it brief and lowercase (hyphens are … | 2026-09-25 |

### registry.okn.us — per-graph kg-stats pages (33 pages)

| URL | Title | One-line summary | Captured |
|---|---|---|---|
| https://registry.okn.us/kg-stats/biobricks-aopwiki-kg/ | biobricks-aopwiki | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/biobricks-ice-kg/ | biobricks-ice | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/biobricks-mesh-kg/ | biobricks-mesh | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/biobricks-pubchem-annotations-kg/ | biobricks-pubchem-annotations | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/biobricks-tox21-kg/ | biobricks-tox21 | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/biobricks-toxcast-kg/ | biobricks-toxcast | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/biohealth/ | biohealth | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/climate-kg/ | Climate Models: Knowledge Graph to Support Evaluation and Development of Climate Models | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/climatepub4-kg/ | climatemodelskg | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/dream-kg%20copy/ | dream-kg (copy) | Sitemap artifact page "dream-kg copy"; per-graph statistics duplicate. | 2026-09-25 |
| https://registry.okn.us/kg-stats/dream-kg/ | No schema name specified (site title bug) | Per-graph statistics page for DREAM-KG (entity types / predicates, LinkML-derived). | 2026-09-25 |
| https://registry.okn.us/kg-stats/fio-kg/ | fiokg | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. Lead: This ontology supports querying the SAWGraph Knowledge Graph and the KnowWhereGraph. It is an … | 2026-09-25 |
| https://registry.okn.us/kg-stats/geoconnex/ | No schema name specified (site title bug) | Per-graph statistics page for GEOCONNEX (entity types / predicates, LinkML-derived). | 2026-09-25 |
| https://registry.okn.us/kg-stats/hydrology-kg/ | hydrologykg | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. Lead: This ontology supports querying the SAWGraph Knowledge Graph and the KnowWhereGraph. It is an … | 2026-09-25 |
| https://registry.okn.us/kg-stats/identifier-mappings/ | identifier-mappings | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/nde/ | nde | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/neighborhood-kg/ | nikg | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/nikg/ | Neighborhood Information: An Open Knowledge Graph for Neighborhood Information | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/rural-kg/ | ruralkg | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. Lead: An ontology which serves the schema for the cross-domain knowledge graph (Rural-KG) to integrate … | 2026-09-25 |
| https://registry.okn.us/kg-stats/sawgraph-kg/ | sawgraph | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. Lead: This ontology supports querying the SAWGraph Knowledge Graph and the KnowWhereGraph. It is an … | 2026-09-25 |
| https://registry.okn.us/kg-stats/sawgraph/ | SAW Graph: Safe Agricultural Products and Water Graph | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. Lead: The Contaminant Observation and Samples Ontology (ContaminOSO) developed as part of the AIKnowsPFAS … | 2026-09-25 |
| https://registry.okn.us/kg-stats/scales-kg/ | No schema name specified (site title bug) | Per-graph statistics page for SCALES (entity types / predicates, LinkML-derived). | 2026-09-25 |
| https://registry.okn.us/kg-stats/secure-chain-kg/ | securechainkg | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/soc-kg/ | sockg | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/spatial-kg/ | No schema name specified (site title bug) | Per-graph statistics page for the SAWGraph Spatial KG (entity types / predicates, LinkML-derived). | 2026-09-25 |
| https://registry.okn.us/kg-stats/spoke-genelab/ | spoke-genelab | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/spoke-kg/ | spoke-okn | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/spoke-okn/ | SPOKE: Connecting Biomedical information on Earth and in Space via the SPOKE knowledge graph | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/sudokn-kg/ | sudokn | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. Lead: SUDOKN Ontology is developed at the Semantic Computing Lab at Arizona State University. SUDOKN … | 2026-09-25 |
| https://registry.okn.us/kg-stats/sudokn/ | SUDOKN: Supply and Demand Open Knowledge Network | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. Lead: SUDOKN Ontology is developed at the Semantic Computing Lab ast ASU. SUDOKN provides the necessary … | 2026-09-25 |
| https://registry.okn.us/kg-stats/ufokn-kg/ | ufokn | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/wen-kg/ | WEN KG: The Water-Energy Nexus Open Knowledge Network | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |
| https://registry.okn.us/kg-stats/wildlife-kg/ | wildlifekn | Per-graph statistics page (entity types / predicates, LinkML-derived) for this Theme 1 KG. | 2026-09-25 |

### registry.okn.us — per-graph registry entries (45 pages)

| URL | Title | One-line summary | Captured |
|---|---|---|---|
| https://registry.okn.us/registry/kgs/babel/ | Babel KG | Registry entry — Babel creates cliques of equivalent identifiers across many biomedical vocabularies | 2026-09-25 |
| https://registry.okn.us/registry/kgs/bio101/ | KB Bio 101 | Registry entry — A knowledge base created from an introductory biology textbook | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biobricks-aopwiki/ | BioBricks AOP-Wiki | Registry entry — BioBricks AOP-Wiki is an open knowledge graph for Adverse Outcome Pathways from the AOP-Wiki. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biobricks-ice/ | BioBricks ICE | Registry entry — BioBricks ICE (Integrated Chemical Environment) is an open knowledge graph for cheminformatics and chemical safety data from EPA's CompTox database. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biobricks-mesh/ | BioBricks MeSH | Registry entry — BioBricks MeSH is an open knowledge graph of Medical Subject Headings (MeSH) biomedical vocabulary. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biobricks-pubchem-annotations/ | BioBricks PubChem Annotations | Registry entry — BioBricks PubChem Annotations is an open knowledge graph of chemical annotations from PubChem. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biobricks-tox21/ | BioBricks Tox21 | Registry entry — BioBricks Tox21 is an open knowledge graph for Tox21 toxicology screening data. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biobricks-toxcast/ | BioBricks ToxCast | Registry entry — BioBricks ToxCast is an open knowledge graph for EPA ToxCast high-throughput screening data. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biohealth/ | Bio-Health KG | Registry entry — Bio-Health KG is a dynamically-updated open knowledge network for health, integrating biomedical insights with social determinants of health. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/biomarkerkg/ | BiomarkerKB KG | Registry entry — The BiomarkerKB knowledge graph is a structured network that connects biomarkers to diseases, drugs, biological entities, and evidence from the scientific literature. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/climatemodelskg/ | Climate Models KG | Registry entry — Climate Models KG is a knowledge graph to support evaluation and development of climate models. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/digcfdekg/ | CFDE REVEAL Knowledge Graph | Registry entry — The CFDE REVEAL Knowledge Graph is a statistically inferred genomic evidence graph to integrate and disseminate knowledge within the Common Fund Data Ecosystem (CFDE). | 2026-09-25 |
| https://registry.okn.us/registry/kgs/dreamkg/ | DREAM-KG | Registry entry — Develop Dynamic, REsponsive, Adaptive, and Multifaceted Knowledge Graphs to Address Homelessness With Explainable AI | 2026-09-25 |
| https://registry.okn.us/registry/kgs/evoweb/ | EvoWeb | Registry entry — EvoWeb - An Open Knowledge Graph of Co-evolving Genes (NIAID) | 2026-09-25 |
| https://registry.okn.us/registry/kgs/fiokg/ | SAWGraph FRS KG | Registry entry — The FRS (Facility Registry Service) KG is the part of the SAWGraph project that stores data about facilities from EPA's Facility Registry service (FRS) together with their NAICS … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/gene-expression-atlas-okn/ | Gene Expression Atlas | Registry entry — Query pre-computed differential gene expression (log2 fold changes and adjusted p-values) for genes across diseases, tissues, cell types, developmental stages, and sex, drawn from a … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/geoconnex/ | GEOCONNEX | Registry entry — Geoconnex is an open, community-driven knowledge graph linking U.S. hydrologic features to enable seamless water data discovery, access, and collaborative monitoring. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/glygenkg/ | GlyGen KG | Registry entry — A knowledge graph of glycans, glycoproteins, genes that code for these proteins and glycosylation sites integrated with protein, gene, disease and publication data. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/hydrologykg/ | SAWGraph Hydrology KG | Registry entry — The Hydrology KG is the part of the SAWGraph project that describes streams, waterbodies and wells and their locations. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/identifier-mappings/ | ID Mappings | Registry entry — Mappings using standard RDF predicates between Wikidata entities and external identifiers represented as RDF IRIs | 2026-09-25 |
| https://registry.okn.us/registry/kgs/medical-device-kg/ | Medical Device Knowledge Graph | Registry entry — A unified medical-device knowledge graph integrating regulatory, clinical, research, safety, and other relevant data from multiple sources. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/nasa-gesdisc-kg/ | NASA-GESDISC-KG | Registry entry — The NASA Knowledge Graph Dataset is an expansive graph-based dataset designed to integrate and interconnect information about satellite datasets, scientific publications, … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/ncipidkg/ | NCI-PID 2.0 KG | Registry entry — The NCI-PID 2.0 Knowledge Graph converts NCI Pathway Interaction Database version 2.0 networks into RDF, capturing protein interactions, signaling pathways, and post-translational … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/nde/ | NIAID Data Ecosystem KG | Registry entry — The nde (NIAID Data Ecosystem) knowledge graph is a dataset-discovery index for finding biomedical research datasets — including gene-expression / transcriptomics data (RNA-seq, … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/nestkg/ | NeST KG | Registry entry — The NeST (Nested Systems in Tumors) Knowledge Graph converts the NeST hierarchical map of cancer protein systems into RDF, together with the IAS (Integrated Association Stringency) … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/nikg/ | Neighborhood Information KG | Registry entry — Neighborhood Information KG (NIKG) is a knowledge graph warehouse for neighborhood information. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/oard-kg/ | Open Annotations for Rare Diseases (OARD) Knowledge Graph | Registry entry — Clinical associations between rare diseases and phenotypes derived from electronic health records | 2026-09-25 |
| https://registry.okn.us/registry/kgs/okn-void/ | OKN VoID graph descriptions | Registry entry — Collected VoID (Vocabulary of Interlinked Datasets) metadata for all OKN graphs | 2026-09-25 |
| https://registry.okn.us/registry/kgs/pankgraph/ | PanKgraph | Registry entry — PanKgraph — PanKbase Knowledge Graph (NIDDK) | 2026-09-25 |
| https://registry.okn.us/registry/kgs/phaseskg/ | PHASES KG | Registry entry — Knowledge graph Promoting Healthy Aging through Semantic Enrichment | 2026-09-25 |
| https://registry.okn.us/registry/kgs/prokn/ | Protein Knowledge Network | Registry entry — The Protein Knowledge Network (ProKN) integrates protein-centric data with the genomic-centric datasets of the Common Fund Data Ecosystem (CFDE), spanning heterogeneous biological … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/rdkg/ | Rare Disease Knowledge Graph | Registry entry — RDKG is an open knowledge graph for rare diseases that integrates standardized disease identifiers and cross-references to support discovery and evidence synthesis. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/ruralkg/ | Rural Resilience KG | Registry entry — Rural Resilience KG is a cross-domain knowledge graph to integrate health and justice for rural resilience. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/sawgraph/ | SAWGraph PFAS KG | Registry entry — The Safe Agricultural Products and Water Graph (SAWGraph) PFAS KG stores data on PFAS observations and releases, describing the samples, the geospatial features they were taken from, … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/scales/ | SCALES | Registry entry — SCALES is an integrated justice platform to connect criminal justice data across data silos. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/securechainkg/ | SecureChain KG | Registry entry — SecureChain is a knowledge graph for resilient, trustworthy, and secure software supply chains. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/sockg/ | SOCKG | Registry entry — The Soil Organic Carbon Knowledge Graph (SOCKG) enhances robust soil carbon modeling, which is crucial for voluntary carbon markets. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/spatialkg/ | SAWGraph Spatial KG | Registry entry — The SAWGraph Spatial KG is part of the Safe Agricultural Products and Water Graph (SAWGraph) project. It contains all the Level 13 grid cells from the S2 grid as well as … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/spoke-genelab/ | SPOKE GeneLab | Registry entry — The spoke-genelab KG complements the spokeokn (SPOKE Open Knowledge Network) KG and is designed to integrate omics data from NASA’s Open Science Data Repository (OSDR/GeneLab), which … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/spoke-okn/ | SPOKE-OKN | Registry entry — The spoke-okn (SPOKE Open Knowledge Network) KG is a comprehensive biomedical and environmental health knowledge graph that integrates diverse data across genomics, environmental … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/sudokn/ | SUDOKN | Registry entry — Supply and Demand Open Knowledge Network is an interconnected network of publicly available manufacturing capability data focused on Small and Medium-Sized Manufacturers. | 2026-09-25 |
| https://registry.okn.us/registry/kgs/ubergraph/ | Ubergraph | Registry entry — Integrated suite of OBO ontologies with precomputed inferred relationships | 2026-09-25 |
| https://registry.okn.us/registry/kgs/ufokn/ | UF-OKN | Registry entry — The Urban Flooding Open Knowledge Network (UF-OKN) is an informational infrastructure built using knowledge graphs aiming to extract structured content from the information scattered … | 2026-09-25 |
| https://registry.okn.us/registry/kgs/wikidata/ | Wikidata | Registry entry — Wikidata is a free and open knowledge base that can be read and edited by both humans and machines | 2026-09-25 |
| https://registry.okn.us/registry/kgs/wildlifekn/ | Wildlife-KN | Registry entry — This project seeks to create a comprehensive, integrative knowledge network for the management of wildlife in the context of climate change | 2026-09-25 |

