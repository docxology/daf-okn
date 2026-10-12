# Frequently Asked Questions

## Architecture and workflow

### Why is `src/daf_okn/core/` kept free of script-level concerns?

`core/` is pure project logic: no I/O at import (the registry only touches the
network when a method is called) and no dependency on the scripts or the
manuscript. This keeps the code testable with zero mocks and the graph logic
reusable in any Python environment.

### What is the "thin orchestrator" pattern?

Files in `scripts/` should not implement project behavior. They should:

- Import functions from `src/`.
- Coordinate pipeline stages (calling those functions).
- Delegate side-effects (file I/O, logging) to `src/` helpers.
- Write outputs to `output/`.

If you find yourself computing a metric or serializing RDF inside `scripts/`,
move it to `src/` and add a test.

### Why are mocks forbidden?

Mocking tests that a function *was called* instead of that it produced
the *correct result*. Pure functions can be tested with real inputs and
expected outputs. Mocks give a false sense of correctness and break the
reproducibility guarantee.

## Testing and coverage

### Why 90% coverage? Can I lower it?

The coverage gate ensures `src/` logic is thoroughly exercised. Lowering
the gate compromises the project's authority. If coverage drops, it
signals missing tests — add them, don't lower the gate.

### My new function lowered coverage. What now?

Write unit tests for the new function before or immediately after adding
it. Follow the existing test classes in `tests/core/` (e.g.
`test_graph_metrics.py`, `test_registry.py`). Use fixed `GraphDocument`
fixtures and assert structural properties (density, component counts,
invariant problems).

### Do I need to test `scripts/`?

`scripts/` is tested via smoke tests that run the real commands
(`tests/analysis/test_scripts_smoke.py`). They invoke the scripts and assert
real output files appear. See [`testing_philosophy.md`](testing_philosophy.md).

## Graphs and the OKN registry

### How do I query a graph?

Use `scripts/pull_registry.py` to list the catalog and snapshot it to
`kgs.yaml`, or to run a per-graph or federation SPARQL query. Programmatically,
`OKNRegistry` (`src/daf_okn/core/registry.py`) exposes `list_graphs`,
`get_graph`, `sparql`/`sparql_rows` (per-graph, federation, VoID endpoints),
TPF fragments, and `embedding_search`; it raises `RegistryError` on HTTP ≥ 400
or malformed responses.

### Where do manuscript numbers come from?

`scripts/z_generate_manuscript_variables.py` calls
`src/daf_okn/core/manuscript_variables.py::generate_variables()`, which reads
`manuscript/config.yaml` and `output/data/graph_report.json` and builds the
flat `{{TOKEN}}` map (`NODE_COUNT`, `EDGE_COUNT`, `DENSITY_PCT`,
`WEAKLY_CONNECTED_COMPONENTS`, `STRONGLY_CONNECTED_COMPONENTS`,
`MEAN_DEGREE`, `TRIANGLE_COUNT`, `TOP_NODE_LABEL`,
`TOP_NODE_CENTRALITY`, `GRAPH_NAME`, plus config and environment tokens).
The map is written to `output/data/manuscript_variables.json`; substitute it
into `manuscript/*.md` with your own rendering toolchain — no hardcoded numbers
in prose.

### Does the pipeline need network access?

Stage 1 (registry pull via `OKNRegistry`) and the connector search
(`scripts/08_connector_search.py`) do. The cognitive export, analysis,
figures, dashboard, contribution packaging (`09_provenance_record.py`), and
variable hydration run offline. `10_research_workflow.py` skips stages 2–3 by
design when no cognitive repo/graph is configured.

### Where does the registry catalog live?

`kgs.yaml` is the single machine-readable registry catalog — 45 graph entries
(shortname, title, description, sparql, tpf, stats, funding, contact,
frink-options). No registry REST API is documented upstream; the entry
metadata schema is "not enforced upstream; treat fields as conventional".
Bulk download, SPARQL auth/rate limits, and the WOBD API are [NOT DOCUMENTED].

## Manuscript and rendering

### How do I add a new figure?

1. Add a generator function to `src/daf_okn/figures/network_figure.py`
   (`plot_network`, `network_figure_bytes`, `plot_graph_catalog`) and wire it
   through `scripts/10_research_workflow.py` or a sibling script that writes a
   PNG to `output/figures/` with a fixed filename (e.g.
   `cognitive_network.png`).
2. In the manuscript results section, add a Pandoc image line:
   ```markdown
   ![Caption text.](../output/figures/cognitive_network.png){#fig:new_label}
   ```
3. Reference it in prose using Pandoc-crossref:
   `See [@fig:new_label] for the result.`
4. Update [`syntax_guide.md`](syntax_guide.md) with the new figure label
   and generator.
5. Re-run the workflow (analysis, variables) and re-render.

### What are `{{VARIABLE}}` tokens and why use them?

Tokens inject dynamic values (config parameters, computed results) into
the manuscript without hard-coding. They keep the prose synchronized
with the analysis outputs. The variable generator
(`scripts/z_generate_manuscript_variables.py`) reads `config.yaml` and
`output/data/graph_report.json`, and writes a `{TOKEN: value}` dictionary to
`output/data/manuscript_variables.json`. Substituting the tokens into the
chapters is left to your rendering toolchain.

See [`syntax_guide.md`](syntax_guide.md) for the canonical token list.

### A token is not being resolved — `{{MY_TOKEN}}` appears in the rendered document

See [`troubleshooting.md`](troubleshooting.md#literal-token_name-appears-in-the-rendered-output).

### Does this repository render a PDF?

No. It produces the variables JSON, the resolved chapters and the figures; PDF/HTML rendering is left
to whatever Markdown/Pandoc toolchain you use.

## Common pitfalls

### My test uses `unittest.mock` and coverage dropped

Replace the mock with real data. Mocks are forbidden. Write a test that
calls the actual function with a fixed `GraphDocument` and asserts the
structural result.

### I added a test and the count changed. Is that OK?

Yes. The count will vary as tests are added or removed. What matters is
**≥ 90% coverage** on `src/` and **all** tests passing.

### The analysis script runs but `output/figures/` is empty

Check that the script completed successfully (exit code 0). Look for
errors in the command output. Ensure you ran the
script with `uv run` from the repository root so imports resolve
correctly. In `10_research_workflow.py`, figure stages are skipped when no
cognitive repo/graph is configured — that skip is by design, not a failure.

## See also

- [`quickstart.md`](quickstart.md) — basic commands.
- [`troubleshooting.md`](troubleshooting.md) — symptom-driven recipes.
- [`output_conventions.md`](output_conventions.md) — output regeneration rules.
- [`syntax_guide.md`](syntax_guide.md) — Pandoc-crossref syntax and token list.
- [`../manuscript/AGENTS.md`](../manuscript/AGENTS.md) — token protocol and figure list.
