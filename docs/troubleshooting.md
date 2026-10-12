# Troubleshooting

Symptom-driven recipes for the most common breakage modes when running this project.

## Literal `{{TOKEN_NAME}}` appears in the rendered output

**Cause.** A placeholder in `manuscript/*.md` was not substituted because
`scripts/z_generate_manuscript_variables.py` was not (re)run after the
analysis stage, or the token is not defined in `src/daf_okn/core/manuscript_variables.py::generate_variables()`.

**Fix.**

1. Run the variable-hydration stage:
   ```bash
   uv run python scripts/z_generate_manuscript_variables.py
   ```
2. Inspect the resolved values:
   ```bash
   cat output/data/manuscript_variables.json | jq .
   ```
3. Re-run `scripts/z_generate_manuscript_variables.py` so `output/manuscript/`
   is regenerated, then re-render with your own Markdown/Pandoc toolchain
   (see [`rendering_pipeline.md`](rendering_pipeline.md)).
4. If the token is still literal, add it to `generate_variables()` in
   `src/daf_okn/core/manuscript_variables.py`.

## `FileNotFoundError`: missing `graph_report.json` during variable hydration

**Cause.** `scripts/z_generate_manuscript_variables.py` runs in strict mode by default (`require_analysis_outputs=True`) and requires `output/data/graph_report.json` from the analysis stage.

**Fix.**

1. Run analysis first:
   ```bash
   uv run python scripts/analyze_graph.py --graph output/data/cognitive_kg.json --out-dir output/data
   ```
2. Re-run variable hydration:
   ```bash
   uv run python scripts/z_generate_manuscript_variables.py
   ```
3. For intentional early drafts only (tokens fall back to `"N/A"` sentinels):
   ```bash
   uv run python scripts/z_generate_manuscript_variables.py --allow-draft
   ```

## `10_research_workflow.py` skipped the export/analysis stages

**Cause.** Stages 2–3 (cognitive export → analysis) are skipped by design
when no cognitive repo or graph is configured. The script records the skip;
it is a deliberate boundary, not a failure.

**Fix.** Point the script at a vault or an existing graph:

```bash
uv run python scripts/10_research_workflow.py --cognitive-repo <vault>
# or reuse an exported graph, skipping the export stage:
uv run python scripts/10_research_workflow.py --graph output/data/cognitive_kg.json
```

The repo path can also come from the environment:
`DAF_OKN_COGNITIVE_REPO`.

## `RegistryError` from `pull_registry.py` / `OKNRegistry`

**Symptom.** `RegistryError: HTTP 404/5xx` or a malformed-response error
while listing the catalog or running SPARQL.

**Cause.** `OKNRegistry` raises `RegistryError` on HTTP ≥ 400 or malformed
responses from the OKN endpoints (`apps.okn.us`, `registry.okn.us`).

**Fix.**

1. Confirm network access to the endpoints (stage 1 and connector search are
   the network-dependent stages).
2. Validate the catalog snapshot:
   ```bash
   uv run python -c "import yaml; yaml.safe_load(open('kgs.yaml'))"
   ```
3. Work offline from a prior snapshot:
   ```bash
   uv run python scripts/pull_registry.py --kgs-path kgs.yaml
   ```
4. Upstream auth/rate limits are [NOT DOCUMENTED]; if a 403/429 persists,
   retry later rather than assuming a client bug.

## `09_provenance_record.py` exits 1 with package problems

**Cause.** `contribute.validate_package()` reported problems in the
contribution package (missing metadata, malformed graph, etc.).

**Fix.**

1. Read the recorded problems:
   ```bash
   cat output/data/provenance/provenance_record.json | jq .problems
   ```
2. Fix the source graph or registry-entry frontmatter, then re-run:
   ```bash
   uv run python scripts/09_provenance_record.py --graph <graph.json>
   ```

## matplotlib figures hang or fail on a headless machine

**Cause.** Matplotlib tried to open a display window.

**Fix.** Force the non-interactive backend before running scripts or tests:

```bash
export MPLBACKEND=Agg
uv run python scripts/10_research_workflow.py --cognitive-repo <vault>
```

`tests/conftest.py` pins this automatically; scripts rely on the environment.

## `uv` command not found

**Fix.** Install `uv` via the canonical installer (`uv`-only tooling; never
bootstrap `uv` through `pip`):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Homebrew (macOS)
brew install uv
```

Make sure `~/.local/bin` (or the install location) is on your `PATH`.

## Coverage gate fails (under 90%)

**Fix.**

1. Find which lines are uncovered:
   ```bash
   uv run pytest tests/ \
       --cov=src \
       --cov-report=term-missing -v
   ```
2. Add tests covering the missing branches.
3. Re-run until coverage ≥ 90% and all tests pass.

## Script fails to import `daf_okn`

**Symptom.** `ModuleNotFoundError: No module named 'daf_okn'`.

**Fix.** Run from the repository root through `uv run` (or install the package with `uv sync`):

```bash
uv run python scripts/analyze_graph.py --graph output/data/cognitive_kg.json
```

## YAML parse error in `manuscript/config.yaml`

**Common mistakes.**

- Indentation uses tabs instead of spaces.
- Trailing commas (JSON style) are invalid in YAML.
- Unclosed quotes or brackets.

**Fix.** Validate the file before running:

```bash
uv run python -c "import yaml; yaml.safe_load(open('manuscript/config.yaml'))"
```

## Preflight failures (`00_preflight.py` exits 1)

**Cause.** The preflight script checks Python ≥ 3.10, required dependency
imports (`yaml`, `requests`, `networkx`, `rdflib`, `matplotlib`, plus
`daf_okn.core.graph`/`registry` and `daf_okn.analysis.pipeline`), and that
`manuscript/config.yaml` parses.

**Fix.**

1. Run `uv sync` at the repository root.
2. Re-run `uv run python scripts/00_preflight.py` and address the first
   reported check failure.

## Tests report PASSED but ran 0 tests / 0.0% coverage

**Symptom:** pytest exits 0 but reports no collected tests or 0.0% coverage.

**Cause:** the interpreter in use lacks `pytest` (for example a `.venv` made by
`uv venv` without `uv sync`), or tests were not collected from the right
directory. **A green exit with zero collected tests is not a pass.**

**Fix:**

1. Run the gate directly from the repository root:
   ```bash
   uv run pytest tests/ \
     --cov=src --cov-fail-under=90
   ```
2. Or `uv sync` so the environment has the test dependencies.
3. Always confirm **collected > 0 AND coverage >= 90%** - never exit code alone.

## See also

- [`output_conventions.md`](output_conventions.md) — output directory layout and regeneration rules.
- [`rendering_pipeline.md`](rendering_pipeline.md) — manuscript variables, rendering notes, and config controls.
- [`syntax_guide.md`](syntax_guide.md) — manuscript token and cross-reference syntax.
- [`quickstart.md`](quickstart.md) — basic run commands.
- [`faq.md`](faq.md) — frequently asked questions.
