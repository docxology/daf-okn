"""Tests for the ``daf-okn`` command line (``python -m daf_okn``).

Everything runs against real files in ``tmp_path``; no command here touches the network
(``pull`` is exercised through ``--kgs-path`` and argument handling only).
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from daf_okn import __version__
from daf_okn.cli import build_parser, main
from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_VAULT = PROJECT_ROOT / "tests" / "fixtures" / "cognitive"

KGS = {
    "kgs": [
        {"shortname": "zeta", "title": "Zeta graph", "sparql": "https://example.org/zeta/sparql"},
        {"shortname": "alpha", "title": "Alpha graph"},
    ]
}


def _graph_file(tmp_path: Path) -> Path:
    doc = GraphDocument(
        name="mini-kg",
        nodes=[
            NodeRecord(id="area/a", title="A"),
            NodeRecord(id="area/b", title="B"),
            NodeRecord(id="area/c", title="C"),
        ],
        edges=[
            EdgeRecord("area/a", "area/b", "implements"),
            EdgeRecord("area/b", "area/c", "related"),
        ],
    )
    return doc.save_json(tmp_path / "mini.json")


def _kgs_file(tmp_path: Path) -> Path:
    path = tmp_path / "kgs.yaml"
    path.write_text(yaml.safe_dump(KGS), encoding="utf-8")
    return path


# ------------------------------------------------------------------------ help / entry
def test_python_dash_m_help_lists_every_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "daf_okn", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for command in ("pull", "export", "analyze", "visualize", "package", "stack-health"):
        assert command in result.stdout


@pytest.mark.parametrize(
    "command", ["pull", "export", "analyze", "visualize", "package", "stack-health"]
)
def test_every_command_has_help(command: str, capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([command, "--help"])
    assert exit_info.value.code == 0
    assert f"daf-okn {command}" in capsys.readouterr().out


def test_version_flag(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"daf-okn {__version__}"


def test_missing_command_is_an_argument_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2


def test_console_script_is_declared() -> None:
    import tomllib

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"]["daf-okn"] == "daf_okn.cli:main"
    module, _, attribute = pyproject["project"]["scripts"]["daf-okn"].partition(":")
    assert callable(getattr(__import__(module, fromlist=[attribute]), attribute))


# ---------------------------------------------------------------------------- pull
def test_pull_list_reads_a_local_kgs_file(tmp_path: Path, capsys) -> None:
    assert main(["pull", "list", "--kgs-path", str(_kgs_file(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert out.index("alpha") < out.index("zeta")  # sorted by shortname
    assert "2 graphs" in out
    assert "https://example.org/zeta/sparql" in out


def test_pull_snapshot_round_trips_a_local_kgs_file(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "snap" / "kgs.yaml"
    code = main(
        ["pull", "snapshot", "--kgs-path", str(_kgs_file(tmp_path)), "--out", str(out_path)]
    )
    assert code == 0
    assert yaml.safe_load(out_path.read_text(encoding="utf-8")) == KGS
    assert "wrote 2 graph entries" in capsys.readouterr().out


def test_pull_save_snapshot_alias_is_accepted() -> None:
    args = build_parser().parse_args(["pull", "save-snapshot"])
    assert args.pull_command in {"snapshot", "save-snapshot"}


def test_pull_reports_malformed_registry_file_without_a_traceback(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- not\n- a mapping\n", encoding="utf-8")
    assert main(["pull", "list", "--kgs-path", str(bad)]) == 1
    assert "error: malformed kgs.yaml" in capsys.readouterr().err


def test_pull_missing_file_is_a_reported_error(tmp_path: Path, capsys) -> None:
    assert main(["pull", "list", "--kgs-path", str(tmp_path / "nope.yaml")]) == 1
    assert "error:" in capsys.readouterr().err


def test_pull_query_requires_shortname_and_query() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["pull", "query", "--shortname", "alpha"])
    assert exit_info.value.code == 2
    args = build_parser().parse_args(
        ["pull", "--timeout", "5", "query", "--shortname", "alpha", "--sparql", "ASK {}"]
    )
    assert (args.timeout, args.shortname, args.sparql) == (5.0, "alpha", "ASK {}")


# -------------------------------------------------------------------------- export
def test_export_writes_graph_json_from_a_vault(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out" / "g.json"
    assert main(["export", "--repo", str(FIXTURE_VAULT), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "graph: cognitive\n" in printed  # plain vault: named after its directory
    assert "vault: cognitive" in printed
    document = GraphDocument.load_json(out)
    pages = {node.id for node in document.nodes if node.attributes.get("entity_role") == "document"}
    topics = {node.id for node in document.nodes if node.attributes.get("entity_role") == "concept"}
    assert len(pages) == 11
    assert topics == {
        "concept:cognitive/pattern_separation",
        "concept:mathematics/bayesian_networks",
        "concept:mathematics/free_energy_principle",
        "concept:mathematics/markov_blanket",
        "concept:relative_links/nested_page",
        "concept:spaced_folder/social_ecological_systems",
    }
    assert {node.id for node in document.nodes} == pages | topics
    assert pages.isdisjoint(topics)
    for topic in topics:
        owner = topic.removeprefix("concept:")
        assert owner in pages
        assert {
            edge.relation
            for edge in document.edges
            if edge.source == owner and edge.target == topic
        } == {"schema:about", "dcterms:subject"}
    assert document.validate() == []


def test_export_names_a_plain_vault_after_its_directory(tmp_path: Path) -> None:
    vault = tmp_path / "My Notes"
    vault.mkdir()
    (vault / "a.md").write_text("[[b]]", encoding="utf-8")
    (vault / "b.md").write_text("", encoding="utf-8")
    out = tmp_path / "g.json"
    assert main(["export", "--repo", str(vault), "--out", str(out)]) == 0
    assert GraphDocument.load_json(out).name == "my-notes"


def test_export_accepts_name_and_options(tmp_path: Path) -> None:
    out = tmp_path / "g.json"
    code = main(
        [
            "export",
            "--repo",
            str(FIXTURE_VAULT),
            "--out",
            str(out),
            "--name",
            "my-notes",
            "--keep-redirects",
            "--no-wikilinks",
        ]
    )
    assert code == 0
    document = GraphDocument.load_json(out)
    assert document.name == "my-notes"
    assert {edge.origin for edge in document.edges} <= {"explicit", "redirect", "entity_model"}
    assert {edge.relation for edge in document.edges if edge.origin == "entity_model"} == {
        "schema:about",
        "dcterms:subject",
    }
    assert any(node.node_type == "redirect" for node in document.nodes)


def test_export_uses_environment_default_and_rejects_bad_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAF_OKN_COGNITIVE_REPO", raising=False)
    with pytest.raises(SystemExit, match="--repo is required"):
        main(["export", "--out", str(tmp_path / "g.json")])
    with pytest.raises(SystemExit, match="not a directory"):
        main(["export", "--repo", str(tmp_path / "missing"), "--out", str(tmp_path / "g.json")])

    monkeypatch.setenv("DAF_OKN_COGNITIVE_REPO", str(FIXTURE_VAULT))
    out = tmp_path / "from_env.json"
    assert build_parser().parse_args(["export"]).repo == str(FIXTURE_VAULT)
    assert main(["export", "--out", str(out)]) == 0
    assert out.is_file()


# -------------------------------------------------------------------------- analyze
def test_analyze_writes_report(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "analysis"
    assert main(["analyze", "--graph", str(_graph_file(tmp_path)), "--out-dir", str(out_dir)]) == 0
    report = json.loads((out_dir / "graph_report.json").read_text(encoding="utf-8"))
    assert report["graph_name"] == "mini-kg"
    assert report["metrics"]["node_count"] == 3
    assert report["metrics"]["edge_count"] == 2
    assert "nodes=3 edges=2" in capsys.readouterr().out


def test_analyze_fails_on_invalid_graph_but_still_writes_report(tmp_path: Path, capsys) -> None:
    doc = GraphDocument(
        name="broken", nodes=[NodeRecord("a", "A")], edges=[EdgeRecord("a", "ghost", "related")]
    )
    path = doc.save_json(tmp_path / "broken.json")
    assert main(["analyze", "--graph", str(path), "--out-dir", str(tmp_path / "r")]) == 1
    assert "problem:" in capsys.readouterr().err
    assert (tmp_path / "r" / "graph_report.json").is_file()


def test_analyze_missing_graph_is_a_reported_error(tmp_path: Path, capsys) -> None:
    assert main(["analyze", "--graph", str(tmp_path / "none.json")]) == 1
    assert "error:" in capsys.readouterr().err


# ------------------------------------------------------------------------ visualize
def test_visualize_writes_figure_and_dashboard(tmp_path: Path) -> None:
    figure, dashboard = tmp_path / "f" / "net.png", tmp_path / "w" / "dash.html"
    code = main(
        [
            "visualize",
            "--graph",
            str(_graph_file(tmp_path)),
            "--figure",
            str(figure),
            "--dashboard",
            str(dashboard),
        ]
    )
    assert code == 0
    assert figure.read_bytes().startswith(b"\x89PNG")
    html = dashboard.read_text(encoding="utf-8")
    assert "mini-kg" in html and "https://registry.okn.us/" in html


def test_visualize_can_skip_outputs_and_takes_metrics(tmp_path: Path) -> None:
    graph = _graph_file(tmp_path)
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"node_count": 3}), encoding="utf-8")
    dashboard = tmp_path / "d.html"
    figure = tmp_path / "f.png"
    code = main(
        [
            "visualize",
            "--graph",
            str(graph),
            "--no-figure",
            "--metrics",
            str(metrics),
            "--dashboard",
            str(dashboard),
            "--figure",
            str(figure),
        ]
    )
    assert code == 0
    assert dashboard.is_file() and not figure.exists()

    code = main(["visualize", "--graph", str(graph), "--no-dashboard", "--figure", str(figure)])
    assert code == 0 and figure.is_file()


def test_visualize_rejects_non_object_metrics(tmp_path: Path) -> None:
    metrics = tmp_path / "m.json"
    metrics.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(SystemExit, match="JSON object"):
        main(
            [
                "visualize",
                "--graph",
                str(_graph_file(tmp_path)),
                "--no-figure",
                "--metrics",
                str(metrics),
                "--dashboard",
                str(tmp_path / "d.html"),
            ]
        )


def test_visualize_unknown_layout_is_a_reported_error(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "visualize",
            "--graph",
            str(_graph_file(tmp_path)),
            "--layout",
            "nope",
            "--figure",
            str(tmp_path / "f.png"),
            "--no-dashboard",
        ]
    )
    assert code == 1
    assert "unsupported layout" in capsys.readouterr().err


# --------------------------------------------------------------------------- package
def test_package_writes_contribution_bundle(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "pkg"
    code = main(
        [
            "package",
            "--graph",
            str(_graph_file(tmp_path)),
            "--out-dir",
            str(out_dir),
            "--entry-shortname",
            "mini-kg",
            "--entry-title",
            "Mini",
            "--entry-description",
            "A tiny graph.",
            "--entry-homepage",
            "https://example.org/mini",
            "--contact",
            "email=me@example.org;github=me;label=Me",
        ]
    )
    assert code == 0
    assert "Wrote package" in capsys.readouterr().out
    assert (out_dir / "mini-kg.nq").is_file()
    assert (out_dir / "registry" / "docs" / "registry" / "kgs" / "mini-kg.md").is_file()
    assert (out_dir / "checklist.md").is_file()


def test_package_exits_one_and_lists_problems_for_incomplete_entry(tmp_path: Path, capsys) -> None:
    code = main(
        ["package", "--graph", str(_graph_file(tmp_path)), "--out-dir", str(tmp_path / "pkg")]
    )
    assert code == 1
    assert "missing contacts in entry inputs" in capsys.readouterr().out


def test_package_format_choice_is_validated() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["package", "--graph", "g.json", "--out-dir", "o", "--fmt", "pdf"])
    assert exit_info.value.code == 2


def test_package_invalid_contact_json_is_a_reported_error(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "package",
            "--graph",
            str(_graph_file(tmp_path)),
            "--out-dir",
            str(tmp_path / "p"),
            "--contact",
            "{not json",
        ]
    )
    assert code == 1
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("defect", ["dangling", "unsafe-shortname"])
def test_package_cli_rejects_invalid_contribution(tmp_path: Path, defect: str) -> None:
    doc = GraphDocument.load_json(_graph_file(tmp_path))
    if defect == "dangling":
        doc.edges.append(EdgeRecord("area/a", "missing"))
    graph = doc.save_json(tmp_path / "invalid.json")
    out_dir = tmp_path / "package"
    shortname = "../escaped" if defect == "unsafe-shortname" else "mini-kg"
    args = [
        "package",
        "--graph",
        str(graph),
        "--out-dir",
        str(out_dir),
        "--entry-shortname",
        shortname,
        "--entry-description",
        "Fixture",
        "--entry-homepage",
        "https://example.org",
        "--contact",
        "email=me@example.org",
    ]

    result = subprocess.run(
        [sys.executable, "-m", "daf_okn", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert not (tmp_path / "escaped.nq").exists()


def test_package_cli_rejects_aliased_output_before_writing(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "package"
    out_dir.mkdir()
    graph_output = out_dir / "mini-kg.nq"
    graph_output.write_text("preserve", encoding="utf-8")
    (out_dir / "checklist.md").symlink_to(graph_output.name)

    code = main(
        [
            "package",
            "--graph",
            str(_graph_file(tmp_path)),
            "--out-dir",
            str(out_dir),
            "--entry-shortname",
            "mini-kg",
            "--entry-description",
            "Fixture",
            "--entry-homepage",
            "https://example.org",
            "--contact",
            "email=me@example.org",
        ]
    )

    assert code == 1
    assert "alias" in capsys.readouterr().out
    assert graph_output.read_text(encoding="utf-8") == "preserve"
    assert not (out_dir / "registry").exists()


# --------------------------------------------------------------------- stack-health
STACK_FILES = (
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "scripts/gate.sh",
    "tasks.yaml",
)


def _stack_checkout(tmp_path: Path) -> Path:
    """A checkout satisfying the roster entry written by ``_roster_file``."""
    root = tmp_path / "checkout"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    for name in STACK_FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content\n", encoding="utf-8")
    return root


def _roster_file(tmp_path: Path, root: Path) -> Path:
    roster = {
        "daf_root": str(root.parent),
        "repos": [
            {
                "name": "daf-okn",
                "path": str(root),
                "branch": "main",
                "require_board": True,
                "require_sidecar": False,
                "gate_cmd": "bash scripts/gate.sh",
                "required_files": list(STACK_FILES),
                "board_path": str(root / "tasks.yaml"),
            }
        ],
    }
    path = tmp_path / "roster.json"
    path.write_text(json.dumps(roster), encoding="utf-8")
    return path


def test_stack_health_passes_for_a_satisfied_checkout(tmp_path: Path, capsys) -> None:
    root = _stack_checkout(tmp_path)
    roster = _roster_file(tmp_path, root)
    code = main(["stack-health", "--roster", str(roster), "--checkout", str(root)])
    health = json.loads(capsys.readouterr().out)
    assert code == 0
    assert health["status"] == "pass"
    assert health["native_gate"] == "not_run"


def test_stack_health_fails_on_a_missing_declared_file(tmp_path: Path, capsys) -> None:
    root = _stack_checkout(tmp_path)
    (root / "uv.lock").unlink()
    roster = _roster_file(tmp_path, root)
    code = main(["stack-health", "--roster", str(roster), "--checkout", str(root)])
    health = json.loads(capsys.readouterr().out)
    assert code == 1
    assert health["status"] == "fail"
    files = {check["name"]: check for check in health["checks"]}
    assert files["required_files"]["detail"] == "missing: uv.lock"


def test_stack_health_reads_stdin(tmp_path: Path, capsys, monkeypatch) -> None:
    root = _stack_checkout(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_roster_file(tmp_path, root).read_text()))
    assert main(["stack-health", "--roster", "-", "--checkout", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["checkout"] == str(root)


def test_stack_health_unknown_member_is_a_reported_error(tmp_path: Path, capsys) -> None:
    root = _stack_checkout(tmp_path)
    roster = _roster_file(tmp_path, root)
    code = main(
        ["stack-health", "--roster", str(roster), "--member", "daf-nope", "--checkout", str(root)]
    )
    assert code == 1
    assert "roster has no member 'daf-nope'" in capsys.readouterr().err


def test_stack_health_malformed_roster_is_a_reported_error(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "roster.json"
    bad.write_text("{", encoding="utf-8")
    assert main(["stack-health", "--roster", str(bad)]) == 1
    assert "roster is not valid JSON" in capsys.readouterr().err


def test_stack_health_requires_a_roster_argument() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["stack-health"])
    assert exit_info.value.code == 2
