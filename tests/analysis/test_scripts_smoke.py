"""Smoke tests for the daf-okn pipeline scripts (network stages excluded).

Scripts that require live OKN network access (``08_connector_search.py``,
``10_research_workflow.py`` stage 1) are only exercised via ``--help`` here;
their logic is covered by the module-level unit suites. Everything runnable
offline (preflight, API reference generation, manuscript-variable hydration,
contribution packaging + provenance receipt) is run end to end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import generate_api_docs as api_docs_mod  # noqa: E402


def _run(
    # 300s: subprocess startup re-reads all site-packages metadata on cold disk
    script: str,
    *args: str,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run a scripts/ CLI with the project cwd and captured output."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_generate_api_docs_writes_reference(tmp_path: Path) -> None:
    """generate_api_docs.py introspects the real daf-okn modules."""
    result = _run("generate_api_docs.py", "--project-root", str(tmp_path))
    assert result.returncode == 0, result.stderr or result.stdout
    api_ref = tmp_path / "output" / "docs" / "api_reference.md"
    assert api_ref.is_file()
    body = api_ref.read_text(encoding="utf-8")
    # The reference must cover the real graph-era modules, not the optimizer era.
    for module_name in (
        "daf_okn.core.graph",
        "daf_okn.core.registry",
        "daf_okn.core.invariants",
        "daf_okn.core.cognitive_adapter",
        "daf_okn.core.contribute",
        "daf_okn.analysis.graph_metrics",
        "daf_okn.analysis.pipeline",
        "daf_okn.figures.network_figure",
        "daf_okn.dashboard.dashboard",
    ):
        assert module_name in body
    assert "OKNRegistry" in body
    assert "run_analysis" in body
    assert "GraphDocument" in body
    assert "gradient_descent" not in body.lower()


def test_preflight_script_passes_with_dependency_stack() -> None:
    """00_preflight.py reports the daf-okn dependency + config checks."""
    result = _run("00_preflight.py")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "[ok] import daf_okn.core.graph" in result.stdout
    assert "[ok] import daf_okn.analysis.pipeline" in result.stdout
    assert "[ok] manuscript/config.yaml parses" in result.stdout


def test_preflight_detects_missing_config(tmp_path: Path) -> None:
    """An empty project root fails preflight on the config check."""
    from importlib import import_module

    preflight = import_module("00_preflight")
    ok, lines = preflight.run_preflight(tmp_path)
    assert not ok
    assert any("manuscript/config.yaml" in line for line in lines)


def test_z_generate_manuscript_variables_allow_draft(tmp_path: Path) -> None:
    """Draft mode hydrates the JSON without requiring the graph report."""
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / "config.yaml").write_text(
        "paper:\n  title: Isolated smoke fixture\n", encoding="utf-8"
    )
    result = _run(
        "z_generate_manuscript_variables.py", "--allow-draft", "--project-root", str(tmp_path)
    )
    assert result.returncode == 0, result.stderr or result.stdout
    variables_path = tmp_path / "output" / "data" / "manuscript_variables.json"
    assert variables_path.is_file()
    variables = json.loads(variables_path.read_text(encoding="utf-8"))
    assert set(variables) >= {
        "CONFIG_TITLE",
        "NODE_COUNT",
        "EDGE_COUNT",
        "DENSITY_PCT",
        "TOP_NODE_LABEL",
    }
    assert variables["CONFIG_TITLE"]
    # Values must agree with whatever report is present (or the draft sentinel).
    report_path = tmp_path / "output" / "data" / "graph_report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert variables["NODE_COUNT"] == str(report["metrics"]["node_count"])
    else:
        assert variables["NODE_COUNT"] == "N/A"
    # Chapters are resolved into output/manuscript/ (none exist in this fixture).
    assert (tmp_path / "output" / "manuscript").is_dir()


def test_provenance_record_packages_graph(tmp_path: Path) -> None:
    """09_provenance_record.py packages a graph and writes a hashed receipt."""
    graph_path = tmp_path / "testkg.json"
    document = {
        "name": "testkg",
        "nodes": [
            {"id": "n1", "title": "Node One", "node_type": "concept", "attributes": {}},
            {"id": "n2", "title": "Node Two", "node_type": "concept", "attributes": {}},
        ],
        "edges": [
            {
                "source": "n1",
                "target": "n2",
                "relation": "related",
                "origin": "explicit",
            }
        ],
        "metadata": {
            "entry": {
                "shortname": "testkg",
                "title": "Test KG",
                "description": "A two-node test graph.",
                "homepage": "https://example.org/testkg",
                "contacts": [{"label": "Alice", "email": "alice@example.org"}],
            }
        },
    }
    graph_path.write_text(json.dumps(document), encoding="utf-8")
    out_dir = tmp_path / "provenance"
    result = _run("09_provenance_record.py", "--graph", str(graph_path), "--out-dir", str(out_dir))
    assert result.returncode == 0, result.stderr or result.stdout
    receipt_path = out_dir / "provenance_record.json"
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["problems"] == []
    assert receipt["graph"] == "testkg"
    artifacts = receipt["artifact_sha256"]
    assert any(name.endswith(".nq") for name in artifacts)
    assert all(len(digest) == 64 for digest in artifacts.values())
    assert (out_dir / "package" / "registry" / "docs" / "registry" / "kgs" / "testkg.md").is_file()


def test_variable_generation_strict_missing_report_fails(tmp_path: Path) -> None:
    """An isolated incomplete input cannot emit a successful research artifact."""
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / "config.yaml").write_text(
        "paper:\n  title: Missing analysis fixture\n", encoding="utf-8"
    )
    result = _run("z_generate_manuscript_variables.py", "--project-root", str(tmp_path))
    assert result.returncode == 1
    assert not (tmp_path / "output" / "data" / "manuscript_variables.json").exists()


def test_connector_search_help_mentions_registry() -> None:
    """Connector search exposes registry CLI options without making live requests."""
    result = _run("08_connector_search.py", "--help")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "--kgs-path" in result.stdout
    assert "registry" in result.stdout.lower()


def test_research_workflow_help_lists_stages() -> None:
    """10_research_workflow.py exposes the pull -> export -> analyze chain."""
    result = _run("10_research_workflow.py", "--help")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "--cognitive-repo" in result.stdout
    assert "--graph" in result.stdout


def test_run_api_doc_generation_writes_custom_module_subset(tmp_path: Path) -> None:
    """API generation writes to the given root and honors a module subset."""
    project_root = tmp_path / "proj"
    project_root.mkdir(parents=True)
    result = api_docs_mod.run_api_doc_generation(project_root, modules=("daf_okn.core.graph",))
    api_ref = Path(result["api_reference"])
    assert api_ref == project_root / "output" / "docs" / "api_reference.md"
    assert api_ref.is_file()
    body = api_ref.read_text(encoding="utf-8")
    assert "GraphDocument" in body
    assert "OKNRegistry" not in body
