# Contributing to the OKN — Graphs, Registry Entries, Queries, Compute

> **Attribution and status.** This file summarises content from [okn.us](https://okn.us/), [registry.okn.us](https://registry.okn.us/) and [github.com/frink-okn/okn-registry](https://github.com/frink-okn/okn-registry), captured on 2026-09-25. It is an unofficial digest, is not endorsed by the Open Knowledge Network, FRINK or RENCI, and may be out of date. Quoted passages remain the work of their original authors; the registry site and repository are the authoritative sources, including for contact details and licence terms.


> Capture date: 2026-09-25. Sources: live pages of https://registry.okn.us/ and https://okn.us/ plus the site source repo https://github.com/frink-okn/okn-registry (main, commit `fc1301e8e0d9a33dd488ff1a9c6802324bf15023`, 2026-09-19 — matches the deployed site's sitemap lastmod). Facts are quoted or closely paraphrased from those sources; topics the sources do not cover are marked **[NOT DOCUMENTED]**.

---

## 1. End-to-end: contributing a knowledge graph

The registry's own summary of the flow (https://registry.okn.us/registry/contribute/):

1. **Create a registry entry** (a pull request adding one Markdown file) — §2 below.
2. **Set up a repository in the landing zone** (lakeFS) and upload your graph — see `registry-help.md` (live doc: https://registry.okn.us/help/setup/).
3. **Merge/tag to trigger build + deployment** — the Fabric pipeline converts your data (to HDT) and deploys SPARQL/TPF endpoints (https://registry.okn.us/help/update/; architecture: https://registry.okn.us/reference/fabric/).
4. Only then do the entry's `sparql` / `tpf` fields get filled in.

> From https://registry.okn.us/registry/contribute/ (warning on the `sparql`/`tpf` frontmatter fields): "If you have *not* already uploaded data to https://repository.okn.us/ *and* triggered the conversion process ([see the documentation page on graph upload workflows and processing](https://registry.okn.us/help/update/#workflows-and-processing)), then please skip this field. We will add it once your graph's individual SPARQL endpoint is up and running."

### 1.1 Registry entry — the PR

From https://registry.okn.us/registry/contribute/ (site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/registry/contribute.md):

> "The okn.us Registry is a lightweight website managed in GitHub. As a result, adding a graph to it entails adding a new page in the 'docs/registry/kgs' folder of the Registry's GitHub repository. In most cases you may submit a pull request with a new entry file similar to the existing files, but other customizations are also possible."

**Choosing a shortname** (verbatim):

> "First choose a 'shortname' for your graph. This will be widely used as a knowledge graph identifier and as part of service URLs such as SPARQL endpoints. Keep it brief and lowercase (hyphens are okay): if your graph is all about fruit, maybe choose 'fruitkg'."

**Entry file**: `<shortname>.md` in [`docs/registry/kgs/`](https://github.com/frink-okn/okn-registry/tree/main/docs/registry/kgs), consisting of YAML frontmatter + a Markdown description.

**Frontmatter fields** (per https://registry.okn.us/registry/contribute/; cross-checked against https://registry.okn.us/reference/fabric/):

| Field | Content |
|---|---|
| `template` | "Should always be `overrides/kg.html`" |
| `shortname` | The chosen shortname |
| `title` | Name of the graph, "used in listings of graphs within the Registry and in SPARQL interfaces" |
| `description` | "One-line description of what is in your graph" |
| `stats` | Link to `https://registry.okn.us/kg-stats/` + your shortname |
| `homepage` | Link to the graph's dedicated website (if any) |
| `funding` | "If your graph is funded by an external source (such as the National Science Foundation), this should be a link to a page describing the associated award" |
| `sparql` | "`https://apps.okn.us/` followed by your graph's shortname, followed by `/sparql`" — skip until your endpoint is live |
| `tpf` | "`https://apps.okn.us/ldf/` followed by your graph's shortname" — skip until your endpoint is live |
| `frink-options` | Two subfields, `lakefs-repo` and `documentation-path`, "each of whose value should be your graph's shortname" (legacy naming artifact) |
| `contacts` | "a list that should hold at least one entry for every maintainer"; each entry has `email`, `github` (GitHub user ID, "who may be tagged on GitHub issues concerning the graph"), `label` (preferred name) |

The `reference/fabric` page adds `license` (license URL) to the observed field set and cautions that "this schema is not currently enforced (it should be)… treat fields as conventional until a schema/validation is added" (https://registry.okn.us/reference/fabric/).

**Why the prose description matters** (tip box on https://registry.okn.us/registry/contribute/):

> "The MCP server provided by okn.us relies on written descriptions of the content of the graphs, such as the one in this file, in addition to the statistics in the `okn-void` graph and any metadata in the RDF about entity types and predicates the graph uses. It is therefore to your advantage to have a good prose characterization here of what your graph does and provides."

**Example entry** (abridged verbatim from https://registry.okn.us/registry/contribute/ — "fruitkg.md"):

```markdown
---
template: overrides/kg.html
shortname: fruitkg
title: Fruit KG
description: A knowledge graph of fruits
stats: https://registry.okn.us/kg-stats/fruitkg
homepage: https://geocities.com/fruitkg
funding: https://www.nsf.gov/awardsearch/showAward?AWD_ID=XXXX
sparql: https://apps.okn.us/fruitkg/sparql
tpf: https://apps.okn.us/ldf/fruitkg
frink-options:
  lakefs-repo: fruitkg
  documentation-path: fruitkg
contacts:
  - email: maintainer@example.org
    github: fruitguy
    label: "John Fruit"
---

This is a wonderful knowledge graph describing everything about fruits…
```

**Finishing up** (verbatim): "Once you have saved this file, open a pull request for the addition of your graph entry file to the Registry. — As soon as the pull request is accepted, you can then move on to [setting up a repository in okn.us's landing zone](https://registry.okn.us/help/setup/) and uploading your graph."

**Updating an existing entry** (verbatim): "Any updates to data in the Registry may be made in the same manner as adding them, with a pull request containing an edited entry file."

The registry repo README repeats the PR-based workflow: "If you are a Proto-OKN KG maintainer, please propose edits to your registry file in a pull request" (https://github.com/frink-okn/okn-registry/blob/main/README.md). It also notes the frontmatter "should use standardized properties (a schema is forthcoming for use in QC)".

### 1.2 Landing zone repo + upload + deployment (summary)

Full details in `registry-help.md`; the essentials, from https://registry.okn.us/help/setup/ and https://registry.okn.us/help/update/:

- Landing zone = **lakeFS at https://repository.okn.us/**; every dataset gets its own lakeFS repository ("Each LakeFS repository should house a single dataset").
- **Credentials** (Access Key ID + Secret Access Key) are requested from Yaphet Kebede — "direct messaging Yaphet Kebede through our OKN Slack channel or by emailing the address given on the setup page (see the registry)" — providing your dataset name.
- Upload to the **`develop`** branch (website drag-and-drop, s5cmd, or rclone; files >1 GB should use S3 clients with chunking, no parallelization).
- **Merge `develop` → `main`** triggers the conversion pipeline (raw data → HDT + QLever index); output lands on a `stable_vX_X_X` branch; the submitter gets an **email** to review build outputs; **creating a tag** (e.g. `v0.0.4`) triggers deployment of the SPARQL and TPF endpoints.
- Supported inputs (from the info box on https://registry.okn.us/help/update/): "Single Neo4j dump files in single repository (WIP)"; "Multiple RDF file with the following extensions: rdf, xml, ttl, nt, nq, jsonld, json, rj, trig, trix, n3"; "Single HDT (WIP)".

## 2. Contributing to the registry site itself

- https://registry.okn.us/contribute/ ("Contribute to the OKN") is a section index: "This section documents the purpose and process for maintaining the OKN Registry", linking graph-construction best practices, external identifiers, biomedical identifiers, and new identifier sources (https://github.com/frink-okn/okn-registry/blob/main/docs/contribute/index.md).
- https://registry.okn.us/contribute/contributing-to-registry/ is an explicit **placeholder** — live page reads "Contributing to registry … Note: This is also a placeholder." (source: https://github.com/frink-okn/okn-registry/blob/main/docs/contribute/contributing-to-registry.md). The real registry-entry instructions live at https://registry.okn.us/registry/contribute/.
- https://registry.okn.us/contribute/registry-overview/ describes the registry's role: "The OKN Registry serves as the central discovery layer for the OKN, providing a structured catalog of the interconnected nodes and 'fabric' that make up the system. Its primary purpose is to enable interoperability and data findability via a directory of domain-specific knowledge graphs, technical endpoints, and metadata."
- Site development itself (from the repo README): the site is built with mkdocs; "You must have snakemake and uv locally installed to run the build scripts"; local preview via `uv run mkdocs serve --livereload` (https://github.com/frink-okn/okn-registry/blob/main/README.md).

## 3. Contributing example SPARQL queries

From https://registry.okn.us/help/update-queries/ ("Updating User Queries"; site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/update-queries.md):

- Example queries shown in the Fabric UI "are fetched from the frink-okn/okn-registry GitHub repository"; add or edit **`.rq` files** in `docs/registry/queries/` (subfolders allowed; "Each `.rq` file should contain **only one** SPARQL query").
- Metadata header required, parsed as YAML from `#+ ` lines — "The UI currently expects two specific metadata fields": `#+ summary: "…"` (string) and `#+ tags: ["tag1", "tag2"]` (array); **tags must reference knowledge-graph shortnames** as defined in `docs/registry/kgs.yaml`.
- Example file structure (verbatim):

  ```sparql
  #+ summary: "Fetches all unique classes in the knowledge graph."
  #+ tags: ["geoconnex", "sockg"]

  SELECT DISTINCT ?class
  WHERE {
    ?s a ?class .
  }
  LIMIT 100
  ```
- Caching: "The Fabric UI caches requests to GitHub for 24 hours in the browser's local storage"; maintainers can use the "invalidate cache" button, "may not yet be deployed on the Sterling instance. To use it, you will need to test on the GitHub Pages deployment: https://frink-okn.github.io/frink-query-ui".
- Questions/contact: "okn-frink at renci.org".
- The repo README adds: "Example queries for each KG can be placed in the appropriate folder (matching the KG shortname) … Please look at existing queries for header syntax documenting a query summary and suggested target KG(s)."

## 4. Contributing compute

Source: live page https://okn.us/contribute-compute/ ("Contribute Compute — OKN", captured 2026-09-25). The program runs a **token-based compute-sharing experiment**:

- "Tokens are being deployed in the OKN program as an experiment. We will probe their utility for sustaining ongoing operations. Lessons learned may be applied towards future initiatives."
- Motivation: "OKN has developed a large multi-subject knowledge graph, but it has also developed a variety of user-facing functionalities such as natural language interaction, visualizations, and much more. These AI-enabled functionalities require GPU servers. These are expensive, and are prohibitively so for supporting public access."
- "In the first stage, tokens will be utilized to support computational needs of the program, with a specific focus on the above workloads involving GPUs. User queries will be handled using a distributed network, facilitated by tokens."
- Onboarding: "Volunteering participants will install a software package made available on the OKN website. The Fabric team will provide online support via a software-integrated chat/messaging system."
- "The volunteer runs the software, which will make itself known to the network and respond to queries. The overall system will ensure that queries are gated by token validity checks."
- Two acceptable machine configurations, quoted verbatim:

  | Configuration | Requirements |
  |---|---|
  | **S(erver)** | "Linux or Macintosh · 16 GB RAM · 1 Gbps · 16 cores ideal, less possible with lower query throughput" |
  | **L(LM)** | "Linux · 1 Gbps · Nvidia GPU with 4x 24-32GB vRAM" |

- Contact: **"Inquire how to set up a node"** links to an email address given on https://okn.us/contribute-compute/.
- Reward/economics details beyond "tokens": **[NOT DOCUMENTED]** on the page.

## 5. Review process

What the sources document:

- Registry entries, query files, and all site content change **via GitHub pull requests** to https://github.com/frink-okn/okn-registry (https://registry.okn.us/registry/contribute/: "open a pull request"; README: "propose edits … in a pull request").
- Maintainers are reachable through the entry's `contacts` field — the `github` subfield exists so maintainers "may be tagged on GitHub issues concerning the graph" (https://registry.okn.us/registry/contribute/).
- The build/deploy pipeline provides its own review checkpoint: after merging to `main`, "the submitter receives an email prompting them to check the build outputs", and deployment happens only when the submitter **creates a tag** (https://registry.okn.us/reference/fabric/, "Data lifecycle"; https://registry.okn.us/help/update/).
- General help contact: "okn-frink at renci.org" (https://registry.okn.us/help/update-queries/); lakeFS credentials: the email address on the setup page / OKN Slack (https://registry.okn.us/help/setup/); compute: the address on https://okn.us/contribute-compute/; MCP example-query issues: the okn.us/mcp page links "file an issue" against the mcp-okn project (https://github.com/sbl-sdsc/mcp-okn).

Not documented anywhere in the sources: formal review SLAs, an approval board, or acceptance criteria for PRs — **[NOT DOCUMENTED]**.

## 6. What is not documented (summary)

- Whether registry-entry PRs are gated by any validation checklist — the "Validation checklist" page (https://registry.okn.us/help/validation-checklist/) is an empty stub.
- Contribution of crosswalks: the crosswalks catalog (https://okn.us/crosswalks) documents 162 verified crosswalks and invites browsing, but no contribution procedure for crosswalks is given on any scraped page — **[NOT DOCUMENTED]** (the MCP page says "If you find an issue or would like to contribute additional example queries, please file an issue" — https://okn.us/mcp).
- Token economics / compensation for compute contributors — **[NOT DOCUMENTED]**.
- A self-service account/credentials flow for the landing zone — **[NOT DOCUMENTED]** (email/Slack request only).
