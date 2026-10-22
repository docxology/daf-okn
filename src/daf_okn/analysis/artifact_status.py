"""Read-only observations of graph validity and analysis report consistency."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict

from ..core.graph import GraphDocument
from ..core.invariants import graph_stats, validate_graph
from .graph_metrics import compute_metrics

__all__ = ["ArtifactObservation", "ArtifactStatus", "inspect_artifacts"]


class ArtifactObservation(TypedDict):
    """The bytes observed and diagnostics from inspecting a requested file."""

    path: str
    sha256: str | None
    problems: list[str]


class ArtifactStatus(TypedDict):
    """One observation; no repository gate or external acceptance is implied."""

    schema: str
    observed_at: str
    status: Literal["pass", "fail"]
    graph: ArtifactObservation
    report: ArtifactObservation | None
    native_gate: Literal["not_run"]
    sidecar: Literal["not_checked"]
    registry_acceptance: Literal["not_checked"]


def inspect_artifacts(graph_path: Path, report_path: Path | None = None) -> ArtifactStatus:
    """Inspect graph invariants and optionally remeasure an analysis report.

    Args:
        graph_path: Existing GraphDocument JSON file; read once for hashing/parsing.
        report_path: Optional existing output of ``run_analysis``. Its graph name,
            stats, problems and metrics must equal freshly computed values.

    Returns:
        A JSON-compatible observation with SHA-256 of the exact bytes read.
        Missing, malformed, structurally invalid or inconsistent inputs fail.
        An omitted report is unassessed. Matching metrics establish consistency,
        not full graph provenance: labels/metadata may change without metrics
        changing. Hashes identify this observation and must be rechecked on reuse.

    Example:
        ``inspect_artifacts(Path("graph.json"), Path("report/graph_report.json"))``
    """
    graph_observation: ArtifactObservation = {
        "path": str(graph_path),
        "sha256": None,
        "problems": [],
    }
    report_observation: ArtifactObservation | None = (
        {"path": str(report_path), "sha256": None, "problems": []}
        if report_path is not None
        else None
    )
    result: ArtifactStatus = {
        "schema": "daf-okn.artifact-status/1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "graph": graph_observation,
        "report": report_observation,
        "native_gate": "not_run",
        "sidecar": "not_checked",
        "registry_acceptance": "not_checked",
    }
    try:
        raw = graph_path.read_bytes()
        graph_observation["sha256"] = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError(
                f"graph {graph_path} must contain an object, got {type(payload).__name__}"
            )
        for field in ("name", "nodes", "edges"):
            if field not in payload:
                raise ValueError(f"graph {graph_path} missing required field {field!r}")
        if not isinstance(payload["name"], str):
            raise TypeError(f"graph name must be a string, got {payload['name']!r}")
        for field in ("nodes", "edges"):
            if not isinstance(payload[field], list):
                raise TypeError(f"graph {field} must be a list, got {payload[field]!r}")
        graph = GraphDocument.from_dict(payload)
        graph_observation["problems"] = validate_graph(graph)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as error:
        graph_observation["problems"].append(f"cannot inspect graph {graph_path}: {error}")
        return result
    if graph_observation["problems"]:
        return result
    if report_path is not None and report_observation is not None:
        try:
            raw = report_path.read_bytes()
            report_observation["sha256"] = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw)
            expected = {
                "graph_name": graph.name,
                "stats": graph_stats(graph),
                "problems": [],
                "metrics": compute_metrics(graph),
            }
            if not isinstance(payload, dict):
                raise TypeError(
                    f"report {report_path} must contain an object, got {type(payload).__name__}"
                )
            # WHY: JSON normalization preserves tuple/list equivalence while
            # distinguishing forged booleans from numeric measurements.
            for field, value in expected.items():
                if field not in payload or json.dumps(payload[field], sort_keys=True) != json.dumps(
                    value, sort_keys=True
                ):
                    report_observation["problems"].append(
                        f"report field {field!r} differs from current graph analysis"
                    )
        except (OSError, ValueError, TypeError, UnicodeError) as error:
            report_observation["problems"].append(f"cannot inspect report {report_path}: {error}")
        if report_observation["problems"]:
            return result
    result["status"] = "pass"
    return result
