# docs/ — Project Documentation

> **Operational rulebook** for the daf-okn project

**Quick Reference:** [Agent Instructions](agent_instructions.md) | [Architecture](architecture.md) | [Testing](testing_philosophy.md) | [Rendering](rendering_pipeline.md) | [Style](style_guide.md) | [Syntax](syntax_guide.md) | [Index](AGENTS.md)

## Purpose

The `docs/` directory contains the behavioral and architectural rules that govern modifications to the daf-okn project. Every document here is a hard constraint — not a suggestion. The authoritative file index (including this `README.md` and `AGENTS.md`) lives in [`AGENTS.md`](AGENTS.md).

## Contents

| File | Purpose | Audience |
|---|---|---|
| [`agent_instructions.md`](agent_instructions.md) | 7 hard rules for AI agents; verification checklist | AI agents, all developers |
| [`architecture.md`](architecture.md) | Layer table, dependency direction, forbidden patterns, how-to-add-a-capability | Developers |
| [`stack-integration.md`](stack-integration.md) | Local artifact status, Sidecar foothold and separate native acceptance evidence | Stack consumers, agents |
| [`testing_philosophy.md`](testing_philosophy.md) | Zero-mock policy, test-file inventory, coverage mechanics, the gate-vs-exit-code rule (live counts → `uv run pytest tests/ --collect-only -q`) | Developers, testers |
| [`rendering_pipeline.md`](rendering_pipeline.md) | Research workflow; manuscript variables; rendering notes; config.yaml controls | Content authors, developers |
| [`style_guide.md`](style_guide.md) | 7 rules: Zero-Mock, Module Layering, Thin Orchestrator, Show-Not-Tell, Explicit Paths, Type Hints, Error Messages | Developers |
| [`syntax_guide.md`](syntax_guide.md) | Markdown links, LaTeX refs, all `{{VARIABLE}}` tokens, figure label registry | Content authors |
| [`output_conventions.md`](output_conventions.md) | Output directory layout, what's disposable, regeneration rules | Developers |
| [`output_inventory.md`](output_inventory.md) | Full pipeline artifact inventory (generator + stage) | Developers |
| [`forking_guide.md`](forking_guide.md) | Fork workflow and drift-check guidance | Developers, agents |
| [`troubleshooting.md`](troubleshooting.md) | Diagnosed failures incl. unresolved tokens and "PASSED but 0 tests", with fix commands | Developers |
| [`quickstart.md`](quickstart.md) | Minimal run commands to first deliverable | New users |
| [`faq.md`](faq.md) | Recurring questions: architecture, testing, manuscript | All |
| [`AGENTS.md`](AGENTS.md) | Technical index of this `docs/` folder; verification commands | Developers, agents |

## Quick Navigation

### Before Modifying Any Code

1. Read **[Agent Instructions](agent_instructions.md)** — 7 rules and the verification checklist
2. Read **[Architecture](architecture.md)** — understand layer boundaries before touching file structure
3. Read **[Testing Philosophy](testing_philosophy.md)** — understand zero-mock constraint before writing tests

### Before Editing Manuscript Files

1. Read **[Rendering Pipeline](rendering_pipeline.md)** — understand the research workflow and how manuscript variables are produced
2. Read **[Syntax Guide](syntax_guide.md)** — complete `{{VARIABLE}}` token list and figure label registry

### Before Writing Source Code

1. Read **[Style Guide](style_guide.md)** — 7 rules covering mocks, imports, error messages, type hints

## Using this project as a reference

`daf-okn` keeps its layers separated so each part can be read, tested, and
forked independently. Mirror these invariants when building a
new project — they are what the repo's gates enforce:

| Invariant | Where it's taught | How it's enforced |
|---|---|---|
| Thin-orchestrator: `scripts/` only I/O + orchestration, logic in `src/daf_okn/` | [`architecture.md`](architecture.md), [`style_guide.md`](style_guide.md) | code review |
| Zero mocks: real data, `tmp_path`, injected session stubs | [`testing_philosophy.md`](testing_philosophy.md) | `grep -rn "unittest.mock\|MagicMock\|@patch" --include='*.py' tests/` |
| ≥90% project coverage on `src/` | [`testing_philosophy.md`](testing_philosophy.md) | `--cov-fail-under=90` (canonical command below) |
| `manuscript/config.yaml` declares every `{{TOKEN}}` | [`rendering_pipeline.md`](rendering_pipeline.md), [`syntax_guide.md`](syntax_guide.md) | `test_all_manuscript_tokens_are_generated` |
| Deterministic outputs (fixed seeds); everything in `output/` regeneratable | [`output_conventions.md`](output_conventions.md) | reproducibility checks |

**Prerequisite to know:** the test gate is the **direct** command below (a
green exit with 0 collected tests is not a pass). See
[`troubleshooting.md`](troubleshooting.md).

## Verification Commands

```bash
# Tests pass + coverage ≥90%
uv run pytest tests/ \
    --cov=src --cov-fail-under=90 -q

# No mocks in tests/
grep -rn "unittest.mock\|MagicMock\|@patch" --include='*.py' tests/ || echo "Clean"
```

## See Also

- [../AGENTS.md](../AGENTS.md) — Full project documentation (API reference, known issues, complete directory map)
- [../README.md](../README.md) — Project quick start
- [../manuscript/AGENTS.md](../manuscript/AGENTS.md) — Manuscript directory rules and `{{VARIABLE}}` protocol
- [output_conventions.md](output_conventions.md) — Output directory structure and regeneration
