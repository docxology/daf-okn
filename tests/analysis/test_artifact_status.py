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


@pytest.mark.parametrize("field", ["id", "source", "target"])
@pytest.mark.parametrize("value", [None, True, False, 0, 7, 1.5, [], {}])
@pytest.mark.parametrize("with_report", [False, True])
def test_non_string_identifiers_cannot_pass(tmp_path, capsys, field, value, with_report):
    """Matching coerced endpoints and reports cannot bless a non-string identifier."""
    identifier = str(value)
    graph = GraphDocument(
        name="identifier-probe",
        nodes=[NodeRecord(identifier, "Coercible"), NodeRecord("peer", "Peer")],
        edges=[
            EdgeRecord("peer", identifier)
            if field == "target"
            else EdgeRecord(identifier, "peer")
        ],
    )
    graph_path = graph.save_json(tmp_path / "graph.json")
    report_path = Path(run_analysis(graph, tmp_path)["report_path"])
    payload = json.loads(graph_path.read_text())
    collection = "nodes" if field == "id" else "edges"
    payload[collection][0][field] = value
    graph_path.write_text(json.dumps(payload))
    paths = (graph_path, report_path)
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
    argv = ["status", "--graph", str(graph_path)]
    if with_report:
        argv.extend(["--report", str(report_path)])

    code = main(argv)

    observation = json.loads(capsys.readouterr().out)
    assert code == 1
    assert observation["status"] == "fail"
    assert observation["graph"]["problems"]
    assert observation["graph"]["sha256"] == hashlib.sha256(before[graph_path][0]).hexdigest()
    assert observation["native_gate"] == "not_run"
    assert observation["sidecar"] == observation["registry_acceptance"] == "not_checked"
    if with_report:
        assert observation["report"] == {
            "path": str(report_path),
            "sha256": None,
            "problems": [],
        }
    else:
        assert observation["report"] is None
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths} == before


@pytest.mark.parametrize("collection", ["nodes", "edges"])
@pytest.mark.parametrize("record", [None, False, 7, 1.5, "record", [], {}])
def test_malformed_graph_records_fail_with_json_diagnostics(artifacts, capsys, collection, record):
    """Non-object records and absent identifiers fail without assessing the report."""
    graph, report = artifacts
    payload = json.loads(graph.read_text())
    payload[collection][0] = record
    graph.write_text(json.dumps(payload))
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in artifacts}

    code = main(["status", "--graph", str(graph), "--report", str(report)])

    observation = json.loads(capsys.readouterr().out)
    assert code == 1
    assert observation["status"] == "fail"
    assert observation["graph"]["problems"]
    assert observation["graph"]["sha256"] == hashlib.sha256(before[graph][0]).hexdigest()
    assert observation["report"] == {"path": str(report), "sha256": None, "problems": []}
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in artifacts} == before


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
