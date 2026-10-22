"""Real-file observations and stale/malformed evidence negative controls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from daf_okn.analysis.artifact_status import inspect_artifacts
from daf_okn.analysis.pipeline import run_analysis
from daf_okn.cli import main
from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord


@pytest.fixture
def artifacts(tmp_path: Path) -> tuple[Path, Path]:
    """A valid graph with its actual pipeline report."""
    graph = GraphDocument(
        name="status-probe",
        nodes=[NodeRecord("a", "A"), NodeRecord("b", "B"), NodeRecord("c", "C")],
        edges=[EdgeRecord("a", "b"), EdgeRecord("b", "c")],
    )
    path = graph.save_json(tmp_path / "graph.json")
    report = run_analysis(graph, tmp_path)
    return path, Path(report["report_path"])


def test_status_cli_observes_bytes_without_changing_files(artifacts, capsys):
    """A passing observation identifies bytes and leaves the evidence unchanged."""
    graph, report = artifacts
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in artifacts}

    code = main(["status", "--graph", str(graph), "--report", str(report)])

    observation = json.loads(capsys.readouterr().out)
    assert code == 0
    assert observation["status"] == "pass"
    assert observation["graph"]["sha256"] == hashlib.sha256(before[graph][0]).hexdigest()
    assert observation["report"]["sha256"] == hashlib.sha256(before[report][0]).hexdigest()
    assert observation["native_gate"] == "not_run"
    assert observation["sidecar"] == observation["registry_acceptance"] == "not_checked"
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in artifacts} == before


def test_omitted_report_is_unassessed(artifacts):
    """Graph validity alone cannot imply an analysis report was inspected."""
    observation = inspect_artifacts(artifacts[0])
    assert observation["status"] == "pass"
    assert observation["report"] is None


@pytest.mark.parametrize("field", ["name", "nodes", "edges"])
@pytest.mark.parametrize("value", [None, {}, 1])
def test_wrong_graph_field_types_cannot_pass(artifacts, field, value):
    """The model's coercions cannot bless malformed serialized graph fields."""
    graph, _ = artifacts
    payload = json.loads(graph.read_text())
    payload[field] = value
    graph.write_text(json.dumps(payload))

    observation = inspect_artifacts(graph)

    assert observation["status"] == "fail"
    assert observation["graph"]["problems"]


@pytest.mark.parametrize("field", ["graph_name", "stats", "problems", "metrics"])
def test_report_mismatch_is_refused(artifacts, field):
    """Every measured report field must agree with current computation."""
    graph, report = artifacts
    payload = json.loads(report.read_text())
    payload[field] = "forged"
    report.write_text(json.dumps(payload))

    observation = inspect_artifacts(graph, report)

    assert observation["status"] == "fail"
    assert observation["report"]["problems"]


def test_same_size_graph_with_changed_structure_refuses_stale_report(artifacts):
    """Counts alone cannot bless a report after the edge structure changes."""
    graph, report = artifacts
    payload = json.loads(graph.read_text())
    payload["edges"][1]["source"] = "a"
    graph.write_text(json.dumps(payload))

    observation = inspect_artifacts(graph, report)

    assert observation["status"] == "fail"
    assert any("metrics" in problem for problem in observation["report"]["problems"])


@pytest.mark.parametrize("target", ["graph", "report"])
@pytest.mark.parametrize("raw", ["[]", "{", "null", "\ud800", "{}"])
def test_malformed_inputs_fail_with_json_diagnostics(artifacts, target, raw, capsys):
    """Malformed files are diagnosed through the actual command surface."""
    graph, report = artifacts
    path = graph if target == "graph" else report
    path.write_bytes(raw.encode("utf-8", errors="surrogatepass"))

    code = main(["status", "--graph", str(graph), "--report", str(report)])

    assert code == 1
    observation = json.loads(capsys.readouterr().out)
    assert observation["status"] == "fail"
    assert observation[target]["problems"]


@pytest.mark.parametrize("target", ["graph", "report"])
def test_missing_input_is_unavailable_and_cannot_pass(artifacts, target):
    """A missing requested input retains a null digest and a failing verdict."""
    graph, report = artifacts
    (graph if target == "graph" else report).unlink()

    observation = inspect_artifacts(graph, report)

    assert observation["status"] == "fail"
    assert observation[target]["sha256"] is None
    assert observation[target]["problems"]


def test_invalid_graph_cannot_reuse_passing_report(artifacts):
    """A dangling endpoint fails before metrics can mask invalid structure."""
    graph, report = artifacts
    payload = json.loads(graph.read_text())
    payload["edges"][0]["target"] = "missing"
    graph.write_text(json.dumps(payload))

    observation = inspect_artifacts(graph, report)

    assert observation["status"] == "fail"
    assert observation["graph"]["problems"]
    assert observation["report"]["sha256"] is None


def test_boolean_cannot_replace_numeric_measurement(artifacts):
    """Python's True == 1 must not admit an incorrectly typed metric."""
    graph, report = artifacts
    payload = json.loads(report.read_text())
    payload["metrics"]["weakly_connected_components"] = True
    report.write_text(json.dumps(payload))

    observation = inspect_artifacts(graph, report)

    assert observation["status"] == "fail"
