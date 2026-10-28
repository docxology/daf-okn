"""Tests for the read-only ``daf-stack`` roster consumer.

Every case uses a roster document in the shape ``daf-stack-doctor roster``
prints and real files on disk; no observation result is stubbed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from daf_okn.core.stack_roster import (
    DEFAULT_BOARD,
    OBSERVATION_SCHEMA,
    RosterError,
    StackHealth,
    check_member,
    parse_roster,
    read_branch,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The requirements the daf-stack manifest declares for daf-okn.
STACK_REQUIRED_FILES = (
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "scripts/gate.sh",
    "tasks.yaml",
)
START_GATE = "bash scripts/gate.sh"


def _checkout(tmp_path: Path) -> Path:
    """Create a checkout that satisfies ``_entry`` without touching the project."""
    root = tmp_path / "daf-okn"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    for name in STACK_REQUIRED_FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content\n", encoding="utf-8")
    return root


def _entry(root: Path, **overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "name": "daf-okn",
        "path": str(root),
        "branch": "main",
        "require_board": True,
        "require_sidecar": False,
        "gate_cmd": START_GATE,
        "required_files": list(STACK_REQUIRED_FILES),
        "board_path": str(root / DEFAULT_BOARD),
    }
    entry.update(overrides)
    return entry


def _roster(*entries: dict[str, object]) -> str:
    return json.dumps(
        {"daf_root": str(Path(str(entries[0]["path"])).parent), "repos": list(entries)}
    )


def _health(entry_payload: dict[str, object], checkout: Path) -> StackHealth:
    entry = parse_roster(_roster(entry_payload)).select("daf-okn")
    return check_member(entry, checkout)


def _by_name(health: StackHealth) -> dict[str, dict[str, object]]:
    return {check["name"]: check for check in health["checks"]}


class TestParseRoster:
    """Tests for parse_roster()."""

    def test_parses_the_documented_roster_shape(self, tmp_path: Path) -> None:
        """Every documented field survives parsing, including the DAF root."""
        root = _checkout(tmp_path)
        roster = parse_roster(_roster(_entry(root)))
        assert roster.daf_root == root.parent
        [entry] = roster.entries
        assert (entry.name, entry.path, entry.branch) == ("daf-okn", root, "main")
        assert (entry.require_board, entry.require_sidecar) == (True, False)
        assert entry.gate_cmd == START_GATE
        assert entry.required_files == STACK_REQUIRED_FILES
        assert entry.board_path == root / DEFAULT_BOARD
        assert roster.select("daf-okn") is entry

    def test_null_optional_values_are_preserved(self, tmp_path: Path) -> None:
        """A null branch, gate and board path parse to None instead of failing."""
        entry = parse_roster(
            _roster(_entry(tmp_path, branch=None, gate_cmd=None, board_path=None))
        ).entries[0]
        assert (entry.branch, entry.gate_cmd, entry.board_path) == (None, None, None)

    def test_select_names_the_known_members(self, tmp_path: Path) -> None:
        """Selecting an absent member reports the names the roster does declare."""
        roster = parse_roster(_roster(_entry(tmp_path)))
        with pytest.raises(RosterError, match="known members: daf-okn"):
            roster.select("daf-jev")

    def test_invalid_json_is_rejected(self) -> None:
        """Non-JSON input raises instead of being treated as an empty roster."""
        with pytest.raises(RosterError, match="not valid JSON"):
            parse_roster("{not json")

    def test_non_object_payload_is_rejected(self) -> None:
        """The roster document itself must be a JSON object."""
        with pytest.raises(RosterError, match="must be a JSON object"):
            parse_roster("[]")

    @pytest.mark.parametrize("payload", ["{}", '{"repos": []}', '{"repos": {}}'])
    def test_repos_must_be_a_non_empty_list(self, payload: str) -> None:
        """A roster without members cannot prove membership."""
        with pytest.raises(RosterError, match="non-empty 'repos' list"):
            parse_roster(payload)

    def test_entry_must_be_an_object(self) -> None:
        """Non-object entries name their index in the error."""
        with pytest.raises(RosterError, match=r"repos\[0\] must be an object"):
            parse_roster('{"repos": ["daf-okn"]}')

    def test_missing_name_is_rejected(self, tmp_path: Path) -> None:
        """The member name is required."""
        payload = _entry(tmp_path)
        del payload["name"]
        with pytest.raises(RosterError, match="missing 'name'"):
            parse_roster(_roster(payload))

    def test_empty_name_is_rejected(self, tmp_path: Path) -> None:
        """An empty member name would match nothing and is rejected."""
        with pytest.raises(RosterError, match="name must be a non-empty string"):
            parse_roster(_roster(_entry(tmp_path, name="")))

    def test_relative_member_path_is_rejected(self, tmp_path: Path) -> None:
        """The roster path is documented as absolute; a relative one is ambiguous."""
        with pytest.raises(RosterError, match="path must be absolute"):
            parse_roster(_roster(_entry(tmp_path, path="daf-okn")))

    def test_duplicate_member_names_are_rejected(self, tmp_path: Path) -> None:
        """Ambiguous member names fail instead of selecting one silently."""
        payload = _entry(tmp_path)
        with pytest.raises(RosterError, match="repeats member names: daf-okn"):
            parse_roster(_roster(payload, payload))

    @pytest.mark.parametrize("value", [[], "README.md", [7]])
    def test_required_files_must_be_a_non_empty_list_of_strings(
        self, tmp_path: Path, value: object
    ) -> None:
        """Malformed required_files cannot declare files to check."""
        with pytest.raises(RosterError, match="required_files"):
            parse_roster(_roster(_entry(tmp_path, required_files=value)))

    @pytest.mark.parametrize("value", ["../escape.md", "/etc/passwd"])
    def test_required_files_must_stay_inside_the_checkout(self, tmp_path: Path, value: str) -> None:
        """Entries outside the checkout are refused rather than probed."""
        with pytest.raises(RosterError, match="must stay inside the checkout"):
            parse_roster(_roster(_entry(tmp_path, required_files=[value])))

    def test_boolean_flags_are_type_checked(self, tmp_path: Path) -> None:
        """``require_board`` accepts only a real boolean."""
        with pytest.raises(RosterError, match="require_board must be a boolean"):
            parse_roster(_roster(_entry(tmp_path, require_board="yes")))

    def test_gate_command_must_be_text(self, tmp_path: Path) -> None:
        """A numeric gate command is a roster error, not a truthy value."""
        with pytest.raises(RosterError, match="gate_cmd must be a non-empty string"):
            parse_roster(_roster(_entry(tmp_path, gate_cmd=3)))


class TestReadBranch:
    """Tests for read_branch()."""

    def test_reads_the_branch_from_git_head(self, tmp_path: Path) -> None:
        """The plain ref form resolves to the branch name."""
        root = _checkout(tmp_path)
        assert read_branch(root) == "main"

    def test_missing_head_is_unavailable(self, tmp_path: Path) -> None:
        """No .git directory means no measured branch."""
        assert read_branch(tmp_path) is None

    @pytest.mark.parametrize(
        "head",
        ["a1b2c3d4\n", "ref: refs/tags/v1\n", "ref: refs/heads/\n", "gitdir: ../elsewhere/.git\n"],
    )
    def test_unresolvable_head_is_unavailable(self, tmp_path: Path, head: str) -> None:
        """Detached, tag, empty and worktree gitfiles carry no branch name."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text(head, encoding="utf-8")
        assert read_branch(tmp_path) is None

    def test_undecodable_head_is_unavailable(self, tmp_path: Path) -> None:
        """Invalid UTF-8 in HEAD is unavailable, not an exception."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_bytes(b"\xff\xfe")
        assert read_branch(tmp_path) is None

    def test_worktree_git_file_resolves_the_git_directory(self, tmp_path: Path) -> None:
        """A worktree .git file points at the real gitdir holding HEAD."""
        checkout = tmp_path / "checkout"
        checkout.mkdir()
        gitdir = tmp_path / "main" / ".git" / "worktrees" / "checkout"
        gitdir.mkdir(parents=True)
        (gitdir / "HEAD").write_text("ref: refs/heads/feature\n", encoding="utf-8")
        (checkout / ".git").write_text("gitdir: ../main/.git/worktrees/checkout\n")
        assert read_branch(checkout) == "feature"

    def test_worktree_git_file_with_a_missing_git_directory_is_unavailable(
        self, tmp_path: Path
    ) -> None:
        """.git files that resolve nowhere report no branch instead of raising."""
        checkout = tmp_path / "checkout"
        checkout.mkdir()
        (checkout / ".git").write_text("gitdir: ../nowhere/.git\n", encoding="utf-8")
        assert read_branch(checkout) is None

    def test_git_file_without_the_gitdir_prefix_is_unavailable(self, tmp_path: Path) -> None:
        """Only Git's own .git file format is followed."""
        (tmp_path / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")
        assert read_branch(tmp_path) is None

    def test_unreadable_git_file_is_unavailable(self, tmp_path: Path) -> None:
        """An undecodable .git file reports no branch."""
        (tmp_path / ".git").write_bytes(b"\xff\xfe")
        assert read_branch(tmp_path) is None


class TestCheckMember:
    """Tests for check_member()."""

    def test_satisfied_checkout_passes(self, tmp_path: Path) -> None:
        """Every declared requirement holds, so the observation passes."""
        root = _checkout(tmp_path)
        health = _health(_entry(root), root)
        assert health["status"] == "pass"
        assert [check["name"] for check in health["checks"]] == [
            "path",
            "branch",
            "required_files",
            "gate",
            "board",
            "sidecar",
        ]
        assert health["native_gate"] == "not_run"

    def test_observation_records_scope(self, tmp_path: Path) -> None:
        """The payload names the schema, member, both paths and both branches."""
        root = _checkout(tmp_path)
        health = _health(_entry(root), root)
        assert health["schema"] == OBSERVATION_SCHEMA
        assert (health["member"], health["roster_entry_path"], health["checkout"]) == (
            "daf-okn",
            str(root),
            str(root),
        )
        assert (health["expected_branch"], health["measured_branch"]) == ("main", "main")

    def test_roster_pointing_at_another_checkout_fails(self, tmp_path: Path) -> None:
        """A roster entry that names a different path is a failure with both paths."""
        root = _checkout(tmp_path)
        other = tmp_path / "other"
        other.mkdir()
        health = _health(_entry(other), root)
        assert health["status"] == "fail"
        path_check = _by_name(health)["path"]
        assert path_check["ok"] is False
        assert str(other) in path_check["detail"] and str(root) in path_check["detail"]

    def test_branch_mismatch_fails(self, tmp_path: Path) -> None:
        """A checkout on another branch fails the declared branch."""
        root = _checkout(tmp_path)
        health = _health(_entry(root, branch="release"), root)
        assert health["status"] == "fail"
        assert _by_name(health)["branch"] == {
            "name": "branch",
            "ok": False,
            "detail": "expected release, measured main",
        }

    def test_unreadable_branch_fails_a_declared_branch(self, tmp_path: Path) -> None:
        """A detached HEAD cannot prove the declared branch."""
        root = _checkout(tmp_path)
        (root / ".git" / "HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
        health = _health(_entry(root), root)
        assert health["status"] == "fail"
        assert health["measured_branch"] is None
        assert "cannot read a branch" in _by_name(health)["branch"]["detail"]

    def test_undeclared_branch_is_not_compared(self, tmp_path: Path) -> None:
        """A roster entry without a branch leaves the branch check informational."""
        root = _checkout(tmp_path)
        (root / ".git" / "HEAD").write_text("detached\n", encoding="utf-8")
        health = _health(_entry(root, branch=None), root)
        assert health["status"] == "pass"
        assert _by_name(health)["branch"]["detail"] == "roster declares no expected branch"

    def test_missing_required_file_fails_and_names_it(self, tmp_path: Path) -> None:
        """Each declared file must exist in the checkout."""
        root = _checkout(tmp_path)
        (root / "uv.lock").unlink()
        (root / "scripts" / "gate.sh").unlink()
        health = _health(_entry(root), root)
        assert health["status"] == "fail"
        assert _by_name(health)["required_files"]["detail"] == "missing: uv.lock, scripts/gate.sh"

    def test_missing_gate_script_fails(self, tmp_path: Path) -> None:
        """A declared gate whose relative script is absent fails."""
        root = _checkout(tmp_path)
        (root / "scripts" / "gate.sh").unlink()
        health = _health(_entry(root), root)
        assert health["status"] == "fail"
        assert "scripts/gate.sh" in _by_name(health)["gate"]["detail"]

    def test_gate_without_a_relative_path_is_presence_only(self, tmp_path: Path) -> None:
        """A bare-command gate has no path to resolve, so only its presence counts."""
        root = _checkout(tmp_path)
        health = _health(_entry(root, gate_cmd="uv run pytest -q"), root)
        assert health["status"] == "pass"
        assert "no checkout-relative path to check" in _by_name(health)["gate"]["detail"]

    def test_undeclared_gate_fails(self, tmp_path: Path) -> None:
        """A member without a gate cannot be verified by the coordinator."""
        root = _checkout(tmp_path)
        health = _health(_entry(root, gate_cmd=None), root)
        assert health["status"] == "fail"
        assert _by_name(health)["gate"]["detail"] == "roster declares no gate_cmd"

    def test_unparseable_gate_fails(self, tmp_path: Path) -> None:
        """Unbalanced quoting in the gate command is reported, not raised."""
        root = _checkout(tmp_path)
        health = _health(_entry(root, gate_cmd='bash "unclosed'), root)
        assert health["status"] == "fail"
        assert "not shell-parseable" in _by_name(health)["gate"]["detail"]

    def test_missing_board_fails_when_required(self, tmp_path: Path) -> None:
        """A required board must exist at the declared path."""
        root = _checkout(tmp_path)
        (root / DEFAULT_BOARD).unlink()
        health = _health(_entry(root), root)
        assert health["status"] == "fail"
        assert _by_name(health)["board"]["detail"].endswith("is missing")

    def test_board_outside_the_checkout_fails(self, tmp_path: Path) -> None:
        """A board declared elsewhere cannot pass against a mismatched checkout."""
        root = _checkout(tmp_path)
        payload = _entry(root, board_path=str(PROJECT_ROOT / DEFAULT_BOARD))
        health = _health(payload, root)
        assert health["status"] == "fail"
        assert _by_name(health)["board"] == {
            "name": "board",
            "ok": False,
            "detail": (
                f"roster board_path {PROJECT_ROOT / DEFAULT_BOARD} "
                f"is outside the checkout {root.resolve()}"
            ),
        }

    def test_board_falls_back_to_the_checkout_board(self, tmp_path: Path) -> None:
        """An entry without board_path uses <checkout>/tasks.yaml."""
        root = _checkout(tmp_path)
        health = _health(_entry(root, board_path=None), root)
        assert health["status"] == "pass"
        assert _by_name(health)["board"]["detail"].startswith(str(root / DEFAULT_BOARD))

    def test_board_is_skipped_when_not_required(self, tmp_path: Path) -> None:
        """A member that requires no board is not failed for lacking one."""
        root = _checkout(tmp_path)
        payload = _entry(root, require_board=False, board_path=str(root / "board" / "tasks.yaml"))
        health = _health(payload, root)
        assert health["status"] == "pass"
        assert _by_name(health)["board"]["detail"] == "not required by the roster"

    def test_required_sidecar_manifest_is_checked(self, tmp_path: Path) -> None:
        """A Sidecar requirement resolves to .docxology/manifest.toml."""
        root = _checkout(tmp_path)
        failing = _health(_entry(root, require_sidecar=True), root)
        assert failing["status"] == "fail"
        assert _by_name(failing)["sidecar"]["detail"].endswith("is missing")
        (root / ".docxology").mkdir()
        (root / ".docxology" / "manifest.toml").write_text("", encoding="utf-8")
        passing = _health(_entry(root, require_sidecar=True), root)
        assert passing["status"] == "pass"
        assert _by_name(passing)["sidecar"]["ok"] is True

    def test_public_checkout_satisfies_the_stack_requirements(self) -> None:
        """This repository meets the requirements daf-stack declares for it."""
        payload = _entry(
            PROJECT_ROOT,
            branch=read_branch(PROJECT_ROOT),
            board_path=str(PROJECT_ROOT / DEFAULT_BOARD),
        )
        health = _health(payload, PROJECT_ROOT)
        checks = _by_name(health)
        assert checks["path"]["ok"] is True
        assert checks["required_files"] == {
            "name": "required_files",
            "ok": True,
            "detail": f"{len(STACK_REQUIRED_FILES)} declared file(s) present",
        }
        assert checks["gate"] == {
            "name": "gate",
            "ok": True,
            "detail": f"declared {START_GATE!r}; present: scripts/gate.sh",
        }
        assert checks["board"]["ok"] is True
        assert health["status"] == "pass", health["checks"]
