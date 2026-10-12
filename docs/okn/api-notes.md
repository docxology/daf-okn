# OKN API & Endpoint Notes

> **Attribution and status.** This file summarises content from [okn.us](https://okn.us/), [registry.okn.us](https://registry.okn.us/) and [github.com/frink-okn/okn-registry](https://github.com/frink-okn/okn-registry), captured on 2026-09-25. It is an unofficial digest, is not endorsed by the Open Knowledge Network, FRINK or RENCI, and may be out of date. Quoted passages remain the work of their original authors; the registry site and repository are the authoritative sources, including for contact details and licence terms.


Capture date: **2026-09-25** (live HTTP probes + scraped pages + site source repo `frink-okn/okn-registry` @ `fc1301e8e0d9a33dd488ff1a9c6802324bf15023`, last commit 2026-09-19 — matches the site's sitemap `lastmod`).

**Convention.** Facts below are split into:

- **CONFIRMED** — stated in official OKN docs/pages (quoted or closely paraphrased with source link) and, where noted, re-verified by a live HTTP probe on 2026-09-25.
- **[NOT DOCUMENTED]** — the OKN surfaces are silent on the topic. Nothing here is invented.

Primary doc sources:
- https://registry.okn.us/reference/fabric/ ("OKN Fabric — Architecture & Resource Guide") — richest endpoint reference; also at https://github.com/frink-okn/okn-registry/blob/main/docs/reference/fabric.md
- https://registry.okn.us/query/query-page/ ("How to Use the Query Tool") — https://github.com/frink-okn/okn-registry/blob/main/docs/query/query-page.md
- https://okn.us/mcp (MCP server page)
- https://github.com/sbl-sdsc/mcp-okn (MCP server README, fetched 2026-09-25)
- https://registry.okn.us/help/ ("Uploading Graphs" section; `help/apis` page is a **stub** — title only, no body, in both the live render and the site source)

---

## 1. Host map (CONFIRMED)

| Host | What lives there | Source |
|---|---|---|
| `okn.us` | Landing / program entry point | https://registry.okn.us/reference/fabric/ |
| `registry.okn.us` | Graph registry: metadata, descriptions, contribution flow | same |
| `apps.okn.us` | Running services: query UI, per-graph SPARQL/TPF endpoints, Federation endpoint, MCP, embeddings | same |
| `repository.okn.us` | LakeFS — versioned store of contributed graph files ("source of truth for each graph's data") | same |
| `github.com/frink-okn` | All fabric source code and deployment artifacts | same |

---

## 2. SPARQL endpoints

### 2.1 Per-graph SPARQL — CONFIRMED

> "Fabric deploys standardized API endpoints for each hosted knowledge graph." — https://registry.okn.us/query/query-page/

Pattern (from https://registry.okn.us/reference/fabric/):

```
https://apps.okn.us/{kg-name}/sparql
```

- Engine: each per-graph endpoint is its own **separate QLever instance**; "Standard SPARQL 1.1 over each individual graph."
- Every hosted graph is served through **two** per-graph interfaces: SPARQL and TPF (§3).
- Canonical per-graph list: `okn-overview.md` (45 graphs in `kgs.yaml`); the registry renders each graph's `sparql` field, e.g. `https://apps.okn.us/biohealth/sparql`, `https://apps.okn.us/geoconnex/sparql` (https://registry.okn.us/registry/kgs/biohealth/).

Documented request shape (fabric.md, verbatim):

```bash
curl https://apps.okn.us/spoke-okn/sparql --data-urlencode \
  'query=SELECT * WHERE { ?s ?p ?o } LIMIT 10' \
  -H 'Accept: application/sparql-results+json'
```

*Live check 2026-09-25:* `GET https://apps.okn.us/spoke-okn/sparql?query=SELECT * WHERE {?s ?p ?o} LIMIT 2` with `Accept: application/sparql-results+json` → `200 application/sparql-results+json` with standard SPARQL JSON (`head.vars` / `results.bindings`). ✔

### 2.2 Cross-OKN "Federation" SPARQL endpoint — CONFIRMED

From https://registry.okn.us/query/query-page/ ("Cross-OKN query endpoint"):

> - SPARQL: `https://apps.okn.us/federation/sparql`

From https://registry.okn.us/reference/fabric/:

> "The Federation endpoint is really just one big QLever triplestore with a named graph for each KG — cross-graph results come from specifying named graphs there."
> "The Federation index takes 2–3 days to build and is rebuilt weekly, so a newly deployed or updated graph is queryable at its own per-graph endpoint immediately but only appears in the Federation endpoint after the next weekly rebuild."

Named-graph IRI form (both mcp-okn README and query-page.md):

```
https://purl.org/okn/frink/kg/{shortname}
```

Documented `FROM`-clause example (query-page.md, verbatim):

```
SELECT *
FROM <https://purl.org/okn/frink/kg/ubergraph>
FROM <https://purl.org/okn/frink/kg/wikidata>
WHERE { ?s ?p ?o }
LIMIT 10
```

> Note (fabric.md, marked "CONFIRM" by the authors): the "Federation" name is legacy — it is a unified triplestore, "no longer federating", and the doc flags that "a clearer name … and its URL" is an open question.

*Live check 2026-09-25:* `GET https://apps.okn.us/federation/sparql?query=SELECT * WHERE {?s ?p ?o} LIMIT 1` → `200 application/sparql-results+json`. ✔

### 2.3 VoID statistics graph — CONFIRMED

- SPARQL: `https://apps.okn.us/okn-void/sparql` — "counts of every 'kind' of triple in each graph — i.e. class–predicate–class combinations" (https://registry.okn.us/reference/fabric/; registry entry at https://registry.okn.us/registry/kgs/okn-void/)
- TPF: `https://apps.okn.us/ldf/okn-void`
- A daily GitHub Action repopulates each KG page's "schema" section by querying this graph.

*Live check 2026-09-25:* `GET https://apps.okn.us/okn-void/sparql?query=SELECT * WHERE {?s ?p ?o} LIMIT 1` → `200` SPARQL JSON. ✔

### 2.4 Authentication / rate limits on SPARQL — [NOT DOCUMENTED]

No OKN page documents authentication, API keys, or rate limits for any SPARQL/TPF endpoint. The registry docs require credentials **only** for the LakeFS data repository (§6). `help/apis/` — the page that would hold this — is an empty stub (title only) in both the live render and the site source (https://github.com/frink-okn/okn-registry/blob/main/docs/help/apis.md).

---

## 3. TPF (Triple Pattern Fragments) endpoints — CONFIRMED

From https://registry.okn.us/reference/fabric/:

> "A low-cost interface that serves one triple pattern at a time. Each graph has its own TPF endpoint under the Linked Data Fragments (`ldf`) path":

```
https://apps.okn.us/ldf/{kg-shortname}
```

- Browser UI for all loaded KGs: **`https://apps.okn.us/ldf/`** (query-page.md: "The TPF endpoints are service endpoints but also provide a browser UI")
- Fragment selection: query arguments **`subject`**, **`predicate`**, **`object`** (any subset; omitting all three returns the full graph, one page at a time). "Each argument takes a full IRI (and `object` may also be a literal) — prefixed names like `rdf:type` are not part of the interface."
- Documented example (fabric.md, verbatim):

```bash
curl -G https://apps.okn.us/ldf/spoke-okn \
  --data-urlencode 'predicate=http://www.w3.org/1999/02/22-rdf-syntax-ns#type' \
  -H 'Accept: application/trig'
```

*Live check 2026-09-25:* the above request returns Trig with `hydra:`/`void:` prefixes and a fragment IRI — standard TPF. ✔
Client-side federation over TPF is done with **Comunica** ("Comunica federates live over a user-selected set of TPF endpoints", fabric.md).

---

## 4. Query UI — CONFIRMED

- URL: **`https://apps.okn.us`** ("The okn.us Query Page is located at https://apps.okn.us" — https://registry.okn.us/query/query-page/; the okn.us hub also links it as "SPARQL Query Tool")
- Built on [Comunica](https://comunica.dev/); "Proto-OKN Federated SPARQL" is a Source in the drop-down; multi-source selection runs Comunica federation **locally in the browser** over TPF endpoints.
- Features per query-page.md: **Sources** drop-down (single/multi), **SPARQL Query** pane, **Run Query**, **EXAMPLES** pane (pre-formulated queries labeled per graph), **Save Query** → SAVED panel, results **download button**.
- Example-query source of truth: `docs/registry/queries/*.rq` in https://github.com/frink-okn/okn-registry (see `contribute.md`).
- The UI caches GitHub requests for **24 hours** in browser local storage; maintainers can use an "invalidate cache" button (update-queries.md).

---

## 5. Embeddings service — CONFIRMED

Source: https://registry.okn.us/reference/fabric/ (§Embeddings) + live probes. Service: `frink-embeddings-web` (https://github.com/frink-okn/frink-embeddings-web), backed by a **Qdrant** vector DB. Base path: `https://apps.okn.us/embeddings/`.

### 5.1 Interactive UI (GET) — CONFIRMED

> "**Interactive UI** — `GET /embeddings/` with query parameters:"

| Param | Meaning |
|---|---|
| `type` | Feature type (`Text` / `Node`) |
| `value` | The text or node to search for |
| `graph-mode` | `include` or `exclude` |
| `graph` | Graph shortname to include/exclude (repeatable) |

Documented example: `https://apps.okn.us/embeddings/?type=text&value=brains`

### 5.2 JSON API (POST) — CONFIRMED

> "**JSON API** — `POST /embeddings/query` with a body matching the `Query` model:"

```bash
curl -X POST https://apps.okn.us/embeddings/query \
  -H 'Content-Type: application/json' \
  -d '{
        "feature": { "type": "text", "value": "brains" },
        "include_graphs": ["spoke-okn"],
        "limit": 10,
        "offset": 0
      }'
```

> "`feature` is a discriminated union on `type` — `text` or `node` (with a `value`). `include_graphs` / `exclude_graphs` are optional lists (only one may be set); `limit` defaults to 10, `offset` to 0. The response is JSON with a `results` array of scored nearest matches."

*Live check 2026-09-25:* `POST https://apps.okn.us/embeddings/query` with `{"feature":{"type":"text","value":"brains"},"limit":3,"offset":0}` → `200` with `{"results":[{...}]}`; observed result-item fields: `encoded_uri`, `id`, `iri_count`, `iris` (array), `payload` (`graph`, `iri` array, `iri_count`, `label`, `repr`), `primary_uri`, `score` (float). ✔ (Response-field names observed empirically; the docs only say "results array of scored nearest matches".)
Also: `GET https://apps.okn.us/embeddings/query` → `405 Method Not Allowed` (POST-only route confirmed).

### 5.3 Undocumented aspects — [NOT DOCUMENTED] / observed

- No OpenAPI spec or docs page: `GET https://apps.okn.us/embeddings/openapi.json` and `.../docs` → **404** (probed 2026-09-25). The UI lists 20 graph shortnames as filter choices (ubergraph, securechainkg, geoconnex, hydrologykg, spoke-okn, nde, biohealth, spoke-genelab, nasa-gesdisc-kg, nikg, ufokn, ruralkg, spatialkg, sawgraph, sudokn, wildlifekn, dreamkg, climatemodelskg, sockg, fiokg, scales).
- Self-hosting details (from https://github.com/frink-embeddings-web README): Python 3.12+, Flask/gunicorn server (default port 8000), Qdrant collection `OKN-Graph`, model `sentence-transformers/all-MiniLM-L6-v2`, CLI `okn-search` (`search`, `survey`, `list-graphs`). These describe the *component*, not the hosted service's guarantees.
- fabric.md flags as an open item: "CONFIRM — the gateway path mapping (this assumes `/embeddings/*` proxies to the app root, so the in-app `POST /query` is reached as `/embeddings/query`)."
- fabric.md marks embeddings-for-MCP-term-discovery as an **idea, not yet wired up**.

---

## 6. Data repository (LakeFS) & graph file access — CONFIRMED (auth), [NOT DOCUMENTED] (public download)

- URL: **`https://repository.okn.us/`** — LakeFS ("versioned store of the contributed graph files; the source of truth for each graph's data") — https://registry.okn.us/reference/fabric/
- Authentication (only documented credential flow in the OKN docs; https://registry.okn.us/help/setup/):
  > "you will need to request credentials for accessing lakeFS. These credentials are an **Access Key ID** and a **Secret Acess Key**. You may request these either by direct messaging Yaphet Kebede through our OKN Slack channel or by emailing the address given on the setup page (see the registry). With your request please provide the name of your dataset."
- S3-compatible API (used by s5cmd/rclone/aws-cli): `LAKEFS_ENDPOINT=https://repository.okn.us/` with `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (help/setup.md).
- Download/export of registered graphs: the help docs describe **upload**, conversion (HDT), and SPARQL/TPF serving; **no public bulk-download endpoint for graph data is documented** → [NOT DOCUMENTED]. Programmatic access today = SPARQL/TPF queries (§2–3); graph metadata = `kgs.yaml` (§7). Authenticated LakeFS REST/S3 access is possible for credentialed contributors (standard LakeFS), but the OKN docs don't document a download procedure → [NOT DOCUMENTED].
- Auth to LakeFS is managed by a `lakefs-acl-server` component (fabric.md component inventory).

---

## 7. Registry metadata (machine-readable) — CONFIRMED

- **`kgs.yaml`** is "the single machine-readable metadata file for all graphs", recompiled from per-KG Markdown frontmatter whenever any KG page changes (https://registry.okn.us/reference/fabric/). Raw file: https://github.com/frink-okn/okn-registry/blob/main/docs/registry/kgs.yaml — 45 graph entries as of 2026-09-25, each with `shortname`, `title`, `description`, `sparql`, `tpf`, `stats`, `funding`, `contact`, `frink-options` (`lakefs-repo`, `documentation-path`, optional `neo4j-conversion-config-path`), etc.
- Full graph table: see `okn-overview.md`.
- **No REST/JSON API for the registry itself is documented** — the registry site is statically generated from the GitHub repo → [NOT DOCUMENTED]. (The registry repo also publishes VoID-derived YAMLs per graph under `docs/registry/void/*.yaml`.)
- Shared namespace prefix list: https://github.com/frink-okn/okn-registry/blob/main/docs/registry/prefixes.yaml

---

## 8. MCP server — CONFIRMED

From https://okn.us/mcp/ and https://github.com/sbl-sdsc/mcp-okn:

- **Current endpoint**: `https://apps.okn.us/okn-mcp-dev/mcp`
- **Legacy endpoint**: `https://apps.okn.us/okn-mcp/mcp` (connector name `mcp-proto-okn`) — "will remain available for a transition period"; users are told to delete/deactivate it and switch to `mcp-okn-dev`.
  - https://registry.okn.us/reference/fabric/ still lists the legacy `https://apps.okn.us/okn-mcp/mcp` — the fabric reference lags the live MCP page.
- **Transport**: MCP over HTTP (Streamable HTTP / JSON-RPC). Evidence: README's `claude mcp add --transport http mcp-okn-dev https://apps.okn.us/okn-mcp-dev/mcp`; and *live check 2026-09-25*: `GET https://apps.okn.us/okn-mcp-dev/mcp` → **406** with `{"jsonrpc":"2.0","id":"server-error","error":{"code":-32600,"message":"Not Acceptable: Client must accept text/event-stream"}}` — the okn.us/mcp page itself says "Visiting it directly in a browser returns a JSON-RPC error (the endpoint speaks JSON-RPC, not HTTP GET); that is expected." ✔
- **Backing query service**: "An MCP server for querying the federated SPARQL endpoint (`https://apps.okn.us/federation/sparql`) over the Proto-OKN knowledge graphs"; SPARQL is scoped to named graphs `https://purl.org/okn/frink/kg/{shortname}` (mcp-okn README).
- **What it provides** (okn.us/mcp): graph discovery + documentation linking, federated queries, precomputed crosswalks with worked examples/replayable transcripts, ontology-driven search expansion (MONDO, HP, GO, UBERON), registry links/metadata. fabric.md notes the MCP server currently "generates its own registry" rather than reading `kgs.yaml` (an open TODO to wire it to registry + `okn-void`).
- **Client configs** (verbatim from okn.us/mcp and the README):
  - Claude Desktop: Connectors → Add custom connector; Name `mcp-okn-dev`, URL `https://apps.okn.us/okn-mcp-dev/mcp` (Pro/Max subscription required).
  - Claude Code: `claude mcp add --transport http mcp-okn-dev https://apps.okn.us/okn-mcp-dev/mcp`, or `.mcp.json`:

    ```json
    { "mcpServers": { "mcp-okn-dev": { "type": "url", "url": "https://apps.okn.us/okn-mcp-dev/mcp" } } }
    ```
  - ChatGPT: web app only, Settings → Apps → Developer mode → Create app (Name `mcp-okn-dev`, URL as above).
  - VS Code Copilot / Cursor: same URL, Agent mode.
- **Companion skills**: `okn-report-style`, `okn-bioanalysis` ship in the sbl-sdsc/mcp-okn repo; literature connectors used by case studies: PubMed `https://pubmed.mcp.claude.com/mcp`, Paperclip `https://paperclip.gxl.ai/mcp`.
- Source repos: `sbl-sdsc/mcp-okn` (hosted server, BSD-3-Clause) and `frink-okn/mcp-proto-okn` (fabric.md lists this as the component source).
- Self-hosting details (from https://github.com/frink-okn/frink-embeddings-web README): Python 3.12+, Flask/gunicorn server (default port 8000), Qdrant collection `OKN-Graph`, model `sentence-transformers/all-MiniLM-L6-v2`, CLI `okn-search` (`search`, `survey`, `list-graphs`). These describe the *component*, not the hosted service's guarantees.

---

## 9. WOBD app ("Web of Biological Data") — CONFIRMED (surface), [NOT DOCUMENTED] (API)

- URL: **`https://apps.okn.us/wobd`** (linked from the okn.us hub as "Web of Biological Data").
- Self-description (live page, 2026-09-25): "WOBD turns biomedical data silos into a queryable discovery network. The Web of Biological Data connects harmonized dataset metadata from the NIAID Data Ecosystem with 30+ Proto-OKN knowledge graphs…" Features "guided queries", "AI assistants", "query guardrails, ontology lookup, and provenance-aware execution."
- Usage modes offered: guided query templates and connecting an AI assistant (MCP); a one-page PDF overview is linked.
- WOBD's own AI-assistant page, **`https://apps.okn.us/wobd/mcp`** ("Connect an AI assistant"): "Built on the mcp-proto-okn project; see the unified server documentation for the full tool list and design" and "Point Claude, ChatGPT, VS Code, or another MCP-capable client at the hosted Proto-OKN endpoint." No WOBD-specific MCP URL is shown on that page (scraped 2026-09-25) — it uses the standard hosted MCP endpoint (§8).
- Underlying HTTP API: **[NOT DOCUMENTED]** — the page is a JS app; no API endpoints are exposed in its server-rendered HTML and no docs mention a WOBD REST API.

---

## 10. Misc surfaces

| Surface | URL | Status |
|---|---|---|
| TPF browser UI | `https://apps.okn.us/ldf/` | CONFIRMED (query-page.md, fabric.md) |
| okn.us hub | `https://okn.us/` | CONFIRMED |
| Crosswalks catalog | `https://okn.us/crosswalks` | CONFIRMED — "162 verified crosswalks" (live count, 2026-09-25) |
| AI-assistant search | `https://okn.us/search` | JS-only page shell; hub says "Configure the mcp-okn MCP server in Claude, ChatGPT, or another compatible AI assistant" — i.e. search = MCP, no separate HTTP API documented → [NOT DOCUMENTED] beyond MCP |
| Sample Query Library | `https://registry.okn.us/query/sample-query-library/` | CONFIRMED (static docs page; ~180 KB of example queries) |
| Contribute compute | `https://okn.us/contribute-compute/` | CONFIRMED (see `contribute.md`) |
| Registry query tool | `https://registry.okn.us/query/query-page/` | CONFIRMED (docs page; the actual tool is `https://apps.okn.us`) |

---

## 11. Verification log (live probes, 2026-09-25)

| Probe | Result |
|---|---|
| `GET https://apps.okn.us/federation/sparql?query=SELECT * WHERE {?s ?p ?o} LIMIT 1` | 200 `application/sparql-results+json` |
| `GET https://apps.okn.us/spoke-okn/sparql?query=... LIMIT 2` | 200 `application/sparql-results+json` |
| `GET https://apps.okn.us/okn-void/sparql?query=... LIMIT 1` | 200 `application/sparql-results+json` |
| `GET https://apps.okn.us/ldf/spoke-okn?predicate=...#type` (`Accept: application/trig`) | 200 Trig fragment (hydra pagination) |
| `POST https://apps.okn.us/embeddings/query` (body per docs) | 200 JSON `{"results":[...]}` |
| `GET https://apps.okn.us/embeddings/query` | 405 Method Not Allowed |
| `GET https://apps.okn.us/embeddings/openapi.json`, `.../docs` | 404 |
| `GET https://apps.okn.us/okn-mcp-dev/mcp` | 406 JSON-RPC `-32600` "Client must accept text/event-stream" |

## 12. Explicitly [NOT DOCUMENTED] summary

- Authentication/API keys for SPARQL, TPF, federation, embeddings, MCP (public, undocumented).
- Rate limits on any endpoint.
- `help/apis/`, `help/file-formats/`, `help/validation-checklist/` pages: stubs (title only) — content not yet written upstream.
- Public bulk download/export of registered graph data files.
- Registry REST/JSON API (only `kgs.yaml` + GitHub repo are machine-readable).
- WOBD underlying API.
- Registry entry metadata schema is **not enforced/validated** upstream (fabric.md: "this schema is not currently enforced (it should be)… treat fields as conventional").
