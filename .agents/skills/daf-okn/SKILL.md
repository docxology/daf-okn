---
name: daf-okn
description: DAF-OKN — pull, analyze, visualize, and contribute to the Open Knowledge Network (okn.us); thin-orchestrator conventions, graph metrics, and dashboard.
version: 0.2.0
author: docxology
license: MIT
tags: [okn, code, knowledge-graphs, thin-orchestrator]
---

# daf-okn

Project-scoped skill for the DAF-OKN project. Load this when working inside
the project.

## When to Use

- Working inside the `daf_okn` package — running scripts, editing source, or
  regenerating outputs.
- Building OKN registry pull/analyze/visualize/contribute workflows.
- Validating that the project's contracts (thin-orchestrator scripts, no-mocks
  testing) still hold after changes.

## Quick Reference

```bash
# From the repository root
uv run pytest tests --cov=src --cov-fail-under=90
uv run python scripts/00_preflight.py
uv run python scripts/10_research_workflow.py --cognitive-repo <vault>
uv run python scripts/09_provenance_record.py --graph output/data/cognitive_kg.json
uv run python scripts/z_generate_manuscript_variables.py   # --allow-draft for drafts
uv run python scripts/build_dashboard.py --graph output/data/cognitive_kg.json
```

## Pitfalls

- **Keep scripts thin.** Business logic belongs in `src/`, not in
  `scripts/`.
- **No mocks.** All tests must use real data, real files, and real
  computation.
- **Outputs are disposable.** Never hand-edit `output/` — regenerate from
  source and config.
- **`RegistryError` is expected offline.** Stage 1 (registry pull) and
  connector search need network; everything else runs offline. Work from a
  prior `kgs.yaml` snapshot with `pull_registry.py --kgs-path` when offline.
- **Strict hydration needs `graph_report.json`.** Run analysis first, or
  pass `--allow-draft` for `"N/A"` sentinels.
- **Run from the repo root.** Commands assume the repository root as working
  directory unless the child `AGENTS.md` states otherwise.

## Cross-refs

- Project contract: [`AGENTS.md`](../../../AGENTS.md)
- README: [`README.md`](../../../README.md)
- TODO: [`TODO.md`](../../../TODO.md)
