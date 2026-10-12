"""Tests for ``daf_okn.core.manuscript_variables`` (graph-era hydration).

``generate_variables`` hydrates the manuscript ``{{TOKEN}}`` map from
``manuscript/config.yaml`` and the graph report written by
``daf_okn.analysis.pipeline.run_analysis``. These tests exercise the fixture
config + report round trip, the ``--allow-draft`` sentinel fallbacks, the
strict ``require_analysis_outputs`` failure path, and the live cross-reference
between manuscript token usage and the generator's key set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from daf_okn.core.manuscript_variables import (  # noqa: E402
    _GRAPH_TOKENS,
    REPORT_PATH,
    _graph_token_strings,
    generate_variables,
    save_variables,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_YAML = """\
paper:
  title: "DAF-OKN Test Title"
  subtitle: "Registry pull, analysis, contribution"
  version: "1.2.3"
authors:
  - name: "Alice Writer"
keywords: ["knowledge graph", "registry"]
"""

# Canonical shape written by daf_okn.analysis.pipeline.run_analysis (stats,
# problems, metrics blocks; metrics keys per graph_metrics.compute_metrics).
GRAPH_REPORT = {
    "graph_name": "cognitive_kg",
    "stats": {
        "node_count": 3,
        "edge_count": 2,
        "density": 0.3333333333333333,
        "directed": True,
        "component_count": 1,
    },
    "problems": [],
    "metrics": {
        "node_count": 3,
        "edge_count": 2,
        "density": 0.3333333333333333,
        "weakly_connected_components": 1,
        "strongly_connected_components": 1,
        "mean_degree": 1.3333333333333333,
        "triangles": 1,
        "top_central_nodes": [["hub_node", 0.5]],
    },
}


def _make_project(
    tmp_path: Path, *, with_report: bool = True, config_text: str = CONFIG_YAML
) -> Path:
    """Build a minimal project tree: manuscript/config.yaml (+ graph report)."""
    (tmp_path / "manuscript").mkdir(parents=True, exist_ok=True)
    (tmp_path / "manuscript" / "config.yaml").write_text(config_text, encoding="utf-8")
    if with_report:
        data_dir = tmp_path / "output" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "graph_report.json").write_text(json.dumps(GRAPH_REPORT), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------


def test_keys_constant_with_and_without_report(tmp_path: Path) -> None:
    """The full key set must not depend on data availability."""
    with_report = generate_variables(
        _make_project(tmp_path / "with"), require_analysis_outputs=False
    )
    without = generate_variables(
        _make_project(tmp_path / "without", with_report=False),
        require_analysis_outputs=False,
    )
    assert set(with_report) == set(without)
    assert set(_GRAPH_TOKENS) <= set(without)


# ---------------------------------------------------------------------------
# Report-derived tokens
# ---------------------------------------------------------------------------


def test_graph_tokens_from_fixture_report(tmp_path: Path) -> None:
    """Metric values come from the graph report's ``metrics`` block."""
    root = _make_project(tmp_path)
    variables = generate_variables(root / "manuscript" / "config.yaml")
    assert variables["GRAPH_NAME"] == "cognitive_kg"
    assert variables["NODE_COUNT"] == "3"
    assert variables["EDGE_COUNT"] == "2"
    assert variables["DENSITY_PCT"] == "33.33"
    assert variables["WEAKLY_CONNECTED_COMPONENTS"] == "1"
    assert variables["STRONGLY_CONNECTED_COMPONENTS"] == "1"
    assert variables["MEAN_DEGREE"] == "1.33"
    assert variables["TRIANGLE_COUNT"] == "1"
    assert variables["TOP_NODE_LABEL"] == "hub_node"
    assert variables["TOP_NODE_CENTRALITY"] == "0.5000"


def test_graph_token_strings_empty_top_nodes() -> None:
    """A graph without central nodes degrades the top-node pair to sentinels."""
    report = {"graph_name": "g", "metrics": {"node_count": 0, "top_central_nodes": []}}
    tokens = _graph_token_strings(report)
    assert tokens["TOP_NODE_LABEL"] == "N/A"
    assert tokens["TOP_NODE_CENTRALITY"] == "0.0000"
    assert tokens["NODE_COUNT"] == "0"


def test_graph_token_strings_without_metrics_block() -> None:
    """A report without a ``metrics`` mapping yields all sentinels."""
    tokens = _graph_token_strings({"graph_name": "g"})
    assert tokens == dict.fromkeys(_GRAPH_TOKENS, "N/A")


def test_malformed_report_json_degrades_to_draft(tmp_path: Path) -> None:
    """An unreadable report file is treated as missing (draft sentinels)."""
    root = _make_project(tmp_path, with_report=False)
    data_dir = root / "output" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "graph_report.json").write_text("{not json", encoding="utf-8")
    variables = generate_variables(
        root / "manuscript" / "config.yaml", require_analysis_outputs=False
    )
    assert all(variables[token] == "N/A" for token in _GRAPH_TOKENS)


def test_non_object_report_json_degrades_to_draft(tmp_path: Path) -> None:
    """A JSON array where a report object is expected is also treated as missing."""
    root = _make_project(tmp_path, with_report=False)
    data_dir = root / "output" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "graph_report.json").write_text("[1, 2]", encoding="utf-8")
    variables = generate_variables(
        root / "manuscript" / "config.yaml", require_analysis_outputs=False
    )
    assert variables["NODE_COUNT"] == "N/A"


# ---------------------------------------------------------------------------
# Config-derived tokens
# ---------------------------------------------------------------------------


def test_config_tokens(tmp_path: Path) -> None:
    """Title/author/keyword tokens come from ``manuscript/config.yaml``."""
    root = _make_project(tmp_path)
    variables = generate_variables(
        root / "manuscript" / "config.yaml", require_analysis_outputs=False
    )
    assert variables["CONFIG_TITLE"] == "DAF-OKN Test Title"
    assert variables["CONFIG_SUBTITLE"] == "Registry pull, analysis, contribution"
    assert variables["CONFIG_VERSION"] == "1.2.3"
    assert variables["CONFIG_FIRST_AUTHOR"] == "Alice Writer"
    assert variables["CONFIG_KEYWORDS"] == "knowledge graph, registry"


def test_config_hash_tracks_config_bytes(tmp_path: Path) -> None:
    """CONFIG_HASH is a 16-hex fingerprint and changes with the config."""
    root = _make_project(tmp_path)
    first = generate_variables(root / "manuscript" / "config.yaml", require_analysis_outputs=False)
    assert len(first["CONFIG_HASH"]) == 16
    assert all(char in "0123456789abcdef" for char in first["CONFIG_HASH"])

    config_path = root / "manuscript" / "config.yaml"
    config_path.write_text(CONFIG_YAML + "\n# touched\n", encoding="utf-8")
    second = generate_variables(config_path, require_analysis_outputs=False)
    assert second["CONFIG_HASH"] != first["CONFIG_HASH"]


def test_config_hash_sentinel_without_config(tmp_path: Path) -> None:
    """A missing config.yaml yields the CONFIG_HASH sentinel."""
    variables = generate_variables(
        tmp_path / "missing" / "config.yaml", require_analysis_outputs=False
    )
    assert variables["CONFIG_HASH"] == "N/A"


# ---------------------------------------------------------------------------
# require_analysis_outputs contract
# ---------------------------------------------------------------------------


def test_require_analysis_outputs_raises_when_report_missing(tmp_path: Path) -> None:
    """Pipeline mode must fail fast when the graph report is absent."""
    root = _make_project(tmp_path, with_report=False)
    with pytest.raises(FileNotFoundError, match="graph_report"):
        generate_variables(root / "manuscript" / "config.yaml")


def test_require_analysis_outputs_passes_with_report(tmp_path: Path) -> None:
    """Pipeline mode succeeds and hydrates real values when the report exists."""
    root = _make_project(tmp_path)
    variables = generate_variables(
        root / "manuscript" / "config.yaml", require_analysis_outputs=True
    )
    assert variables["NODE_COUNT"] == "3"


# ---------------------------------------------------------------------------
# Provenance tokens
# ---------------------------------------------------------------------------


def test_report_path_contract() -> None:
    """The hydration report location is pinned to output/data/graph_report.json."""
    assert Path("output") / "data" / "graph_report.json" == REPORT_PATH


def test_environment_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SOURCE_DATE_EPOCH pins GENERATION_TIMESTAMP for reproducible builds."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    root = _make_project(tmp_path)
    variables = generate_variables(
        root / "manuscript" / "config.yaml", require_analysis_outputs=False
    )
    assert variables["GENERATION_TIMESTAMP"] == "2023-11-14T22:13:20Z"
    assert variables["PYTHON_VERSION"].count(".") >= 1
    assert "unknown" not in {
        variables["NETWORKX_VERSION"],
        variables["MATPLOTLIB_VERSION"],
    }
    assert variables["PLATFORM"]


# ---------------------------------------------------------------------------
# save_variables round trip
# ---------------------------------------------------------------------------


def test_save_variables_round_trip(tmp_path: Path) -> None:
    """save_variables persists the exact generated mapping as JSON."""
    root = _make_project(tmp_path)
    variables = generate_variables(root / "manuscript" / "config.yaml")
    out_path = save_variables(variables, tmp_path / "vars" / "manuscript_variables.json")
    assert out_path == tmp_path / "vars" / "manuscript_variables.json"
    assert out_path.is_file()
    assert json.loads(out_path.read_text(encoding="utf-8")) == variables


# ---------------------------------------------------------------------------
# Live cross-reference: every {{TOKEN}} used in manuscript/*.md must be
# produced by generate_variables().
# ---------------------------------------------------------------------------


def test_all_manuscript_tokens_are_generated() -> None:
    """Regression guard: no prose token may lack a generator key."""
    import re

    token_pattern = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
    used: set[str] = set()
    _DOC_ONLY = frozenset({"AGENTS.md", "README.md", "SYNTAX.md"})
    for chapter in sorted((REPO_ROOT / "manuscript").glob("*.md")):
        if chapter.name in _DOC_ONLY:
            continue  # syntax guides quote {{MY_TOKEN}} placeholders, not real tokens
        used.update(token_pattern.findall(chapter.read_text(encoding="utf-8")))
    used -= {"TOKEN", "MY_TOKEN"}  # generic syntax placeholders quoted in prose
    assert used, "expected {{TOKEN}} placeholders in the manuscript chapters"
    generated = generate_variables(
        REPO_ROOT / "manuscript" / "config.yaml", require_analysis_outputs=False
    )
    missing = used - set(generated)
    assert not missing, f"manuscript tokens not produced by generate_variables(): {sorted(missing)}"


def test_write_resolved_manuscript_substitutes_known_tokens(tmp_path: Path) -> None:
    from daf_okn.core.manuscript_variables import write_resolved_manuscript

    source = tmp_path / "manuscript"
    source.mkdir()
    (source / "01_a.md").write_text(
        "Nodes: {{NODE_COUNT}}; again {{NODE_COUNT}}.", encoding="utf-8"
    )
    (source / "02_b.md").write_text(
        "Known {{NODE_COUNT}} but {{MISSING_TOKEN}}; syntax like {{TOKEN}} stays.", encoding="utf-8"
    )
    (source / "README.md").write_text("Docs quote {{NODE_COUNT}}.", encoding="utf-8")
    (source / "notes.txt").write_text("{{NODE_COUNT}} (not markdown)", encoding="utf-8")
    out = tmp_path / "out" / "manuscript"

    unresolved = write_resolved_manuscript(source, out, {"NODE_COUNT": "42"})

    assert unresolved == {"01_a.md": [], "02_b.md": ["MISSING_TOKEN"]}
    assert (out / "01_a.md").read_text(encoding="utf-8") == "Nodes: 42; again 42."
    assert (out / "02_b.md").read_text(encoding="utf-8") == (
        "Known 42 but {{MISSING_TOKEN}}; syntax like {{TOKEN}} stays."
    )
    assert sorted(p.name for p in out.iterdir()) == ["01_a.md", "02_b.md"]  # chapters only
    assert (source / "01_a.md").read_text(encoding="utf-8").startswith("Nodes: {{")  # untouched
