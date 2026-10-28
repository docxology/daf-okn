"""Read-only consumer of the ``daf-stack`` roster contract.

``daf-stack-doctor roster`` prints the DAF stack manifest as JSON: ``daf_root``
plus one entry per member with ``name``, ``path``, ``branch``, ``gate_cmd``,
``required_files`` and the board/sidecar requirements. Because the roster is
the documented cross-repo contract, this public checkout can verify -- offline
-- that a stack entry names it and that the entry's declared requirements hold.

Nothing in this module runs the declared gate, writes files, or reaches the
network. A passing observation therefore means "the roster's declared
requirements hold for these bytes on disk", never "the gate passed".
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypedDict

__all__ = [
    "DEFAULT_BOARD",
    "OBSERVATION_SCHEMA",
    "SIDECAR_MANIFEST",
    "MemberCheck",
    "Roster",
    "RosterEntry",
    "RosterError",
    "StackHealth",
    "check_member",
    "parse_roster",
    "read_branch",
]

OBSERVATION_SCHEMA = "daf-okn.stack-roster/1"
SIDECAR_MANIFEST = ".docxology/manifest.toml"
DEFAULT_BOARD = "tasks.yaml"


class RosterError(ValueError):
    """Raised when a roster payload is malformed or names no usable member."""


@dataclass(frozen=True)
class RosterEntry:
    """One stack member exactly as the roster declares it.

    Attributes:
        name: Member name, e.g. ``"daf-okn"``.
        path: Absolute root of the checkout the roster expects.
        branch: Expected Git branch, or ``None`` when the roster declares none.
        require_board: Whether the member must carry an operator board.
        require_sidecar: Whether the member must carry a Sidecar manifest.
        gate_cmd: The member's declared native gate command, or ``None``.
        required_files: Checkout-relative paths the member must contain.
        board_path: Explicit board path, or ``None`` for ``<path>/tasks.yaml``.
    """

    name: str
    path: Path
    branch: str | None
    require_board: bool
    require_sidecar: bool
    gate_cmd: str | None
    required_files: tuple[str, ...]
    board_path: Path | None


@dataclass(frozen=True)
class Roster:
    """The parsed roster: an inferred DAF root plus every member."""

    daf_root: Path | None
    entries: tuple[RosterEntry, ...]

    def select(self, name: str) -> RosterEntry:
        """Return the single member called ``name``.

        Args:
            name: Exact roster member name.

        Returns:
            The matching entry.

        Raises:
            RosterError: If no member has that name; the message lists the
                names the roster does declare.
        """
        for entry in self.entries:
            if entry.name == name:
                return entry
        known = ", ".join(entry.name for entry in self.entries) or "none"
        raise RosterError(f"roster has no member {name!r}; known members: {known}")


class MemberCheck(TypedDict):
    """One declared requirement and whether the checkout satisfies it."""

    name: str
    ok: bool
    detail: str


class StackHealth(TypedDict):
    """Offline comparison of a roster entry against one checkout on disk."""

    schema: str
    status: Literal["pass", "fail"]
    member: str
    roster_entry_path: str
    checkout: str
    expected_branch: str | None
    measured_branch: str | None
    checks: list[MemberCheck]
    native_gate: Literal["not_run"]


def _require(payload: dict[str, Any], key: str, where: str) -> Any:
    if key not in payload:
        raise RosterError(f"{where}: missing {key!r}")
    return payload[key]


def _text(value: object, field: str, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RosterError(f"{where}: {field} must be a non-empty string, got {value!r}")
    return value


def _optional_text(value: object, field: str, where: str) -> str | None:
    return None if value is None else _text(value, field, where)


def _flag(value: object, field: str, where: str) -> bool:
    if not isinstance(value, bool):
        raise RosterError(f"{where}: {field} must be a boolean, got {value!r}")
    return value


def _required_files(raw: object, where: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise RosterError(f"{where}: required_files must be a non-empty list, got {raw!r}")
    files: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise RosterError(f"{where}: required_files entry must be a string, got {item!r}")
        pure = PurePosixPath(item)
        # WHY: a traversal or absolute entry would make the membership check read
        # outside the checkout it claims to describe.
        if pure.is_absolute() or ".." in pure.parts:
            raise RosterError(
                f"{where}: required_files entry {item!r} must stay inside the checkout"
            )
        files.append(item)
    return tuple(files)


def _entry(raw: object, index: int) -> RosterEntry:
    if not isinstance(raw, dict):
        raise RosterError(f"repos[{index}] must be an object, got {type(raw).__name__}")
    name = _text(_require(raw, "name", f"repos[{index}]"), "name", f"repos[{index}]")
    where = f"repos[{index}] ({name})"
    path = Path(_text(_require(raw, "path", where), "path", where))
    if not path.is_absolute():
        raise RosterError(f"{where}: path must be absolute, got {path}")
    board_text = _optional_text(_require(raw, "board_path", where), "board_path", where)
    return RosterEntry(
        name=name,
        path=path,
        branch=_optional_text(_require(raw, "branch", where), "branch", where),
        require_board=_flag(_require(raw, "require_board", where), "require_board", where),
        require_sidecar=_flag(_require(raw, "require_sidecar", where), "require_sidecar", where),
        gate_cmd=_optional_text(_require(raw, "gate_cmd", where), "gate_cmd", where),
        required_files=_required_files(_require(raw, "required_files", where), where),
        board_path=Path(board_text) if board_text else None,
    )


def parse_roster(text: str) -> Roster:
    """Parse the JSON printed by ``daf-stack-doctor roster``.

    Args:
        text: Complete stdout of the roster command.

    Returns:
        The validated roster; member order is preserved.

    Raises:
        RosterError: If the text is not JSON, is not the documented roster
            object shape, has a malformed member entry, or repeats a member
            name.

    Example:
        ``parse_roster(text).select("daf-okn")``
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise RosterError(f"roster is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RosterError(f"roster must be a JSON object, got {type(payload).__name__}")
    repos = payload.get("repos")
    if not isinstance(repos, list) or not repos:
        raise RosterError(f"roster must contain a non-empty 'repos' list, got {repos!r}")
    entries = tuple(_entry(raw, index) for index, raw in enumerate(repos))
    names = [entry.name for entry in entries]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise RosterError(f"roster repeats member names: {', '.join(repeated)}")
    daf_root = _optional_text(payload.get("daf_root"), "daf_root", "roster")
    return Roster(daf_root=Path(daf_root) if daf_root else None, entries=entries)


def _git_dir(checkout: Path) -> Path | None:
    """Return the Git directory for ``checkout``, following a worktree ``.git`` file."""
    marker = Path(checkout) / ".git"
    if marker.is_dir():
        return marker
    if not marker.is_file():
        return None
    try:
        raw = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    prefix = "gitdir:"
    if not raw.startswith(prefix):
        return None
    target = Path(raw[len(prefix) :].strip())
    return target if target.is_absolute() else (Path(checkout) / target).resolve()


def read_branch(checkout: Path) -> str | None:
    """Return the branch named by the checkout's Git ``HEAD``, when readable.

    A worktree or submodule ``.git`` file is followed to its ``gitdir``; nothing
    here shells out to Git.

    Args:
        checkout: Repository root to inspect.

    Returns:
        The branch name, or ``None`` for a detached HEAD, an unreadable ``HEAD``
        or a ``.git`` file that does not resolve to a Git directory. A detached
        HEAD has no branch, so a declared branch then fails rather than
        passing by default.
    """
    git_dir = _git_dir(checkout)
    if git_dir is None:
        return None
    try:
        raw = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    prefix = "ref: refs/heads/"
    if not raw.startswith(prefix) or len(raw) == len(prefix):
        return None
    return raw[len(prefix) :]


def _path_check(entry: RosterEntry, checkout: Path) -> MemberCheck:
    same = entry.path.resolve() == checkout
    relation = "matches" if same else "differs from"
    return {
        "name": "path",
        "ok": same,
        "detail": f"roster path {entry.path} {relation} {checkout}",
    }


def _branch_check(entry: RosterEntry, checkout: Path, measured: str | None) -> MemberCheck:
    if entry.branch is None:
        return {"name": "branch", "ok": True, "detail": "roster declares no expected branch"}
    if measured is None:
        return {
            "name": "branch",
            "ok": False,
            "detail": f"cannot read a branch from {checkout / '.git' / 'HEAD'}",
        }
    return {
        "name": "branch",
        "ok": measured == entry.branch,
        "detail": f"expected {entry.branch}, measured {measured}",
    }


def _files_check(entry: RosterEntry, checkout: Path) -> MemberCheck:
    missing = [item for item in entry.required_files if not (checkout / item).exists()]
    detail = (
        f"missing: {', '.join(missing)}"
        if missing
        else f"{len(entry.required_files)} declared file(s) present"
    )
    return {"name": "required_files", "ok": not missing, "detail": detail}


def _gate_check(entry: RosterEntry, checkout: Path) -> MemberCheck:
    if entry.gate_cmd is None:
        return {"name": "gate", "ok": False, "detail": "roster declares no gate_cmd"}
    try:
        tokens = shlex.split(entry.gate_cmd)
    except ValueError as error:
        return {"name": "gate", "ok": False, "detail": f"gate_cmd is not shell-parseable: {error}"}
    # Only path-shaped tokens are checked; a bare command name (pytest, uv) has
    # nothing to resolve against the checkout without executing it.
    relative = [token for token in tokens if "/" in token and not token.startswith("-")]
    if not relative:
        return {
            "name": "gate",
            "ok": True,
            "detail": f"declared {entry.gate_cmd!r}; no checkout-relative path to check",
        }
    missing = [token for token in relative if not (checkout / token).exists()]
    if missing:
        return {
            "name": "gate",
            "ok": False,
            "detail": f"gate_cmd names missing path(s): {', '.join(missing)}",
        }
    return {
        "name": "gate",
        "ok": True,
        "detail": f"declared {entry.gate_cmd!r}; present: {', '.join(relative)}",
    }


def _board_check(entry: RosterEntry, checkout: Path) -> MemberCheck:
    if not entry.require_board:
        return {"name": "board", "ok": True, "detail": "not required by the roster"}
    if entry.board_path is None:
        board = checkout / DEFAULT_BOARD
    else:
        board = entry.board_path.resolve()
        # WHY: a declared board outside the checkout under test would let a
        # mismatched checkout collect a passing board check from another tree.
        if board != checkout and checkout not in board.parents:
            return {
                "name": "board",
                "ok": False,
                "detail": (
                    f"roster board_path {entry.board_path} is outside the checkout {checkout}"
                ),
            }
    present = board.is_file()
    return {
        "name": "board",
        "ok": present,
        "detail": f"{board} {'exists' if present else 'is missing'}",
    }


def _sidecar_check(entry: RosterEntry, checkout: Path) -> MemberCheck:
    if not entry.require_sidecar:
        return {"name": "sidecar", "ok": True, "detail": "not required by the roster"}
    manifest = checkout / SIDECAR_MANIFEST
    present = manifest.is_file()
    return {
        "name": "sidecar",
        "ok": present,
        "detail": f"{manifest} {'exists' if present else 'is missing'}",
    }


def check_member(entry: RosterEntry, checkout: Path) -> StackHealth:
    """Compare one roster entry against an on-disk checkout.

    Every declared requirement produces one check: ``path`` (the roster names
    this checkout), ``branch`` (the Git ``HEAD`` names the expected branch),
    ``required_files``, ``gate`` (a declared command whose relative paths
    exist), ``board`` and ``sidecar``. A declared ``board_path`` must stay
    inside the checkout, so a mismatched checkout cannot borrow another tree's
    board.

    Args:
        entry: Member entry obtained from :func:`parse_roster`.
        checkout: Directory to compare; resolved before comparison.

    Returns:
        A JSON-compatible observation. ``status`` is ``pass`` only when every
        check holds. ``native_gate`` is always ``not_run``: no command is
        executed, so this observation never stands in for gate evidence.

    Example:
        ``check_member(entry, Path("."))["status"]``
    """
    root = Path(checkout).resolve()
    measured = read_branch(root)
    checks = [
        _path_check(entry, root),
        _branch_check(entry, root, measured),
        _files_check(entry, root),
        _gate_check(entry, root),
        _board_check(entry, root),
        _sidecar_check(entry, root),
    ]
    return {
        "schema": OBSERVATION_SCHEMA,
        "status": "pass" if all(check["ok"] for check in checks) else "fail",
        "member": entry.name,
        "roster_entry_path": str(entry.path),
        "checkout": str(root),
        "expected_branch": entry.branch,
        "measured_branch": measured,
        "checks": checks,
        "native_gate": "not_run",
    }
