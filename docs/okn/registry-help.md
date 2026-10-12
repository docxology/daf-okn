# OKN Registry Help — Uploading & Updating Graphs (Practical Digest)

> **Attribution and status.** This file summarises content from [okn.us](https://okn.us/), [registry.okn.us](https://registry.okn.us/) and [github.com/frink-okn/okn-registry](https://github.com/frink-okn/okn-registry), captured on 2026-09-25. It is an unofficial digest, is not endorsed by the Open Knowledge Network, FRINK or RENCI, and may be out of date. Quoted passages remain the work of their original authors; the registry site and repository are the authoritative sources, including for contact details and licence terms.


> Digest of the OKN Registry "Uploading Graphs" help documentation (https://registry.okn.us/help/).
> Sources scraped 2026-09-25; repo checkout of https://github.com/frink-okn/okn-registry (main, 2026-09-25). Live pages cross-checked against site source repo.

## Contents of this section

The help section ("Uploading Graphs") covers four topics, each a page under https://registry.okn.us/help/:

| Page | Live URL | Status |
|---|---|---|
| Uploading and Updating Graphs in the OKN (index) | https://registry.okn.us/help/ | Documented |
| Setup Your Repo in the Landing Zone | https://registry.okn.us/help/setup/ | Documented |
| Update Your Graph in the OKN | https://registry.okn.us/help/update/ | Documented |
| Update Example Queries | https://registry.okn.us/help/update-queries/ | Documented |
| Using OKN Fabric APIs | https://registry.okn.us/help/apis/ | **Stub — [NOT DOCUMENTED]** |
| Supported File Formats | https://registry.okn.us/help/file-formats/ | **Stub — [NOT DOCUMENTED]** |
| Validation checklist | https://registry.okn.us/help/validation-checklist/ | **Stub — [NOT DOCUMENTED]** |

Source for the page inventory: https://registry.okn.us/help/ (also site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/index.md and `mkdocs.yml` nav). The three stub pages render only their titles live (verified against scraped text for https://registry.okn.us/help/apis/, .../help/file-formats/, .../help/validation-checklist/); in the site source repo the files https://github.com/frink-okn/okn-registry/blob/main/docs/help/apis.md and https://github.com/frink-okn/okn-registry/blob/main/docs/help/file-formats.md contain a heading only, and https://github.com/frink-okn/okn-registry/blob/main/docs/help/validation-checklist.md is empty — (site source repo).

## 1. Prerequisite: Registry entry

The help index opens with a warning: if your graph does not yet have an entry in the registry, you must first create one. Verbatim from https://registry.okn.us/help/ (site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/index.md):

> "If your graph does not yet have an entry in okn.us's registry, then you must first create a registry entry for your graph."

- Full instructions: https://registry.okn.us/registry/contribute/
- **Shortname rules** (from https://registry.okn.us/registry/contribute/, site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/registry/contribute.md): "First choose a 'shortname' for your graph. This will be widely used as a knowledge graph identifier and as part of service URLs such as SPARQL endpoints. Keep it brief and lowercase (hyphens are okay)."
- A registry entry = a new Markdown file `<shortname>.md` in the [`docs/registry/kgs`](https://github.com/frink-okn/okn-registry/tree/main/docs/registry/kgs) folder of the [okn-registry repo](https://github.com/frink-okn/okn-registry/), submitted as a pull request. It carries YAML frontmatter (`template`, `shortname`, `title`, `description`, `stats`, `homepage`, `funding`, `sparql`, `tpf`, `frink-options` with `lakefs-repo`/`documentation-path`, `contacts`) plus a Markdown description.
- Per the `sparql`/`tpf` field warnings on https://registry.okn.us/registry/contribute/: if you have not yet uploaded data to https://repository.okn.us/ and triggered the conversion process, skip those fields — they are added once your endpoints are live.
- After the PR is accepted you proceed to https://registry.okn.us/help/setup/.

## 2. The Landing Zone: lakeFS

Source: https://registry.okn.us/help/setup/ (site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/setup.md).

- The Landing Zone is lakeFS at https://repository.okn.us/.
- **Credentials**: "an **Access Key ID** and a **Secret Acess Key**" (sic — typo is in the source). They are not self-service: "You may request these either by direct messaging Yaphet Kebede through our OKN Slack channel or by emailing the address given on the setup page (see the registry). With your request please provide the name of your dataset, that will be used to create a repository to host your data on lakeFS."
- **Repository structure**: "Every dataset hosted in the OKN will have its own lakeFS repository. Data submissions should be made by uploading the data to the develop branch of the respective repository. After uploads and commits are completed on the develop branch, the data update can be finalized by creating a merge request to the main branch."
- The update page reinforces this (https://registry.okn.us/help/update/): "Each LakeFS repository should house a single dataset to allow for independent versioning and easier maintenance" — explicitly not one repo per team.

## 3. Size limits and tool rules

Verbatim from the "File Upload Size Requirements" warning on https://registry.okn.us/help/setup/:

- "For files **less than 1G** clients can use **any of the tools** mentioned on this page to upload files."
- "For file sizes **greater than 1G** we recommend using **s3 clients (such as rclone or aws-cli)** as they support chunking large files to small manageable sizes."
- "We also recommend using **no parallelization** (this will ensure that our server is not overwhelmed)."

Tool recommendation (page intro): "We recommend uploading through the website for smaller files and using Amazon's S3 Tool for larger files or for automating the process."

## 4. Upload step-by-step: through the website

Source: https://registry.okn.us/help/setup/ (see also the lakeFS QuickStart guide linked there: https://docs.lakefs.io/quickstart/).

1. Navigate to https://repository.okn.us/
2. Enter your **Access Key ID** and **Secret Access Key** to log in.
3. Browse to your working repository.
4. "By default, your repository would be on main branch, double check to make sure that is set to `develop` branch."
5. Click the **Upload Object** button.
6. In the **Upload Object** pop-up, drag and drop a single file from your desktop, then click **Upload**. Warning from the docs: although there is a **Path** text field, "it will not recognize a file path on your local machine. So please use the drag and drop feature." Also: "**Repeat this step for each file you need to upload.**"
7. "Your upload is not complete until you commit the change to lakeFS." Open the **Uncommitted Changes** tab, verify your upload appears, click **Commit Changes**.
8. In the **Commit Changes** pop-up, enter a **Commit Message** describing the upload; the docs suggest including your name "in case multiple individuals from your team are uploading files to lakeFS. The date and time will be recorded automatically."

## 5. Upload via CLI

### 5a. s5cmd

Source: https://registry.okn.us/help/setup/ ("Upload Using s5cmd"; tool docs: https://github.com/peak/s5cmd — "a fast S3-compatible command line tool that works seamlessly with lakeFS").

1. Install or run s5cmd:
   - Local: download from https://github.com/peak/s5cmd, extract the binary, ensure it is on PATH, then verify with `s5cmd version`.
   - Docker (no local install): `docker run --rm peakcom/s5cmd version`
2. Configure credentials and lakeFS endpoint (s5cmd uses standard AWS environment variables):
   ```bash
   export AWS_ACCESS_KEY_ID=<your-access-key-id>
   export AWS_SECRET_ACCESS_KEY=<your-secret-access-key>
   export LAKEFS_ENDPOINT=https://repository.okn.us/
   ```
3. Upload:
   - Installed locally:
     ```bash
     s5cmd --endpoint-url $LAKEFS_ENDPOINT cp my-local-dataset.hdt s3://my-repo/develop/my-local-graph.hdt
     ```
   - With Docker:
     ```bash
     docker run --rm \
     -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
     -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
     -v $(pwd):/data \
     peakcom/s5cmd \
     --endpoint-url $LAKEFS_ENDPOINT \
     cp /data/my-local-dataset.hdt s3://my-repo/develop/my-local-graph.hdt
     ```
   Per the docs: "This example copies the `my-local-dataset.hdt` file to a repo called `my-repo` on the `develop` branch, renamed as `my-local-graph.hdt`. The `--endpoint-url` option ensures the command targets your lakeFS instance."
4. Commit the upload: back in the web browser, go to your repository, open the **Uncommitted Changes** tab, click **Commit Changes**, and enter an appropriate **Commit Message**.

### 5b. rclone from another storage provider (Azure, S3, …)

Source: https://registry.okn.us/help/setup/ ("Upload from other Storage providers (Azure, S3 etc...)" — worked example uses Azure Blob Storage; rclone docs: https://rclone.org/docs/). Download rclone from https://rclone.org/downloads/.

1. **Configure the Azure source remote**: run `rclone config`, type `n` to create a new remote, name it (e.g. `azureblob`), choose storage type `32` (Microsoft Azure Blob Storage), and supply `Account Name` (Azure storage account name) and `Account Key`. Save the configuration.
2. **Configure the lakeFS remote**: run `rclone config` again, type `n`, name it (e.g. `lakefs`), choose storage type `5` (S3) "and then select `31` (Other) on the next prompt". Configure with: `AWS Access Key ID` = your lakeFS access key id; `AWS Secret Access Key` = your lakeFS secret access key; "For region leave empty"; `Endpoint for S3 API`: "this is the url for lakefs https://repository.okn.us/". Follow the remaining prompts as needed and save.
3. **Verify the configuration**:
   ```bash
   rclone ls azureblob:your-container-name
   rclone ls lakefs:your-repository-name
   ```
   "If the configuration is correct, you should see the contents of your Azure Blob Storage container and lakeFS bucket."
4. **Copy the data**:
   ```bash
   rclone copy azureblob:your-container-name/path/in/container lakefs:your-repository-name/develop/location/of/file
   ```

## 6. Branching, formats, and automated workflows

Source: https://registry.okn.us/help/update/ (site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/update.md).

### Branch strategy

| Branch | Purpose | Notes |
|---|---|---|
| `main` | "Holds the final, stable dataset." | "Initial State: Contains no data on first creation." "Protected branch—only allows merge requests (no direct commits)." |
| `develop` | "Serves as the working branch for raw data." | Data owners make changes here, then merge into `main`. |
| `stable` | "Contains processed and validated datasets ready for deployment. These branches are used by Fabric's automation tools." | Naming: format `stable_vX_X_X` (e.g. `stable_v0_90_1`). Intermediary before deployment to Fabric database servers. |

### Supported input formats

From the info box on https://registry.okn.us/help/update/:

- "Single Neo4j dump files in single repository (WIP)"
- "Multiple RDF file with the following extensions : rdf, xml, ttl, nt, nq, jsonld, json, rj, trig, trix, n3"
- "Single HDT (WIP)"

"raw data to stable datasets in HDT format (preferred by the Fabric system)" — conversion happens via the automated workflows. Caution note on the same page: "Please make sure the contents of your files match standard file extensions. The automation pipelines are sensetive to file extensions." (sic).

### Workflow: merge → conversion → stable branch → tag → deploy

1. **Merge to Main**: "When raw data on the `develop` branch is merged into the `main` branch, conversion workflow is triggered." (Click the Compare icon to merge the branches.)
2. **Conversion**: the workflow processes raw data into the stable format (HDT).
3. **Stable Branch Creation**: "Upon successful processing, a new `stable` branch is created, following the `stable_v*` naming convention." "Once the ETL process is complete, the system pushes the new dataset onto a `stable` branch."
4. **Tagging**: "After successful push, the stable branch is tagged with the corresponding version number." "Tags can be automatically created after successful validation of the dataset. This ensures data reliability and minimizes manual intervention."
5. **Deployment**: "The tag on the main branch represents an official release of the dataset and will trigger deployment pipelines." "The creation of this tag initiates an automatic deployment process, loading the new dataset."

Tag naming convention: "Tags should follow the version format used in the stable branch, such as `v0_90_1` reformatted to `v0.90.1`." So stable branches use underscores (`stable_v0_90_1`) and tags use dots (`v0.90.1`).

Summary as given on the page: changes in `develop` → merge to `main` → automation triggers conversion pipelines → HDT pushed to new `stable` branch → `stable` branch automatically tagged → tag creation triggers automatic deployment.

## 7. Updating Example Queries (Fabric UI)

Source: https://registry.okn.us/help/update-queries/ (site source repo: https://github.com/frink-okn/okn-registry/blob/main/docs/help/update-queries.md). "The example queries displayed in the Fabric UI (previously called FRINK) are fetched from the frink-okn/okn-registry GitHub repository" — specifically the [`docs/registry/queries/`](https://github.com/frink-okn/okn-registry/tree/main/docs/registry/queries) directory.

Steps:

1. Go to the `frink-okn/okn-registry` repository on GitHub; locate `/docs/registry/queries/`.
2. Create or edit `.rq` files there (or in any subfolder you create). "Each `.rq` file should contain **only one** SPARQL query." The UI "scans the entire `/docs/registry/queries/` directory and its subdirectories for `.rq` files", so folder structure is organizational only.
3. Add a metadata block at the very top of each file, lines starting with `#+ `, parsed as YAML and which "must be valid". Two fields are expected:
   - `#+ summary: "Your concise description of what the query does."` (string)
   - `#+ tags: ["tag1", "tag2", "another_tag"]` (array of strings)
   - **Tags must reference the knowledge graph `shortname`** as defined in [docs/registry/kgs.yaml](https://github.com/frink-okn/okn-registry/blob/main/docs/registry/kgs.yaml).
4. Commit and push.

Example `.rq` structure from the docs:

```sparql
#+ summary: "Fetches all unique classes in the knowledge graph."
#+ tags: ["geoconnex", "sockg"]

SELECT DISTINCT ?class
WHERE {
  ?s a ?class .
}
LIMIT 100
```

Caching:

- "The Fabric UI caches requests to GitHub for **24 hours** in the browser's local storage", so new/updated queries may not appear immediately.
- Maintainers can use a "invalidate cache" button on the settings page of the Fabric UI. Caveat: "This cache invalidation feature may not yet be deployed on the Sterling instance. To use it, you will need to test on the GitHub Pages deployment: https://frink-okn.github.io/frink-query-ui"

Contact for further questions: "okn-frink at renci.org".

## 8. What is NOT documented

These topics have stub pages (title only) as of capture date 2026-09-25 — content is [NOT DOCUMENTED]:

- **Account self-service / requesting lakeFS credentials**: no self-service path is documented; the only documented route is contacting Yaphet Kebede (OKN Slack DM or the email address on the setup page; see the registry) with your dataset name — see section 2.
- **Supported File Formats page**: https://registry.okn.us/help/file-formats/ renders only "Supported File Formats". Source repo file https://github.com/frink-okn/okn-registry/blob/main/docs/help/file-formats.md contains only the heading "# Supported File Formats" (site source repo). Format info actually lives in the info box on https://registry.okn.us/help/update/ (see section 6).
- **Validation checklist page**: https://registry.okn.us/help/validation-checklist/ renders only "Validation checklist"; source repo file https://github.com/frink-okn/okn-registry/blob/main/docs/help/validation-checklist.md is empty (site source repo).
- **Using OKN Fabric APIs page**: https://registry.okn.us/help/apis/ renders only "Using OKN Fabric APIs"; source repo file https://github.com/frink-okn/okn-registry/blob/main/docs/help/apis.md is empty (site source repo).
- Not covered anywhere in this help section: aws-cli-specific recipes (aws-cli is named as a recommended >1G tool but no worked example is given — [NOT DOCUMENTED]), HDT conversion tooling details, details of the validation step that gates automated tag creation.
